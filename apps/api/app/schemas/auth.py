from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.security import BCRYPT_MAX_BYTES


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


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    created_at: str
