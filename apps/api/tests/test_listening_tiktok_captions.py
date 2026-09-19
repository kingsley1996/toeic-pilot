"""Phụ đề TikTok: chọn track tiếng Anh + map lỗi, không gọi mạng."""

import pytest

from app.services.listening_tiktok_captions import (
    CAPTIONS_FETCH_FAILED,
    CAPTIONS_UNAVAILABLE,
    CaptionError,
    fetch_tiktok_captions,
    pick_subtitle,
)

_VTT = """WEBVTT

00:00:00.000 --> 00:00:06.680
of or from she's afraid spiders

00:00:09.860 --> 00:00:15.520
of they're suffering food poisoning
"""

_URL = "https://www.tiktok.com/@u/video/7253146839854222619"


def _info(**overrides: object) -> dict:
    base: dict = {"title": "  Of vs from  ", "subtitles": {}, "automatic_captions": {}}
    base.update(overrides)
    return base


class _FakeTransport:
    def __init__(self, info: dict, text: str = _VTT) -> None:
        self.info = info
        self.text = text
        self.seen: list[str] = []

    def extract_info(self, url: str) -> dict:
        self.seen.append(url)
        return self.info

    def get_text(self, url: str) -> str:
        self.seen.append(url)
        return self.text


def test_prefers_manual_over_auto() -> None:
    info = _info(
        subtitles={"en": [{"url": "https://cdn/x.vtt", "ext": "vtt"}]},
        automatic_captions={"eng-US": [{"url": "https://cdn/y.vtt", "ext": "vtt"}]},
    )
    assert pick_subtitle(info) == ("en", "https://cdn/x.vtt", "manual")


def test_picks_english_variant_and_https_only() -> None:
    info = _info(
        automatic_captions={
            "vi": [{"url": "https://cdn/vi.vtt", "ext": "vtt"}],
            "eng-US": [{"url": "https://cdn/en.vtt", "ext": "vtt"}],
            "en": [{"url": "http://cdn/plain.vtt", "ext": "vtt"}],
        }
    )
    assert pick_subtitle(info) == ("eng-US", "https://cdn/en.vtt", "asr")


def test_no_english_track_is_unavailable() -> None:
    assert pick_subtitle(_info()) is None
    with pytest.raises(CaptionError) as exc:
        fetch_tiktok_captions(_URL, transport=_FakeTransport(_info()))
    assert exc.value.code == CAPTIONS_UNAVAILABLE


def test_fetch_returns_segments_and_title() -> None:
    info = _info(automatic_captions={"eng-US": [{"url": "https://cdn/en.vtt", "ext": "vtt"}]})
    captions = fetch_tiktok_captions(_URL, transport=_FakeTransport(info))
    assert captions.language == "eng-US"
    assert captions.kind == "asr"
    assert captions.title == "Of vs from"
    assert [s.text for s in captions.segments] == [
        "of or from she's afraid spiders",
        "of they're suffering food poisoning",
    ]


def test_unparseable_subtitle_is_unavailable() -> None:
    info = _info(automatic_captions={"en": [{"url": "https://cdn/en.vtt", "ext": "vtt"}]})
    with pytest.raises(CaptionError) as exc:
        fetch_tiktok_captions(_URL, transport=_FakeTransport(info, text="not subtitles"))
    assert exc.value.code == CAPTIONS_UNAVAILABLE


def test_transport_blowup_is_fetch_failed() -> None:
    class _Broken:
        def extract_info(self, url: str) -> dict:
            raise RuntimeError("yt-dlp exploded")

        def get_text(self, url: str) -> str:
            raise AssertionError("unreached")

    with pytest.raises(CaptionError) as exc:
        fetch_tiktok_captions(_URL, transport=_Broken())
    assert exc.value.code == CAPTIONS_FETCH_FAILED
