"""vocabulary topic session: học tới đâu được lưu trên server

Revision ID: 026_vocabulary_topic_session
Revises: 025_review_log_grade_mastered
Create Date: 2026-08-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "026_vocabulary_topic_session"
down_revision: str | None = "025_review_log_grade_mastered"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_topic_session",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        # Danh sách id của từ theo thứ tự học, không phải FK: từ bị gỡ khỏi chủ
        # đề thì id thành mồ côi, phía đọc so với hồ từ hiện tại và xáo lại nếu
        # lệch. FK vào entry ở đây sẽ chặn việc gỡ từ còn dang dở trong một bàn cờ.
        sa.Column(
            "entry_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "topic_id"),
    )


def downgrade() -> None:
    op.drop_table("vocabulary_topic_session")
