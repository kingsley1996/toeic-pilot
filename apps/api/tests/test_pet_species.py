"""Bảng loài thú (ADR-010 §6.3), và cách nó được gieo."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PetSpecies
from app.models.pet import DEFAULT_PET_SPECIES


def test_the_table_seeds_itself_on_first_read(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Mặc định gieo LƯỜI, không gieo trong migration.

    Gieo trong migration nghĩa là danh sách nằm ở hai chỗ, và cái ở migration
    đông cứng ở thời điểm viết: thêm loài thứ mười ba về sau thì máy mới có mười
    ba còn máy cũ có mười hai, cùng một mã nguồn.
    """
    assert db_session.scalar(select(func.count(PetSpecies.code))) == 0
    rows = client.get("/api/v1/admin/pet/species", headers=auth("admin")).json()
    assert len(rows) == len(DEFAULT_PET_SPECIES)
    assert {row["code"] for row in rows} >= {"cat", "tiger", "duck"}


def test_an_empty_table_means_never_configured(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Xoá sạch rồi đọc lại thì mười hai loài quay về.

    Hệ quả trực tiếp của việc gieo lười, và nó phải được nói ra: muốn bỏ một loài
    thì TẮT nó, đừng xoá — cùng tính chất mà `frame_tier` có.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/pet/species", headers=headers)
    db_session.query(PetSpecies).delete()
    db_session.commit()

    again = client.get("/api/v1/admin/pet/species", headers=headers).json()
    assert len(again) == len(DEFAULT_PET_SPECIES)


def test_disabling_a_species_keeps_it_visible_in_admin(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Màn quản trị là nơi DUY NHẤT nhìn thấy hàng đã tắt.

    Giấu chúng ở đây thì cách duy nhất bật lại là sửa database.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/pet/species", headers=headers)
    off = client.patch("/api/v1/admin/pet/species/cat", json={"enabled": False}, headers=headers)
    assert off.status_code == 200 and off.json()["enabled"] is False

    codes = [r["code"] for r in client.get("/api/v1/admin/pet/species", headers=headers).json()]
    assert "cat" in codes


def test_a_disabled_species_still_draws_for_whoever_owns_it(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Tắt phải làm loài biến khỏi gacha, KHÔNG làm con thú đang nuôi thành ô trống."""
    admin = auth("admin")
    client.get("/api/v1/admin/pet/species", headers=admin)
    # Con đang nuôi không còn cố định là "cat" — nó là thứ quả trứng đầu tiên
    # bốc ra, nên bài này phải nở nó ra rồi hỏi xem đó là con gì.
    assert client.post("/api/v1/pet/eggs/open", headers=admin).status_code == 200
    mine = client.get("/api/v1/pet", headers=admin).json()
    species, before = mine["species"], mine["tile"]

    client.patch(f"/api/v1/admin/pet/species/{species}", json={"enabled": False}, headers=admin)
    after = client.get("/api/v1/pet", headers=admin).json()
    assert after["species"] == species
    assert after["tile"] == before


@pytest.mark.parametrize("tile", [-1, 180, 999])
def test_a_tile_outside_the_sheet_is_refused(
    client: TestClient, auth: Callable[[str], dict[str, str]], tile: int
) -> None:
    """Ô ngoài lưới 10x18 vẽ ra một mảnh TRONG SUỐT.

    Con thú tàng hình, không lỗi nào, và chỉ người mở trứng ra mới biết — nên nó
    bị chặn ở tầng schema để lỗi là 422 nói rõ trường nào.
    """
    headers = auth("admin")
    bad = client.patch("/api/v1/admin/pet/species/cat", json={"tile": tile}, headers=headers)
    assert bad.status_code == 422


def test_the_code_cannot_be_changed_by_editing(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`code` là thứ `pet_state.species` trỏ tới.

    Đổi nó nghĩa là mọi con thú mang mã cũ thành mồ côi cùng lúc — cùng lý do
    `slug` của bộ đề không sửa được từ ô đổi tên. `PetSpeciesEdit` không khai
    `code`, nên Pydantic bỏ qua và đây là chỗ pin điều đó.
    """
    headers = auth("admin")
    client.get("/api/v1/admin/pet/species", headers=headers)
    client.patch(
        "/api/v1/admin/pet/species/cat", json={"code": "kitty", "label": "Mèo con"}, headers=headers
    )
    codes = [r["code"] for r in client.get("/api/v1/admin/pet/species", headers=headers).json()]
    assert "cat" in codes and "kitty" not in codes


def test_only_admins_may_configure_species(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    # Đặt bảng loài và hạng hiếm là quyết định VẬN HÀNH — nó định giá cho cả hệ
    # gacha — chứ không phải việc biên tập nội dung.
    assert client.get("/api/v1/admin/pet/species", headers=auth("editor")).status_code == 403
    assert client.get("/api/v1/admin/pet/species", headers=auth("learner")).status_code == 403
