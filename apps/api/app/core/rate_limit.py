"""Giới hạn tần suất cho những endpoint mà mỗi request đều tốn tiền.

P1-8 trong `REVIEW-OPUS.md`. `ROADMAP.md` viết lập luận này cho tầng LLM và nó
đúng nguyên vẹn cho upload: một endpoint ký-upload không đo đếm vừa là hoá đơn
không giới hạn, vừa là dịch vụ hosting file miễn phí cho bất kỳ ai đọc được mã
nguồn trình duyệt.

Cửa sổ cố định, không phải cửa sổ trượt. Cửa sổ trượt chính xác hơn nhưng cần
một sorted set và một lần dọn mỗi request; cửa sổ cố định là `INCR` + `EXPIRE`,
và sai số tệ nhất của nó — gấp đôi hạn mức quanh ranh giới cửa sổ — không đáng
để đánh đổi ở đây. Chúng ta đang chặn lạm dụng, không đang tính cước.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import redis
from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.redis_client import get_redis
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Quota:
    """Bao nhiêu lần, trong bao nhiêu giây."""

    limit: int
    window_seconds: int


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


def hit(client: redis.Redis, key: str, quota: Quota) -> int:
    """Đếm một lượt và trả về số lượt đã dùng trong cửa sổ hiện tại.

    `INCR` rồi mới `EXPIRE`, và chỉ đặt hạn khi đếm được 1 — đặt lại hạn ở mỗi
    lượt sẽ biến cửa sổ cố định thành cửa sổ trượt-về-phía-trước vô hạn, tức là
    một người gọi liên tục sẽ không bao giờ được reset.
    """
    used = int(client.incr(key))
    if used == 1:
        client.expire(key, quota.window_seconds)
    return used


def check(client: redis.Redis, key: str, quota: Quota) -> None:
    used = hit(client, key, quota)
    if used > quota.limit:
        ttl = int(client.ttl(key))
        raise RateLimitExceeded(retry_after=max(ttl, 1))


def client_ip(request: Request) -> str:
    """IP của client, dùng làm khoá cho endpoint chưa đăng nhập.

    `request.client.host` là **hop gần nhất**. Sau một reverse proxy đó là IP
    của proxy, nên mọi người dùng sẽ chung một khoá và giới hạn biến thành giới
    hạn toàn hệ thống.

    Lấy phần tử **cuối cùng** của `X-Forwarded-For`, không phải phần tử đầu.
    Client tự thêm được bao nhiêu mục tuỳ thích vào đầu chuỗi; mục cuối là thứ
    proxy của chính ta ghi vào, và đó là địa chỉ duy nhất trong chuỗi mà client
    không giả được. Đọc mục đầu — cách mọi ví dụ trên mạng viết — là để lộ
    nguyên cái khoá cho kẻ tấn công tự đặt.
    """
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def rate_limit_anonymous(bucket: str, quota: Quota) -> Callable[[Request, redis.Redis], None]:
    """Giới hạn theo IP cho endpoint KHÔNG yêu cầu đăng nhập.

    `rate_limit` khoá theo `user.id` và vì thế không dùng được ở đây: `/login`
    tồn tại chính là để chưa có người dùng nào. Không có bộ này thì số lần đoán
    mật khẩu là vô hạn, và đó là lỗ P1-8 thật sự — phần upload đã được che từ
    trước.

    Khoá theo IP có cái giá đã ghi ở `rate_limit`: một văn phòng dùng chung một
    IP sẽ dùng chung hạn mức. Nên hạn mức ở đây phải rộng rãi — đủ cho vài người
    gõ nhầm mật khẩu, chật với một máy dò.

    **KHÔNG khoá thêm theo email.** Nó chặn được kẻ tấn công phân tán qua nhiều
    IP, nhưng mở ra một đường khoá tài khoản người khác: đốt hạn mức của một
    email là chủ nhân của nó không đăng nhập được. Đổi một lỗ khó khai thác lấy
    một lỗ dễ khai thác thì không đáng.

    **`fail_open=True`**, ngược với `rate_limit`. Ở đó Redis là thứ duy nhất
    đứng giữa một tài khoản và hoá đơn, nên chặn khi hỏng là đúng. Ở đây chặn
    khi hỏng nghĩa là **không ai đăng nhập được** — một phụ thuộc mềm kéo sập
    toàn bộ sản phẩm. Redis chết thì mở cửa sổ dò mật khẩu trong lúc đó, và đó
    là cái giá nhỏ hơn.
    """

    def dependency(
        request: Request,
        client: redis.Redis = Depends(get_redis),
    ) -> None:
        key = f"ratelimit:{bucket}:{client_ip(request)}"
        try:
            check(client, key, quota)
        except RateLimitExceeded as exceeded:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quá nhiều lần thử. Thử lại sau ít phút.",
                headers={"Retry-After": str(exceeded.retry_after)},
            ) from None
        except redis.RedisError:
            logger.warning("rate_limit_unavailable", extra={"bucket": bucket})

    return dependency


def rate_limit(bucket: str, quota: Quota, fail_open: bool = False) -> Callable[..., None]:
    """Dependency giới hạn theo NGƯỜI DÙNG đã đăng nhập.

    Khoá theo `user.id` chứ không theo IP: IP dùng chung ở văn phòng và ở mạng
    di động, nên chặn theo IP sẽ chặn nhầm cả một toà nhà vì một người. Mọi
    endpoint dùng bộ này đều đã yêu cầu đăng nhập, nên luôn có id để khoá.

    `fail_open=False` là mặc định và là lựa chọn có cân nhắc. Ở khắp nơi khác
    Redis là phụ thuộc mềm — `/ready` báo `degraded` chứ không sập. Nhưng ở đây
    Redis chính là **thứ duy nhất** đứng giữa một tài khoản và hoá đơn của bạn:
    cho qua khi Redis hỏng nghĩa là ai hạ được Redis thì có upload không giới
    hạn. Chặn khi hỏng làm mất tính năng một lúc; cho qua khi hỏng làm mất tiền.
    """

    def dependency(
        current_user: User = Depends(get_current_user),
        # Tiêm qua `Depends` chứ không gọi `get_redis()` thẳng trong thân hàm.
        # Không phải để cho đẹp: đó là thứ cho phép test ghi đè Redis đúng như
        # đã ghi đè `get_db`. Gọi thẳng thì mọi test chạm endpoint có giới hạn
        # đều nhận 503, vì bộ test không dựng Redis — và cách sửa nhanh khi đó
        # sẽ là cho `fail_open=True`, tức là tắt luôn thứ đang được test.
        client: redis.Redis = Depends(get_redis),
    ) -> None:
        key = f"ratelimit:{bucket}:{current_user.id}"
        try:
            check(client, key, quota)
        except RateLimitExceeded as exceeded:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Bạn thao tác quá nhanh. Thử lại sau ít phút.",
                headers={"Retry-After": str(exceeded.retry_after)},
            ) from None
        except redis.RedisError:
            if fail_open:
                return
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tạm thời không nhận thao tác này. Thử lại sau ít phút.",
            ) from None

    return dependency
