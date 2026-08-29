"""Một lần đo tình trạng dịch vụ (migration 049)."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HealthSample(Base):
    __tablename__ = "health_sample"
    __table_args__ = (
        CheckConstraint("state IN ('ok', 'degraded', 'down')", name="ck_health_sample_state"),
        Index("ix_health_sample_service_time", "service", "checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
