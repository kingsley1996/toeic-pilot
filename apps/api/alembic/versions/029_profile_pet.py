"""profile pet: con mascot Petland mà người học đã chọn

Revision ID: 029_profile_pet
Revises: 028_backdrop_speed
Create Date: 2026-08-21 09:00:00.000000

VIẾT TAY, không autogenerate. Cơ sở dữ liệu dev mang bốn bảng mồ côi `pet`,
`learner_pet`, `pet_feed`, `pet_feed_log` — dấu vết của một tính năng dựng tại
máy rồi hoàn tác phần code mà không hoàn tác cơ sở dữ liệu (ROADMAP §4r). Chạy
`alembic revision --autogenerate` ở trạng thái đó sẽ sinh thêm bốn lệnh DROP
TABLE mà không ai yêu cầu, và chúng sẽ đi thẳng vào bản phát hành.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "029_profile_pet"
down_revision: str | None = "028_backdrop_speed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable, không `server_default`. NULL nghĩa là "chưa chọn", và frontend rơi
    # về con mặc định của nó. Điền sẵn một con ở đây sẽ ghim mọi người đang có
    # vào con mặc định của HÔM NAY, nên ngày đổi mặc định họ không đi theo — cùng
    # bẫy mà `daily_new_limit` tránh, và nó hỏng lặng lẽ y hệt.
    #
    # Cũng không có CHECK: danh sách mascot sống ở `app/schemas/profile.py::PetId`
    # để đi qua OpenAPI ra tới TypeScript. Thêm CHECK ở đây là thêm một chỗ thứ
    # hai phải nhớ sửa mỗi lần thêm mascot, và chỗ bị quên báo lỗi muộn nhất.
    op.add_column("user_profile", sa.Column("pet", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profile", "pet")
