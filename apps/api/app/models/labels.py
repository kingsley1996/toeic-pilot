import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["QuestionLabel", "QuestionSetLabel"]

# Dài nhất hiện tại là `PART_1_PERSON_AND_OBJECT_DESCRIPTION` (36). Cột cũ
# `skill_tag` là String(32) và mã đó TRÀN — một lỗi chỉ nổ lúc ghi hàng Part 1
# đầu tiên, tức là sau khi mọi thứ khác trông đã chạy.
_CODE = String(48)
_FACET = String(24)


class QuestionLabel(Base):
    """Nhãn của MỘT câu hỏi, ở một mặt phân loại.

    **Khoá chính là `(question_id, facet)`.** Đó là chỗ luật "đúng một nhãn mỗi
    mặt" được thi hành — không phải một quy ước ai đó phải nhớ, mà là một ràng
    buộc database từ chối vi phạm.

    `proposed_code` giữ nguyên nhãn MÁY đề xuất kể cả sau khi người sửa `code`.
    Không có nó thì biết "đã có người kiểm" là chưa đủ: phải biết người đó có
    phải SỬA hay không, và đó chính là KPI độ đúng.
    """

    __tablename__ = "question_label"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), primary_key=True
    )
    facet: Mapped[str] = mapped_column(_FACET, primary_key=True)

    code: Mapped[str] = mapped_column(_CODE, nullable=False, index=True)
    proposed_code: Mapped[str | None] = mapped_column(_CODE, nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # `SET NULL`: xoá một tài khoản biên tập không được xoá luôn sự thật rằng
    # nhãn này ĐÃ được kiểm — KPI độ đúng tính trên đúng tập đó.
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QuestionSetLabel(Base):
    """Nhãn của một NHÓM câu hỏi — thứ mô tả ngữ liệu dùng chung.

    Bốn mặt sống ở đây: Topic (Part 3), Speech Type (Part 4), Passage Type
    (Part 6, 7), Passage Structure (Part 7). Chúng là thuộc tính của đoạn hội
    thoại hay đoạn văn, không của từng câu — ba câu cùng một hội thoại Part 3
    luôn cùng chủ đề.

    Treo chúng trên `question` thì schema CHO PHÉP ba câu mang ba chủ đề khác
    nhau và không gì báo lỗi; thống kê theo chủ đề sẽ đếm một hội thoại thành ba
    hội thoại. Cùng lý do ADR-001 §A4.3 treo audio Part 3/4 ở `question_set`.
    """

    __tablename__ = "question_set_label"

    set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question_set.id", ondelete="CASCADE"), primary_key=True
    )
    facet: Mapped[str] = mapped_column(_FACET, primary_key=True)

    code: Mapped[str] = mapped_column(_CODE, nullable=False, index=True)
    proposed_code: Mapped[str | None] = mapped_column(_CODE, nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
