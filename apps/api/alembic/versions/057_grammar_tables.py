"""grammar tables — SPEC-GRAMMAR.md §4

Revision ID: 057_grammar_tables
Revises: 056_profile_toured_at
Create Date: 2026-09-05 10:00:00.000000

Module thứ năm: bài học ngữ pháp theo chủ đề. Hai tầng (topic → lesson), không
phải bốn như dictation — một bài ngữ pháp không phải đơn vị audio.

`grammar_topic.code` là khoá ngoại LOGIC vào facet `grammar` của taxonomy
(`services/labels.py`), kiểm ở endpoint bằng cùng hàm `enrich_skills` dùng —
không phải FK DB vì mã nhãn sống trong mã, và một FK trỏ vào hư không vẫn là
hư không.

Bài tập LÀ hàng `question` qua bảng nối, không phải loại nội dung mới: dùng lại
`validate_question`, options, màn soạn đề, cổng publish của khu luyện thi.

`grammar_attempt.option_id` là SET NULL vì admin editor xoá-and-tạo lại options
mỗi lần lưu; RESTRICT ở đó biến mỗi lượt sửa một câu đã có người làm thành 500.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "057_grammar_tables"
down_revision: Union[str, None] = "056_profile_toured_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grammar_topic",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('draft', 'published', 'archived')", name="ck_grammar_topic_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_grammar_topic_status"), "grammar_topic", ["status"], unique=False)
    op.create_table(
        "grammar_lesson",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('draft', 'published', 'archived')", name="ck_grammar_lesson_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["grammar_topic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_grammar_lesson_status"), "grammar_lesson", ["status"], unique=False)
    op.create_index(
        op.f("ix_grammar_lesson_topic_id"), "grammar_lesson", ["topic_id"], unique=False
    )
    op.create_table(
        "grammar_lesson_question",
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 1", name="ck_grammar_lesson_question_position"
        ),
        sa.ForeignKeyConstraint(["lesson_id"], ["grammar_lesson.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("lesson_id", "question_id"),
    )
    op.create_table(
        "grammar_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["option_id"], ["question_option.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_grammar_attempt_user_id"), "grammar_attempt", ["user_id"], unique=False
    )
    op.create_index(
        "ix_grammar_attempt_user_question", "grammar_attempt", ["user_id", "question_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_grammar_attempt_user_question", table_name="grammar_attempt")
    op.drop_index(op.f("ix_grammar_attempt_user_id"), table_name="grammar_attempt")
    op.drop_table("grammar_attempt")
    op.drop_table("grammar_lesson_question")
    op.drop_index(op.f("ix_grammar_lesson_topic_id"), table_name="grammar_lesson")
    op.drop_index(op.f("ix_grammar_lesson_status"), table_name="grammar_lesson")
    op.drop_table("grammar_lesson")
    op.drop_index(op.f("ix_grammar_topic_status"), table_name="grammar_topic")
    op.drop_table("grammar_topic")
