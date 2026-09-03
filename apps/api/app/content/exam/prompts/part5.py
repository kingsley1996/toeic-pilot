"""Part 5 — Incomplete Sentences."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.services.labels import LABELS

# Hợp đồng định dạng, gửi kèm mọi lượt gọi. Viết ra tường minh chứ không tả bằng
# lời: mô hình bám theo ví dụ chặt hơn nhiều so với bám theo mô tả.
# Dòng giải thích của ví dụ, ghép từ nhiều mảnh để NGUỒN ngắn dưới 100 cột mà
# chuỗi gửi đi vẫn nằm trên MỘT dòng. Ngắt dòng thật ở đây sẽ dạy mô hình ngắt
# dòng theo, và parser coi dòng lạ sau các đáp án là lỗi — một lựa chọn định
# dạng của tệp nguồn sẽ đi thẳng vào đầu ra của mô hình.
EXAMPLE_EXPLANATION = (
    'Explanation: Sau "must be" cần phân từ hai để tạo thể bị động. '
    '| (A) "submitted" — đúng phân từ hai mà thể bị động đòi. '
    '| (B) "submitting" — là V-ing, không đi sau "be" theo nghĩa bị động. '
    '| (C) "submission" — là danh từ, sai từ loại cho vị trí này. '
    '| (D) "submissive" — là tính từ nghĩa "phục tùng", không liên quan.'
)

SYSTEM = exam_prompt("part5_system").render(EXAMPLE_EXPLANATION=EXAMPLE_EXPLANATION)


def prompt_for(slot: QuestionSlot) -> str:
    grammar = LABELS[slot.grammar].label_vi if slot.grammar else "từ vựng thương mại"
    kind = LABELS[slot.question_type].label_vi
    lines = [
        "Viết một câu hỏi Part 5.",
        f"- Dạng câu: {kind}",
        f"- Điểm kiểm tra: {grammar}",
        f"- Bối cảnh: {slot.context}",
    ]
    if not slot.grammar:
        # Câu TỪ VỰNG là chỗ lỗi "hai đáp án cùng đúng" xảy ra nhiều nhất, vì
        # cách viết dễ nhất là lấy bốn từ gần nghĩa. Nói thẳng đường đi đúng thay
        # vì chỉ cấm đường sai: bốn từ cùng đăng ký ngôn ngữ nhưng KHÁC trường
        # nghĩa, và chỉ một từ hợp với danh từ/động từ đứng cạnh chỗ trống.
        lines.append(
            "- Bốn lựa chọn phải là bốn từ KHÁC TRƯỜNG NGHĨA, không phải bốn từ gần nghĩa. "
            "Ba từ sai phải sai vì không đi được với từ đứng cạnh chỗ trống, "
            "không phải vì 'kém tự nhiên hơn'."
        )
    else:
        lines.append(
            "- Ba lựa chọn sai phải sai vì đúng điểm kiểm tra đó (sai từ loại, sai thì, "
            "sai thể, sai dạng), không phải sai vu vơ."
        )
    lines.append(
        "- Bốn lựa chọn dài xấp xỉ nhau: lựa chọn dài hơn hẳn là một manh mối rò rỉ đáp án."
    )
    return "\n".join(lines)
