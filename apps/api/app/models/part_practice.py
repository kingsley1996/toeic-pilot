"""Bảng cho khu "Luyện theo part": chiến thuật tĩnh và PHIÊN luyện tập.

Theo khuôn khu luyện thi (`Attempt`/`AttemptItem`) chứ không phải sổ lượt:
một lần luyện là một PHIÊN có danh sách câu chốt lúc bắt đầu, trả lời dần, và
XEM LẠI được sau khi xong. `part_drill_attempt` (migration 063, lượt rời) bị
các bảng phiên thay ngay ở 064 — chưa ai phụ thuộc, giữ lại là giữ hai sự thật
cho cùng một hoạt động.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PartTactics(Base):
    """Trang chiến thuật của một part — `part` 1..7 là khoá chính tự nhiên.

    Nội dung sống trong DB chứ không đọc từ đĩa khi render: production web
    không có thư mục `content/` của repo (image chỉ chứa code đã build), và
    "sửa một trang chiến thuật không đáng một lần deploy" là lý do grammar
    lesson nằm trong DB. Nguồn sự thật để SOẠN vẫn là markdown trong
    `apps/web/content/parts/`; `scripts/sync-parts.sh` là đường một chiều
    md → DB.
    """

    __tablename__ = "part_tactics"

    part: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PartSession(Base):
    """Một phiên luyện theo part.

    `label` NULL = "Tất cả". Câu được CHỐT lúc tạo phiên (bảng item) chứ không
    mẫu lại mỗi lần đọc — "xem lại phiên hôm qua" mà ra câu khác là phiên khác.
    """

    __tablename__ = "part_session"
    __table_args__ = (CheckConstraint("part BETWEEN 1 AND 7", name="ck_part_session_part"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Danh sách mã taxonomy, rỗng = "Tất cả". JSON (biến thể JSONB trên
    # Postgres) theo đúng khuôn `audio_script`: SQLite của bộ test không có
    # JSONB. Một nhãn mỗi phiên là giả — luyện "Thì" với "Giới từ" cùng lúc là
    # chuyện bình thường, và checkbox nhiều lựa chọn là khuôn của khu luyện thi.
    labels: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    # NULL = không giới hạn giờ. Đồng hồ tính từ `created_at` và chạy cả khi
    # đóng tab — cùng lý lẽ với khu luyện thi: đồng hồ máy khách chỉnh được.
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    # NULL = đang làm. Không có nút "nộp" bắt buộc: bấm "Xem kết quả", trả lời
    # câu cuối, hoặc hết giờ đều chốt nó — ba đường, một cột.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phiên đóng vì hết giờ chứ không vì người học bấm nộp.
    expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    items: Mapped[list["PartSessionItem"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PartSessionItem.position",
    )


class PartSessionItem(Base):
    """Một câu của phiên — trả lời tại chỗ, lần trả lời ĐẦU là lần cuối.

    Drill cho phản hồi tức thì nên câu đã trả lời là đóng; muốn làm lại thì tạo
    PHIÊN mới, đừng viết đè lịch sử của phiên cũ.
    """

    __tablename__ = "part_session_item"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_part_session_item_question"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("part_session.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_option.id", ondelete="SET NULL"), nullable=True
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[PartSession] = relationship(back_populates="items")
