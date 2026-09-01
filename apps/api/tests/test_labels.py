"""Bộ nhãn trong mã phải khớp `planning/docs/toeic_question_label_taxonomy.md`.

Tài liệu là nguồn sự thật vì con người sửa nó; `app/services/labels.py` là bản
sinh ra để chạy. Không có bài test này thì hai bên lệch nhau âm thầm — ai đó
thêm một nhãn vào tài liệu, không ai sinh lại, và nhãn đó vừa "đã được quyết"
vừa "bị hệ thống từ chối" cùng lúc.
"""

import re
from pathlib import Path

from app.services.labels import FACETS, LABELS

TAXONOMY = (
    Path(__file__).resolve().parents[3] / "planning" / "docs" / "toeic_question_label_taxonomy.md"
)


def parse_doc() -> dict[str, tuple[str, set[int]]]:
    codes: dict[str, tuple[str, set[int]]] = {}
    part = 0
    for line in TAXONOMY.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Part "):
            part = int(line[8:].strip())
        elif line.startswith("- `"):
            match = re.match(r"- `([A-Z0-9_]+)` — (.+)", line)
            assert match, f"dòng nhãn sai định dạng: {line!r}"
            code, label = match.group(1), match.group(2).strip()
            if code in codes:
                codes[code][1].add(part)
            else:
                codes[code] = (label, {part})
    return codes


def test_tai_lieu_va_ma_khop_nhau_tung_ma_mot() -> None:
    doc = parse_doc()
    assert set(doc) == set(LABELS), (
        f"chỉ có ở tài liệu: {sorted(set(doc) - set(LABELS))}\n"
        f"chỉ có trong mã:   {sorted(set(LABELS) - set(doc))}"
    )
    for code, (label_vi, parts) in doc.items():
        assert LABELS[code].label_vi == label_vi, code
        assert set(LABELS[code].parts) == parts, code


def test_moi_ma_thuoc_dung_MOT_mat() -> None:
    """Một mã nằm ở hai mặt thì `facet` không còn suy ra được từ `code`.

    Cả pipeline lẫn giao diện đều tra ngược mã ra mặt để biết ghi vào đâu; hai
    mặt cùng một mã sẽ khiến nhãn được ghi vào chỗ tuỳ theo thứ tự duyệt.
    """
    seen: dict[str, str] = {}
    for facet in FACETS:
        for label in facet.labels:
            assert label.code not in seen, f"{label.code} ở cả {seen[label.code]} và {facet.key}"
            seen[label.code] = facet.key


def test_ma_du_ngan_cho_cot_database() -> None:
    """Cột `code` là `String(48)`; mã dài nhất hiện là 36 ký tự.

    Cột cũ `skill_tag` là `String(32)` và `PART_1_PERSON_AND_OBJECT_DESCRIPTION`
    tràn — một lỗi chỉ nổ lúc ghi hàng đầu tiên của Part 1.
    """
    longest = max(LABELS, key=len)
    assert len(longest) <= 48, f"{longest} dài {len(longest)}"
