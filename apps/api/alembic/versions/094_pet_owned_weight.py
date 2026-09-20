"""Petland: cân nặng động từng con (`pet_owned.weight_grams` + `weight_at`).

Cho ăn thì +1% cân chuẩn, đói thì tụt dần — cùng khuôn `needs_at`: cột giữ ảnh
chụp tại mốc, giá trị bây giờ suy ra lúc đọc. NULL nghĩa là chưa ăn lần nào kể
từ khi có cột, hiển thị bằng cân chuẩn của loài.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "094_pet_owned_weight"
down_revision: Union[str, None] = "093_pet_species_weight"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pet_owned", sa.Column("weight_grams", sa.Integer(), nullable=True))
    op.add_column("pet_owned", sa.Column("weight_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("pet_owned", "weight_at")
    op.drop_column("pet_owned", "weight_grams")
