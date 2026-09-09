"""grammar_lesson video bài giảng — hai cột nullable (SPEC-GRAMMAR-VIDEO §2)

Revision ID: 077_grammar_video
Revises: 076_seed_ruby_rules
Create Date: 2026-09-09 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "077_grammar_video"
down_revision: Union[str, None] = "076_seed_ruby_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("grammar_lesson", sa.Column("video_storage_key", sa.String(512), nullable=True))
    op.add_column("grammar_lesson", sa.Column("video_duration_s", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("grammar_lesson", "video_duration_s")
    op.drop_column("grammar_lesson", "video_storage_key")
