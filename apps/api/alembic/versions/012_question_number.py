"""Số câu chính thức trên practice_test_question

Revision ID: 012_question_number
Revises: 011_mock_test
Create Date: 2026-08-10

`position` là thứ tự trình bày, `number` là con số người học nhìn thấy. Với đề
đầy đủ hai thứ trùng nhau; với đề rút gọn thì không, và trước migration này
`attempt.py` đánh số lại từ 1 nên luyện riêng Part 5 hiện "câu 1-30" trong khi
mọi tài liệu gọi chúng là 101-130 (ADR-007 §2.6).
"""

import typing

import sqlalchemy as sa
from alembic import op

revision: str = "012_question_number"
down_revision: typing.Union[str, None] = "011_mock_test"
branch_labels: typing.Union[str, typing.Sequence[str], None] = None
depends_on: typing.Union[str, typing.Sequence[str], None] = None


def upgrade() -> None:
    # Thêm nullable rồi backfill rồi mới siết NOT NULL: cột NOT NULL không
    # server_default sẽ chết ngay trên bảng đang có dữ liệu.
    op.add_column(
        "practice_test_question",
        sa.Column("number", sa.SmallInteger(), nullable=True),
    )
    # Đề đang có là đề demo rút gọn, và với nó `position` chính là số câu đang
    # hiển thị. Chép sang để không có hàng nào mất số; người soạn chỉnh lại sau.
    op.execute("UPDATE practice_test_question SET number = position WHERE number IS NULL")
    op.alter_column("practice_test_question", "number", nullable=False)
    op.create_unique_constraint(
        "uq_practice_test_question_number",
        "practice_test_question",
        ["test_id", "number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_practice_test_question_number", "practice_test_question", type_="unique"
    )
    op.drop_column("practice_test_question", "number")
