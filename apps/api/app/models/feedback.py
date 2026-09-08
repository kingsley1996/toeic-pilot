"""Góp ý của người học (migration 074).

**Ảnh đính kèm là khoá THÔ, không có hàng `image_asset`** — cùng khuôn với
`user_profile.avatar_storage_key`. Bảng `image_asset` có `license`,
`attribution` và `source_url` NOT NULL vì ảnh mượn phần lớn là CC-BY; ảnh người
học chụp màn hình thì không có ba thứ đó và cũng không cần, nên bắt nó đi qua
bảng ấy là bịa ra ba giá trị giả. Tiền tố `feedback/` riêng giữ nó ngoài tầm
lệnh dọn ảnh mồ côi khu nội dung (ADR-006 §2.1).
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

FEEDBACK_TYPES = ("bug", "feature", "content", "other")
FEEDBACK_STATUSES = ("pending", "approved", "rejected")

# Trần số góp ý CHƯA XỬ LÝ của một người. Chặn theo `pending` chứ không theo
# tổng: người góp ý đều đặn và được duyệt đều đặn thì không bao giờ chạm trần,
# còn người rải hàng loạt thì dừng lại ngay — và trần tự mở ra khi admin xử lý.
PENDING_CAP = 10

# Trần số ảnh một góp ý mang theo. Ba là đủ để kể một lỗi — trước, trong, sau —
# và đủ ít để màn duyệt không thành một thư viện ảnh.
MAX_SCREENSHOTS = 3

# JSONB ở Postgres, JSON thường ở SQLite của bộ test — `SQLiteTypeCompiler`
# không dựng được JSONB, và cùng khuôn `coach.py` với `dictation.py` đã dùng.
_JSON = JSON().with_variant(JSONB(), "postgresql")


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("type IN ('bug', 'feature', 'content', 'other')", name="ck_feedback_type"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_feedback_status"),
        Index("ix_feedback_status_created", "status", "created_at"),
        Index("ix_feedback_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # MỘT CỘT JSONB, không phải ba cột `screenshot_2/3`. Khuôn nhiều cột đã có
    # trong repo (`question_set.passage_2_image_id`) và nó tính tiền ở chỗ khác:
    # luật `reconcile_media` phải liệt kê ĐỦ mọi cột trỏ tới ảnh, và cột nào bị
    # quên thì mọi ảnh của nó bị báo là mồ côi. Một mảng thì không có cột nào để
    # quên. Cùng khuôn `pet_species.lines` (migration 073).
    screenshot_keys: Mapped[list[str] | None] = mapped_column(_JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `SET NULL`, không `CASCADE`: xoá tài khoản admin không được phép xoá góp ý
    # của người học. Ai duyệt là thông tin phụ; bản thân góp ý mới là dữ liệu.
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
