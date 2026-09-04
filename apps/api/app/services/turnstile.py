"""Xác minh token Cloudflare Turnstile (ADR-015).

Turnstile là cái mà bộ rate limit theo IP **tự nhận là không làm được**. Trích
nguyên văn `app/api/routes/auth.py`:

    Nó KHÔNG chặn được botnet xoay IP. Chống dò mật khẩu thật sự cần đếm theo
    tài khoản, mà đếm theo tài khoản lại mở đường khoá tài khoản người khác.

Turnstile thoát khỏi thế lưỡng nan ấy vì nó không đếm gì cả: nó bắt **mỗi
request phải trả một cái giá tính toán** ở phía trình duyệt. Kẻ tấn công đổi IP
bao nhiêu lần cũng không né được cái giá đó, còn người dùng thật không bị tính
chung hạn mức với người ngồi cùng đường mạng.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Cloudflare đọc token dưới tên này ở mọi ví dụ của họ; giữ đúng tên để người đọc
# tra ra tài liệu gốc mà không phải đoán.
TOKEN_HEADER = "cf-turnstile-response"

# Token dài tối đa 2048 ký tự theo tài liệu. Cắt sớm ở đây để một header rác
# không thành một request đi ra ngoài mạng.
MAX_TOKEN_LENGTH = 2048

_TIMEOUT = 5.0


class TurnstileRejected(Exception):
    """Cloudflare đã trả lời, và câu trả lời là không."""


def is_configured() -> bool:
    return bool(settings.turnstile_site_key and settings.turnstile_secret_key.get_secret_value())


def verify(token: str, remote_ip: str | None = None) -> None:
    """Hỏi Cloudflare xem token có thật không. Không hợp lệ thì ném `TurnstileRejected`.

    **Hỏng thì MỞ, chối thì ĐÓNG.** Cloudflare nói "không" là chặn; còn không
    *hỏi* được Cloudflare — mạng chập, hết giờ chờ, phía họ 5xx — thì cho qua và
    ghi một dòng cảnh báo.

    Đây đúng là cách bộ rate limit auth đã chọn, vì cùng một lý lẽ: đóng lại
    nghĩa là **không ai đăng nhập được nữa**, tức một phụ thuộc mềm kéo sập cả
    sản phẩm. Và cái giá của việc mở thì có giới hạn đo được: trong lúc
    Cloudflare hỏng, hàng rào tụt về đúng mức bảo vệ của ngày hôm qua — rate
    limit theo IP vẫn chạy — chứ không tụt về không.

    Chỗ này chỉ đúng vì kẻ tấn công **không điều khiển được** đường mạng đi ra
    của máy chủ ta. Ngày nào Turnstile được đặt sau một thứ mà người ngoài chọc
    hỏng được, lý lẽ này hết hiệu lực.
    """
    payload = {"secret": settings.turnstile_secret_key.get_secret_value(), "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = httpx.post(VERIFY_URL, data=payload, timeout=_TIMEOUT)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("turnstile unreachable, letting the request through: %s", error)
        return

    if body.get("success"):
        return

    codes = body.get("error-codes") or []
    # Khoá sai là lỗi CỦA TA, không phải của người đang bấm. Ghi ở mức error để
    # nó không lẫn vào đám cảnh báo bình thường — nếu không, một khoá dán nhầm
    # trông y hệt một ngày nhiều bot.
    if "invalid-input-secret" in codes or "missing-input-secret" in codes:
        logger.error("turnstile secret key is wrong: %s", codes)
    else:
        logger.info("turnstile rejected a token: %s", codes)
    raise TurnstileRejected(", ".join(codes) or "verification failed")
