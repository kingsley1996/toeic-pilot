"""collocation_detail — siêu dữ liệu collocation của vocabulary_entry (1:1)

Revision ID: 079_collocation_detail
Revises: 078_part_video
Create Date: 2026-09-09 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "079_collocation_detail"
down_revision: Union[str, None] = "078_part_video"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PATTERNS = (
    "VERB_NOUN",
    "ADJ_PREP",
    "NOUN_NOUN",
    "VERB_PREP",
    "PREP_PHRASE",
    "ADJ_NOUN",
    "VERB_ADJ",
)


def upgrade() -> None:
    op.create_table(
        "collocation_detail",
        sa.Column("entry_id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "base_word",
            sa.Text(),
            nullable=False,
            comment="Lexical anchor để nhóm các cụm liên quan",
        ),
        sa.Column("gap_word", sa.Text(), nullable=True),
        sa.Column("pattern", sa.String(16), nullable=False),
        sa.Column("distractors", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["vocabulary_entry.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("trim(base_word) <> ''", name="ck_collocation_detail_base_word"),
        sa.CheckConstraint(
            "gap_word IS NULL OR (trim(gap_word) <> ''"
            " AND gap_word = replace(gap_word, ' ', ''))",
            name="ck_collocation_detail_gap_word",
        ),
        sa.CheckConstraint(
            "pattern IN (" + ", ".join(f"'{p}'" for p in _PATTERNS) + ")",
            name="ck_collocation_detail_pattern",
        ),
    )
    # Prefix base_word phục vụ query discovery chỉ theo base_word (§23).
    op.create_index(
        "ix_collocation_detail_base_word_pattern",
        "collocation_detail",
        ["base_word", "pattern"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_collocation_detail_base_word_pattern", table_name="collocation_detail"
    )
    op.drop_table("collocation_detail")
