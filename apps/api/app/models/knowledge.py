"""Knowledge base của TOEIC Pilot — corpus cho Trợ lý trang web.

Mỗi hàng là MỘT mục tài liệu, đồng bộ từ `apps/api/content/kb/*.md`. Nội dung
là NỘI DUNG nên nằm trong git, đi qua review như mã; bảng chỉ là bản đã tính
sẵn cho retrieval — cùng quan hệ "manifest ↔ hàng" với `audio_asset`.

Docstring của migration `051` ghi vì sao chưa có cột embedding.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["KnowledgeChunk"]


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nguồn sự thật: "tests-scoring" ↔ `content/kb/tests-scoring.md`. Đi vào
    # ngữ cảnh để câu trả lời trích dẫn được, và là khoá upsert của lượt sync.
    ref: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Từ khoá người viết khai, phân tách dấu phẩy — signal mạnh nhất của phép
    # tra lexical, vì title với content hiếm khi nhắc đúng từ người dùng dùng.
    keywords: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
