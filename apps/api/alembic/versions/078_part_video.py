"""part_tactics video chiến thuật — hai cột nullable (khuôn SPEC-GRAMMAR-VIDEO)

Revision ID: 078_part_video
Revises: 077_grammar_video
Create Date: 2026-09-09 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "078_part_video"
down_revision: Union[str, None] = "077_grammar_video"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("part_tactics", sa.Column("video_storage_key", sa.String(512), nullable=True))
    op.add_column("part_tactics", sa.Column("video_duration_s", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("part_tactics", "video_duration_s")
    op.drop_column("part_tactics", "video_storage_key")
