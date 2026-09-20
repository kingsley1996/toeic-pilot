"""Petland: cân nặng từng loài (`pet_species.weight_grams`).

Số liệu điền bằng backfill ở `pet_species.all_species` (map
`SPECIES_WEIGHT_GRAMS`), không ở đây: migration đóng băng theo thời gian còn
cân nặng là dữ liệu admin sửa được — ghi số vào DDL là chôn một bản sao.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "093_pet_species_weight"
down_revision: Union[str, None] = "092_listening_segment_vi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pet_species", sa.Column("weight_grams", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("pet_species", "weight_grams")
