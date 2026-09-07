"""Kết quả so sánh planner V1/V2 — `planner_eval` (SPEC-PLACEMENT §5).

Mỗi hàng là MỘT lượt chạy so sánh trên một lượt placement: V1 chọn gì, V2
chọn gì, phủ bao nhiêu %, tốn bao nhiêu. Đó là dữ liệu để trả lời câu hỏi
"LLM có đáng không" bằng số thay vì bằng cảm tính — và nó LƯU, không tính
lại lúc đọc, vì chạy V2 là một lượt gọi model thật (tiền + ~54 giây).
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlannerEval(Base):
    __tablename__ = "planner_eval"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weak_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # JSON với biến thể JSONB — cùng khuôn `audio_script`: SQLite test không có
    # JSONB.
    v1_items: Mapped[list[dict[str, str | None]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    v2_items: Mapped[list[dict[str, str | None]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    coverage: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    dangling: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
