"""Listening Lab: video tự host cho bài TikTok.

TikTok chặn nhúng (overload-protect) lẫn hotlink CDN (403) nên bài TikTok
không phát được bằng URL gốc — cột này giữ storage key của file mp4 đã ingest
một lần, phát qua `<video>` của mình (seek/timeline như YouTube). NULL là chưa
ingest (dùng embed + link ngoài như cũ). Không di chuyển dữ liệu.

Revision ID: 091_listening_media
Revises: 090_listening_library
Create Date: 2026-09-19 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "091_listening_media"
down_revision: Union[str, None] = "090_listening_library"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listening_content", sa.Column("media_storage_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("listening_content", "media_storage_key")
