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
_SENTENCE_END = re.compile(r"[.!?…][\"'”’)>\]}♪♫\s]*$")


def _ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.strip()))


def _first_word_char(text: str) -> str:
    for char in text:
        if char.isalnum():
            return char
    return ""


def _is_fragment(text: str, duration: Decimal) -> bool:
    stripped = text.strip()
    return bool(stripped) and duration < MIN_FRAGMENT_SECONDS and not _ends_sentence(stripped)


def _continues(prev: ParsedSegment, current: ParsedSegment) -> bool:
    """Câu sau có phải đoạn nối của câu trước? Hai dấu hiệu, cái nào cũng đủ:
    (1) câu trước là mảnh vỡ; (2) câu sau mở bằng chữ thường trong khi câu
    trước chưa kết thúc ("...real c" + "in easy English...") — captioner ngắt
    giữa chừng. Cả hai đều chặn độ dài để không dính cả đoạn văn thành một."""
    if _is_fragment(prev.text, prev.end - prev.start):
        return True
    first = _first_word_char(current.text)
    return (
        bool(first)
        and first.islower()
        and not _ends_sentence(prev.text)
        and current.end - prev.start < MAX_MERGED_SECONDS
    )


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
