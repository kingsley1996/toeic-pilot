"""Lời thoại và thời điểm gắn audio cho Part 1-4

Revision ID: 014_audio_script
Revises: 013_passage_images
Create Date: 2026-08-11

Part 1 và 2 không in gì cả — ETS chỉ đọc lên — nên `prompt_text` và
`question_option.content` đều phải NULL. Thứ biên tập viên gõ vào chính là lời
thoại, và trước migration này nó không có chỗ nào để ở (ADR-007 §2.1).

`audio_attached_at` là cột riêng chứ không so với `audio_asset.created_at`: gắn
một bản thu cũ vào câu vừa sửa sẽ báo lệch oan, mà cảnh báo oan là cách nhanh
nhất dạy người ta bấm bỏ qua mọi cảnh báo (§2.7). Nó dùng để HIỂN THỊ "gắn lúc
nào"; thứ trả lời "bản thu còn khớp không" là `audio_script_hash`, vì so hai mốc
thời gian là so hai chiếc đồng hồ khác nhau — xem `script_fingerprint`.
"""

import typing

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_audio_script"
down_revision: typing.Union[str, None] = "013_passage_images"
branch_labels: typing.Union[str, typing.Sequence[str], None] = None
depends_on: typing.Union[str, typing.Sequence[str], None] = None

_TABLES = ("question", "question_set")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("audio_script", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        op.add_column(
            table, sa.Column("audio_attached_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.add_column(table, sa.Column("audio_script_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "audio_script_hash")
        op.drop_column(table, "audio_attached_at")
        op.drop_column(table, "audio_script")
