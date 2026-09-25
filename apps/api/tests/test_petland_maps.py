"""Map theo slug: đọc/ghi từng map, cổng vào tháp, và map chính bất khả xoá.

Chỉ kiểm luật mới của migration 098: slug lạ 204, portal phải đi được, và
`DELETE` từ chối map chính. Luật cũ (độ dài layers, ô spawn) đã có chủ.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PetlandMap

W, H = 18, 13
SIZE = W * H


def _body(**over: object) -> dict:
    ground = [{"sheet": "town", "index": 1}] * SIZE
    data: dict = {
        "w": W,
        "h": H,
        "ground": ground,
        "objects": [None] * SIZE,
        "solid": [False] * SIZE,
        "portal": None,
    }
    data.update(over)
    return data


def test_legacy_endpoints_still_drive_the_main_map(client: TestClient, auth: dict) -> None:
    headers = auth("admin")
    assert client.get("/api/v1/petland/map").status_code == 204

    saved = client.put("/api/v1/admin/petland/map", headers=headers, json=_body()).json()
    assert saved["w"] == W and saved["portal"] is None

    listed = client.get("/api/v1/admin/petland/maps", headers=headers).json()
    assert [item["slug"] for item in listed] == ["main"]

    assert client.get("/api/v1/petland/map/main").json()["w"] == W
    assert client.get("/api/v1/petland/map/chua-co").status_code == 204


def test_portal_must_be_walkable_and_inside(client: TestClient, auth: dict) -> None:
    headers = auth("admin")
    solid = [False] * SIZE
    solid[5 * W + 3] = False
    assert (
        client.put(
            "/api/v1/admin/petland/map",
            headers=headers,
            json=_body(portal={"x": 99, "y": 0}),
        ).status_code
        == 422
    )
    blocked = [False] * SIZE
    blocked[6] = True
    assert (
        client.put(
            "/api/v1/admin/petland/map",
            headers=headers,
            json=_body(objects=[None] * SIZE, solid=blocked, portal={"x": 6, "y": 0}),
        ).status_code
        == 422
    )
    ok = client.put(
        "/api/v1/admin/petland/map",
        headers=headers,
        json=_body(portal={"x": 6, "y": 0}),
    ).json()
    assert ok["portal"] == {"x": 6, "y": 0}
    assert client.get("/api/v1/admin/petland/maps", headers=headers).json()[0]["has_portal"] is True


def test_second_map_lives_and_dies_by_slug(client: TestClient, auth: dict) -> None:
    headers = auth("admin")
    assert (
        client.put("/api/v1/admin/petland/map/Hoa Cỏ", headers=headers, json=_body()).status_code
        == 422
    )
    saved = client.put("/api/v1/admin/petland/map/sanh-phu", headers=headers, json=_body()).json()
    assert saved["w"] == W
    slugs = [
        item["slug"] for item in client.get("/api/v1/admin/petland/maps", headers=headers).json()
    ]
    assert slugs == ["main", "sanh-phu"] or set(slugs) >= {"sanh-phu"}

    assert client.delete("/api/v1/admin/petland/map/main", headers=headers).status_code == 409
    assert client.delete("/api/v1/admin/petland/map/sanh-phu", headers=headers).status_code == 204
    assert client.get("/api/v1/petland/map/sanh-phu").status_code == 204


def test_public_map_hides_admin_detail_but_keeps_portal(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    headers = auth("admin")
    client.put("/api/v1/admin/petland/map", headers=headers, json=_body(portal={"x": 4, "y": 6}))
    public = client.get("/api/v1/petland/map").json()
    assert public["portal"] == {"x": 4, "y": 6}
    row = db_session.get(PetlandMap, "main")
    assert row is not None and (row.portal_x, row.portal_y) == (4, 6)
