"""Hình dạng của màn hình theo dõi hệ thống ở khu quản trị."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DependencyState = Literal["ok", "degraded", "down"]


class DependencyStatus(BaseModel):
    """Một phụ thuộc mà API tự kiểm được vì nó tự gọi tới."""

    id: str
    label: str
    provider: str
    state: DependencyState
    latency_ms: float | None = None
    detail: str | None = None


class MediaChannel(BaseModel):
    """Một kho media mà API KHÔNG tự kiểm.

    Trình duyệt mới là thứ tải media, không phải API (ADR-006 §2.9), nên phép
    kiểm đúng phải chạy ở trình duyệt. Ở đây chỉ mô tả cấu hình cộng một khoá
    thật để phía kia có cái mà thử.
    """

    id: str
    label: str
    driver: str
    public_base_url: str
    sample_url: str | None = None


class SystemStatus(BaseModel):
    environment: str
    checked_at: datetime
    schema_revision: str | None = Field(
        default=None, description="Bản migration mà database đang đứng ở đó."
    )
    dependencies: list[DependencyStatus]
    media: list[MediaChannel]
