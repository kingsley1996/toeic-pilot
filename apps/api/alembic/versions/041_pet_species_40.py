"""bốn mươi loài thú và hạng huyền thoại (ADR-010 §6.3)

Revision ID: 041_pet_species_40
Revises: 040_pet_stats_per_pet
Create Date: 2026-08-27 17:20:00.000000

Hai việc, và việc thứ hai là việc bất thường.

**Nới `ck_pet_species_tier` để nhận `legendary`.** Thang hạng nằm ở CHECK chứ
không ở một bảng riêng, nên thêm một hạng là một migration — đánh đổi đã ghi khi
dựng bảng: một bảng hạng riêng cho năm dòng chữ là một phép JOIN cho mỗi lần đọc
loài, đổi lấy một thứ đổi vài năm một lần.

**Và chèn thẳng danh sách loài vào đây, một lần.** Đây là chỗ DUY NHẤT trong dự
án mà một danh sách mặc định xuất hiện hai lần, nên nó cần một lý do: bộ mặc định
ở `app/models/pet.py` được gieo LƯỜI, và gieo lười chỉ chạy khi bảng RỖNG — đúng
tính chất khiến "xoá một loài" không bị hoàn tác ở lần đọc sau. Hệ quả là mọi cài
đặt đã chạy (dev, và production nếu có) đang giữ 12 hàng cũ và sẽ **không bao giờ**
thấy 28 loài mới, dù mã nguồn đã có.

Nên bản sao ở đây không phải bản sao của bảng: nó là **ảnh chụp tại đúng lần sửa
này**, đông cứng vĩnh viễn, và nó không bao giờ được cập nhật theo bộ mặc định
nữa. `ON CONFLICT DO NOTHING` giữ nguyên mọi hàng admin đã chỉnh — trọng số, nhãn,
công tắc bật/tắt của 12 loài cũ không bị đụng tới.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_pet_species_40"
down_revision: Union[str, None] = "040_pet_stats_per_pet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (mã, nhãn, ô, hạng, thứ tự, trọng số) — ảnh chụp lúc 2026-08-27, không sửa nữa.
SPECIES = [
    ("duck", "Vịt", 150, "common", 1, 40),
    ("squirrel", "Sóc", 175, "common", 2, 40),
    ("frog", "Ếch", 147, "common", 3, 40),
    ("rabbit", "Thỏ", 177, "common", 4, 40),
    ("sheep", "Cừu", 153, "common", 5, 40),
    ("goat", "Dê", 151, "common", 6, 40),
    ("hedgehog", "Nhím", 143, "common", 7, 40),
    ("parrot", "Vẹt", 103, "common", 8, 40),
    ("crab", "Cua", 145, "common", 9, 40),
    ("cat", "Mèo", 169, "uncommon", 10, 25),
    ("monkey", "Khỉ", 168, "uncommon", 11, 25),
    ("turtle", "Rùa", 149, "uncommon", 12, 25),
    ("otter", "Rái cá", 176, "uncommon", 13, 25),
    ("skunk", "Chồn hôi", 179, "uncommon", 14, 25),
    ("bat", "Dơi", 130, "uncommon", 15, 25),
    ("lizard", "Thằn lằn", 146, "uncommon", 16, 25),
    ("camel", "Lạc đà", 129, "uncommon", 17, 25),
    ("bear_cub", "Gấu con", 92, "uncommon", 18, 25),
    ("snake", "Rắn", 148, "uncommon", 19, 25),
    ("owl", "Cú", 117, "rare", 20, 10),
    ("deer", "Hươu", 161, "rare", 21, 10),
    ("raccoon", "Gấu mèo", 178, "rare", 22, 10),
    ("eagle", "Đại bàng", 134, "rare", 23, 10),
    ("zebra", "Ngựa vằn", 155, "rare", 24, 10),
    ("boar", "Lợn rừng", 160, "rare", 25, 10),
    ("polar_bear", "Gấu trắng", 164, "rare", 26, 10),
    ("ostrich", "Đà điểu", 154, "rare", 27, 10),
    ("tiger", "Hổ", 157, "epic", 28, 4),
    ("bear", "Gấu", 165, "epic", 29, 4),
    ("giraffe", "Hươu cao cổ", 159, "epic", 30, 4),
    ("lion", "Sư tử", 156, "epic", 31, 4),
    ("elephant", "Voi", 158, "epic", 32, 4),
    ("gorilla", "Khỉ đột", 166, "epic", 33, 4),
    ("rhino", "Tê giác", 170, "epic", 34, 4),
    ("unicorn", "Kỳ lân", 51, "legendary", 35, 2),
    ("pegasus", "Thiên mã", 30, "legendary", 36, 2),
    ("dragon_fire", "Rồng lửa", 33, "legendary", 37, 2),
    ("dragon_ice", "Rồng băng", 31, "legendary", 38, 2),
    ("fairy", "Tiên", 12, "legendary", 39, 2),
    ("djinn", "Thần đèn", 109, "legendary", 40, 2),
]


def upgrade() -> None:
    op.drop_constraint("ck_pet_species_tier", "pet_species", type_="check")
    op.create_check_constraint(
        "ck_pet_species_tier",
        "pet_species",
        "tier IN ('common', 'uncommon', 'rare', 'epic', 'legendary')",
    )

    insert = sa.text(
        """
        INSERT INTO pet_species (code, label, tile, tier, position, drop_weight, enabled)
        VALUES (:code, :label, :tile, :tier, :position, :drop_weight, true)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, label, tile, tier, position, weight in SPECIES:
        op.execute(
            insert.bindparams(
                code=code, label=label, tile=tile, tier=tier, position=position, drop_weight=weight
            )
        )


def downgrade() -> None:
    # Xoá những loài hạng huyền thoại trước, vì CHECK cũ không nhận chúng — và
    # KHÔNG xoá 28 loài kia: người chơi có thể đã nở ra chúng, và `pet_owned` giữ
    # mã loài chứ không giữ khoá ngoại, nên xoá hàng ở đây sẽ để lại những con
    # thú mồ côi trong tủ của họ.
    op.execute(sa.text("DELETE FROM pet_species WHERE tier = 'legendary'"))
    op.drop_constraint("ck_pet_species_tier", "pet_species", type_="check")
    op.create_check_constraint(
        "ck_pet_species_tier",
        "pet_species",
        "tier IN ('common', 'uncommon', 'rare', 'epic')",
    )
