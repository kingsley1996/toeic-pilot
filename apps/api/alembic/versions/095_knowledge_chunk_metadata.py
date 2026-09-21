"""Metadata cho chunk knowledge base (guides §5.1).

Revision ID: 095_knowledge_chunk_metadata
Revises: 094_pet_owned_weight
Create Date: 2026-09-21 00:00:00.000000

Năm cột nullable toàn bộ: hàng cũ giữ NULL nghĩa là "chưa khai", không phải dữ
liệu thiếu — nên không backfill, không default. `sync_knowledge` đọc từ
frontmatter file markdown; thiếu key thì giữ giá trị cũ và cảnh báo, không fail.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "095_knowledge_chunk_metadata"
down_revision: Union[str, None] = "094_pet_owned_weight"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("knowledge_chunk", sa.Column("source", sa.String(200), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("doc_type", sa.String(32), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("topic", sa.String(120), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("language", sa.String(8), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("content_version", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_chunk", "content_version")
    op.drop_column("knowledge_chunk", "language")
    op.drop_column("knowledge_chunk", "topic")
    op.drop_column("knowledge_chunk", "doc_type")
    op.drop_column("knowledge_chunk", "source")
