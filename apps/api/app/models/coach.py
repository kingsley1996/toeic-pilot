import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

__all__ = ["COACH_STATUSES", "CoachExplanation", "CoachFeedback"]

# `draft` = máy vừa sinh, chưa ai đọc. `published` = người duyệt đã giữ lại.
# `rejected` = người duyệt bỏ; bản bị bỏ KHÔNG được phục vụ, và lần gặp sau sinh
# lại — nên `rejected` là một trạng thái sống, không phải rác cần xoá.
COACH_STATUSES = ("draft", "published", "rejected")

# JSONB ở Postgres, JSON ở SQLite của bộ test. Cùng cách `audio_script` đã làm.
_JSON = JSON().with_variant(JSONB(), "postgresql")


class CoachExplanation(Base):
    """Lời giải cho MỘT câu hỏi khi học viên chọn MỘT phương án cụ thể.

    **`prompt_version` nằm trong khoá duy nhất, và đó là chỗ dễ bỏ sót nhất.**
    Không có nó thì sửa prompt xong, mọi học viên đã có bản cache vẫn nhận bản
    cũ **vĩnh viễn**, và người sửa không có cách nào biết bản sửa của mình chưa
    tới ai. Có nó thì đổi prompt tự làm mới, và tỉ lệ cache trúng tụt xuống rồi
    bò lên — một tín hiệu nhìn thấy được.

    Bảng chứ không phải Redis: đây là **nội dung**. Nó cần sống qua restart, cần
    duyệt được, và cần gắn phản hồi của học viên vào. Redis giữ hạn mức;
    Postgres giữ nội dung.

    `UNIQUE` ba cột **chính là** cache — tra trước khi gọi, ghi sau khi gọi.
    """

    __tablename__ = "coach_explanation"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "selected_option_id",
            "prompt_version",
            name="uq_coach_explanation_key",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'rejected')", name="ck_coach_explanation_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), nullable=False
    )
    # Phương án học viên đã chọn. NULL nghĩa là bỏ trống — và bỏ trống là một
    # trạng thái CÓ THẬT đáng giải thích riêng ("bạn không kịp làm câu này"),
    # không phải dữ liệu thiếu. `attempt_item` đã theo đúng luật ấy (ADR-001 §A4.5).
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question_option.id", ondelete="CASCADE"), nullable=True
    )
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # Đầu ra CÓ CẤU TRÚC, không phải một khối văn xuôi: giao diện render theo
    # mục, và bộ eval kiểm được từng trường.
    body: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoachFeedback(Base):
    """Học viên thấy lời giải này có ích không.

    Thước đo **chất lượng** duy nhất đến từ người thật. Không có nó thì mọi con
    số chỉ nói được "rẻ và nhanh", không nói được "có dạy được ai không".

    Khoá chính `(explanation_id, user_id)` khiến một người chỉ bỏ được một phiếu
    — không có nó thì một người bấm mười lần làm lệch đúng con số duy nhất đo
    chất lượng.
    """

    __tablename__ = "coach_feedback"

    explanation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("coach_explanation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
