"""Bảng `eval_run` — lượt chạy eval AI từ giao diện (P2 UI).

Revision ID: 097_eval_run
Revises: 096_ai_interaction_telemetry
Create Date: 2026-09-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "097_eval_run"
down_revision: str | None = "096_ai_interaction_telemetry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "eval_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("suite", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("triggered_by", sa.Uuid(), nullable=True),
        sa.Column("params", JSONB(), nullable=True),
        sa.Column("report", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'error')", name="ck_eval_run_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("eval_run")
