"""placement — bảng kết quả xếp lớp + cờ đề placement

Revision ID: 067_placement
Revises: 066_part_session_labels
Create Date: 2026-09-07 18:00:00.000000

SPEC-PLACEMENT: đề placement tái dùng máy thi (practice_test kind='mini' +
is_placement), kết quả là SNAPSHOT gắn lượt làm — ước lượng v1 và v2 cho cùng
một lượt khác nhau, nên phán quyết của thời điểm chấm nằm lại bảng này.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "067_placement"
down_revision: Union[str, None] = "066_part_session_labels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "practice_test",
        sa.Column("is_placement", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "placement_result",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("estimator_version", sa.String(length=16), nullable=False),
        sa.Column("listening_raw", sa.SmallInteger(), nullable=False),
        sa.Column("reading_raw", sa.SmallInteger(), nullable=False),
        sa.Column("listening_low", sa.SmallInteger(), nullable=False),
        sa.Column("listening_high", sa.SmallInteger(), nullable=False),
        sa.Column("reading_low", sa.SmallInteger(), nullable=False),
        sa.Column("reading_high", sa.SmallInteger(), nullable=False),
        sa.Column("cefr_listening", sa.String(length=2), nullable=False),
        sa.Column("cefr_reading", sa.String(length=2), nullable=False),
        sa.Column("cefr_overall", sa.String(length=2), nullable=False),
        sa.Column("self_reported_score", sa.SmallInteger(), nullable=True),
        sa.Column("target_score", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempt.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_placement_result"),
    )
    op.create_index("ix_placement_result_user", "placement_result", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_placement_result_user", table_name="placement_result")
    op.drop_table("placement_result")
    op.drop_column("practice_test", "is_placement")
