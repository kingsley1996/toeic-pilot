import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token

EMAIL = "learner@example.com"
PASSWORD = "correct-horse-battery"


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- register -------------------------------------------------------------


def test_register_returns_201_and_public_user(client: TestClient):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert uuid.UUID(body["id"])  # id is a real UUID
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_normalises_email_to_lowercase(client: TestClient):
    response = register(client, email="Mixed.Case@Example.COM")
    assert response.status_code == 201
    assert response.json()["email"] == "mixed.case@example.com"


def test_register_duplicate_email_returns_409(client: TestClient):
    assert register(client).status_code == 201
    response = register(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_register_short_password_returns_422(client: TestClient):
    response = register(client, password="short")
    assert response.status_code == 422


def test_register_invalid_email_returns_422(client: TestClient):
    response = register(client, email="not-an-email")
    assert response.status_code == 422


def test_register_race_on_unique_index_returns_409_not_500(client: TestClient):
    """P0-6 regression.

    Two concurrent registrations both clear the advisory pre-check; only the unique
    index stops the second. That surfaces as IntegrityError on commit. Racing real
    threads against SQLite is not deterministic, so the commit is forced to raise
    exactly what Postgres would raise, and we assert the branch maps it to 409.
    """
    boom = IntegrityError("INSERT INTO users", {}, Exception("duplicate key"))
    with patch.object(Session, "commit", side_effect=boom):
        response = register(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


# --- login ----------------------------------------------------------------


def test_login_returns_bearer_token(client: TestClient):
    register(client)
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_returns_401(client: TestClient):
    register(client)
    response = login(client, password="wrong-password-entirely")
    assert response.status_code == 401


def test_login_unknown_email_returns_401(client: TestClient):
    response = login(client, email="ghost@example.com")
    assert response.status_code == 401


def test_login_is_case_insensitive_on_email(client: TestClient):
    register(client)
    response = login(client, email=EMAIL.upper())
    assert response.status_code == 200


# --- /me ------------------------------------------------------------------


def test_me_with_valid_token_returns_current_user(client: TestClient):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_me_without_token_returns_401(client: TestClient):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_garbage_token_returns_401(client: TestClient):
    response = client.get("/api/v1/auth/me", headers=auth_header("not.a.jwt"))
    assert response.status_code == 401


@pytest.mark.parametrize("subject", ["admin", "1", "", "'; DROP TABLE users;--", "not-a-uuid"])
def test_me_with_non_uuid_subject_returns_401_not_500(client: TestClient, subject: str):
    """P0-5 regression.

    The token is correctly signed, so it clears decode_access_token; only `sub` is
    malformed. Comparing that text to a UUID column made Postgres raise DataError,
    which FastAPI surfaces as 500. A bad subject must be a 401.
    """
    token = create_access_token(subject)
    response = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_with_well_formed_but_unknown_uuid_returns_401(client: TestClient):
    token = create_access_token(str(uuid.uuid4()))
    response = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


# --- password length boundary (P1-1) --------------------------------------


def test_register_password_at_byte_limit_is_accepted(client: TestClient):
    at_limit = "a" * 72
    assert register(client, password=at_limit).status_code == 201
    assert login(client, password=at_limit).status_code == 200


def test_register_over_long_password_returns_422_not_500(client: TestClient):
    response = register(client, password="a" * 73)
    assert response.status_code == 422
    assert "72 bytes" in response.text


def test_register_multibyte_password_counted_in_bytes(client: TestClient):
    # 40 chars but 120 UTF-8 bytes — a char-based limit would wrongly allow this.
    response = register(client, password="đ" * 40)
    assert response.status_code == 422


def test_login_with_absurdly_long_password_returns_401_not_500(client: TestClient):
    register(client)
    response = login(client, password="a" * 5000)
    assert response.status_code == 401


def test_me_reports_the_role(client: TestClient, db_session: Session) -> None:
    # The frontend needs this to decide whether to offer the admin area at all;
    # without it a learner discovers the boundary as a 403.
    client.post(
        "/api/v1/auth/register",
        json={"email": "roles@example.com", "password": "supersecret123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "roles@example.com", "password": "supersecret123"},
    ).json()["access_token"]

    body = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert body["role"] == "learner"


def test_registration_cannot_choose_a_role(client: TestClient, db_session: Session) -> None:
    # A self-service signup that picks its own role is not a role system.
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "sneaky@example.com", "password": "supersecret123", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "learner"


# --- P1-8: giới hạn tần suất cho cửa đăng nhập ----------------------------


def test_client_ip_reads_the_last_forwarded_hop_not_the_first() -> None:
    """Phần tử CUỐI của `X-Forwarded-For`, không phải phần tử đầu.

    Client tự thêm được bao nhiêu mục tuỳ thích vào đầu chuỗi. Đọc mục đầu —
    cách hầu hết ví dụ trên mạng viết — nghĩa là kẻ tấn công tự đặt khoá giới
    hạn của mình và mỗi request lại là một khoá mới. Giới hạn khi đó trông như
    đang bảo vệ mà không chặn được gì.
    """
    from app.core.config import settings
    from app.core.rate_limit import client_ip

    request = _request_with(headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1, 203.0.113.7"})
    original = settings.trust_forwarded_for
    try:
        settings.trust_forwarded_for = True
        assert client_ip(request) == "203.0.113.7"
    finally:
        settings.trust_forwarded_for = original


def test_forwarded_header_is_ignored_unless_a_proxy_is_declared() -> None:
    """Mặc định TẮT, và mặc định đó là phần bảo mật.

    Không có proxy nào đứng trước mà vẫn tin header thì bất kỳ ai cũng tự khai
    IP của mình — tức là tự cấp cho mình hạn mức không giới hạn.
    """
    from app.core.config import settings
    from app.core.rate_limit import client_ip

    request = _request_with(headers={"x-forwarded-for": "9.9.9.9"})
    assert settings.trust_forwarded_for is False
    assert client_ip(request) == "198.51.100.4"


def _request_with(headers: dict[str, str]):  # type: ignore[no-untyped-def]
    from starlette.requests import Request

    raw = [(k.encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": ("198.51.100.4", 1234)})


def test_login_stops_answering_after_too_many_attempts(client: TestClient) -> None:
    """Đoán mật khẩu phải có trần.

    Trước đây `/login` không có giới hạn nào: bộ `rate_limit` cũ khoá theo
    `user.id`, mà `/login` tồn tại chính vì chưa có người dùng nào để khoá.
    """
    from app.api.routes.auth import LOGIN_QUOTA

    body = {"email": "khong-ton-tai@example.com", "password": "sai-mat-khau-123"}
    for _ in range(LOGIN_QUOTA.limit):
        assert client.post("/api/v1/auth/login", json=body).status_code == 401

    refused = client.post("/api/v1/auth/login", json=body)
    assert refused.status_code == 429
    # `Retry-After` là phần khiến 429 dùng được: không có nó, client chỉ biết
    # "bị chặn" mà không biết chờ bao lâu, và cách xử lý phổ biến nhất là thử lại ngay.
    assert refused.headers.get("Retry-After")


# --- logout ---------------------------------------------------------------


def test_logout_makes_the_same_token_stop_working(client: TestClient):
    """Đăng xuất phải thu hồi token, không chỉ xoá nó khỏi trình duyệt.

    Đây là lỗ thật của P1-7, và nó không dính gì tới XSS: trước bản này `logout`
    chỉ là `localStorage.removeItem` ở phía client, nên token vẫn sống thêm tới
    bảy ngày. Máy dùng chung, một phiên trình duyệt được khôi phục, hay một
    token lọt vào log — tất cả vẫn vào được, trong khi giao diện đã nói là đã
    đăng xuất.
    """
    register(client)
    token = login(client).json()["access_token"]

    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth_header(token)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 401


def test_logout_does_not_touch_the_other_sessions(client: TestClient):
    """Thu hồi MỘT phiên, không phải mọi phiên.

    Đây chính là chỗ khác biệt với `pwc`: đổi mật khẩu đăng xuất mọi thiết bị,
    và trước bản này đó là công cụ thu hồi duy nhất tồn tại. Đăng xuất trên máy
    ở thư viện mà rớt luôn phiên trên điện thoại là một sản phẩm khác.
    """
    register(client)
    laptop = login(client).json()["access_token"]
    phone = login(client).json()["access_token"]

    client.post("/api/v1/auth/logout", headers=auth_header(laptop))

    assert client.get("/api/v1/auth/me", headers=auth_header(phone)).status_code == 200


def test_logout_still_returns_204_when_redis_is_down(client: TestClient, fake_redis):
    """Redis hỏng thì đăng xuất vẫn phải báo thành công.

    Redis là phụ thuộc mềm ở khắp nơi khác, và trả 503 ở đây sẽ khiến giao diện
    giữ người dùng ở lại trạng thái đã đăng nhập — đúng cái trạng thái họ vừa
    bảo là muốn thoát ra. Client xoá token của mình dù thế nào; danh sách thu
    hồi là lớp phòng thủ thứ hai chứ không phải lớp duy nhất.
    """
    import redis as redis_lib

    register(client)
    token = login(client).json()["access_token"]

    def boom(*args: object, **kwargs: object) -> None:
        raise redis_lib.RedisError("down")

    fake_redis.setex = boom
    assert client.post("/api/v1/auth/logout", headers=auth_header(token)).status_code == 204
