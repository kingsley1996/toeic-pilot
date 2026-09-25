"""Tháp dungeon: map theo slug, encounter kind dungeon, bảng dungeon_run

Revision ID: 098_dungeon_tower
Revises: 097_eval_run
Create Date: 2026-09-25 00:00:00.000000

Ba việc nhỏ gộp một lần, cùng một tính năng (tháp leo 100 tầng, spec ở
`planning/docs/DUNGEON-TOWER.md`):

1. `petland_map` khoá theo `slug` thay vì "đúng một hàng id=1": editor quản
   nhiều map, hàng cũ thành `slug='main'`. Thêm `portal_x/portal_y` (cổng vào
   tháp, NULL khi map không có cổng).
2. `ck_encounter_kind` thêm `'dungeon'`: mỗi lượt đánh trong tháp là một bước
   encounter, đi qua đúng bộ chấm/SM-2/thưởng của chạm mặt thường.
3. Bảng `dungeon_run`: một hàng mỗi người — tầng đang đứng, checkpoint, HP pet,
   và trận đang đánh (`battle_id`, không FK cùng lý do `target_id`).
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "098_dungeon_tower"
down_revision: Union[str, None] = "097_eval_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

JSON = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column("petland_map", sa.Column("slug", sa.Text(), nullable=True))
    op.execute("UPDATE petland_map SET slug = 'main' WHERE slug IS NULL")
    op.alter_column("petland_map", "slug", nullable=False)
    op.drop_constraint("ck_petland_map_single_row", "petland_map")
    op.drop_constraint("petland_map_pkey", "petland_map", type_="primary")
    op.drop_column("petland_map", "id")
    op.create_primary_key("pk_petland_map", "petland_map", ["slug"])
    op.add_column("petland_map", sa.Column("portal_x", sa.SmallInteger(), nullable=True))
    op.add_column("petland_map", sa.Column("portal_y", sa.SmallInteger(), nullable=True))

    op.drop_constraint("ck_encounter_kind", "encounter", type_="check")
    op.create_check_constraint(
        "ck_encounter_kind",
        "encounter",
        "kind IN ('npc', 'intruder', 'rescue', 'dungeon')",
    )

    op.create_table(
        "dungeon_run",
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("floor", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("checkpoint", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("pet_hp", sa.SmallInteger(), nullable=False, server_default="20"),
        sa.Column("status", sa.String(16), nullable=False, server_default="fighting"),
        sa.Column("battle_id", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("floor >= 1 AND floor <= 100", name="ck_dungeon_run_floor"),
        sa.CheckConstraint(
            "checkpoint >= 1 AND checkpoint <= floor", name="ck_dungeon_run_checkpoint"
        ),
        sa.CheckConstraint("pet_hp >= 0", name="ck_dungeon_run_hp"),
        sa.CheckConstraint("status IN ('fighting', 'dead', 'done')", name="ck_dungeon_run_status"),
    )


def downgrade() -> None:
    op.drop_table("dungeon_run")
    op.drop_constraint("ck_encounter_kind", "encounter", type_="check")
    op.create_check_constraint(
        "ck_encounter_kind", "encounter", "kind IN ('npc', 'intruder', 'rescue')"
    )
    op.drop_constraint("pk_petland_map", "petland_map", type_="primary")
    op.add_column("petland_map", sa.Column("id", sa.SmallInteger(), nullable=True))
    op.execute("UPDATE petland_map SET id = 1 WHERE slug = 'main'")
    op.execute("DELETE FROM petland_map WHERE slug <> 'main'")
    op.alter_column("petland_map", "id", nullable=False)
    op.create_primary_key("petland_map_pkey", "petland_map", ["id"])
    op.create_check_constraint("ck_petland_map_single_row", "petland_map", "id = 1")
    op.drop_column("petland_map", "slug")
    op.drop_column("petland_map", "portal_x")
    op.drop_column("petland_map", "portal_y")
