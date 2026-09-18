"""Listening Lab (YouTube-first): content + segment + attempt do user tự tạo.

Không di chuyển dữ liệu: ba bảng mới hoàn toàn, cây dictation cũ không đụng.

Revision ID: 089_listening_lab
Revises: 088_streak_date_indexes
Create Date: 2026-09-18 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "089_listening_lab"
down_revision: Union[str, None] = "088_streak_date_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Khoá ngoại đặt tên tường minh (bài học ở 007): autogenerate để Postgres tự
    # đặt tên thì cặp `drop_constraint` ở downgrade không bao giờ chạy được.
    op.create_table(
        "listening_content",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript_status", sa.String(length=16), nullable=False),
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
        sa.CheckConstraint(
            "source_type IN ('youtube', 'tiktok', 'upload')",
            name="ck_listening_content_source",
        ),
        sa.CheckConstraint(
            "transcript_status IN ('pending', 'ready', 'failed')",
            name="ck_listening_content_transcript_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_listening_content_user",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_listening_content_user_id"), "listening_content", ["user_id"], unique=False
    )
    op.create_index(
        "ix_listening_content_user_created",
        "listening_content",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "listening_segment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("end_seconds", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.CheckConstraint("start_seconds >= 0", name="ck_listening_segment_start"),
        sa.CheckConstraint("end_seconds > start_seconds", name="ck_listening_segment_end"),
        sa.ForeignKeyConstraint(
            ["content_id"], ["listening_content.id"], name="fk_listening_segment_content",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_listening_segment_content_order",
        "listening_segment",
        ["content_id", "segment_index"],
        unique=False,
    )

    op.create_table(
        "listening_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("segment_id", sa.Uuid(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_complete", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("accuracy", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "word_diff",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("accuracy BETWEEN 0 AND 100", name="ck_listening_attempt_accuracy"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_listening_attempt_user",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["segment_id"], ["listening_segment.id"], name="fk_listening_attempt_segment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_listening_attempt_user_id"), "listening_attempt", ["user_id"], unique=False
    )
    op.create_index(
        "ix_listening_attempt_user_created",
        "listening_attempt",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_listening_attempt_user_created", table_name="listening_attempt")
    op.drop_index(op.f("ix_listening_attempt_user_id"), table_name="listening_attempt")
    op.drop_table("listening_attempt")
    op.drop_index("ix_listening_segment_content_order", table_name="listening_segment")
    op.drop_table("listening_segment")
    op.drop_index("ix_listening_content_user_created", table_name="listening_content")
    op.drop_index(op.f("ix_listening_content_user_id"), table_name="listening_content")
    op.drop_table("listening_content")
