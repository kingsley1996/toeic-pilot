"""mốc người học đã xem tour giới thiệu

Revision ID: 056_profile_toured_at
Revises: 055_pet_state_species_nullable
Create Date: 2026-09-04 17:30:00.000000

Tour chỉ chạy MỘT lần trong đời tài khoản, nên phải có chỗ nhớ là đã chạy.

Chỗ ấy là máy chủ, không phải `localStorage`. Cùng lý do `vocabulary_topic_session`
không nằm ở trình duyệt: "tôi đã xem cái này rồi" là dữ liệu người dùng — nó phải
đi theo tài khoản, sống sót qua một lần xoá cache, và nhìn thấy được trong
database. Để ở `localStorage` thì tour bật lại ở mỗi thiết bị mới, và người học
gặp lại lời chào ấy trên điện thoại sau khi đã bỏ qua nó trên máy tính.

MỐC THỜI GIAN chứ không phải cờ `boolean`: nó trả lời thêm được câu "bao nhiêu
người mới thật sự xem tới cuối", và một cột `true/false` thì không. Cùng hình
dạng với `user_badge.seen_at`.

NULL nghĩa là chưa xem — nên mọi tài khoản đang có sẽ thấy tour ở lần đăng nhập
tới. Đó là chủ ý: nó giới thiệu những thứ họ cũng chưa từng được giới thiệu.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "056_profile_toured_at"
down_revision: Union[str, None] = "055_pet_state_species_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "user_profile", sa.Column("toured_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_profile", "toured_at")
