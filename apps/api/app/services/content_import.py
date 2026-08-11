"""Parsing pasted content into draft records.

Pure functions returning parsed rows **and their problems**, never raising on the
first bad line: whoever pastes 300 words wants every complaint at once, not a
game of whack-a-mole. Nothing here writes to the database — the parse result is
shown for review first (ADR-005 §3.4).
"""

import re
import unicodedata
from dataclasses import dataclass, field

from app.core.media import LOGICAL_VOICE_ACCENTS
from app.models.vocabulary import PARTS_OF_SPEECH

# Pipe-delimited because the fields are short and a paste from a spreadsheet or a
# notes file needs no escaping rules to be readable. It breaks if a meaning
# contains "|", which is good enough for now and recorded as a known limit in
# SPEC-LEARNING-HUB.md §5.
FIELD_SEP = "|"

VOCABULARY_COLUMNS = (
    "headword",
    "part_of_speech",
    "phonetic",
    "meaning_en",
    "meaning_vi",
    "example",
    "example_vi",
)
REQUIRED_VOCABULARY_COLUMNS = ("headword", "part_of_speech", "meaning_en", "meaning_vi")


@dataclass
class ParsedVocabulary:
    line: int
    headword: str = ""
    part_of_speech: str = ""
    phonetic: str | None = None
    meaning_en: str = ""
    meaning_vi: str = ""
    example: str | None = None
    example_vi: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class ParsedDictation:
    line: int
    transcript: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


def parse_vocabulary(raw: str) -> list[ParsedVocabulary]:
    """One entry per line: headword | pos | phonetic | en | vi | example | example_vi.

    Trailing fields may be omitted; empty ones are allowed for anything not in
    `REQUIRED_VOCABULARY_COLUMNS`.
    """
    rows: list[ParsedVocabulary] = []
    seen: dict[tuple[str, str], int] = {}

    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(FIELD_SEP)]
        row = ParsedVocabulary(line=lineno)

        if len(parts) > len(VOCABULARY_COLUMNS):
            row.problems.append(
                f"too many fields ({len(parts)}); expected at most "
                f"{len(VOCABULARY_COLUMNS)}: {', '.join(VOCABULARY_COLUMNS)}"
            )
            rows.append(row)
            continue

        values = dict(zip(VOCABULARY_COLUMNS, parts, strict=False))
        row.headword = values.get("headword", "").strip()
        row.part_of_speech = values.get("part_of_speech", "").strip().lower()
        row.phonetic = _clean(values.get("phonetic", ""))
        row.meaning_en = values.get("meaning_en", "").strip()
        row.meaning_vi = values.get("meaning_vi", "").strip()
        row.example = _clean(values.get("example", ""))
        row.example_vi = _clean(values.get("example_vi", ""))

        for column in REQUIRED_VOCABULARY_COLUMNS:
            if not getattr(row, column):
                row.problems.append(f"{column} is required")

        if row.part_of_speech and row.part_of_speech not in PARTS_OF_SPEECH:
            row.problems.append(
                f"part_of_speech {row.part_of_speech!r} is not one of {list(PARTS_OF_SPEECH)}"
            )

        # Caught here rather than by the database, because a unique violation at
        # commit time aborts the whole batch and says nothing about which line.
        key = (row.headword.lower(), row.part_of_speech)
        if row.headword and row.part_of_speech:
            if key in seen:
                row.problems.append(f"duplicate of line {seen[key]} in this paste")
            else:
                seen[key] = lineno

        rows.append(row)
    return rows


def parse_dictation(raw: str) -> list[ParsedDictation]:
    """One sentence per line.

    No delimiter: the transcript is the whole line. Anything else would need
    escaping for a format whose only field is free text.
    """
    rows: list[ParsedDictation] = []
    seen: dict[str, int] = {}

    for lineno, line in enumerate(raw.splitlines(), start=1):
        transcript = line.strip()
        if not transcript:
            continue
        row = ParsedDictation(line=lineno, transcript=transcript)

        if len(transcript.split()) < 3:
            # Two words is not a dictation exercise; it is almost certainly a
            # stray line from the paste.
            row.problems.append("transcript is too short to be a dictation sentence")

        key = transcript.lower()
        if key in seen:
            row.problems.append(f"duplicate of line {seen[key]} in this paste")
        else:
            seen[key] = lineno

        rows.append(row)
    return rows


# --- đề thi: Part 5, 6, 7 (ADR-007 §2.3) ------------------------------------
#
# Định dạng khối, không phải phân tách bằng dấu gạch đứng như vocabulary. Lý do
# là hình dạng dữ liệu: một câu hỏi có đề bài nhiều dòng, bốn đáp án, và có thể
# một đoạn văn dài dùng chung. Ép vào một dòng ngăn bằng "|" sẽ tạo ra những
# dòng dài vài trăm ký tự mà mắt người không soát được — mà soát được chính là
# lý do bước xem trước tồn tại.
#
#   [PASSAGE] Tiêu đề tuỳ chọn       <- chỉ Part 6/7; lặp lại tối đa 3 lần
#   <văn bản>
#
#   [QUESTION]
#   <đề bài, có thể nhiều dòng>
#   (A) ...
#   (B) ...
#   (C) ...
#   (D) ...
#   answer: B
#   source: original
#   explanation: ...                 <- tuỳ chọn, nội dung viết TIẾNG VIỆT
#
# Một [PASSAGE] xuất hiện SAU một [QUESTION] mở một cụm mới; nhiều [PASSAGE] liền
# nhau thì cùng thuộc một cụm (Part 7 có bài đọc đôi và đọc ba).

# Mốc và khoá đều bằng **tiếng Anh ASCII thuần**, và đó là một quyết định chứ
# không phải thói quen: bản đầu dùng `[CÂU]` và `[NGỮ LIỆU]`, rồi hỏng ngay lần
# dùng đầu tiên vì macOS trả chữ Â ở dạng phân rã — chuỗi dán vào dài 6 ký tự
# thay vì 5 trong khi hiện lên **giống hệt**. ASCII không có dạng phân rã, nên
# cả lớp lỗi đó biến mất thay vì được vá.
#
# Nó cũng dễ soát hơn: mốc nổi bật khỏi phần nội dung tiếng Anh xung quanh, và
# một dòng sai chính tả nhìn ra được ngay.
SET_MARKER = "[PASSAGE]"
QUESTION_MARKER = "[QUESTION]"

# Dạng tiếng Việt vẫn được nhận, để nội dung soạn dở theo bản cũ không mất.
# Không phải định dạng chính, và thông báo lỗi chỉ nêu dạng tiếng Anh.
SET_ALIASES = ("[NGỮ LIỆU]", "[NGU LIEU]")
QUESTION_ALIASES = ("[CÂU]", "[CAU]")
QUESTION_SOURCES = ("original", "licensed")
# Số đoạn văn tối đa của một cụm, theo ĐÚNG format từng part:
#
#   Part 6 — Text Completion: **một** đoạn văn có các chỗ trống, mỗi chỗ trống
#            là một câu hỏi. Không có bài hai đoạn, và không có ảnh.
#   Part 7 — Reading Comprehension: bài một đoạn, hai đoạn hoặc ba đoạn.
#
# Cho Part 6 nhận nhiều đoạn là mở đường cho một cụm không tồn tại trong đề
# thật, và người soạn sẽ chỉ phát hiện khi so với đề mẫu.
MAX_PASSAGES = {6: 1, 7: 3}

_KEYS = {
    "đáp án": "answer",
    "dap an": "answer",
    "answer": "answer",
    "nguồn": "source",
    "nguon": "source",
    "source": "source",
    "giải thích": "explanation",
    "giai thich": "explanation",
    "explanation": "explanation",
    "ghi chú nguồn": "source_note",
    "source_note": "source_note",
}
_OPTION_LINE = re.compile(r"^\(([A-D])\)\s*(.*)$")


def _fold(text: str) -> str:
    """Bỏ dấu và viết hoa, để so khớp mốc không phụ thuộc cách gõ.

    Mốc chính thức giờ là ASCII (`[QUESTION]`), nên phần bỏ dấu chỉ còn phục vụ
    các dạng tiếng Việt cũ. Phần **viết hoa** thì vẫn cần cho cả hai: `[question]`
    gõ thường là chuyện bình thường.

    Vì sao vẫn giữ sau khi mốc đã là ASCII: nó ghi lại cách hỏng đã xảy ra thật.
    macOS trả chữ Â ở dạng phân rã, nên `"[CÂU]"` dán từ một số ứng dụng dài 6
    ký tự chứ không phải 5 — trong khi hai chuỗi hiện lên **giống hệt nhau**.
    """
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).upper()


_SET_FOLDED = tuple(_fold(marker) for marker in (SET_MARKER, *SET_ALIASES))
_QUESTION_FOLDED = tuple(_fold(marker) for marker in (QUESTION_MARKER, *QUESTION_ALIASES))


@dataclass
class ParsedTurn:
    """Một lượt nói trong bản thu: ai nói, nói gì."""

    text: str
    voice: str


@dataclass
class ParsedOption:
    label: str
    # None nghĩa là KHÔNG IN — giá trị đúng của Part 1 và 2, không phải dữ liệu
    # thiếu (ADR-001 §A2). Chuỗi rỗng không thay được: `validate_question` hỏi
    # `is not None`, nên `""` là "có in, in ra số 0 ký tự" và bị từ chối.
    content: str | None
    is_correct: bool


@dataclass
class ParsedQuestion:
    line: int
    prompt_text: str | None = None
    options: list[ParsedOption] = field(default_factory=list)
    source: str = ""
    source_note: str | None = None
    explanation: str | None = None
    # Chỉ Part 1 và 2: lời thoại của riêng câu này.
    script: list[ParsedTurn] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class ParsedGroup:
    """Một cụm: ngữ liệu dùng chung (nếu có) và các câu thuộc về nó.

    Part 5 cũng đi qua hình dạng này, mỗi cụm đúng một câu và không có ngữ liệu
    — nên nơi ghi vào database chỉ có một đường, và `question_set` là NULL đúng
    ở chỗ ADR-001 §A2 nói nó phải NULL.
    """

    line: int
    title: str | None = None
    passages: list[str] = field(default_factory=list)
    # Chỉ Part 3 và 4: bản thu dùng chung cho cả cụm.
    script: list[ParsedTurn] = field(default_factory=list)
    questions: list[ParsedQuestion] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and all(question.ok for question in self.questions)


def parse_reading_part(raw: str, part: int) -> list[ParsedGroup]:
    """Tách nội dung dán thành các cụm. **Không ghi gì vào database** (ADR-005).

    Trả về mọi vấn đề tìm được thay vì dừng ở lỗi đầu tiên: người dán 30 câu
    muốn biết hết một lượt, không phải đập chuột từng con.
    """
    if part not in (5, 6, 7):
        raise ValueError(f"parse_reading_part chỉ nhận part 5, 6, 7 — nhận được {part}")

    # Chuẩn hoá về NFC một lần ở đây, nên phần nội dung được lưu cũng đồng nhất:
    # hai chuỗi NFC/NFD hiện lên giống hệt nhau nhưng `==` trả về False, và sự
    # khác biệt đó sẽ đi thẳng vào `prompt_text` rồi nằm im tới lúc có ai đó so
    # sánh chuỗi.
    raw = unicodedata.normalize("NFC", raw)

    groups: list[ParsedGroup] = []
    current: ParsedGroup | None = None
    buffer: list[str] = []
    mode: str | None = None
    start_line = 0

    def flush() -> None:
        nonlocal buffer, mode, current
        if mode is None:
            buffer = []
            return
        text = "\n".join(buffer).strip()
        if mode == "passage" and current is not None:
            if text:
                current.passages.append(text)
            else:
                current.problems.append(f"dòng {start_line}: {SET_MARKER} không có nội dung")
        elif mode == "question" and current is not None:
            current.questions.append(_parse_question_block(text, start_line, part))
        buffer = []
        mode = None

    for lineno, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()

        folded = _fold(stripped)

        if folded.startswith(_SET_FOLDED):
            flush()
            # Ngữ liệu mở cụm mới CHỈ khi cụm hiện tại đã có câu hỏi. Nhiều khối
            # ngữ liệu liền nhau là bài đọc đôi/ba của Part 7, không phải hai cụm.
            if current is None or current.questions:
                current = ParsedGroup(line=lineno)
                groups.append(current)
            title = stripped.partition("]")[2].strip()
            if title and current.title is None:
                current.title = title
            mode, start_line = "passage", lineno
            continue

        if folded.startswith(_QUESTION_FOLDED):
            flush()
            if current is None:
                current = ParsedGroup(line=lineno)
                groups.append(current)
            # Part 5 không có ngữ liệu, nên mỗi câu là một cụm riêng.
            elif part == 5 and current.questions:
                current = ParsedGroup(line=lineno)
                groups.append(current)
            mode, start_line = "question", lineno
            continue

        if mode is not None:
            buffer.append(line)

    flush()

    if not groups and raw.strip():
        # Im lặng ở đây chính là lỗi đã xảy ra thật: dán 10 câu, nhận về 0 cụm
        # và 0 lỗi, tức giao diện báo "hợp lệ" cho một thứ nó không đọc được
        # dòng nào. Không nhận ra gì là một kết quả, và nó phải được nói ra.
        raise ValueError(
            f"Không nhận ra dòng nào. Mỗi câu phải bắt đầu bằng một dòng "
            f"{QUESTION_MARKER}" + (f", và ngữ liệu bằng {SET_MARKER}" if part != 5 else "") + "."
        )

    for group in groups:
        _check_group(group, part)
    return groups


def _parse_question_block(text: str, line: int, part: int) -> ParsedQuestion:
    question = ParsedQuestion(line=line)
    prompt: list[str] = []
    answer: str | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        option = _OPTION_LINE.match(stripped)
        if option:
            label, content = option.group(1), option.group(2).strip()
            question.options.append(ParsedOption(label=label, content=content, is_correct=False))
            continue

        key, _, value = stripped.partition(":")
        field_name = _KEYS.get(key.strip().lower())
        if field_name and value.strip():
            if field_name == "answer":
                answer = value.strip().upper()
            elif field_name == "source":
                question.source = value.strip().lower()
            elif field_name == "explanation":
                question.explanation = value.strip()
            else:
                question.source_note = value.strip()
            continue

        # Chưa có đáp án nào thì đây còn là đề bài; sau đó thì là dòng lạc.
        if question.options:
            question.problems.append(f"không hiểu dòng {stripped[:40]!r}")
        else:
            prompt.append(stripped)

    question.prompt_text = " ".join(prompt).strip()
    _check_question(question, answer, part)
    return question


def _check_question(question: ParsedQuestion, answer: str | None, part: int) -> None:
    if not question.prompt_text:
        # Part 5, 6, 7 đều IN đề bài — `validate_question` cũng đòi đúng thế,
        # nên trình dán không được nới lỏng hơn cổng chặn ở tầng dưới.
        question.problems.append("thiếu đề bài")

    labels = [option.label for option in question.options]
    if len(question.options) != 4:
        question.problems.append(f"cần đúng 4 đáp án, đang có {len(question.options)}")
    if len(set(labels)) != len(labels):
        question.problems.append("đáp án bị trùng nhãn")
    if any(not option.content for option in question.options):
        question.problems.append(f"part {part} in đáp án, nên đáp án không được để trống")

    if answer is None:
        question.problems.append("thiếu dòng 'answer:'")
    elif answer not in labels:
        question.problems.append(f"đáp án {answer!r} không có trong các nhãn {sorted(labels)}")
    else:
        for option in question.options:
            option.is_correct = option.label == answer

    # `source` KHÔNG có giá trị mặc định, ở bất kỳ tầng nào (ADR-007 §2.5).
    # Trả lời sai câu "nội dung này ở đâu ra" là rủi ro pháp lý, và một giá trị
    # mặc định là cách chắc chắn nhất để không ai từng trả lời nó.
    if not question.source:
        question.problems.append(
            "thiếu dòng 'source:' — phải là 'original' (tự viết theo định dạng) "
            "hoặc 'licensed' (đã xin được phép)"
        )
    elif question.source not in QUESTION_SOURCES:
        question.problems.append(
            f"nguồn {question.source!r} không hợp lệ; phải là một trong {list(QUESTION_SOURCES)}"
        )


def _check_group(group: ParsedGroup, part: int) -> None:
    if not group.questions:
        group.problems.append("cụm này không có câu hỏi nào")

    if part == 5:
        if group.passages:
            group.problems.append("Part 5 không có ngữ liệu dùng chung")
        if len(group.questions) > 1:
            group.problems.append("Part 5 mỗi câu đứng riêng, không gom cụm")
        return

    if not group.passages:
        group.problems.append(f"Part {part} cần ít nhất một khối {SET_MARKER}")

    limit = MAX_PASSAGES[part]
    if len(group.passages) > limit:
        group.problems.append(
            f"Part {part} tối đa {limit} đoạn văn cho một cụm, đang có {len(group.passages)}"
            + (" — Part 6 là một đoạn văn có nhiều chỗ trống" if part == 6 else "")
        )


# --- đề thi: Part 1, 2, 3, 4 (phần Nghe) ------------------------------------
#
# Ngữ pháp khác phần Đọc ở một điểm gốc rễ: **Part 1 và 2 không in gì cả**. ETS
# nói rõ cho cả hai — lời dẫn và các câu đáp chỉ được ĐỌC LÊN, không in trong đề
# — nên `prompt_text` và `question_option.content` phải NULL, và thứ biên tập
# viên gõ vào chính là LỜI THOẠI.
#
#   [SCRIPT] Tiêu đề tuỳ chọn        <- chỉ Part 3/4: ngữ liệu nói dùng chung
#   voice: us_female_1
#   Hi, I'm calling about the chairs we ordered.
#   voice: us_male_1
#   I'm sorry about that.
#
#   [QUESTION]
#   <Part 3/4: đề bài IN ra · Part 1/2: lời dẫn được ĐỌC>
#   (A) ...                          <- Part 1/2: lời đọc · Part 3/4: đáp án in
#   (B) ...
#   (C) ...
#   (D) ...                          <- Part 2 chỉ có ba đáp án
#   answer: B
#   source: original
#
# `voice:` là công tắc: mọi dòng sau nó thuộc giọng đó, cho tới `voice:` kế
# tiếp. Một luật cho cả bốn part, thay vì bốn cú pháp phải nhớ riêng.

SCRIPT_MARKER = "[SCRIPT]"
SCRIPT_ALIASES = ("[LỜI THOẠI]", "[LOI THOAI]")
_SCRIPT_FOLDED = tuple(_fold(marker) for marker in (SCRIPT_MARKER, *SCRIPT_ALIASES))

# Part 1 và 2 in ra con số 0 chữ. Part 3 và 4 in đề bài và đáp án như phần Đọc.
UNPRINTED_PARTS = (1, 2)
LISTENING_OPTION_COUNT = {1: 4, 2: 3, 3: 4, 4: 4}


def parse_listening_part(raw: str, part: int) -> list[ParsedGroup]:
    """Tách nội dung dán của phần Nghe. **Không ghi gì vào database.**"""
    if part not in LISTENING_OPTION_COUNT:
        raise ValueError(f"parse_listening_part chỉ nhận part 1-4 — nhận được {part}")

    raw = unicodedata.normalize("NFC", raw)
    groups: list[ParsedGroup] = []
    current: ParsedGroup | None = None
    buffer: list[str] = []
    mode: str | None = None
    start_line = 0

    def flush() -> None:
        nonlocal buffer, mode, current
        if mode is not None and current is not None:
            text = "\n".join(buffer).strip()
            if mode == "script":
                current.script = _parse_turns(text, start_line, current)
            else:
                current.questions.append(_parse_listening_question(text, start_line, part))
        buffer = []
        mode = None

    for lineno, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        folded = _fold(stripped)

        if folded.startswith(_SCRIPT_FOLDED):
            flush()
            if current is None or current.questions:
                current = ParsedGroup(line=lineno)
                groups.append(current)
            title = stripped.partition("]")[2].strip()
            if title and current.title is None:
                current.title = title
            mode, start_line = "script", lineno
            continue

        if folded.startswith(_QUESTION_FOLDED):
            flush()
            if current is None:
                current = ParsedGroup(line=lineno)
                groups.append(current)
            # Part 1 và 2: mỗi câu là một cụm riêng, đúng như Part 5.
            elif part in UNPRINTED_PARTS and current.questions:
                current = ParsedGroup(line=lineno)
                groups.append(current)
            mode, start_line = "question", lineno
            continue

        if mode is not None:
            buffer.append(line)

    flush()

    if not groups and raw.strip():
        raise ValueError(
            f"Không nhận ra dòng nào. Mỗi câu phải bắt đầu bằng {QUESTION_MARKER}"
            + (f", và lời thoại dùng chung bằng {SCRIPT_MARKER}" if part in (3, 4) else "")
            + "."
        )

    for group in groups:
        _check_listening_group(group, part)
    return groups


def _parse_turns(text: str, line: int, group: ParsedGroup) -> list[ParsedTurn]:
    """Các lượt nói, theo công tắc `voice:`."""
    turns: list[ParsedTurn] = []
    voice: str | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        key, _, value = stripped.partition(":")
        if key.strip().lower() in ("voice", "giọng", "giong") and value.strip():
            voice = value.strip()
            if voice not in LOGICAL_VOICE_ACCENTS:
                group.problems.append(
                    f"dòng {line}: giọng {voice!r} không có; "
                    f"các giọng: {sorted(LOGICAL_VOICE_ACCENTS)}"
                )
            continue
        if voice is None:
            group.problems.append(f"dòng {line}: cần một dòng 'voice:' trước lời thoại")
            return turns
        turns.append(ParsedTurn(text=stripped, voice=voice))
    return turns


def _parse_listening_question(text: str, line: int, part: int) -> ParsedQuestion:
    question = ParsedQuestion(line=line)
    lead: list[str] = []
    answer: str | None = None
    voice: str | None = None
    spoken: list[ParsedTurn] = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        option = _OPTION_LINE.match(stripped)
        if option:
            label, content = option.group(1), option.group(2).strip()
            if part in UNPRINTED_PARTS:
                # Đáp án của Part 1/2 được ĐỌC chứ không in: nội dung đi vào lời
                # thoại, còn `content` để None — đó là giá trị đúng theo ADR-001
                # §A2, không phải dữ liệu thiếu.
                spoken.append(ParsedTurn(text=content, voice=voice or ""))
                question.options.append(ParsedOption(label=label, content=None, is_correct=False))
            else:
                question.options.append(
                    ParsedOption(label=label, content=content, is_correct=False)
                )
            continue

        key, _, value = stripped.partition(":")
        field_name = _KEYS.get(key.strip().lower())
        if key.strip().lower() in ("voice", "giọng", "giong") and value.strip():
            voice = value.strip()
            if voice not in LOGICAL_VOICE_ACCENTS:
                question.problems.append(f"giọng {voice!r} không có trong danh sách")
            continue
        if field_name and value.strip():
            if field_name == "answer":
                answer = value.strip().upper()
            elif field_name == "source":
                question.source = value.strip().lower()
            elif field_name == "explanation":
                question.explanation = value.strip()
            else:
                question.source_note = value.strip()
            continue

        if question.options:
            question.problems.append(f"không hiểu dòng {stripped[:40]!r}")
        elif part in UNPRINTED_PARTS:
            # Part 1: lời dẫn ("Look at the picture marked number one…").
            # Part 2: chính câu hỏi được đọc lên.
            spoken.append(ParsedTurn(text=stripped, voice=voice or ""))
        else:
            lead.append(stripped)

    # `or None`: không có dòng đề bài nào thì giá trị đúng là NULL, không phải
    # chuỗi rỗng. Part 1/2 luôn rơi vào nhánh này vì phần chữ đã đi vào lời thoại.
    question.prompt_text = " ".join(lead).strip() or None
    question.script = spoken
    _check_listening_question(question, answer, part)
    return question


def _check_listening_question(question: ParsedQuestion, answer: str | None, part: int) -> None:
    expected = LISTENING_OPTION_COUNT[part]
    labels = [option.label for option in question.options]
    if len(question.options) != expected:
        question.problems.append(f"Part {part} cần đúng {expected} đáp án, đang có {len(labels)}")
    if len(set(labels)) != len(labels):
        question.problems.append("đáp án bị trùng nhãn")

    if part in UNPRINTED_PARTS:
        # `prompt_text` PHẢI rỗng: `validate_question` từ chối câu Part 1/2 có
        # đề bài, và trình dán không được nới lỏng hơn cổng chặn ở tầng dưới.
        if question.prompt_text:
            question.problems.append(f"Part {part} không in đề bài; phần chữ thuộc về lời thoại")
        if not question.script:
            question.problems.append(f"Part {part} cần lời thoại — đây là toàn bộ nội dung câu")
        if any(not turn.voice for turn in question.script):
            question.problems.append("cần một dòng 'voice:' trước lời thoại")
    else:
        if not question.prompt_text:
            question.problems.append(f"Part {part} in đề bài, nên không được để trống")
        if any(not option.content for option in question.options):
            question.problems.append(f"Part {part} in đáp án, nên đáp án không được để trống")

    if answer is None:
        question.problems.append("thiếu dòng 'answer:'")
    elif answer not in labels:
        question.problems.append(f"đáp án {answer!r} không có trong {sorted(labels)}")
    else:
        for option in question.options:
            option.is_correct = option.label == answer

    if not question.source:
        question.problems.append("thiếu dòng 'source:' — phải là 'original' hoặc 'licensed'")
    elif question.source not in QUESTION_SOURCES:
        question.problems.append(f"nguồn {question.source!r} không hợp lệ")


def _check_listening_group(group: ParsedGroup, part: int) -> None:
    if not group.questions:
        group.problems.append("cụm này không có câu hỏi nào")

    if part in UNPRINTED_PARTS:
        if group.script:
            group.problems.append(f"Part {part} để lời thoại trên từng câu, không dùng cụm")
        if len(group.questions) > 1:
            group.problems.append(f"Part {part} mỗi câu đứng riêng")
        return

    # Part 3 và 4: một bản thu dùng chung cho cả cụm, gắn ở `question_set`
    # (ADR-001 §A4.3). Không có lời thoại thì không có gì để thu.
    if not group.script:
        group.problems.append(f"Part {part} cần một khối {SCRIPT_MARKER} cho cả cụm")
