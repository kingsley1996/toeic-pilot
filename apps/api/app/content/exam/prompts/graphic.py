"""Luật hình ngữ liệu: định dạng bảng, và luật GIAO ĐIỂM của câu hỏi về hình.

Dùng chung cho Part 3, 4 và 7. Part 7 chỉ nhận ĐỊNH DẠNG — hình của nó là ngữ
liệu, câu hỏi hỏi về nội dung chứ không bắt chọn giữa bốn hàng."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts.contract import GRAPHIC_MARKER

GRAPHIC_FORMAT = f"""EVERY graphic has a `kind:` line, then a TITLE LINE of its own, then its data.
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

Separate cells with a vertical bar. Keep every value short."""

GRAPHIC_RULES_TEMPLATE = f"""

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
{GRAPHIC_FORMAT}

Invent your own titles, labels and numbers. The examples above are a shape to
copy, never content to copy — reusing their values makes two different papers
carry the same graphic.

Everything printed on the graphic is English: its title, its column headings,
its row names, every cell. The brief you are given is an internal note for the
author and may be written in Vietnamese — translate its labels, never copy them
across.

Three rules make it a real graphic question rather than a detail question:

1. The four options of the LAST question are exactly the four items on that
   kind's answer axis, and nothing else.
2. The speaker must NEVER say the winning item's name. It gives the other
   information instead ("the one that's about twenty-seven dollars", "the hour
   when we're both free", "right across from the bookstore"), so the listener
   has to read the graphic. If the weekly planner is named out loud, the graphic
   is decoration and the question is answerable without it.

   Nor may the talk name the OTHER three options. Elimination leaks the answer
   just as completely as naming it: a talk that says "Planning is finished,
   Development's at seventy-five percent, and Testing's at forty" has told the
   listener which phase is the remaining one, and the chart is never opened.
   Name AT MOST ONE of the four items out loud, and never the winning one.
3. The GRAPHIC alone must not answer it either. The answer sits where the two
   meet: the talk supplies a coordinate that is NOT on the answer axis, and the
   graphic looks that coordinate up. If someone can pick the right option from
   the picture without hearing a word, you have written a reading question with
   a recording stapled to it.

   What the talk must supply, by kind:
   - table / form: a value from one of the OTHER columns ("the plan that runs
     about fifty dollars"). The graphic maps that value to a row name.
   - schedule / survey: which ROW ("Room B", "the downtown branch"). The graphic
     maps that row to its free — or highest, or lowest — column.
   - chart: a value or a comparison ("the quarter we finally passed ninety
     thousand"). The graphic maps that value to a bar label.
   - map: a position or a relation ("right across from the bookstore", "the unit
     at the end of the corridor"). The graphic maps that position to a name.

   Two ways to break rule 3, both easy to write by accident:
   - The question just reads a cell out loud. "Which phase is forty percent
     complete?" is answered by looking at the chart. Ask instead what the
     SPEAKERS will do, pick, book or visit.
   - A label gives itself away. Asking where the sound engineer works when one
     room is named "Audio Control Room" needs no recording at all. The question
     has to turn on something only the talk says."""

# Thoại phải cấp toạ độ NGOÀI trục đáp án, và toạ độ đó khác nhau theo dạng.
_TALK_SUPPLIES = {
    "table": "một giá trị ở CỘT KHÁC (số ngày, hạn chót, giá…)",
    "form": "một giá trị ở CỘT KHÁC của phiếu",
    "schedule": "biết HÀNG nào (tên người, tên phòng)",
    "survey": "biết HÀNG nào (ai, chi nhánh nào trả lời)",
    "chart": "một trị số hoặc một phép so sánh",
    "map": "một vị trí hoặc một quan hệ vị trí",
}


def graphic_note(slot: QuestionSlot, speaker: str) -> str:
    """Dòng nhắc luật hình trong user prompt, RIÊNG theo `kind` của ô.

    System prompt đã có bảng đầy đủ, nhưng user prompt là chỗ model bám sát nhất
    vì nó cụ thể cho ô này — và bản cũ ở đây chỉ nhắc nửa luật ("không đọc tên
    đáp án"), đúng cái nửa đã chứng minh là không đủ: `p3-12` tuân thủ nó trọn
    vẹn rồi vẫn lộ đáp án bằng cách kể tên ba mục kia.
    """
    if not slot.graphic:
        return ""
    kind = slot.graphic.split(":")[0].strip()
    supplies = _TALK_SUPPLIES.get(kind, "một toạ độ ngoài trục đáp án")
    return (
        f"\n- Hình đi kèm — dùng ĐÚNG `kind: {kind}`: "
        f"{slot.graphic.partition(':')[2].strip()}"
        f"\n- {speaker} phải cho biết {supplies}, rồi HÌNH mới tra ra đáp án."
        f" Nói tối đa MỘT trong bốn mục và không bao giờ nói mục là đáp án —"
        f" kể tên ba mục kia cũng lộ đáp án bằng loại trừ."
        f" Ngược lại, nhìn hình một mình cũng KHÔNG được đủ để chọn."
    )


def graphic_rules(position: int) -> str:
    """Luật hình, gắn đúng VỊ TRÍ câu hỏi về hình của part đang viết.

    Vị trí khác nhau giữa hai part (Part 3 câu thứ ba, Part 4 câu thứ hai), nên
    một hằng số nói "câu cuối" là đúng cho Part 3 và sai cho Part 4 — và cái sai
    đó chỉ lộ ra ở cổng kiểm, sau khi đã trả tiền cho lượt gọi.
    """
    ordinal = {1: "one", 2: "two", 3: "three"}[position + 1]
    return GRAPHIC_RULES_TEMPLATE.format(ordinal=ordinal)
