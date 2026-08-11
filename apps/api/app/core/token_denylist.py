"""Thu hồi một token cụ thể trước khi nó hết hạn.

Lỗ mà bộ này lấp không phải là XSS — nó là chuyện **"Đăng xuất" không đăng
xuất**. Trước bản này `logout` chỉ xoá token khỏi `localStorage`; token vẫn hợp
lệ tới bảy ngày, nên một máy dùng chung hay một phiên trình duyệt được khôi
phục vẫn vào được sau khi người dùng đã bấm thoát. Công cụ thu hồi duy nhất khi
đó là `pwc` — đổi mật khẩu — và nó đăng xuất *mọi* thiết bị, tức là quá thô cho
việc "thoát khỏi cái máy này".

**Vì sao `pwc` không đủ:** nó là một *thế hệ* dùng chung cho cả tài khoản, nên
chỉ biểu diễn được "huỷ tất cả". Thu hồi từng phiên cần một định danh cho từng
token, và đó là `jti`.

**Vì sao có TTL:** sau `exp` thì token đã bị chính chữ ký từ chối, nên giữ khoá
thêm là rác thuần tuý. Đặt hạn bằng đúng quãng còn lại khiến danh sách tự dọn
và không bao giờ phình quá số phiên đang sống.
"""

from datetime import UTC, datetime

import redis


def _key(token_id: str) -> str:
    return f"denylist:{token_id}"


def revoke(client: redis.Redis, token_id: str, expires_at: datetime) -> None:
    """Ghi token vào danh sách thu hồi, hết hạn cùng lúc với chính nó."""
    remaining = int((expires_at - datetime.now(UTC)).total_seconds())
    if remaining <= 0:
        # Hết hạn rồi thì chữ ký lo phần còn lại; `setex` với TTL <= 0 là lỗi.
        return
    client.setex(_key(token_id), remaining, "1")


def is_revoked(client: redis.Redis, token_id: str) -> bool:
    return bool(client.exists(_key(token_id)))
