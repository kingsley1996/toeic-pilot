"""Part 3 — Conversations."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.content.exam.prompts.graphic import graphic_note
from app.services.labels import LABELS

SYSTEM_PART3 = exam_prompt("part3_system").render()


def prompt_for_part3(slot: QuestionSlot) -> str:
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    cast = ", ".join(slot.voices)
    return (
        f"Viết một cuộc hội thoại Part 3 và ba câu hỏi về nó.\n"
        f"- {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        f"- Số người nói: {len(slot.voices)}. Chỉ dùng đúng các tên giọng này, "
        f"mỗi người một giọng: {cast}\n"
        f"- Ba câu hỏi, theo đúng thứ tự này:\n{kinds}\n"
        f"- Mọi dữ kiện mà ba câu hỏi cần phải được NÓI RA trong hội thoại."
        + graphic_note(slot, "Hội thoại")
    )
