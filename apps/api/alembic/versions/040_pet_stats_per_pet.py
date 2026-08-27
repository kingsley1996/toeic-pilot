"""chỉ số dời từ pet_state sang pet_owned: mỗi con một bộ (ADR-010 lát 9)

Revision ID: 040_pet_stats_per_pet
Revises: 039_pet_gacha
Create Date: 2026-08-27 15:10:00.000000

Trước đó cả góc thú cưng chỉ có MỘT bộ chỉ số, nằm trên `pet_state`. Đổi con là
con mới thừa hưởng độ no của con cũ, và con cũ mất sạch quá trình được chăm —
mỗi con là một sinh vật riêng, mà bảng chỉ kể được một lịch sử.

Ba cột Ở LẠI `pet_state` vì chúng thuộc về NGƯỜI CHƠI chứ không con nào:
`species` (đang nuôi con nào), `rolls_since_rare` (bộ đếm an ủi đo mấy quả trứng
vừa mở), và cặp `xp_today`/`xp_day`. Cặp cuối là quan trọng nhất: **trần XP mỗi
ngày phải là trần của NGƯỜI**. Cho mỗi con một bộ đếm riêng nghĩa là ai có năm
con thì có năm lần trần, và lúc đó level không còn nói lên điều gì về việc nuôi
thú — đúng thứ trần ngày sinh ra để chặn.

`hatched_at` không chuyển sang: `pet_owned.obtained_at` đã trả lời đúng câu đó
cho từng con, và hai cột cùng nghĩa là hai cột sẽ lệch nhau.

**Chuyển dữ liệu trước khi xoá cột.** Con đang nuôi của mỗi người được ghi vào
`pet_owned` nếu chưa có ở đó (tài khoản có từ trước lát 8 chưa có hàng nào), rồi
chỉ số chép sang đúng hàng ấy. Không làm bước đó thì mọi con thú đang được nuôi
trở về mặc định — không lỗi nào, chỉ là ai cũng thấy con thú của mình bị đặt lại.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "040_pet_stats_per_pet"
down_revision: Union[str, None] = "039_pet_gacha"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Cột dời đi, kèm định nghĩa để dựng lại được ở cả hai chiều.
MOVED = (
    ("nickname", sa.String(length=40), None),
    ("xp", sa.Integer(), "0"),
    ("level_reached", sa.SmallInteger(), "1"),
    ("tile_x", sa.SmallInteger(), "3"),
    ("tile_y", sa.SmallInteger(), "8"),
    ("facing", sa.String(length=5), "right"),
    ("fullness", sa.Numeric(4, 3), "0.62"),
    ("energy", sa.Numeric(4, 3), "0.78"),
    ("mood", sa.Numeric(4, 3), "0.70"),
    ("needs_at", sa.DateTime(timezone=True), "now()"),
)


def _add(table: str, nullable_first: bool = True) -> None:
    for name, kind, default in MOVED:
        op.add_column(
            table,
            sa.Column(
                name,
                kind,
                nullable=True,
                server_default=sa.text(default) if default == "now()" else default,
            ),
        )


def upgrade() -> None:
    _add("pet_owned")

    # Con đang nuôi phải có mặt trong tủ trước đã. `ON CONFLICT DO NOTHING` vì
    # phần lớn tài khoản đã có hàng đó rồi (đường đọc tự ghi từ lát 9).
    op.execute(
        sa.text(
            """
            INSERT INTO pet_owned (user_id, species, copies, obtained_at)
            SELECT user_id, species, 1, hatched_at FROM pet_state
            ON CONFLICT (user_id, species) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE pet_owned AS o SET
                nickname = s.nickname,
                xp = s.xp,
                level_reached = s.level_reached,
                tile_x = s.tile_x,
                tile_y = s.tile_y,
                facing = s.facing,
                fullness = s.fullness,
                energy = s.energy,
                mood = s.mood,
                needs_at = s.needs_at
            FROM pet_state AS s
            WHERE o.user_id = s.user_id AND o.species = s.species
            """
        )
    )

    # Hàng của những con CHƯA từng được nuôi (nở ra rồi để đó) chưa có chỉ số:
    # điền mặc định, rồi mới siết NOT NULL.
    op.execute(
        sa.text(
            """
            UPDATE pet_owned SET
                xp = COALESCE(xp, 0),
                level_reached = COALESCE(level_reached, 1),
                tile_x = COALESCE(tile_x, 3),
                tile_y = COALESCE(tile_y, 8),
                facing = COALESCE(facing, 'right'),
                fullness = COALESCE(fullness, 0.62),
                energy = COALESCE(energy, 0.78),
                mood = COALESCE(mood, 0.70),
                needs_at = COALESCE(needs_at, now())
            """
        )
    )
    for name, _kind, default in MOVED:
        if default is None:
            continue  # `nickname` được phép NULL: chưa đặt tên là một trạng thái thật.
        op.alter_column("pet_owned", name, nullable=False)

    op.create_check_constraint(
        "ck_pet_owned_needs_range",
        "pet_owned",
        "fullness BETWEEN 0 AND 1 AND energy BETWEEN 0 AND 1 AND mood BETWEEN 0 AND 1",
    )
    op.create_check_constraint("ck_pet_owned_facing", "pet_owned", "facing IN ('left', 'right')")

    op.drop_constraint("ck_pet_state_needs_range", "pet_state", type_="check")
    op.drop_constraint("ck_pet_state_facing", "pet_state", type_="check")
    for name, _kind, _default in MOVED:
        op.drop_column("pet_state", name)
    op.drop_column("pet_state", "hatched_at")


def downgrade() -> None:
    _add("pet_state")
    op.add_column(
        "pet_state",
        sa.Column(
            "hatched_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")
        ),
    )
    # Chép NGƯỢC từ con đang nuôi. Chỉ số của những con KHÁC mất ở đây, và không
    # có cách nào khác: schema cũ chỉ có chỗ cho một con.
    op.execute(
        sa.text(
            """
            UPDATE pet_state AS s SET
                nickname = o.nickname,
                xp = o.xp,
                level_reached = o.level_reached,
                tile_x = o.tile_x,
                tile_y = o.tile_y,
                facing = o.facing,
                fullness = o.fullness,
                energy = o.energy,
                mood = o.mood,
                needs_at = o.needs_at,
                hatched_at = o.obtained_at
            FROM pet_owned AS o
            WHERE o.user_id = s.user_id AND o.species = s.species
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE pet_state SET
                xp = COALESCE(xp, 0),
                level_reached = COALESCE(level_reached, 1),
                tile_x = COALESCE(tile_x, 3),
                tile_y = COALESCE(tile_y, 8),
                facing = COALESCE(facing, 'right'),
                fullness = COALESCE(fullness, 0.62),
                energy = COALESCE(energy, 0.78),
                mood = COALESCE(mood, 0.70),
                needs_at = COALESCE(needs_at, now()),
                hatched_at = COALESCE(hatched_at, now())
            """
        )
    )
    for name, _kind, default in MOVED:
        if default is None:
            continue
        op.alter_column("pet_state", name, nullable=False)
    op.alter_column("pet_state", "hatched_at", nullable=False)
    op.create_check_constraint(
        "ck_pet_state_needs_range",
        "pet_state",
        "fullness BETWEEN 0 AND 1 AND energy BETWEEN 0 AND 1 AND mood BETWEEN 0 AND 1",
    )
    op.create_check_constraint("ck_pet_state_facing", "pet_state", "facing IN ('left', 'right')")

    op.drop_constraint("ck_pet_owned_needs_range", "pet_owned", type_="check")
    op.drop_constraint("ck_pet_owned_facing", "pet_owned", type_="check")
    for name, _kind, _default in MOVED:
        op.drop_column("pet_owned", name)
