"""bản đồ Petland sửa và lưu được trên web

Revision ID: 048_petland_map
Revises: 047_pet_tier_god
Create Date: 2026-08-29 09:00:00.000000

Trình vẽ bản đồ trước đây TẢI TỆP VỀ và người sửa phải commit nó. Quyết định ấy
có lý do — bản đồ là nội dung, và nội dung thuộc về git — nhưng nó được đưa ra
khi chưa có production. Nay sửa một ô cỏ phải đi qua một lần deploy.

Một hàng, không phải nhiều: bản đồ là số ít. `id` bị CHECK ép bằng 1 nên không
thể có hàng thứ hai lặng lẽ xuất hiện rồi không ai biết hàng nào đang chạy.

Bảng RỖNG là trạng thái hợp lệ và có nghĩa: "chưa ai sửa trên web", và lúc đó
tệp `public/pet/map.json` đã commit là bản đang chạy. Đó là cách giữ lại điều
tốt của thiết kế cũ — bản đồ vẫn nằm trong git — mà vẫn sửa được trên production.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "048_petland_map"
down_revision: Union[str, None] = "047_pet_tier_god"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

JSON = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "petland_map",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("w", sa.SmallInteger(), nullable=False),
        sa.Column("h", sa.SmallInteger(), nullable=False),
        sa.Column("ground", JSON, nullable=False),
        sa.Column("objects", JSON, nullable=False),
        sa.Column("solid", JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_petland_map_single_row"),
    )


def downgrade() -> None:
    op.drop_table("petland_map")
