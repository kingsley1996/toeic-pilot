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


# Bốn biến thể hàm ý cho câu `*_IMPLICATION` của Part 3/4. §6.8 của guidelines liệt
# năm loại câu khó cho phần Nghe; `TOPIC_OR_PURPOSE` đã phủ loại "purpose", còn
# IMPLICATION gánh bốn loại kia — và mỗi loại hỏi theo MỘT khuôn khác nhau. Giống
# `_HOW_VARIANTS`: để mô hình tự chọn thì nó lãnh trọn kiểu quote-a-line (khuôn dễ
# viết nhất, đã có sẵn trong system prompt), và người học gặp đúng một câu hỏi
# khó dù đề có sáu cụm hàm ý. Mặc định 0 = quote-a-line = đúng hành vi cũ.
_IMPLICATION_VARIANTS = (
    (
        "HÀM Ý QUA MỘT ĐƯỢC NÓI",
        "Hỏi \u201cWhat does the woman/speaker mean when she says, \u2026?\u201d và TRÍCH "
        "đúng một dòng 4\u20139 từ có thật trong {unit}. Đáp án là NGHĨA HÀM của dòng "
        "ấy, không bao giờ là nghĩa đen.",
    ),
    (
        "SUY RA TỪ HAI CHI TIẾT RỜI NHAU",
        "Hỏi \u201cWhat can be inferred about \u2026?\u201d \u2014 không trích dòng nào. "
        "Đáp án KHÔNG được nói ra ở đâu cả; phải ghép một dữ kiện nêu sớm với một "
        "dữ kiện nêu muộn mới ra. Cổng kiểm chặn đáp án mà từ khóa chỉ chạm "
        "ĐÚNG MỘT câu của lời thoại.",
    ),
    (
        "HỆ QUẢ CỦA MỘT KẾ HOẠCH BỊ ĐỔI",
        "Hỏi \u201cWhat will probably happen next?\u201d hoặc \u201cWhat does the man "
        "still need to do?\u201d Một kế hoạch/lịch/giá được nêu rồi BỊ SỬA ở phần sau; "
        "đáp án là hệ quả của BẢN ĐÃ SỬA, bản cũ là một đáp án sai.",
    ),
    (
        "MỤC ĐÍCH CỦA MỘT CHI TIẾT",
        "Hỏi \u201cWhy does the speaker mention \u2026?\u201d hoặc \u201cWhat is the "
        "speaker\u2019s attitude toward \u2026?\u201d Đáp án là CHỨC NĂNG của chi tiết "
        "trong lập luận, không phải nội dung bản thân nó.",
    ),
)


def implication_note(slot: QuestionSlot, unit: str) -> str:
    """Dòng nhắc biến thể hàm ý, rỗng nếu cụm không có câu `*_IMPLICATION`."""
    codes = slot.question_types or ([slot.question_type] if slot.question_type else [])
    if not any(code.endswith("_IMPLICATION") for code in codes):
        return ""
    name, how = _IMPLICATION_VARIANTS[slot.implication_kind % len(_IMPLICATION_VARIANTS)]
    return (
        f"\n- Câu HÀM Ý của cụm này là biến thể \u201c{name}\u201d: {how.format(unit=unit)} "
        f"Ba đáp án sai vẫn là những cách đọc THƯỜNG TÌNH của cùng dữ kiện \u2014 nghĩa "
        f"đen của dòng được trích, một suy ra có lý nhưng bị phần còn lại của {unit} "
        f"bác bỏ, hoặc một chi tiết có thật nhưng trả lời câu hỏi khác \u2014 chứ không "
        f"phải ba câu vô nghĩa."
    )
