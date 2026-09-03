"""Chặng kiểm: chạy TRƯỚC khi tốn một giây audio hay một tấm ảnh nào.

Ba tầng, và tầng đầu là tầng quan trọng nhất về mặt kiến trúc.

**Tầng cú pháp gọi thẳng parser thật**, không viết bản kiểm riêng. Một bản kiểm
riêng sẽ trôi khỏi parser, và ngày nó trôi thì pipeline báo "hợp lệ" cho đúng
thứ mà `POST /parts/parse` sẽ từ chối — người chạy nhận được hai câu trả lời trái
ngược từ hai chỗ, và không chỗ nào sai rõ ràng.

**Tầng ngữ nghĩa** bắt những gì parser không thể biết: đáp án có thật sự đúng
không, nhiễu có sai một cách hợp lý không, 30 câu có lặp lại nhau không.

**Tầng đối chiếu đáp án dùng một lượt gọi KHÁC, với bốn lựa chọn đã xáo thứ tự.**
Không xáo thì mô hình có xu hướng chọn lại đúng vị trí nó vừa đặt đáp án, và phép
kiểm thành một nghi thức luôn xanh.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.content.exam import explanation as exp_format
from app.content.exam.blueprint import (
    LISTENING_QUESTIONS_PER_SET,
    QUESTIONS_PER_SET,
    Blueprint,
    QuestionSlot,
)
from app.content.exam.check_prompts import (
    _AMBIGUITY_SYSTEM_FOR,
    _VERIFY_SYSTEM_FOR,
    AMBIGUITY_SYSTEM,
    CHECK_MAX_TOKENS,
    GRAPHIC_VERDICT_SYSTEM,
    VERIFY_SYSTEM,
)
from app.content.exam.writer import BLANK, RETRY_DELAY, RETRY_TRIES, paste_path
from app.services.content_import import (
    ParsedOption,
    ParsedQuestion,
    parse_listening_part,
    parse_reading_part,
)
from app.services.llm.base import LLMQuotaExhausted, LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier

# Đáp án dài hơn hẳn phần còn lại là một manh mối rò rỉ: người làm bài đoán được
# mà không cần đọc câu. Ngưỡng đặt theo tỉ lệ chứ không theo số ký tự tuyệt đối,
# vì một câu từ vựng và một câu chia động từ có độ dài rất khác nhau.
LENGTH_TELL_RATIO = 1.8


# …nhưng chỉ khi lựa chọn dài nhất đủ dài để tỉ lệ có nghĩa. Câu ngữ pháp có
# lựa chọn là những từ hai ba chữ cái (`by` / `until`), và ở cỡ đó "dài gấp đôi"
# là sáu ký tự so với ba — không ai đoán được đáp án từ chuyện đó. Đo được: hai
# cờ đầu tiên của lượt chạy thật đều thuộc loại này, tức là ngưỡng tỉ lệ đơn
# thuần sinh ra báo động giả nhanh hơn sinh ra tín hiệu.
LENGTH_TELL_MIN_CHARS = 12


@dataclass
class SlotReport:
    slot_id: str
    number: int
    problems: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    # Các chữ cái mà người chấm nói là điền được. Ghi lại cho MỌI câu, kể cả câu
    # đạt: phân bố của cả cột này là thứ duy nhất phát hiện được người chấm đang
    # trả lời phản xạ — nhìn riêng những câu bị cờ thì không thấy gì.
    workable: str | None = None

    @property
    def blocked(self) -> bool:
        """Có `problems` là KHÔNG nạp được; `flags` chỉ là chỗ người cần nhìn."""
        return bool(self.problems)


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def parse_one(block: str, part: int = 5) -> tuple[ParsedQuestion | None, list[str]]:
    """Đọc một khối bằng parser THẬT. Trả (câu, vấn đề)."""
    try:
        groups = (
            parse_listening_part(block, part)
            if part in (1, 2, 3, 4)
            else parse_reading_part(block, part)
        )
    except ValueError as error:
        return None, [str(error)]
    questions = [question for group in groups for question in group.questions]
    if len(questions) != 1:
        return None, [f"khối phải chứa đúng một câu, đọc được {len(questions)}"]
    question = questions[0]
    return question, list(question.problems)


def _stem(question: ParsedQuestion, part: int, context: str) -> str:
    """Phần người chấm được đọc trước khi chọn.

    Part 1 KHÔNG in đề bài, nên `context` (mô tả ảnh) là tất cả những gì có.
    Part 3/4 in đề bài NHƯNG câu hỏi vô nghĩa nếu thiếu lời thoại — hỏi "người
    phụ nữ sẽ làm gì tiếp theo" mà không cho nghe hội thoại thì mô hình vẫn trả
    về một chữ cái, và phép kiểm trông như đang chạy.

    **Part 2 cũng không in gì, và câu hỏi của nó nằm ở LƯỢT NÓI ĐẦU** — không
    phải ở `prompt_text`, vốn là NULL. Đọc `prompt_text` ở đó là gửi cho người
    chấm ba câu đáp mà không có câu hỏi nào, và nó vẫn trả về một chữ cái. Đo
    được: 15 trên 25 câu bị báo "đối chiếu chọn khác" ở lượt chạy đầu, toàn bộ
    là nhiễu đo chứ không phải lỗi nội dung.
    """
    if part == 1:
        return context.strip()
    if part == 2:
        spoken = [turn.text for turn in question.script]
        return spoken[0] if spoken else ""
    if part in (3, 4, 6, 7) and context.strip():
        # Part 6 cũng cần cả NGỮ LIỆU: đề bài của nó chỉ là nhãn `Blank (N)`,
        # nên gửi mỗi thế là hỏi "điền gì vào chỗ trống thứ nhất" mà không cho
        # xem đoạn văn nào. Đây là lần thứ TƯ cùng một lỗi trong pipeline này.
        #
        # …và Part 7 là lần thứ NĂM. Nó rơi xuống nhánh cuối và người chấm chỉ
        # nhận được đề bài trần: "What is the main purpose of the e-mail?" mà
        # không có email nào. Đo thật ngày 2026-08-31: 50 cờ trên 54 câu, phần
        # lớn là "có 4 phương án điền được (ABCD)" — toàn bộ là NHIỄU ĐO, không
        # một cái nào là lỗi nội dung. Một người chấm mù vẫn trả về một chữ cái,
        # nên phép kiểm TRÔNG như đang chạy.
        return f"{context.strip()}\n\n{question.prompt_text or ''}"
    return question.prompt_text or ""


def option_text(option: ParsedOption) -> str:
    """Chữ của một lựa chọn, dù nó được IN hay được NÓI.

    Part 1 và 2 không in gì, nên `content` là NULL ở đó và chữ nằm ở
    `spoken_text`. Đọc thẳng `content` là mọi phép kiểm ngữ nghĩa của phần Nghe
    so bốn chuỗi rỗng với nhau — và chúng đều "đạt".
    """
    return ((option.content or option.spoken_text) or "").strip()


def parse_group(
    block: str, part: int, wanted: int | None = None, wanted_passages: int | None = None
) -> tuple[list[ParsedQuestion], str, list[str]]:
    """Đọc một khối CỤM (Part 3, 4): trả (các câu, lời thoại dạng chữ, vấn đề).

    Lời thoại đi ra dưới dạng chữ vì mọi phép kiểm ngữ nghĩa của Part 3/4 đều cần
    nó: một câu hỏi "người phụ nữ sẽ làm gì tiếp theo" không kiểm được nếu người
    chấm không được nghe hội thoại — và nó vẫn trả về một chữ cái, nên phép kiểm
    sẽ TRÔNG như đang chạy.
    """
    reading = part in (6, 7)
    try:
        groups = parse_reading_part(block, part) if reading else parse_listening_part(block, part)
    except ValueError as error:
        return [], "", [str(error)]
    if len(groups) != 1:
        return [], "", [f"khối phải chứa đúng một cụm, đọc được {len(groups)}"]
    group = groups[0]
    problems = list(group.problems)
    if wanted is None:
        wanted = QUESTIONS_PER_SET.get(part, LISTENING_QUESTIONS_PER_SET)
    if len(group.questions) != wanted:
        problems.append(f"cụm Part {part} cần {wanted} câu, đọc được {len(group.questions)}")

    if reading:
        # Ngữ liệu của phần ĐỌC là chữ in, không phải lời thoại — nhưng nó đóng
        # đúng vai đó ở mọi chặng sau: đây là thứ người chấm phải đọc mới trả lời
        # được, và là khoá chống trùng của cụm.
        for question in group.questions:
            problems.extend(question.problems)
        if not group.passages:
            problems.append("cụm không có ngữ liệu")
        elif wanted_passages is not None and len(group.passages) != wanted_passages:  # noqa: E501
            # Đếm ngữ liệu, không chỉ hỏi "có ngữ liệu không".
            #
            # Đo được: cả ba cụm BA ngữ liệu của lượt chạy đầu chỉ sinh ra MỘT
            # khối `[PASSAGE]` — mô hình gộp cả ba tài liệu vào một đoạn. Parser
            # nhận (1–3 đều hợp lệ), cổng cũ chỉ hỏi "có ngữ liệu không", nên
            # nhóm bài đọc ba ngữ liệu lặng lẽ biến thành nhóm một ngữ liệu và
            # mất đúng cái làm nên nhóm đó.
            problems.append(f"cụm cần {wanted_passages} ngữ liệu, đọc được {len(group.passages)}")
        return group.questions, "\n\n".join(group.passages), problems

    if not group.script:
        # Parser cho phép dán cụm KHÔNG kèm lời thoại (bản thu gắn sau bằng
        # `import_media`), nhưng ở pipeline này lời thoại là thứ mô hình vừa
        # viết ra — thiếu nó nghĩa là đầu ra hỏng, không phải quy trình khác.
        problems.append("cụm không có lời thoại")
    script = "\n".join(f"{turn.voice}: {turn.text}" for turn in group.script)
    for question in group.questions:
        problems.extend(question.problems)
    return group.questions, script, problems


def check_shape(question: ParsedQuestion, part: int = 5) -> list[str]:
    """Những luật của một part mà parser không tự nói ra."""
    problems: list[str] = []
    if part == 7:
        if question.source != "original":
            problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
        return problems
    if part == 6:
        # Đề bài của một câu Part 6 chỉ là nhãn chỗ trống; chỗ trống thật nằm
        # trong ngữ liệu. Kiểm nó ở `check_part6` cùng với ngữ liệu, chứ không
        # ở đây — một câu Part 6 nhìn riêng không đủ để nói đúng hay sai.
        if question.source != "original":
            problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
        return problems
    if part in (3, 4):
        # Part 3/4 IN đáp án ra sách thi — ngược hẳn Part 1/2. Parser đã bắt
        # `content` rỗng, nên ở đây chỉ còn luật riêng của pipeline.
        if question.prompt_text and BLANK in question.prompt_text:
            problems.append("câu Part 3/4 không có chỗ trống — đây không phải câu điền")
        if question.source != "original":
            problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
        return problems
    if part == 1:
        # Part 1 KHÔNG in gì cả — bốn câu là lời nói, `prompt_text` phải là NULL.
        # Parser đã cưỡng chế điều đó, nên ở đây chỉ còn luật riêng của pipeline:
        # bốn câu nói phải có thật, vì `spoken_text` rỗng thì clip sẽ im lặng và
        # không gì báo cho tới lúc có người bấm play.
        empty = [o.label for o in question.options if not (o.spoken_text or "").strip()]
        if empty:
            problems.append(f"câu nói rỗng ở lựa chọn {', '.join(empty)}")
        if question.source != "original":
            problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
        return problems
    if question.prompt_text and "-------" not in question.prompt_text:
        # Chỗ trống là hình dạng của Part 5. Không có nó thì câu vẫn hợp lệ với
        # parser nhưng không phải một câu Part 5, và cái sai đó chỉ lộ ra khi có
        # người học đọc.
        problems.append("thiếu chỗ trống `-------` trong đề bài")
    if question.source != "original":
        problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
    return problems


def check_voice_names(question: ParsedQuestion) -> list[str]:
    """Không lựa chọn nào được là một TÊN GIỌNG.

    `uk_female_1` là chỉ dẫn thu âm, không phải một con người — nhưng nó nằm
    ngay trong prompt, nên mô hình nhỏ chép thẳng vào phần in ra. Đo được: một
    cụm Part 3 có ba trong bốn lựa chọn là tên giọng, và câu hỏi trở nên vô
    nghĩa. Đây là VẤN ĐỀ chứ không phải cờ: không có cách đọc nào khiến nó đúng.
    """
    from app.core.media import LOGICAL_VOICE_ACCENTS

    bad = [
        option.label
        for option in question.options
        if option_text(option).strip().lower() in LOGICAL_VOICE_ACCENTS
    ]
    if not bad:
        return []
    return [
        f"lựa chọn {', '.join(bad)} là TÊN GIỌNG chứ không phải nội dung — "
        f"tên giọng là chỉ dẫn thu âm, không bao giờ được in ra đề"
    ]


def check_options(question: ParsedQuestion) -> list[str]:
    flags: list[str] = []
    contents = [option_text(option) for option in question.options]
    if len(set(_normalise(text) for text in contents)) != len(contents):
        flags.append("có hai lựa chọn trùng nhau sau khi chuẩn hoá")

    lengths = [len(text) for text in contents if text]
    if lengths:
        longest, rest = max(lengths), sorted(lengths)[:-1]
        average = sum(rest) / len(rest) if rest else longest
        if longest >= LENGTH_TELL_MIN_CHARS and average and longest > average * LENGTH_TELL_RATIO:
            flags.append(f"một lựa chọn dài bất thường ({longest} vs trung bình {average:.0f})")
    return flags


# Chữ cái nêu trong lời giải thích, ví dụ "(A) đúng" hay "nên (B)". Bắt cả dạng
# có ngoặc lẫn không, vì hai kiểu đều xuất hiện trong đầu ra thật.
_EXPLAINED_LETTER = re.compile(r"\(([A-D])\)\s*(?:là\s+)?(?:đáp án\s+)?đúng|nên\s*\(?([A-D])\)?\b")

# Đoạn tiếng Anh đặt trong ngoặc kép — thứ lời giải thích dùng làm bằng chứng.
#
# KHÔNG lọc độ dài trong chính regex. `"([^"]{12,})"` ghép nhầm cặp: gặp một
# trích dẫn ngắn (`"report"`, `"Where...?"` — Part 2 đầy thứ này) nó bỏ qua dấu
# mở ấy rồi ghép dấu ĐÓNG của cặp đó với dấu MỞ của cặp sau, nuốt trọn đoạn
# tiếng Việt ở giữa và coi đó là một trích dẫn. Đoạn ấy tất nhiên không có trong
# ngữ liệu, nên cổng báo oan hàng loạt. Ghép hết rồi lọc bằng Python.
_QUOTED = re.compile(r'"([^"]*)"')
_QUOTE_MIN_CHARS = 12


def check_explanation(question: ParsedQuestion, evidence: str) -> list[str]:
    """Hai cổng cho lời giải thích. Cả hai bắt kiểu hỏng ĐỌC RẤT TRÔI CHẢY.

    1. **Chữ cái nêu trong giải thích phải khớp đáp án.** Một mô hình biện hộ cho
       đáp án sai cũng mượt mà y như biện hộ cho đáp án đúng, nên đọc bằng mắt
       không phát hiện được ở quy mô vài trăm câu.
    2. **Đoạn trích phải có thật trong ngữ liệu.** Đây là kiểu tệ nhất: người học
       đi tìm một câu không tồn tại rồi kết luận tai mình có vấn đề, chứ không
       kết luận lời giải thích sai.

    `evidence` là lời thoại / đoạn văn / nội dung các lựa chọn — tuỳ part. Rỗng
    thì bỏ qua cổng thứ hai: không có gì để đối chiếu thì im lặng còn hơn báo
    bừa. Trả `flags` chứ không `problems`: một lời giải thích lệch không làm câu
    hỏi sai, nên nó cần người nhìn chứ không đáng chặn cả đợt nạp.
    """
    text = (question.explanation or "").strip()
    if not text:
        return []

    flags: list[str] = []
    answer = next((o.label for o in question.options if o.is_correct), None)
    labels = [o.label for o in question.options]
    value = text.split(":", 1)[1].strip() if text.lower().startswith("explanation:") else text
    parsed = exp_format.parse(value)

    flags.extend(exp_format.problems(value, labels))
    if parsed is None:
        # Lối cũ, văn xuôi tự do: chỉ đối chiếu được chữ cái mà nó tự nêu là đúng.
        claimed = {a or b for a, b in _EXPLAINED_LETTER.findall(text)} - {""}
        if answer and claimed and answer not in claimed:
            flags.append(
                f"giải thích nói ({'/'.join(sorted(claimed))}) đúng nhưng đáp án là ({answer})"
            )
    else:
        # Mệnh đề mở đầu bằng chính lời của lựa chọn thì đối chiếu được CHÍNH XÁC
        # nó có nằm đúng nhãn không. Bắt lỗi lúc SINH, chứ phép cân thì đã đúng
        # theo cấu trúc — nó đổi chỗ payload, không sửa chữ trong câu.
        for label, clause in parsed.clauses.items():
            opening = _QUOTED.match(clause.lstrip())
            content = next((o.content for o in question.options if o.label == label), None)
            if opening is None or not content:
                continue
            if _normalise(opening.group(1)) not in _normalise(content):
                flags.append(f"mệnh đề ({label}) mở đầu bằng lời của một lựa chọn khác")

    if evidence:
        haystack = _normalise(evidence)
        for quote in _QUOTED.findall(text):
            if len(quote) < _QUOTE_MIN_CHARS:
                continue
            if _normalise(quote) not in haystack:
                flags.append(f"trích dẫn không có trong ngữ liệu: {quote[:48]!r}")
    return flags


def verify_answer(
    gateway: Gateway,
    question: ParsedQuestion,
    tier: Tier,
    seed: int,
    part: int = 5,
    context: str = "",
) -> str | None:
    """Hỏi lại mô hình với bốn lựa chọn ĐÃ XÁO. Trả về cờ nếu lệch, `None` nếu khớp.

    Đây là phép kiểm đắt nhất của chặng này (một lượt gọi mỗi câu) và cũng là
    phép duy nhất chạm tới thứ quan trọng nhất — đáp án có đúng không. Hai mô
    hình cùng dòng vẫn có thể sai giống nhau, nên nó GẮN CỜ cho người xem chứ
    không tự sửa và không tự loại.
    """
    labelled = [(option.label, option_text(option)) for option in question.options]
    truth = next(
        (
            label
            for label, option in zip([o.label for o in question.options], question.options)
            if option.is_correct
        ),
        None,
    )
    if truth is None:
        return "không tìm thấy đáp án đúng để đối chiếu"

    order = list(labelled)
    random.Random(seed).shuffle(order)
    letters = "ABCD"[: len(order)]
    shuffled = "\n".join(f"({letters[i]}) {text}" for i, (_, text) in enumerate(order))
    expected = letters[[label for label, _ in order].index(truth)]

    stem = _stem(question, part, context)
    # `max_tokens` rộng dù câu trả lời chỉ có một chữ cái: model SUY LUẬN xuất
    # chuỗi suy nghĩ trước, và cắt ở 4 token thì nó trả về rỗng — một lỗi đọc ra
    # như "không trả về chữ cái hợp lệ", tức là đổ lỗi cho câu hỏi thay vì cho
    # giới hạn của chính ta.
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=_VERIFY_SYSTEM_FOR.get(part, VERIFY_SYSTEM),
                user=f"{stem}\n{shuffled}",
                max_tokens=CHECK_MAX_TOKENS,
                temperature=0.0,
            ),
            feature="exam_verify",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    picked = result.text.strip().upper()[:1]
    if picked not in letters:
        return f"lượt đối chiếu không trả về chữ cái hợp lệ ({result.text.strip()[:20]!r})"
    if picked != expected:
        original = order[letters.index(picked)][0]
        return f"đối chiếu chọn ({original}), đề ghi đáp án ({truth})"
    return None


def count_workable_options(
    gateway: Gateway,
    question: ParsedQuestion,
    tier: Tier,
    part: int = 5,
    context: str = "",
) -> tuple[int, str]:
    """Hỏi thẳng: có bao nhiêu phương án điền được? Trả (số lượng, các chữ cái).

    Đây là phép kiểm cho ĐÚNG lỗi nội dung trội nhất — câu có hơn một đáp án
    dùng được — và nó là thứ mà mọi phép kiểm khác trong tệp này đều mù: bốn
    phương án đồng nghĩa không trùng chuỗi, không lệch độ dài, và vẫn là bốn
    đáp án đúng.

    Suy gián tiếp từ chuyện người chấm bất đồng thì KHÔNG tách được "đáp án ghi
    sai" với "hai đáp án cùng đúng" — hai lỗi cần hai cách xử lý khác nhau. Hỏi
    thẳng thì tách được.

    Trả về `0` khi không đọc được câu trả lời: một con số không đọc được không
    được phép trở thành "đạt".
    """
    letters = "".join(f"({option.label}) {option_text(option)}\n" for option in question.options)
    stem = _stem(question, part, context)
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=_AMBIGUITY_SYSTEM_FOR.get(part, AMBIGUITY_SYSTEM),
                user=f"{stem}\n{letters}",
                max_tokens=CHECK_MAX_TOKENS,
                temperature=0.0,
            ),
            feature="exam_ambiguity",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    found = "".join(sorted({ch for ch in result.text.upper() if ch in "ABCD"}))
    return len(found), found


def _graphic_as_text(source: Path) -> str:
    """Bảng ở dạng chữ, để người chấm đọc được thứ người học sẽ nhìn."""
    from app.content.exam.graphics import parse_graphic

    return f"[Hình in kèm trong sách thi]\n{parse_graphic(source.read_text()).alt_text()}"


def _is_prompt_example(graphic: object) -> bool:
    """Hình có trùng với một trong các ví dụ viết trong `GRAPHIC_RULES` không."""
    from app.content.exam import prompts

    rows = getattr(graphic, "rows", [])
    if not rows:
        return False
    body = _normalise(prompts.GRAPHIC_RULES_TEMPLATE)
    copied = sum(1 for row in rows if _normalise(" ".join(row)) in body)
    # QUÁ NỬA số hàng, không phải tất cả: mô hình hay đổi đúng một con số rồi
    # giữ nguyên phần còn lại, và đòi trùng khít thì lần chép đó lọt qua.
    return copied * 2 > len(rows)


def check_graphic(
    questions: list[ParsedQuestion], script: str, source: Path, part: int = 3
) -> tuple[list[str], list[str]]:
    """Kiểm hình ngữ liệu của một cụm. Trả (vấn đề, cờ).

    Hai luật, và cả hai đều quyết định hình là NGỮ LIỆU hay chỉ là trang trí:

    1. **Bốn lựa chọn của câu cuối phải là trục đáp án của hình.** Trục đó khác
       nhau theo dạng — đo ở đề mẫu ETS, câu 64 hỏi giữa bốn loại sổ (tên hàng
       của một bảng), câu 67 giữa bốn khung giờ (tiêu đề cột của một lưới lịch),
       câu 70 giữa bốn cửa hàng (ô của một sơ đồ). Lựa chọn lấy từ chỗ khác
       nghĩa là người học không cần nhìn hình.
    2. **Lời thoại KHÔNG được đọc tên hàng là đáp án.** Nếu có người nói "the
       weekly planner" thì câu trả lời được ngay từ audio, và tấm hình thành ra
       thừa. Đây là lỗi khó thấy nhất của dạng câu này: mọi thứ khác vẫn hợp lệ,
       câu vẫn có đúng một đáp án, chỉ là nó không còn là câu hỏi Part 3 về hình.
    """
    from app.content.exam.graphics import parse_graphic

    if not source.exists():
        return [f"thiếu dữ liệu bảng ({source.name})"], []
    graphic = parse_graphic(source.read_text())
    problems = list(graphic.problems())
    # Mô hình chép nguyên VÍ DỤ trong prompt khá thường. Nó không sai về hình
    # thức, nên không cổng nào khác thấy — nhưng hai đề sinh bằng cùng prompt sẽ
    # dùng chung một tấm hình, và người luyện nhiều đề nhận ra ngay.
    if _is_prompt_example(graphic):
        problems.append("hình chép nguyên ví dụ trong prompt — cần dữ liệu của riêng nó")
    if problems or not questions:
        return problems, []

    from app.content.exam.blueprint import GRAPHIC_POSITION

    # ĐÚNG MỘT câu hỏi về hình mỗi cụm. Đề thật không bao giờ có hai — và khi mô
    # hình viết hai, cả hai đều dùng đúng trục đáp án nên phép so trục vẫn xanh.
    # Cái mất là câu thứ ba: nó lẽ ra hỏi một dạng khác, và cụm mất một dạng câu
    # mà blueprint đã giao.
    marked = [
        index
        for index, question in enumerate(questions)
        if "look at the graphic" in (question.prompt_text or "").lower()
    ]
    want_at = GRAPHIC_POSITION.get(part, len(questions) - 1)
    if marked != [want_at]:
        at = ", ".join(str(index + 1) for index in marked) or "không câu nào"
        problems.append(
            f'"Look at the graphic" phải nằm ở đúng câu thứ {want_at + 1} và chỉ một câu '
            f"— đang ở câu {at}"
        )
        return problems, []

    # Part 3 hỏi về hình ở câu thứ ba, Part 4 ở câu thứ hai (đề mẫu ETS: câu 64,
    # 67, 70 so với 96, 99). Lấy cứng `questions[-1]` thì ở Part 4 ta đang kiểm
    # nhầm câu — và câu bị kiểm nhầm vẫn có bốn lựa chọn hợp lệ, nên cổng vẫn
    # cho ra một kết luận, chỉ là về sai câu.
    last = questions[GRAPHIC_POSITION.get(part, len(questions) - 1)]
    options = [_normalise(option_text(option)) for option in last.options]
    # TRỤC ĐÁP ÁN khác nhau theo dạng hình, và đây là chỗ dễ sai nhất: bảng thì
    # lấy tên hàng, lưới lịch lấy tiêu đề CỘT (khung giờ), biểu đồ lấy nhãn cột,
    # sơ đồ lấy tên ô. Lấy nhầm trục thì câu hỏi vẫn hợp lệ về mọi mặt và vẫn có
    # đúng một đáp án — nó chỉ không còn hỏi về tấm hình nữa.
    axis = [_normalise(item) for item in graphic.answer_axis()]
    if sorted(options) != sorted(axis):
        problems.append(
            f"bốn lựa chọn của câu cuối phải đúng là trục đáp án của hình "
            f"dạng {graphic.kind} — hình có {axis}, câu hỏi có {options}"
        )
        return problems, []

    flags: list[str] = []
    if graphic.kind == "schedule":
        # Cột đầu của lưới lịch là những CON NGƯỜI, và hội thoại phải là của
        # chính họ. Đo được: một cụm có bảng ghi "Liam" và "Emma" trong khi hai
        # người nói tên là Sarah và James — bảng và hội thoại nói về hai nhóm
        # người khác nhau, nên câu hỏi không có đáp án. Mọi cổng khác vẫn xanh:
        # bảng hợp lệ, bốn lựa chọn khớp trục, câu vẫn có đúng một `Answer:`.
        lowered = _normalise(script)
        missing = [row[0] for row in graphic.rows if row and _normalise(row[0]) not in lowered]
        if missing:
            problems.append(
                f"người trong lịch không xuất hiện trong hội thoại: {', '.join(missing)}"
            )
            return problems, []

    correct = next((option for option in last.options if option.is_correct), None)
    if correct is not None and _normalise(option_text(correct)) in _normalise(script):
        flags.append(
            "lời thoại đọc thẳng tên hàng là đáp án — người nghe không cần nhìn "
            "hình nữa, nên đây không còn là câu hỏi về hình"
        )
    return problems, flags


_GRAPHIC_VERDICTS = {
    "GRAPHIC_ONLY": (
        "hình TỰ trả lời được — người học không cần nghe. Câu phải hỏi thứ chỉ lời "
        "thoại nói ra, rồi dùng hình để tra ra đáp án"
    ),
    "TALK_ONLY": (
        "lời thoại TỰ trả lời được — tấm hình thành trang trí. Thoại phải nói thông "
        "tin khác thay vì đọc tên đáp án"
    ),
    "NEITHER": (
        "ghép cả hình lẫn lời thoại vẫn không ra đúng một đáp án — toạ độ thoại đưa "
        "không có trên hình, hoặc khớp nhiều hơn một lựa chọn"
    ),
}


def graphic_rule_verdict(
    gateway: Gateway,
    question: ParsedQuestion,
    script: str,
    source: Path,
    tier: Tier,
) -> tuple[str, str | None]:
    """Câu hỏi về hình có đúng luật giao điểm không. Trả (phán quyết, lời mô tả lỗi).

    Đây là nửa còn thiếu của luật hình: `check_graphic` cấm lời thoại đọc tên đáp
    án, còn "hình không được tự trả lời" thì không luật tất định nào nói được.

    Hỏi bằng PHÂN LOẠI có tiêu chí, không bằng cách bảo model tự trả lời câu hỏi
    rồi xem có trúng không. Cách sau phụ thuộc một lần đoán: bốn lựa chọn thì
    đoán bừa trúng 1/4, và trúng hay trượt đều bị đọc thành kết luận. Ở đây model
    được đọc CẢ hình lẫn lời thoại, được cho luật và một ví dụ đạt, rồi chỉ phải
    nói item rơi vào ô nào trong bốn ô — thứ nó có đủ dữ kiện để xét.

    Phán quyết không đọc được KHÔNG được biến thành "đạt": caller ghi nó thành cờ.

    Đo tay với glm-5.3-flash ngày 2026-08-31 trên hai bản `p3-12` thật: bản kể
    tên ba trong bốn lựa chọn ra `TALK_ONLY`, bản đạt ra `OK`. Trước khi vế loại
    trừ được thêm vào `TALK_ONLY`, bản hỏng ra `OK` — rubric thiếu vế nào thì mù
    đúng vế đó, và test với gateway giả không thấy được điều này.
    """
    letters = "".join(f"({o.label}) {option_text(o)}\n" for o in question.options)
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=GRAPHIC_VERDICT_SYSTEM,
                user=(
                    f"{_graphic_as_text(source)}\n\n"
                    f"[TRANSCRIPT]\n{script.strip()}\n\n"
                    f"[QUESTION]\n{question.prompt_text or ''}\n{letters}"
                ),
                max_tokens=CHECK_MAX_TOKENS,
                temperature=0.0,
            ),
            feature="exam_ambiguity",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    verdict = result.text.strip().upper()
    for name in ("GRAPHIC_ONLY", "TALK_ONLY", "NEITHER", "OK"):
        if name in verdict:
            return name, _GRAPHIC_VERDICTS.get(name)
    return verdict[:40], None


_INSERT_RE = re.compile(r"positions marked \[1\], \[2\], \[3\],? and \[4\]", re.IGNORECASE)


_VOCAB_RE = re.compile(r'the word ["“]([^"”]+)["”]', re.IGNORECASE)


_QUOTE_RE = re.compile(r'writes,\s*["“]([^"”]+)["”]', re.IGNORECASE)


_LINE_REF = re.compile(r"\bline\s+\d+", re.IGNORECASE)


def check_part7_forms(questions: list[ParsedQuestion], passages: str) -> list[str]:
    """Ba dạng câu của Part 7 áp ràng buộc lên chính NGỮ LIỆU.

    Cả ba đều hỏng theo cùng một kiểu: câu vẫn đọc trôi chảy, vẫn có đúng một
    đáp án, và thứ nó trỏ tới thì không có trong ngữ liệu. Người học đi tìm một
    chỗ không tồn tại và kết luận là mình đọc sót.
    """
    problems: list[str] = []
    body = passages
    for index, question in enumerate(questions, start=1):
        stem = question.prompt_text or ""

        if _INSERT_RE.search(stem):
            missing = [mark for mark in ("[1]", "[2]", "[3]", "[4]") if mark not in body]
            if missing:
                problems.append(
                    f"câu {index} là câu điền câu nhưng ngữ liệu thiếu dấu {', '.join(missing)}"
                )
            labels = {(option.content or "").strip() for option in question.options}
            if labels != {"[1]", "[2]", "[3]", "[4]"}:
                problems.append(f"câu {index}: bốn lựa chọn phải đúng là [1] [2] [3] [4]")

        found = _VOCAB_RE.search(stem)
        if found and "closest in meaning" in stem.lower():
            word = found.group(1).strip()
            # Đúng MỘT lần trong cả cụm. Đó là thứ thay cho số dòng của đề giấy:
            # số dòng vô nghĩa khi chữ tự xuống dòng theo bề ngang màn hình, còn
            # "chỉ có một chỗ" thì đúng trên mọi thiết bị (§29.2).
            hits = len(re.findall(rf"\b{re.escape(word)}\b", body, re.IGNORECASE))
            if hits != 1:
                problems.append(
                    f"câu {index}: từ {word!r} xuất hiện {hits} lần trong ngữ liệu — phải đúng một"
                )
            if _LINE_REF.search(stem):
                problems.append(
                    f"câu {index}: bỏ số dòng khỏi đề bài — chữ tự xuống dòng nên nó trỏ sai"
                )

        quoted = _QUOTE_RE.search(stem)
        if quoted and quoted.group(1).strip() not in body:
            problems.append(
                f"câu {index}: lời trích {quoted.group(1)[:40]!r} không có trong ngữ liệu"
            )
    return problems


def _check_set(
    slot: QuestionSlot,
    block: str,
    part: int,
    blueprint: Blueprint,
    gateway: Gateway | None,
    tier: Tier,
    ambiguity: bool,
    seen: dict[str, str],
    workdir: Path,
) -> list[SlotReport]:
    """Kiểm một cụm Part 3/4: một báo cáo cho MỖI câu, không một cho cả cụm.

    Ba câu một báo cáo thì `prune` chỉ có thể xoá cả cụm hoặc giữ cả cụm — mà
    đơn vị sinh lại đúng là cả cụm (ba câu hỏi về cùng một đoạn thoại, viết rời
    thì trùng nhau). Nhưng đơn vị ĐỌC là từng câu: người duyệt cần biết câu nào
    trong ba câu có vấn đề. Nên vấn đề của cụm được nhân ra cả ba báo cáo, và
    `prune` xoá tệp đúng một lần dù ba báo cáo cùng đỏ.
    """
    # Ngữ liệu là HÌNH thì KHÔNG có khối `[PASSAGE]` — nó không có chữ nào, và
    # ô ngữ liệu của nó chỉ mang ảnh (`_passages` giữ ô có ảnh mà không có chữ).
    # Đếm cả hai loại như nhau là đòi mô hình viết một khối rỗng, và cụm trộn
    # chữ với hình — đúng hình dạng của bài đọc ba ngữ liệu — không bao giờ qua.
    text_passages = sum(1 for spec in slot.passages if not spec) if part == 7 else None
    questions, script, shared = parse_group(block, part, len(slot.question_types), text_passages)
    # Ngữ liệu để đối chiếu trích dẫn: CHÍNH khối dán, trừ các dòng giải thích.
    # Dùng cả khối thay vì ghép script + passage vì `parse_group` không trả ngữ
    # liệu ra ngoài, và cả khối lại đúng hơn — nó phủ mọi part, kể cả Part 2 nơi
    # bằng chứng nằm trong ba câu đáp. Phải trừ dòng `Explanation:` đi, nếu
    # không một trích dẫn bịa sẽ khớp với chính nó và cổng thành vô dụng.
    evidence = "\n".join(
        line for line in block.splitlines() if not line.strip().lower().startswith("explanation:")
    )
    if slot.graphic:
        source = workdir / "graphics" / f"{slot.id}.txt"
        graphic_problems, graphic_flags = check_graphic(questions, script, source, part)
        shared = [*shared, *graphic_problems]
        # Người chấm phải được ĐỌC BẢNG, không chỉ nghe hội thoại.
        #
        # Câu "Look at the graphic" được viết sao cho hội thoại KHÔNG đọc tên
        # hàng là đáp án — đó là toàn bộ điểm của dạng câu này. Nên đưa mỗi lời
        # thoại vào là hỏi một câu không thể trả lời, và người chấm vẫn trả về
        # một chữ cái: cùng kiểu mù đã làm 26 câu bị gắn cờ oan ở §22.2. Đo
        # được: ba câu về hình bị gắn cờ khi thiếu bảng, sạch khi có.
        # Nửa còn thiếu của luật hình, và nó chỉ chạy khi hình đã hợp lệ: hỏi
        # model về một tấm bảng đã hỏng thì câu trả lời không nói lên gì.
        if gateway is not None and ambiguity and not graphic_problems and source.exists():
            from app.content.exam.blueprint import GRAPHIC_POSITION

            asked = questions[GRAPHIC_POSITION.get(part, len(questions) - 1)]
            try:
                verdict, complaint = graphic_rule_verdict(gateway, asked, script, source, tier)
            except LLMQuotaExhausted:
                raise
            except Exception as failure:  # noqa: BLE001
                verdict, complaint = "", None
                graphic_flags = [*graphic_flags, f"không xét được luật hình: {failure}"]
            if complaint:
                shared = [*shared, complaint]
            elif verdict and verdict != "OK":
                # Phán quyết không đọc được KHÔNG được thành "đạt" — nhưng cũng
                # không chặn nạp, vì lỗi nằm ở lượt gọi chứ không ở nội dung.
                graphic_flags = [*graphic_flags, f"phán quyết luật hình lạ: {verdict!r}"]
        # Cùng điều kiện với lượt hỏi phán quyết ngay trên: một tấm hình đã
        # hỏng thì không dựng thành chữ được. Thiếu `not graphic_problems` ở
        # đây, `alt_text()` gặp hàng biểu đồ thiếu cột và ném IndexError — một
        # lỗi lẽ ra được BÁO CÁO lại giết cả lượt kiểm 103 ô ở ô thứ 54.
        if source.exists() and not graphic_problems:
            script = f"{script}\n\n{_graphic_as_text(source)}"
            # …và vào cả NGỮ LIỆU ĐỐI CHIẾU. Lời giải thích trích thẳng một ô
            # của bảng ("Refund | Yes"), nhưng `evidence` chỉ dựng từ khối dán
            # nên mọi trích dẫn kiểu đó bị báo là bịa. Ghép NGUỒN THÔ chứ không
            # phải `alt_text`: mô hình trích đúng chữ trong tệp, còn alt_text đã
            # diễn lại thành câu tiếng Việt nên không khớp.
            evidence = f"{evidence}\n\n{source.read_text()}"
    else:
        graphic_flags = []
    if part == 7:
        shared = [*shared, *check_part7_forms(questions, script)]
        # …và đếm riêng số HÌNH, thứ nằm ở hiện vật khác.
        wanted_graphics = sum(1 for spec in slot.passages if spec)
        if wanted_graphics:
            # Tên `have`, KHÔNG phải `found`: `found` đã mang nghĩa khác trong
            # chính hàm này (các chữ cái người chấm nói là điền được). Dùng lại
            # tên là đúng cái bẫy `total` mà CLAUDE.md ghi — mypy bắt được lần
            # này, nhưng nó chỉ bắt vì hai kiểu khác nhau.
            have = len(list((workdir / "graphics").glob(f"{slot.id}.txt"))) + len(
                list((workdir / "graphics").glob(f"{slot.id}-*.txt"))
            )
            if have != wanted_graphics:
                shared = [*shared, f"cụm cần {wanted_graphics} hình, có {have}"]
            # …và ĐƯA NỘI DUNG của chúng cho người chấm. Dòng nối hình vào
            # `script` ở trên nằm trong nhánh `slot.graphic`, tức chỉ Part 3/4;
            # hình Part 7 sống ở `slot.passages` nên khối này trước đây chỉ ĐẾM
            # tệp. Hệ quả: mọi câu Part 7 hỏi về bảng đều bị chấm mà không có
            # bảng — lần thứ SÁU của cùng một lỗi, và lần nào cũng lộ ra thành
            # "cả bốn phương án đều dùng được" chứ không thành một lỗi đọc được.
            for found_path in sorted(
                [
                    *(workdir / "graphics").glob(f"{slot.id}.txt"),
                    *(workdir / "graphics").glob(f"{slot.id}-*.txt"),
                ]
            ):
                script = f"{script}\n\n{_graphic_as_text(found_path)}"
                evidence = f"{evidence}\n\n{found_path.read_text()}"
    # Hội thoại trùng là lỗi ở tầng ĐỀ và đáng nói RIÊNG, không nấp trong một
    # thông báo về đề bài: ba câu vẫn khác nhau, chỉ có đoạn thoại là lặp lại,
    # và người học nghe lại đúng một đoạn hai lần trong cùng một đề.
    voice_key = _normalise(script)
    if voice_key:
        if voice_key in seen:
            shared = [*shared, f"hội thoại trùng với {seen[voice_key]}"]
        else:
            seen[voice_key] = slot.id
    if not questions:
        return [SlotReport(slot_id=slot.id, number=slot.number, problems=shared or ["khối rỗng"])]

    reports: list[SlotReport] = []
    for index, question in enumerate(questions):
        report = SlotReport(slot_id=slot.id, number=slot.number + index)
        report.problems.extend(shared)
        report.problems.extend(check_shape(question, part))
        report.problems.extend(check_voice_names(question))
        report.flags.extend(check_options(question))
        # Ngữ liệu để đối chiếu trích dẫn KHÁC nhau theo part: Part 3/4 là lời
        # thoại, Part 6/7 là đoạn văn, Part 2 là chính ba câu đáp (đề không in
        # gì nên lời giải thích phải thuật lại chúng). Part 1 và 5 không có ngữ
        # liệu chữ — cổng trích dẫn tự tắt ở đó thay vì báo bừa.
        report.flags.extend(check_explanation(question, evidence))
        from app.content.exam.blueprint import GRAPHIC_POSITION

        if index == GRAPHIC_POSITION.get(part, len(questions) - 1):
            report.flags.extend(graphic_flags)

        # Khoá chống trùng của Part 3/4 gồm CẢ lời thoại, không chỉ đề bài.
        #
        # "What will the man do next?" là khuôn câu chuẩn của Part 3 và lặp lại
        # nhiều lần trong một đề THẬT — câu trả lời nằm ở hội thoại chứ không ở
        # đề bài. Chống trùng trên riêng đề bài bắt đúng ba câu như thế ở lượt
        # chạy đầu, và nếu tin nó thì cổng kiểm đang ép mô hình bịa ra những câu
        # hỏi không tự nhiên để né chính nó.
        #
        # Cái đáng bắt là hai câu hỏi giống nhau về CÙNG một đoạn thoại — và
        # gộp lời thoại vào khoá thì bắt luôn cả trường hợp hai cụm có hội thoại
        # trùng nhau, vì lúc đó cả hai nửa của khoá đều trùng.
        key = _normalise(f"{question.prompt_text or ''} | {script}")
        if key and key in seen:
            report.problems.append(f"câu này trùng với {seen[key]}")
        elif key:
            seen[key] = f"{slot.id} câu {index + 1}"

        if gateway is not None:
            try:
                flag = verify_answer(
                    gateway, question, tier, blueprint.seed + report.number, part, script
                )
            except LLMQuotaExhausted:
                raise
            except Exception as failure:  # noqa: BLE001
                flag = f"không đối chiếu được đáp án: {failure}"
            if flag:
                report.flags.append(flag)
            if ambiguity:
                try:
                    count, found = count_workable_options(gateway, question, tier, part, script)
                except LLMQuotaExhausted:
                    raise
                except Exception as failure:  # noqa: BLE001
                    count, found = 1, None
                    report.flags.append(f"không đếm được phương án điền được: {failure}")
                report.workable = found
                if count != 1:
                    report.flags.append(
                        f"có {count} phương án điền được ({found or 'không đọc được'}) — "
                        f"một câu chỉ được có đúng một"
                    )
        reports.append(report)
    return reports


def check_blueprint(
    blueprint: Blueprint,
    workdir: Path,
    gateway: Gateway | None = None,
    tier: Tier = Tier.CHEAP,
    ambiguity: bool = False,
    only: int | None = None,
    quiet: bool = False,
    slot_id: str | None = None,
) -> list[SlotReport]:
    """Kiểm mọi ô đã có tệp dán. `gateway=None` thì bỏ mọi tầng cần gọi model.

    `ambiguity=True` bật phép kiểm "có mấy phương án điền được". Nó là phép kiểm
    ĐÚNG lỗi trội nhất, nhưng cũng là phép nhiễu nhất: người chấm yếu sẽ gật đầu
    với những phương án mà người bản ngữ loại ngay. Nên nó ghi thành CỜ chứ không
    chặn nạp, và chỉ lệnh `prune` mới quyết định dựa vào nó.

    `slot_id` thu về ĐÚNG một ô, và nó chỉ đáng dùng cho lượt CÓ gọi model. Đồ
    thị gọi hàm này sau mỗi ô: với `only=part` thì ô thứ k kéo theo cả k ô đã
    viết, nên chi phí cộng dồn thành bình phương — đo được 8,2 lần mức cần thiết
    trên một đề, riêng Part 5 là 15,5 lần. Tệ hơn tiền: một ô đã đạt bị chấm lại
    hàng chục lần, và mỗi lần model có thể trả lời khác, nên nó "hỏng" vì nhiễu
    ở lượt kiểm của một ô khác.

    Lượt MIỄN PHÍ thì vẫn nên để `only=part`: phép dò hội thoại trùng là chuyện
    giữa các ô, thu về một ô là mất nó, và ở đó không có gì để tiết kiệm.
    """
    reports: list[SlotReport] = []
    seen: dict[str, str] = {}

    slots: list[tuple[int, QuestionSlot]] = [
        (part.part, slot)
        for part in blueprint.parts
        for slot in part.slots
        if (only is None or part.part == only) and (slot_id is None or slot.id == slot_id)
    ]
    for slot_index, (part_number, slot) in enumerate(slots, start=1):
        if not quiet:
            # Dòng tiến độ là để người chạy `check` biết nó chưa treo. Đồ thị gọi
            # lại hàm này cho MỖI vòng của MỖI ô, nên ở đó nó chỉ là nhiễu che
            # mất dòng kết cục — xem `exam_agents/graph.py`.
            print(f"  … [{slot_index}/{len(slots)}] {slot.id} (part {part_number})", flush=True)
        report = SlotReport(slot_id=slot.id, number=slot.number)
        path = paste_path(workdir, slot)
        if not path.exists():
            report.problems.append("chưa có tệp dán")
            reports.append(report)
            continue

        if part_number in (3, 4, 6, 7):
            reports.extend(
                _check_set(
                    slot,
                    path.read_text(),
                    part_number,
                    blueprint,
                    gateway,
                    tier,
                    ambiguity,
                    seen,
                    workdir,
                )
            )
            continue

        question, problems = parse_one(path.read_text(), part_number)
        # Mô tả ảnh là hiện vật RIÊNG (writer.split_photo), nên chặng kiểm phải
        # đi lấy nó. Không có nó thì mọi phép kiểm ngữ nghĩa của Part 1 đang so
        # bốn câu mô tả với hư không — và chúng đều "đạt".
        context = ""
        if part_number == 1:
            photo = workdir / "photos" / f"{slot.id}.txt"
            if photo.exists():
                context = photo.read_text().strip()
            else:
                # CỜ chứ không chặn: tệp dán vẫn nạp được, mô tả ảnh chỉ phục vụ
                # chặng vẽ. Nhưng nó chặn hai phép kiểm ngữ nghĩa bên dưới —
                # chọn một trong bốn câu mà không biết tấm ảnh có gì thì vẫn trả
                # về một chữ cái, nên phép kiểm sẽ TRÔNG như đang chạy.
                report.flags.append("thiếu mô tả ảnh (`photos/<slot>.txt`) — chưa đối chiếu được")
        report.problems.extend(problems)
        if question is None:
            reports.append(report)
            continue

        report.problems.extend(check_shape(question, part_number))
        report.problems.extend(check_voice_names(question))
        report.flags.extend(check_options(question))

        # Part 1 không in đề bài, nên khoá chống trùng phải lấy từ chính bốn câu
        # nói. Lấy `prompt_text` ở đó là mọi ô cùng khoá rỗng, và phép chống
        # trùng tắt lặng lẽ đúng vào part dễ lặp nhất.
        key = _normalise(question.prompt_text or " ".join(option_text(o) for o in question.options))
        if key and key in seen:
            # Trùng câu trong CÙNG một đề. Mô hình lặp lại chính nó nhiều hơn
            # người ta tưởng, và hai câu giống nhau trong một đề là thứ người học
            # nhận ra ngay còn máy thì không.
            report.problems.append(f"đề bài trùng với {seen[key]}")
        elif key:
            seen[key] = slot.id

        blind = part_number == 1 and not context
        if gateway is not None and not blind:
            # Một lượt gọi hỏng KHÔNG được dừng cả chặng kiểm. Chặng này chạy
            # hàng chục phút trên cả đề, và để một lỗi 503 nhất thời vứt hết kết
            # quả của những ô đã kiểm là cách chắc chắn nhất khiến không ai chạy
            # nó. Ghi thành cờ: ô đó "chưa đối chiếu được" — nhìn thấy được, và
            # chạy lại được.
            try:
                flag = verify_answer(
                    gateway, question, tier, blueprint.seed + slot.number, part_number, context
                )
            except LLMQuotaExhausted:
                # Hạn mức NGÀY không tự hết sau vài giây, nên đi tiếp chỉ sinh ra
                # đúng dòng cờ đó cho mọi ô còn lại — và dòng nói đúng nguyên nhân
                # bị chôn dưới ba mươi dòng giống hệt. Dừng hẳn, giữ lại những ô
                # đã kiểm. Cùng cách xử lý mà `write` đã dùng.
                raise
            except Exception as failure:  # noqa: BLE001
                flag = f"không đối chiếu được đáp án: {failure}"
            if flag:
                report.flags.append(flag)
            if ambiguity:
                try:
                    count, found = count_workable_options(
                        gateway, question, tier, part_number, context
                    )
                except LLMQuotaExhausted:
                    raise
                except Exception as failure:  # noqa: BLE001
                    # `count = 1` để phép kiểm này KHÔNG gắn thêm cờ "nhiều phương
                    # án" từ một con số chưa từng được đo. Cờ nói đúng chuyện đã
                    # xảy ra nằm ngay dưới.
                    count, found = 1, None
                    report.flags.append(f"không đếm được phương án điền được: {failure}")
                report.workable = found
                if count != 1:
                    report.flags.append(
                        f"có {count} phương án điền được ({found or 'không đọc được'}) — "
                        f"một câu chỉ được có đúng một"
                    )

        reports.append(report)
    return reports


# Ngưỡng lệch của phân bố đáp án trên cả đề. Đều tuyệt đối là 25%; cho phép trôi
# tới 40% vì 30 câu là mẫu nhỏ, nhưng quá đó thì không còn là ngẫu nhiên.
ANSWER_SKEW_LIMIT = 0.40


def check_answer_spread(reports_dir: Path, blueprint: Blueprint) -> list[str]:
    """Phân bố đáp án trên TOÀN đề — lỗi ở tầng đề, không tầng câu.

    Đo được trên một lượt chạy thật: 29/30 câu có đáp án là (A), tức người chọn
    bừa A được 97%. Mỗi câu riêng lẻ hoàn toàn hợp lệ, nên không phép kiểm từng
    câu nào thấy được — đây là chỗ duy nhất nó lộ ra.
    """
    from app.content.exam.writer import paste_path

    tally: dict[str, int] = {}
    total = 0
    for part in blueprint.parts:
        for slot in part.slots:
            path = paste_path(reports_dir, slot)
            if not path.exists():
                continue
            text = path.read_text()
            if part.part in (3, 4):
                questions, _, _ = parse_group(text, part.part)
            else:
                one, _ = parse_one(text, part.part)
                questions = [one] if one is not None else []
            for question in questions:
                correct = next((o.label for o in question.options if o.is_correct), None)
                if correct:
                    tally[correct] = tally.get(correct, 0) + 1
                    total += 1

    if total < 8:
        # Mẫu quá nhỏ để nói gì về phân bố. Im lặng ở đây đúng hơn là báo động
        # trên bốn câu đầu tiên của một lượt sinh còn dở.
        return []
    problems = []
    for letter, count in sorted(tally.items()):
        if count / total > ANSWER_SKEW_LIMIT:
            problems.append(
                f"đáp án lệch: ({letter}) chiếm {count}/{total} = {count / total * 100:.0f}% "
                f"— chọn bừa cũng đúng chừng đó. Chạy `balance` trước khi nạp."
            )
    return problems
