"""Content-addressed naming for audio assets.

Pure stdlib on purpose. Both the runtime API and the offline content pipeline
(`app.content`, which lives behind the optional `content` extra) need these
helpers, so they sit in `core` where either side can import them without
dragging in a dependency the other does not have.

See `planning/PHASE2-AUDIO.md` A4.2 and A4.3 for why the hash is built the way
it is; both invariants are easy to break and neither breaks loudly.
"""

import hashlib
from pathlib import Path

# Unit separator. A printable delimiter such as "|" would let a source text
# containing that character collide with a different (text, voice) pair;
# \x1f cannot appear in the transcripts we feed to TTS.
_FIELD_SEP = "\x1f"

AUDIO_KEY_PREFIX = "audio"
IMAGE_KEY_PREFIX = "image"
# Tiền tố riêng cho avatar: media người dùng và media nội dung nằm hai nhánh
# khác nhau ngay ở đường dẫn, nên một lệnh dọn nhắm vào nhánh này không thể vô
# tình chạm vào nhánh kia.
AVATAR_KEY_PREFIX = "avatar"

# Kept as plain tuples rather than a native PostgreSQL enum: adding a value to a
# native enum needs its own migration, and Alembic downgrades across enum types
# are painful enough that a CHECK constraint is the cheaper trade.
AUDIO_SOURCES = ("tts", "scraped", "uploaded")

# BCP-47 tags for the four accents TOEIC listening requires. Free text here would
# make "en-us", "US" and "American" all look like distinct accents to a query.
AUDIO_ACCENTS = ("en-US", "en-GB", "en-AU", "en-CA")

# media.py -> core -> app -> apps/api
_API_DIR = Path(__file__).resolve().parents[2]

# Where generated audio lands on disk. Defined here rather than in either
# settings object because two of them need it — the API (to serve /media in
# development) and the offline pipeline (to write into) — and they must not
# be free to disagree. Each may still override it from the environment.
DEFAULT_MEDIA_ROOT = _API_DIR / "media"


def _digest(*fields: str) -> str:
    return hashlib.sha256(_FIELD_SEP.join(fields).encode("utf-8")).hexdigest()


def source_hash(text: str, voice: str, engine: str, engine_version: str) -> str:
    """Fingerprint the INPUT to a synthesis, never the resulting bytes.

    TTS is not byte-deterministic: synthesising the same sentence twice yields
    two different mp3s. Hashing the output would therefore hand back a new hash
    on every run, turning "skip what already exists" into "insert a duplicate".
    Hashing the input is what makes the pipeline resumable and `seed` idempotent.

    `voice` must be a logical voice (``us_female_1``), not a provider voice id
    (``en-US-JennyNeural``). Provider ids in the hash would invalidate every
    existing asset the day the engine changes — see A4.3.
    """
    return _digest(text, voice, engine, engine_version)


def image_source_hash(source_url: str, transform_version: str) -> str:
    """Fingerprint a sourced image by where it came from and how it is processed.

    Hashing the downloaded bytes would be defensible — unlike TTS, a download is
    reproducible — but we never store those bytes. The pipeline resizes and
    re-encodes first, and Pillow makes no promise that two versions produce
    identical output. Hashing the result would therefore invalidate the whole
    library on a routine dependency bump, exactly the failure A4.2 avoids for
    audio.

    `transform_version` is the deliberate manual knob, the counterpart of
    `tts_engine_version`: bump it when you actually want everything re-fetched.
    """
    return _digest(source_url, transform_version, "image")


def storage_key_for(
    source_hash_value: str, ext: str = "mp3", prefix: str = AUDIO_KEY_PREFIX
) -> str:
    """Object-store key for an asset: ``audio/ab/abcdef....mp3``.

    The two-character shard keeps a local directory listing usable once the
    library grows; it is inert on an object store, which has no directories.
    """
    if len(source_hash_value) < 2:
        raise ValueError(f"source_hash is too short to shard: {source_hash_value!r}")
    return f"{prefix}/{source_hash_value[:2]}/{source_hash_value}.{ext}"


def image_storage_key_for(source_hash_value: str, ext: str = "jpg") -> str:
    return storage_key_for(source_hash_value, ext=ext, prefix=IMAGE_KEY_PREFIX)


def avatar_storage_key_for(source_hash_value: str, ext: str = "jpg") -> str:
    return storage_key_for(source_hash_value, ext=ext, prefix=AVATAR_KEY_PREFIX)


def public_audio_url(storage_key: str, base_url: str | None = None) -> str:
    """Join the public base URL and a storage key into a playable URL.

    Serving is a string join and nothing more: the runtime never calls the
    object store to produce a URL (A2.4). `base_url` defaults to
    `settings.audio_public_base_url`; it is a parameter so the content pipeline
    and tests can point elsewhere without mutating global settings.
    """
    if base_url is None:
        # Imported lazily: settings reads .env at import time, and this module is
        # also used by offline tooling that should not need a configured app.
        from app.core.config import settings

        base_url = settings.audio_public_base_url
    return f"{base_url.rstrip('/')}/{storage_key.lstrip('/')}"


def upload_source_hash(upload_id: str, transform_version: str = "1") -> str:
    """Danh tính của một lần upload — **không** phải địa chỉ nội dung.

    Mọi `source_hash` khác trong hệ băm *đầu vào sinh ra file*: text + giọng cho
    audio, URL nguồn + phiên bản biến đổi cho ảnh lấy về. Nhờ vậy sinh lại cho
    ra đúng khoá cũ, và `media_state` phát hiện được clip đã lệch khỏi text.

    File do người tải lên không có đầu vào nào như thế. Nó không tái tạo được —
    đó chính là lý do phải upload — nên ở đây `source_hash` chỉ còn giữ vai trò
    khoá duy nhất, và nó băm một id ngẫu nhiên do phía ta sinh ra.
    """
    return _digest("upload", upload_id, transform_version)
