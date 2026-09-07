"""placement — điểm quy đổi tại tỉ lệ đúng thật, cạnh dải ước lượng

Revision ID: 070_placement_scaled
Revises: 069_planner_eval
Create Date: 2026-09-07 23:40:00.000000

Trung điểm của dải KHÔNG phải điểm quy đổi: đường cong `score_conversion` dốc
khác nhau từng khúc và dải bị kẹp ở 0 và n, nên ở hai cực trung điểm lệch hơn
20 điểm mỗi section. Giao diện chỉ có dải nên buộc phải lấy trung điểm; cột này
là để nó lấy đúng con số.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "070_placement_scaled"
down_revision: Union[str, None] = "069_planner_eval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for section in ("listening", "reading"):
        op.add_column(
            "placement_result",
            sa.Column(f"{section}_scaled", sa.SmallInteger(), nullable=True),
        )
    # Hàng cũ không có con số thật để điền — trung điểm của dải là ước lượng
    # tốt nhất còn lại, và là đúng thứ giao diện đang hiện cho chúng.
    op.execute(
        "UPDATE placement_result SET "
        "listening_scaled = (listening_low + listening_high) / 2, "
        "reading_scaled = (reading_low + reading_high) / 2"
    )
    for section in ("listening", "reading"):
        op.alter_column("placement_result", f"{section}_scaled", nullable=False)


def downgrade() -> None:
    op.drop_column("placement_result", "reading_scaled")
    op.drop_column("placement_result", "listening_scaled")
