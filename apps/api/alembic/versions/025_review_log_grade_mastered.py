"""widen vocabulary_review_log grade to 0-6 (mastered)

Revision ID: 025_review_log_grade_mastered
Revises: 024_vocabulary_tree
Create Date: 2026-08-17 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_review_log_grade_mastered"
down_revision: str | None = "024_vocabulary_tree"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "ck_vocabulary_review_log_grade"


def upgrade() -> None:
    # Nút "Thành thạo" ghi grade 6. CHECK cũ chặn 6 lại nên phải nới rộng —
    # drop rồi add lại, PostgreSQL không có ALTER CHECK.
    op.drop_constraint(_OLD, "vocabulary_review_log", type_="check")
    op.create_check_constraint(
        _OLD, "vocabulary_review_log", "grade BETWEEN 0 AND 6"
    )


def downgrade() -> None:
    # Siết lại 0-5: nếu đã có dòng log grade=6 (ai đó bấm "Thành thạo") thì
    # downgrade sẽ lỗi CHECK — đúng, đó là dữ liệu không còn hợp lệ với bản cũ,
    # và fail to thay vì âm thầm để log hỏng là hành vi mong muốn.
    op.drop_constraint(_OLD, "vocabulary_review_log", type_="check")
    op.create_check_constraint(_OLD, "vocabulary_review_log", "grade BETWEEN 0 AND 5")
