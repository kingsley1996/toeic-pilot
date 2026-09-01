"""Lời nhắc (prompt) cho các phép kiểm có gọi mô hình.

Tách khỏi `check.py` theo đúng ranh giới đã dùng cho `mixes.py` và
`blueprint.py`: đây là **chữ người ta chỉnh**, còn bên kia là **mã quyết định
đạt hay không đạt**. Sửa một câu trong prompt không nên phải mở tệp chứa thuật
toán chấm.

Lưu ý phạm vi: `check.py` **không** tách được theo part như
`REFACTOR-LONG-FILES.md` §3 dự tính. Các phép kiểm ở đó gần như không phụ thuộc
part — chỉ 12 nhánh rẽ theo part trên toàn tệp — nên chẻ theo part sẽ nhân đôi
phần dùng chung thay vì tách được thứ gì. Cái tách được là prompt, và chỉ prompt.
"""

# Trần đầu ra cho hai phép kiểm bằng model. Câu trả lời chỉ có một chữ cái,
# nhưng model SUY LUẬN viết cả nghìn ký tự tự nhủ trước — đo được: qwen3.8 nghĩ
# 6 275 ký tự về một câu Part 3 rồi hết hạn mức trước khi kịp trả lời. Cắt ở đó
# đọc ra như "không trả về chữ cái hợp lệ", tức là đổ lỗi cho câu hỏi thay vì
# cho giới hạn của chính ta.
# Câu trả lời chỉ là một chữ cái, nhưng model bắt buộc suy luận tiêu trần vào
# phần NGHĨ trước đã. Đo thật ngày 2026-08-31: p3-07 nghĩ 18 716 ký tự rồi chết ở
# trần 4 000, và triệu chứng đọc ra là "không đếm được phương án điền được" — tức
# đổ lỗi cho câu hỏi thay vì cho giới hạn của chính ta.
CHECK_MAX_TOKENS = 16000


# Lời nhắc chặng kiểm viết bằng TIẾNG ANH, khác phần còn lại của tệp. Người chấm
# ở đây đóng vai người ĐI THI: đọc câu tiếng Anh rồi tự chọn đáp án, và đây là
# bề mặt duy nhất trong pipeline bắt model phán đoán tiếng Anh mà không có một
# mỏ neo tiếng Anh nào (chặng viết còn nguyên system prompt tiếng Anh của nó).
# `AMBIGUITY_SYSTEM_PART2` là chỗ rõ nhất: nó hỏi "người bản ngữ có nói thế
# không".
#
# CHƯA ĐO. Đây là lập luận, không phải số liệu — phép đo là chạy `check --model`
# trên cùng một tập ô của `tp-form-06` bằng cả hai bản rồi so số lỗi bắt được.
VERIFY_SYSTEM_PART6 = """You are answering one TOEIC Part 6 question. You are
given the whole passage; the blanks in it are numbered. Choose the option that
fills the blank you are asked about. Reply with exactly ONE capital letter: A, B,
C or D. No explanation."""


AMBIGUITY_SYSTEM_PART6 = """You are reviewing one TOEIC Part 6 question.

You are given the whole passage and four options for one numbered blank. Reply
with the letter of EVERY option that leaves the passage both grammatical and
consistent with the sentences around it.

Part 6 tests reading a whole passage, not one line: an option that is
grammatical but does not fit the surrounding text does NOT count as workable.

Reply with the letters only, run together, no explanation."""


VERIFY_SYSTEM_PART2 = """You hear one TOEIC Part 2 question and three responses.
Reply with exactly ONE capital letter — the response that fits best: A, B or C.
No explanation, nothing else."""


AMBIGUITY_SYSTEM_PART2 = """You are reviewing one TOEIC Part 2 question.

You are given the question and its three responses. Reply with the letter of
EVERY response that genuinely answers it — answering means a native speaker
would actually say that, not that it "sounds acceptable".

There are only three options: A, B, C. There is no D. Reply with the letters
only, run together, no explanation."""


VERIFY_SYSTEM_PART3 = """You hear one TOEIC Part 3 conversation and answer one
question about it. You are given the transcript. Reply with exactly ONE capital
letter: A, B, C or D. No explanation, nothing else."""


AMBIGUITY_SYSTEM_PART3 = """You are reviewing one TOEIC Part 3 question.

You are given the transcript and four options. Reply with the letter of EVERY
option the transcript ACTUALLY supports — supported by what is said, not "could
be true if you infer further".

Reply with the letters only, run together, no explanation. Example: `B` or `AB`."""


VERIFY_SYSTEM_PART1 = """You hear four statements describing one TOEIC Part 1
photograph. You are given a description of that photograph. Reply with exactly
ONE capital letter — the statement that correctly describes the photograph: A,
B, C or D. No explanation, nothing else."""


AMBIGUITY_SYSTEM_PART1 = """You are reviewing one TOEIC Part 1 question.

You are given a description of the photograph and four statements. Reply with
the letter of EVERY statement that correctly describes the photograph — correct
as verifiable from the description, not "could be true from another angle".

Reply with the letters only, run together, no explanation. Example: `B` or `AB`."""


VERIFY_SYSTEM = """You are answering one TOEIC Part 5 question. Reply with
exactly ONE capital letter: A, B, C or D. No explanation, nothing else."""


AMBIGUITY_SYSTEM = """You are reviewing one TOEIC Part 5 question.

Read the sentence four times, each time putting a different option into the
------- blank. Reply with the letter of EVERY option that leaves the sentence
both grammatical and natural to a user of business English.

Reply with the letters only, run together, no explanation. Example: `B` or `AB`."""


_VERIFY_SYSTEM_FOR = {
    1: VERIFY_SYSTEM_PART1,
    2: VERIFY_SYSTEM_PART2,
    3: VERIFY_SYSTEM_PART3,
    4: VERIFY_SYSTEM_PART3,
    6: VERIFY_SYSTEM_PART6,
}


_AMBIGUITY_SYSTEM_FOR = {
    1: AMBIGUITY_SYSTEM_PART1,
    2: AMBIGUITY_SYSTEM_PART2,
    3: AMBIGUITY_SYSTEM_PART3,
    4: AMBIGUITY_SYSTEM_PART3,
    6: AMBIGUITY_SYSTEM_PART6,
}


GRAPHIC_VERDICT_SYSTEM = """You review ONE TOEIC listening item that comes with a
graphic. You are given the graphic, the full transcript, and the question with
its four options. Judge it against one rule and report which case it falls into.

THE RULE
The answer must sit where the two sources MEET. The talk supplies a coordinate
that is NOT on the answer axis — a name, a price, a position, a room. The
graphic looks that coordinate up and yields the answer. Both are required:
neither source alone may settle it.

THE FOUR CASES
GRAPHIC_ONLY — the graphic alone settles it. Reading the table, chart or map is
  enough; the talk adds nothing needed. This includes a question that merely
  reads a cell out ("Which phase is forty percent complete?" against a chart
  showing Testing 40), and a question whose answer is given away by a label
  ("Where does the sound engineer work?" when a room is named Audio Control
  Room).
TALK_ONLY — the talk alone settles it, and there are TWO ways. Either a speaker
  names the winning option out loud. Or the talk accounts for the OTHER options
  and leaves the winner as the only one unexplained — elimination settles it
  just as completely, and the listener never opens the graphic. So count how
  many of the four options the talk accounts for: if it is more than one, ask
  whether what remains is already forced. A talk saying "Planning is finished,
  Development's at seventy-five percent, and Testing's at forty", asked which
  phase is only fifteen percent along, is TALK_ONLY — three of four are spoken
  for and the fourth needs no chart.
NEITHER — the two together still do not settle it: the coordinate the talk gives
  does not appear in the graphic, or it matches more than one option.
OK — both are needed and together they settle it, on exactly one option.

WORKED EXAMPLE OF `OK`
Graphic: a table of resident parking fees; rows Motorcycle $8, Sedan $35, SUV
$50, Visitor free. Talk: the woman says she drives "one of the larger cars"; the
manager says larger vehicles are fifty dollars a month. Question: what type of
vehicle does the woman drive? Answer: SUV.
The talk never says "SUV"; the graphic cannot know what she drives. The talk
gives a price, the graphic maps the price to a row name. That is `OK`.

Reply with exactly one word: GRAPHIC_ONLY, TALK_ONLY, NEITHER or OK. No
explanation."""
