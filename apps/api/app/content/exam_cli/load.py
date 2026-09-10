"""Đưa đề vào database: `load`, và wizard tương tác."""

from __future__ import annotations

import argparse
import sys

from app.content.exam import blueprint as bp
from app.content.exam import loader
from app.content.exam_cli.label import apply_labels
from app.content.exam_cli.paths import blueprint_path, workdir_for
from app.core.database import SessionLocal


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

    # Nhãn đến từ blueprint, không từ câu chữ, nên `load` (đường API) không tự
    # sinh ra nó — và mỗi lần regen một part là DELETE cả đề rồi nạp lại, kéo
    # theo mọi `question_label` rơi theo CASCADE (FK ondelete). Quên bước này là
    # đề lên production không nhãn, và `make_placement` + màn phân tích kỹ năng
    # im lặng hỏng. Vì vậy tự gắn nhãn ở đây cho lượt nạp TRỌN đề; nạp lẻ một
    # part/slot thì bỏ qua, vì những ô khác chưa có mặt mà `apply_labels` đòi đủ.
    if args.part is None and args.slot is None:
        with SessionLocal() as db:
            written, skipped, problems = apply_labels(db, plan)
        print(f"  nhãn: {written} ghi mới · {skipped} đã có")
        for line in problems[:20]:
            print(f"  ⚠ {line}", file=sys.stderr)
        if len(problems) > 20:
            print(f"  … và {len(problems) - 20} dòng nữa", file=sys.stderr)

    print(f"\nĐề `{plan.slug}` đã nạp ở trạng thái draft. Duyệt ở /admin/tests/{plan.slug}.")
    return 0


def cmd_interact(args: argparse.Namespace) -> int:
    """Wizard tương tác. Import trễ để `generate_exam` không kéo questionary
    theo khi chỉ dùng các lệnh thường."""
    from app.content.exam_wizard import run_interactive

    return run_interactive(args.slug)
