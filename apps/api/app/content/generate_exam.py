"""Sinh một đề TOEIC — bốn chặng, chạy riêng từng chặng.

    uv run python -m app.content.generate_exam plan  --slug tp-form-03
    uv run python -m app.content.generate_exam write --slug tp-form-03 [--limit 3]
    uv run python -m app.content.generate_exam check --slug tp-form-03 [--verify]
    uv run python -m app.content.generate_exam load  --slug tp-form-03 --token <editor token>

Chạy NGOÀI LUỒNG, trong image worker: `app.content` không bao giờ được import từ
`app/main.py`, và ảnh production build không có extra `content`.

Mỗi chặng đọc và ghi tệp dưới `content/generated/<slug>/`, nên chạy lại chặng sau
không phải trả tiền lại cho chặng trước. Một lượt sinh cả đề tốn hàng chục phút
và SẼ đứt — hết quota, mất mạng, máy ngủ.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from app.content.exam import balance as balancer
from app.content.exam import blueprint as bp
from app.content.exam import check as checker
from app.content.exam import loader, writer
from app.content.settings import content_settings
from app.services.llm.base import LLMQuotaExhausted
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier

DEFAULT_ROOT = Path("content/generated")


def workdir_for(slug: str) -> Path:
    return DEFAULT_ROOT / slug


def blueprint_path(slug: str) -> Path:
    return workdir_for(slug) / "blueprint.json"


def _gateway(model: str | None = None) -> Gateway:
    """Dựng gateway y hệt `enrich_skills`, kể cả `resolve_feature`.

    Không nối `resolve_feature` thì màn cấu hình ở `/admin/ai/providers` lưu
    được, hiện ra được, và không ảnh hưởng gì tới thứ thật sự chạy — kiểu hỏng
    tệ nhất, vì mọi thứ trông như đang hoạt động.

    `model` (dạng `provider/model`) ghi đè cả hai tầng bằng đúng một model —
    đường đi mà wizard `interact` và `--model` dùng. `resolve_feature` vẫn chạy
    trước: một hàng `ai_feature_config` khớp feature sẽ thắng override này.
    """
    from app.content.enrich_skills import _providers_for, _split
    from app.core.ai_budget import Budget
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.redis_client import get_redis
    from app.services.ai_features import resolver_for

    routes = {
        Tier.CHEAP: _split(settings.llm_tier_cheap),
        Tier.STRONG: _split(settings.llm_tier_strong),
    }
    if model:
        routes = {tier: _split(model) for tier in routes}
    providers = _providers_for({provider for provider, _ in routes.values()})
    session = SessionLocal()
    return Gateway(
        providers=providers,
        routes=routes,
        budget=Budget(limit_micro=settings.ai_daily_budget_micro_usd),
        redis_client=get_redis(),
        session_factory=SessionLocal,
        resolve_feature=resolver_for(session),
    )


def cmd_plan(args: argparse.Namespace) -> int:
    title = args.title or f"TOEIC Pilot — {args.slug}"
    builder = {
        1: bp.build_part1,
        2: bp.build_part2,
        3: bp.build_part3,
        4: bp.build_part4,
        5: bp.build_part5,
        6: bp.build_part6,
        7: bp.build_part7,
    }[args.part]
    path = blueprint_path(args.slug)
    plan = bp.merge(bp.load(path) if path.exists() else None, builder(args.slug, title, args.seed))
    problems = bp.validate(plan)
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        return 1
    bp.save(plan, path)
    shape = ", ".join(f"part {plan_.part}: {len(plan_.slots)} ô" for plan_ in plan.parts)
    print(f"{path} — {shape}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    plan = bp.load(blueprint_path(args.slug))
    workdir = workdir_for(args.slug)
    todo = writer.pending(plan, workdir)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} ô còn thiếu tệp dán.\n", flush=True)

    gateway = _gateway(args.model)
    tier = Tier(args.tier)
    written = 0
    started = time.monotonic()
    for index, slot in enumerate(todo, start=1):
        part = next(p.part for p in plan.parts if slot in p.slots)
        # In TRƯỚC lượt gọi, không chỉ sau.
        #
        # Một lượt gọi mất một tới ba phút, và chỉ in sau khi xong nghĩa là suốt
        # thời gian đó màn hình đứng im — không phân biệt được "đang viết" với
        # "đã treo". Dòng này nói đang ở ô nào và còn bao nhiêu ô.
        #
        # `flush` là bắt buộc chứ không phải cho đẹp: khi đầu ra đi vào tệp hay
        # ống dẫn, Python đệm theo khối, nên `tail -f` không thấy gì cho tới khi
        # đầy đệm — đúng lúc người ta cần nhìn nhất thì nó im.
        print(f"  … [{index}/{len(todo)}] {slot.id} (part {part})", flush=True)
        each = time.monotonic()
        try:
            block = writer.write_slot(gateway, slot, tier, part, args.max_tokens)
        except LLMQuotaExhausted as quota:
            # Hạn mức NGÀY không tự hết sau ba mươi giây. Backoff ở đây sẽ cày
            # hết mọi ô còn lại, hỏng y hệt nhau, và chôn mất dòng nói đúng
            # nguyên nhân. Dừng hẳn, và những ô đã ghi vẫn còn trên đĩa.
            print(f"\nHết hạn mức: {quota}", file=sys.stderr)
            print(f"Đã ghi {written} ô. Chạy lại lệnh này sau để làm tiếp.", file=sys.stderr)
            return 3
        except Exception as failure:  # noqa: BLE001 - một ô hỏng không dừng cả lượt
            print(
                f"  ✗ [{index}/{len(todo)}] {slot.id} sau {time.monotonic() - each:.0f}s: "
                f"{failure}",
                file=sys.stderr,
                flush=True,
            )
            continue
        # Part 1 trả về hai khối. Mô tả ảnh đi ra hiện vật RIÊNG: parser từ chối
        # dòng lạ sau các đáp án, nên nhét nó vào tệp dán là làm cả khối không
        # đọc được.
        photo, block = writer.split_photo(block)
        if photo:
            photo_path = workdir / "photos" / f"{slot.id}.txt"
            photo_path.parent.mkdir(parents=True, exist_ok=True)
            photo_path.write_text(photo + "\n")
        # Bảng của Part 3/4 cũng là hiện vật riêng, cùng lý do như mô tả ảnh: nó
        # là DỮ LIỆU để vẽ và để sinh chữ thay ảnh, không phải dòng để dán.
        tables, block = writer.split_all(block, writer.GRAPHIC_MARKER)
        for order, table in enumerate(tables, start=1):
            # Một cụm Part 7 có thể mang hai hình, nên tên tệp mang số thứ tự.
            # Ô chỉ có một hình vẫn giữ tên cũ `<slot>.txt`, để Part 3/4 không
            # phải sinh lại.
            suffix = "" if len(tables) == 1 else f"-{order}"
            table_path = workdir / "graphics" / f"{slot.id}{suffix}.txt"
            table_path.parent.mkdir(parents=True, exist_ok=True)
            table_path.write_text(table + "\n")
        path = writer.save_slot(workdir, slot, block)
        written += 1
        print(
            f"  ✓ [{index}/{len(todo)}] {slot.id} sau {time.monotonic() - each:.0f}s  {path}",
            flush=True,
        )
    minutes = (time.monotonic() - started) / 60
    print(f"\nĐã ghi {written}/{len(todo)} ô trong {minutes:.1f} phút.", flush=True)
    return 0


# Bộ sinh ảnh nằm ngoài repo — cùng lệnh mà bộ skill sprite dùng, và cũng là
# đường đã vẽ xong khung avatar và linh vật. Gọi qua tiến trình con chứ không
# import: nó chạy trong một virtualenv riêng có mflux, thứ không nằm trong
# `pyproject.toml` của API và không được phép nằm ở đó.
IMAGE_GEN = Path.home() / ".claude" / "skills" / "_imagegen" / "image_gen.py"


def cmd_photo(args: argparse.Namespace) -> int:
    """Vẽ ảnh Part 1 từ phần mô tả mà chặng `write` đã lưu.

    Hàng đợi vẫn là một TRUY VẤN trên thư mục: ô nào có mô tả mà chưa có tệp PNG.
    Xoá một tấm ảnh là cách đưa nó vẽ lại — không có cột trạng thái nào phải giữ
    đồng bộ với sự tồn tại của tệp.

    **Ảnh phải được người xem trước khi gắn** (kế hoạch §8). Mô hình vẽ thừa một
    người là chuyện đã xảy ra thật ở bộ linh vật, và ở đây nó làm hỏng đúng thứ
    bốn câu mô tả dựa vào. Lệnh này chỉ vẽ ra đĩa; không có gì tự gắn vào câu hỏi.
    """
    import subprocess

    from app.content.exam.photos import photo_prompt, to_greyscale

    plan = bp.load(blueprint_path(args.slug))
    workdir = workdir_for(args.slug)
    out_dir = workdir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = []
    for part in plan.parts:
        if part.part != 1:
            continue
        for slot in part.slots:
            description = workdir / "photos" / f"{slot.id}.txt"
            target = out_dir / f"{slot.id}.png"
            if description.exists() and not target.exists():
                todo.append((slot.id, description, target))
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} tấm cần vẽ.\n")

    drawn = 0
    for slot_id, description, target in todo:
        prompt, avoid = photo_prompt(description.read_text())
        (out_dir / f"{slot_id}.prompt.txt").write_text(f"{prompt}\n\nAvoid: {avoid}\n")
        command = [
            "python3",
            str(IMAGE_GEN),
            "--prompt",
            prompt,
            "--negative",
            avoid,
            "--out",
            str(target),
            "--aspect",
            args.aspect,
            "--seed",
            str(args.seed or plan.seed),
        ]
        print(f"  … {slot_id}")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0 or not target.exists():
            print(f"  ✗ {slot_id}: {result.stderr.strip()[-300:]}", file=sys.stderr)
            continue
        if args.greyscale:
            to_greyscale(target)
        drawn += 1
        print(f"  ✓ {slot_id}  {target}")
    print(f"\nĐã vẽ {drawn}/{len(todo)} tấm. XEM từng tấm trước khi gắn.")
    return 0


def cmd_media(args: argparse.Namespace) -> int:
    """Hỏi NHÀ CUNG CẤP xem media của đề đã lên chưa. `--push` thì đẩy nốt.

    Chặng này tồn tại vì một lỗ có thật và hoàn toàn im lặng: worker TTS ghi clip
    xuống đĩa **local**, còn `audio_public_base_url` trỏ tới Supabase — nên một
    đề vừa nạp xong có đủ hàng `audio_asset`, `validate_question` trả về OK, giao
    diện hiện nút play, và không có gì phát ra. Không truy vấn nào trong database
    thấy được, vì database đúng; thứ sai nằm ở nơi database không nhìn tới.

    Ảnh không dính lỗi này (`import_media` đẩy thẳng lên Cloudinary), nhưng vẫn
    kiểm cả hai: một lệnh trả lời được "đề này phát được chưa" thì đáng tin hơn
    một lệnh chỉ trả lời được nửa câu hỏi.
    """
    from sqlalchemy import func, select

    from app.content.push_media import push, uploader_for
    from app.core.database import SessionLocal
    from app.core.storage import MediaKind, get_driver
    from app.models import (
        ImageAsset,
        PracticeTest,
        PracticeTestQuestion,
        Question,
        QuestionSet,
    )
    from app.models.audio import AudioAsset

    db = SessionLocal()
    test = db.scalar(select(PracticeTest).where(PracticeTest.slug == args.slug))
    if test is None:
        print(f"không có đề `{args.slug}`", file=sys.stderr)
        return 2

    # Media của một đề treo ở HAI tầng (ADR-001 §A4.3): Part 1/2 trên câu, Part
    # 3/4 trên cụm. Chỉ hỏi tầng câu thì lệnh này trả lời "mọi thứ đã lên" cho
    # một đề mà toàn bộ mười ba hội thoại chưa lên — nửa câu trả lời, và là nửa
    # dễ tin nhất vì nó màu xanh.
    rows = db.execute(
        select(
            PracticeTestQuestion.number,
            Question.part,
            AudioAsset.storage_key,
            ImageAsset.storage_key,
        )
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .outerjoin(AudioAsset, AudioAsset.id == Question.audio_asset_id)
        .outerjoin(ImageAsset, ImageAsset.id == Question.image_asset_id)
        .where(PracticeTestQuestion.test_id == test.id)
        .order_by(PracticeTestQuestion.number)
    ).all()

    set_rows = db.execute(
        select(
            func.min(PracticeTestQuestion.number),
            Question.part,
            AudioAsset.storage_key,
            ImageAsset.storage_key,
        )
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .join(QuestionSet, QuestionSet.id == Question.set_id)
        .outerjoin(AudioAsset, AudioAsset.id == QuestionSet.audio_asset_id)
        .outerjoin(ImageAsset, ImageAsset.id == QuestionSet.passage_image_id)
        .where(PracticeTestQuestion.test_id == test.id)
        .group_by(QuestionSet.id, Question.part, AudioAsset.storage_key, ImageAsset.storage_key)
        .order_by(func.min(PracticeTestQuestion.number))
    ).all()
    rows = [*rows, *set_rows]

    media_root = Path("media")
    kinds: tuple[MediaKind, ...] = ("audio", "image")
    missing: dict[MediaKind, list[tuple[str, Path]]] = {"audio": [], "image": []}
    for number, part, audio_key, image_key in rows:
        if args.part is not None and part != args.part:
            continue
        for kind, key in zip(kinds, (audio_key, image_key), strict=True):
            if not key:
                continue
            try:
                get_driver(kind).verify(key)
            except Exception:
                print(f"  ✗ câu {number}: {kind} chưa có ở nhà cung cấp")
                missing[kind].append((key, media_root / key))

    total = sum(len(items) for items in missing.values())
    if not total:
        print("mọi media của đề đã có ở nhà cung cấp.")
        return 0
    if not args.push:
        print(f"\n{total} tệp thiếu. Thêm `--push` để đẩy lên.")
        return 1

    for kind, items in missing.items():
        on_disk = [(key, path) for key, path in items if path.exists()]
        gone = [key for key, path in items if not path.exists()]
        for key in gone:
            print(f"  ✗ {kind} {key}: KHÔNG có trên đĩa, không đẩy được", file=sys.stderr)
        if on_disk:
            tally = push(uploader_for(kind), on_disk)
            print(f"{kind}: đẩy {tally['uploaded']} · lỗi {tally['failed']}")
        if gone:
            return 1
    return 0


def cmd_graphic(args: argparse.Namespace) -> int:
    """Vẽ hình ngữ liệu Part 3/4/7 từ dữ liệu bảng, kèm chữ thay ảnh.

    KHÔNG gọi mô hình ảnh. Hình này là một tài liệu và giá trị của nó nằm ở chữ
    đọc được, thứ mô hình khuếch tán không vẽ đáng tin. Vẽ từ dữ liệu cũng là
    thứ duy nhất khiến chữ thay ảnh sinh ra tự động — và `assign_passage_image`
    TỪ CHỐI (409) một hình ngữ liệu không có chữ thay ảnh.

    Tên ảnh mang **số ô ngữ liệu** (`p7-15-s2.png`) chứ không chỉ số thứ tự: một
    cụm Part 7 có thể có hai hình và chúng gắn vào hai ô khác nhau, nên chặng
    gắn phải đọc được chỗ từ chính tên tệp.
    """
    from app.content.exam.graphics import parse_graphic, render

    plan = bp.load(blueprint_path(args.slug))
    workdir = workdir_for(args.slug)
    made = 0
    problems = 0

    for part in plan.parts:
        for slot in part.slots:
            # Part 3/4: tối đa một hình, gắn vào ô ngữ liệu 1, tệp `<ô>.txt`.
            # Part 7: tối đa ba, tệp `<ô>.txt` hoặc `<ô>-N.txt`, và mỗi cái gắn
            # vào đúng ô ngữ liệu mà blueprint đã chỉ.
            jobs: list[tuple[str, int]] = []
            if slot.graphic:
                jobs.append((f"{slot.id}.txt", 1))
            specs = [index for index, spec in enumerate(slot.passages, start=1) if spec]
            for order, passage_slot in enumerate(specs, start=1):
                suffix = "" if len(specs) == 1 else f"-{order}"
                jobs.append((f"{slot.id}{suffix}.txt", passage_slot))

            for name, passage_slot in jobs:
                source = workdir / "graphics" / name
                if not source.exists():
                    print(f"  ✗ {name}: thiếu dữ liệu bảng", file=sys.stderr)
                    problems += 1
                    continue
                graphic = parse_graphic(source.read_text())
                found = graphic.problems()
                if found:
                    print(f"  ✗ {name}: {'; '.join(found)}", file=sys.stderr)
                    problems += 1
                    continue
                out_dir = workdir / "graphic-images" / f"part{part.part}"
                out_dir.mkdir(parents=True, exist_ok=True)
                stem = f"{slot.id}-s{passage_slot}" if part.part == 7 else slot.id
                target = out_dir / f"{stem}.png"
                render(graphic, target)
                (out_dir / f"{stem}.alt.txt").write_text(graphic.alt_text() + "\n")
                made += 1
                print(f"  ✓ {stem}  {target}", flush=True)

    print(f"\nĐã vẽ {made} hình · {problems} lỗi.")
    return 1 if problems else 0


def cmd_balance(args: argparse.Namespace) -> int:
    plan = bp.load(blueprint_path(args.slug))
    tally = balancer.balance(plan, workdir_for(args.slug), args.part)
    total = sum(tally.values()) or 1
    print(
        "phân bố đáp án sau khi cân: "
        + "  ".join(
            f"{letter}={count} ({count / total * 100:.0f}%)" for letter, count in tally.items()
        )
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    plan = bp.load(blueprint_path(args.slug))
    gateway = _gateway(args.model) if args.verify else None
    try:
        reports = checker.check_blueprint(
            plan, workdir_for(args.slug), gateway, Tier(args.tier), args.verify, args.part
        )
    except LLMQuotaExhausted as quota:
        print(f"\nHết hạn mức: {quota}", file=sys.stderr)
        print("Chạy lại lệnh này sau; các ô đã kiểm không mất gì.", file=sys.stderr)
        return 3

    spread = checker.check_answer_spread(workdir_for(args.slug), plan)
    for problem in spread:
        print(f"  ✗ CẢ ĐỀ: {problem}")

    blocked = [report for report in reports if report.blocked]
    flagged = [report for report in reports if report.flags and not report.blocked]
    for report in reports:
        for problem in report.problems:
            print(f"  ✗ {report.slot_id} (câu {report.number}): {problem}")
        for flag in report.flags:
            print(f"  ⚠ {report.slot_id} (câu {report.number}): {flag}")

    print(
        f"\n{len(reports)} ô · {len(blocked)} chặn nạp · {len(flagged)} cần người nhìn"
        + ("" if args.verify else " · CHƯA đối chiếu đáp án (thêm --verify)")
    )
    # Cờ KHÔNG làm lệnh thất bại: chúng là chỗ người cần nhìn, không phải lỗi.
    # Trộn hai loại lại thì người chạy học cách bỏ qua mã thoát, và lúc đó cả hai
    # loại cùng mất tác dụng.
    return 1 if blocked or spread else 0


def cmd_prune(args: argparse.Namespace) -> int:
    """XOÁ tệp dán của những ô không đạt, để lượt `write` sau sinh lại đúng chúng.

    Xoá chứ không đánh dấu, và đó là cả ý tưởng: hàng đợi của chặng sinh là một
    TRUY VẤN trên thư mục ("ô nào chưa có tệp"), nên xoá một tệp chính là đưa ô
    đó trở lại hàng đợi. Một cột `status` bên cạnh sẽ là trạng thái thứ hai phải
    giữ đồng bộ với sự tồn tại của tệp, và hai nguồn sự thật cho cùng một câu
    hỏi là chỗ chúng lệch nhau.

    Mặc định chỉ loại theo những lỗi CHẮC CHẮN (cú pháp, thiếu `Source`, trùng
    đề bài). `--ambiguity` bật thêm phép kiểm "có mấy phương án điền được" —
    phép kiểm đúng lỗi trội nhất, nhưng nhiễu nhất: người chấm yếu sẽ gật đầu
    với phương án mà người bản ngữ loại ngay, nên nó phải được bật có chủ ý.
    """
    plan = bp.load(blueprint_path(args.slug))
    workdir = workdir_for(args.slug)
    gateway = _gateway(args.model) if args.ambiguity else None
    reports = checker.check_blueprint(
        plan, workdir, gateway, Tier(args.tier), args.ambiguity, args.part
    )

    # Đo NGƯỜI CHẤM trước khi tin nó.
    #
    # Một model nhỏ trả lời phép kiểm mơ hồ bằng phản xạ: đo thật với gemma3 4B,
    # nó trả về đúng chuỗi "AB" cho mọi câu, kể cả những câu mà `whose` vs
    # `which` sai rõ ràng. Nếu cứ thế mà loại thì ta xoá những câu ĐẠT dựa trên
    # một phép đo không đo gì cả — và mỗi lần chạy lại sẽ xoá tiếp, vì câu sinh
    # lại cũng nhận cùng câu trả lời phản xạ ấy.
    #
    # Dấu hiệu: cùng một tập chữ cái lặp lại ở gần hết các câu. Một người chấm
    # thật sẽ cho ra nhiều đáp án khác nhau, vì các câu vốn khác nhau.
    answers = [report.workable for report in reports if report.workable is not None]
    if args.ambiguity and answers:
        modal = max(set(answers), key=answers.count)
        share = answers.count(modal) / len(answers)
        if share >= 0.7:
            print(
                f"  ✗ NGƯỜI CHẤM KHÔNG DÙNG ĐƯỢC: {answers.count(modal)}/{len(answers)} câu "
                f"({share * 100:.0f}%) nhận cùng một câu trả lời ({modal!r}). Đó là phản xạ, "
                f"không phải phán đoán."
            )
            print("     Bỏ qua phép kiểm mơ hồ. Dùng model mạnh hơn làm người chấm rồi chạy lại.")
            args.ambiguity = False

    doomed: list[tuple[str, str]] = []
    for report in reports:
        reasons = [problem for problem in report.problems if problem != "chưa có tệp dán"]
        if args.ambiguity:
            reasons += [flag for flag in report.flags if "phương án điền được" in flag]
        if reasons and report.slot_id not in {slot_id for slot_id, _ in doomed}:
            # Một ô CỤM sinh ba báo cáo, nên cùng một `slot_id` có thể hỏng ba
            # lần. Đơn vị sinh lại là cả cụm (ba câu hỏi về cùng một đoạn thoại),
            # nên nó chỉ được xoá — và chỉ được đếm — đúng một lần.
            doomed.append((report.slot_id, reasons[0]))

    for slot_id, reason in doomed:
        slot = next(s for part in plan.parts for s in part.slots if s.id == slot_id)
        path = writer.paste_path(workdir, slot)
        if path.exists():
            if args.dry_run:
                print(f"  · sẽ xoá {slot_id}: {reason}")
                continue
            path.unlink()
            # Mô tả ảnh đi cùng ô, nên nó cũng phải đi. Để lại thì một ô đã bị
            # loại vẫn còn mô tả của lần viết hỏng, và nếu ô đó không được sinh
            # lại thì `check` vẫn đọc mô tả cũ — một hiện vật mồ côi mô tả một
            # câu hỏi không còn tồn tại.
            for extra in (workdir / "photos", workdir / "graphics"):
                sidecar = extra / f"{slot_id}.txt"
                if sidecar.exists():
                    sidecar.unlink()
            print(f"  ✗ đã xoá {slot_id}: {reason}")

    kept = sum(1 for report in reports if not report.problems)
    print(f"\n{kept} ô giữ lại · {len(doomed)} ô loại" + (" (chạy thử)" if args.dry_run else ""))
    if doomed and not args.dry_run:
        print("Chạy lại `write` để sinh lại đúng những ô vừa loại.")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    plan = bp.load(blueprint_path(args.slug))
    try:
        loader.ensure_test(args.api, args.token, plan)
        for part in plan.parts:
            # `--part` không phải tiện nghi: một đề được nạp từng part một, và
            # `commit_part` CỘNG THÊM câu chứ không thay thế. Nạp lại cả blueprint
            # để thêm Part 1 sẽ dán Part 5 vào đề lần thứ hai.
            if args.part is not None and part.part != args.part:
                continue
            count = loader.load_part(
                args.api, args.token, plan, workdir_for(args.slug), part.part, args.slot
            )
            print(f"  ✓ part {part.part}: {count} cụm")
    except loader.LoadError as failure:
        print(f"  ✗ {failure}", file=sys.stderr)
        return 1
    print(f"\nĐề `{plan.slug}` đã nạp ở trạng thái draft. Duyệt ở /admin/tests/{plan.slug}.")
    return 0


def cmd_interact(args: argparse.Namespace) -> int:
    """Wizard tương tác. Import trễ để `generate_exam` không kéo questionary
    theo khi chỉ dùng các lệnh thường."""
    from app.content.exam_wizard import run_interactive

    return run_interactive(args.slug)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh một đề TOEIC.")
    parser.add_argument("--tier", default=Tier.CHEAP.value, choices=[tier.value for tier in Tier])
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="dựng blueprint")
    plan_cmd.add_argument("--slug", required=True)
    plan_cmd.add_argument("--title")
    plan_cmd.add_argument("--seed", type=int, default=20260822)
    plan_cmd.add_argument("--part", type=int, default=5, choices=(1, 2, 3, 4, 5, 6, 7))
    plan_cmd.set_defaults(func=cmd_plan)

    write_cmd = sub.add_parser("write", help="sinh tệp dán cho các ô còn thiếu")
    write_cmd.add_argument("--slug", required=True)
    write_cmd.add_argument("--limit", type=int, default=0)
    write_cmd.add_argument(
        "--max-tokens",
        type=int,
        default=writer.DEFAULT_MAX_TOKENS,
        help="trần đầu ra mỗi lượt gọi; model suy luận cần rộng, hạn mức TPM lại cần hẹp",
    )
    write_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model (vd `bai/gpt-5.6-sol`). Xem known_models() hoặc wizard interact",
    )
    write_cmd.set_defaults(func=cmd_write)

    balance_cmd = sub.add_parser("balance", help="cân lại vị trí đáp án trên cả đề")
    balance_cmd.add_argument("--slug", required=True)
    balance_cmd.add_argument("--part", type=int, default=None, help="chỉ cân một part")
    balance_cmd.set_defaults(func=cmd_balance)

    photo_cmd = sub.add_parser("photo", help="vẽ ảnh Part 1 từ phần mô tả")
    photo_cmd.add_argument("--slug", required=True)
    photo_cmd.add_argument("--limit", type=int, default=0)
    photo_cmd.add_argument("--aspect", default="4:3")
    # Vẽ lại một tấm bị loại cần một seed KHÁC. Không có cờ này thì xoá tệp rồi
    # chạy lại cho ra đúng tấm ảnh vừa bị loại — hàng đợi làm đúng việc của nó,
    # và người chạy tưởng lệnh hỏng.
    photo_cmd.add_argument("--seed", type=int, default=0)
    # Đen trắng là MẶC ĐỊNH vì đề thi thật in đen trắng; màu là một manh mối mà
    # phòng thi không cho. Cờ tắt tồn tại để xem bản màu khi soi bố cục.
    photo_cmd.add_argument("--no-greyscale", dest="greyscale", action="store_false")
    photo_cmd.set_defaults(greyscale=True)
    photo_cmd.set_defaults(func=cmd_photo)

    media_cmd = sub.add_parser("media", help="media của đề đã lên nhà cung cấp chưa")
    media_cmd.add_argument("--slug", required=True)
    media_cmd.add_argument("--part", type=int, default=None)
    media_cmd.add_argument("--push", action="store_true", help="đẩy nốt phần còn thiếu")
    media_cmd.set_defaults(func=cmd_media)

    graphic_cmd = sub.add_parser("graphic", help="vẽ hình ngữ liệu Part 3/4 từ dữ liệu bảng")
    graphic_cmd.add_argument("--slug", required=True)
    graphic_cmd.set_defaults(func=cmd_graphic)

    check_cmd = sub.add_parser("check", help="kiểm tệp dán")
    check_cmd.add_argument("--slug", required=True)
    check_cmd.add_argument("--verify", action="store_true", help="đối chiếu đáp án bằng LLM")
    check_cmd.add_argument("--part", type=int, default=None, help="chỉ kiểm một part")
    check_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model (vd `bai/gpt-5.6-sol`). Xem known_models() hoặc wizard interact",
    )
    check_cmd.set_defaults(func=cmd_check)

    prune_cmd = sub.add_parser("prune", help="xoá tệp dán của những ô không đạt")
    prune_cmd.add_argument("--slug", required=True)
    prune_cmd.add_argument("--part", type=int, default=None, help="chỉ loại trong một part")
    prune_cmd.add_argument("--dry-run", action="store_true")
    prune_cmd.add_argument(
        "--ambiguity", action="store_true", help="loại cả câu có hơn một phương án điền được"
    )
    prune_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model (vd `bai/gpt-5.6-sol`). Xem known_models() hoặc wizard interact",
    )
    prune_cmd.set_defaults(func=cmd_prune)

    load_cmd = sub.add_parser("load", help="nạp vào database qua đường dán")
    load_cmd.add_argument("--slug", required=True)
    load_cmd.add_argument("--token", required=True, help="token của một tài khoản editor")
    load_cmd.add_argument("--api", default="http://localhost:8000")
    load_cmd.add_argument("--part", type=int, default=None, help="chỉ nạp một part")
    load_cmd.add_argument(
        "--slot", default=None, help="chỉ nạp một ô (vd `p2-01`), lấp vào số câu còn trống"
    )
    load_cmd.set_defaults(func=cmd_load)

    interact_cmd = sub.add_parser(
        "interact",
        help="wizard tương tác: điều khiển cả pipeline bằng menu",
    )
    interact_cmd.add_argument(
        "--slug", default=None, help="đề muốn làm; bỏ trống thì chọn lúc chạy"
    )
    interact_cmd.set_defaults(func=cmd_interact)

    args = parser.parse_args(argv)
    _ = content_settings  # giữ cùng khuôn khởi động với các lệnh content khác
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
