"""Cache-Control cho GET nội dung đọc nhiều.

Không CDN/proxy (ADR-015: Cloudflare chỉ là widget Turnstile) nên cache duy
nhất là trình duyệt, theo từng máy — không có chuyện user A đọc ké entry của
user B ở edge. Nội dung đổi chỉ khi admin publish tay (hiếm), nên stale trong
TTL là thẩm mỹ chứ không phải hỏng dữ liệu.

ALLOWLIST chứ không phải blocklist: endpoint user mới sinh sau này mặc định
không cache. Hai nhóm:

- thuần public (không auth, không trường user): `public`, trình duyệt nào
  cũng giữ, qua lại giữa các trang trong TTL không tốn RTT;
- lẫn user-data (`learned_count`, `completed_*` — cùng URL cho khách lẫn
  learner, token nằm ở header): `private` + `Vary: Authorization`, nếu không
  máy dùng chung + đổi acc sẽ thấy số người trước (đúng lỗi R1 vừa sửa).

Chỉ GET 2xx. POST/PUT/PATCH/DELETE và mọi endpoint authed còn lại không header.
"""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_PUBLIC = "public, max-age=60, stale-while-revalidate=300"
_PRIVATE = "private, max-age=60"

# (pattern, cache-control, vary). Thứ tự không quan trọng: các pattern không
# giao nhau — đặc biệt `/vocabulary/<uuid>` chỉ khớp đúng UUID nên không nuốt
# `/vocabulary-progress`, `/vocabulary-review/...`, `/vocabulary-topic-...`
# (toàn endpoint user).
_RULES: tuple[tuple[re.Pattern[str], str, str | None], ...] = tuple(
    (re.compile(pattern), policy, vary)
    for pattern, policy, vary in (
        (r"^/api/v1/practice/parts$", _PUBLIC, None),
        (r"^/api/v1/topics$", _PUBLIC, None),
        (r"^/api/v1/vocabulary-collections$", _PUBLIC, None),
        (r"^/api/v1/vocabulary-collection-items/[^/]+$", _PUBLIC, None),
        (r"^/api/v1/vocabulary$", _PUBLIC, None),
        (r"^/api/v1/vocabulary-collocations$", _PUBLIC, None),
        (r"^/api/v1/vocabulary/[0-9a-fA-F-]{36}$", _PUBLIC, None),
        (r"^/api/v1/dictation$", _PUBLIC, None),
        (r"^/api/v1/vocabulary-collections/.+$", _PRIVATE, "Authorization"),
        (r"^/api/v1/grammar-topics($|/.+$)", _PRIVATE, "Authorization"),
        (r"^/api/v1/grammar-lessons/[^/]+$", _PRIVATE, "Authorization"),
        (r"^/api/v1/practice/parts/\d+/tactics$", _PRIVATE, "Authorization"),
    )
)


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.method != "GET" or not 200 <= response.status_code < 300:
            return response
        for pattern, policy, vary in _RULES:
            if pattern.match(request.url.path):
                response.headers["Cache-Control"] = policy
                if vary is not None:
                    response.headers["Vary"] = vary
                break
        return response
