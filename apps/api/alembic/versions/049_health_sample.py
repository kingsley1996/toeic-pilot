"""lịch sử tình trạng dịch vụ, để tính uptime

Revision ID: 049_health_sample
Revises: 048_petland_map
Create Date: 2026-08-29 11:00:00.000000

`/ready` đã kiểm Postgres và Redis ở mỗi lần được gọi, và một monitor bên ngoài
gọi nó năm phút một lần để giữ ba dịch vụ khỏi ngủ. Bảng này chỉ GHI LẠI thứ
đang được kiểm sẵn — không thêm bộ lập lịch nào, vì kiến trúc này cố ý không có
bộ lập lịch nào chạy ở production.

Giới hạn phải nói ra: **một sự cố Postgres không thể ghi vào Postgres.** Nó hiện
ra dưới dạng KHOẢNG TRỐNG trong chuỗi mẫu, không phải một hàng "down". Giao diện
vẽ khoảng trống thành ô xám riêng chứ không nhuộm xanh — con số uptime trung
thực quan trọng hơn con số đẹp.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "049_health_sample"
down_revision: Union[str, None] = "048_petland_map"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "health_sample",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("service", sa.String(24), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("state IN ('ok', 'degraded', 'down')", name="ck_health_sample_state"),
    )
    # Mọi truy vấn đều là "một dịch vụ, trong một khoảng thời gian".
    op.create_index("ix_health_sample_service_time", "health_sample", ["service", "checked_at"])


def downgrade() -> None:
    op.drop_index("ix_health_sample_service_time", table_name="health_sample")
    op.drop_table("health_sample")
