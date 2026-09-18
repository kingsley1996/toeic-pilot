"""Resolve a pasted video URL into a normalized listening source.

Frontend KHÔNG tự parse URL ở nhiều nơi: mọi đường vào (paste form hôm nay,
import hàng loạt ngày mai) đều đi qua `resolve_source`, và backend validate lại
kể cả khi client đã kiểm — client chỉ kiểm để phản hồi tức thì.

YouTube là thuần cú pháp (host + ID). TikTok link rút gọn (vm/vt) phải theo
redirect mới biết ID — một GET duy nhất tới host đã allowlist, đích đến cũng
phải là TikTok mới nhận (chi tiết ở `_resolve_short`). Không key, không quota.
"""

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qs, urlparse

import httpx

# Mã lỗi ra ngoài theo SPEC §18 — frontend map thành câu thân thiện, không bao
# giờ hiện raw exception.
INVALID_URL = "INVALID_URL"
UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"

_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)
_TIKTOK_HOSTS = frozenset(
    {
        "tiktok.com",
        "www.tiktok.com",
        "vm.tiktok.com",
        "vt.tiktok.com",
    }
)
# Host rút gọn — chỉ hai host này được fetch redirect, và đích đến phải là
# TikTok đầy đủ (dưới). Fetch host user đưa mà không allowlist trước là SSRF.
_TIKTOK_SHORT_HOSTS = frozenset({"vm.tiktok.com", "vt.tiktok.com"})
_TIKTOK_FULL_HOSTS = frozenset({"tiktok.com", "www.tiktok.com"})

# YouTube video ID: đúng 11 ký tự URL-safe. Ngắn/dài hơn là ID hỏng, không phải
# video khác — báo INVALID chứ không nhận bừa rồi để player kẹt.
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
# TikTok video ID là số (snowflake, thực tế 19 chữ số). Nới 8–24 để không gãy
# khi họ đổi độ dài — sai số còn lại (số bừa) thì oEmbed/player báo sau.
_TIKTOK_ID = re.compile(r"^\d{8,24}$")


class SourceError(Exception):
    """URL không dùng được. `code` là một trong hai hằng trên."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RedirectTransport(Protocol):
    """Theo redirect của link rút gọn, trả về URL cuối. Tách protocol để test
    không chạm mạng — cùng mẹo với `YoutubeTransport` bên captions."""

    def final_url(self, url: str) -> str: ...


class HttpxRedirectTransport:
    def final_url(self, url: str) -> str:
        try:
            with httpx.Client(follow_redirects=True, max_redirects=5, timeout=10.0) as client:
                response = client.get(url)
        except httpx.HTTPError as exc:
            raise SourceError(INVALID_URL) from exc
        return str(response.url)


@dataclass(frozen=True)
class ListeningSource:
    type: str
    external_id: str
    url: str


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _pick(path_parts: list[str], query: dict[str, list[str]]) -> str | None:
    """Trích video ID theo hình dạng path. Không đoán: không khớp hình nào quen
    thì trả None (INVALID), chứ không cắt bừa một đoạn path làm ID."""
    if len(path_parts) == 1 and path_parts[0] in ("embed", "shorts", "live"):
        return None
    if len(path_parts) == 2 and path_parts[0] in ("embed", "shorts", "live"):
        return path_parts[1]
    if path_parts[:1] == ["watch"]:
        values = query.get("v", [])
        return values[0] if values else None
    if len(path_parts) == 1 and path_parts[0]:
        # youtu.be/<id> — host đã xác định, phần path duy nhất là ID.
        return path_parts[0]
    return None


def _pick_tiktok(path_parts: list[str]) -> str | None:
    """Trích TikTok video ID số. Không đoán như `_pick`: không khớp hình quen
    (kể cả URL profile `/@user` không có video) thì None — link đúng mà không
    phải video thì báo INVALID, vì với Lab nó cũng vô dụng như link hỏng."""
    if len(path_parts) == 3 and path_parts[1] == "video" and path_parts[0]:
        candidate = path_parts[2]
    elif len(path_parts) == 2 and path_parts[0] == "video":
        candidate = path_parts[1]
    elif len(path_parts) == 2 and path_parts[0] == "embed":
        candidate = path_parts[1]
    elif len(path_parts) == 3 and path_parts[:2] == ["embed", "v2"]:
        candidate = path_parts[2]
    else:
        return None
    return candidate if _TIKTOK_ID.match(candidate) else None


def _resolve_tiktok_short(
    candidate: str, transport: RedirectTransport | None
) -> ListeningSource:
    """Link rút gọn vm/vt → theo redirect → parse như link đầy đủ. Đích đến
    KHÔNG phải TikTok (link chết hay bị tráo) thì INVALID, không phải
    UNSUPPORTED — vấn đề nằm ở link này, không phải ở loại nguồn."""
    transport = transport or HttpxRedirectTransport()
    final = transport.final_url(candidate)
    if _host(final) not in _TIKTOK_FULL_HOSTS or not final.startswith("https://"):
        raise SourceError(INVALID_URL)
    parts = [p for p in urlparse(final).path.split("/") if p]
    video_id = _pick_tiktok(parts)
    if not video_id:
        raise SourceError(INVALID_URL)
    return ListeningSource(
        type="tiktok",
        external_id=video_id,
        url=f"https://www.tiktok.com/{'/'.join(parts)}",
    )


def resolve_source(raw_url: str, transport: RedirectTransport | None = None) -> ListeningSource:
    """Chuẩn hoá URL paste thành source YouTube hoặc TikTok.

    `transport` chỉ dùng cho link rút gọn TikTok (test truyền giả, production
    mặc định httpx thật). Đường YouTube thuần cú pháp như cũ, không chạm mạng.
    """
    text = (raw_url or "").strip()
    if not text:
        raise SourceError(INVALID_URL)
    candidate = text if "://" in text else f"https://{text}"

    host = _host(candidate)
    # Không có dấu chấm thì không phải URL (chữ gõ nhầm, câu văn...) — báo
    # INVALID để user kiểm tra lại link, chứ không phải UNSUPPORTED.
    if not host or "." not in host:
        raise SourceError(INVALID_URL)
    if host not in _YOUTUBE_HOSTS and host not in _TIKTOK_HOSTS:
        raise SourceError(UNSUPPORTED_SOURCE)

    if host in _TIKTOK_HOSTS:
        if host in _TIKTOK_SHORT_HOSTS:
            return _resolve_tiktok_short(candidate, transport)
        parts = [p for p in urlparse(candidate).path.split("/") if p]
        video_id = _pick_tiktok(parts)
        if not video_id:
            raise SourceError(INVALID_URL)
        return ListeningSource(
            type="tiktok",
            external_id=video_id,
            url=f"https://www.tiktok.com/{'/'.join(parts)}",
        )
    parsed = urlparse(candidate)
    parts = [p for p in parsed.path.split("/") if p]
    video_id = _pick(parts, parse_qs(parsed.query))
    if not video_id or not _VIDEO_ID.match(video_id):
        raise SourceError(INVALID_URL)

    return ListeningSource(
        type="youtube",
        external_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
    )
