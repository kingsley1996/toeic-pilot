"""gợi ý cho nhiệm vụ gõ lại từ: đếm ở máy chủ (ADR-012)

Revision ID: 045_encounter_hints
Revises: 044_encounters
Create Date: 2026-08-28 09:40:00.000000

Một cột đếm, và nó phải nằm ở database chứ không ở trình duyệt. Trần gợi ý là
thứ giữ cho nhiệm vụ gõ lại từ còn là một bài kiểm: xin đủ nhiều lần thì gợi ý
in ra cả từ, và lúc đó phần thưởng ruby chỉ còn là một cái nút bấm nhiều lần.
Một bộ đếm trong `useState` thì devtools đặt lại được trong hai giây.

`server_default='0'` chứ không chỉ mặc định ở tầng Python: những hàng đã có sẵn
cần một giá trị, và NOT NULL không có mặc định ở tầng database thì lệnh thêm cột
sẽ hỏng ngay trên bảng đang có dữ liệu.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "045_encounter_hints"
down_revision: Union[str, None] = "044_encounters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "encounter",
        sa.Column("hints_used", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("ck_encounter_hints", "encounter", "hints_used >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_encounter_hints", "encounter", type_="check")
    op.drop_column("encounter", "hints_used")
