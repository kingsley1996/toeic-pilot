"""pet_state: trạng thái con thú đang nuôi, và dọn bốn bảng mồ côi

Revision ID: 035_pet_state
Revises: 034_user_identity
Create Date: 2026-08-26 21:40:00.000000

VIẾT TAY, không autogenerate — cùng lý do đã ghi ở `029_profile_pet`.

Cơ sở dữ liệu dev mang bốn bảng mồ côi `pet`, `learner_pet`, `pet_feed`,
`pet_feed_log`: dấu vết của một tính năng dựng tại máy rồi hoàn tác phần code mà
không hoàn tác database (ROADMAP §4r). Không bảng nào nằm trong `Base.metadata`.
`029` chọn cách SỐNG CHUNG với chúng để một lần `--autogenerate` không lén đưa
bốn lệnh DROP vào bản phát hành. Lần này chúng ta **cố ý xoá**, nên lệnh xoá
được viết ra bằng tay và có lý do kèm theo.

`IF EXISTS` là bắt buộc chứ không phải phòng xa: CI dựng một Postgres trắng mỗi
lần chạy, nơi bốn bảng ấy chưa từng tồn tại. `op.drop_table` sẽ làm hỏng migration
ở đúng nơi không có gì để dọn.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_pet_state"
down_revision: Union[str, None] = "034_user_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORPHANS = ("pet_feed_log", "pet_feed", "learner_pet", "pet")


def upgrade() -> None:
    # Cả bốn chỉ trỏ tới `users`, không trỏ lẫn nhau — đã kiểm bằng `\d`. Nên thứ
    # tự không quan trọng, và KHÔNG dùng CASCADE: cascade ở đây sẽ âm thầm kéo
    # theo bất cứ thứ gì trỏ vào chúng, kể cả thứ ta chưa biết là có.
    for table in ORPHANS:
        op.execute(f"DROP TABLE IF EXISTS {table}")

    op.create_table(
        "pet_state",
        # Khoá chính CHÍNH LÀ khoá ngoại: quan hệ 1-1 được ép ở tầng database
        # thay vì bằng một quy ước ai đó phải nhớ. Cùng hình dạng `user_profile`.
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("species", sa.String(length=32), nullable=False),
        sa.Column("nickname", sa.String(length=40), nullable=True),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_reached", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("tile_x", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("tile_y", sa.SmallInteger(), nullable=False, server_default="8"),
        sa.Column("facing", sa.String(length=5), nullable=False, server_default="right"),
        sa.Column("fullness", sa.Numeric(4, 3), nullable=False, server_default="0.62"),
        sa.Column("energy", sa.Numeric(4, 3), nullable=False, server_default="0.78"),
        sa.Column("mood", sa.Numeric(4, 3), nullable=False, server_default="0.70"),
        sa.Column(
            "needs_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "hatched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        # Ba nhu cầu nằm trong 0..1. CHECK ở đây được vì nó là một BẤT BIẾN của
        # miền, không phải một danh sách sẽ dài ra — khác hẳn `species`, vốn cố ý
        # không có CHECK vì danh sách loài sẽ do admin sửa.
        sa.CheckConstraint(
            "fullness BETWEEN 0 AND 1 AND energy BETWEEN 0 AND 1 AND mood BETWEEN 0 AND 1",
            name="ck_pet_state_needs_range",
        ),
        sa.CheckConstraint("facing IN ('left', 'right')", name="ck_pet_state_facing"),
    )


def downgrade() -> None:
    op.drop_table("pet_state")
    # KHÔNG dựng lại bốn bảng mồ côi.
    #
    # Downgrade có nghĩa vụ trả lại một schema CHẠY ĐƯỢC cho bản code cũ, không
    # có nghĩa vụ trả lại rác. Bốn bảng ấy không nằm trong `Base.metadata` của bất
    # kỳ bản nào, không code nào đọc chúng, và chúng rỗng. Dựng lại là chép rác
    # vào migration để nó sống thêm một vòng nữa.
