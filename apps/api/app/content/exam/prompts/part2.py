"""Part 2 — Question-Response."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.services.labels import LABELS

SYSTEM_PART2 = exam_prompt("part2_system").render()


def prompt_for_part2(slot: QuestionSlot) -> str:
    kind = LABELS[slot.question_type].label_vi
    ask, reply = slot.voices
    return (
        f"Viết một câu hỏi Part 2.\n"
        f"- Dạng: {kind}\n"
        f"- Bối cảnh: {slot.context}\n"
        f"- Dòng đầu tiên sau [QUESTION] phải là chính xác:\nvoice: {ask}\n"
        f"- Ngay trước (A) phải là chính xác:\nvoice: {reply}\n"
        f"- BA câu đáp, không phải bốn. Hai câu sai phải sai theo một kiểu gọi "
        f"tên được, và phải hấp dẫn với người chỉ nghe được một phần câu hỏi."
    )
