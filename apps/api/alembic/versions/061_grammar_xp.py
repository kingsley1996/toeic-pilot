"""xp_grammar_attempt — mức XP cho một câu ngữ pháp đúng (G5)

Nguồn XP mới chỉ cần thêm vào `XP_SOURCES` (chuỗi tự do), nhưng MỨC ĐIỂM thì là
một cột của `progression_setting`: mọi con số gamification là dữ liệu admin sửa
được, và một nguồn cứng mã trong code là ngoại lệ đầu tiên sẽ kéo theo ngoại lệ
thứ hai.

`server_default='2'` nuôi cả hàng cấu hình đã tồn tại lẫn hàng mới — bộ mặc định
lazy-seed chỉ chạy khi bảng còn trống, nên không có default thì upgrade chết ở
mọi môi trường đã seed.

Revision ID: 061_grammar_xp
Revises: 060_grammar_topic_code_nullable
Create Date: 2026-09-06 12:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "061_grammar_xp"
down_revision: Union[str, None] = "060_grammar_topic_code_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "progression_setting",
        sa.Column("xp_grammar_attempt", sa.Integer(), nullable=False, server_default="2"),
    )


def downgrade() -> None:
    op.drop_column("progression_setting", "xp_grammar_attempt")
