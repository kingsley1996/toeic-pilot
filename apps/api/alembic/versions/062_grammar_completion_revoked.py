"""grammar completion revoked_at — bỏ hoàn thành là đánh dấu, không phải xoá

Hàng completion đang nuôi hai thứ xung đột nhau: daily task (phải ngừng đếm
khi người ta gỡ dấu) và chuỗi ngày (không được phép rút lại quá khứ khi một
hàng biến mất). `revoked_at` tách hai câu hỏi: "nó từng xảy ra hôm nào" trả lời
bằng `created_at` và bất biến, "nó còn hiệu lực không" trả lời bằng cột mới.

Bấm lại một bài đã gỡ dấu KHÔNG dời `created_at` — đó cũng là lúc kẽ hở "bấm
lại bài cũ tính là bài của hôm nay" đóng lại.

Revision ID: 062_grammar_completion_revoked
Revises: 061_grammar_xp
Create Date: 2026-09-06 15:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "062_grammar_completion_revoked"
down_revision: Union[str, None] = "061_grammar_xp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "grammar_lesson_completion", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.execute("DELETE FROM grammar_lesson_completion WHERE revoked_at IS NOT NULL")
    op.drop_column("grammar_lesson_completion", "revoked_at")
