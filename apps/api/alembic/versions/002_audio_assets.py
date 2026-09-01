"""Audio assets.

Content-addressed store of synthesised audio. See planning/docs/PHASE2-AUDIO.md.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_audio_assets"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("voice", sa.String(length=32), nullable=False),
        sa.Column("accent", sa.String(length=8), nullable=False),
        sa.Column(
            "source_text",
            sa.Text(),
            nullable=True,
            comment=(
                "Text fed to TTS, for re-derivation only. NOT the grading answer key — "
                "dictation grades against dictation_item.transcript."
            ),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('tts', 'scraped', 'uploaded')",
            name="ck_audio_asset_source",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    # Unique index rather than a second UNIQUE constraint: the model declares
    # unique=True, index=True, which yields exactly one index. Declaring both
    # would leave Postgres maintaining two identical btrees on every insert.
    op.create_index(
        op.f("ix_audio_asset_source_hash"), "audio_asset", ["source_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audio_asset_source_hash"), table_name="audio_asset")
    op.drop_table("audio_asset")
