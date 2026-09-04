"""tổng XP thô trong ngày của thú cưng

Revision ID: 053_pet_xp_raw_today
Revises: 052_dictation_transcript_vi
Create Date: 2026-09-04 10:20:00.000000

Trần XP ngày của thú cưng đổi từ chặn cứng ở 30 sang giảm dần: 30 điểm đầu ăn
đủ suất, phần sau ăn một phần năm. Chặn cứng nói với người học rằng chăm tiếp
không còn ý nghĩa, tức một luật trò chơi bảo người ta thôi học.

Đường cong ấy phải đo trên tổng THÔ của ngày, và `xp_today` không suy ngược ra
được: nhiều mức thô khác nhau cùng cho một mức đã trao. Chia tỉ lệ trên từng
lượt thay vì trên tổng dồn cũng không thay được cột này — một lượt đáng một điểm
sau mốc sẽ thành `1 // 5 = 0`, tức lại là trần cứng, chỉ khác chỗ đặt.

Khởi tạo bằng `xp_today` chứ không bằng 0: hàng đang có thuộc về ngày hôm nay
của ai đó, và đặt 0 sẽ trả lại cho họ trọn suất đầy mà họ đã dùng. Dưới mốc 30
thì thô và đã trao vốn bằng nhau, nên với mọi hàng hợp lệ đây là con số đúng chứ
không phải một phép xấp xỉ.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "053_pet_xp_raw_today"
down_revision: Union[str, None] = "052_dictation_transcript_vi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "pet_owned",
        sa.Column("xp_raw_today", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE pet_owned SET xp_raw_today = xp_today")


def downgrade() -> None:
    op.drop_column("pet_owned", "xp_raw_today")
