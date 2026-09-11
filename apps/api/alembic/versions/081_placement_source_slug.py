"""Nguồn của đề placement.

`practice_test.source_slug` (nullable): đề mà `make_placement` đã rút 84 câu
ra — màn `/admin/placement` hiển thị trên card để nhóm đề đầu vào không còn là
mấy cái tên suông. Chuỗi thuần, không FK: dấu vết xuất xứ, không ràng buộc sống.

Revision ID: 081_placement_source_slug
Revises: 080_collection_item_cover
Create Date: 2026-09-11 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "081_placement_source_slug"
down_revision: Union[str, None] = "080_collection_item_cover"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("practice_test", sa.Column("source_slug", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("practice_test", "source_slug")
