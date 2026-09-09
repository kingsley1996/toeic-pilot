"""Cover image cho cuốn sách từ vựng.

`vocabulary_collection_item.image_id` → `image_asset` (nullable): ảnh cover của
bộ thẻ trên trang từ vựng, đi cùng đường ống ticket → POST → confirm của
ADR-006. `ON DELETE SET NULL`: xoá ảnh không được xoá cuốn sách — card chỉ
mất ảnh, quay về placeholder.

Revision ID: 080_collection_item_cover
Revises: 079_collocation_detail
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "080_collection_item_cover"
down_revision: Union[str, None] = "079_collocation_detail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vocabulary_collection_item",
        sa.Column("image_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_vocabulary_collection_item_image",
        "vocabulary_collection_item",
        "image_asset",
        ["image_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_vocabulary_collection_item_image", "vocabulary_collection_item", type_="foreignkey"
    )
    op.drop_column("vocabulary_collection_item", "image_id")
