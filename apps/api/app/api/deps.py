import logging
import uuid
from collections.abc import Callable

import redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import (
    PASSWORD_CLAIM,
    TOKEN_ID_CLAIM,
    decode_access_token,
    password_epoch,
)
from app.core.token_denylist import is_revoked
from app.models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    # Tiêm qua `Depends` chứ không gọi `get_redis()` trong thân hàm — đó là thứ
    # cho phép bộ test ghi đè Redis y như đã ghi đè `get_db`.
    redis_client: redis.Redis = Depends(get_redis),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Token đã bị thu hồi (người dùng bấm Đăng xuất) thì dừng ngay tại đây, TRƯỚC
    # lượt truy vấn database: một token vô hiệu không đáng một vòng tới Postgres.
    #
    # **Cho qua khi Redis hỏng**, giống `rate_limit_anonymous` và ngược với
    # `rate_limit`. Chặn khi hỏng ở đây nghĩa là Redis chết kéo theo *không ai*
    # dùng được sản phẩm — một phụ thuộc mềm biến thành phụ thuộc cứng ở đúng
    # đường đi nóng nhất. Cái giá của việc cho qua là những token đã thu hồi
    # sống lại trong lúc Redis hỏng, và đó là cái giá nhỏ hơn hẳn.
    #
    # Token **không có `jti`** được cho qua như token chưa từng bị thu hồi: đó
    # là token phát trước bản này, và cách xử lý giống hệt lý do "không có `pwc`
    # thì đọc là thế hệ 0" — để bản này lên được mà không đá văng mọi phiên đang
    # đăng nhập.
    token_id = payload.get(TOKEN_ID_CLAIM)
    if token_id is not None:
        try:
            if is_revoked(redis_client, str(token_id)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except redis.RedisError:
            logger.warning("token_denylist_unavailable")

    # `sub` is attacker-controllable text. Comparing it straight against a UUID
    # column makes Postgres raise DataError (HTTP 500) for anything unparseable;
    # a malformed subject is an authentication failure, not a server fault.
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Equality, not recency: see `password_epoch` for why an "issued after" test
    # cannot be made correct at one-second resolution.
    if payload.get(PASSWORD_CLAIM, 0) != password_epoch(user.password_changed_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issued before the password was changed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed: str) -> Callable[[User], User]:
    """Gate an endpoint on the caller's role.

    A dependency rather than a check inside the handler, and deliberately so: a
    check in the body is one someone forgets to copy when they add the next
    route, and the failure mode is an admin endpoint quietly open to every
    signed-up learner. As a dependency it is visible in the signature and in the
    generated OpenAPI.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these roles: {', '.join(allowed)}",
            )
        return current_user

    return dependency
