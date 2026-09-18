"""Parse + validate transcript paste (SRT/VTT) cho Listening Lab.

Một parser cho cả hai định dạng: VTT là SRT đội thêm dòng `WEBVTT` và dùng dấu
chấm cho mili giây — chuẩn hoá hai điểm đó xong thì phần còn lại chung một
đường. Không nhận format tự chế (`mm:ss text`...): timestamp thiếu giờ kết thúc
thì replay segment không biết dừng ở đâu, và đoán giờ kết thúc bằng "câu sau bắt
đầu" là đoán — SPEC §8 cấm tạo exercise từ transcript đoán.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

# `00:01:02,500 --> 00:01:05,000` (SRT) hay `00:01:02.500 --> 00:01:05,000`
# (VTT); giờ có thể vắng (`01:02.500`). Phần setting sau timestamp VTT
# (`align:start position:0%`) bỏ qua — nghe-chép không cần vị trí chữ trên hình.
_TIMESTAMP = re.compile(
    r"(?:(\d+):)?([0-5]?\d):([0-5]\d)[,.](\d{3})\s*-->\s*"
    r"(?:(\d+):)?([0-5]?\d):([0-5]\d)[,.](\d{3})"
)
_CUE_NUMBER = re.compile(r"^\d+$")
_TAG = re.compile(r"<[^>]*>")
_WS = re.compile(r"\s+")
# Nhóm ngoặc `[...]`/`(...)` — phụ đề thật ghi tiếng động trong đó.
_BRACKETED = re.compile(r"[\(\[][^\n\)\]]*[\)\]]")
# Nốt nhạc lẻ (♪, ♫).
_NOTES = re.compile(r"[♪♫]+")
# Nốt nhạc đứng lẻ (♪, ♫): lyric giữ lại chữ, còn trơ mỗi nốt thì không lời.
_NOTES = re.compile(r"[♪♫]+")
# Tên tiếng động quen thuộc (so khớp từng từ, chữ thường). Nguyên tắc: THÀ GIỮ
# NHẦM còn hơn bỏ sót — "[man laughing]" giữ (có thể là lời dẫn), chỉ bỏ khi
# MỌI từ trong ngoặc đều là tiếng động ("[music playing]") hoặc ngoặc không có
# chữ nào ("[♪♪♪]").
_SOUND_WORDS = frozenset(
    {
        "music",
        "playing",
        "applause",
        "laughter",
        "cheering",
        "cheers",
        "coughing",
        "silence",
        "silent",
        "inaudible",
        "unintelligible",
        "mumbling",
        "sighing",
        "noise",
    }
)


@dataclass(frozen=True)
class ParsedSegment:
    start: Decimal
    end: Decimal
    text: str


@dataclass(frozen=True)
class TranscriptValidation:
    """Đúng hình SPEC §8: `valid` + `errors` + `warnings`.

    Overlap chỉ là warning: sub thật ngoài đời chồng nhau vẫn nghe-chép được
    từng câu, chặn là bắt user sửa một thứ không hỏng.
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _to_seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> Decimal:
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    return Decimal(total) + Decimal(int(millis)) / 1000


def parse_srt_vtt(raw: str) -> list[ParsedSegment]:
    """Bóc transcript paste thành segments. Không ném: input hỏng thì trả list
    rỗng và để `validate_transcript` báo EMPTY — một đường báo lỗi duy nhất."""
    lines = (raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[ParsedSegment] = []
    stamp: re.Match[str] | None = None
    words: list[str] = []

    def flush() -> None:
        if stamp is None:
            return
        text = _WS.sub(" ", _TAG.sub("", " ".join(words)).replace("&nbsp;", " ")).strip()
        if text:
            first, second = stamp.groups()[0:4], stamp.groups()[4:8]
            segments.append(
                ParsedSegment(
                    start=_to_seconds(*first),
                    end=_to_seconds(*second),
                    text=text,
                )
            )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            stamp, words = None, []
            continue
        if stamp is None:
            if stripped == "WEBVTT" or stripped.startswith("NOTE"):
                continue
            match = _TIMESTAMP.search(stripped)
            if match:
                stamp = match
            # Dòng số thứ tự cue và header mở rộng: bỏ qua im lặng.
            continue
        words.append(stripped)

    flush()
    return segments


def validate_transcript(
    segments: list[ParsedSegment],
    duration_seconds: Decimal | None = None,
) -> TranscriptValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if not segments:
        return TranscriptValidation(valid=False, errors=["Transcript is empty"])

    for index, seg in enumerate(segments, start=1):
        if not seg.text.strip():
            errors.append(f"Segment {index} has empty text")
        if seg.start < 0:
            errors.append(f"Segment {index} has negative start")
        if seg.end <= seg.start:
            errors.append(f"Segment {index} has end <= start")

    for index in range(2, len(segments) + 1):
        prev, current = segments[index - 2], segments[index - 1]
        if current.start < prev.start:
            errors.append(f"Segment {index} starts before segment {index - 1}")
        elif current.start < prev.end:
            warnings.append(f"Segment {index} overlaps segment {index - 1}")

    if duration_seconds is not None:
        for index, seg in enumerate(segments, start=1):
            if seg.end > duration_seconds:
                errors.append(f"Segment {index} ends after the video duration")

    return TranscriptValidation(valid=not errors, errors=errors, warnings=warnings)


def _is_sound_bracket(content: str) -> bool:
    """Nội dung trong `[...]`/`(...)` có phải tiếng động không lời? Chỉ đúng khi
    KHÔNG CÓ chữ nào ngoài danh sách (`[♪♪♪]`, `[Music]`, `[music playing]`);
    `[man laughing]` là False có chủ ý — thà giữ nhầm một dòng còn hơn bỏ sót
    một câu thoại."""
    words = re.findall(r"[A-Za-z]+", content.lower())
    if not words:
        return True
    return all(word in _SOUND_WORDS for word in words)


def is_speakable(text: str) -> bool:
    """Dòng này có lời để chép không? Bóc nốt nhạc + nhóm ngoặc tiếng động rồi
    còn chữ/số nào không. Lyric giữ nguyên (`♪ ... ♪` còn chữ là còn giữ) —
    chỉ loại dòng trơ nhạc/nền mà thành bài dictation thì vô nghĩa."""
    cleaned = _NOTES.sub(" ", _TAG.sub(" ", text or ""))
    cleaned = _BRACKETED.sub(
        lambda match: " " if _is_sound_bracket(match.group(0)[1:-1]) else match.group(0),
        cleaned,
    )
    return any(char.isalnum() for char in cleaned)


# Phụ đề tự động ngắt câu theo nhịp thở chứ không theo ngữ nghĩa ("Today we're
# going" / "to discuss the new" / "schedule.") — cue nào KHÔNG kết thúc bằng
# dấu câu mà ngắn hơn ngưỡng này thì coi là mảnh vỡ, ghép vào câu sau. Dài hơn
# thì giữ nguyên kể cả thiếu dấu câu (blob ASR 20s mà ghép tiếp chỉ tệ hơn).
MIN_FRAGMENT_SECONDS = Decimal("3")
# Câu ghép dài tối đa: dictation đo từng câu, quá dài là bài đọc chứ không phải
# bài nghe — chặn để hai câu dài thiếu dấu câu không dính thành một.
MAX_MERGED_SECONDS = Decimal("12")
# Câu sau ngắn chừng này mà câu trước chưa kết thúc thì gần như chắc là mảnh
# còn lại của cùng một câu ("Step by Step.", "Clothing Store.").
MAX_SHORT_NEXT_WORDS = 3
_SENTENCE_END = re.compile(r"[.!?…][\"'”’)>\]}♪♫\s]*$")

# Từ mà đứng cuối câu thì câu CHƯA XONG: mạo từ, giới từ, liên từ, trợ động từ,
# đại từ, từ hỏi, lượng từ ("how to" + "Let's go", "tell me" + "about it").
# Cố ý thiếu những từ hai mặt ("there", "so", "no", "more" — "See you there"
# hoàn chỉnh nhưng "I need some" thì dở): thà sót một mảnh còn hơn dính hai câu
# trọn thành một. Riêng "there/here is|are" thì luôn dở ("there is" + "a pen").
_DANGLING_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "about",
        "into",
        "over",
        "after",
        "at",
        "by",
        "from",
        "than",
        "as",
        "like",
        "up",
        "out",
        "off",
        "down",
        "away",
        "back",
        "and",
        "or",
        "but",
        "that",
        "if",
        "because",
        "although",
        "while",
        "when",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "am",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "can",
        "could",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "us",
        "them",
        "my",
        "your",
        "his",
        "her",
        "our",
        "their",
        "its",
        "this",
        "these",
        "those",
        "some",
        "any",
        "just",
        "very",
    }
)
_DANGLING_BIGRAMS = frozenset(
    {
        ("there", "is"),
        ("there", "are"),
        ("there", "was"),
        ("there", "were"),
        ("here", "is"),
        ("here", "are"),
    }
)


def _ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.strip()))


def count_complete(segments: list[ParsedSegment]) -> tuple[int, int]:
    """(số câu trọn, tổng số câu). Câu trọn = hết bằng dấu câu, hoặc ngắn dưới
    6 giây (lyric một dòng, interjection — ngắn thì nghe-chép được nguyên câu
    dù không có dấu câu). Seed script dùng tỉ lệ này làm cổng chất lượng."""
    complete = sum(1 for seg in segments if _ends_sentence(seg.text) or (seg.end - seg.start) < 6)
    return complete, len(segments)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def _is_dangling(text: str) -> bool:
    """Câu kết thúc bằng từ treo (chưa thể hết ý): "how to", "tell me", "there
    is". Từ hai mặt ("there", "so") không có trong danh sách — thà sót mảnh còn
    hơn dính hai câu trọn (xem chú thích ở `_DANGLING_WORDS`)."""
    words = _words(text)
    if not words:
        return False
    if words[-1] in _DANGLING_WORDS:
        return True
    return len(words) >= 2 and (words[-2], words[-1]) in _DANGLING_BIGRAMS


def _first_word_char(text: str) -> str:
    for char in text:
        if char.isalnum():
            return char
    return ""


def _is_fragment(text: str, duration: Decimal) -> bool:
    stripped = text.strip()
    return bool(stripped) and duration < MIN_FRAGMENT_SECONDS and not _ends_sentence(stripped)


def _continues(prev: ParsedSegment, current: ParsedSegment) -> bool:
    """Câu sau có phải đoạn nối của câu trước? Ba dấu hiệu, cái nào cũng đủ —
    nhưng TẤT CẢ đều đòi câu trước chưa kết thúc bằng dấu câu (dấu câu là rào
    cứng: "I'm Georgie." + "And I'm Beth." không bao giờ dính):
    (1) câu trước là mảnh vỡ ngắn; (2) câu sau mở bằng chữ thường (captioner
    ngắt giữa chừng); (3) câu trước kết thúc bằng từ treo ("how to"); (4) câu
    sau ngắn cũn (<=3 từ, kiểu "Step by Step.", "Clothing Store."). (3)(4) thêm
    sau khi thấy ASR viết hoa mọi đầu cue — trường hợp (2) không bắt được."""
    if current.end - prev.start >= MAX_MERGED_SECONDS:
        return False
    if _ends_sentence(prev.text):
        return False
    if _is_fragment(prev.text, prev.end - prev.start):
        return True
    first = _first_word_char(current.text)
    if first and first.islower():
        return True
    if _is_dangling(prev.text):
        return True
    return len(_words(current.text)) <= MAX_SHORT_NEXT_WORDS


def merge_fragments(segments: list[ParsedSegment]) -> list[ParsedSegment]:
    """Ghép mảnh vỡ vào câu sau (câu cuối vỡ thì ghép ngược vào câu trước).
    Thứ tự + mốc giữ nguyên ý nghĩa (start=min, end=max) nên transcript đã
    valid thì merge xong vẫn valid — validate lại chỉ để lấy warnings đúng số
    thứ tự mới."""
    if not segments:
        return []
    merged: list[ParsedSegment] = []
    for seg in segments:
        if merged and _continues(merged[-1], seg):
            prev = merged.pop()
            merged.append(
                ParsedSegment(start=prev.start, end=seg.end, text=f"{prev.text} {seg.text}")
            )
        else:
            merged.append(seg)
    if len(merged) > 1:
        last_duration = merged[-1].end - merged[-1].start
        if _is_fragment(merged[-1].text, last_duration):
            last = merged.pop()
            prev = merged.pop()
            merged.append(
                ParsedSegment(start=prev.start, end=last.end, text=f"{prev.text} {last.text}")
            )
    return merged


def _stamp(value: Decimal) -> str:
    ms = int((value * 1000).to_integral_value())
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def segments_to_vtt(segments: list[ParsedSegment]) -> str:
    """Xuất lại VTT để user sửa trên form trước khi tạo bài."""
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{_stamp(seg.start)} --> {_stamp(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)
