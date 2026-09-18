"""Resolve a pasted video URL into a normalized listening source.

Frontend KHÔNG tự parse URL ở nhiều nơi: mọi đường vào (paste form hôm nay,
import hàng loạt ngày mai) đều đi qua `resolve_source`, và backend validate lại
kể cả khi client đã kiểm — client chỉ kiểm để phản hồi tức thì.

Không có fetch mạng ở đây: resolve là thuần cú pháp (host + ID). Có mạng mới
biết video có tồn tại/embed được không, và slice này cố ý không gọi ra ngoài
(không key, không quota, không SSRF — xem SPEC §19).
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

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

# YouTube video ID: đúng 11 ký tự URL-safe. Ngắn/dài hơn là ID hỏng, không phải
# video khác — báo INVALID chứ không nhận bừa rồi để player kẹt.
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class SourceError(Exception):
    """URL không dùng được. `code` là một trong hai hằng trên."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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


def resolve_source(raw_url: str) -> ListeningSource:
    """Chuẩn hoá URL paste thành source YouTube.

    Slice này chỉ cho qua YouTube; TikTok nhận diện đúng rồi từ chối lịch sự
    (UNSUPPORTED) thay vì báo URL hỏng — người dùng cần biết link họ đúng mà
    tính năng chưa có, chứ không phải đi sửa một cái link không sai.
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
    if host in _TIKTOK_HOSTS:
        raise SourceError(UNSUPPORTED_SOURCE)
    if host not in _YOUTUBE_HOSTS:
        raise SourceError(UNSUPPORTED_SOURCE)

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
