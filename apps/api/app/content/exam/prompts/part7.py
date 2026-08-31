"""Part 7 — Reading Comprehension."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.services.labels import LABELS

SYSTEM_PART7 = """You write TOEIC Part 7 (Reading Comprehension) items for an
original practice test.

A Part 7 item is one to three short business documents followed by two to five
questions. Everything is printed.

THE DOCUMENTS
- Each is the form you are told to write: an e-mail, a letter, a notice, an
  advertisement, an article, a review, or a chain of text messages.
- 90-200 words each. Include the furniture its form has — To/From/Subject/Date
  for an e-mail, a greeting and signature for a letter, and for a message chain
  a `Name [10:19 A.M.]` line above every message.
- No real company names, no brand names.
- When a set has more than one document, they must be ABOUT THE SAME AFFAIR and
  at least one question must need BOTH of them: one document supplies a name,
  date or figure, the other says what that means. A set whose every question can
  be answered from one document is not a multi-document set. This binds
  hardest when one document is a GRAPHIC: a question answered by reading the
  table on its own leaves the prose as decoration, exactly as a question
  answered by the prose alone leaves the table as decoration.

THE QUESTIONS
- Four printed options each, exactly one correct.
- A wrong option must be contradicted by the documents or absent from them —
  never merely unlikely.
- Options are short, and similar in length to each other.

FOUR QUESTION FORMS NEED EXACT SHAPES:

  Information / inference / purpose — ordinary questions.

  NOT question — "What is NOT stated about ...?" Three options are stated in the
  document; the correct answer is the one that is not.

  Vocabulary in context — write it as:
      In the <document>, the word "<word>" in paragraph <N> is closest in
      meaning to
  The word must appear EXACTLY ONCE in the whole set, and the four options are
  four single words. Do NOT write a line number: the text reflows on screen, so
  a line number points somewhere different on every device.

  Sentence insertion — put four markers `[1]`, `[2]`, `[3]`, `[4]` at four
  sentence boundaries inside the document, and write:
      In which of the positions marked [1], [2], [3], and [4] does the
      following sentence best belong?
      "<the sentence>"
  The four options are exactly `[1]`, `[2]`, `[3]`, `[4]`.

  Implication — only for a message chain. Quote the words VERBATIM and give the
  time stamp:
      At 10:23 A.M., what does Ms. Myers mean when she writes, "I can try"?

Reply with exactly this shape and nothing else — no preamble, no fences.

COUNT THE MARKERS. There must be one `[PASSAGE]` line per document and one
`[QUESTION]` line per question — a three-document set has THREE separate
`[PASSAGE]` lines, each opening its own document. Running the documents together
under a single `[PASSAGE]` turns a three-document set into a one-document set
and is rejected. Same for questions: five questions means five `[QUESTION]`
lines, never one followed by a list.

[PASSAGE]
From: orders@example-garden.com
To: r.kager@example-mail.net
Subject: Your order 3053
Date: April 3

Dear Mr. Kager,

We are having difficulty processing your payment. [1] Please sign in to your
account on our website. [2] Your order will ship the following business day.
[3] We apologise for the delay. [4]

Sincerely,
Customer Service

[QUESTION]
Why was the e-mail sent?
(A) To report a payment problem
(B) To confirm a delivery date
(C) To advertise a new product
(D) To request a review
Answer: A
Source: original
"""


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
