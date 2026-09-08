"""practice_test.kind nhận 'placement' — đề đầu vào thành một kiểu riêng

Revision ID: 075_placement_kind
Revises: 074_feedback
Create Date: 2026-09-08 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "075_placement_kind"
down_revision: Union[str, None] = "074_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_practice_test_kind", "practice_test", type_="check")
    op.create_check_constraint(
        "ck_practice_test_kind", "practice_test", "kind IN ('full', 'mini', 'placement')"
    )
    # Các đề đầu vào đang mang `kind='mini'` — đúng về độ dài, sai về mục đích.
    # Chuyển chúng sang kiểu thật; `is_placement` vẫn giữ nguyên vì hợp đồng API
    # và bốn chỗ gọi đang đọc nó.
    op.execute(sa.text("UPDATE practice_test SET kind = 'placement' WHERE is_placement"))
    # Hai cột nói cùng một điều, nên chúng phải không thể nói khác nhau. Một
    # hàng `kind='placement'` mà `is_placement=false` sẽ không bao giờ được rút
    # và không có gì báo — nhóm đề chỉ đơn giản là thiếu nó.
    op.create_check_constraint(
        "ck_practice_test_placement_kind",
        "practice_test",
        "(kind = 'placement') = is_placement",
    )


def downgrade() -> None:
    op.drop_constraint("ck_practice_test_placement_kind", "practice_test", type_="check")
    op.execute(sa.text("UPDATE practice_test SET kind = 'mini' WHERE kind = 'placement'"))
    op.drop_constraint("ck_practice_test_kind", "practice_test", type_="check")
    op.create_check_constraint("ck_practice_test_kind", "practice_test", "kind IN ('full', 'mini')")
