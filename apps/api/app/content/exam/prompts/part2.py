"""Part 2 — Question-Response."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.content.exam.prompts.contract import BLOCK_TAIL
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
        f"- Đáp án đúng: {_answer_kind(slot)}\n"
        f"- BA câu đáp, không phải bốn. Hai câu sai phải sai theo một kiểu gọi "
        f"tên được, và phải hấp dẫn với người chỉ nghe được một phần câu hỏi." + BLOCK_TAIL
    )


# Bốn kiểu né mà `part2_system.md` tả. Nói ra ở prompt TỪNG Ô vì system prompt
# liệt kê cả bốn, còn ô thì phải là một — và để mô hình tự chọn thì nó dồn về
# kiểu dễ viết nhất: 5 trên 8 ô của `tp-form-11` đều ra "Ask the ___".
_INDIRECT_KINDS = (
    "nói rằng mình KHÔNG BIẾT hoặc chưa thể trả lời"
    ' ("Where\'s the sales report?" / "I just got back from lunch.").',
    "CHỈ SANG người hoặc chỗ khác"
    ' ("When does the shipment arrive?" / "Ask the warehouse manager.").',
    "đáp lại bằng MỘT CÂU HỎI của chính mình"
    ' ("Should we book the larger room?" / "How many people are coming?").',
    "làm câu hỏi TRỞ NÊN VÔ NGHĨA"
    ' ("Who\'s leading the training?" / "It was cancelled this morning.").',
)


def _answer_kind(slot: QuestionSlot) -> str:
    """Trục độ khó của Part 2 — xem `PART2_MIX`. Nói ra ở prompt của TỪNG ô chứ
    không chỉ ở system prompt: system prompt mô tả cả hai loại, còn ô này phải
    là một trong hai, và mô hình không có gì khác để chọn theo."""
    if slot.indirect:
        return (
            "GIÁN TIẾP — không cung cấp thứ được hỏi. Không được nêu địa điểm "
            "cho câu WHERE, thời gian cho câu WHEN, người cho câu WHO."
            f" Dùng ĐÚNG kiểu này: {_INDIRECT_KINDS[slot.indirect_kind % len(_INDIRECT_KINDS)]}"
        )
    return "TRỰC TIẾP — trả lời thẳng vào thứ được hỏi."
