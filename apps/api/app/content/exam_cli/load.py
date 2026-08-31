"""Đưa đề vào database: `load`, và wizard tương tác."""

from __future__ import annotations

import argparse
import sys

from app.content.exam import blueprint as bp
from app.content.exam import loader
from app.content.exam_cli.paths import blueprint_path, workdir_for


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
