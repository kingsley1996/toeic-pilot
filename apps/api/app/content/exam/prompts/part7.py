"""Part 7 — Reading Comprehension."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.services.labels import LABELS

SYSTEM_PART7 = exam_prompt("part7_system").render()


def prompt_for_part7(slot: QuestionSlot) -> str:
    # Đánh số khối [PASSAGE] cho từng ô CHỮ, đừng bắt mô hình tự đếm. Một ô hình
    # nằm GIỮA làm nó mất dấu: `p7-15` (chữ + HÌNH + chữ) viết khối thứ nhất, gặp
    # ô hình, rồi dừng — hai lượt sinh liên tiếp đều ra một khối thay vì hai,
    # trong khi ba cụm có hình ở cuối đều đúng. Nói ra "đây là khối thứ hai" là
    # thứ duy nhất phân biệt hai trường hợp đó.
    docs = []
    written = 0
    for index, spec in enumerate(slot.passages, start=1):
        if spec:
            kind, _, detail = spec.partition(":")
            docs.append(
                f"  Ngữ liệu {index}: HÌNH dạng `{kind.strip()}` — {detail.strip()} "
                f"→ KHÔNG có khối [PASSAGE] cho ô này"
            )
        else:
            written += 1
            docs.append(f"  Ngữ liệu {index}: văn bản → khối [PASSAGE] thứ {written}")
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    graphics = [spec for spec in slot.passages if spec]
    text_slots = sum(1 for spec in slot.passages if not spec)
    # Dòng "Tình huống" được viết tay theo `PART7_SETS`, còn ô HÌNH thì
    # `build_part7` lấy từ `PART7_GRAPHIC_POOL` để mỗi đề một khác — nên hai chỗ
    # có thể mô tả hai thứ khác nhau. Nói thẳng cái nào thắng, thay vì để mô
    # hình đoán: bản vẽ đi theo brief hình, và nó là thứ thật sự được render.
    note = (
        f"\n- Ngữ liệu nào ghi là HÌNH thì xuất một khối [GRAPHIC] cho nó và "
        f"KHÔNG xuất [PASSAGE] cho nó — hình không có chữ chạy. Cụm này có "
        f"{sum(1 for p in slot.passages if not p)} khối [PASSAGE] và "
        f"{len(graphics)} khối [GRAPHIC]."
        f"\n- Nếu dòng Tình huống gọi tên một ngữ liệu khác với brief HÌNH ở trên "
        f"thì theo BRIEF HÌNH: đó mới là thứ được vẽ ra. Viết lại phần văn bản "
        f"cho khớp với nó."
        if graphics
        else ""
    )
    multi = (
        "\n- ÍT NHẤT MỘT câu phải cần CẢ HAI (hoặc cả ba) ngữ liệu mới trả lời "
        "được: một ngữ liệu cho cái tên/ngày/số, ngữ liệu kia nói cái đó nghĩa là gì."
        if len(slot.passages) > 1
        else ""
    )
    # Ngân sách chữ tính SẴN ở đây chứ không để mô hình tự nhân. Luật ở
    # `part7_system.md` là 60 từ cho mỗi câu hỏi, và một mô hình được đưa một
    # phép tính sẽ làm sai nó theo hướng ra số nhỏ hơn — đúng cái đã xảy ra với
    # khoảng "90-200 words each".
    budget = 60 * len(slot.question_types)
    budget_line = (
        f"\n- TỔNG khoảng {budget} từ cho {text_slots} khối [PASSAGE] "
        f"(≈{budget // max(text_slots, 1)} từ mỗi khối). Ngắn hơn nhiều là cụm "
        f"không đủ chỗ giấu vế thứ hai của đáp án."
    )
    listed = "\n".join(docs)
    return (
        f"Viết một cụm Part 7.\n"
        f"- {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        # Đếm ô CHỮ, không đếm cả ô hình. Bản cũ viết `len(slot.passages)` rồi ba
        # gạch đầu dòng sau mới đính chính ("Cụm này có 2 khối [PASSAGE] và 1 khối
        # [GRAPHIC]") — hai con số mâu thuẫn trong cùng một prompt, và `p7-15` đã
        # làm theo con số đầu: một khối [PASSAGE] duy nhất, không có [GRAPHIC].
        f"- ĐÚNG {text_slots} khối [PASSAGE]. Cụm có {len(slot.passages)} ngữ liệu:\n{listed}\n"
        f"- {len(slot.question_types)} câu hỏi, theo đúng thứ tự này:\n{kinds}"
        f"{budget_line}{multi}{note}"
    )
