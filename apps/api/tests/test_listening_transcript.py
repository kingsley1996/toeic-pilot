"""parse + validate transcript paste: SRT/VTT vào, lỗi báo đúng chỗ."""

from decimal import Decimal

import pytest

from app.services.listening_transcript import (
    ParsedSegment,
    is_speakable,
    merge_fragments,
    parse_srt_vtt,
    validate_transcript,
)

_SRT = """1
00:00:12,420 --> 00:00:15,180
Hello everyone.

2
00:00:15,180 --> 00:00:20,910
Today we're going to discuss the new schedule.
"""

_VTT = """WEBVTT

00:12.420 --> 00:15.180
<v Speaker>Hello everyone.</v>

00:15.180 --> 00:20.910
Today we're going
to discuss the new schedule.
"""


def test_srt_parses_with_start_end_text() -> None:
    segments = parse_srt_vtt(_SRT)
    assert [(s.start, s.end, s.text) for s in segments] == [
        (Decimal("12.42"), Decimal("15.18"), "Hello everyone."),
        (Decimal("15.18"), Decimal("20.91"), "Today we're going to discuss the new schedule."),
    ]


def test_vtt_header_voice_tags_and_multiline_fold() -> None:
    segments = parse_srt_vtt(_VTT)
    assert len(segments) == 2
    assert segments[0].text == "Hello everyone."
    assert segments[1].text == "Today we're going to discuss the new schedule."


def test_valid_transcript_passes() -> None:
    result = validate_transcript(parse_srt_vtt(_SRT))
    assert result.valid is True
    assert result.errors == []


def test_end_before_start_is_error() -> None:
    segments = parse_srt_vtt("1\n00:00:05,000 --> 00:00:02,000\nBackwards.\n")
    result = validate_transcript(segments)
    assert result.valid is False
    assert result.errors == ["Segment 1 has end <= start"]


def test_unsorted_is_error() -> None:
    raw = "1\n00:00:10,000 --> 00:00:12,000\nSecond.\n\n2\n00:00:01,000 --> 00:00:03,000\nFirst.\n"
    result = validate_transcript(parse_srt_vtt(raw))
    assert result.valid is False
    assert result.errors == ["Segment 2 starts before segment 1"]


def test_empty_text_is_error() -> None:
    segments = parse_srt_vtt("1\n00:00:01,000 --> 00:00:03,000\n<i></i>\n")
    assert segments == []
    result = validate_transcript(segments)
    assert result.valid is False
    assert result.errors == ["Transcript is empty"]


def test_overlap_is_warning_not_error() -> None:
    raw = "1\n00:00:01,000 --> 00:00:05,000\nOne.\n\n2\n00:00:04,000 --> 00:00:06,000\nTwo.\n"
    result = validate_transcript(parse_srt_vtt(raw))
    assert result.valid is True
    assert result.warnings == ["Segment 2 overlaps segment 1"]


def test_end_after_duration_is_error_only_when_duration_known() -> None:
    segments = parse_srt_vtt(_SRT)
    assert validate_transcript(segments, duration_seconds=Decimal("30")).valid is True
    result = validate_transcript(segments, duration_seconds=Decimal("20"))
    assert result.valid is False
    assert result.errors == ["Segment 2 ends after the video duration"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello everyone.", True),
        ("♪ We're no strangers to love ♪", True),
        ("[Music] hello?", True),
        ("Call me at 5.", True),
        ("[♪♪♪]", False),
        ("[Music]", False),
        ("[music playing]", False),
        ("[Applause]", False),
        ("(laughter)", False),
        ("...", False),
        ("", False),
        ("   ", False),
        # Thà giữ nhầm còn hơn bỏ sót: ngoặc có chữ ngoài danh sách là giữ.
        ("[man laughing]", True),
    ],
)
def test_is_speakable(text: str, expected: bool) -> None:
    assert is_speakable(text) is expected


def _seg(start: str, end: str, text: str) -> ParsedSegment:
    return ParsedSegment(start=Decimal(start), end=Decimal(end), text=text)


def test_merge_fragments_forward() -> None:
    out = merge_fragments(
        [
            _seg("1", "2", "Today we're going"),
            _seg("2", "4", "to discuss the new schedule."),
            _seg("5", "9", "Hello everyone."),
        ]
    )
    assert [(s.start, s.end, s.text) for s in out] == [
        (Decimal("1"), Decimal("4"), "Today we're going to discuss the new schedule."),
        (Decimal("5"), Decimal("9"), "Hello everyone."),
    ]


def test_merge_keeps_terminated_and_long_lines() -> None:
    out = merge_fragments(
        [
            _seg("1", "2", "Hello."),
            _seg("3", "23", "a twenty second blob without punctuation at all"),
            _seg("24", "25", "Bye."),
        ]
    )
    assert [s.text for s in out] == [
        "Hello.",
        "a twenty second blob without punctuation at all",
        "Bye.",
    ]


def test_merge_trailing_fragment_backwards() -> None:
    out = merge_fragments(
        [
            _seg("1", "5", "Hello everyone."),
            _seg("6", "7", "and welcome"),
        ]
    )
    assert [(s.start, s.end, s.text) for s in out] == [
        (Decimal("1"), Decimal("7"), "Hello everyone. and welcome"),
    ]


def test_merge_empty() -> None:
    assert merge_fragments([]) == []


def test_merge_continuation_mid_word_cut() -> None:
    # Captioner ngắt giữa chừng ("real c" + "in easy..."): câu sau mở bằng chữ
    # thường trong khi câu trước chưa kết thúc -> ghép dù câu trước đã dài.
    out = merge_fragments(
        [
            _seg("0", "6.1", "Hello and welcome to Real Easy English we have real c"),
            _seg("6.1", "8.3", "in easy English to help you learn."),
            _seg("9.4", "11.0", "And I'm Beth."),
        ]
    )
    assert [(s.start, s.end) for s in out] == [
        (Decimal("0"), Decimal("8.3")),
        (Decimal("9.4"), Decimal("11.0")),
    ]
    assert out[0].text.startswith("Hello and welcome")
    assert out[0].text.endswith("to help you learn.")
    assert out[1].text == "And I'm Beth."


def test_count_complete() -> None:
    from app.services.listening_transcript import count_complete

    segs = [
        _seg("0", "2", "Hello."),
        _seg("2", "4", "Never gonna give you up"),
        _seg("4", "14", "a ten second blob without punctuation at all"),
    ]
    assert count_complete(segs) == (2, 3)
    assert count_complete([]) == (0, 0)


def test_passes_quality_rejects_salad_keeps_others() -> None:
    from app.services.listening_transcript import passes_quality

    salad = [
        _seg("11.96", "19.68", "courts power group is an energy company based in the"),
        _seg("15.92", "25.84", "UK Marcus the managing director wants to discuss"),
        _seg("22.68", "28.52", "is meeting Meer the finance director"),
    ]
    ok, reason = passes_quality(salad)
    assert ok is False
    assert "overlapping" in reason

    lyrics = [
        _seg("0", "2.4", "Never gonna give you up"),
        _seg("2.4", "4.4", "Never gonna let you down"),
    ]
    assert passes_quality(lyrics) == (True, "")

    punctuated_overlap = [
        _seg("0.3", "4.7", "Hello. Excuse me."),
        _seg("2.5", "7.4", "Hello. How can I help you?"),
    ]
    assert passes_quality(punctuated_overlap) == (True, "")

    assert passes_quality([]) == (False, "no segments")
