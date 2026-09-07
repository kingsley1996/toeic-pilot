"""Bộ sưu tập thú — con gì hiện trong tủ của người học.

Tắt một loài phải làm nó ẩn khỏi TỦ SƯU TẬP (quyết định vận hành 2026-09-07):
tủ là mặt tiền, một con bị rút khỏi gacha không nên tiếp tục hiện như một thứ
có thể kiếm được. Con thú đang NUÔI vẫn vẽ ra được — đường vẽ đọc cả hàng đã
tắt (`tile_for`), chỉ ô trong tủ là ẩn.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PetOwned, PetSpecies, User


def test_a_disabled_species_hides_from_the_collection(
    client: TestClient,
    db_session: Session,
    auth: Callable[[str], dict[str, str]],
) -> None:
    learner_headers = auth("learner")
    admin_headers = auth("admin")
    # Gieo bảng loài qua chính session của test: client và `db_session` dùng
    # chung một Session ở đây (dependency override), nên commit là thấy nhau.
    from app.services.pet_species import all_species

    all_species(db_session)
    duck = db_session.scalar(select(PetSpecies).where(PetSpecies.code == "duck"))
    assert duck is not None

    user = db_session.query(User).filter(User.email == "learner@example.com").first()
    assert user is not None
    db_session.add(PetOwned(user_id=user.id, species="duck"))
    db_session.commit()

    assert "duck" in _codes(client, learner_headers)

    client.patch("/api/v1/admin/pet/species/duck", json={"enabled": False}, headers=admin_headers)
    assert "duck" not in _codes(client, learner_headers)

    client.patch("/api/v1/admin/pet/species/duck", json={"enabled": True}, headers=admin_headers)
    assert "duck" in _codes(client, learner_headers)


def _codes(client: TestClient, headers: dict[str, str]) -> list[str]:
    response = client.get("/api/v1/pet/collection", headers=headers)
    assert response.status_code == 200
    return [row["code"] for row in response.json()]
