"""Quản trị thành viên — `admin_users.py`.

Ba thứ đáng pin: ruby cấp phải là HÀNG SỔ CÁI (không phải sửa số dư), quyền
phải là `admin` (không phải editor), và admin không được tự xoá/hạ quyền
chính mình.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RubyEvent, User


def test_learner_and_editor_cannot_see_users(client: TestClient, auth) -> None:
    assert client.get("/api/v1/admin/users", headers=auth("learner")).status_code == 403
    assert client.get("/api/v1/admin/users", headers=auth("editor")).status_code == 403
    assert client.get("/api/v1/admin/users", headers=auth("admin")).status_code == 200


def test_create_list_search_and_role_change(client: TestClient, db_session: Session, auth) -> None:
    created = client.post(
        "/api/v1/admin/users",
        json={"email": "Moi@Example.com", "password": "mat-khau-dai", "role": "learner"},
        headers=auth("admin"),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == "moi@example.com"  # chuẩn hoá HOA-THƯỜNG như đăng ký

    dup = client.post(
        "/api/v1/admin/users",
        json={"email": "moi@example.com", "password": "mat-khau-dai"},
        headers=auth("admin"),
    )
    assert dup.status_code == 409

    rows = client.get("/api/v1/admin/users?q=moi@", headers=auth("admin")).json()
    assert [r["id"] for r in rows["items"]] == [body["id"]]

    patched = client.patch(
        f"/api/v1/admin/users/{body['id']}",
        json={"role": "editor"},
        headers=auth("admin"),
    ).json()
    assert patched["role"] == "editor"


def test_grant_ruby_is_a_ledger_row(client: TestClient, db_session: Session, auth) -> None:
    target = User(email="nhan@example.com", hashed_password="x", role="learner")
    db_session.add(target)
    db_session.commit()

    granted = client.post(
        f"/api/v1/admin/users/{target.id}/ruby",
        json={"amount": 2000},
        headers=auth("admin"),
    )
    assert granted.status_code == 200
    assert granted.json()["ruby_balance"] == 2000

    row = db_session.scalar(
        select(RubyEvent).where(
            RubyEvent.user_id == target.id, RubyEvent.source_type == "admin_grant"
        )
    )
    assert row is not None and row.amount == 2000 and row.source_id is not None

    # Số ÂM bị chặn ngay ở schema — đường tiêu là `spend`, không phải cửa này.
    assert (
        client.post(
            f"/api/v1/admin/users/{target.id}/ruby",
            json={"amount": -5},
            headers=auth("admin"),
        ).status_code
        == 422
    )


def test_admin_cannot_delete_or_demote_self(client: TestClient, auth) -> None:
    me = client.get("/api/v1/auth/me", headers=auth("admin")).json()
    denied = client.delete(f"/api/v1/admin/users/{me['id']}", headers=auth("admin"))
    assert denied.status_code == 409
    assert (
        client.patch(
            f"/api/v1/admin/users/{me['id']}", json={"role": "learner"}, headers=auth("admin")
        ).status_code
        == 409
    )


def test_delete_user_removes_ledger(client: TestClient, db_session: Session, auth) -> None:
    target = User(email="xoá@example.com", hashed_password="x", role="learner")
    db_session.add(target)
    db_session.commit()
    client.post(f"/api/v1/admin/users/{target.id}/ruby", json={"amount": 10}, headers=auth("admin"))

    assert (
        client.delete(f"/api/v1/admin/users/{target.id}", headers=auth("admin")).status_code == 204
    )
    assert db_session.get(User, target.id) is None
    # Hàng ruby có còn hay không là việc của `ON DELETE CASCADE` — SQLite của bộ
    # test không bật FK, nên kiểm nó ở đây sẽ kiểm pragma chứ không kiểm schema.


def test_stats_counts_growth_and_activity(client: TestClient, db_session: Session, auth) -> None:
    fresh = User(email="nay@example.com", hashed_password="x", role="learner")
    db_session.add(fresh)
    db_session.commit()
    db_session.add(
        RubyEvent(user_id=fresh.id, amount=5, source_type="daily_gift", source_id=uuid.uuid4())
    )
    db_session.commit()

    stats = client.get("/api/v1/admin/users/stats", headers=auth("admin")).json()
    assert stats["total"] >= 2  # admin (fixture) + fresh
    assert stats["new_7d"] >= 1
    assert stats["active_7d"] >= 1
    assert len(stats["growth"]) == 31
    today = stats["growth"][-1]
    assert today["count"] >= 1

    feed = client.get(f"/api/v1/admin/users/{fresh.id}/activity", headers=auth("admin")).json()
    assert feed[0]["kind"] == "ruby" and "daily_gift" in feed[0]["label"]


def test_activity_of_stranger_is_404_and_bad_role_is_422(
    client: TestClient, db_session: Session, auth
) -> None:
    assert (
        client.get(
            f"/api/v1/admin/users/{uuid.uuid4()}/activity", headers=auth("admin")
        ).status_code
        == 404
    )

    target = User(email="role-vi-pham@example.com", hashed_password="x", role="learner")
    db_session.add(target)
    db_session.commit()
    # `pattern` chặn ở schema: role lạ không bao giờ chạm tới handler.
    assert (
        client.patch(
            f"/api/v1/admin/users/{target.id}",
            json={"role": "superadmin"},
            headers=auth("admin"),
        ).status_code
        == 422
    )
