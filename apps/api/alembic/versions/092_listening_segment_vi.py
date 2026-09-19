"""Listening Lab: bản dịch tiếng Việt từng câu transcript.

Học viên chép được câu vẫn có thể không hiểu nó nói gì — dictation đo NGHE
ra chữ, không đo hiểu. `DictationItem.transcript_vi` đã có tiền lệ này; segment
video thiếu nó nên bài nghe video kém một nửa so với dictation soạn sẵn.

NULL là chưa dịch (học được như cũ), không phải dữ liệu hỏng.

Revision ID: 092_listening_segment_vi
Revises: 091_listening_media
Create Date: 2026-09-19 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "092_listening_segment_vi"
down_revision: Union[str, None] = "091_listening_media"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listening_segment", sa.Column("text_vi", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("listening_segment", "text_vi")
