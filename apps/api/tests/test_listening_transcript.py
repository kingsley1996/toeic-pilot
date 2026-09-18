"""parse + validate transcript paste: SRT/VTT vào, lỗi báo đúng chỗ."""

from decimal import Decimal

import pytest

from app.services.listening_transcript import (
    is_speakable,
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
    raw = (
        "1\n00:00:10,000 --> 00:00:12,000\nSecond.\n\n"
        "2\n00:00:01,000 --> 00:00:03,000\nFirst.\n"
    )
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
