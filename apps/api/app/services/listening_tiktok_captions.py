"""Lấy phụ đề auto của TikTok để điền Listening Lab.

YouTube có InnerTube trả track caption trực tiếp (`listening_youtube_captions`);
TikTok không có API public nên đi qua yt-dlp — INFO-ONLY, không tải media
(SPEC §3, §19 giữ nguyên): `extract_info` với `writesubtitles` cho ra
`requested_subtitles` (URL file VTT), rồi fetch URL đó bằng httpx và parse
bằng parser VTT có sẵn.

Ba thứ giòn ghi ở đây để người sau không mất công tìm lại:
- TikTok chặn client lạ ("Unexpected response from webpage request"): phải
  impersonate Chrome qua curl_cffi — thiếu là hỏng 100%, không phải flaky.
- Không `writesubtitles` thì extractor không fetch sub (info về rỗng) — thiếu
  flag này mà kết luận "video không có sub" là sai.
- Không phải video nào cũng có sub tiếng Anh: thiếu thì CAPTIONS_UNAVAILABLE
  (UI bảo dán tay), không phải lỗi fetch.
- Chậm hơn YouTube (vài request + JS challenge, ~10-30s). Đây là hành động của
  admin lúc soạn bài, không phải đường nóng của learner — quota captions vẫn
  chặn loop như cũ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from yt_dlp import YoutubeDL
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import YoutubeDLError

from app.services.listening_transcript import ParsedSegment, parse_srt_vtt
from app.services.listening_youtube_captions import (
    CAPTIONS_FETCH_FAILED,
    CAPTIONS_UNAVAILABLE,
    CaptionError,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 12.0


class TiktokTransport(Protocol):
    """Lấy info video + nội dung file sub. Tách protocol để test không chạm
    mạng — cùng mẹo với `YoutubeTransport` bên YouTube."""

    def extract_info(self, url: str) -> dict[str, Any]: ...
    def get_text(self, url: str) -> str: ...


@dataclass(frozen=True)
class TiktokCaptions:
    language: str
    kind: str
    raw_vtt: str
    segments: list[ParsedSegment]
    title: str | None


class YtDlpTiktokTransport:
    def extract_info(self, url: str) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "impersonate": ImpersonateTarget.from_str("chrome"),
            "socket_timeout": 20,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en.*"],
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except YoutubeDLError as exc:
            # Video xoá/riêng tư hay mạng hỏng đều ra đây — yt-dlp không phân
            # biệt đủ tin để tách VIDEO_UNAVAILABLE riêng như YouTube.
            raise CaptionError(CAPTIONS_FETCH_FAILED) from exc
        if not isinstance(info, dict):
            raise CaptionError(CAPTIONS_FETCH_FAILED)
        return info

    def get_text(self, url: str) -> str:
        # URL sub do yt-dlp trả về cho video vừa resolve (host CDN ký theo
        # video, không allowlist cứng được như YouTube) — chỉ nhận https.
        if not url.startswith("https://"):
            raise CaptionError(CAPTIONS_FETCH_FAILED)
        try:
            response = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise CaptionError(CAPTIONS_FETCH_FAILED) from exc
        if response.status_code >= 400 or not response.text.strip():
            raise CaptionError(CAPTIONS_UNAVAILABLE)
        return response.text


def _is_english(code: str) -> bool:
    # TikTok trả mã 3 chữ (`eng-US`), YouTube 2 chữ (`en-US`) — nhận cả hai.
    normalized = code.lower().replace("_", "-")
    return normalized in ("en", "eng") or normalized.startswith(("en-", "eng-"))


def pick_subtitle(info: dict[str, Any]) -> tuple[str, str, str] | None:
    """(language, url, kind) của track tiếng Anh tốt nhất: sub tay trước, auto
    sau; trong mỗi nhóm `en` đúng rồi mới `en-*`. Trả None khi không có gì."""
    manual = info.get("subtitles")
    auto = info.get("automatic_captions")
    for tracks, kind in (
        (manual, "manual") if isinstance(manual, dict) else (None, ""),
        (auto, "asr") if isinstance(auto, dict) else (None, ""),
    ):
        if not tracks:
            continue
        candidates: list[tuple[str, str]] = []
        for code, items in tracks.items():
            if not _is_english(str(code)) or not isinstance(items, list):
                continue
            for track in items:
                if not isinstance(track, dict):
                    continue
                url = track.get("url")
                if isinstance(url, str) and url.startswith("https://"):
                    candidates.append((str(code), url))
        if not candidates:
            continue
        candidates.sort(
            key=lambda c: (0 if c[0].lower().replace("_", "-") in ("en", "eng") else 1, c[0])
        )
        code, url = candidates[0]
        return code, url, kind
    # Dự phòng: `requested_subtitles` (yt-dlp đã lọc theo subtitleslangs).
    requested = info.get("requested_subtitles")
    if isinstance(requested, dict):
        for code, track in requested.items():
            if not _is_english(str(code)) or not isinstance(track, dict):
                continue
            url = track.get("url")
            if isinstance(url, str) and url.startswith("https://"):
                kind = "manual" if isinstance(manual, dict) and code in manual else "asr"
                return str(code), url, kind
    return None


def fetch_tiktok_captions(
    canonical_url: str,
    *,
    transport: TiktokTransport | None = None,
) -> TiktokCaptions:
    client = transport or YtDlpTiktokTransport()
    try:
        info = client.extract_info(canonical_url)
    except CaptionError:
        raise
    except Exception as exc:
        raise CaptionError(CAPTIONS_FETCH_FAILED) from exc
    picked = pick_subtitle(info)
    if picked is None:
        raise CaptionError(CAPTIONS_UNAVAILABLE)
    language, url, kind = picked
    raw = client.get_text(url)
    segments = parse_srt_vtt(raw)
    if not segments:
        raise CaptionError(CAPTIONS_UNAVAILABLE)
    title = info.get("title")
    return TiktokCaptions(
        language=language,
        kind=kind,
        raw_vtt=raw,
        segments=segments,
        title=title.strip() if isinstance(title, str) and title.strip() else None,
    )
