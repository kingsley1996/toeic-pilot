import logging
from datetime import UTC, datetime

import redis
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, security
from app.core.database import get_db
from app.core.rate_limit import Quota, rate_limit, rate_limit_anonymous
from app.core.redis_client import get_redis
from app.core.security import (
    PASSWORD_CLAIM,
    TOKEN_ID_CLAIM,
    create_access_token,
    decode_access_token,
    get_password_hash,
    password_epoch,
    verify_password,
)
from app.core.token_denylist import revoke
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.auth import (
    PasswordChange,
    TokenResponse,
    UserLogin,
    UserPublic,
    UserRegister,
)
from app.services.profile import ensure_profile, profile_public

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_public(db: Session, user: User) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        # Never taken from the request: a signup that can choose its own role is
        # not a role system. It only ever comes off the stored row.
        role=user.role,
        created_at=user.created_at.isoformat(),
        profile=profile_public(ensure_profile(db, user)),
    )


# Hạn mức RỘNG, và con số này được chọn bằng cách hỏi "ai bị chặn oan" trước khi
# hỏi "ai bị chặn đúng".
#
# Khoá theo IP, mà ở Việt Nam mạng di động chạy CGNAT: hàng nghìn thuê bao dùng
# chung một địa chỉ công cộng. Quán net, trường học, văn phòng cũng vậy. Đặt
# chặt thì thứ hỏng trước tiên không phải máy dò mật khẩu mà là một lớp học đăng
# ký cùng lúc — và người dùng thật bị chặn thì không ai báo lại, họ chỉ bỏ đi.
#
# Nên hãy thành thật về việc bộ này làm được gì: nó cắt một vòng dò từ điển từ
# hàng nghìn lần/phút xuống 6 lần/phút, và nó chặn script ngây thơ. Nó KHÔNG
# chặn được botnet xoay IP. Chống dò mật khẩu thật sự cần đếm theo tài khoản,
# mà đếm theo tài khoản lại mở đường khoá tài khoản người khác — xem
# `rate_limit_anonymous`. Đây là chỗ đã cân nhắc, không phải chỗ bỏ sót.
LOGIN_QUOTA = Quota(limit=60, window_seconds=60 * 10)
# Tạo tài khoản hàng loạt là cách rẻ nhất bơm rác vào database, nhưng vẫn phải
# đủ chỗ cho một lớp học đăng ký cùng lúc từ một đường mạng.
#
# 20 KHÔNG đủ chỗ cho chính cái lớp học mà dòng trên vừa nói tới, và nó chặt hơn
# cả `LOGIN_QUOTA` — trong khi ĐĂNG NHẬP mới là cửa dò mật khẩu thật, còn đăng ký
# chỉ mở đường bơm rác. Một lớp 40 học sinh cùng bấm "Tạo tài khoản" trong giờ
# học sẽ có non nửa lớp bị chặn, và như dòng trên đã viết: người dùng thật bị
# chặn thì không ai báo lại, họ chỉ bỏ đi.
#
# 60 mỗi 10 phút = 6 lần/phút cho một địa chỉ. Đủ cho một lớp cộng vài lần gõ
# lại, và vẫn là cái phanh cần thiết cho script bơm tài khoản — thứ này chưa bao
# giờ là hàng rào chống botnet xoay IP, xem đoạn trên.
#
# Con số 20 còn có một cái giá không ai định trả: bộ e2e chạy 22 bài và mỗi bài
# đăng ký một tài khoản, nên bài cuối cùng LUÔN đỏ ở `toHaveURL(/dashboard$/)` —
# một chỗ chẳng liên quan gì tới nó. Đó là triệu chứng, không phải lý do đổi:
# lý do là dòng ngay trên đã hứa một điều mà con số không giữ.
REGISTER_QUOTA = Quota(limit=60, window_seconds=60 * 10)
# Đổi mật khẩu ĐÃ đăng nhập, nhưng vẫn cần giới hạn: nó xác minh mật khẩu hiện
# tại, nên nó cũng là một cửa dò — chỉ khác là kẻ dò phải có token hợp lệ trước.
PASSWORD_QUOTA = Quota(limit=10, window_seconds=60 * 10)


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_anonymous("register", REGISTER_QUOTA))],
)
def register(body: UserRegister, db: Session = Depends(get_db)) -> UserPublic:
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=body.email.lower(), hashed_password=get_password_hash(body.password))
    db.add(user)
    # The check above is advisory: two concurrent registrations both pass it and
    # only the unique index on users.email stops the second one. Without this the
    # loser of that race gets a 500 instead of the 409 the check already decided on.
    try:
        # Flush before building the profile, because `users.id` is a column
        # default: SQLAlchemy fills it in on INSERT, not on construction, so
        # reading `user.id` any earlier hands the profile a NULL foreign key.
        # It also brings the unique-email race forward to here, which is why the
        # whole sequence sits inside the same try.
        db.flush()
        # The profile row is created in the same transaction, never lazily on
        # first read. A 1:1 table whose row might be missing means a null check
        # at every read site, and the one someone forgets is a 500 on a page
        # that worked yesterday.
        db.add(UserProfile(user_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from None
    db.refresh(user)
    return _user_public(db, user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_anonymous("login", LOGIN_QUOTA))],
)
def login(body: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    # `hashed_password is None` = tài khoản chỉ đăng nhập bằng Google/Apple.
    #
    # Trả về đúng thông báo chung như khi sai mật khẩu, KHÔNG phải "tài khoản này
    # dùng Google": câu đó xác nhận email nào có tài khoản ở đây và bằng đường
    # nào, tức là một máy dò tài khoản miễn phí. Lời nhắc đúng chỗ nằm ở trang
    # đăng nhập, nơi cả hai nút cùng hiện ra cho mọi người.
    if (
        user is None
        or user.hashed_password is None
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(
        str(user.id), extra={PASSWORD_CLAIM: password_epoch(user.password_changed_at)}
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    return _user_public(db, current_user)


@router.post(
    "/password",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("password", PASSWORD_QUOTA))],
)
def change_password(
    body: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    """Đổi mật khẩu, và cắt mọi phiên khác đang mở.

    Trả về token MỚI chứ không trả 204. Ghi `password_changed_at` làm mọi token
    phát hành trước đó hết hiệu lực — kể cả token vừa dùng để gọi chính endpoint
    này — nên nếu không đưa lại token thì người dùng đổi mật khẩu xong sẽ bị
    đăng xuất ngay tại chỗ, và trông y hệt như một lỗi.
    """
    if current_user.hashed_password is None:
        # Tài khoản chưa từng có mật khẩu (đăng nhập bằng Google/Apple). Đây
        # KHÔNG phải chỗ đặt mật khẩu lần đầu: endpoint này chứng minh quyền
        # bằng chính mật khẩu cũ, nên với tài khoản không có mật khẩu thì nó
        # không chứng minh được gì cả. Một đường "đặt mật khẩu lần đầu" cần bằng
        # chứng khác (email xác minh), và đó là tính năng riêng.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản này đăng nhập bằng Google hoặc Apple nên chưa có mật khẩu.",
        )
    if not verify_password(body.current_password, current_user.hashed_password):
        # Cố ý không nói rõ sai ở đâu, và cố ý KHÔNG dùng 401: token vẫn hợp lệ,
        # thứ bị từ chối là hành động. Trả 401 ở đây sẽ khiến tầng frontend hiểu
        # nhầm là hết phiên và đá người dùng ra trang đăng nhập.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mật khẩu hiện tại không đúng",
        )

    current_user.hashed_password = get_password_hash(body.new_password)
    current_user.password_changed_at = datetime.now(UTC)
    db.commit()
    db.refresh(current_user)

    # Phát hành token mang thế hệ mật khẩu MỚI. Mọi token cũ vẫn mang thế hệ cũ
    # nên từ giờ không khớp nữa — kể cả token vừa dùng để gọi chính request này.
    return TokenResponse(
        access_token=create_access_token(
            str(current_user.id),
            extra={PASSWORD_CLAIM: password_epoch(current_user.password_changed_at)},
        )
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    # Phụ thuộc này là thứ bắt buộc phải có token hợp lệ; giá trị trả về không
    # dùng tới. Không có nó thì bất kỳ ai cũng gọi được endpoint với một `jti`
    # tự bịa và ghi rác vào Redis.
    _: User = Depends(get_current_user),
    client: redis.Redis = Depends(get_redis),
) -> Response:
    """Thu hồi đúng token đang dùng để gọi request này.

    Chỉ phiên này, không phải mọi phiên: đăng xuất ở máy thư viện mà rớt luôn
    phiên trên điện thoại là một sản phẩm khác. Cắt tất cả là việc của
    `/auth/password`.

    **Luôn trả 204, kể cả khi Redis hỏng.** Trả 503 sẽ khiến giao diện giữ người
    dùng ở lại đúng cái trạng thái họ vừa bảo là muốn thoát ra. Client xoá token
    của mình dù thế nào; danh sách thu hồi là lớp phòng thủ thứ hai, cho những
    bản sao của token mà trình duyệt này không xoá được.
    """
    payload = decode_access_token(credentials.credentials) if credentials else None
    token_id = (payload or {}).get(TOKEN_ID_CLAIM)
    expires_at = (payload or {}).get("exp")
    if token_id is not None and expires_at is not None:
        try:
            revoke(client, str(token_id), datetime.fromtimestamp(float(expires_at), UTC))
        except redis.RedisError:
            logger.warning("token_denylist_unavailable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
