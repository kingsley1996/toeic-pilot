from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.security import BCRYPT_MAX_BYTES
from app.schemas.profile import UserProfilePublic


def _within_bcrypt_limit(value: str) -> str:
    # Enforced here so an over-long password is a 422 with a clear message rather
    # than a 500 from bcrypt (or, worse, a silent truncation that would let a
    # shorter prefix of the password authenticate later).
    encoded = len(value.encode("utf-8"))
    if encoded > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes; got {encoded}. "
            "Accented and non-Latin characters use more than one byte each."
        )
    return value


Password = Annotated[str, Field(min_length=8), AfterValidator(_within_bcrypt_limit)]


class UserRegister(BaseModel):
    email: EmailStr
    password: Password


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    # The current password is required even though the caller is already
    # authenticated. A valid token proves this browser was signed in at some
    # point, not that whoever is holding it now knows the password — and that
    # gap is the entire case this endpoint exists to close.
    current_password: str
    new_password: Password


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    # Exposed so the frontend can decide what to render rather than discovering
    # a 403 after the fact. It is a display hint only: every admin endpoint
    # enforces the role server-side through `require_role`.
    role: str
    created_at: str
    # Embedded rather than left to a second request. `SessionProvider` resolves
    # the signed-in user exactly once for the whole app, and the header needs a
    # name to render on that first paint — a separate /profile fetch would put a
    # second loading state inside the one place the app has already decided to
    # have only one.
    profile: UserProfilePublic


class AuthProviderPublic(BaseModel):
    """Một nhà cung cấp đang bật.

    Giao diện chỉ hiện nút của thứ có trong danh sách này. Không có nó thì nút
    phải hiện theo phỏng đoán, và một nút bấm vào ra 404 tệ hơn hẳn không có nút.
    """

    id: str
    label: str


class TurnstilePublic(BaseModel):
    """Site key của Turnstile, để giao diện dựng ô kiểm.

    Khoá này CÔNG KHAI theo thiết kế — nó nằm trong HTML của mọi trang có ô kiểm.
    Máy chủ phát nó ra thay vì để giao diện tự đọc biến môi trường của mình, vì
    chỉ khi ấy mới có đúng một nguồn sự thật: hai bên đọc hai biến khác nhau thì
    sẽ có ngày trang vẽ ô kiểm mà máy chủ không kiểm, và không gì báo cả.
    """

    site_key: str
