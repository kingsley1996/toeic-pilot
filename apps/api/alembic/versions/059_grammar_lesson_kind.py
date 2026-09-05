"""grammar lesson kind — lý thuyết vs luyện tập (SPEC-GRAMMAR §2, G4)

Revision ID: 059_grammar_lesson_kind
Revises: 058_grammar_lesson_completion
Create Date: 2026-09-05 16:00:00.000000

Một chủ đề có nhiều BÀI LUYỆN TẬP, và chúng là lesson đúng nghĩa — xuất hiện
trong danh sách bài, đếm vào tiến độ — chứ không phải một lối đi riêng. `kind`
tách hai hình dạng:

- `theory`: có `body`, Hoàn thành là dấu tay của người học (bảng
  `grammar_lesson_completion`).
- `practice`: không body, câu lấy từ `grammar_lesson_question`, hoàn thành SUY
  RA từ `grammar_attempt` — không có nút để bấm mà chưa làm.

server_default 'theory' để toàn bộ lesson đang có giữ nguyên nghĩa; CHECK đóng
tập giá trị vì `kind` chọn ĐƯỜNG ĐI của code, một chữ sai là bài rơi vào renderer
của loại kia.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "059_grammar_lesson_kind"
down_revision: Union[str, None] = "058_grammar_lesson_completion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "grammar_lesson",
        sa.Column("kind", sa.String(length=16), server_default="theory", nullable=False),
    )
    op.create_check_constraint(
        "ck_grammar_lesson_kind", "grammar_lesson", "kind IN ('theory', 'practice')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_grammar_lesson_kind", "grammar_lesson", type_="check")
    op.drop_column("grammar_lesson", "kind")
