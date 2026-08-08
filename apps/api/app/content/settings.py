"""Configuration for the offline content pipeline.

Deliberately a separate settings object from `app.core.config`. The pipeline is
the only thing that ever *writes* to the object store, so its credentials have no
business sitting in the environment of a process that serves HTTP. Keeping the
two apart means a leak in the API cannot hand an attacker write access to the
audio bucket.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.content.manifest import DEFAULT_MANIFEST_PATH
from app.core.media import DEFAULT_MEDIA_ROOT

# settings.py -> content -> app -> apps/api
_API_DIR = Path(__file__).resolve().parents[2]


class ContentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_API_DIR.parents[1] / ".env", _API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    object_store_dir: Path = DEFAULT_MEDIA_ROOT
    manifest_path: Path = DEFAULT_MANIFEST_PATH

    # A deliberate manual knob, NOT the installed edge-tts version. It feeds the
    # source hash, so deriving it from the package would mean every routine
    # dependency bump invalidated the entire audio library and forced a full
    # regeneration. Bump this only when you actually want everything re-synthesised.
    tts_engine_version: str = "1"

    tts_max_attempts: int = 4
    tts_backoff_seconds: float = 2.0

    # Reserved for the Cloudflare R2 migration (PHASE2-AUDIO A5). Unset until
    # there is a domain on Cloudflare DNS; the API runtime never reads these.
    r2_account_id: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None


content_settings = ContentSettings()
