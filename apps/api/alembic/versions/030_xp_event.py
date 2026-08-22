"""xp_event: sổ cái XP cho hệ level

Revision ID: 030_xp_event
Revises: 029_profile_pet
Create Date: 2026-08-21 12:00:00.000000

VIẾT TAY, không autogenerate — cùng lý do như `029`: cơ sở dữ liệu dev mang bốn
bảng mồ côi `pet`, `learner_pet`, `pet_feed`, `pet_feed_log`, nên autogenerate
sinh thêm bốn lệnh DROP TABLE không ai yêu cầu.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030_xp_event"
down_revision: str | None = "029_profile_pet"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "xp_event",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        # Cố ý KHÔNG phải khoá ngoại: nó trỏ vào ba bảng khác nhau tuỳ
        # `source_type`, và với `daily_task` thì không trỏ vào hàng nào cả.
        sa.Column("source_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        # Ngày theo múi giờ NGƯỜI HỌC, quy đổi lúc ghi. Xem chú thích trên model.
        sa.Column("awarded_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    # Chống trao hai lần cho cùng một hoạt động. Lưu ý Postgres coi mọi NULL là
    # khác nhau, nên ràng buộc này không chặn được nguồn có `source_id` NULL —
    # đó là lý do các nguồn không có hàng gốc phải sinh uuid tất định.
    op.create_unique_constraint(
        "uq_xp_event_source", "xp_event", ["user_id", "source_type", "source_id"]
    )
    op.create_index("ix_xp_event_user_day", "xp_event", ["user_id", "awarded_on"])


def downgrade() -> None:
    op.drop_index("ix_xp_event_user_day", table_name="xp_event")
    op.drop_constraint("uq_xp_event_source", "xp_event", type_="unique")
    op.drop_table("xp_event")
