from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    PASSWORD_CLAIM,
    create_access_token,
    get_password_hash,
    password_epoch,
    verify_password,
)
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


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
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


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.hashed_password):
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


@router.post("/password", response_model=TokenResponse)
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
