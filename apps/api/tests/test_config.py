from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET_KEY, Settings

STRONG_KEY = "9f2c" * 16


def _settings(**overrides) -> Settings:
    # _env_file=None keeps the developer's real .env out of these assertions.
    return Settings(_env_file=None, **overrides)


# --- P0-3: .env discovery must not depend on the process CWD ---------------


def test_env_file_paths_are_absolute():
    env_files = Settings.model_config["env_file"]
    assert all(Path(p).is_absolute() for p in env_files), env_files


def test_env_file_includes_repo_root_and_api_dir():
    env_files = [Path(p) for p in Settings.model_config["env_file"]]
    names = {p.parent.name for p in env_files}
    assert all(p.name == ".env" for p in env_files)
    # Repo root holds the shared .env; apps/api may hold a local override.
    assert "api" in names
    repo_root = Path(__file__).resolve().parents[3]
    assert repo_root / ".env" in env_files


# --- P0-4: production must refuse the placeholder secret -------------------


def test_production_with_default_secret_is_rejected():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(environment="production", secret_key=DEFAULT_SECRET_KEY)


@pytest.mark.parametrize("env_name", ["production", "PRODUCTION", "prod"])
def test_production_aliases_are_all_guarded(env_name: str):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(environment=env_name, secret_key=DEFAULT_SECRET_KEY)


def test_production_with_strong_secret_is_accepted():
    settings = _settings(environment="production", secret_key=STRONG_KEY)
    assert settings.is_production
    assert settings.secret_key == STRONG_KEY


def test_development_tolerates_the_default_secret():
    settings = _settings(environment="development", secret_key=DEFAULT_SECRET_KEY)
    assert not settings.is_production


# --- ADR-006: nửa vời thì hỏng lúc khởi động, không phải lúc ai đó bấm Tải lên


def test_s3_driver_without_credentials_refuses_to_boot():
    """Nếu không nổ ở đây, nó sẽ nổ ở request đầu tiên của một biên tập viên.

    Ràng buộc bắt cả hai driver, không riêng audio: từ khi `s3` dùng chung một
    bộ khoá cho cả ảnh lẫn audio, đặt mỗi `IMAGE_STORAGE_DRIVER=s3` cũng đủ để
    cấu hình thành nửa vời.
    """
    with pytest.raises(ValidationError, match="S3_BUCKET"):
        _settings(audio_storage_driver="s3", s3_endpoint_url="https://x.supabase.co/storage/v1/s3")

    with pytest.raises(ValidationError, match="S3_ENDPOINT_URL"):
        _settings(image_storage_driver="s3")
