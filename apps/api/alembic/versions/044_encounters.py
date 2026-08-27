"""chạm mặt: NPC giao việc và những đợt xâm nhập (ADR-012 lát 1)

Revision ID: 044_encounters
Revises: 043_pet_sleep
Create Date: 2026-08-27 22:10:00.000000

Bảng `encounter` **không có ô sprite và không có toạ độ**: nó giữ *nhiệm vụ là
gì* và *còn hiệu lực tới bao giờ*, còn hình dạng với chỗ đứng thì trình duyệt
suy ra từ `encounter.id`. Máy chủ không đọc `map.json` — cùng lý do đã ghi cho
`PUT /pet/position` — và bảng phân vai sinh vật sống ở frontend, nên chép một
danh sách ô sang đây là dựng bản sao thứ hai của thứ đã có một bản.

`pet_state` nhận hai mốc HẸN GIỜ. Chúng được chốt ngay khi một cuộc chạm mặt kết
thúc, kèm khoảng ngẫu nhiên — chứ không bốc xúc xắc ở mỗi lần đọc. Nếu mỗi lần
đọc là một lần bốc thì bấm F5 mười lần gọi NPC ra nhanh gấp mười, và cái góc này
lập tức dạy người ta bấm lại trang thay vì học.

`encounter_setting` để RỖNG, gieo lười ở lần đọc đầu — đúng khuôn `egg_setting`.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "044_encounters"
down_revision: Union[str, None] = "043_pet_sleep"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encounter",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("task_kind", sa.String(length=16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("steps_total", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("steps_done", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("reward_ruby", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="waiting"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('npc', 'intruder')", name="ck_encounter_kind"),
        sa.CheckConstraint(
            "task_kind IN ('vocabulary', 'dictation', 'quiz')", name="ck_encounter_task"
        ),
        sa.CheckConstraint("state IN ('waiting', 'done', 'expired')", name="ck_encounter_state"),
        sa.CheckConstraint("steps_total > 0", name="ck_encounter_steps_total"),
        sa.CheckConstraint(
            "steps_done >= 0 AND steps_done <= steps_total", name="ck_encounter_steps"
        ),
    )
    op.create_index("ix_encounter_user_state", "encounter", ["user_id", "state"])

    op.create_table(
        "encounter_setting",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("npc_gap_seconds", sa.Integer(), nullable=False, server_default="1200"),
        sa.Column("npc_life_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("npc_reward", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("intruder_gap_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("intruder_life_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("intruder_reward", sa.SmallInteger(), nullable=False, server_default="20"),
        sa.Column("intruder_steps", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("npc_gap_seconds > 0", name="ck_encounter_npc_gap"),
        sa.CheckConstraint("npc_life_seconds > 0", name="ck_encounter_npc_life"),
        sa.CheckConstraint("intruder_gap_seconds > 0", name="ck_encounter_intruder_gap"),
        sa.CheckConstraint("intruder_life_seconds > 0", name="ck_encounter_intruder_life"),
        sa.CheckConstraint("intruder_steps > 0", name="ck_encounter_intruder_steps"),
    )

    op.add_column("pet_state", sa.Column("next_npc_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "pet_state", sa.Column("next_intruder_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("pet_state", "next_intruder_at")
    op.drop_column("pet_state", "next_npc_at")
    op.drop_table("encounter_setting")
    op.drop_index("ix_encounter_user_state", table_name="encounter")
    op.drop_table("encounter")
