"""Cờ "đã xem đáp án" cho lượt dictation và listening.

Revision ID: 100_attempt_revealed
Revises: 099_blog_post
Create Date: 2026-10-20 00:00:00.000000

Cột riêng thay vì suy từ `is_complete`: bài gõ vẫn được chấm đúng sự thật (để
hiển thị diff), nhưng tiến độ/XP phải bỏ qua lượt đã mở đáp án. Mặc định false
để mọi lượt cũ giữ nguyên nghĩa.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "100_attempt_revealed"
down_revision: str | None = "099_blog_post"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    for table in ("dictation_attempt", "listening_attempt"):
        op.add_column(
            table,
            sa.Column(
                "revealed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    for table in ("listening_attempt", "dictation_attempt"):
        op.drop_column(table, "revealed")
