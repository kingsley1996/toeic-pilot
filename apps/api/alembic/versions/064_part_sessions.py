"""part sessions — phiên luyện theo part thay cho lượt rời

Revision ID: 064_part_sessions
Revises: 063_part_practice
Create Date: 2026-09-06 20:00:00.000000

`part_drill_attempt` (063) sống đúng một ngày: drill đổi sang mô hình PHIÊN
theo khuôn `attempt`/`attempt_item` — câu chốt lúc bắt đầu, xem lại được.
063 chưa kịp lên production nên drop ở đây không mất gì; dev có vài hàng smoke
test, và đó chính xác là loại dữ liệu được phép bỏ.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "064_part_sessions"
down_revision: Union[str, None] = "063_part_practice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `if_exists`: bản 063 có thể chưa từng chạy trên một DB nào đó (064 đi kèm
    # ngay trong cùng đợt phát triển), và DB dev đã được dọn tay trước khi
    # migration này kịp chạy ở đó.
    op.drop_table("part_drill_attempt", if_exists=True)
    op.create_table(
        "part_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("part", sa.SmallInteger(), nullable=False),
        sa.Column("label", sa.String(length=48), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_part_session"),
        sa.CheckConstraint("part BETWEEN 1 AND 7", name="ck_part_session_part"),
    )
    op.create_index("ix_part_session_user", "part_session", ["user_id"])
    op.create_table(
        "part_session_item",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["part_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["option_id"], ["question_option.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("session_id", "question_id", name="pk_part_session_item"),
        sa.UniqueConstraint("session_id", "question_id", name="uq_part_session_item_question"),
    )


def downgrade() -> None:
    op.drop_table("part_session_item")
    op.drop_index("ix_part_session_user", table_name="part_session")
    op.drop_table("part_session")
    op.create_table(
        "part_drill_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=True),
        sa.Column("part", sa.SmallInteger(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["option_id"], ["question_option.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_part_drill_attempt"),
        sa.CheckConstraint("part BETWEEN 1 AND 7", name="ck_part_drill_attempt_part"),
    )
