"""Bảng `pet_state` (ADR-010 §4).

Chỉ kiểm hai thứ, và cả hai đều là chuyện hỏng im lặng chứ không phải chép lại
khai báo cột.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PetState, User


def make_user(db: Session, email: str) -> User:
    user = User(email=email, hashed_password="x")
    db.add(user)
    db.flush()
    return user


def test_a_pet_row_is_reachable_through_the_models_package(db_session: Session) -> None:
    """Model phải được xuất lại từ `app/models/__init__.py`.

    Đây là bài kiểm rẻ nhất cho một lỗi đắt: thiếu dòng xuất thì bảng không nằm
    trong `Base.metadata`, và hậu quả là "no such table" ở test cùng một
    `--autogenerate` RỖNG — tức migration tiếp theo lặng lẽ bỏ quên bảng này.
    Chèn được một hàng nghĩa là cả hai chuyện đó đều không xảy ra.
    """
    user = make_user(db_session, "pet-owner@example.com")
    db_session.add(PetState(user_id=user.id, species="cat"))
    db_session.commit()

    row = db_session.get(PetState, user.id)
    assert row is not None
    assert row.tile_x == 3 and row.tile_y == 8
    assert row.level_reached == 1
    assert row.needs_at is not None


@pytest.mark.parametrize("field", ["fullness", "energy", "mood"])
def test_a_need_outside_zero_to_one_is_refused(db_session: Session, field: str) -> None:
    """Ba nhu cầu là tỉ lệ, và tỉ lệ 1.4 không có nghĩa gì.

    Chốt ở tầng database chứ không chỉ ở tầng dịch vụ: phép trừ dần sẽ được gọi
    từ nhiều đường (đọc, cho ăn, đi dạo), và cái kẹp bị quên ở MỘT đường là thứ
    chỉ lộ ra dưới dạng một thanh chỉ số tràn khỏi khung.
    """
    user = make_user(db_session, f"pet-{field}@example.com")
    db_session.add(PetState(user_id=user.id, species="cat", **{field: 1.4}))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_one_pet_per_learner(db_session: Session) -> None:
    # Khoá chính CHÍNH LÀ khoá ngoại, nên "mỗi người một con" được ép ở tầng
    # database chứ không phải bằng một quy ước ai đó phải nhớ.
    user = make_user(db_session, "pet-twice@example.com")
    db_session.add(PetState(user_id=user.id, species="cat"))
    db_session.commit()
    db_session.add(PetState(user_id=uuid.UUID(str(user.id)), species="dog"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_the_pet_is_created_on_first_read_not_at_registration(
    client: TestClient, db_session: Session
) -> None:
    """Con thú dựng LÚC ĐỌC, không lúc đăng ký.

    Khác `user_profile`, vốn phải luôn tồn tại vì `get_current_user` đọc nó ở mọi
    request. Con thú chỉ có nghĩa với người đã mở góc này; tạo sẵn cho mọi tài
    khoản để chờ vài người bấm vào là trả tiền cho thứ chưa ai xin.
    """
    client.post(
        "/api/v1/auth/register", json={"email": "petless@example.com", "password": "supersecret123"}
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "petless@example.com", "password": "supersecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = db_session.scalars(select(User).where(User.email == "petless@example.com")).one()
    assert db_session.get(PetState, user.id) is None

    body = client.get("/api/v1/pet", headers=headers).json()
    assert body["species"] == "cat"
    assert (body["tile_x"], body["tile_y"]) == (3, 8)
    db_session.expire_all()
    assert db_session.get(PetState, user.id) is not None


def test_reading_twice_does_not_make_a_second_pet(client: TestClient, db_session: Session) -> None:
    # Khoá chính là khoá ngoại, nên hàng thứ hai sẽ nổ IntegrityError chứ không
    # lặng lẽ nhân đôi — nhưng đường đọc phải không bao giờ tới được chỗ đó.
    client.post(
        "/api/v1/auth/register", json={"email": "twice@example.com", "password": "supersecret123"}
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "twice@example.com", "password": "supersecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    first = client.get("/api/v1/pet", headers=headers).json()
    second = client.get("/api/v1/pet", headers=headers).json()
    assert first == second
    assert db_session.scalar(select(func.count(PetState.user_id))) == 1


def test_the_needs_carry_their_own_timestamp(client: TestClient, db_session: Session) -> None:
    """`needs.at` có mặt từ bây giờ, dù phép trừ dần còn ở lát sau.

    Thêm nó sau là một thay đổi hợp đồng ở đúng chỗ client đã kịp tin rằng ba con
    số kia là "bây giờ" — và niềm tin đó không sai ở đâu cả cho tới ngày phép trừ
    được bật lên.
    """
    client.post(
        "/api/v1/auth/register", json={"email": "needs@example.com", "password": "supersecret123"}
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "needs@example.com", "password": "supersecret123"}
    ).json()["access_token"]
    needs = client.get("/api/v1/pet", headers={"Authorization": f"Bearer {token}"}).json()["needs"]
    assert set(needs) == {"fullness", "energy", "mood", "at"}
    assert 0 <= needs["fullness"] <= 1
    assert needs["at"]


def test_the_pet_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/pet").status_code == 401


def auth_headers(client: TestClient, email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "supersecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_the_pet_stays_where_it_stopped(client: TestClient, db_session: Session) -> None:
    """Vị trí phải sống sót qua lần đọc sau — đó là cả lý do bảng này tồn tại.

    Bản Petland cũ giữ mọi thứ trong bộ nhớ trang: đóng tab là con thú về chỗ
    mặc định, và không có gì báo vì trang mới trông hoàn toàn bình thường.
    """
    headers = auth_headers(client, "walker@example.com")
    client.get("/api/v1/pet", headers=headers)

    moved = client.put(
        "/api/v1/pet/position",
        json={"tile_x": 11, "tile_y": 4, "facing": "left"},
        headers=headers,
    )
    assert moved.status_code == 200
    assert (moved.json()["tile_x"], moved.json()["tile_y"]) == (11, 4)

    again = client.get("/api/v1/pet", headers=headers).json()
    assert (again["tile_x"], again["tile_y"], again["facing"]) == (11, 4, "left")


def test_moving_does_not_let_the_client_set_its_own_needs(
    client: TestClient, db_session: Session
) -> None:
    """`PetMove` chỉ nhận toạ độ và hướng.

    Nhận nhu cầu từ trình duyệt là mở một đường sửa chỉ số bằng devtools: con thú
    lúc nào cũng no, và mọi thứ dựng trên nhu cầu — nhiệm vụ, XP — mất nghĩa.
    Pydantic bỏ khoá lạ, nên phép kiểm là con số KHÔNG đổi.
    """
    headers = auth_headers(client, "cheater@example.com")
    before = client.get("/api/v1/pet", headers=headers).json()["needs"]["fullness"]
    after = client.put(
        "/api/v1/pet/position",
        json={"tile_x": 2, "tile_y": 2, "facing": "right", "fullness": 1.0},
        headers=headers,
    ).json()["needs"]["fullness"]
    assert after == before


def test_a_facing_outside_the_two_values_is_refused(client: TestClient) -> None:
    # Cột `facing` có CHECK ở database; chặn từ tầng schema để lỗi là 422 nói rõ
    # trường nào, chứ không phải một IntegrityError 500.
    headers = auth_headers(client, "sideways@example.com")
    bad = client.put(
        "/api/v1/pet/position", json={"tile_x": 1, "tile_y": 1, "facing": "up"}, headers=headers
    )
    assert bad.status_code == 422
