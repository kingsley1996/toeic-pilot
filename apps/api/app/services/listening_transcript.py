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
