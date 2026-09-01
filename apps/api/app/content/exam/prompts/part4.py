"""Part 4 — Talks."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.content.exam.prompts.graphic import graphic_note
from app.services.labels import LABELS

SYSTEM_PART4 = exam_prompt("part4_system").render()


def prompt_for_part4(slot: QuestionSlot) -> str:
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    return (
        f"Viết một bài nói Part 4 và ba câu hỏi về nó.\n"
        f"- {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        f"- MỘT người nói, giọng: {slot.voices[0]}\n"
        f"- Ba câu hỏi, theo đúng thứ tự này:\n{kinds}\n"
        f"- Mọi dữ kiện mà ba câu hỏi cần phải được NÓI RA trong bài."
        + graphic_note(slot, "Bài nói")
    )
