"""gacha trứng: bộ sưu tập, trọng số rơi, bộ đếm an ủi (ADR-010 lát 8)

Revision ID: 039_pet_gacha
Revises: 038_ruby
Create Date: 2026-08-27 12:20:00.000000

**Tiền tệ là ruby, không phải `egg_token`.** ADR-010 §6.2 đề xuất một bộ đếm
riêng kiếm từ nhiệm vụ ngày; ADR-011 thay nó bằng một sổ cái dùng chung, và lý
do là cùng một lý do khiến §6.2 loại XP: một bộ đếm không trả lời được câu "điểm
này từ đâu ra, tiêu vào đâu". Không có bảng `egg_token` nào ở đây.

**Một HẠNG trứng, không phải bảng `egg_tier` nhiều hàng.** Với 12 loài, ba hạng
trứng là chia một cái bể nhỏ thành ba ngăn rỗng. `egg_setting` là một hàng duy
nhất theo khuôn `progression_setting`; ngày cần nhiều hạng thì nó lên thành một
bảng nhiều hàng, và đó là một migration chứ không phải một cuộc viết lại.

**Trọng số nằm trên chính `pet_species`, không phải bảng `egg_drop` riêng.** Với
một hạng trứng, một bảng nối chỉ để mang một số nguyên là một JOIN cho mỗi lần
mở trứng. Trọng số chứ không phải phần trăm: phần trăm phải cộng lại đúng 100,
nên tắt hay thêm một loài biến cả bảng thành sai.

**Bảng để RỖNG.** `egg_setting` gieo lười ở lần đọc đầu, đúng như `pet_species`.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "039_pet_gacha"
down_revision: Union[str, None] = "038_ruby"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pet_species",
        sa.Column("drop_weight", sa.SmallInteger(), nullable=False, server_default="10"),
    )
    # Hàng đã có từ trước được đặt trọng số theo hạng của chính nó, chứ không để
    # nguyên mặc định 10: để nguyên thì mười hai loài rơi đều nhau và hạng hiếm
    # không còn hiếm — một thay đổi về tỉ lệ mà không ai ra lệnh.
    for tier, weight in (("common", 40), ("uncommon", 25), ("rare", 10), ("epic", 4)):
        op.execute(
            sa.text("UPDATE pet_species SET drop_weight = :w WHERE tier = :t").bindparams(
                w=weight, t=tier
            )
        )

    op.add_column(
        "pet_state",
        sa.Column("rolls_since_rare", sa.SmallInteger(), nullable=False, server_default="0"),
    )

    op.create_table(
        "pet_owned",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("species", sa.String(length=32), nullable=False),
        sa.Column("copies", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "obtained_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # Khoá chính kép: "đã có con này chưa" là câu hỏi database trả lời, nên
        # hai lần mở trùng nhau không thể tạo ra hàng thứ hai.
        sa.PrimaryKeyConstraint("user_id", "species"),
    )

    op.create_table(
        "egg_setting",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ruby_cost", sa.SmallInteger(), nullable=False, server_default="25"),
        sa.Column("pity_rolls", sa.SmallInteger(), nullable=False, server_default="10"),
        sa.Column("duplicate_refund", sa.SmallInteger(), nullable=False, server_default="10"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ruby_cost > 0", name="ck_egg_setting_cost"),
        sa.CheckConstraint("pity_rolls > 0", name="ck_egg_setting_pity"),
        sa.CheckConstraint("duplicate_refund >= 0", name="ck_egg_setting_refund"),
        # Hoàn nhiều hơn giá trứng là một cỗ máy in ruby: mở trứng trùng liên tục
        # sinh ruby từ hư không.
        sa.CheckConstraint("duplicate_refund < ruby_cost", name="ck_egg_setting_refund_below_cost"),
    )


def downgrade() -> None:
    op.drop_table("egg_setting")
    op.drop_table("pet_owned")
    op.drop_column("pet_state", "rolls_since_rare")
    op.drop_column("pet_species", "drop_weight")
