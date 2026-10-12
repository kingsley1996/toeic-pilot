"""Bài viết blog editorial (SPEC-BLOG).

Một bảng duy nhất. `body_json` là tài liệu Tiptap (gốc để mở editor soạn
tiếp), `body_html` là HTML render sẵn lúc Lưu (trang đọc SSR thẳng, đã qua
sanitize allowlist ở route admin trước khi cất — xem `admin_blog.py`).
"""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base
from app.models.mixins import PublishableMixin, status_check

# JSONB ở Postgres, JSON ở SQLite của bộ test — cùng khuôn `coach._JSON`.
_JSON = JSON().with_variant(JSONB(), "postgresql")

# Danh mục v1 chốt ở SPEC-BLOG §5. Text tự do + check ở DB để thêm category
# không cần migration mới; đổi slug category thì cấm (URL category đã crawl).
BLOG_CATEGORIES = (
    "meo-lam-bai",
    "ngu-phap",
    "tu-vung",
    "kinh-nghiem",
    "thong-bao",
)


class BlogPost(Base, PublishableMixin):
    __tablename__ = "blog_post"
    __table_args__ = (
        status_check("blog_post"),
        # Độ dài min/max + format slug validate ở Pydantic — `char_length` và
        # toán tử `~` của Postgres làm SQLite của bộ test vỡ. DB chỉ giữ check
        # chạy được cả hai dialect: status + category.
        CheckConstraint(
            "category IN ('meo-lam-bai', 'ngu-phap', 'tu-vung', 'kinh-nghiem', 'thong-bao')",
            name="ck_blog_post_category",
        ),
        Index("ix_blog_post_status_published", "status", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Bất biến sau publish (route khóa, không phải DB — DB không biết publish).
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(160), nullable=False)
    body_json: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    tags: Mapped[list[str]] = mapped_column(_JSON, nullable=False, default=list)
    author_name: Mapped[str] = mapped_column(String(64), nullable=False, default="ToeicPilot")
    # Part TOEIC bài viết nhắc tới (khối "Học tiếp" link đúng). NULL = không gắn.
    related_part: Mapped[int | None] = mapped_column(nullable=True)
