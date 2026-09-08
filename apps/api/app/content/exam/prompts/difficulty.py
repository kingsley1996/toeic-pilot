"""Trục độ khó ghi trên ô, đưa vào prompt của chính ô đó.

Cùng khuôn với `indirect` của Part 2: mix quyết định, prompt của TỪNG Ô nói ra,
và một cổng ở `check.py` cưỡng chế. Bảo mô hình "viết khó hơn" ở system prompt
thì nó vẫn rơi vào thể hiện dễ nhất của dạng được giao (SPEC-EXAM-DIFFICULTY §1).
"""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot

# `unit` là chữ dùng để gọi ngữ liệu của part: "hội thoại", "bài nói", "tài liệu".
_HARD = (
    "\n- ÍT NHẤT {count} câu phải buộc GHÉP hai chỗ TÁCH RỜI của {unit}: một dữ kiện"
    " nêu sớm cộng với một điều kiện thêm vào muộn hơn — một mức giá rồi một ràng"
    " buộc, một lịch hẹn rồi một thay đổi. Câu trả lời được chỉ bằng một câu văn"
    " duy nhất KHÔNG tính. Đo trên 470 câu đã sinh: 41% có toàn bộ chứng cứ nằm"
    " gọn trong một câu, nên phần lớn đề trả lời được bằng cách bắt đúng một dòng."
)


def hard_note(slot: QuestionSlot, unit: str) -> str:
    """Dòng nhắc trục D1 cho ô này, rỗng nếu ô không được đánh dấu."""
    if not slot.hard:
        return ""
    return _HARD.format(count=slot.hard, unit=unit)
