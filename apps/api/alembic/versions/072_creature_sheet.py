"""pet_species.sheet — ô chỉ có nghĩa khi biết nó thuộc tấm nào

Revision ID: 072_creature_sheet
Revises: 071_creature
Create Date: 2026-09-07 22:10:00.000000

Không có cột này thì ô 5 của `dinos.png` và ô 5 của `creatures.png` là cùng một
hàng dữ liệu. Ràng buộc `tile < 180` cũng phải nới: trần trên phụ thuộc tấm, mà
database không biết tấm nào bao nhiêu ô — nó nằm ở `CREATURE_SHEET_TILES` và
được cưỡng chế ở tầng schema.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "072_creature_sheet"
down_revision: Union[str, None] = "071_creature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pet_species",
        sa.Column("sheet", sa.String(length=16), nullable=False, server_default="creatures"),
    )
    op.drop_constraint("ck_pet_species_tile", "pet_species", type_="check")
    op.create_check_constraint("ck_pet_species_tile", "pet_species", "tile >= 0")


def downgrade() -> None:
    # Hàng của tấm khác `creatures` không quay lui được — ô của chúng vô nghĩa
    # khi cột `sheet` biến mất, và giữ lại thì chúng trỏ nhầm vào tấm gốc.
    op.execute("DELETE FROM pet_species WHERE sheet <> 'creatures'")
    op.drop_constraint("ck_pet_species_tile", "pet_species", type_="check")
    op.create_check_constraint("ck_pet_species_tile", "pet_species", "tile >= 0 AND tile < 180")
    op.drop_column("pet_species", "sheet")
