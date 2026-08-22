"""user_badge: badge nào đã thấy lần đầu lúc nào, và đã xem chưa

Revision ID: 031_user_badge
Revises: 030_xp_event
Create Date: 2026-08-21 16:00:00.000000

VIẾT TAY, không autogenerate — cùng lý do như `029` và `030`: cơ sở dữ liệu dev
mang bốn bảng mồ côi `pet`, `learner_pet`, `pet_feed`, `pet_feed_log`, nên
autogenerate sinh thêm bốn lệnh DROP TABLE không ai yêu cầu.

Bảng này KHÔNG lưu "người này có badge gì" — điều kiện suy ra từ lịch sử học ở
`app/services/badges.py`. Nó chỉ lưu hai thứ lịch sử không tự nói được: lần đầu
hệ thống nhìn thấy, và đã xem thông báo chưa.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031_user_badge"
down_revision: str | None = "030_xp_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_badge",
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # Mã badge, không phải khoá ngoại: danh sách badge sống trong code
        # (`app/services/badges.py`) chứ không trong một bảng nội dung. Một bảng
        # định nghĩa badge sẽ phải được giữ đồng bộ bằng tay với các điều kiện,
        # mà điều kiện thì là code — hai nguồn sự thật cho cùng một danh sách.
        sa.Column("code", sa.String(length=32), primary_key=True),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # NULL = chưa xem.
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("user_badge")
