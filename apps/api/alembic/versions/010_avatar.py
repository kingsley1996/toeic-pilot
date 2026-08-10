"""avatar cho hồ sơ người dùng

Revision ID: 010_avatar
Revises: 009_user_profile
Create Date: 2026-08-10 17:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_avatar"
down_revision: Union[str, None] = "009_user_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, và ảnh chữ cái đầu vẫn là mặc định (ADR-006 §2.7). Cột này vừa
    # là "chưa tải lên", vừa là chỗ để rơi về khi một ảnh bị gỡ — nên NULL phải
    # là một trạng thái bình thường, không phải dữ liệu thiếu.
    #
    # KHÔNG có hàng `image_asset` đi kèm: avatar là media của NGƯỜI DÙNG, không
    # phải media nội dung. Nó không có bản quyền để ghi, không qua cổng duyệt,
    # và phải xoá được cùng tài khoản (ADR-006 §2.1).
    op.add_column("user_profile", sa.Column("avatar_storage_key", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profile", "avatar_storage_key")
