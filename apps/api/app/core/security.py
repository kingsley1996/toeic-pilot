from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt only consumes the first 72 bytes of a password. bcrypt < 4.1 truncated
# silently; 4.1+ raises ValueError. Neither is acceptable at the API boundary, so
# the limit is enforced explicitly — see app.schemas.auth.validate_password_length.
BCRYPT_MAX_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what bcrypt can hash without truncation."""


def _encode(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes "
            f"({len(encoded)} given). Note non-ASCII characters use several bytes each."
        )
    return encoded


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(plain_password), hashed_password.encode("utf-8"))
    except (PasswordTooLongError, ValueError):
        # An over-long or structurally invalid candidate is a failed login, not a 500.
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


# Which generation of the password this token belongs to. Named rather than
# inlined because `deps.get_current_user` and both token-issuing routes have to
# agree on the spelling, and a typo would simply stop revoking anything.
PASSWORD_CLAIM = "pwc"

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def password_epoch(changed_at: datetime | None) -> int:
    """The value `PASSWORD_CLAIM` carries: when this account's password last moved.

    Zero means never, which is also what a token minted before this claim existed
    reads as — so shipping revocation does not sign out everyone already in.

    Deliberately compared for **equality**, not for "issued after". `iat` has
    one-second resolution, so a token issued in the same second as the password
    change is indistinguishable from one issued just before it: an ordering test
    either lets that token through or rejects the replacement token the change
    itself just handed back. Equality has no such window — a token either names
    the current generation of the password or it does not.

    Measured in **microseconds**, which is why this is not `int(timestamp())`.
    This is a private claim, so nothing obliges it to use the one-second
    resolution the registered time claims use, and seconds would put the same
    ambiguity back one level up: two password changes inside one second would
    produce the same generation, leaving the token the first one issued valid
    after the second.
    """
    if changed_at is None:
        return 0
    # SQLite returns naive datetimes even for `DateTime(timezone=True)`. Reading
    # one as local time would be wrong by the machine's UTC offset — correct in
    # CI, wrong on a developer's laptop.
    at = changed_at.replace(tzinfo=UTC) if changed_at.tzinfo is None else changed_at
    # Integer arithmetic rather than `timestamp() * 1_000_000`: at microsecond
    # scale the float is near the edge of what float64 represents exactly, and a
    # generation that rounds differently on two machines revokes nothing.
    elapsed = at - _EPOCH
    return (elapsed.days * 86_400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire, "iat": now}
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
