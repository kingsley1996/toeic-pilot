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
    payload = _FIELD_SEP.join((text, voice, engine, engine_version))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def storage_key_for(source_hash_value: str, ext: str = "mp3") -> str:
    """Object-store key for an asset: ``audio/ab/abcdef....mp3``.

    The two-character shard keeps a local directory listing usable once the
    library grows; it is inert on an object store, which has no directories.
    """
    if len(source_hash_value) < 2:
        raise ValueError(f"source_hash is too short to shard: {source_hash_value!r}")
    return f"{AUDIO_KEY_PREFIX}/{source_hash_value[:2]}/{source_hash_value}.{ext}"


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
