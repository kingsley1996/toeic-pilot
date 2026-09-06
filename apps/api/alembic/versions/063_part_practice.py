"""part practice — chiến thuật trong DB + lượt làm câu rời theo part

Revision ID: 063_part_practice
Revises: 062_grammar_completion_revoked
Create Date: 2026-09-06 18:00:00.000000

`part_tactics`: nội dung chiến thuật Part 1–7 vào DB thay vì đọc từ đĩa —
production web chỉ chứa code đã build, và "sửa một trang không đáng một deploy"
là đúng lý do grammar lesson đã nằm trong DB. Nguồn soạn vẫn là markdown ở
`apps/web/content/parts/`, đường một chiều md → DB qua `scripts/sync-parts.sh`.

`part_drill_attempt`: bản sao hình của `grammar_attempt` nhưng là bảng riêng —
bảng grammar đang nuôi XP/streak/daily task của module ngữ pháp, trộn thêm
nguồn "luyện part" vào đó bắt mọi truy vấn hiện tại phải nhớ lọc `source`.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "063_part_practice"
down_revision: Union[str, None] = "062_grammar_completion_revoked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "part_tactics",
        sa.Column("part", sa.SmallInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("part", name="pk_part_tactics"),
    )
    op.create_table(
        "part_drill_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=True),
        sa.Column("part", sa.SmallInteger(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_part_drill_attempt"),
        sa.CheckConstraint("part BETWEEN 1 AND 7", name="ck_part_drill_attempt_part"),
    )
    op.create_index("ix_part_drill_attempt_user", "part_drill_attempt", ["user_id"])
    op.create_index("ix_part_drill_attempt_part", "part_drill_attempt", ["part"])


def downgrade() -> None:
    op.drop_table("part_drill_attempt")
    op.drop_table("part_tactics")
