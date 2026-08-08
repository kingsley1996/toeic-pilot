from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> core -> app -> apps/api -> apps -> <repo root>
_API_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _API_DIR.parents[1]

# `env_file` is resolved relative to the process CWD, so a bare ".env" is only
# found when uvicorn is launched from the repo root. The documented dev flow runs
# from apps/api, which would silently fall back to the defaults below — including
# the placeholder secret key. Pass absolute paths instead; later entries win, so a
# per-app .env can override the shared one. Real env vars still outrank both,
# which is how the Docker Compose `env_file:` values reach the app.
DEFAULT_SECRET_KEY = "dev-secret-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://toeic:toeic@localhost:5432/toeic"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    log_format: str = "json"  # "json" for shipping, "text" for local reading

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> "Settings":
        if self.is_production and self.secret_key == DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a unique value when ENVIRONMENT=production. "
                "Generate one with: openssl rand -hex 32"
            )
        return self


settings = Settings()
