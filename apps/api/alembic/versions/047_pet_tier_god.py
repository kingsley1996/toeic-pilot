"""bậc hiếm thứ sáu: "god" (ADR-010 §6.3)

Revision ID: 047_pet_tier_god
Revises: 046_pet_spawn_tile
Create Date: 2026-08-28 15:10:00.000000

Nới ràng buộc CHECK, RỒI chèn năm loài của bậc mới.

Chèn ở migration là điều bảng loài vốn tránh — nó là dữ liệu admin sửa được, và
gieo lười (`all_species`) chỉ chạy khi bảng còn RỖNG. Nhưng mọi cài đặt đã chạy
đều có bảng khác rỗng, nên không chèn nghĩa là năm loài mới không bao giờ xuất
hiện ở đâu cả: một tính năng tồn tại mà không tồn tại, và cách duy nhất để thấy
nó là tự gõ tay năm hàng vào `/admin/pet`.

Lằn ranh: chèn `ON CONFLICT DO NOTHING` theo `code`, tức là chỉ THÊM những mã
chưa từng có. Nó không ghi đè nhãn, ô, trọng số hay công tắc bật/tắt của bất cứ
loài nào — những thứ người vận hành đã chỉnh. Đó là khác biệt giữa "thêm một
lựa chọn mới" và "ghi đè lựa chọn cũ".
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "047_pet_tier_god"
down_revision: Union[str, None] = "046_pet_spawn_tile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

TIERS = "'common', 'uncommon', 'rare', 'epic', 'legendary'"

GODS = (
    ("spirit_fire", "Thần Lửa", 45, 41),
    ("spirit_water", "Thần Nước", 46, 42),
    ("spirit_stone", "Thần Đá", 47, 43),
    ("spirit_storm", "Thần Bão", 48, 44),
    ("seraph", "Thiên Thần", 37, 45),
)


def upgrade() -> None:
    op.drop_constraint("ck_pet_species_tier", "pet_species", type_="check")
    op.create_check_constraint("ck_pet_species_tier", "pet_species", f"tier IN ({TIERS}, 'god')")

    # Chỉ chèn khi bảng ĐÃ có dữ liệu. Bảng rỗng nghĩa là "chưa từng cấu hình",
    # và `all_species` sẽ gieo trọn bộ bốn mươi lăm loài ở lần đọc đầu; chèn vào
    # một bảng rỗng ở đây làm nhánh gieo ấy không bao giờ chạy, và cài đặt mới
    # chỉ có đúng năm loài thần.
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM pet_species")).scalar_one() == 0:
        return
    for code, label, tile, position in GODS:
        bind.execute(
            sa.text(
                "INSERT INTO pet_species"
                " (code, label, tile, tier, position, enabled, drop_weight)"
                " VALUES (:code, :label, :tile, 'god', :position, true, 1)"
                " ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "label": label, "tile": tile, "position": position},
        )


def downgrade() -> None:
    # Xoá đúng năm loài migration này thêm vào. Loài bậc thần do người vận hành
    # tự tạo thì KHÔNG xoá — chỉ hạ cấp, xem dưới.
    op.execute("DELETE FROM pet_species WHERE code IN " + str(tuple(g[0] for g in GODS)))
    # Hạ cấp phần còn lại TRƯỚC khi thắt lại ràng buộc: để nguyên thì lệnh
    # tạo CHECK đổ vì dữ liệu đang vi phạm nó, và người chạy `downgrade` nhận
    # một lỗi Postgres thay vì một câu giải thích.
    op.execute("UPDATE pet_species SET tier = 'legendary' WHERE tier = 'god'")
    op.drop_constraint("ck_pet_species_tier", "pet_species", type_="check")
    op.create_check_constraint("ck_pet_species_tier", "pet_species", f"tier IN ({TIERS})")
