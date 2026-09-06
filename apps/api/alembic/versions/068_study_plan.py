"""study plan — kế hoạch học sinh từ placement (SPEC-PLACEMENT lát 2)

Revision ID: 068_study_plan
Revises: 067_placement
Create Date: 2026-09-07 21:00:00.000000

Một người một kế hoạch hiện hành (partial unique index trên is_current);
tiến độ KHÔNG lưu cột — suy từ bản ghi học thật lúc đọc (SPEC-PLACEMENT §6).
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "068_study_plan"
down_revision: Union[str, None] = "067_placement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "study_plan",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("placement_attempt_id", UUID(), nullable=False),
        sa.Column("target_score", sa.SmallInteger(), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="rule"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["placement_attempt_id"], ["attempt.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_study_plan"),
    )
    op.create_index("ix_study_plan_user", "study_plan", ["user_id"])
    op.create_index(
        "uq_study_plan_current",
        "study_plan",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "study_plan_item",
        sa.Column("plan_id", UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("part", sa.SmallInteger(), nullable=False),
        sa.Column("ref_id", UUID(), nullable=True),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_id", "position", name="pk_study_plan_item"),
        sa.CheckConstraint("kind IN ('grammar_lesson', 'part_drill')", name="ck_study_plan_item_kind"),
        sa.UniqueConstraint("plan_id", "position", name="uq_study_plan_item_position"),
    )


def downgrade() -> None:
    op.drop_table("study_plan_item")
    op.drop_index("uq_study_plan_current", table_name="study_plan")
    op.drop_index("ix_study_plan_user", table_name="study_plan")
    op.drop_table("study_plan")
