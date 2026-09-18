"""Lấy phụ đề public của YouTube để điền Listening Lab.

Không tải media (SPEC §3, §19). Không fetch URL user dán: `resolve_source` lấy
ID, rồi chỉ gọi host YouTube đã whitelist. Cùng track phụ đề mà player embed
đã dùng — không phải Data API (captions.download chỉ cho chủ video).

YouTube đổi InnerTube thường xuyên; test mock HTTP, không gọi mạng.
"""

from __future__ import annotations

import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.services.listening_transcript import ParsedSegment, parse_srt_vtt, segments_to_vtt

logger = logging.getLogger(__name__)

CAPTIONS_UNAVAILABLE = "CAPTIONS_UNAVAILABLE"
CAPTIONS_FETCH_FAILED = "CAPTIONS_FETCH_FAILED"
VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"

_PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"
_TIMEOUT = 12.0
_CAPTION_HOSTS = frozenset(
    {
        "www.youtube.com",
        "youtube.com",
        "m.youtube.com",
        "youtubei.googleapis.com",
    }
)
_WS = re.compile(r"\s+")


class CaptionError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class YoutubeTransport(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any: ...
    def get_text(self, url: str, headers: dict[str, str]) -> str: ...


@dataclass(frozen=True)
class YoutubeCaptions:
    language: str
    kind: str
    raw_vtt: str
    segments: list[ParsedSegment]
    title: str | None


class HttpxYoutubeTransport:
    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        except httpx.HTTPError as exc:
            raise CaptionError(CAPTIONS_FETCH_FAILED) from exc
        if response.status_code >= 400:
            raise CaptionError(CAPTIONS_FETCH_FAILED)
        try:
            return response.json()
        except ValueError as exc:
            raise CaptionError(CAPTIONS_FETCH_FAILED) from exc

    def get_text(self, url: str, headers: dict[str, str]) -> str:
        _assert_caption_url(url)
        try:
            response = httpx.get(url, headers=headers, timeout=_TIMEOUT, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise CaptionError(CAPTIONS_FETCH_FAILED) from exc
        if response.status_code >= 400 or not response.text.strip():
            raise CaptionError(CAPTIONS_UNAVAILABLE)
        return response.text


def _assert_caption_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _CAPTION_HOSTS:
        raise CaptionError(CAPTIONS_FETCH_FAILED)


def _android_payload(video_id: str) -> dict[str, Any]:
    return {
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "20.10.38",
                "hl": "en",
                "gl": "US",
            }
        },
        "videoId": video_id,
        "contentCheckOk": True,
        "racyCheckOk": True,
    }


def _player_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 14) gzip",
        "X-YouTube-Client-Name": "3",
        "X-YouTube-Client-Version": "20.10.38",
    }


def _playability(player: Any) -> tuple[str | None, str | None]:
    """(status, reason) của InnerTube. `reason` là thứ duy nhất phân biệt được
    region-block/bot-wall/video-xoá — vứt nó là mọi ca prod-khác-local đều mù."""
    status_block = player.get("playabilityStatus") if isinstance(player, dict) else None
    if not isinstance(status_block, dict):
        return None, None
    status = status_block.get("status")
    reason = status_block.get("reason")
    return (
        status if isinstance(status, str) else None,
        reason if isinstance(reason, str) else None,
    )


def _caption_tracks(player: Any, video_id: str) -> list[dict[str, Any]]:
    if not isinstance(player, dict):
        return []
    status, reason = _playability(player)
    if status and status != "OK":
        # Không raise ở đây: client android bị tường bot (LOGIN_REQUIRED) không
        # có nghĩa client web cũng thế — để caller thử hết rồi mới kết luận.
        logger.warning("youtube playability %s for %s: %s", status, video_id, (reason or "")[:160])
        return []
    renderer = (player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}
    tracks = renderer.get("captionTracks") or []
    return [t for t in tracks if isinstance(t, dict) and t.get("baseUrl")]


def _score(track: dict[str, Any]) -> tuple[int, int, int]:
    lang = str(track.get("languageCode") or "").lower()
    asr = 1 if track.get("kind") == "asr" else 0
    if lang == "en":
        en = 0
    elif lang.startswith("en"):
        en = 1
    else:
        en = 2
    return (en, asr, 0 if lang == "en" else 1)


def _pick_track(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    return min(tracks, key=_score)


def _clean(text: str) -> str:
    stripped = _WS.sub(" ", html.unescape(re.sub(r"<[^>]*>", "", text))).strip()
    # Dấu ">>" đầu dòng là marker người nói của TTML (">> Hello.") — để lại thì
    # mặt hiển thị lẫn đáp án đều dính nhiễu.
    return re.sub(r"(^|\s)>>+\s?", r"\1", stripped).strip()


def parse_caption_payload(raw: str) -> list[ParsedSegment]:
    text = (raw or "").lstrip("\ufeff").strip()
    if not text:
        return []
    if text.startswith("WEBVTT") or "-->" in text[:400]:
        return parse_srt_vtt(text)
    if text.startswith("{") or text.startswith("["):
        return _parse_json3(text)
    return _parse_xml(text)


def _parse_xml(raw: str) -> list[ParsedSegment]:
    """Timedtext XML có hai hình: srv1 (`<text start="12.42" dur="2.76">`, GIÂY)
    và v3 (`<p t="1360" d="1680">`, MILI-GIÂY). Nhầm tỉ lệ là bài học seek tới
    phút 22 của video 3 phút rưỡi — hỏng im lặng, nên đơn vị suy từ TÊN attr
    (chuẩn timedtext), không đoán theo độ lớn số."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    segments: list[ParsedSegment] = []
    for node in list(root.iter("text")) + list(root.iter("p")):
        if node.tag == "p":
            start_raw, dur_raw, scale = node.attrib.get("t"), node.attrib.get("d"), Decimal(1000)
        else:
            start_raw, dur_raw, scale = node.attrib.get("start"), node.attrib.get("dur"), Decimal(1)
        if start_raw is None:
            continue
        try:
            start = Decimal(start_raw) / scale
            dur = Decimal(dur_raw or "0") / scale
        except (InvalidOperation, ValueError):
            continue
        body = _clean("".join(node.itertext()))
        if not body or dur <= 0:
            continue
        segments.append(ParsedSegment(start=start, end=start + dur, text=body))
    return segments


def _parse_json3(raw: str) -> list[ParsedSegment]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        return []
    segments: list[ParsedSegment] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs")
        if not isinstance(segs, list):
            continue
        body = _clean(
            "".join(str(part.get("utf8") or "") for part in segs if isinstance(part, dict))
        )
        if not body:
            continue
        start_ms = event.get("tStartMs")
        dur_ms = event.get("dDurationMs")
        if not isinstance(start_ms, int) or not isinstance(dur_ms, int) or dur_ms <= 0:
            continue
        start = Decimal(start_ms) / 1000
        segments.append(ParsedSegment(start=start, end=start + Decimal(dur_ms) / 1000, text=body))
    return segments


def _web_payload(video_id: str) -> dict[str, Any]:
    return {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20241219.01.00",
                "hl": "en",
                "gl": "US",
            }
        },
        "videoId": video_id,
        "contentCheckOk": True,
        "racyCheckOk": True,
    }


def _web_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }


def fetch_youtube_captions(
    video_id: str,
    *,
    transport: YoutubeTransport | None = None,
) -> YoutubeCaptions:
    client = transport or HttpxYoutubeTransport()
    blocked: list[str] = []
    player: Any = None
    tracks: list[dict[str, Any]] = []
    for name, payload, headers in (
        ("android", _android_payload(video_id), _player_headers()),
        ("web", _web_payload(video_id), _web_headers()),
    ):
        player = client.post_json(_PLAYER_URL, payload, headers)
        status, _ = _playability(player)
        if status and status != "OK":
            blocked.append(f"{name}={status}")
        tracks = _caption_tracks(player, video_id)
        if tracks:
            break
    if not tracks:
        # Cả hai client đều không ra track: video bị chặn/xoá (blocked có tên)
        # hay thật sự không có phụ đề (blocked rỗng) — hai mã khác nhau để UI
        # nói đúng câu.
        if blocked:
            logger.warning("youtube blocked %s for %s", ",".join(blocked), video_id)
            raise CaptionError(VIDEO_UNAVAILABLE)
        raise CaptionError(CAPTIONS_UNAVAILABLE)
    track = _pick_track(tracks)
    caption_url = str(track["baseUrl"])
    raw = client.get_text(caption_url, {"User-Agent": _player_headers()["User-Agent"]})
    segments = parse_caption_payload(raw)
    if not segments:
        raise CaptionError(CAPTIONS_UNAVAILABLE)
    language = str(track.get("languageCode") or "und")
    kind = "asr" if track.get("kind") == "asr" else "manual"
    title = None
    details = player.get("videoDetails") if isinstance(player, dict) else None
    if isinstance(details, dict) and isinstance(details.get("title"), str):
        title = details["title"].strip() or None
    return YoutubeCaptions(
        language=language,
        kind=kind,
        raw_vtt=segments_to_vtt(segments),
        segments=segments,
        title=title,
    )
