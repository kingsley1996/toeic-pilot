"""Part 5 — Incomplete Sentences."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.services.labels import LABELS

# Hợp đồng định dạng, gửi kèm mọi lượt gọi. Viết ra tường minh chứ không tả bằng
# lời: mô hình bám theo ví dụ chặt hơn nhiều so với bám theo mô tả.
# Dòng giải thích của ví dụ, ghép từ nhiều mảnh để NGUỒN ngắn dưới 100 cột mà
# chuỗi gửi đi vẫn nằm trên MỘT dòng. Ngắt dòng thật ở đây sẽ dạy mô hình ngắt
# dòng theo, và parser coi dòng lạ sau các đáp án là lỗi — một lựa chọn định
# dạng của tệp nguồn sẽ đi thẳng vào đầu ra của mô hình.
EXAMPLE_EXPLANATION = (
    'Explanation: Sau "must be" cần phân từ hai của thể bị động. '
    '(B) là V-ing, không đi sau "be" theo nghĩa bị động; '
    '(C) là danh từ; (D) là tính từ nghĩa "phục tùng", không liên quan.'
)

SYSTEM = f"""You write TOEIC Part 5 (Incomplete Sentences) questions for an original practice test.

THE ONE RULE THAT DECIDES WHETHER AN ITEM IS USABLE
Exactly one option can complete the sentence. Apply this test before you answer:
read the sentence four times, once with each option in the blank. If a competent
speaker of business English would accept two of them, the item is broken — throw
it away and write a different one. Near-synonyms are the usual way this goes
wrong: "verify / confirm / validate" all fit "------- the references", so that is
not an item, it is four right answers.

Each wrong option must fail for a reason you can state in one short clause:
- wrong part of speech for that slot,
- wrong collocation with the noun or verb next to the blank,
- wrong tense, voice, or number given the rest of the sentence,
- a real word that means something unrelated in this context.
"Slightly less natural" is NOT a reason. If that is the best you can say about a
distractor, replace it.

Other rules:
- One English sentence with exactly one blank, written as seven hyphens: -------
- Exactly FOUR options labelled (A) (B) (C) (D).
- Setting is always work, business or office life — never private life.
- Neutral register. No humour, no real brand names.
- Never copy a sentence from any real exam. Write new material.
- Sentence and options in ENGLISH. Explanation in Vietnamese.
- The explanation names the reason EACH wrong option is wrong, not just why the
  right one is right.

Reply with exactly this block and nothing else — no preamble, no code fences:

[QUESTION]
All maintenance requests must be ------- through the facilities portal by Friday.
(A) submitted
(B) submitting
(C) submission
(D) submissive
Answer: A
{EXAMPLE_EXPLANATION}
Source: original

Note the shape of the answer line: a single letter, nothing else."""


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
