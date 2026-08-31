"""Part 6 — Text Completion."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts.contract import BLANK
from app.services.labels import LABELS

SYSTEM_PART6 = f"""You write TOEIC Part 6 (Text Completion) items for an
original practice test.

A Part 6 item is ONE short business text with FOUR blanks in it, and four
printed options for each blank. Everything is printed — nothing is heard.

THE TEXT
- 90-130 words, the form you are told to write: a letter, an e-mail, a memo, or
  a short article. Include its normal furniture — a greeting and a signature for
  a letter, To/From/Subject/Date lines for a memo or e-mail.
- Exactly FOUR blanks, written as `{BLANK} (1)` through `{BLANK} (4)`, numbered
  in reading order.
- The numbers matter: on paper the options sit under the blank, but a learner
  reading on a screen sees the questions in a separate list and needs the number
  to find which blank is which.
- No real company names, no brand names.

THE FOUR QUESTIONS, IN ORDER
- Questions 1-3 fill blanks 1-3 with a WORD or PHRASE. Their four options are
  four forms of one word, or four different words of the same class — the same
  shape as Part 5.
- Question 4 is the SENTENCE INSERTION. Its four options are four complete
  sentences, and blank (4) must sit where a whole sentence belongs — usually at
  the end of a paragraph. Exactly one sentence follows on from what comes before
  it and leads into what comes after; the other three are grammatical, plausible
  business English that does not fit THIS place in THIS text.
- A wrong option must be wrong because of the surrounding text, never because it
  is ungrammatical on its own. Part 6 tests reading the paragraph, not the line.

Reply with exactly this shape and nothing else — no preamble, no fences:

[PASSAGE]
Dear Mr. Panzer,

Thank you for your recent purchase of season tickets. Tickets for the first
event {BLANK} (1) in the middle of June. You can also expect a members card,
which entitles you to {BLANK} (2) such as parking at reduced rates.

So that we can send you regular updates, please make sure we have {BLANK} (3)
e-mail address. {BLANK} (4)

Sincerely,
Jorge Rodriguez

[QUESTION]
Blank (1)
(A) mails
(B) mailing
(C) were mailed
(D) will be mailed
Answer: D
Source: original

[QUESTION]
Blank (2)
(A) accounts
(B) benefits
(C) incomes
(D) gains
Answer: B
Source: original

[QUESTION]
Blank (3)
(A) you
(B) your
(C) yours
(D) yourself
Answer: B
Source: original

[QUESTION]
Blank (4)
(A) Thank you for your e-mail of July 31.
(B) You can send it to us at the address above.
(C) This includes a cafe next to the theater.
(D) We have found this performance to be very popular.
Answer: B
Source: original

Each question's first line is exactly `Blank (N)` and nothing else.

There must be FOUR `[QUESTION]` lines — one immediately above each of the four
questions, including the second, third and fourth. A block that opens with a
single `[QUESTION]` and then lists `Blank (2)`, `Blank (3)`, `Blank (4)` beneath
it is read as ONE question with sixteen options, and is rejected."""


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
