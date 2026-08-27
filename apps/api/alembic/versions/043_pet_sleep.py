"""ngủ để hồi sức: một mốc hết hạn trên từng con

Revision ID: 043_pet_sleep
Revises: 042_pet_xp_cap_per_pet
Create Date: 2026-08-27 20:10:00.000000

`sleep_until` là một MỐC HẾT HẠN, không phải cờ `đang_ngủ`, và khác biệt ấy là
toàn bộ lý do giấc ngủ không thành việc phải làm: nó tự dứt khi tới mốc — không
cần ai bấm gì, không cần job nền đi đánh thức, và người đóng tab giữa chừng vẫn
thấy con thú đã dậy khi quay lại. Một cái cờ thì phải có ai đó tắt nó, và "ai
đó" cuối cùng luôn là người dùng.

NULL nghĩa là đang thức, nên hàng cũ không cần vá gì: mọi con thú có từ trước
migration này đều thức, và đó đúng là trạng thái của chúng.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "043_pet_sleep"
down_revision: Union[str, None] = "042_pet_xp_cap_per_pet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pet_owned", sa.Column("sleep_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("pet_owned", "sleep_until")
