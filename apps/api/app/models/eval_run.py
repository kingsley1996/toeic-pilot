"""Lượt chạy eval AI từ giao diện — `eval_run`.

Mỗi hàng là MỘT lượt chạy do người bấm nút (hoặc CLI về sau): suite nào, ai
bấm, xong chưa, báo cáo JSON. LƯU chứ không chạy lại lúc đọc, vì judge là lượt
gọi model thật (tiền + phút), và vì UI cần hiện lượt đang chạy dở.

Ranh giới với `ai_interaction`: đó là sổ từng lượt GỌI model; đây là sổ từng
lượt CHẠY eval. Worker ghi cả hai — gọi model nào trong lượt chạy đều có hàng
bên kia để đối chiếu chi phí.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["EVAL_RUN_STATUSES", "EvalRun"]

EVAL_RUN_STATUSES = ("queued", "running", "done", "error")


class EvalRun(Base):
    __tablename__ = "eval_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'done', 'error')",
            name="ck_eval_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Suite đã chạy: "all" hoặc một tên trong eval_core.SUITES. Chuỗi tự do có
    # CHECK ở tầng API (422 khi lạ), không enum ở DB — thêm suite mới không
    # được phép thành một migration.
    suite: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")

    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Tham số chạy: {"judge_model": ..., "gen_model": ..., "retrieval_mode": ...}.
    # Chỉ judge tốn tiền và cần model — suite offline bỏ qua.
    params: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # Báo cáo đúng hình `_report_json` của runner + mục judge (nếu có).
    report: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
