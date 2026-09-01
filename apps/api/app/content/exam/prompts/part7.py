"""Part 7 — Reading Comprehension."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.services.labels import LABELS

SYSTEM_PART7 = exam_prompt("part7_system").render()


def prompt_for_part7(slot: QuestionSlot) -> str:
    docs = []
    for index, spec in enumerate(slot.passages, start=1):
        if spec:
            kind, _, detail = spec.partition(":")
            docs.append(f"  Ngữ liệu {index}: HÌNH dạng `{kind.strip()}` — {detail.strip()}")
        else:
            docs.append(f"  Ngữ liệu {index}: văn bản")
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    graphics = [spec for spec in slot.passages if spec]
    note = (
        f"\n- Ngữ liệu nào ghi là HÌNH thì xuất một khối [GRAPHIC] cho nó và "
        f"KHÔNG xuất [PASSAGE] cho nó — hình không có chữ chạy. Cụm này có "
        f"{sum(1 for p in slot.passages if not p)} khối [PASSAGE] và "
        f"{len(graphics)} khối [GRAPHIC]."
        if graphics
        else ""
    )
    multi = (
        "\n- ÍT NHẤT MỘT câu phải cần CẢ HAI (hoặc cả ba) ngữ liệu mới trả lời "
        "được: một ngữ liệu cho cái tên/ngày/số, ngữ liệu kia nói cái đó nghĩa là gì."
        if len(slot.passages) > 1
        else ""
    )
    listed = "\n".join(docs)
    return (
        f"Viết một cụm Part 7.\n"
        f"- {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        f"- ĐÚNG {len(slot.passages)} khối [PASSAGE], mỗi ngữ liệu một khối:\n{listed}\n"
        f"- {len(slot.question_types)} câu hỏi, theo đúng thứ tự này:\n{kinds}"
        f"{multi}{note}"
    )
