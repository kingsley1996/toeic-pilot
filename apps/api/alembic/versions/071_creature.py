"""creature — phân vai ô sinh vật xuống database, thay bảng tĩnh của frontend

Revision ID: 071_creature
Revises: 070_placement_scaled
Create Date: 2026-09-07 23:55:00.000000

`petland-bestiary.ts` hứa từ ngày viết: khi phân vai thành thứ người vận hành
cân chỉnh thì nó phải xuống database như `pet_species` đã xuống. Màn
`/admin/petland/creatures` là cái cò của lời hứa đó. Bảng gieo LƯỜI 180 hàng ở
lần đọc đầu — migration chỉ dựng khung, nên downgrade chỉ drop, không mất dữ
liệu cấu hình nào ngoài chính nó.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "071_creature"
down_revision: Union[str, None] = "070_placement_scaled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "creature",
        sa.Column("tile", sa.SmallInteger(), primary_key=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.CheckConstraint("tile >= 0 AND tile < 180", name="ck_creature_tile"),
        sa.CheckConstraint(
            "role IN ('npc', 'wildlife', 'intruder')", name="ck_creature_role"
        ),
    )


def downgrade() -> None:
    op.drop_table("creature")
