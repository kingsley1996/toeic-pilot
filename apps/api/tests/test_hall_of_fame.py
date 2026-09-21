"""Sảnh danh vọng: BXH level học viên + level thú cưng (SPEC-HALL-OF-FAME).

Mọi user lên bảng học viên, mọi con đang nuôi lên bảng thú — không cổng
private. Chưa đặt tên thì hiện email che, không bao giờ lộ nguyên email.
"""

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PetOwned, PetState, User
from app.models.profile import UserProfile
from app.models.progression import XpEvent


def _user(
    db: Session,
    email: str,
    *,
    xp: int = 0,
    level: int = 1,
    name: str | None = None,
) -> User:
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, hashed_password="x", role="learner")
        db.add(user)
        db.flush()
    profile = db.get(UserProfile, user.id)
    if profile is None:
        db.add(UserProfile(user_id=user.id, level_reached=level, display_name=name))
    else:
        profile.level_reached = level
        profile.display_name = name
    if xp:
        db.add(
            XpEvent(
                user_id=user.id,
                source_type="test",
                source_id=uuid.uuid4(),
                amount=xp,
                awarded_on=date(2026, 9, 21),
            )
        )
    db.commit()
    return user


def _pet(db: Session, user: User, species: str = "duck", *, level: int = 1, xp: int = 0) -> None:
    db.add(PetState(user_id=user.id, species=species))
    db.add(
        PetOwned(
            user_id=user.id,
            species=species,
            xp=xp,
            level_reached=level,
            fullness=0.6,
            energy=0.7,
            mood=0.7,
        )
    )
    db.commit()


def _login(client: TestClient, email: str) -> dict[str, str]:
    # Tài khoản có thể đã dựng tay ở trên — register 409 thì bỏ qua, login vẫn ăn.
    client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "supersecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ranking_is_by_total_xp_with_competition_ranks(
    client: TestClient, db_session: Session
) -> None:
    """Đồng XP thì cùng hạng, hạng kế nhảy (`1,2,2,4`) — không bốc thăm."""
    _user(db_session, "a@example.com", xp=100, level=5, name="An")
    _user(db_session, "b@example.com", xp=50, level=3, name="Bình")
    _user(db_session, "c@example.com", xp=50, level=2, name="Chi")
    _user(db_session, "d@example.com", xp=0, name="Dũng")

    body = client.get("/api/v1/hall-of-fame/users").json()
    assert [(e["rank"], e["display_name"], e["xp_total"]) for e in body["entries"]] == [
        (1, "An", 100),
        (2, "Bình", 50),
        (2, "Chi", 50),
        (4, "Dũng", 0),
    ]
    assert body["total"] == 4
    assert body["my_rank"] is None
    assert all(e["is_me"] is False for e in body["entries"])


def test_unnamed_users_show_a_masked_email_never_the_raw_one(
    client: TestClient, db_session: Session
) -> None:
    _user(db_session, "linhdn0908@example.com", xp=10)

    body = client.get("/api/v1/hall-of-fame/users").json()
    assert body["entries"][0]["display_name"] == "li***"
    assert "linhdn0908" not in client.get("/api/v1/hall-of-fame/users").text


def test_avatar_url_follows_the_profile_key(client: TestClient, db_session: Session) -> None:
    """Có ảnh thì trả đúng URL, không có thì null — cùng cách `profile_public`."""
    named = _user(db_session, "face@example.com", xp=10, name="Mặt")
    db_session.get(UserProfile, named.id).avatar_storage_key = "avatar/abc123.jpg"
    db_session.commit()
    _user(db_session, "plain@example.com", xp=5, name="Trơn")

    entries = {e["display_name"]: e for e in client.get("/api/v1/hall-of-fame/users").json()["entries"]}
    assert entries["Mặt"]["avatar_url"] is not None
    assert "avatar/abc123.jpg" in entries["Mặt"]["avatar_url"]
    assert entries["Trơn"]["avatar_url"] is None


def test_my_rank_counts_quietly_even_outside_the_limit(
    client: TestClient, db_session: Session
) -> None:
    _user(db_session, "top@example.com", xp=999, name="Top")
    _user(db_session, "mid@example.com", xp=50, name="Mid")
    headers = _login(client, "me@example.com")
    _user(db_session, "me@example.com", xp=10, name="Tôi")

    body = client.get("/api/v1/hall-of-fame/users?limit=1", headers=headers).json()
    assert len(body["entries"]) == 1
    assert body["my_rank"] == 3
    assert body["total"] == 3


def test_limit_outside_1_to_100_is_refused(client: TestClient) -> None:
    assert client.get("/api/v1/hall-of-fame/users?limit=101").status_code == 422
    assert client.get("/api/v1/hall-of-fame/pets?limit=0").status_code == 422


def test_pet_board_lists_every_owned_pet_not_just_the_active_one(
    client: TestClient, db_session: Session
) -> None:
    """Một hàng là một con — một người được chiếm nhiều hàng."""
    owner = _user(db_session, "keeper@example.com", name="Chủ")
    _pet(db_session, owner, "duck", level=2, xp=30)
    # Con thứ hai trong tủ, không dắt — vẫn lên bảng.
    db_session.add(PetOwned(user_id=owner.id, species="cat", xp=999, level_reached=9))
    db_session.commit()
    rookie = _user(db_session, "rookie@example.com")
    _pet(db_session, rookie, "frog", level=1, xp=5)

    body = client.get("/api/v1/hall-of-fame/pets").json()
    assert [(e["rank"], e["species"], e["level"]) for e in body["entries"]] == [
        (1, "cat", 9),
        (2, "duck", 2),
        (3, "frog", 1),
    ]
    assert body["total"] == 3


def test_my_pet_rank_is_my_best_pet(client: TestClient, db_session: Session) -> None:
    headers = _login(client, "best@example.com")
    me = _user(db_session, "best@example.com", name="Tôi")
    _pet(db_session, me, "duck", level=1, xp=0)
    db_session.add(PetOwned(user_id=me.id, species="cat", xp=100, level_reached=4))
    db_session.commit()
    rival = _user(db_session, "rival@example.com", name="Địch")
    _pet(db_session, rival, "frog", level=2, xp=10)

    body = client.get("/api/v1/hall-of-fame/pets", headers=headers).json()
    assert body["my_rank"] == 1
    assert [e["species"] for e in body["entries"] if e["is_me"]] == ["cat", "duck"]


def test_no_pet_means_no_pet_rank(client: TestClient, db_session: Session) -> None:
    headers = _login(client, "nopet@example.com")
    _user(db_session, "nopet@example.com", xp=5, name="Chưa")

    users = client.get("/api/v1/hall-of-fame/users", headers=headers).json()
    assert users["my_rank"] == 1
    pets = client.get("/api/v1/hall-of-fame/pets", headers=headers).json()
    assert pets["entries"] == [] and pets["my_rank"] is None and pets["total"] == 0
