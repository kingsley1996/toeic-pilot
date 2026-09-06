"""Kế hoạch học — `study_plan` / `study_plan_item` (SPEC-PLACEMENT §6).

Một người MỘT kế hoạch hiện hành (`is_current`) — kế hoạch mới thay kế hoạch
cũ chứ không chồng lên. Tiến độ KHÔNG nằm ở đây: nó suy từ bản ghi học thật
(`grammar_lesson_completion`, `part_session_item`), cùng nguyên tắc §4
SPEC-GRAMMAR — cột tick trên kế hoạch là thứ lệch khỏi thực tế ở lần học đầu.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudyPlan(Base):
    __tablename__ = "study_plan"
    __table_args__ = (
        # Hai kế hoạch hiện hành của một người là hai lời khuyên mâu thuẫn
        # hiển thị cùng lúc — ràng buộc chặn ở tầng dữ liệu, không phải ở một
        # đoạn `if` ai đó phải nhớ.
        Index(
            "uq_study_plan_current",
            "user_id",
            unique=True,
            sqlite_where=text("is_current"),
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Phán quyết placement mà kế hoạch sinh từ — kế hoạch không có gốc thì
    # không giải thích được vì sao nó đề xuất cái này thay cái kia.
    placement_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="RESTRICT"), nullable=False
    )
    # Snapshot đầu vào (từ user_profile lúc sinh — nguồn sự thật là profile).
    target_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="rule"
    )  # "rule" | "llm" — cột so sánh V1/V2 (SPEC §5) có sẵn từ đầu.
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StudyPlanItem(Base):
    """Một mục kế hoạch = một nội dung THẬT (N4: tham chiếu treo không ghi).

    `kind` quyết định `ref_id` trỏ đâu: `grammar_lesson` → `grammar_lesson.id`,
    `part_drill` → số part (ref_id NULL). Trạng thái xong/chưa suy ra lúc đọc,
    không lưu cột.
    """

    __tablename__ = "study_plan_item"
    __table_args__ = (
        CheckConstraint("kind IN ('grammar_lesson', 'part_drill')", name="ck_study_plan_item_kind"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_plan.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
