"""User-built listening lessons from real-world video (YouTube-first slice).

Khác cây dictation có sẵn (`DictationItem` thuộc topic/section/story do đội ngũ
biên soạn): ở đây MỖI user tự tạo bài từ URL của mình, nên ownership (`user_id`)
là biên an ninh — mọi endpoint đọc/ghi đều phải lọc theo nó.

Không có bảng exercise riêng: một segment HỢP LỆ chính là một bài dictation
(`promptType = "full"` duy nhất ở MVP). Attempt trỏ thẳng `segment_id`. Ngày nào
có biến thể (blank, shadowing...) mới tách bảng exercise — tách sớm là trả tiền
JOIN cho một quan hệ 1:1.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.mixins import TimestampMixin

# JSONB on PostgreSQL, plain JSON on the SQLite used by the test fixture —
# cùng mẹo với `models/dictation.py`.
_JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")

# Slice này resolver chỉ cho qua "youtube"; giữ đủ ba loại ở CHECK để thêm
# TikTok/Upload sau không phải sửa ràng buộc, chỉ mở cổng ở service.
LISTENING_SOURCE_TYPES = ("youtube", "tiktok", "upload")
LISTENING_TRANSCRIPT_STATUSES = ("pending", "ready", "failed")


class ListeningContent(Base, TimestampMixin):
    __tablename__ = "listening_content"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('youtube', 'tiktok', 'upload')",
            name="ck_listening_content_source",
        ),
        CheckConstraint(
            "transcript_status IN ('pending', 'ready', 'failed')",
            name="ck_listening_content_transcript_status",
        ),
        # Lịch sử bài đã tạo của một user, mới nhất trước.
        Index("ix_listening_content_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Video ID nền tảng (YouTube 11 ký tự). NULL chỉ khi source không có khái
    # niệm external ID (upload) — YouTube luôn có, thiếu là dữ liệu hỏng.
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # Chưa biết khi tạo từ oEmbed (nó không trả duration) — validation
    # timestamp-trong-duration chỉ chạy khi cột này có giá trị.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Slice paste-transcript tạo xong là `ready` ngay trong cùng transaction;
    # `pending`/`failed` dành cho đường STT bất đồng bộ (Upload) sau này.
    transcript_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    # Bài của đội biên soạn, mọi user đọc được (thư viện có sẵn). Mặc định
    # false: bài user tự tạo là riêng tư, công khai là hành động chủ ý (hiện
    # tại chỉ seed script làm việc đó).
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False, index=True
    )
    # Key file mp4 tự host cho bài TikTok (embed/hotlink gốc đều bị chặn) —
    # NULL là chưa ingest, UI dùng embed + link ngoài. Xem migration 091.
    media_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    segments: Mapped[list["ListeningSegment"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by="ListeningSegment.segment_index",
    )


class ListeningSegment(Base):
    __tablename__ = "listening_segment"
    __table_args__ = (
        CheckConstraint("start_seconds >= 0", name="ck_listening_segment_start"),
        CheckConstraint("end_seconds > start_seconds", name="ck_listening_segment_end"),
        Index("ix_listening_segment_content_order", "content_id", "segment_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listening_content.id", ondelete="CASCADE"), nullable=False
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    end_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Dạng đã chuẩn hoá (`services.dictation.normalise` nối lại) — để dành
    # chấm lại/tìm kiếm mà không phụ thuộc bộ chấm hiện tại.
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)

    content: Mapped[ListeningContent] = relationship(back_populates="segments")


class ListeningAttempt(Base):
    __tablename__ = "listening_attempt"
    __table_args__ = (
        CheckConstraint("accuracy BETWEEN 0 AND 100", name="ck_listening_attempt_accuracy"),
        # Streak/profile lọc (người, ngày): thiếu nó là quét toàn lịch sử user —
        # cùng lý do với `ix_dictation_attempt_user_created`.
        Index("ix_listening_attempt_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listening_segment.id", ondelete="RESTRICT"), nullable=False
    )
    # Giữ nguyên văn như gõ. Chuẩn hoá là việc của bộ chấm, và bộ chấm sẽ đổi —
    # chỉ giữ bản chuẩn hoá thì không bao giờ chấm lại được bài cũ.
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Khớp từng từ, không thiếu không thừa — tiến độ đếm cột NÀY (đặt tên theo
    # `dictation_attempt.is_complete`), vì accuracy 100 vẫn có thể thừa từ.
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    # `matched / expected * 100` từ bộ chấm dictation — đóng vai `similarity`
    # của SPEC (không đẻ thêm khái niệm mới cho cùng một con số).
    accuracy: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    # Word-diff để UI vẽ lại highlight mà không chạy lại bộ chấm.
    word_diff: Mapped[Any | None] = mapped_column(_JSON_TYPE, nullable=True)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
