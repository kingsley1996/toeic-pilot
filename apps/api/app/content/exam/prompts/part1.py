"""Part 1 — Photographs."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.content.exam.prompts.contract import PHOTO_MARKER
from app.services.labels import LABELS

SYSTEM_PART1 = exam_prompt("part1_system").render(PHOTO_MARKER=PHOTO_MARKER)

# Số người trong ảnh đổi cả bộ mẫu câu, không chỉ đổi nội dung. Không nói ra thì
# mô hình viết "The man is ..." cho một tấm ảnh không có ai — và câu đó sai theo
# một kiểu người học không học được gì từ nó.
_PEOPLE_BRIEF = {
    "one": (
        "Trong ảnh có ĐÚNG MỘT người. Mẫu câu chính là thì hiện tại tiếp diễn "
        "với người đó làm chủ ngữ."
    ),
    "several": (
        "Trong ảnh có TỪ HAI NGƯỜI TRỞ LÊN. Dùng cả chủ ngữ số nhiều "
        '("The workers are...") lẫn chủ ngữ chỉ một người trong nhóm.'
    ),
    "none": (
        "Trong ảnh KHÔNG CÓ NGƯỜI NÀO — chỉ đồ vật hoặc quang cảnh. Vì thế "
        'KHÔNG câu nào được có người làm chủ ngữ. Dùng "There is / There are", '
        'thể bị động trạng thái ("Some chairs have been arranged in rows"), '
        "hoặc hiện tại tiếp diễn với chủ ngữ là đồ vật "
        '("Some boxes are sitting on the floor"). Một câu nhiễu tốt ở dạng này '
        "là câu nhắc tới một người không hề có trong ảnh."
    ),
}


def prompt_for_part1(slot: QuestionSlot) -> str:
    kind = LABELS[slot.question_type].label_vi
    return (
        f"Viết một câu hỏi Part 1.\n"
        f"- Dạng ảnh: {kind}\n"
        f"- {_PEOPLE_BRIEF[slot.people]}\n"
        f"- Bối cảnh: {slot.context}\n"
        # Đưa NGUYÊN dòng cần in ra, không mô tả nó. Bản cũ viết
        # "- Dòng `voice:` phải ghi đúng: ca_male_1" và mô hình nhỏ chép luôn cả
        # dấu ngoặc ngược vào đầu ra — `\`voice:\` ca_male_1` — thứ parser từ chối.
        # Hỏng ba lần liên tiếp y hệt nhau với gemma3, tức là lỗi của prompt chứ
        # không phải của mô hình.
        f"- Dòng đầu tiên sau [QUESTION] phải là chính xác:\nvoice: {slot.voice}\n"
        f"- Ba câu sai phải SAI KIỂM CHỨNG ĐƯỢC so với tấm ảnh sẽ vẽ, "
        f"không phải chỉ 'ít khả năng'."
    )
