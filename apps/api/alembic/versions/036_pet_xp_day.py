"""pet_state: bộ đếm XP theo ngày, để trần XP có chỗ mà đếm

Revision ID: 036_pet_xp_day
Revises: 035_pet_state
Create Date: 2026-08-27 02:10:00.000000

Hai cột chứ không phải một sổ cái.

Level người học dựng trên `xp_event` — sổ cái chỉ ghi thêm — vì XP ở đó nuôi
level, huy hiệu, nhiệm vụ ngày và trần ngày cùng lúc: nhiều thứ đọc chung một
nguồn nên nguồn ấy phải là LỊCH SỬ. XP con thú chỉ nuôi đúng một thứ là level
con thú, nên một bộ đếm cộng với ngày của nó là đủ, và rẻ hơn hẳn.

Đánh đổi ấy **hết hạn vào ngày XP con thú mua được thứ gì thật** (thức ăn, đồ
trang trí). Lúc đó phải chuyển sang sổ cái TRƯỚC khi thêm chỗ tiêu, vì một bộ
đếm không trả lời được câu "điểm này từ đâu ra".
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "036_pet_xp_day"
down_revision: Union[str, None] = "035_pet_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pet_state",
        sa.Column("xp_today", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    # NULL nghĩa là "chưa nhận XP ngày nào", khác hẳn với "hôm nay chưa nhận".
    # Điền sẵn ngày hôm nay sẽ ghim mọi hàng đang có vào múi giờ của MÁY CHỦ tại
    # thời điểm chạy migration, trong khi ngày ở đây phải theo múi giờ NGƯỜI HỌC.
    op.add_column("pet_state", sa.Column("xp_day", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("pet_state", "xp_day")
    op.drop_column("pet_state", "xp_today")
