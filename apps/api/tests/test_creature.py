"""Phân vai ô sinh vật — `petland-bestiary.ts` xuống database (migration 071).

Ba tính chất phải giữ, mỗi cái hỏng im lặng nếu bỏ:

1. **180 hàng gieo lười** — bảng rỗng là "chưa cấu hình", đọc lại là gieo đủ.
2. **Ô thú nuôi không sửa được vai** — vai của nó thuộc `pet_species`; cho PATCH
   là cho bảng creature cai trị một thứ nó không sở hữu.
3. **Map công khai không chứa vai "pet"** — client đã có danh sách loài từ cổng
   gacha, gửi kèm là dựng bản sao thứ hai của một bảng đã có một bản.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Creature, PetSpecies


def test_the_table_seeds_all_180_tiles_on_first_read(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    assert db_session.scalars(select(Creature)).first() is None
    rows = client.get("/api/v1/admin/petland/creatures", headers=auth("admin")).json()
    assert len(rows) == 180
    assert {row["tile"] for row in rows} == set(range(180))
    # Ba vai của bảng seed; vai "pet" là join, không phải hàng.
    assert {row["role"] for row in rows} == {"npc", "wildlife", "intruder"}


def test_the_role_map_matches_the_static_table_where_it_counts(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Những ô exception của bảng TS phải đến đúng vai của chúng.

    Sai một ô là một con thỏ bị hỏi câu tiếng Anh, hoặc người chơi bắt chuyện
    với một con quái — đúng hai triệu chứng mà bảng tĩnh tồn tại để chống.
    """
    roles = client.get("/api/v1/petland/creatures").json()["roles"]
    assert roles["0"] == "intruder"
    assert roles["9"] == "npc"
    assert roles["60"] == "wildlife"
    assert roles["123"] == "intruder"


def test_pet_tiles_reject_editing(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Ô có loài trỏ tới thì 409 — kể cả khi chỉ đổi tên.

    Vai của ô đó không nằm ở bảng creature, và cho sửa nửa cái là tạo cảm giác
    bảng đang cai trị ô. Nơi đổi là `/admin/pet`.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)
    # Gieo bảng loài qua cổng của nó trước: 409 phải đến từ dữ liệu thật, và
    # `db_session` là kết nối khác — chỉ thấy loài sau khi seed đã commit.
    client.get("/api/v1/admin/pet/species", headers=headers)
    duck = db_session.scalar(select(PetSpecies).where(PetSpecies.code == "duck"))
    assert duck is not None

    blocked = client.patch(
        f"/api/v1/admin/petland/creatures/{duck.tile}",
        json={"label": "vịt"},
        headers=headers,
    )
    assert blocked.status_code == 409


def test_role_change_moves_a_tile_between_boards(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Đổi vai là đổi hành vi: ô rời bảng cũ, vào bảng mới, ngay lượt đọc sau."""
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)

    moved = client.patch("/api/v1/admin/petland/creatures/5", json={"role": "npc"}, headers=headers)
    assert moved.status_code == 200 and moved.json()["role"] == "npc"

    roles = client.get("/api/v1/petland/creatures").json()["roles"]
    assert roles["5"] == "npc"


def test_sending_null_label_clears_it(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`{"label": null}` là LỆNH XOÁ, không phải "bỏ qua".

    Gộp "không gửi" với "gửi null" là ô không bao giờ được trả lại đúng danh
    nghĩa — cùng bẫy `exclude_unset` mà `PetSpeciesEdit` đã né.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)
    named = client.patch(
        "/api/v1/admin/petland/creatures/6", json={"label": "mắt bay nhỏ"}, headers=headers
    )
    assert named.json()["label"] == "mắt bay nhỏ"

    cleared = client.patch(
        "/api/v1/admin/petland/creatures/6", json={"label": None}, headers=headers
    )
    assert cleared.json()["label"] is None


def test_the_seed_survives_a_full_wipe(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Xoá sạch rồi đọc lại: 180 ô quay về — muốn bỏ vai thì đổi vai, đừng xoá."""
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)
    db_session.query(Creature).delete()
    db_session.commit()

    rows = client.get("/api/v1/admin/petland/creatures", headers=headers).json()
    assert len(rows) == 180


def test_promoting_a_tile_creates_a_species_and_locks_the_tile(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """ "Chuyển thành thú nuôi" là TẠO loài (`pet_species`), không phải một vai.

    Ô nhảy sang bảng thú nuôi ngay lượt đọc sau (species_code), bị khoá PATCH
    như mọi ô thú nuôi, và nhảy vào gacha. Vai cũ được giữ làm vai phụ trong
    hàng creature — dùng khi loài sau này bị xoá, không phải vai đang chạy.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)

    made = client.post(
        "/api/v1/admin/petland/creatures/123/promote",
        json={"code": "eye-bat"},
        headers=headers,
    )
    assert made.status_code == 201 and made.json()["species_code"] == "eye-bat"

    row = client.get("/api/v1/admin/petland/creatures", headers=headers).json()
    assert next(r for r in row if r["tile"] == 123)["species_code"] == "eye-bat"
    assert db_session.scalar(select(PetSpecies).where(PetSpecies.code == "eye-bat")) is not None

    now_locked = client.patch(
        "/api/v1/admin/petland/creatures/123", json={"label": "x"}, headers=headers
    )
    assert now_locked.status_code == 409

    again = client.post(
        "/api/v1/admin/petland/creatures/123/promote", json={"code": "other"}, headers=headers
    )
    assert again.status_code == 409


def test_promoting_needs_a_unique_species_code(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Mã là khoá mà `pet_state.species` trỏ tới — trùng mã là nổ ngay ở đây,
    không phải thành một con thú hai người nuôi một nửa."""
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)
    client.get("/api/v1/admin/pet/species", headers=headers)

    taken = client.post(
        "/api/v1/admin/petland/creatures/0/promote", json={"code": "duck"}, headers=headers
    )
    assert taken.status_code == 409


def test_promoting_a_god_tier_defaults_to_a_rare_weight(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Hạng god mà không điền trọng số thì nhận 1, KHÔNG phải 10.

    Tỉ lệ gacha chuẩn hoá từ trọng số (`gacha.chances`), nên một god mang 10 là
    một god rơi dễ hơn epic — hạng hiếm mà không hiếm, và ai đó phải mở bảng
    loài ra sửa tay từng con sau mỗi lần promote.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/petland/creatures", headers=headers)

    made = client.post(
        "/api/v1/admin/petland/creatures/124/promote",
        json={"code": "god-test", "tier": "god"},
        headers=headers,
    )
    assert made.status_code == 201
    row = db_session.scalar(select(PetSpecies).where(PetSpecies.code == "god-test"))
    assert row is not None and row.drop_weight == 1

    # Điền rõ ràng thì thắng mặc định — admin luôn có quyền ghi đè.
    over = client.post(
        "/api/v1/admin/petland/creatures/125/promote",
        json={"code": "god-test-2", "tier": "god", "drop_weight": 10},
        headers=headers,
    )
    assert over.status_code == 201
    row2 = db_session.scalar(select(PetSpecies).where(PetSpecies.code == "god-test-2"))
    assert row2 is not None and row2.drop_weight == 10
