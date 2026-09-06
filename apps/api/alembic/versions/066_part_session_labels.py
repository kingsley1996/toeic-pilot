"""part session labels — một phiên chọn NHIỀU nhãn, theo khuôn checkbox đề thi

Revision ID: 066_part_session_labels
Revises: 065_part_session_timer
Create Date: 2026-09-07 14:00:00.000000

`label` một mã đổi thành `labels` JSON (rỗng = tất cả) khi màn setup chuyển
sang checkbox như khu luyện thi. 064–065 chưa lên production; dev chỉ có vài
phiên smoke test — chuyển dữ liệu cũ là một phép gán có điều kiện.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "066_part_session_labels"
down_revision: Union[str, None] = "065_part_session_timer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "part_session",
        sa.Column("labels", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.execute(
        "UPDATE part_session SET labels = jsonb_build_array(label) WHERE label IS NOT NULL"
    )
    op.drop_column("part_session", "label")


def downgrade() -> None:
    op.add_column("part_session", sa.Column("label", sa.String(length=48), nullable=True))
    op.execute(
        "UPDATE part_session SET label = labels ->> 0 WHERE jsonb_array_length(labels) > 0"
    )
    op.drop_column("part_session", "labels")
