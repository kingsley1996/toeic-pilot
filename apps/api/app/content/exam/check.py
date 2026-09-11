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

import hashlib
import json
import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


# Lời giải hay trích HAI mảnh cách xa nhau, nối bằng dấu lược: *"the review is
# finished... below is an overview"*. Đó là cách trích ĐÚNG, và nó chính là dấu
# hiệu của một câu ghép hai chỗ — thứ trục D1 đang cố tăng. So cả chuỗi kể cả
# dấu lược thì không bao giờ khớp; ba cờ giả trên `tp-form-11` đều là dạng này.
_ELLIPSIS = re.compile(r"\.{3,}|…")


def quote_parts(quote: str) -> list[str]:
    """Các mảnh của một trích dẫn, tách ở dấu lược. Bỏ mảnh quá ngắn để so."""
    parts = [part.strip(" .,;:") for part in _ELLIPSIS.split(quote)]
    return [part for part in parts if len(part) >= _QUOTE_MIN_CHARS]


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
            parts = quote_parts(quote) or [quote]
            missing = [part for part in parts if _normalise(part) not in haystack]
            if missing:
                flags.append(f"trích dẫn không có trong ngữ liệu: {missing[0][:48]!r}")
    return flags


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _cached_verify(workdir: Path, name: str, digest: str) -> dict[str, Any] | None:
    """Kết quả đối chiếu lưu MỖI CÂU một xuống `verify/<slot>-<câu>-<loại>.json`.

    Chặng verify là chặng đắt nhất của pipeline — một lượt gọi model cho mỗi
    câu, cả đề hàng trăm lượt. Không lưu thì một lần Ctrl-C hay hết quota giữa
    đường đốt sạch những gì đã trả tiền, và chạy lại bắt đầu từ số không. Hàng
    đợi là một truy vấn trên thư mục: chạy lại chỉ gọi những câu chưa có kết
    quả. Khoá là nội dung khối dán — sửa câu hỏi làm kết quả cũ tự hết hiệu
    lực, cờ xanh cũ không sống sót qua nội dung mới.
    """
    try:
        data = json.loads((workdir / "verify" / f"{name}.json").read_text())
    except (OSError, ValueError):
        return None
    return data if data.get("h") == digest else None


def _store_verify(workdir: Path, name: str, digest: str, payload: dict[str, Any]) -> None:
    path = workdir / "verify" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"h": digest, **payload}))


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
    problems = list(graphic.problems(part))
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

# Part 3/4 NÓI, Part 7 VIẾT — và cụm tin nhắn của Part 7 là chỗ duy nhất dạng
# câu hàm ý sống được ở phần Đọc, nên đề thật viết "what does Mr. X mean when he
# **writes**". Bản chỉ bắt `says` chặn oan 100% câu hàm ý Part 7: hai ô mỗi đề,
# và cả hai trích dẫn hoàn toàn đúng.
_SAYS_RE = re.compile(r'(?:says?|writes?|wrote),?\s*["“]([^"”]+)["”]', re.IGNORECASE)


# Từ chức năng — bỏ ra khi đo độ phủ, vì chúng có mặt ở mọi câu và làm mọi lựa
# chọn trông như đang nhại lời thoại.
_FUNCTION_WORDS = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been am "
    "this that these those it its you he she we they will would can could should "
    "have has had do does did not no yes as if so up out about your our my me him her "
    "there their them what when where who how why which than then also more most just".split()
)

# Dưới ngưỡng này coi như lựa chọn KHÔNG nhắc tới gì trong ngữ liệu.
UNRELATED = 0.2


def _content_words(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in _FUNCTION_WORDS
    ]


def echo(option: str, source: str) -> float:
    """Bao nhiêu phần từ nội dung của một lựa chọn có sẵn trong ngữ liệu."""
    words = _content_words(option)
    if not words:
        return 0.0
    have = set(_content_words(source))
    return sum(1 for w in words if w in have) / len(words)


def check_distractors(question: ParsedQuestion, script: str) -> list[str]:
    """Đáp án nhiễu của Part 3/4 phải NHẠI lời thoại, không được là chuyện lạ.

    Đây là bẫy trung tâm của đề thật, và tài liệu luyện thi mô tả nó thẳng —
    *"distractors copy words from the audio but twist the meaning"*. Người nghe
    được một từ quen rồi chọn đại phải SAI phần lớn số lần.

    Đề tự sinh đang làm ngược. Đo trên 276 câu Part 3/4 của bốn đề đầu:

        đáp án ĐÚNG nhại gần hết lời thoại    58%
        đáp án NHIỄU không nhắc tới gì        37%
        câu có TỪ HAI nhiễu "không nhắc tới"  35%   (17% có cả ba)

    Ở 17% ấy, đáp án đúng là lựa chọn DUY NHẤT chứa từ nào của lời thoại — một
    điểm cho không với người bắt được đúng một từ.

    **Không chặn đáp án đúng nhại lời thoại.** Đề thật có những câu trả lời được
    bằng cách khớp cụm từ; bỏ chúng đi làm đề khó hơn đề thật, sai theo hướng
    ngược lại. Thứ bị chặn là **sàn của đáp án nhiễu**.
    """
    wrong = [option_text(o) for o in question.options if not o.is_correct]
    if len(wrong) < 3 or not script.strip():
        return []
    # Một lựa chọn không có từ nội dung nào ("At 2:30 P.M.") không ĐO được:
    # bẫy giờ trên đề thật là nhầm con số, không phải nhầm từ — nắn nó về phía
    # "nhại lời thoại" là phá đúng cái bẫy nó dựng. Cùng tiền lệ với đáp án số
    # trong `check_retrieval_spread`.
    measurable = [o for o in wrong if _content_words(o)]
    unrelated = sum(1 for o in measurable if echo(o, script) < UNRELATED)
    if unrelated > 1:
        return [
            f"{unrelated}/{len(measurable)} đáp án nhiễu không nhắc tới gì trong lời thoại — "
            "nhiều nhất một, phần còn lại phải nhại lời đã nói rồi bẻ nghĩa"
        ]
    return []


# Hai dạng câu mà đáp án đúng là KHÁI NIỆM BAO TRÙM chứ không phải một lời đã
# nói: hàm ý (theo định nghĩa là thứ người nói không nói ra) và mục đích. Chúng
# không thể có độ phủ cao, nên đếm chúng vào phép cân là phạt cụm vì nó khó.
ABSTRACT_ANSWER = (
    "_IMPLICATION",
    "_TOPIC_OR_PURPOSE",
    # Đáp án của câu nhận diện người nói và câu nơi chốn cũng là một PHẠM TRÙ
    # ("At an airport", "A caller making a reservation"), không phải một lời đã
    # nói — nên độ phủ thấp là tính chất của dạng câu, không phải khuyết điểm.
    # Đo trên `tp-form-11`: 6 trên 7 cờ `thin_paraphrase` rơi vào bốn dạng này.
    "_SPEAKER_IDENTITY",
    "_SPEAKER_OR_LOCATION",
    "_LOCATION",
)


def check_paraphrase_balance(
    questions: list[ParsedQuestion], script: str, codes: list[str] | None = None
) -> list[str]:
    """Trong một cụm, độ trùng chữ không được ĐOÁN ĐƯỢC đáp án — cả hai chiều.

    Đây là nửa còn lại của `check_distractors`, và nó phải là luật của CỤM chứ
    không của từng câu. Đề thật **có** câu khớp cụm từ — cấm sạch là làm đề khó
    hơn đề thật.

    Luật đối xứng, và sự đối xứng ấy là bài học phải trả giá mới có. Bản đầu chỉ
    chặn một phía ("nhiều nhất một câu có đáp án đúng giống lời thoại nhất"), và
    model làm đúng lời — rồi lật hẳn sang phía kia:

        chiến thuật đoán bừa      may rủi   kho cũ   sau luật một phía
        chọn cái GIỐNG nhất          25%      47%          0%
        chọn cái ÍT GIỐNG nhất       25%       3%         67%

    Thiên lệch 47% bị thay bằng thiên lệch 67% ngược chiều — tệ hơn chỗ xuất
    phát. Một cổng chặn một phía không làm tín hiệu biến mất, nó chỉ đổi dấu.
    """
    if not script.strip():
        return []
    # `strict=False`: gọi không kèm `codes` thì đếm mọi câu, đúng hành vi cũ.
    pairs = zip(questions, codes or [""] * len(questions), strict=False)
    judged = [q for q, code in pairs if not code.endswith(ABSTRACT_ANSWER)]
    if len(judged) < 2:
        return []
    highest = lowest = 0
    for question in judged:
        correct = [option_text(o) for o in question.options if o.is_correct]
        wrong = [option_text(o) for o in question.options if not o.is_correct]
        if not correct or not wrong:
            continue
        mine = echo(correct[0], script)
        theirs = [echo(o, script) for o in wrong]
        if mine > max(theirs):
            highest += 1
        if mine < min(theirs):
            lowest += 1
    problems = []
    if highest > 1:
        problems.append(
            f"{highest}/{len(judged)} câu có đáp án đúng GIỐNG lời thoại nhất — nhiều nhất "
            "một; sửa các đáp án sai cho nhại lời thoại hơn"
        )
    if lowest > 1:
        problems.append(
            f"{lowest}/{len(judged)} câu có đáp án đúng ÍT GIỐNG lời thoại nhất — nhiều nhất "
            "một; chọn cái nghe lạ nhất cũng thành một mẹo đoán đúng"
        )
    return problems


def evidence_sentences(option: str, script: str) -> set[int]:
    """Chỉ số những câu của ngữ liệu mà một lựa chọn chạm tới.

    Xấp xỉ theo TỪ CHUNG, không phải phép hiểu — nên nó đọc là "chứng cứ có thể
    nằm ở đâu", không phải "chứng cứ nằm ở đâu". Đủ dùng cho hai việc: xem hai
    câu có cùng dựa vào một chỗ không, và xem đáp án có phải ghép nhiều chỗ không.
    """
    words = set(_content_words(option))
    if not words:
        return set()
    sentences = [s for s in re.split(r"(?<=[.?!])\s+", script) if s.strip()]
    return {i for i, sentence in enumerate(sentences) if words & set(_content_words(sentence))}


def check_leakage(questions: list[ParsedQuestion]) -> list[str]:
    """Không câu nào được gọi tên đáp án của câu khác trong cùng cụm (guide §27–28).

    Đo được trên 30 câu Part 4 vừa sinh: **23%** có một lựa chọn gọi tên đáp án
    của câu bên cạnh. Một trường hợp trùng gần nguyên ví dụ của guide — câu 1 có
    nhiễu "To explain how to use the pool access" trong khi đáp án câu 2 là
    "Personal training, group classes, and pool access". Ai đọc câu 1 trước thì
    đã gặp từ vựng của đáp án câu 2 trước khi nghe.

    Chặn chứ không cảnh báo: đây là tính chất đọc được của bốn dòng chữ, không
    phải phán đoán về độ khó.

    **Chỉ tính những từ RIÊNG của đáp án đúng.** Một từ có mặt cả trong nhiễu
    của câu kia không trỏ vào đâu cả, nên gặp trước nó không biết thêm gì. Đo
    được: `p4-03` bị báo oan vì "eleven fifteen" — cụm ấy nằm ở ba trên bốn lựa
    chọn của câu bên cạnh.
    """
    problems = []
    for i, mine in enumerate(questions):
        for j, other in enumerate(questions):
            if i == j:
                continue
            gold = [option_text(o) for o in other.options if o.is_correct]
            if not gold:
                continue
            decoys = {
                word
                for o in other.options
                if not o.is_correct
                for word in _content_words(option_text(o))
            }
            keys = set(_content_words(gold[0])) - decoys
            for option in mine.options:
                shared = keys & set(_content_words(option_text(option)))
                if len(shared) >= 2:
                    problems.append(
                        f"câu {i + 1} lựa chọn ({option.label}) gọi tên đáp án của câu {j + 1} "
                        f"({', '.join(sorted(shared))}) — đọc câu này là biết trước câu kia"
                    )
                    break
    return problems


def check_redundancy(questions: list[ParsedQuestion], script: str) -> list[str]:
    """Hai câu cùng dựa vào một chỗ của ngữ liệu là MỘT câu in hai lần (guide §27).

    Đề bài khác nhau không cứu được: thứ được đo là cùng một sự kiện, và người
    làm trả lời câu thứ hai bằng đúng thao tác vừa làm cho câu thứ nhất.
    """
    if not script.strip():
        return []
    spots = []
    for question in questions:
        gold = [option_text(o) for o in question.options if o.is_correct]
        spots.append(evidence_sentences(gold[0], script) if gold else set())
    problems = []
    for i in range(len(spots)):
        for j in range(i + 1, len(spots)):
            if spots[i] and spots[i] == spots[j]:
                problems.append(
                    f"câu {i + 1} và câu {j + 1} cùng dựa vào một chỗ của ngữ liệu — "
                    "hỏi hai lần về một sự kiện"
                )
    return problems


# Dưới ngưỡng này, đáp án đúng gần như không dùng chữ nào của ngữ liệu.
THIN_PARAPHRASE = 0.25


def check_retrieval_spread(questions: list[ParsedQuestion], script: str) -> list[str]:
    """CỜ, không chặn: cụm nên có ít nhất một câu phải ghép hai chỗ (guide §10, D1).

    Đo được: 63% câu Part 4 vừa sinh có toàn bộ chứng cứ nằm gọn trong MỘT câu
    của lời thoại, và nhóm "phải ghép từ ba chỗ trở lên" tụt từ 20% (kho cũ)
    xuống 7%. Luật cân bằng độ trùng chữ đã đẩy đáp án về phía cục bộ hơn — cách
    rẻ nhất để thoả nó là giữ chứng cứ một chỗ rồi đổi vài từ bề mặt.

    Là CỜ chứ không phải vấn đề, vì guide §23 xếp "difficulty questionable" vào
    REVIEW chứ không REJECT, và phép đo này là xấp xỉ theo từ chung: một đáp án
    diễn đạt lại giỏi có thể chạm ít câu mà vẫn khó. Chặn nạp bằng một xấp xỉ là
    cách chắc chắn để không ai chạy cổng nữa.
    """
    if not script.strip() or len(questions) < 2:
        return []
    spans = []
    for question in questions:
        gold = [option_text(o) for o in question.options if o.is_correct]
        spans.append(len(evidence_sentences(gold[0], script)) if gold else 0)
    # Một câu KHÔNG ĐO ĐƯỢC làm cả lời phàn nàn mất căn cứ.
    #
    # Lời phàn nàn là "KHÔNG câu nào trong cụm phải ghép hai chỗ", và muốn khẳng
    # định điều đó thì phải đo được mọi câu. Hai dạng câu hợp lệ luôn cho span 0:
    # đáp án là một CON SỐ tính ra (`_content_words` chỉ bắt `[a-z]+`, nên
    # "¥18,700" tách ra rỗng), và câu NOT/EXCEPT, nơi đáp án đúng theo định nghĩa
    # KHÔNG có trong ngữ liệu. Đo trên `p7-01`: câu 3 đúng là câu ghép mà prompt
    # yêu cầu — giá Advanced ở một chỗ, ưu đãi 15% ở chỗ khác — và cổng vẫn chặn
    # cả cụm vì không nhìn thấy nó.
    if 0 in spans:
        return []
    if max(spans, default=0) < 2:
        return [
            "cả cụm chỉ hỏi những gì nằm gọn trong một câu — nên có một câu buộc "
            "ghép hai chỗ tách rời"
        ]
    return []


def check_thin_paraphrase(question: ParsedQuestion, script: str, code: str = "") -> list[str]:
    """CỜ: đáp án đúng gần như không dùng chữ nào của ngữ liệu (guide §26, Failure 5).

    Mặt còn lại của `check_paraphrase_balance`. Diễn đạt lại là điều được khuyến
    khích, nhưng một diễn đạt không ai nói là lỗi riêng của nó: guide lấy ví dụ
    "Transmit a lexical token through a mobile communication service" cho
    *"Text the word OPEN"*.

    Cờ chứ không chặn, vì độ phủ thấp KHÔNG chứng minh câu đó không tự nhiên —
    nó chỉ nói đáp án dùng chữ khác. Người duyệt đọc một dòng là biết.
    """
    if not script.strip() or code.endswith(ABSTRACT_ANSWER):
        return []
    gold = [option_text(o) for o in question.options if o.is_correct]
    if not gold or not _content_words(gold[0]):
        return []
    if echo(gold[0], script) < THIN_PARAPHRASE:
        return [f"đáp án đúng gần như không dùng chữ nào của ngữ liệu: {gold[0][:48]!r}"]
    return []


def passage_blocks(block: str) -> list[str]:
    """Từng khối `[PASSAGE]` của một cụm, theo thứ tự, chưa chuẩn hoá.

    `parse_group` nối chúng lại thành một chuỗi, mà câu hỏi ở đây là trích dẫn
    nằm ở tài liệu NÀO — nên biên giới giữa các khối phải còn.
    """
    from app.content.exam.prompts.contract import PASSAGE_MARKER

    out: list[list[str]] = []
    current: list[str] | None = None
    for line in block.splitlines():
        stripped = line.strip()
        if stripped == PASSAGE_MARKER:
            current = []
            out.append(current)
        elif stripped.startswith("[") and stripped.endswith("]"):
            current = None
        elif current is not None:
            current.append(line)
    return ["\n".join(lines).strip() for lines in out]


def check_cross_passage(questions: list[ParsedQuestion], block: str) -> list[str]:
    """Cụm NHIỀU tài liệu phải có một câu vắt qua hai tài liệu (guide §9.4–9.5).

    Đây là toàn bộ lý do cụm nhiều ngữ liệu tồn tại. Không có câu bắc cầu thì ba
    tài liệu chỉ là ba cụm một tài liệu in cạnh nhau.

    **Đo bằng TRÍCH DẪN, không bằng từ chung**, và đó là điểm khác `check_retrieval_spread`.
    Trích dẫn trong lời giải là nguyên văn theo hợp đồng — `check_explanation` đã
    cưỡng chế điều đó — còn biên giới các khối thì biết chính xác, nên câu hỏi
    "đoạn này nằm ở tài liệu nào" là phép tra bảng chứ không phải ước lượng. Phép
    đếm từ chung mù với ba thứ Part 7 đầy rẫy: đáp án là con số tính ra, câu
    NOT/EXCEPT, và suy luận. Đo được: nó im ở **69%** cụm Part 7.

    Cái giá là nó đặt một yêu cầu lên LỜI GIẢI, không chỉ quan sát câu hỏi — một
    câu thật sự bắc cầu mà lời giải chỉ dẫn một bên sẽ bị bắt. Chấp nhận được, vì
    người học cần thấy cả hai vế mới hiểu vì sao đáp án đúng; nhưng vì thế
    `prompt_for_part7` phải nói ra luật này, nếu không cổng lại chặt hơn prompt.
    """
    docs = [_normalise(doc) for doc in passage_blocks(block) if doc.strip()]
    if len(docs) < 2:
        return []
    for question in questions:
        touched: set[int] = set()
        for quote in _QUOTED.findall(question.explanation or ""):
            if len(quote) < _QUOTE_MIN_CHARS:
                continue
            for part in quote_parts(quote) or [quote]:
                needle = _normalise(part)
                touched.update(i for i, doc in enumerate(docs) if needle and needle in doc)
        if len(touched) >= 2:
            return []
    return [
        f"cụm {len(docs)} tài liệu nhưng không lời giải nào dẫn chứng từ hai tài liệu "
        "khác nhau — không có câu nào bắc cầu thì đây là mấy cụm một tài liệu in cạnh nhau"
    ]


def _filled_passage(passage: str, questions: list[ParsedQuestion]) -> str:
    """Ngữ liệu Part 6 với mỗi chỗ trống thay bằng đáp án đúng của nó."""
    out = passage
    for index, question in enumerate(questions, start=1):
        gold = next((option_text(o) for o in question.options if o.is_correct), None)
        if gold:
            out = out.replace(f"{BLANK} ({index})", gold)
    return out


def check_implication(question: ParsedQuestion, script: str, kind: int = 0) -> list[str]:
    """Câu hàm ý phải đúng khuôn của BIẾN THỂ mà blueprint giao (`implication_kind`).

    Đây là dạng câu khó nhất của Part 3/4 và cũng là dạng dễ trượt về dạng dễ
    nhất: bỏ lời trích đi thì còn lại một câu hỏi chi tiết hoàn toàn hợp lệ, và
    không có gì trong đầu ra nói cho ta biết ô này đã không viết đúng thứ được
    giao.

    `difficulty.py` dạy bốn biến thể và rotation cố ý chia chúng đều, nên cổng
    không được ép tất cả về form 1. Chỉ form 0 mới có lời trích để kiểm tất định.

    - kind 0 (quote-a-line): stem phải trích `"..."` sau says/writes, và lời
      trích phải CÓ THẬT trong lời thoại.
    - kind 1 (suy từ hai chi tiết rời): đáp án đúng phải chạm ÍT NHẤT HAI câu
      của lời thoại — đó chính là định nghĩa của biến thể. Đáp án không có từ
      nội dung nào (con số, tên riêng) thì không đo được, bỏ qua.
    - kind 2, 3 (hệ quả kế hoạch đổi / mục đích chi tiết): không có dấu vết tất
      định nào trong đầu ra phân biệt chúng với câu chi tiết — chỉ prompt và
      `--verify` giữ được chúng.
    """
    if kind == 1:
        gold = [option_text(o) for o in question.options if o.is_correct]
        if gold:
            spans = evidence_sentences(gold[0], script)
            if spans and len(spans) < 2:
                return [
                    "câu hàm ý 'suy từ hai chi tiết rời' phải dựa trên ít nhất "
                    "hai câu tách rời của lời thoại"
                ]
        return []
    if kind > 1:
        return []
    quoted = _SAYS_RE.search(question.prompt_text or "")
    if quoted is None:
        return ["câu hàm ý không trích lời nào — phải hỏi về một câu người nói đã nói"]
    said = quoted.group(1).strip()
    # Chuẩn hoá CẢ HAI vế: `_normalise` bỏ dấu câu, nên so một vế thô với một vế
    # đã chuẩn hoá thì mọi lời trích có dấu phẩy hay dấu nháy đều báo là bịa.
    if _normalise(said) not in _normalise(script):
        return [f"lời trích {said[:40]!r} không có trong lời thoại"]
    return []


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
    # Cờ của CẢ CỤM, nhân ra mọi báo cáo giống như `shared` — cùng lý do: đơn vị
    # đọc là từng câu, còn thứ sai là quan hệ giữa ba câu.
    shared_flags: list[str] = []
    # Ngữ liệu để đối chiếu trích dẫn: CHÍNH khối dán, trừ các dòng giải thích.
    # Dùng cả khối thay vì ghép script + passage vì `parse_group` không trả ngữ
    # liệu ra ngoài, và cả khối lại đúng hơn — nó phủ mọi part, kể cả Part 2 nơi
    # bằng chứng nằm trong ba câu đáp. Phải trừ dòng `Explanation:` đi, nếu
    # không một trích dẫn bịa sẽ khớp với chính nó và cổng thành vô dụng.
    evidence = "\n".join(
        line for line in block.splitlines() if not line.strip().lower().startswith("explanation:")
    )
    if part == 6:
        # Ngữ liệu Part 6 MANG chỗ trống trong chính nó, nên lời giải trích câu
        # "đã điền" không bao giờ khớp — mà đoạn ấy bắt buộc phải có, không cho
        # người học thấy kết quả điền thì lời giải không giải thích gì. Ghép thêm
        # bản đã điền vào ngữ liệu đối chiếu; cùng cách hình được ghép vào dưới.
        evidence = f"{evidence}\n\n{_filled_passage(script, questions)}"
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
            digest = _digest(block + source.read_text())
            hit = _cached_verify(workdir, f"{slot.id}-graphic", digest)
            if hit is not None:
                verdict, complaint = hit["verdict"], hit["complaint"]
            else:
                try:
                    verdict, complaint = graphic_rule_verdict(gateway, asked, script, source, tier)
                except LLMQuotaExhausted:
                    raise
                except Exception as failure:  # noqa: BLE001
                    verdict, complaint = "", None
                    graphic_flags = [*graphic_flags, f"không xét được luật hình: {failure}"]
                else:
                    _store_verify(
                        workdir,
                        f"{slot.id}-graphic",
                        digest,
                        {"verdict": verdict, "complaint": complaint},
                    )
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
    if part in (3, 4):
        from app.content.exam.blueprint import GRAPHIC_POSITION

        # Luật của CỤM, nên nó vào `shared` — mỗi câu riêng lẻ hoàn toàn hợp lệ,
        # thứ sai là ba câu cùng trả lời được bằng cách khớp chữ.
        #
        # Bỏ câu hỏi về HÌNH ra: lựa chọn của nó là tên hàng trong bảng và lời
        # thoại cố ý không đọc tên ấy, nên nó không bao giờ là "khớp chữ".
        graphic_at = GRAPHIC_POSITION.get(part, len(questions) - 1)
        keep = [i for i in range(len(questions)) if not (slot.graphic and i == graphic_at)]
        judged = [questions[i] for i in keep]
        kinds = [slot.question_types[i] if i < len(slot.question_types) else "" for i in keep]
        shared = [*shared, *check_paraphrase_balance(judged, script, kinds)]
        shared = [*shared, *check_redundancy(judged, script)]
    if part in (3, 4, 7):
        # CHẶN ở ô blueprint đã đánh dấu `hard`, CỜ ở ô không. Cùng một phép đo,
        # hai mức — vì ô cũ không mang cột ấy (mặc định 0) nên đề đã sinh giữ
        # nguyên hành vi, còn ô dựng sau khi có cột thì phải đạt.
        #
        # `judged` chứ không phải `questions`: câu hỏi về HÌNH được miễn ở đây y
        # như ở `check_paraphrase_balance` và `check_distractors`. Ở ô có hình,
        # `script` đã được ghép thêm bảng, nên đáp án của nó (một tên hàng) tìm
        # thấy trong phần bảng và span thành 1 — cổng bèn đếm nó rồi kết luận
        # "không câu nào ghép hai chỗ", trong khi chính câu ấy là câu ghép HAI
        # NGUỒN: thoại cấp toạ độ, hình tra ra đáp án. Đo trên `p3-13`.
        # Cụm có HÌNH được miễn hẳn: câu hỏi về hình CHÍNH LÀ câu ghép hai
        # nguồn — thoại cấp một toạ độ ngoài trục đáp án, hình tra toạ độ ấy ra
        # đáp án — và phép đếm câu văn không nhìn thấy điều đó. Bỏ nó ra rồi đòi
        # một câu ghép nữa trong hai câu còn lại là bắt cụm ba câu mang HAI câu
        # khó, thứ đề thật không làm. Đo trên `p3-13`.
        spread = [] if slot.graphic else check_retrieval_spread(questions, script)
        if part == 7:
            spread = [*spread, *check_cross_passage(questions, block)]
        if slot.hard:
            shared = [*shared, *spread]
        else:
            shared_flags = [*shared_flags, *spread]
        # Rò rỉ chéo áp cho MỌI cụm, kể cả Part 7 — guide §27 nói về cụm câu
        # hỏi, không về phương thức nghe hay đọc.
        shared = [*shared, *check_leakage(questions)]
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
        report.flags.extend(shared_flags)
        report.problems.extend(check_shape(question, part))
        report.problems.extend(check_voice_names(question))
        # Câu hỏi về HÌNH được miễn phép so độ dài: bốn lựa chọn của nó BẮT
        # BUỘC đúng bằng nhãn trục đáp án của bảng (`check_graphic` cưỡng chế),
        # nên độ dài do tấm hình quyết định chứ không phải người viết. Đo trên
        # `p3-13`: "Social Media" (12) cạnh "Email" (5) bị gắn cờ, mà rút ngắn
        # nó là làm bốn lựa chọn thôi khớp trục và cụm rớt một cổng khác.
        from app.content.exam.blueprint import GRAPHIC_POSITION as _AT

        if not (slot.graphic and index == _AT.get(part, len(questions) - 1)):
            report.flags.extend(check_options(question))
        # Ngữ liệu để đối chiếu trích dẫn KHÁC nhau theo part: Part 3/4 là lời
        # thoại, Part 6/7 là đoạn văn, Part 2 là chính ba câu đáp (đề không in
        # gì nên lời giải thích phải thuật lại chúng). Part 1 và 5 không có ngữ
        # liệu chữ — cổng trích dẫn tự tắt ở đó thay vì báo bừa.
        report.flags.extend(check_explanation(question, evidence))
        from app.content.exam.blueprint import GRAPHIC_POSITION

        if index == GRAPHIC_POSITION.get(part, len(questions) - 1):
            report.flags.extend(graphic_flags)
        if index < len(slot.question_types) and slot.question_types[index].endswith("_IMPLICATION"):
            report.problems.extend(check_implication(question, script, slot.implication_kind))
        # Câu hỏi về HÌNH được miễn, và không phải vì tiện: lựa chọn của nó là
        # tên hàng trong bảng, còn lời thoại CỐ Ý không đọc tên ấy ra — đó là
        # toàn bộ cơ chế của dạng câu này (xem `graphic_rule_verdict`). Bắt nó
        # nhại lời thoại là bắt nó thôi làm câu hỏi về hình.
        graphic_index = GRAPHIC_POSITION.get(part, len(questions) - 1)
        if part in (3, 4) and not (slot.graphic and index == graphic_index):
            report.problems.extend(check_distractors(question, script))
            kind = slot.question_types[index] if index < len(slot.question_types) else ""
            report.flags.extend(check_thin_paraphrase(question, script, kind))

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
            digest = _digest(block)
            hit = _cached_verify(workdir, f"{slot.id}-{index + 1}-answer", digest)
            if hit is not None:
                flag = hit["flag"]
            else:
                try:
                    flag = verify_answer(
                        gateway, question, tier, blueprint.seed + report.number, part, script
                    )
                except LLMQuotaExhausted:
                    raise
                except Exception as failure:  # noqa: BLE001
                    flag = f"không đối chiếu được đáp án: {failure}"
                else:
                    _store_verify(workdir, f"{slot.id}-{index + 1}-answer", digest, {"flag": flag})
            if flag:
                report.flags.append(flag)
            if ambiguity:
                hit = _cached_verify(workdir, f"{slot.id}-{index + 1}-workable", digest)
                if hit is not None:
                    count, found = hit["count"], hit["found"]
                    report.workable = found
                    if count != 1:
                        report.flags.append(
                            f"có {count} phương án điền được ({found or 'không đọc được'}) — "
                            f"một câu chỉ được có đúng một"
                        )
                else:
                    try:
                        count, found = count_workable_options(gateway, question, tier, part, script)
                    except LLMQuotaExhausted:
                        raise
                    except Exception as failure:  # noqa: BLE001
                        count, found = 1, None
                        report.flags.append(f"không đếm được phương án điền được: {failure}")
                    else:
                        _store_verify(
                            workdir,
                            f"{slot.id}-{index + 1}-workable",
                            digest,
                            {"count": count, "found": found},
                        )
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

        block = path.read_text()
        question, problems = parse_one(block, part_number)
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
            digest = _digest(block)
            hit = _cached_verify(workdir, f"{slot.id}-answer", digest)
            if hit is not None:
                flag = hit["flag"]
            else:
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
                else:
                    _store_verify(workdir, f"{slot.id}-answer", digest, {"flag": flag})
            if flag:
                report.flags.append(flag)
            if ambiguity:
                hit = _cached_verify(workdir, f"{slot.id}-workable", digest)
                if hit is not None:
                    count, found = hit["count"], hit["found"]
                else:
                    try:
                        count, found = count_workable_options(
                            gateway, question, tier, part_number, context
                        )
                    except LLMQuotaExhausted:
                        raise
                    except Exception as failure:  # noqa: BLE001
                        # `count = 1` để phép kiểm này KHÔNG gắn thêm cờ "nhiều
                        # phương án" từ một con số chưa từng được đo. Cờ nói đúng
                        # chuyện đã xảy ra nằm ngay dưới.
                        count, found = 1, None
                        report.flags.append(f"không đếm được phương án điền được: {failure}")
                    else:
                        _store_verify(
                            workdir,
                            f"{slot.id}-workable",
                            digest,
                            {"count": count, "found": found},
                        )
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


# Nhiễu mở đầu bằng Yes/No cho một câu hỏi WH là bẫy THẬT của đề thật — nhưng ở
# tần suất cao nó thôi là bẫy và thành một luật, mà luật nào cũng là một lần
# loại trừ miễn phí. Đo trên `tp-form-11`: 11/15 câu WH (73%) dùng nó, nên người
# làm chỉ còn chọn giữa hai phương án và cái gián tiếp không bao giờ được kiểm.
#
# **Con số 0.3 KHÔNG tra từ đề thật** — nó là một trần đặt tay để chặn thiên
# lệch, không phải một tỉ lệ đo được. Và mẫu chỉ có 15 câu WH, nên mỗi câu là
# 6,7 điểm phần trăm: trần 0.25 thực chất là "nhiều nhất 3 câu", còn 0.3 là
# "nhiều nhất 4". Sinh lại để cạo một ô cuối cùng đã thất bại BỐN lượt liên tiếp
# trên `p2-15` — mô hình chọn lại đúng nhiễu ấy mỗi lần — nên trần được nới cho
# khớp với thứ mẫu này phân giải được, thay vì đuổi theo hai điểm phần trăm.
YES_NO_DECOY_LIMIT = 0.3
_YES_NO_OPENER = re.compile(r"^(yes|no|sure|of course)\b[,.]?", re.IGNORECASE)
# Dạng câu Part 2 mà một lời đáp Yes/No là SAI theo định nghĩa.
_WH_CODES = ("_WHO_", "_WHERE_", "_WHEN_", "_WHY_", "_HOW_", "_WHAT_", "_STATEMENT")


def check_yes_no_spread(reports_dir: Path, blueprint: Blueprint) -> list[str]:
    """Bao nhiêu câu WH của Part 2 có nhiễu loại được ngay từ chữ đầu tiên.

    Lỗi ở tầng ĐỀ, không tầng câu — y như phân bố đáp án. Một câu WH có nhiễu mở
    đầu bằng "Yes" hoàn toàn hợp lệ và là bẫy đúng của đề thật; ba trên bốn câu
    như thế thì người làm học được một luật thay vì nghe.
    """
    from app.content.exam.writer import paste_path

    total = 0
    using: list[str] = []
    for part in blueprint.parts:
        if part.part != 2:
            continue
        for slot in part.slots:
            if not any(code in slot.question_type for code in _WH_CODES):
                continue
            path = paste_path(reports_dir, slot)
            if not path.exists():
                continue
            question, _ = parse_one(path.read_text(), 2)
            if question is None:
                continue
            total += 1
            wrong = [o for o in question.options if not o.is_correct]
            if any(_YES_NO_OPENER.match((o.spoken_text or option_text(o)).strip()) for o in wrong):
                using.append(slot.id)

    if total < 8 or len(using) / total <= YES_NO_DECOY_LIMIT:
        return []
    # Giữ lại phần trong hạn ngạch, gọi tên phần VƯỢT. Bẫy này hợp lệ, nên xoá
    # sạch là sai — thứ phải xoá là số dôi ra. Cắt theo thứ tự id để hai lần chạy
    # trên cùng nội dung chỉ đúng một tập ô, nếu không `prune` sẽ đuổi theo một
    # đích di động.
    keep = int(total * YES_NO_DECOY_LIMIT)
    over = sorted(using)[keep:]
    return [
        f"nhiễu Yes/No cho câu WH: {len(using)}/{total} = {len(using) / total * 100:.0f}% "
        f"— quá {YES_NO_DECOY_LIMIT * 100:.0f}% thì nó thôi là bẫy và thành một luật, "
        f"loại được từ chữ đầu tiên mà không cần nghe hết câu. Sinh lại {len(over)} ô "
        f"dôi ra: {' '.join(over)}"
    ]


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
