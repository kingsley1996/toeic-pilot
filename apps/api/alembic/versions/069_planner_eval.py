"""planner eval — bảng kết quả so sánh V1/V2 (SPEC-PLACEMENT §5)

Revision ID: 069_planner_eval
Revises: 068_study_plan
Create Date: 2026-09-07 23:00:00.000000

Chạy V2 là một lượt gọi model thật (tiền + ~54 giây), nên kết quả so sánh
LƯU vào bảng này; GET chỉ đọc. Không tính lại lúc đọc.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "069_planner_eval"
down_revision: Union[str, None] = "068_study_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planner_eval",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("weak_count", sa.SmallInteger(), nullable=False),
        sa.Column("v1_items", JSONB(), nullable=False),
        sa.Column("v2_items", JSONB(), nullable=True),
        sa.Column("coverage", sa.Numeric(5, 4), nullable=True),
        sa.Column("dangling", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.SmallInteger(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempt.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_planner_eval"),
    )
    op.create_index("ix_planner_eval_attempt", "planner_eval", ["attempt_id"])
    op.create_index("ix_planner_eval_user", "planner_eval", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_planner_eval_user", table_name="planner_eval")
    op.drop_index("ix_planner_eval_attempt", table_name="planner_eval")
    op.drop_table("planner_eval")
