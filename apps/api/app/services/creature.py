"""Phân vai ô sinh vật, đọc từ bảng `creature` và gieo lười từ bản port của
`petland-bestiary.ts`.

Tách khỏi `services/pet_species.py` vì hai tệp trả lời hai câu: kia trả lời
"loài nuôi được nào có hàng gacha", đây trả lời "180 ô của tấm ghép đóng vai gì".
Cả hai gieo lười cùng một khuôn race-safe, nhưng chung tệp thì mỗi lần đọc loài
kéo theo 180 hàng phân vai — hai câu hỏi, hai lần đi database, không nên gộp.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pet import CREATURE_ROLES, Creature

# Bản port của RANGES + EXCEPTIONS trong `petland-bestiary.ts`. Sáu hàng đầu và
# hàng cá gộp thành một khoảng vì vai như nhau; phần "pet" của bảng TS KHÔNG
# được port — ô thú nuôi là join với `pet_species`, không phải một hàng ở đây
# (xem docstring `CREATURE_ROLES`).
_SEED_RANGES: tuple[tuple[int, int, str], ...] = (
    (0, 119, "intruder"),
    (120, 179, "wildlife"),
)

# {tile: (role, tên)} — ngoại lệ thắng khoảng, đúng luật của bảng TS. Ô mang vai
# "pet" trong TS (ô 117 cú) gieo vai PHỤ của khoảng nó và giữ nguyên tên.
_SEED_EXCEPTIONS: dict[int, tuple[str, str]] = {
    9: ("npc", "người lùn mũ xanh"),
    12: ("npc", "tiên có cánh"),
    19: ("npc", "pháp sư râu bạc"),
    27: ("npc", "tiên cá"),
    35: ("npc", "thiên thần"),
    36: ("npc", "thiên thần nhỏ"),
    37: ("npc", "thiên thần áo trắng"),
    50: ("wildlife", "ngựa nâu"),
    51: ("wildlife", "ngựa một sừng trắng"),
    52: ("wildlife", "ngựa trắng"),
    60: ("wildlife", "cá xanh"),
    61: ("wildlife", "cá hồng"),
    62: ("wildlife", "cá xám"),
    63: ("wildlife", "cá nâu"),
    64: ("wildlife", "cá cam"),
    70: ("wildlife", "cá xanh (hàng hai)"),
    71: ("wildlife", "cá hồng (hàng hai)"),
    72: ("wildlife", "cá xám (hàng hai)"),
    73: ("wildlife", "cá nâu (hàng hai)"),
    74: ("wildlife", "cá cam (hàng hai)"),
    92: ("wildlife", "gấu con"),
    100: ("npc", "phù thuỷ mũ xanh"),
    101: ("wildlife", "gấu nâu"),
    103: ("wildlife", "gà trống"),
    106: ("wildlife", "lạc đà"),
    109: ("npc", "thần đèn"),
    117: ("wildlife", "cú"),
    120: ("intruder", "mắt bay"),
    121: ("intruder", "cây ăn thịt sẫm"),
    122: ("intruder", "cây ăn thịt"),
    123: ("intruder", "tiểu quỷ đỏ"),
    124: ("intruder", "yêu tinh cầm khiên"),
    128: ("intruder", "hiệp sĩ giáp xám"),
}

# Sai chính tả trong bản port sẽ nổ ngay khi gieo, không phải thành một ô lặng
# lẽ sai vai trong database.
assert set(_SEED_EXCEPTIONS) <= set(range(180)), "ô ngoài tấm ghép"
for _role, _ in _SEED_EXCEPTIONS.values():
    assert _role in CREATURE_ROLES, f"vai lạ: {_role}"


def _default_row(tile: int) -> tuple[str, str | None]:
    exception = _SEED_EXCEPTIONS.get(tile)
    if exception is not None:
        return exception
    for start, end, role in _SEED_RANGES:
        if start <= tile <= end:
            return role, None
    raise AssertionError(f"ô {tile} ngoài mọi khoảng")


def seed_if_empty(db: Session) -> list[Creature]:
    """Gieo 180 hàng ở lần đọc đầu, race-safe như `pet_species`.

    Hai request đầu tiên sau một lần triển khai cùng đọc bảng rỗng và cùng gieo;
    kẻ thua vỡ khoá chính và đọc lại — cùng cách chữa mà `pet_species`, gacha và
    `encounters` đều đang dùng.
    """
    rows = list(db.scalars(select(Creature).order_by(Creature.tile)))
    if rows:
        return rows
    for tile in range(180):
        role, label = _default_row(tile)
        db.add(Creature(tile=tile, role=role, label=label))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return list(db.scalars(select(Creature).order_by(Creature.tile)))


def role_map(db: Session) -> dict[int, str]:
    """{tile: role} cho runtime phía frontend — bản gọn của cả bảng."""
    return {row.tile: row.role for row in seed_if_empty(db)}
