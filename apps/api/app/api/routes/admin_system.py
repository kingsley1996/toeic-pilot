"""Trạng thái sống của các dịch vụ dựng nên production (ADR-014).

`require_role("admin")` chứ không `editor`: hạ tầng là chuyện vận hành, và câu
trả lời có kèm tên nhà cung cấp cùng địa chỉ kho media.

Endpoint này KHÔNG tự gọi ra CDN. Media đi thẳng từ trình duyệt tới kho, không
qua API (ADR-006 §2.9), nên phép kiểm chạy ở API sẽ kiểm một đường mà không ai
đi. Nó chỉ trả về cấu hình cộng một khoá có thật để trình duyệt tự thử.
"""

import time
from datetime import UTC, datetime

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import settings
from app.core.database import get_db
from app.core.media import public_audio_url
from app.core.redis_client import get_redis
from app.core.storage import StorageError, get_driver
from app.models import AudioAsset, ImageAsset, User
from app.schemas.system import DependencyStatus, MediaChannel, SystemStatus

router = APIRouter(prefix="/admin/system", tags=["admin"])

can_view = require_role("admin")


def _host(url: str) -> str:
    """Chỉ phần host.

    Phải cắt cả phần `user:password@` ở giữa. Chuỗi kết nối Postgres và Redis
    đều mang mật khẩu ở đó, nên bỏ sót một bước là in mật khẩu production lên
    màn hình quản trị — và màn hình ấy tồn tại để đưa cho người khác xem.
    """
    authority = url.split("://", 1)[-1].split("/", 1)[0]
    return authority.rsplit("@", 1)[-1] or url


def _check_database(db: Session) -> tuple[DependencyStatus, str | None]:
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        elapsed = (time.perf_counter() - started) * 1000
        try:
            revision = db.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
        except SQLAlchemyError:
            revision = None
        return (
            DependencyStatus(
                id="database",
                label="PostgreSQL",
                provider=_host(settings.database_url),
                state="ok",
                latency_ms=round(elapsed, 1),
                detail=f"migration {revision}" if revision else None,
            ),
            revision,
        )
    except SQLAlchemyError as exc:
        return (
            DependencyStatus(
                id="database",
                label="PostgreSQL",
                provider=_host(settings.database_url),
                state="down",
                detail=type(exc).__name__,
            ),
            None,
        )


def _check_redis() -> DependencyStatus:
    started = time.perf_counter()
    try:
        get_redis().ping()
        return DependencyStatus(
            id="redis",
            label="Redis",
            provider=_host(settings.redis_url),
            state="ok",
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
    except (redis.RedisError, OSError) as exc:
        # `degraded`, không phải `down`: Redis là phụ thuộc MỀM ở khắp nơi trừ
        # luồng OAuth. Vẽ nó thành đỏ sẽ nói rằng sản phẩm đã chết, trong khi
        # thứ thật sự mất là thu hồi token và giới hạn tần suất.
        return DependencyStatus(
            id="redis",
            label="Redis",
            provider=_host(settings.redis_url),
            state="degraded",
            detail=type(exc).__name__,
        )


def _media_channel(db: Session, kind: str) -> MediaChannel:
    if kind == "audio":
        key = db.execute(select(AudioAsset.storage_key).limit(1)).scalar_one_or_none()
        sample = public_audio_url(key) if key else None
        driver = settings.audio_storage_driver
        base = settings.audio_public_base_url
        label = "Audio store"
    else:
        key = db.execute(select(ImageAsset.storage_key).limit(1)).scalar_one_or_none()
        try:
            sample = get_driver("image").public_url(key) if key else None
        except StorageError:
            sample = None
        driver = settings.image_storage_driver
        base = settings.image_public_base_url
        label = "Image store"
    return MediaChannel(
        id=kind,
        label=label,
        driver=driver,
        public_base_url=_host(base),
        sample_url=sample,
    )


@router.get("/status", response_model=SystemStatus)
def system_status(db: Session = Depends(get_db), _: User = Depends(can_view)) -> SystemStatus:
    database, revision = _check_database(db)
    return SystemStatus(
        environment=settings.environment,
        checked_at=datetime.now(UTC),
        schema_revision=revision,
        dependencies=[database, _check_redis()],
        media=[_media_channel(db, "audio"), _media_channel(db, "image")],
    )
