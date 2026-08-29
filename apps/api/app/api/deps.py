import logging
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

import redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.redis_client import get_redis
from app.core.security import (
    PASSWORD_CLAIM,
    TOKEN_ID_CLAIM,
    decode_access_token,
    password_epoch,
)
from app.core.token_denylist import is_revoked
from app.models.user import User

if TYPE_CHECKING:
    from app.services.llm.gateway import Gateway

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


def get_gateway(db: Session) -> "Gateway":
    """Dựng gateway cho một request — chỗ duy nhất, mọi router AI cùng dùng.

    Tập tên nhà cung cấp cần từ HAI nguồn: hai route mặc định trong settings,
    và mọi nhà cung cấp mà một hàng cấu hình tính năng đang trỏ tới — `admin_ai`
    chỉ buộc chọn model CÓ GIÁ, nên một hàng có thể trỏ tới Google hay Groq
    trong khi route mặc định nói ollama. Thiếu khoá của nhà cung cấp nào thì
    nhà cung cấp đó bị bỏ qua (`strict=False`): tính năng A trỏ sai không được
    phép kéo sập tính năng B. Lượt gọi thật tới provider thiếu sẽ nhận 503 có
    ghi sổ, thay vì KeyError 500 không dấu vết.
    """
    from app.core.ai_budget import Budget
    from app.core.config import settings
    from app.models.ai_config import AiFeatureConfig
    from app.services.ai_features import resolver_for
    from app.services.llm.gateway import Gateway
    from app.services.llm.providers import build_providers
    from app.services.llm.router import Tier

    routes = {
        Tier.CHEAP: _split(settings.llm_tier_cheap),
        Tier.STRONG: _split(settings.llm_tier_strong),
    }
    names = {provider for provider, _ in routes.values()}
    names.update(db.scalars(select(AiFeatureConfig.provider)).all())

    return Gateway(
        providers=build_providers(names, strict=False),
        routes=routes,
        budget=Budget(limit_micro=settings.ai_daily_budget_micro_usd),
        redis_client=get_redis(),
        session_factory=SessionLocal,
        resolve_feature=resolver_for(db),
    )


def _split(value: str) -> tuple[str, str]:
    provider, _, model = value.partition("/")
    return provider, model
