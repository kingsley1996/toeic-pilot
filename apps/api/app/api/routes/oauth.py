"""Đăng nhập bằng Google và Apple.

Ba đường: liệt kê nhà cung cấp đang bật, bắt đầu luồng, và nhận callback. Quyết
định và lý do nằm ở `app/services/oauth.py`; ở đây chỉ là HTTP.

**Callback trả token qua FRAGMENT của URL, không qua query.** Query đi vào log
máy chủ, vào header `Referer` của mọi ảnh và script trên trang đích, và vào lịch
sử trình duyệt ở dạng đọc được. Fragment thì không rời khỏi trình duyệt. Đây là
cách ít tệ nhất khi token còn nằm trong `localStorage` (P1-7b); ngày chuyển sang
cookie httpOnly thì cả đoạn này biến mất.
"""

import logging

import redis
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import Quota, rate_limit_anonymous
from app.core.redis_client import get_redis
from app.core.security import PASSWORD_CLAIM, create_access_token, password_epoch
from app.models.identity import UserIdentity
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.auth import AuthProviderPublic
from app.services import oauth
from app.services.oauth import OAuthError, Provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Cùng hình dạng với hạn mức của `/login`: theo IP, vì ở đây cũng chưa có ai để
# tính theo tài khoản. Rộng hơn một chút vì một lần đăng nhập hỏng giữa chừng
# (bấm huỷ ở màn Google) là chuyện rất bình thường và người ta bấm lại ngay.
START_QUOTA = Quota(limit=20, window_seconds=300)


def _provider_or_404(provider_id: str) -> Provider:
    """Nhà cung cấp chưa cấu hình thì 404, KHÔNG phải 503.

    404 nói đúng sự thật với người gọi: đường này không tồn tại ở bản triển khai
    này. 503 ngụ ý "có nhưng đang hỏng", và nó mời người ta thử lại một thứ sẽ
    không bao giờ chạy cho tới khi ai đó điền khoá vào `.env`.
    """
    provider = oauth.PROVIDERS.get(provider_id)
    if provider is None or not oauth.is_configured(provider):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not available")
    return provider


@router.get("/providers", response_model=list[AuthProviderPublic])
def list_providers() -> list[AuthProviderPublic]:
    """Nhà cung cấp đang BẬT — trả mảng trần, không phân trang.

    Đây là bucket (A) của `app/schemas/common.py`: bị chặn bởi miền, tối đa vài
    phần tử. Giao diện dùng nó để chỉ hiện nút của thứ thật sự bấm được.
    """
    return [AuthProviderPublic(id=p.id, label=p.label) for p in oauth.enabled_providers()]


@router.get(
    "/{provider_id}/start",
    dependencies=[Depends(rate_limit_anonymous("oauth-start", START_QUOTA))],
)
def start(
    provider_id: str,
    next: str = "/dashboard",
    redis_client: redis.Redis = Depends(get_redis),
) -> RedirectResponse:
    """Chuyển hướng sang nhà cung cấp.

    `next` chỉ nhận đường dẫn nội bộ. Nhận URL tuyệt đối ở đây là dựng sẵn một
    open redirect: kẻ tấn công gửi link `/auth/google/start?next=https://…` và
    trang lừa đảo hiện ra sau một lần đăng nhập THẬT, tức là sau khi người dùng
    vừa được xác nhận rằng mọi thứ bình thường.
    """
    provider = _provider_or_404(provider_id)
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/dashboard"
    try:
        state, nonce = oauth.start_flow(redis_client, provider, safe_next)
    except OAuthError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from None
    return RedirectResponse(oauth.authorize_url(provider, state, nonce), status_code=307)


def _failure(message: str) -> RedirectResponse:
    """Về trang đăng nhập kèm lý do, không phải một trang lỗi JSON.

    Người dùng đang ở giữa một luồng trình duyệt; ném JSON vào mặt họ là bỏ họ ở
    một ngõ cụt không có nút nào bấm được.
    """
    from urllib.parse import quote

    base = settings.web_base_url.rstrip("/")
    return RedirectResponse(f"{base}/login?oauth_error={quote(message)}", status_code=303)


def _resolve_user(db: Session, provider: Provider, identity: oauth.Identity) -> User:
    """Tìm tài khoản của danh tính này, liên kết, hoặc tạo mới.

    Thứ tự ba nhánh là phần bảo mật của hàm: tra theo `(provider, subject)`
    TRƯỚC, vì đó là thứ duy nhất bền và không giả được. Chỉ khi chưa có mới xét
    tới email, và khi đó luật ở `may_link_by_email` mới có tiếng nói.
    """
    existing = (
        db.query(UserIdentity)
        .filter(UserIdentity.provider == provider.id, UserIdentity.subject == identity.subject)
        .one_or_none()
    )
    if existing is not None:
        user = db.get(User, existing.user_id)
        if user is not None:
            return user

    if oauth.may_link_by_email(identity):
        match = db.query(User).filter(User.email == identity.email).one_or_none()
        if match is not None:
            db.add(
                UserIdentity(
                    user_id=match.id,
                    provider=provider.id,
                    subject=identity.subject,
                    email=identity.email,
                )
            )
            return match

    email = (
        identity.email if identity.email else oauth.deterministic_email(provider, identity.subject)
    )
    if db.query(User).filter(User.email == email).one_or_none() is not None:
        # Email trùng nhưng KHÔNG đủ điều kiện liên kết (chưa xác minh, hoặc là
        # địa chỉ ẩn). Từ chối kèm lối ra thay vì lặng lẽ gắn vào tài khoản kia:
        # gắn bừa ở đây đúng là kịch bản chiếm tài khoản mà luật liên kết tồn tại
        # để chặn.
        raise OAuthError(
            "Email này đã có tài khoản. Đăng nhập bằng mật khẩu, rồi liên kết trong trang hồ sơ."
        )

    user = User(email=email, hashed_password=None)
    db.add(user)
    db.flush()
    # Hồ sơ tạo NGAY, không tạo lười — cùng luật với đăng ký bằng mật khẩu: một
    # bảng 1:1 mà hàng có thể vắng mặt nghĩa là mọi chỗ đọc phải kiểm null, và
    # chỗ ai đó quên kiểm là một lỗi 500 trên trang hôm qua vẫn chạy.
    db.add(UserProfile(user_id=user.id, display_name=identity.display_name))
    db.add(
        UserIdentity(
            user_id=user.id,
            provider=provider.id,
            subject=identity.subject,
            email=identity.email,
        )
    )
    return user


def _complete(
    db: Session, provider: Provider, code: str, state: str, redis_client: redis.Redis
) -> RedirectResponse:
    flow = oauth.take_flow(redis_client, state)
    if flow.provider != provider.id:
        # State sinh cho nhà cung cấp này nhưng quay về ở đường của nhà cung cấp
        # kia. Không thể xảy ra trong luồng bình thường, nên nó là dấu hiệu có
        # người đang ghép mảnh của hai luồng lại với nhau.
        raise OAuthError("Phiên đăng nhập không khớp. Thử lại.")

    identity = oauth.verify_id_token(provider, oauth.exchange_code(provider, code), flow.nonce)
    user = _resolve_user(db, provider, identity)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        str(user.id), extra={PASSWORD_CLAIM: password_epoch(user.password_changed_at)}
    )
    base = settings.web_base_url.rstrip("/")
    # Fragment, không phải query — xem chú thích đầu tệp.
    return RedirectResponse(
        f"{base}/auth/callback#token={token}&next={flow.next_path}", status_code=303
    )


@router.get("/{provider_id}/callback")
def callback_get(
    provider_id: str,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> RedirectResponse:
    """Google quay về bằng GET."""
    provider = _provider_or_404(provider_id)
    if error:
        # Người dùng bấm "Huỷ" ở màn của Google. Đây không phải lỗi hệ thống, và
        # không được ghi log như lỗi.
        return _failure("Bạn đã huỷ đăng nhập.")
    try:
        return _complete(db, provider, code, state, redis_client)
    except OAuthError as failure:
        logger.warning("oauth_failed", extra={"provider": provider.id, "reason": str(failure)})
        return _failure(str(failure))


@router.post("/{provider_id}/callback")
def callback_post(
    provider_id: str,
    code: str = Form(default=""),
    state: str = Form(default=""),
    error: str = Form(default=""),
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> RedirectResponse:
    """Apple quay về bằng POST form (`response_mode=form_post`).

    Hai đường riêng chứ không một đường nhận cả hai: FastAPI đọc tham số từ query
    hay từ form là do KIỂU khai báo quyết định, nên gộp lại sẽ thành một hàm mà
    mỗi tham số phải thử hai chỗ — và chỗ nó đọc nhầm thì im lặng ra chuỗi rỗng.
    """
    provider = _provider_or_404(provider_id)
    if error:
        return _failure("Bạn đã huỷ đăng nhập.")
    try:
        return _complete(db, provider, code, state, redis_client)
    except OAuthError as failure:
        logger.warning("oauth_failed", extra={"provider": provider.id, "reason": str(failure)})
        return _failure(str(failure))
