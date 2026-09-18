"""Listening Lab library: flag bài public cho thư viện có sẵn.

Không di chuyển dữ liệu: cột mới default false nên mọi bài user đang có giữ
nguyên riêng tư — công khai là hành động chủ ý (seed script), không phải thứ
rơi ra từ một migration.

Revision ID: 090_listening_library
Revises: 089_listening_lab
Create Date: 2026-09-18 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "090_listening_library"
down_revision: Union[str, None] = "089_listening_lab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "listening_content",
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        op.f("ix_listening_content_is_public"), "listening_content", ["is_public"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_listening_content_is_public"), table_name="listening_content")
    op.drop_column("listening_content", "is_public")
