"""Cấu hình nền lưới động.

Hai thứ đáng ghim và cả hai đều hỏng im lặng: đường đọc phải CÔNG KHAI (bắt xác
thực thì khách xem trang giới thiệu rơi về nền mặc định, tức cấu hình vừa đặt
không áp cho đúng nhóm đông nhất), và đường ghi phải đóng với học viên.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import BackdropSetting, User


def _user(db: Session, email: str, role: str) -> dict[str, str]:
    user = User(email=email, hashed_password="x", role=role)
    db.add(user)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_reading_the_backdrop_needs_no_account(client: TestClient) -> None:
    body = client.get("/api/v1/backdrop").json()
    assert body == {
        "spark_count": 2,
        "twinkle_count": 5,
        "color": "action",
        "speed_percent": 100,
        "enabled": True,
    }


def test_a_learner_cannot_change_it(client: TestClient, db_session: Session) -> None:
    headers = _user(db_session, "learner-backdrop@example.com", "learner")
    payload = {
        "spark_count": 4,
        "twinkle_count": 8,
        "color": "ok",
        "speed_percent": 100,
        "enabled": True,
    }
    assert client.put("/api/v1/admin/backdrop", json=payload, headers=headers).status_code == 403
    assert client.put("/api/v1/admin/backdrop", json=payload).status_code == 401


def test_an_editor_changes_it_and_the_public_read_reflects_it(
    client: TestClient, db_session: Session
) -> None:
    headers = _user(db_session, "editor-backdrop@example.com", "editor")
    saved = client.put(
        "/api/v1/admin/backdrop",
        json={
            "spark_count": 4,
            "twinkle_count": 0,
            "color": "accent-uk",
            "speed_percent": 175,
            "enabled": False,
        },
        headers=headers,
    )
    assert saved.status_code == 200
    assert client.get("/api/v1/backdrop").json() == {
        "spark_count": 4,
        "twinkle_count": 0,
        "color": "accent-uk",
        "speed_percent": 175,
        "enabled": False,
    }
    # Vẫn đúng MỘT hàng: cấu hình là singleton, và mọi lần ghi phải sửa hàng đó
    # chứ không chèn hàng mới. Một bảng cấu hình hai hàng thì `LIMIT 1` trả về
    # cái nào là chuyện của thứ tự vật lý — không lỗi, chỉ sai.
    assert db_session.query(BackdropSetting).count() == 1


def test_values_outside_the_allowed_range_are_refused(
    client: TestClient, db_session: Session
) -> None:
    headers = _user(db_session, "editor-range@example.com", "editor")
    base = {
        "spark_count": 2,
        "twinkle_count": 5,
        "color": "action",
        "speed_percent": 100,
        "enabled": True,
    }
    # Trần số lượng không phải chuyện hiệu năng mà là chuyện hình thức: nền có
    # mười hai tia thì không còn là nền.
    assert (
        client.put(
            "/api/v1/admin/backdrop", json={**base, "spark_count": 99}, headers=headers
        ).status_code
        == 422
    )
    # Mã màu tự do bị từ chối: chỉ token của hệ thiết kế mới có sẵn giá trị cho
    # cả nền sáng lẫn nền tối.
    assert (
        client.put(
            "/api/v1/admin/backdrop", json={**base, "color": "#ff00ff"}, headers=headers
        ).status_code
        == 422
    )
    # Tốc độ có cả sàn lẫn trần. Sàn tồn tại vì một vệt đi dưới một pixel mỗi
    # khung hình thì RUNG chứ không trôi (DESIGN-SYSTEM §9.7b) — chỉnh chậm quá
    # không cho ra hiệu ứng êm hơn mà cho ra hiệu ứng hỏng.
    for bad in (0, 10, 500):
        assert (
            client.put(
                "/api/v1/admin/backdrop", json={**base, "speed_percent": bad}, headers=headers
            ).status_code
            == 422
        ), bad
