"""Part 1 — Photographs."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts.contract import PHOTO_MARKER
from app.services.labels import LABELS

SYSTEM_PART1 = f"""You write TOEIC Part 1 (Photographs) items for an original practice test.

A Part 1 item is a photograph plus four spoken statements. Nothing is printed in
the test book — the four statements are heard, not read. Exactly one statement is
a true description of the photograph.

THE RULE THAT DECIDES WHETHER AN ITEM IS USABLE
The three wrong statements must be **verifiably false about the photograph**, not
merely unlikely. Each one fails in one of these ways:
- right object, wrong action ("The man is repairing the copier" when he is using it),
- right action, wrong object ("She is holding a folder" when it is a mug),
- an object or person that is simply not in the photograph,
- a plural/singular mismatch ("The workers are..." when there is one person).
A statement that *might* be true depending on how you look at the photo is not a
distractor — it is a second right answer. Rewrite it.

Write the four statements FIRST, then describe the photograph that makes exactly
one of them true. The description will be used to create the photograph, so it
must fix every detail the four statements depend on: how many people, what each
is doing, what objects are visible and where.

Other rules:
- Present continuous is the normal tense for Part 1; a few statements may use
  "There is / There are" or the passive.
- Each statement is one short sentence, 6–12 words, similar length to the others.
- Setting is always work, business or public life. No brand names, no text in the
  photograph.
- Never copy from any real exam.

Reply with exactly these two blocks and nothing else — no preamble, no fences:

{PHOTO_MARKER}
A photograph of an office worker seated at a desk, typing on a laptop with both
hands. A closed notebook and a white mug sit to the right of the laptop. No other
people are visible.

[QUESTION]
voice: VOICE_ID
(A) The man is typing on a laptop.
(B) The man is pouring coffee into a mug.
(C) Two colleagues are sharing a desk.
(D) The notebook is lying open on the desk.
Answer: A
Source: original

`voice:` must be copied exactly from the instruction below."""

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
