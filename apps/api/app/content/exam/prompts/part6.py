"""Part 6 — Text Completion."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.content.exam.prompts.contract import BLANK
from app.services.labels import LABELS

SYSTEM_PART6 = exam_prompt("part6_system").render(BLANK=BLANK)


def prompt_for_part6(slot: QuestionSlot) -> str:
    kind = LABELS[slot.topic].label_vi
    lines = []
    insert_at = 4
    for index, (code, grammar) in enumerate(
        zip(slot.question_types, slot.grammars, strict=True), start=1
    ):
        detail = f" — {LABELS[grammar].label_vi}" if grammar else ""
        if code == "PART_6_SENTENCE_INSERTION":
            insert_at = index
        lines.append(f"  Chỗ trống ({index}): {LABELS[code].label_vi}{detail}")
    listed = "\n".join(lines)
    return (
        f"Viết một văn bản Part 6 và bốn câu hỏi cho bốn chỗ trống.\n"
        f"- {kind}\n"
        f"- Nội dung: {slot.context}\n"
        f"- Bốn chỗ trống, theo đúng thứ tự này:\n{listed}\n"
        f"- Chỗ trống ({insert_at}) là câu ĐIỀN CÂU: bốn lựa chọn là bốn câu hoàn chỉnh, "
        f"và ba câu sai phải sai vì KHÔNG HỢP với đoạn văn quanh nó, không phải "
        f"vì sai ngữ pháp."
    )
