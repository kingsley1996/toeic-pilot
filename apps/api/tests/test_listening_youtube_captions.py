"""Phụ đề YouTube: parse XML/json3/VTT + chọn track, không gọi mạng."""

from decimal import Decimal

import pytest

from app.services.listening_youtube_captions import (
    CAPTIONS_FETCH_FAILED,
    CAPTIONS_UNAVAILABLE,
    VIDEO_UNAVAILABLE,
    CaptionError,
    fetch_youtube_captions,
    parse_caption_payload,
)

_XML = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
  <text start="12.42" dur="2.76">Hello &amp; welcome.</text>
  <text start="15.18" dur="5.73">Today we&#39;re going to discuss the new schedule.</text>
</transcript>
"""

_JSON3 = """{
  "events": [
    {"tStartMs": 12420, "dDurationMs": 2760, "segs": [{"utf8": "Hello "}, {"utf8": "everyone."}]},
    {"tStartMs": 15000, "segs": [{"utf8": "\\n"}]},
    {"tStartMs": 15180, "dDurationMs": 5730, "segs": [{"utf8": "Today we're going."}]}
  ]
}"""

_VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
First line.
"""

# Timedtext v3 (thứ InnerTube trả cho video thật, VD dQw4w9WgXcQ): thẻ `<p>`,
# timestamp MILI-GIÂY. Parser cũ chỉ biết `<text>` giây nên trả rỗng.
_XML_V3 = """<?xml version="1.0" encoding="utf-8" ?><timedtext format="3">
<body>
<p t="1360" d="1680">[\u266a\u266a\u266a]</p>
<p t="18640" d="3240">\u266a We&#39;re no strangers to love \u266a</p>
</body>
</timedtext>
"""


def test_parse_xml_v3_uses_milliseconds() -> None:
    segs = parse_caption_payload(_XML_V3)
    assert [(s.start, s.end) for s in segs] == [
        (Decimal("1.36"), Decimal("3.04")),
        (Decimal("18.64"), Decimal("21.88")),
    ]
    assert segs[1].text == "♪ We're no strangers to love ♪"


def test_parse_xml_unescapes_and_keeps_times() -> None:
    segs = parse_caption_payload(_XML)
    assert [s.text for s in segs] == [
        "Hello & welcome.",
        "Today we're going to discuss the new schedule.",
    ]
    assert segs[0].start == Decimal("12.42")
    assert segs[0].end == Decimal("15.18")


def test_parse_json3_skips_newline_only_events() -> None:
    segs = parse_caption_payload(_JSON3)
    assert [s.text for s in segs] == ["Hello everyone.", "Today we're going."]
    assert segs[0].start == Decimal("12.42")


def test_parse_vtt_reuses_existing_parser() -> None:
    segs = parse_caption_payload(_VTT)
    assert len(segs) == 1
    assert segs[0].text == "First line."


class _FakeTransport:
    def __init__(self, player: object, captions: str, *, seen: list[str] | None = None) -> None:
        self.player = player
        self.captions = captions
        self.seen = seen if seen is not None else []

    def post_json(self, url: str, payload: dict[str, object], headers: dict[str, str]) -> object:
        self.seen.append(url)
        return self.player

    def get_text(self, url: str, headers: dict[str, str]) -> str:
        self.seen.append(url)
        return self.captions


def test_prefers_manual_english_over_asr() -> None:
    player = {
        "playabilityStatus": {"status": "OK"},
        "videoDetails": {"title": "Demo talk"},
        "captions": {
            "playerCaptionsTracklistRenderer": {
                "captionTracks": [
                    {
                        "baseUrl": "https://www.youtube.com/api/timedtext?lang=vi",
                        "languageCode": "vi",
                    },
                    {
                        "baseUrl": "https://www.youtube.com/api/timedtext?lang=en&kind=asr",
                        "languageCode": "en",
                        "kind": "asr",
                    },
                    {
                        "baseUrl": "https://www.youtube.com/api/timedtext?lang=en",
                        "languageCode": "en",
                    },
                ]
            }
        },
    }
    seen: list[str] = []
    result = fetch_youtube_captions(
        "dQw4w9WgXcQ", transport=_FakeTransport(player, _XML, seen=seen)
    )
    assert result.kind == "manual"
    assert result.language == "en"
    assert result.title == "Demo talk"
    assert len(result.segments) == 2
    assert "lang=en" in seen[-1]
    assert "kind=asr" not in seen[-1]
    assert result.raw_vtt.startswith("WEBVTT")


def test_unplayable_video_is_unavailable() -> None:
    player = {"playabilityStatus": {"status": "UNPLAYABLE"}}
    with pytest.raises(CaptionError) as exc:
        fetch_youtube_captions("dQw4w9WgXcQ", transport=_FakeTransport(player, _XML))
    assert exc.value.code == VIDEO_UNAVAILABLE


def test_missing_tracks_is_captions_unavailable() -> None:
    player = {"playabilityStatus": {"status": "OK"}, "captions": {}}
    with pytest.raises(CaptionError) as exc:
        fetch_youtube_captions("dQw4w9WgXcQ", transport=_FakeTransport(player, _XML))
    assert exc.value.code == CAPTIONS_UNAVAILABLE


def test_refuses_non_youtube_caption_host() -> None:
    from app.services.listening_youtube_captions import HttpxYoutubeTransport

    with pytest.raises(CaptionError) as exc:
        HttpxYoutubeTransport().get_text("https://evil.example/steal", {})
    assert exc.value.code == CAPTIONS_FETCH_FAILED
