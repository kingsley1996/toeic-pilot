"""backdrop speed: hệ số tốc độ cho hiệu ứng nền

Revision ID: 028_backdrop_speed
Revises: 027_backdrop_setting
Create Date: 2026-08-17 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_backdrop_speed"
down_revision: str | None = "027_backdrop_setting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `server_default` là bắt buộc: cột NOT NULL thêm vào một bảng đã có hàng
    # sẽ hỏng nếu không có giá trị cho hàng đó. Bảng này luôn có sẵn đúng một
    # hàng (migration 027 chèn nó), nên đây không phải trường hợp giả định.
    op.add_column(
        "backdrop_setting",
        sa.Column("speed_percent", sa.Integer(), nullable=False, server_default="100"),
    )
    op.create_check_constraint(
        "ck_backdrop_setting_speed", "backdrop_setting", "speed_percent BETWEEN 25 AND 300"
    )


def downgrade() -> None:
    op.drop_constraint("ck_backdrop_setting_speed", "backdrop_setting", type_="check")
    op.drop_column("backdrop_setting", "speed_percent")
