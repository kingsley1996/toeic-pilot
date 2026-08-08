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
