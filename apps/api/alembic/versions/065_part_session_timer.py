"""part session timer — cột thời gian cho phiên luyện theo part

Revision ID: 065_part_session_timer
Revises: 064_part_sessions
Create Date: 2026-09-07 10:00:00.000000

Drill part chuyển từ "chọn số câu" sang "toàn bộ kho + đồng hồ", theo khuôn
khu luyện thi. 064 chưa lên production nên thêm cột vào thẳng bảng của nó là
không mất gì.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "065_part_session_timer"
down_revision: Union[str, None] = "064_part_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "part_session", sa.Column("time_limit_seconds", sa.Integer(), nullable=True)
    )
    op.add_column(
        "part_session",
        sa.Column("expired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("part_session", "expired")
    op.drop_column("part_session", "time_limit_seconds")
