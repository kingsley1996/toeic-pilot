"""trần XP ngày trả về TỪNG CON, không phải từng người (sửa lỗi của 040)

Revision ID: 042_pet_xp_cap_per_pet
Revises: 041_pet_species_40
Create Date: 2026-08-27 18:40:00.000000

Migration `040` dời chỉ số sang từng con nhưng **giữ cặp `xp_today`/`xp_day` ở
`pet_state`**, với lý do viết ra lúc đó: "cho mỗi con một bộ đếm riêng nghĩa là
ai có năm con thì có năm lần trần, và lúc đó level không còn nói lên điều gì về
việc nuôi thú".

Lý do đó SAI, và cái sai lộ ra ngay khi dùng thật: **một con vừa nở ra không
nhận được một điểm XP nào cho tới hôm sau**. Người ta mở trứng sau khi đã chơi
với con cũ, nên trần ngày gần như luôn đã cạn vào đúng lúc con mới xuất hiện —
chọc nó ba mươi cái thì XP vẫn đứng ở 0, level vẫn 1, và không có gì nói vì sao.
Đo được: chọc con mèo 30 lần cho kịch trần, đổi sang con cua vừa nở, chọc mười
lần nữa — `xp=0 lv=1` nguyên vẹn.

Chỗ lập luận trượt: **level là của TỪNG CON**, nên thứ trần ngày phải bảo vệ là
"một con không thể lên max level trong một buổi", chứ không phải "một người
không được chơi quá lâu". Trần theo từng con giữ nguyên tính chất ấy — mỗi con
vẫn tối đa 30 XP một ngày — và điều nó cho phép thêm chỉ là một người có nhiều
thú thì dành nhiều thời gian hơn cho cả bộ sưu tập. Đó là một trò sưu tầm đang
hoạt động đúng, không phải một lỗ hổng: level của một con nói "con này được chăm
bao nhiêu ngày", không nói "chủ nó rảnh bao nhiêu".

Chép giá trị đang có sang con ĐANG NUÔI rồi mới xoá cột, để cái trần của hôm nay
không bị mở lại giữa ngày cho chính con vừa dùng hết nó.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "042_pet_xp_cap_per_pet"
down_revision: Union[str, None] = "041_pet_species_40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pet_owned", sa.Column("xp_today", sa.SmallInteger(), nullable=False, server_default="0")
    )
    op.add_column("pet_owned", sa.Column("xp_day", sa.Date(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE pet_owned AS o
               SET xp_today = s.xp_today, xp_day = s.xp_day
              FROM pet_state AS s
             WHERE o.user_id = s.user_id AND o.species = s.species
            """
        )
    )
    op.drop_column("pet_state", "xp_today")
    op.drop_column("pet_state", "xp_day")


def downgrade() -> None:
    op.add_column(
        "pet_state", sa.Column("xp_today", sa.SmallInteger(), nullable=False, server_default="0")
    )
    op.add_column("pet_state", sa.Column("xp_day", sa.Date(), nullable=True))
    # Chép ngược từ con đang nuôi; bộ đếm của những con khác mất ở đây, và schema
    # cũ không có chỗ cho chúng.
    op.execute(
        sa.text(
            """
            UPDATE pet_state AS s
               SET xp_today = o.xp_today, xp_day = o.xp_day
              FROM pet_owned AS o
             WHERE o.user_id = s.user_id AND o.species = s.species
            """
        )
    )
    op.drop_column("pet_owned", "xp_today")
    op.drop_column("pet_owned", "xp_day")
