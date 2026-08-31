"""Vòng viết đề: `write`, `balance`, `check`, `prune`."""

from __future__ import annotations

import argparse
import sys
import time

from app.content.exam import balance as balancer
from app.content.exam import blueprint as bp
from app.content.exam import check as checker
from app.content.exam import writer
from app.content.exam_cli.paths import _gateway, blueprint_path, workdir_for
from app.services.llm.base import LLMQuotaExhausted
from app.services.llm.router import Tier


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


def cmd_prompt(args: argparse.Namespace) -> int:
    """In ĐÚNG hai chuỗi sẽ gửi đi cho một ô — không gọi model.

    Có lệnh này vì trong một phiên gỡ lỗi tôi đã phải dựng lại prompt bằng tay
    hai lần để trả lời cùng một câu: "nó thật sự gửi đi cái gì". Chuỗi dựng tay
    thì không chứng minh được điều gì — nó có thể khác chuỗi thật ở đúng chỗ
    đang hỏng.
    """
    from app.content.exam.prompts import _PROMPT_FOR, SYSTEM, _system_for, prompt_for

    plan = bp.load(blueprint_path(args.slug))
    found = [
        (part.part, slot) for part in plan.parts for slot in part.slots if slot.id == args.slot
    ]
    if not found:
        print(f"không có ô {args.slot!r} trong blueprint", file=sys.stderr)
        return 1
    part, slot = found[0]
    system = SYSTEM if part == 5 else _system_for(part, slot)
    user = prompt_for(slot) if part == 5 else _PROMPT_FOR[part](slot)

    print(f"── Ô {slot.id} · part {part} · câu {slot.number}")
    for key, value in vars(slot).items():
        if value not in ("", [], None):
            print(f"   {key}: {value}")
    print(f"\n── SYSTEM ({len(system):,} ký tự)\n{system}")
    print(f"\n── USER ({len(user):,} ký tự)\n{user}")
    total = len(system) + len(user)
    print(f"\n── tổng {total:,} ký tự (~{total // 4:,} token)")
    return 0
