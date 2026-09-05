"""grammar lesson completion — dấu "đã học xong bài"

Revision ID: 058_grammar_lesson_completion
Revises: 057_grammar_tables
Create Date: 2026-09-05 14:00:00.000000

Khóa chính là cặp (user, lesson): hai lần bấm "Hoàn thành" là một hàng, không
phải hai — endpoint INSERT phải chịu được bấm đúp mà không cần đọc-trước-ghi.

`created_at` mang thời điểm, không chỉ có/không: "chủ đề này học xong hôm nào"
là câu hỏi sẽ có người hỏi khi thêm chuỗi ngày (G5).
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "058_grammar_lesson_completion"
down_revision: Union[str, None] = "057_grammar_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "grammar_lesson_completion",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["grammar_lesson.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "lesson_id"),
    )


def downgrade() -> None:
    op.drop_table("grammar_lesson_completion")
