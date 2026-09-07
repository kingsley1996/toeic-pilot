"""pet_species.lines — bộ lời thoại riêng của loài (huyền thoại trở lên)

Revision ID: 073_pet_lines
Revises: 072_creature_sheet
Create Date: 2026-09-08 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "073_pet_lines"
down_revision: Union[str, None] = "072_creature_sheet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pet_species", sa.Column("lines", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("pet_species", "lines")
