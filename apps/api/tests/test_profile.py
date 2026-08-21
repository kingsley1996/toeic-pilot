from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.profile import UserProfile
from app.models.user import User
from app.services.profile_stats import compute_streaks

EMAIL = "profile@example.com"
PASSWORD = "correct-horse-battery"


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def signed_in(client: TestClient) -> dict[str, str]:
    register(client)
    return {"Authorization": f"Bearer {login(client)}"}


# --- the row exists from the start ----------------------------------------


def test_register_creates_the_profile_row(client: TestClient, db_session: Session):
    response = register(client)
    assert response.status_code == 201

    user = db_session.query(User).filter(User.email == EMAIL).one()
    profile = db_session.get(UserProfile, user.id)
    # Created in the same transaction as the account, not on first read. If this
    # ever becomes lazy, every read site grows a null check and the one that gets
    # forgotten is a 500.
    assert profile is not None
    assert profile.timezone == "Asia/Ho_Chi_Minh"
    assert profile.locale == "vi"
    assert profile.display_name is None


def test_me_embeds_the_profile(client: TestClient):
    headers = signed_in(client)
    body = client.get("/api/v1/auth/me", headers=headers).json()
    # The header renders a name on first paint; a second request for it would put
    # a second loading state inside the one place the app resolves the session.
    assert body["profile"]["timezone"] == "Asia/Ho_Chi_Minh"
    assert body["profile"]["display_name"] is None


def test_profile_requires_authentication(client: TestClient):
    assert client.get("/api/v1/profile").status_code == 401
    assert client.patch("/api/v1/profile", json={}).status_code == 401
    assert client.get("/api/v1/profile/stats").status_code == 401


# --- partial update -------------------------------------------------------


def test_patch_updates_only_what_it_is_given(client: TestClient):
    headers = signed_in(client)
    client.patch(
        "/api/v1/profile", json={"display_name": "Linh", "target_score": 800}, headers=headers
    )

    body = client.patch("/api/v1/profile", json={"minutes_per_day": 30}, headers=headers).json()

    # Sending one field must not blank the others.
    assert body["display_name"] == "Linh"
    assert body["target_score"] == 800
    assert body["minutes_per_day"] == 30


def test_explicit_null_clears_a_field(client: TestClient):
    headers = signed_in(client)
    client.patch("/api/v1/profile", json={"exam_date": "2026-12-01"}, headers=headers)

    body = client.patch("/api/v1/profile", json={"exam_date": None}, headers=headers).json()

    # The whole point of `exclude_unset`: absent means "leave alone", null means
    # "clear". A `value or existing` merge makes this assertion fail while the
    # endpoint still answers 200, so nobody finds out until they reload.
    assert body["exam_date"] is None


def test_null_is_ignored_for_the_not_null_columns(client: TestClient):
    headers = signed_in(client)
    body = client.patch(
        "/api/v1/profile", json={"timezone": None, "locale": None}, headers=headers
    ).json()

    # There is no meaningful "no time zone", so this is a nonsense request rather
    # than a clear request — and letting it reach the database is a 500.
    assert body["timezone"] == "Asia/Ho_Chi_Minh"
    assert body["locale"] == "vi"


def test_timezone_must_be_a_real_zone(client: TestClient):
    headers = signed_in(client)
    assert (
        client.patch(
            "/api/v1/profile", json={"timezone": "Asia/Hanoi"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/profile", json={"timezone": "Europe/London"}, headers=headers
        ).status_code
        == 200
    )


def test_target_score_must_be_a_score_that_exists(client: TestClient):
    headers = signed_in(client)
    # TOEIC is reported 10–990 in steps of 5, so 812 is not a goal anyone can reach.
    assert (
        client.patch("/api/v1/profile", json={"target_score": 812}, headers=headers).status_code
        == 422
    )
    assert (
        client.patch("/api/v1/profile", json={"target_score": 1000}, headers=headers).status_code
        == 422
    )
    assert (
        client.patch("/api/v1/profile", json={"target_score": 990}, headers=headers).status_code
        == 200
    )


def test_preferred_accent_must_be_one_we_synthesise(client: TestClient):
    headers = signed_in(client)
    assert (
        client.patch(
            "/api/v1/profile", json={"preferred_accent": "en-IE"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/profile", json={"preferred_accent": "en-GB"}, headers=headers
        ).status_code
        == 200
    )


def test_display_name_cannot_be_blank(client: TestClient):
    headers = signed_in(client)
    assert (
        client.patch("/api/v1/profile", json={"display_name": ""}, headers=headers).status_code
        == 422
    )


# --- password change and token revocation ---------------------------------


def test_wrong_current_password_is_403_not_401(client: TestClient):
    headers = signed_in(client)
    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": "not-it", "new_password": "brand-new-passphrase"},
        headers=headers,
    )
    # 401 would tell the frontend the session expired and bounce the user to
    # /login, when in fact they are signed in and merely mistyped.
    assert response.status_code == 403


def test_changing_the_password_kills_the_old_token(client: TestClient):
    register(client)
    old_token = login(client)
    old_headers = {"Authorization": f"Bearer {old_token}"}
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 200

    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-passphrase"},
        headers=old_headers,
    )
    assert response.status_code == 200

    # The session the user was worried about is the one this has to end.
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401


def test_the_replacement_token_still_works(client: TestClient):
    register(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    new_token = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-passphrase"},
        headers=headers,
    ).json()["access_token"]

    # Without handing back a token, changing your password logs you out on the
    # spot and looks exactly like a bug.
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code
        == 200
    )


def test_the_new_password_is_the_one_that_logs_in(client: TestClient):
    register(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-passphrase"},
        headers=headers,
    )

    assert (
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "brand-new-passphrase"}
        ).status_code
        == 200
    )


def test_untouched_passwords_leave_sessions_alone(client: TestClient, db_session: Session):
    """Shipping the mechanism must not sign out everyone who is already in.

    Tokens minted before `iat` existed carry no claim to compare, so an account
    that never changed its password is never checked against anything.
    """
    register(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    user = db_session.query(User).filter(User.email == EMAIL).one()
    assert user.password_changed_at is None
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_a_token_without_the_claim_is_refused_once_the_password_moved(
    client: TestClient, db_session: Session
):
    """A token predating the claim reads as generation zero, and zero is not current.

    This is also the case an "issued after" comparison gets wrong: the forged
    token below is minted in the *same second* as the password change, so its
    `iat` cannot be ordered against it. Equality on the generation has no such
    blind spot, which is why this test is deterministic rather than a coin flip
    on how long bcrypt happened to take.
    """
    from jose import jwt

    from app.core.config import settings

    register(client)
    user = db_session.query(User).filter(User.email == EMAIL).one()
    user.password_changed_at = datetime.now(UTC)
    db_session.commit()

    legacy = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code
        == 401
    )


def test_two_changes_one_microsecond_apart_are_different_generations(
    client: TestClient, db_session: Session
):
    """The resolution of `password_epoch` is the thing under test, so it is set
    explicitly rather than left to how long bcrypt happened to take.

    An end-to-end "change it twice quickly" test proves nothing here: two hashes
    take long enough that the two changes almost always land in different
    seconds, so it passes at second resolution too.
    """
    from jose import jwt

    from app.core.config import settings
    from app.core.security import PASSWORD_CLAIM, password_epoch

    register(client)
    user = db_session.query(User).filter(User.email == EMAIL).one()

    first = datetime(2026, 8, 10, 9, 0, 0, 500_000, tzinfo=UTC)
    second = first + timedelta(microseconds=1)
    assert password_epoch(first) != password_epoch(second)

    user.password_changed_at = second
    db_session.commit()

    stale = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            PASSWORD_CLAIM: password_epoch(first),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {stale}"}).status_code
        == 401
    )


def test_the_generation_survives_a_database_round_trip(client: TestClient, db_session: Session):
    """Login recomputes the generation from the stored column, so what the
    database gives back has to equal what was written — including on SQLite,
    which returns the value naive and would otherwise be read as local time.
    """
    from app.core.security import password_epoch

    register(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "second-passphrase-here"},
        headers=headers,
    )

    db_session.expire_all()
    user = db_session.query(User).filter(User.email == EMAIL).one()
    fresh = login(client, password="second-passphrase-here")
    from jose import jwt

    from app.core.config import settings
    from app.core.security import PASSWORD_CLAIM

    payload = jwt.decode(fresh, settings.secret_key, algorithms=[settings.algorithm])
    assert payload[PASSWORD_CLAIM] == password_epoch(user.password_changed_at)


# --- streak arithmetic ----------------------------------------------------


def test_streak_of_nothing_is_zero():
    assert compute_streaks(set(), date(2026, 8, 10)) == (0, 0)


def test_current_streak_counts_back_from_today():
    days = {date(2026, 8, 8), date(2026, 8, 9), date(2026, 8, 10)}
    assert compute_streaks(days, date(2026, 8, 10)) == (3, 3)


def test_a_day_still_in_progress_does_not_break_the_streak():
    days = {date(2026, 8, 8), date(2026, 8, 9)}
    # Nothing studied today *yet*. Zeroing the streak at 00:01 tells the learner
    # they lost it while they still have the whole day to keep it.
    assert compute_streaks(days, date(2026, 8, 10))[0] == 2


def test_the_streak_is_broken_by_a_missed_day():
    days = {date(2026, 8, 5), date(2026, 8, 6), date(2026, 8, 9), date(2026, 8, 10)}
    current, longest = compute_streaks(days, date(2026, 8, 10))
    assert current == 2
    assert longest == 2


def test_longest_streak_can_be_in_the_past():
    days = {
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 3),
        date(2026, 7, 4),
        date(2026, 8, 10),
    }
    assert compute_streaks(days, date(2026, 8, 10)) == (1, 4)


def test_a_gap_of_two_days_ends_the_current_streak():
    days = {date(2026, 8, 7), date(2026, 8, 8)}
    assert compute_streaks(days, date(2026, 8, 10))[0] == 0


# --- stats ----------------------------------------------------------------


def test_stats_start_empty_and_are_shaped_right(client: TestClient):
    headers = signed_in(client)
    body = client.get("/api/v1/profile/stats", headers=headers).json()

    assert body["reviews_total"] == 0
    assert body["dictation_completed"] == 0
    assert body["current_streak"] == 0
    # Thưa: chưa học ngày nào thì lịch rỗng, chứ không phải 365 hàng số 0.
    assert body["calendar"] == []
    # Lưới do trình duyệt dựng, nên nó cần đúng hai thứ này và không cần gì thêm.
    assert body["window_days"] == 365
    assert body["today"]


def test_the_calendar_only_carries_days_with_activity(client: TestClient, db_session: Session):
    """Thưa chứ không đặc, và ngày trong lịch phải là ngày TRONG múi giờ hồ sơ.

    Một lượt ôn lúc 23:30 giờ Hà Nội là 16:30 UTC cùng ngày, nhưng một lượt lúc
    00:30 là 17:30 UTC của ngày HÔM TRƯỚC — nếu lịch tính theo UTC thì ô sáng
    lên nằm sai một cột so với chuỗi ngày, và không có gì báo.
    """
    import uuid as uuidlib

    from app.models.vocabulary import VocabularyReviewLog

    headers = signed_in(client)
    user = db_session.query(User).filter(User.email == EMAIL).one()

    entry_id = uuidlib.uuid4()
    # 17:30 UTC = 00:30 hôm sau ở Asia/Ho_Chi_Minh (UTC+7).
    late = datetime.now(UTC).replace(hour=17, minute=30, second=0, microsecond=0) - timedelta(
        days=2
    )
    db_session.add(
        VocabularyReviewLog(
            user_id=user.id,
            entry_id=entry_id,
            grade=4,
            interval_days=1,
            ease_factor=Decimal("2.50"),
            reviewed_at=late,
        )
    )
    db_session.commit()

    body = client.get("/api/v1/profile/stats", headers=headers).json()
    assert len(body["calendar"]) == 1
    assert body["calendar"][0]["reviews"] == 1
    # Ngày địa phương đi TRƯỚC một ngày so với ngày UTC của cùng mốc thời gian.
    assert body["calendar"][0]["date"] == (late + timedelta(hours=7)).date().isoformat()


def test_pet_must_be_a_mascot_that_exists(client: TestClient):
    """Một mascot không tồn tại bị chặn ở cổng, không lưu rồi hỏng sau.

    Cái giá của việc nới chỗ này là im lặng: giá trị sai vẫn lưu được, frontend
    tra bảng không thấy và rơi về con mặc định — nên người dùng chọn xong, thấy
    con cũ, và không có lỗi nào ở đâu cả.
    """
    headers = signed_in(client)
    assert (
        client.patch("/api/v1/profile", json={"pet": "dragon"}, headers=headers).status_code == 422
    )
    r = client.patch("/api/v1/profile", json={"pet": "rex"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["pet"] == "rex"


def test_pet_distinguishes_absent_from_null(client: TestClient):
    """Ba trạng thái, không phải hai — cùng luật `exclude_unset` như các cột khác.

    NULL ở đây là "chưa chọn", và frontend rơi về con mặc định của nó. Nếu khoá
    vắng mặt cũng xoá thì mọi lần lưu một trường khác sẽ âm thầm trả pet về mặc
    định, và nhận ra điều đó đòi phải nạp lại trang.
    """
    headers = signed_in(client)
    client.patch("/api/v1/profile", json={"pet": "rex"}, headers=headers)

    # khoá vắng mặt: giữ nguyên
    r = client.patch("/api/v1/profile", json={"locale": "en"}, headers=headers)
    assert r.json()["pet"] == "rex"

    # null tường minh: xoá
    r = client.patch("/api/v1/profile", json={"pet": None}, headers=headers)
    assert r.json()["pet"] is None
