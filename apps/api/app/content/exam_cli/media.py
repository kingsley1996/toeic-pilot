"""Ảnh và hình ngữ liệu: `photo`, `media`, `attach-images`, `graphic`."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from app.content.exam import blueprint as bp
from app.content.exam_cli.paths import blueprint_path, workdir_for

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


def cmd_attach_images(args: argparse.Namespace) -> int:
    """Gắn ảnh tự sinh (Part 1 chụp + graphic Part 3/4/7) vào đề đã nạp.

    Chạy sau `load` và sau `photo`/`graphic` (render ra đĩa). Mỗi part lấy đúng
    chế độ khớp của nó: Part 1 theo số câu, Part 3/4 theo thứ tự cụm, Part 7 theo
    `cụm-sô`. Giấy phép và ghi công điền sẵn cho ảnh do pipeline tự sinh.

    Mặc định CHỈ XEM bảng khớp: ảnh phải được người nhìn trước khi gắn (§8) —
    thêm `--commit` để ghi vào DB.
    """
    from sqlalchemy import select

    from app.content.import_media import (
        IMAGE_SUFFIXES,
        collect,
        image_slots,
        import_images,
        match_files,
        report,
    )
    from app.core.database import SessionLocal
    from app.models.practice import PracticeTest

    workdir = workdir_for(args.slug)

    jobs: list[tuple[int, Path, str]] = []
    for part in (1, 3, 4, 7):
        if args.part is not None and part != args.part:
            continue
        directory = workdir / "images" if part == 1 else workdir / "graphic-images" / f"part{part}"
        if not directory.is_dir() or not any(directory.glob("*")):
            continue
        match = "passage" if part == 7 else ("index" if part in (3, 4) else "number")
        jobs.append((part, directory, match))

    if not jobs:
        print("không có part nào có ảnh để gắn.", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        test = session.scalar(select(PracticeTest).where(PracticeTest.slug == args.slug))
        if test is None:
            print(f"không có đề `{args.slug}`", file=sys.stderr)
            return 2

        any_failed = False
        for part, directory, match in jobs:
            slots = image_slots(session, test, part)
            if not slots:
                print(
                    f"  part {part} không có ô ảnh nào trong DB — chạy load trước",
                    file=sys.stderr,
                )
                any_failed = True
                continue
            files = collect(directory, IMAGE_SUFFIXES)
            pairs, extra, empty = match_files(files, slots, match)
            skipped = [] if args.overwrite else [p for p in pairs if p[1].filled]
            if not args.overwrite:
                pairs = [p for p in pairs if not p[1].filled]
            empty = [s for s in empty if not s.filled]
            report(pairs, extra, empty, kind="image", skipped=skipped)

            if not args.commit:
                continue

            is_partial = part in (3, 4, 7)
            if extra or (empty and not is_partial):
                print("\nDừng: còn file thừa hoặc ô trống không thể bỏ qua.", file=sys.stderr)
                any_failed = True
                continue

            try:
                done = import_images(
                    session,
                    pairs,
                    source_url=args.source_url or f"file://{directory}",
                    license_name=args.license or "generated",
                    attribution=args.attribution or "TOEIC Pilot — ảnh tự sinh",
                    alt_text=args.alt_text,
                )
                session.commit()
                print(f"  đã gắn {done} image cho Part {part}")
            except Exception as exc:
                session.rollback()
                print(f"  ✗ Part {part}: {exc}", file=sys.stderr)
                any_failed = True

    return 1 if any_failed else 0


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
