from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.media import DEFAULT_MEDIA_ROOT

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

    # Có tin `X-Forwarded-For` để lấy IP client hay không.
    #
    # Mặc định TẮT, và mặc định đó là phần bảo mật chứ không phải sự thận trọng
    # thừa: header này do client gửi. Tin nó khi KHÔNG có proxy nào đứng trước
    # nghĩa là bất kỳ ai cũng tự khai IP của mình, và giới hạn tần suất theo IP
    # trở thành thứ trông như đang bảo vệ mà không chặn được gì.
    #
    # Bật nó lên khi và chỉ khi có reverse proxy của chính bạn đứng trước API.
    trust_forwarded_for: bool = False

    # --- Tầng AI (ADR-003) -------------------------------------------------
    # Model cho từng tầng là CẤU HÌNH chứ không phải mã: đổi model là việc vận
    # hành, không nên là một lần sửa mã cộng một lần triển khai.
    llm_tier_cheap: str = "fake/fake-1"
    llm_tier_strong: str = "fake/fake-1"
    # Trần chi tiêu mỗi học viên mỗi ngày, tính bằng micro-USD (1_000_000 = 1 USD).
    # Con số này là TẠM và có chủ ý: đặt nó trước khi biết một lượt Coach tốn
    # bao nhiêu là đoán, và lát A tồn tại để đo (AI-ENGINEERING-PLAN §10).
    ai_daily_budget_micro_usd: int = 50_000
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    openrouter_api_key: str | None = None
    # `localhost` khi chạy pipeline từ dòng lệnh trên máy; container phải dùng
    # `host.docker.internal`. Là cấu hình chính vì lý do đó.
    ollama_base_url: str = "http://localhost:11434"
    secret_key: str = DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    log_format: str = "json"  # "json" for shipping, "text" for local reading
    # Prefix for playable audio URLs. In development this points at the /media
    # mount served by this app; in production it is the CDN/object-store origin.
    # The API only ever concatenates it with a storage key — it never calls the
    # object store at request time, so no bucket credential belongs in this file.
    audio_public_base_url: str = "http://localhost:8000/media"
    # Directory backing the development-only /media mount. Shares its default
    # with the content pipeline so the two cannot drift apart; in production
    # nothing is mounted and audio is served straight from the CDN origin.
    media_root: Path = DEFAULT_MEDIA_ROOT

    # --- media upload (ADR-006) ---------------------------------------------
    #
    # Hai driver TÁCH RIÊNG, không phải một. Ảnh cần biến đổi và tốn ít băng
    # thông; audio thì ngược lại — không cần biến đổi gì nhưng ngốn băng thông
    # tuyến tính theo số học viên. Mô hình giá của hai loại dịch vụ này ngược
    # nhau, nên ép chúng dùng chung một nơi là chọn sai ở một trong hai đầu
    # (ADR-006 §2.2).
    image_storage_driver: str = "local"  # "local" | "cloudinary" | "s3"
    audio_storage_driver: str = "local"  # "local" | "s3"

    # Tiền tố URL công khai của ảnh. Cùng vai trò với `audio_public_base_url`:
    # runtime chỉ NỐI CHUỖI, không bao giờ gọi object store lúc có request.
    image_public_base_url: str = "http://localhost:8000/media"

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    # `SecretStr` để giá trị không lọt ra qua `repr()` hay một dòng log lỡ in cả
    # settings. Đọc bằng `.get_secret_value()` ngay tại chỗ dùng.
    cloudinary_api_secret: SecretStr = SecretStr("")
    cloudinary_folder: str = "toeic-pilot"

    # Object store nói giao thức S3. MỘT bộ biến dùng chung cho cả hai loại
    # media, vì endpoint và cặp khoá là của tài khoản chứ không của loại file;
    # cái tách riêng theo loại là *driver nào được chọn* và *URL công khai nào
    # được nối vào*, và hai thứ đó đã có biến riêng ở trên.
    #
    # Cố ý không đặt tên theo nhà cung cấp. `S3_ENDPOINT_URL` quyết định đó là
    # Supabase, B2, R2, DO Spaces hay MinIO — đổi nhà cung cấp là đổi một dòng
    # env, không phải sửa code.
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")

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

    @model_validator(mode="after")
    def _reject_half_configured_storage(self) -> "Settings":
        """Thiếu credential thì hỏng lúc KHỞI ĐỘNG, không phải lúc ai đó bấm Tải lên.

        Chọn driver `cloudinary` mà quên một biến môi trường là lỗi cấu hình, và
        lỗi cấu hình phải nổ ở chỗ có người đang nhìn. Để nó nổ ở request đầu
        tiên nghĩa là nó nổ với một biên tập viên đang dở tay nhập đề.
        """
        if self.image_storage_driver == "cloudinary":
            missing = [
                name
                for name, value in (
                    ("CLOUDINARY_CLOUD_NAME", self.cloudinary_cloud_name),
                    ("CLOUDINARY_API_KEY", self.cloudinary_api_key),
                    ("CLOUDINARY_API_SECRET", self.cloudinary_api_secret.get_secret_value()),
                )
                if not value
            ]
            if missing:
                raise ValueError("IMAGE_STORAGE_DRIVER=cloudinary needs: " + ", ".join(missing))
        if "s3" in {self.image_storage_driver, self.audio_storage_driver}:
            missing = [
                name
                for name, value in (
                    ("S3_ENDPOINT_URL", self.s3_endpoint_url),
                    ("S3_BUCKET", self.s3_bucket),
                    ("S3_ACCESS_KEY_ID", self.s3_access_key_id),
                    ("S3_SECRET_ACCESS_KEY", self.s3_secret_access_key.get_secret_value()),
                )
                if not value
            ]
            if missing:
                raise ValueError("STORAGE_DRIVER=s3 needs: " + ", ".join(missing))
        return self


settings = Settings()
