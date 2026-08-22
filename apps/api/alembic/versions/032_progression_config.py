"""Cấu hình hệ level thành dữ liệu: mức XP, khe daily task, bậc level/khung, luật badge

Revision ID: 032_progression_config
Revises: 031_user_badge
Create Date: 2026-08-21 17:00:00.000000

VIẾT TAY, không autogenerate — cùng lý do như `029`–`031`: database dev mang bốn
bảng mồ côi `pet`, `learner_pet`, `pet_feed`, `pet_feed_log`, nên autogenerate
sinh thêm bốn lệnh DROP TABLE không ai yêu cầu.

**Migration này KHÔNG chèn dữ liệu mặc định.** Bộ mặc định sống ở một chỗ duy
nhất, `app/models/progression.py`, và lớp dịch vụ seed lười ở lần đọc đầu tiên
khi bảng còn trống — cùng khuôn với `backdrop_setting`. Chèn ở cả hai nơi là hai
bộ mặc định phải giữ đồng bộ bằng tay, và chúng sẽ lệch nhau ở đúng lần đầu ai đó
sửa một con số mà quên nơi kia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "032_progression_config"
down_revision: str | None = "031_user_badge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "progression_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("xp_vocabulary_review", sa.Integer(), nullable=False),
        sa.Column("xp_dictation_complete", sa.Integer(), nullable=False),
        sa.Column("xp_attempt_submit", sa.Integer(), nullable=False),
        sa.Column("daily_xp_cap", sa.Integer(), nullable=False),
        # Tham số của MÁY SINH bảng level, không phải của phép tra cứu — phép tra
        # cứu chỉ đọc `level_tier`.
        sa.Column("curve_coefficient", sa.Numeric(8, 2), nullable=False),
        sa.Column("curve_exponent", sa.Numeric(4, 2), nullable=False),
        sa.Column("curve_break", sa.Integer(), nullable=False),
        sa.Column("curve_linear_step", sa.Integer(), nullable=False),
        sa.Column("max_level", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_progression_setting_singleton"),
        sa.CheckConstraint("daily_xp_cap > 0", name="ck_progression_setting_cap"),
    )

    op.create_table(
        "daily_task_slot",
        # uuid của hàng này đi thẳng vào `xp_event.source_id` (qua uuid5), nên nó
        # phải bền: đổi tên khe không được biến ngày đã thưởng thành chưa thưởng.
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("target > 0", name="ck_daily_task_slot_target"),
        sa.CheckConstraint("xp >= 0", name="ck_daily_task_slot_xp"),
    )

    op.create_table(
        "level_tier",
        sa.Column("level", sa.Integer(), primary_key=True),
        sa.Column("xp_required", sa.Integer(), nullable=False),
        sa.CheckConstraint("xp_required >= 0", name="ck_level_tier_xp"),
    )

    op.create_table(
        "frame_tier",
        sa.Column("code", sa.String(length=32), primary_key=True),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("min_level", sa.Integer(), nullable=False),
        sa.Column("tone", sa.String(length=16), nullable=False),
        sa.Column("ring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("min_level >= 1", name="ck_frame_tier_min_level"),
        sa.UniqueConstraint("min_level", name="uq_frame_tier_min_level"),
    )

    op.create_table(
        "badge_rule",
        sa.Column("code", sa.String(length=32), primary_key=True),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("hint", sa.String(length=160), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("target > 0", name="ck_badge_rule_target"),
    )

    # Mốc nước cao: level không bao giờ tụt khi admin sửa bảng ngưỡng. Mặc định 1
    # cho mọi hàng cũ là đúng — nó chỉ nói "chưa từng đạt gì cao hơn level 1", và
    # lần đọc đầu tiên sau đây sẽ nâng nó lên theo XP thật.
    op.add_column(
        "user_profile",
        sa.Column("level_reached", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "level_reached")
    op.drop_table("badge_rule")
    op.drop_table("frame_tier")
    op.drop_table("level_tier")
    op.drop_table("daily_task_slot")
    op.drop_table("progression_setting")
