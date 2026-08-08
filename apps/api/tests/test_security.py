import bcrypt
import pytest

from app.core.security import (
    BCRYPT_MAX_BYTES,
    PasswordTooLongError,
    get_password_hash,
    verify_password,
)

# Produced by passlib 1.7.4 + bcrypt 4.0.1 (the pre-P1-1 stack) for
# "legacy-passlib-password". Guards the migration: any change that stops this
# verifying would silently lock out every account created before the swap.
LEGACY_PASSLIB_HASH = "$2b$12$mwuPm0m7M5WSO9mthFOBweAWwfvg9.EeG3nmJpPXzkSEUUrmhC8F."
LEGACY_PASSWORD = "legacy-passlib-password"


def test_legacy_passlib_hash_still_verifies():
    assert verify_password(LEGACY_PASSWORD, LEGACY_PASSLIB_HASH)


def test_legacy_passlib_hash_rejects_wrong_password():
    assert not verify_password("wrong-password", LEGACY_PASSLIB_HASH)


def test_hash_roundtrip():
    hashed = get_password_hash("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("correct-horse-batteru", hashed)


def test_hash_uses_modern_bcrypt_prefix():
    assert get_password_hash("correct-horse-battery").startswith("$2b$")


def test_salt_is_random():
    a = get_password_hash("correct-horse-battery")
    b = get_password_hash("correct-horse-battery")
    assert a != b


def test_password_at_the_byte_limit_is_accepted():
    at_limit = "a" * BCRYPT_MAX_BYTES
    assert verify_password(at_limit, get_password_hash(at_limit))


def test_password_over_the_byte_limit_is_rejected_loudly():
    # bcrypt 4.0.x truncated this silently, which meant only the first 72 bytes
    # ever authenticated. Refuse instead of quietly weakening the password.
    with pytest.raises(PasswordTooLongError):
        get_password_hash("a" * (BCRYPT_MAX_BYTES + 1))


def test_multibyte_password_is_measured_in_bytes_not_characters():
    # 40 characters, 120 bytes in UTF-8.
    vietnamese = "đ" * 40
    assert len(vietnamese) < BCRYPT_MAX_BYTES
    assert len(vietnamese.encode("utf-8")) > BCRYPT_MAX_BYTES
    with pytest.raises(PasswordTooLongError):
        get_password_hash(vietnamese)


def test_verify_with_over_long_candidate_returns_false_not_raise():
    hashed = get_password_hash("correct-horse-battery")
    assert verify_password("a" * 500, hashed) is False


def test_verify_with_malformed_hash_returns_false_not_raise():
    assert verify_password("correct-horse-battery", "not-a-bcrypt-hash") is False


def test_no_silent_truncation_between_two_long_passwords():
    """Two passwords sharing a 72-byte prefix must not be interchangeable."""
    base = "a" * BCRYPT_MAX_BYTES
    hashed = get_password_hash(base)
    # Under the old silent-truncation behaviour this returned True.
    assert verify_password(base + "DIFFERENT-SUFFIX", hashed) is False


def test_bcrypt_is_the_only_hashing_dependency():
    import importlib.util

    assert importlib.util.find_spec("passlib") is None, "passlib should be gone"
    assert bcrypt.__version__ >= "4.2"
