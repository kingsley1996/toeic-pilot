"""backdrop setting: cấu hình nền lưới động, sửa từ giao diện quản trị

Revision ID: 027_backdrop_setting
Revises: 026_vocabulary_topic_session
Create Date: 2026-08-17 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_backdrop_setting"
down_revision: str | None = "026_vocabulary_topic_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLORS = ("action", "ok", "warn", "alert", "accent-us", "accent-uk", "accent-au", "accent-ca")


def upgrade() -> None:
    op.create_table(
        "backdrop_setting",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spark_count", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("twinkle_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="action"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # Một hàng duy nhất, do DATABASE bảo đảm chứ không do quy ước. Thiếu nó
        # thì hàng thứ hai xuất hiện vào ngày ai đó viết một script seed, và
        # `LIMIT 1` trả về cái nào trở thành chuyện của thứ tự vật lý.
        sa.CheckConstraint("id = 1", name="ck_backdrop_setting_singleton"),
        sa.CheckConstraint("spark_count BETWEEN 0 AND 6", name="ck_backdrop_setting_spark_count"),
        sa.CheckConstraint(
            "twinkle_count BETWEEN 0 AND 12", name="ck_backdrop_setting_twinkle_count"
        ),
        sa.CheckConstraint(
            "color IN ('" + "', '".join(_COLORS) + "')", name="ck_backdrop_setting_color"
        ),
    )
    # Chèn sẵn hàng mặc định: đường đọc công khai không có quyền ghi, nên nếu
    # bảng rỗng thì nó phải rơi về giá trị cứng — và từ đó cấu hình "mặc định"
    # tồn tại ở hai nơi. Một hàng có sẵn giữ nó ở đúng một nơi.
    op.execute("INSERT INTO backdrop_setting (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("backdrop_setting")
