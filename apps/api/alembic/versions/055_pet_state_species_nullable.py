"""người mới chưa có thú cưng — `pet_state.species` được phép rỗng

Revision ID: 055_pet_state_species_nullable
Revises: 054_encounter_rescue_kind
Create Date: 2026-09-04 15:10:00.000000

Trước đây mở góc thú cưng lần đầu là được tặng thẳng một con mèo. Giờ người mới
nhận một quả TRỨNG và tự mở — nên tồn tại một quãng, dài bằng đúng ý người dùng,
mà tài khoản có góc thú cưng nhưng chưa nuôi con nào.

`NULL` là cách nói "chưa mở trứng". Một mã giả kiểu `""` hay `"none"` thì mọi
đường đọc phải nhớ so với nó, và chỗ ai đó quên sẽ đi tra một loài không tồn tại
rồi trả về `None` — hỏng im lặng. `NULL` thì trình kiểm kiểu bắt được ở từng chỗ.

Không đụng tới hàng cũ: tài khoản đã có thú vẫn giữ nguyên `species`, nên thay
đổi này chỉ chạm tới người chưa từng mở bảng.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "055_pet_state_species_nullable"
down_revision: Union[str, None] = "054_encounter_rescue_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("pet_state", "species", existing_type=sa.String(32), nullable=True)


def downgrade() -> None:
    # Thắt lại được thì phải có gì đó trong ô rỗng; "cat" là con mặc định cũ.
    op.execute("UPDATE pet_state SET species = 'cat' WHERE species IS NULL")
    op.alter_column("pet_state", "species", existing_type=sa.String(32), nullable=False)
