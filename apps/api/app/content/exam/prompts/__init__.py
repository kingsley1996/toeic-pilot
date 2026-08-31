"""Lời nhắc của chặng sinh đề — mỗi part một file.

Tách khỏi `writer.py` vì hai thứ đổi vì hai lý do khác nhau: lời nhắc đổi khi
cách ra đề đổi, còn cơ chế (tách khối, làm sạch, gọi model, ghi tệp) đổi khi
pipeline đổi.

Tách tiếp thành package vì cùng lý do ở mức nhỏ hơn — sửa prompt của Part 4
không nên phải cuộn qua sáu part khác, và một file 800 dòng xếp lộn xộn
(Part 1, rồi Part 3, rồi luật hình, rồi Part 4, rồi Part 2) làm việc đó thành
bắt buộc.

    contract.py   các MỐC của hợp đồng định dạng
    graphic.py    định dạng bảng + luật GIAO ĐIỂM, dùng chung Part 3/4/7
    part1..7.py   system prompt và bộ dựng user prompt của từng part

`__init__` giữ bảng tra và TÁI XUẤT toàn bộ bề mặt cũ, nên `writer`, `check` và
các test không phải đổi một dòng nào.

Xem prompt thật của một ô: `generate_exam prompt --slug <slug> --slot <id>`.
"""

from __future__ import annotations

from collections.abc import Callable

from app.content.exam.blueprint import GRAPHIC_POSITION, QuestionSlot
from app.content.exam.prompts.contract import (
    BLANK,
    GRAPHIC_MARKER,
    PASSAGE_MARKER,
    PHOTO_MARKER,
    SCRIPT_MARKER,
)
from app.content.exam.prompts.graphic import (
    GRAPHIC_FORMAT,
    GRAPHIC_RULES_TEMPLATE,
    graphic_note,
    graphic_rules,
)
from app.content.exam.prompts.part1 import SYSTEM_PART1, prompt_for_part1
from app.content.exam.prompts.part2 import SYSTEM_PART2, prompt_for_part2
from app.content.exam.prompts.part3 import SYSTEM_PART3, prompt_for_part3
from app.content.exam.prompts.part4 import SYSTEM_PART4, prompt_for_part4
from app.content.exam.prompts.part5 import EXAMPLE_EXPLANATION, SYSTEM, prompt_for
from app.content.exam.prompts.part6 import SYSTEM_PART6, prompt_for_part6
from app.content.exam.prompts.part7 import SYSTEM_PART7, prompt_for_part7

__all__ = [
    "BLANK",
    "EXAMPLE_EXPLANATION",
    "GRAPHIC_FORMAT",
    "GRAPHIC_MARKER",
    "GRAPHIC_RULES_TEMPLATE",
    "PASSAGE_MARKER",
    "PHOTO_MARKER",
    "SCRIPT_MARKER",
    "SYSTEM",
    "SYSTEM_PART1",
    "SYSTEM_PART2",
    "SYSTEM_PART3",
    "SYSTEM_PART4",
    "SYSTEM_PART6",
    "SYSTEM_PART7",
    "graphic_note",
    "graphic_rules",
    "prompt_for",
    "prompt_for_part1",
    "prompt_for_part2",
    "prompt_for_part3",
    "prompt_for_part4",
    "prompt_for_part6",
    "prompt_for_part7",
]


def _system_for(part: int, slot: QuestionSlot) -> str:
    """System prompt của một lượt viết, ghép thêm luật hình khi cụm có hình.

    Part 3/4 nhận **cả** định dạng lẫn luật câu hỏi về hình — ở đó bốn lựa chọn
    chính là bốn mục trên hình. Part 7 chỉ nhận **định dạng**: hình của nó là
    NGỮ LIỆU, câu hỏi hỏi về nội dung chứ không bắt chọn giữa bốn hàng (§28).

    Bản đầu chỉ ghép cho Part 3/4, nên Part 7 được bảo "xuất một khối [GRAPHIC]"
    mà không bao giờ được cho biết khối đó trông thế nào — và mô hình vẽ bảng
    bằng ký tự `+---+`, thứ không đọc ra dữ liệu nào.
    """
    base = _SYSTEM_FOR.get(part, SYSTEM)
    if part in (3, 4) and slot.graphic:
        return base + graphic_rules(GRAPHIC_POSITION[part])
    if part == 7 and any(slot.passages):
        return f"{base}\n\nTHE GRAPHIC BLOCKS\n{GRAPHIC_FORMAT}"
    return base


_SYSTEM_FOR = {
    1: SYSTEM_PART1,
    2: SYSTEM_PART2,
    3: SYSTEM_PART3,
    4: SYSTEM_PART4,
    6: SYSTEM_PART6,
    7: SYSTEM_PART7,
}
_PROMPT_FOR: dict[int, Callable[[QuestionSlot], str]] = {
    1: prompt_for_part1,
    2: prompt_for_part2,
    3: prompt_for_part3,
    4: prompt_for_part4,
    6: prompt_for_part6,
    7: prompt_for_part7,
}
