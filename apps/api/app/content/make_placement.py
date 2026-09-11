"""CLI lắp đề placement — logic nằm ở `app/services/placement_builder.py`.

    uv run python -m app.content.make_placement                # tạo/cập nhật draft
    uv run python -m app.content.make_placement --publish      # duyệt + xuất bản
    uv run python -m app.content.make_placement --preview     # chỉ xem, không ghi

Mã không thể ở đây: không gì với tới từ `app/main.py` được phép import
`app.content` (image production thiếu extra `content` — xem luật ở
`app/services/placement_builder.py`).
"""

import argparse
import sys
from typing import Any

from app.core.database import SessionLocal
from app.services.placement_builder import (
    PLACEMENT_SLUG,
    PRIORITY,
    SOURCE_SLUG,
    PlacementError,
    breakdown,
    build,
    select_questions,
)


def _describe(info: dict[str, Any]) -> None:
    for part in info["parts"]:
        print(f"  part {part['part']}: {part['count']} câu")
        for code, n in part["types"].items():
            mark = " ←" if code in PRIORITY.get(part["part"], ()) else ""
            print(f"      {n:>2}  {code}{mark}")
        if part["missing_priority"]:
            print(f"      THIẾU dạng khó: {', '.join(part['missing_priority'])}")
    print(f"  nhãn grammar: {info['grammar_code_count']} mã")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        default=PLACEMENT_SLUG,
        help="slug đề placement. Đề đã published KHÔNG dựng lại được — đổi đề dưới "
        "chân người học; dùng slug mới.",
    )
    parser.add_argument(
        # Nguồn là thứ đổi theo từng lượt dựng, không phải một hằng số của công
        # cụ: mỗi đề mới sinh ra là một nguồn mới có thể lấy. Mặc định giữ đề cũ
        # để lệnh không đổi nghĩa với người đang gõ nó theo thói quen.
        "--source",
        default=SOURCE_SLUG,
        help=f"slug đề nguồn để rút câu (mặc định {SOURCE_SLUG})",
    )
    parser.add_argument("--publish", action="store_true", help="xuất bản sau khi lắp")
    parser.add_argument(
        "--preview", action="store_true", help="chỉ in phân bố dạng câu, không ghi gì"
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            if args.preview:
                _source, chosen, type_labels, grammar_labels = select_questions(db, args.source)
                print(f"{args.slug} ← {args.source}: {len(chosen)} câu (preview, chưa ghi)")
                _describe(breakdown(chosen, type_labels, grammar_labels))
                return
            info = build(db, slug=args.slug, source_slug=args.source, publish=args.publish)
        except PlacementError as failure:
            print(failure, file=sys.stderr)
            raise SystemExit(1) from None
    print(
        f"{info['slug']}: {info['question_count']} câu ({'published' if args.publish else 'draft'})"
    )
    _describe(info)


if __name__ == "__main__":
    main()
