"""Chặng sinh văn bản: một ô một lượt gọi, ghi thẳng ra tệp dán.

**Mô hình xuất ra ĐỊNH DẠNG DÁN**, không phải JSON rồi mình dựng lại. Đó là
quyết định kiến trúc chính của cả pipeline: định dạng dán đã có parser thật
(`content_import.py`) và bộ luật thật (`validators.py`) đứng sau, nên bản sinh
phải qua đúng cái cổng mà bản người dán phải qua. Nhận JSON rồi tự lắp câu là
dựng đường vào thứ hai, và mọi luật ở cổng kia phải được nhớ lại lần nữa ở đây —
chỗ nào quên thì hỏng im lặng.

**Một ô một lượt gọi.** Cùng lý do `enrich_skills` gọi một facet một lượt: gộp
thì ít lượt hơn nhưng mô hình trượt một chỗ là hỏng cả mẻ, phải chạy lại toàn bộ
thay vì chạy lại đúng ô hỏng, và ngữ cảnh rộng ra làm nó lệch khỏi điểm ngữ pháp
đã giao.

**Ghi xuống đĩa NGAY sau mỗi ô**, không gom cuối lượt: 30 ô là nhiều phút, và
một lần Ctrl-C không được phép vứt sạch.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from app.content.exam.blueprint import (
    GRAPHIC_POSITION,
    LISTENING_QUESTIONS_PER_SET,
    Blueprint,
    QuestionSlot,
)
from app.services.content_import import SCRIPT_MARKER as CONTENT_SCRIPT_MARKER
from app.services.labels import LABELS
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier

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


PHOTO_MARKER = "[PHOTO]"
# Mốc lời thoại dùng chung của Part 3/4. Cùng chuỗi mà `content_import` nhận,
# nhập từ đó chứ không viết lại: hai hằng số cho một giao thức là hai thứ trôi
# khỏi nhau, và cái trôi chỉ lộ ra ở chặng nạp.
SCRIPT_MARKER = CONTENT_SCRIPT_MARKER
GRAPHIC_MARKER = "[GRAPHIC]"

# Cả pipeline sinh đề kiên nhẫn hơn mặc định của `with_backoff`. Đo được trên
# model miễn phí của tokenrouter: **ba lượt 503 liên tiếp rồi lượt thứ tư trả
# 200** — tức là `tries=4` mặc định bỏ cuộc đúng một lượt trước khi thành công.
# Một chặng chạy ngoài luồng hàng chục phút thì đợi thêm hai phút là rẻ; bỏ cuộc
# thì ô đó về hàng đợi và người chạy phải tự chạy lại.
RETRY_TRIES = 7
RETRY_DELAY = 6.0

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


SYSTEM_PART3 = """You write TOEIC Part 3 (Conversations) items for an original
practice test.

A Part 3 item is ONE short conversation plus THREE questions about it. The
conversation is heard, never printed; the questions and their four options ARE
printed in the test book.

THE CONVERSATION
- 6 to 9 turns, natural spoken business English, roughly 100-140 words total.
- Speakers alternate; in a three-speaker conversation the third speaker joins
  partway through and speaks at least twice.
- Every fact the three questions depend on must be SAID out loud. A question
  whose answer is only implied by tone is not answerable from a recording.
- No names of real companies, no brand names, no prices in currency symbols
  (say "forty dollars", not "$40" — it is read aloud).

THE THREE QUESTIONS
- Each asks about something different. Do not ask twice about the same turn.
- Four printed options each, exactly one correct.
- The three wrong options must be wrong **against what was said**: a detail from
  the wrong speaker, an action that was rejected, a time that was changed, or
  something never mentioned. An option that is merely unlikely is a second
  correct answer.
- Options are short noun phrases or short clauses, similar length to each other.

Reply with exactly this shape and nothing else — no preamble, no fences:

[SCRIPT]
voice: VOICE_A
Good morning. I'm calling about the delivery scheduled for Thursday.
voice: VOICE_B
Let me check the order. It looks like it left the warehouse yesterday.
voice: VOICE_A
That's earlier than we expected. Can it be held until Friday?

[QUESTION]
Why is the woman calling?
(A) To reschedule a delivery
(B) To place a new order
(C) To report a damaged item
(D) To request an invoice
Answer: A
Source: original

[QUESTION]
...

[QUESTION]
...

Each `voice:` line switches who is speaking, and you may only use the voice
names given in the instruction below. Every question block needs its own
`Answer:` and `Source: original` lines."""


_GRAPHIC_RULES_TEMPLATE = f"""

THIS ITEM COMES WITH A GRAPHIC
The test book prints a small graphic beside the three questions. EXACTLY ONE
question begins with "Look at the graphic", and it is question number {{ordinal}}
of the three — not any other. Emit the graphic first, as data. The first line
names its kind. Four kinds exist; use the one you are told to.

{GRAPHIC_MARKER}
kind: table
Office Supply Prices
Type | Cost
Daily planner | $14.89
Weekly planner | $27.49
Monthly desk pad | $5.49
Undated desk pad | $4.99

EVERY graphic has a `kind:` line, then a TITLE LINE of its own, then its data.
The title is never a row — leaving it out shifts the whole graphic up a line and
the block is rejected. Here is each kind in full:

{GRAPHIC_MARKER}
kind: schedule
Wednesday Availability
Person | 8-9 | 9-10 | 10-11 | 11-12
Zahra | Busy |  | Team meeting |
Sammy |  | Client call |  | Budget meeting

{GRAPHIC_MARKER}
kind: chart
Quarterly Sales in thousands
First quarter | 42
Second quarter | 58
Third quarter | 35
Fourth quarter | 71

{GRAPHIC_MARKER}
kind: map
Mall Directory, Ground Floor
Store 1: Electronics | Store 2: Bookstore
Store 3: Sporting Goods | Store 4: Pharmacy

Where the answer options come from, per kind:

  table     the four ROW NAMES
  schedule  the four TIME SLOTS — the column headings, NOT the people
  chart     the four LABELS
  map       the four CELL NAMES, the part before any colon

For `schedule`, LEAVE A CELL EMPTY when that person is free; that emptiness is
what the question turns on, and a grid with every cell filled has no answer.
Use ordinary personal names for the people — never a voice name like
`us_female_1`, which is a recording instruction and not a person.

Separate cells with a vertical bar. Keep every value short.

Invent your own titles, labels and numbers. The examples above are a shape to
copy, never content to copy — reusing their values makes two different papers
carry the same graphic.

Two rules make it a real graphic question rather than a detail question:

1. The four options of the LAST question are exactly the four items on that
   kind's answer axis, and nothing else.
2. The speaker must NEVER say the winning item's name. It gives the other
   information instead ("the one that's about twenty-seven dollars", "the hour
   when we're both free", "right across from the bookstore"), so the listener
   has to read the graphic. If the weekly planner is named out loud, the graphic
   is decoration and the question is answerable without it."""


def graphic_rules(position: int) -> str:
    """Luật hình, gắn đúng VỊ TRÍ câu hỏi về hình của part đang viết.

    Vị trí khác nhau giữa hai part (Part 3 câu thứ ba, Part 4 câu thứ hai), nên
    một hằng số nói "câu cuối" là đúng cho Part 3 và sai cho Part 4 — và cái sai
    đó chỉ lộ ra ở cổng kiểm, sau khi đã trả tiền cho lượt gọi.
    """
    ordinal = {1: "one", 2: "two", 3: "three"}[position + 1]
    return _GRAPHIC_RULES_TEMPLATE.format(ordinal=ordinal)


SYSTEM_PART4 = """You write TOEIC Part 4 (Talks) items for an original practice
test.

A Part 4 item is ONE short talk by a SINGLE speaker plus THREE questions about
it. The talk is heard, never printed; the questions and their four options ARE
printed in the test book.

THE TALK
- One voice throughout. No dialogue, no second speaker, no interruptions.
- 100-150 words of natural spoken business English, in the register its form
  calls for: a voice-mail message, a public announcement, a radio commercial, an
  excerpt from a meeting, or a short talk to an audience.
- It opens the way that form opens — "Hi, this is Marcus from...", "Attention,
  shoppers", "Good morning, everyone, and welcome to..." — because the first
  question is usually about who is speaking or where.
- Every fact the three questions depend on must be SAID out loud.
- No real company names, no brand names, no currency symbols (say "forty
  dollars", not "$40" — it is read aloud).

THE THREE QUESTIONS
- Each asks about something different. Do not ask twice about the same sentence.
- Four printed options each, exactly one correct.
- The three wrong options must be wrong **against what was said**: a detail that
  was corrected, an action ruled out, a time that changed, or something never
  mentioned. An option that is merely unlikely is a second correct answer.
- Options are short noun phrases or short clauses, similar length to each other.

Reply with exactly this shape and nothing else — no preamble, no fences:

[SCRIPT]
voice: VOICE_A
Attention, passengers on flight two-oh-six to Denver. The departure gate has
been changed from gate twelve to gate nineteen. Boarding will begin in about
twenty minutes. Please allow extra time to reach the new gate.

[QUESTION]
Where is the announcement being made?
(A) At an airport
(B) At a train station
(C) At a bus terminal
(D) At a ferry landing
Answer: A
Source: original

[QUESTION]
...

[QUESTION]
...

Use only the voice name given in the instruction below, on a single `voice:`
line. Every question block needs its own `Answer:` and `Source: original`."""


SYSTEM_PART2 = """You write TOEIC Part 2 (Question-Response) items for an
original practice test.

A Part 2 item is ONE spoken question or statement, followed by THREE spoken
responses. NOTHING is printed in the test book — the test taker only listens.
Exactly one response is an appropriate reply.

THE PROMPT LINE
- One sentence, 6-14 words, natural spoken business English.
- It is the form you are told to write: a WHERE question, a tag question, a
  request, a plain statement, and so on.

THE THREE RESPONSES
- Short — usually 4-12 words, the length a person actually answers in.
- Exactly one works as a reply. The other two must fail for a reason a listener
  can name, and these are the failures the real test uses:
    · answers a DIFFERENT question word (a place when the question asked when),
    · repeats or echoes a word from the prompt in an unrelated sense
      ("Where's the *report*?" / "He'll *report* to the manager."),
    · a similar-sounding word ("fare" for "fair", "copy" for "coffee"),
    · a yes/no answer to a question that cannot take one.
- Do NOT make a wrong response absurd. It should be tempting to someone who
  caught only part of the prompt.

Reply with exactly this shape and nothing else — no preamble, no fences:

[QUESTION]
voice: VOICE_ASK
Where did you put the quarterly sales report?
voice: VOICE_REPLY
(A) On your desk, next to the printer.
(B) Yes, I finished it last night.
(C) About thirty copies, I think.
Answer: A
Source: original

There are THREE responses, not four — Part 2 has no (D). The two `voice:` lines
must be copied exactly from the instruction below: the first switches to the
person asking, the second to the person replying."""


def prompt_for_part2(slot: QuestionSlot) -> str:
    kind = LABELS[slot.question_type].label_vi
    ask, reply = slot.voices
    return (
        f"Viết một câu hỏi Part 2.\n"
        f"- Dạng: {kind}\n"
        f"- Bối cảnh: {slot.context}\n"
        f"- Dòng đầu tiên sau [QUESTION] phải là chính xác:\nvoice: {ask}\n"
        f"- Ngay trước (A) phải là chính xác:\nvoice: {reply}\n"
        f"- BA câu đáp, không phải bốn. Hai câu sai phải sai theo một kiểu gọi "
        f"tên được, và phải hấp dẫn với người chỉ nghe được một phần câu hỏi."
    )


def prompt_for_part4(slot: QuestionSlot) -> str:
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    return (
        f"Viết một bài nói Part 4 và ba câu hỏi về nó.\n"
        f"- Dạng bài: {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        f"- MỘT người nói, giọng: {slot.voices[0]}\n"
        f"- Ba câu hỏi, theo đúng thứ tự này:\n{kinds}\n"
        f"- Mọi dữ kiện mà ba câu hỏi cần phải được NÓI RA trong bài."
        + (
            f"\n- Hình đi kèm — dùng ĐÚNG `kind: {slot.graphic.split(':')[0].strip()}`: "
            f"{slot.graphic.partition(':')[2].strip()}. Bài nói KHÔNG được đọc tên "
            f"mục là đáp án — nó chỉ nói thông tin còn lại."
            if slot.graphic
            else ""
        )
    )


def prompt_for_part3(slot: QuestionSlot) -> str:
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    cast = ", ".join(slot.voices)
    return (
        f"Viết một cuộc hội thoại Part 3 và ba câu hỏi về nó.\n"
        f"- Chủ đề: {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        f"- Số người nói: {len(slot.voices)}. Chỉ dùng đúng các tên giọng này, "
        f"mỗi người một giọng: {cast}\n"
        f"- Ba câu hỏi, theo đúng thứ tự này:\n{kinds}\n"
        f"- Mọi dữ kiện mà ba câu hỏi cần phải được NÓI RA trong hội thoại."
        + (
            f"\n- Hình đi kèm — dùng ĐÚNG `kind: {slot.graphic.split(':')[0].strip()}`: "
            f"{slot.graphic.partition(':')[2].strip()}. Hội thoại KHÔNG được đọc tên "
            f"mục là đáp án — nó chỉ nói thông tin còn lại."
            if slot.graphic
            else ""
        )
    )


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


def split_marked(block: str, marker: str) -> tuple[str, str]:
    """Tách khối mang `marker` ra khỏi phần dán. Trả (phần tách, phần còn lại).

    Cùng lý do như `split_photo`: parser TỪ CHỐI dòng lạ, nên mô tả ảnh và dữ
    liệu bảng phải rời khỏi tệp dán. Nó cũng đúng về vòng đời — hai hiện vật đó
    phục vụ chặng vẽ, tệp dán phục vụ chặng nạp, và hai chặng chạy lại độc lập.
    """
    lines = block.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == marker]
    if not starts:
        return "", block
    begin = starts[-1]
    # Khối kết thúc ở mốc tiếp theo bất kỳ ([SCRIPT], [QUESTION], [PHOTO]).
    end = next(
        (
            index
            for index in range(begin + 1, len(lines))
            if lines[index].strip().startswith("[") and lines[index].strip().endswith("]")
        ),
        len(lines),
    )
    taken = "\n".join(lines[begin + 1 : end]).strip()
    rest = "\n".join(lines[:begin] + lines[end:]).strip()
    return taken, rest


def split_photo(block: str) -> tuple[str, str]:
    """Tách phần mô tả ảnh khỏi phần dán.

    Hai hiện vật riêng vì parser TỪ CHỐI dòng lạ sau các đáp án: nhét mô tả ảnh
    vào cùng tệp dán là làm cả khối không đọc được. Tách ở đây cũng đúng về mặt
    vòng đời — mô tả ảnh phục vụ chặng vẽ, tệp dán phục vụ chặng nạp, và hai
    chặng đó chạy lại độc lập với nhau.
    """
    if PHOTO_MARKER not in block:
        return "", block
    _, _, rest = block.partition(PHOTO_MARKER)
    photo, marker, paste = rest.partition("[QUESTION]")
    return photo.strip(), (marker + paste).strip()


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


def paste_path(workdir: Path, slot: QuestionSlot) -> Path:
    return workdir / "paste" / f"{slot.id}.txt"


# Chỗ trống viết bằng gạch DƯỚI, hoặc bằng số gạch ngang khác bảy. Cả hai đều là
# sai lệch định dạng, không phải sai nội dung — chỗ trống ở đâu thì vẫn ở đó.
_BLANK_VARIANTS = re.compile(r"_{3,}|-{3,}")
BLANK = "-------"


def clean(text: str) -> str:
    """Gỡ rào ``` và mọi thứ trước `[QUESTION]`.

    Mô hình nhỏ hay thêm một câu dẫn ("Chắc chắn rồi, đây là…") dù prompt đã cấm.
    Cắt ở đây rẻ hơn nhiều so với để parser từ chối cả khối — và nó không che
    giấu gì: phần bị cắt luôn nằm TRƯỚC mốc, tức là không phải nội dung câu hỏi.
    """
    body = text.strip()
    if "```" in body:
        parts = [chunk for chunk in body.split("```") if "[QUESTION]" in chunk]
        body = parts[0] if parts else body.replace("```", "")
    # Mốc phải đứng ĐẦU DÒNG, và lấy lần xuất hiện CUỐI CÙNG.
    #
    # Cả hai điều kiện đều học được từ một lượt chạy thật: model suy luận trích
    # dẫn chính cái mốc này trong lúc tự nhủ ("Format must be [QUESTION] ..."),
    # nên `find` bắt được nó ở giữa đoạn suy nghĩ và giữ lại toàn bộ phần suy
    # nghĩ như thể đó là câu hỏi. Khối thật luôn là khối cuối.
    lines_all = body.splitlines()
    # Part 3 và 4 mở đầu bằng `[SCRIPT]` và mang BA khối câu hỏi, nên "lấy khối
    # cuối" là sai ở đó: nó vứt mất lời thoại và hai câu đầu. Có `[SCRIPT]` đầu
    # dòng thì cắt từ đó và giữ trọn phần còn lại.
    script_starts = [index for index, line in enumerate(lines_all) if line.strip() == SCRIPT_MARKER]
    if script_starts:
        # Giữ khối [GRAPHIC] nếu nó đứng TRƯỚC lời thoại — mô hình đặt bảng lên
        # đầu vì prompt bảo thế, và cắt sạch phần trước [SCRIPT] sẽ vứt mất nó.
        # Mất bảng thì chỉ lộ ra ở chặng vẽ, tức là sau khi đã trả tiền gọi.
        graphic_starts = [
            index
            for index, line in enumerate(lines_all[: script_starts[-1]])
            if line.strip() == GRAPHIC_MARKER
        ]
        begin = graphic_starts[-1] if graphic_starts else script_starts[-1]
        return "\n".join(lines_all[begin:]).strip()

    starts = [index for index, line in enumerate(lines_all) if line.strip() == "[QUESTION]"]
    if starts:
        # Giữ khối [PHOTO] nếu nó đứng NGAY TRƯỚC khối câu hỏi cuối cùng: Part 1
        # cần cả hai, và cắt sạch phần đầu sẽ vứt mất mô tả ảnh — thứ chỉ phát
        # hiện được ở chặng vẽ, tức là sau khi đã trả tiền cho lượt gọi.
        photo_starts = [
            index
            for index, line in enumerate(lines_all[: starts[-1]])
            if line.strip() == PHOTO_MARKER
        ]
        begin = photo_starts[-1] if photo_starts else starts[-1]
        body = "\n".join(lines_all[begin:]).strip()

    # Chuẩn hoá chỗ trống. Sửa ĐỊNH DẠNG thì được, sửa nội dung thì không: một
    # chuỗi gạch dưới và bảy gạch ngang nói cùng một điều ở cùng một chỗ, nên
    # quy về một dạng không giấu đi lỗi nào. Ngược lại, tự sửa một đáp án sai
    # thành đúng sẽ che mất đúng tín hiệu mà cổng kiểm sinh ra để bắt.
    #
    # Đo được: mô hình ĐANG dùng viết `_______` ở khoảng 1 trên 15 câu, và bắt
    # sinh lại chỉ để đổi ký tự là trả tiền cho một lượt gọi mà không đổi gì.
    lines = body.splitlines()
    if lines and lines[0].strip() == "[QUESTION]" and len(lines) > 1:
        lines[1] = _BLANK_VARIANTS.sub(BLANK, lines[1])
    return "\n".join(lines)


class MissingBlock(RuntimeError):
    """Đầu ra không chứa `[QUESTION]` — không có gì để lưu."""


_SYSTEM_FOR = {1: SYSTEM_PART1, 2: SYSTEM_PART2, 3: SYSTEM_PART3, 4: SYSTEM_PART4}
_PROMPT_FOR: dict[int, Callable[[QuestionSlot], str]] = {
    1: prompt_for_part1,
    2: prompt_for_part2,
    3: prompt_for_part3,
    4: prompt_for_part4,
}


def write_slot(gateway: Gateway, slot: QuestionSlot, tier: Tier, part: int = 5) -> str:
    # Qua `with_backoff`: nhà cung cấp lớn trả 503 "high demand" khá thường, và
    # không lùi thì vòng lặp đốt sạch 30 ô trong vài giây, mỗi ô hỏng một lần vì
    # cùng một cơn quá tải kéo dài vài chục giây. Đo được với Gemini: một lượt
    # chạy 30 ô ra 0 tệp.
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=(
                    _SYSTEM_FOR[part] + graphic_rules(GRAPHIC_POSITION[part])
                    if part in (3, 4) and slot.graphic
                    else _SYSTEM_FOR.get(part, SYSTEM)
                ),
                user=_PROMPT_FOR.get(part, prompt_for)(slot),
                # Rộng tay, vì model SUY LUẬN xuất cả chuỗi suy nghĩ trước khi tới
                # khối cần lấy. Đo được: `nemotron-3-ultra` cụt giữa phần suy nghĩ ở
                # 600 token, và cái cụt đó không hiện ra như một lỗi — nó hiện ra
                # như một ô đã ghi xong với nội dung là đoạn model đang tự nhủ.
                max_tokens=12000,
                # Nhiệt độ KHÁC 0, và đây là chỗ duy nhất trong dự án cố ý như thế.
                # Mọi lượt gọi khác (gắn nhãn, chấm) muốn cùng đầu vào ra cùng đầu
                # ra. Ở đây thì ngược lại: 30 câu ở nhiệt độ 0 sẽ trôi về cùng một
                # khuôn câu, và cái giống nhau đó đọc ra ngay là máy viết.
                temperature=0.8,
            ),
            feature="exam_write",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    block = clean(result.text)
    lines = [line.strip() for line in block.splitlines()]
    # Part 1 mở đầu bằng [PHOTO], Part 3/4 bằng [SCRIPT], còn lại là [QUESTION].
    header_ok = bool(lines) and lines[0] in (
        "[QUESTION]",
        PHOTO_MARKER,
        SCRIPT_MARKER,
        GRAPHIC_MARKER,
    )
    # Ba dấu hiệu của một khối HOÀN CHỈNH, không phải một khối bị cắt giữa chừng.
    # Chỉ hỏi "có mốc không" là không đủ: đầu ra bị cắt vẫn có mốc, và nó được
    # lưu như một ô đã xong.
    # Part 3/4 phải có ĐỦ BA câu, và đây là chỗ duy nhất đếm được rẻ. Thiếu một
    # câu thì parser vẫn đọc ra một cụm hợp lệ hai câu, `commit_part` vẫn ghi, và
    # đề lặng lẽ ngắn đi một câu ở đúng chỗ không ai đếm.
    wanted = LISTENING_QUESTIONS_PER_SET if part in (3, 4) else 1
    # Part 2 có BA lựa chọn, nên `(D)` là dấu hiệu sai ở đó — đòi nó thì mọi ô
    # Part 2 đều bị ném đi dù viết đúng.
    final = "(C)" if part == 2 else "(D)"
    complete = (
        header_ok
        and sum(1 for line in lines if line == "[QUESTION]") >= wanted
        and sum(1 for line in lines if line.startswith(final)) >= wanted
        and sum(1 for line in lines if line.lower().startswith("answer:")) >= wanted
    )
    if not complete:
        # NÉM chứ không lưu. Lưu một đầu ra không có mốc nghĩa là ô đó coi như
        # xong — hàng đợi là một truy vấn trên thư mục, nên lần chạy sau sẽ bỏ
        # qua nó, và thứ rác kia nằm lại tới tận chặng kiểm. Ném thì ô vẫn thiếu
        # tệp, và chạy lại lệnh là tự nó thử lại.
        raise MissingBlock(
            f"đầu ra không phải một khối hoàn chỉnh ({len(result.text)} ký tự) — "
            f"thường là bị cắt giữa phần suy luận"
        )
    return block


def pending(blueprint: Blueprint, workdir: Path) -> list[QuestionSlot]:
    """Ô nào còn thiếu tệp dán.

    Hàng đợi là một TRUY VẤN trên thư mục, không phải một bảng job — cùng luật
    với `backfill_audio` hỏi database "cái gì còn thiếu audio". Chạy lại lệnh là
    tìm thấy ít việc hơn, và đó là toàn bộ cơ chế phục hồi.
    """
    return [
        slot
        for part in blueprint.parts
        for slot in part.slots
        if not paste_path(workdir, slot).exists()
    ]


def save_slot(workdir: Path, slot: QuestionSlot, block: str) -> Path:
    path = paste_path(workdir, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(block.rstrip() + "\n")
    return path
