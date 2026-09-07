"""Kết quả bài test đầu vào — SPEC-PLACEMENT §2–§4.

Snapshot, cùng lý `attempt_item.is_correct`: ước lượng v1 (tỉ lệ + khoảng tin
cậy) và v2 (IRT) cho cùng một lượt làm sẽ khác nhau, nên phán quyết của thời
điểm chấm nằm lại đây chứ không tính lại lúc đọc.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlacementResult(Base):
    __tablename__ = "placement_result"
    # Tên index khai TAY để khớp migration 067. `index=True` sinh ra
    # `ix_placement_result_user_id`, tức dev (`create_all`) và prod (alembic)
    # mang hai tên khác nhau và autogenerate sau này đòi drop + create.
    __table_args__ = (Index("ix_placement_result_user", "user_id"),)

    # Một lượt làm — một phán quyết. Lượt placement là 1-1 với kết quả của nó.
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    estimator_version: Mapped[str] = mapped_column(String(16), nullable=False)

    listening_raw: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reading_raw: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Điểm quy đổi tại tỉ lệ đúng THẬT. Không suy được từ dải: đường cong quy
    # đổi dốc khác nhau từng khúc và dải bị kẹp ở hai đầu, nên trung điểm của
    # dải lệch tới hơn 20 điểm ở hai cực.
    listening_scaled: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reading_scaled: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    listening_low: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    listening_high: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reading_low: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reading_high: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Bảng ETS (Tannenbaum & Wylie 2006) map từng section; trần là C1.
    cefr_listening: Mapped[str] = mapped_column(String(2), nullable=False)
    cefr_reading: Mapped[str] = mapped_column(String(2), nullable=False)
    cefr_overall: Mapped[str] = mapped_column(String(2), nullable=False)
    # Điểm tự khai TRƯỚC khi làm — mốc so sánh, không phải dữ liệu chấm được.
    self_reported_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    target_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
