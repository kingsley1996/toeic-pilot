"""Tranh cho khung avatar và huy hiệu

Revision ID: 033_progression_art
Revises: 032_progression_config
Create Date: 2026-08-22 09:00:00.000000

Khoá thô dưới tiền tố `progression/`, không phải hàng trong `image_asset`: ba cột
`license`, `attribution`, `source_url` của bảng đó là NOT NULL vì ảnh nội dung
phần lớn là CC-BY và phải ghi công. Tranh khung/huy hiệu là tài sản của chính sản
phẩm — cùng loại với avatar, và avatar cũng lưu khoá thô vì đúng lý do này.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "033_progression_art"
down_revision: str | None = "032_progression_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("frame_tier", sa.Column("image_storage_key", sa.String(length=255), nullable=True))
    op.add_column("badge_rule", sa.Column("image_storage_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("badge_rule", "image_storage_key")
    op.drop_column("frame_tier", "image_storage_key")
