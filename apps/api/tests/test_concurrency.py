"""Real concurrency tests for the register race (P0-6).

The unit test in test_auth.py forces IntegrityError with a mock. This file drives
the actual path against PostgreSQL. Skipped when no PostgreSQL is reachable.

Note on scheduling: a naive "fire N threads at once" test does NOT reproduce the
race — the first thread commits before the others run their pre-check, so every
loser is rejected by the advisory check and the IntegrityError branch is never
entered. `test_forced_interleaving_*` uses a barrier placed after the pre-check
and before the commit to guarantee all writers are in flight simultaneously.
"""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.redis_client import get_redis
from app.core.security import get_password_hash as real_get_password_hash
from app.main import app
from app.models import User  # noqa: F401 — registers the table
from tests.conftest import FakeRedis

# Bắt buộc TEST_DATABASE_URL, không mặc định vào dev: các test ở đây ghi thẳng
# vào cơ sở dữ liệu (test_ruby_race còn DELETE full-table các bảng pet), chạy
# nhầm vào DB dev là mất dữ liệu thật (đã xảy ra 2026-08-30). CI set sẵn biến này.
POSTGRES_URL: str = os.environ.get("TEST_DATABASE_URL") or ""
if not POSTGRES_URL:
    pytest.skip("cần TEST_DATABASE_URL — không chạy test ghi vào DB dev", allow_module_level=True)
CONCURRENCY = 12
PASSWORD = "correct-horse-battery"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(POSTGRES_URL, pool_size=CONCURRENCY + 4, max_overflow=8)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable at {POSTGRES_URL}: {exc}")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_client(pg_engine):
    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def override_get_db():
        # One session per request, exactly as production does.
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # Ghi đè cả Redis, không chỉ database.
    #
    # `/register` có giới hạn tần suất theo IP (P1-8), và `TestClient` luôn gửi
    # cùng một địa chỉ — nên dùng Redis THẬT ở đây biến bộ đếm thành trạng thái
    # dùng chung giữa các test và giữa các lần chạy. Ba test này đã đỏ đúng như
    # thế: cả 12 request trả 429 vì bộ đếm còn nguyên từ lần chạy trước, và lỗi
    # chỉ hiện ở CI nơi có Redis thật, không hiện ở lệnh `-m "not integration"`
    # vẫn chạy hằng ngày.
    #
    # Thứ đang được kiểm ở đây là cuộc đua trên chỉ mục duy nhất, không phải
    # giới hạn tần suất. Cho nó một bộ đếm sạch mỗi test là trả lại cho test
    # đúng phạm vi của nó.
    app.dependency_overrides[get_redis] = lambda: FakeRedis()
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def unique_email(pg_engine):
    email = f"race-{uuid.uuid4().hex}@example.com"
    yield email
    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})


def _register(email: str) -> int:
    # A client per thread, without the context manager: entering it would run the
    # lifespan (and its create_all) once per thread, which serialises on DDL locks.
    return (
        TestClient(app)
        .post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
        .status_code
    )


def _run(email: str, workers: int = CONCURRENCY) -> list[int]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda _: _register(email), range(workers)))


def test_forced_interleaving_produces_one_201_and_no_500(pg_client, unique_email):
    """Every writer clears the pre-check before any of them commits.

    This is the only arrangement that actually reaches the unique-index violation,
    and it fails with a 500 if the IntegrityError branch is removed.
    """
    barrier = threading.Barrier(CONCURRENCY, timeout=30)

    def hash_then_wait(password: str) -> str:
        # Called after the advisory pre-check and before db.commit().
        barrier.wait()
        return real_get_password_hash(password)

    with patch("app.api.routes.auth.get_password_hash", side_effect=hash_then_wait):
        codes = _run(unique_email)

    assert 500 not in codes, f"unique-index violation surfaced as a server error: {codes}"
    assert codes.count(201) == 1, f"expected exactly one winner, got {codes}"
    assert codes.count(409) == CONCURRENCY - 1, f"losers must all be 409, got {codes}"


def test_forced_interleaving_persists_exactly_one_row(pg_client, unique_email, pg_engine):
    barrier = threading.Barrier(CONCURRENCY, timeout=30)

    def hash_then_wait(password: str) -> str:
        barrier.wait()
        return real_get_password_hash(password)

    with patch("app.api.routes.auth.get_password_hash", side_effect=hash_then_wait):
        _run(unique_email)

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM users WHERE email = :e"), {"e": unique_email}
        ).scalar_one()
    assert count == 1


def test_natural_concurrency_is_also_clean(pg_client, unique_email):
    """Unsynchronised load. Whether this reaches the unique-index violation is
    timing-dependent — it does so often enough to fail against the unfixed code,
    but not reliably, which is exactly why the barrier tests above exist. Kept as
    a smoke test, not as the regression guard."""
    codes = _run(unique_email)
    assert 500 not in codes
    assert codes.count(201) == 1
    assert set(codes) <= {201, 409}


def test_forced_interleaving_assistant_conversation(pg_engine):
    """Hai lượt hỏi đầu tiên cùng lúc chỉ được mở MỘT cuộc trợ lý.

    Cùng lý do đã ghi ở đầu tệp: bắn N luồng không tái hiện được cuộc đua, vì
    người đầu tiên commit xong trước khi người sau kịp đọc. `Barrier` đặt sau
    lượt đọc và trước lượt ghi mới ép cả hai bên cùng tin rằng "chưa có cuộc
    nào" — đúng trạng thái mà chỉ mục duy nhất từng phần tồn tại để chặn.

    Không có chỉ mục ấy, test này để lại hai cuộc và lịch sử của người học tách
    làm hai mà không có lỗi nào được ném ra.
    """
    from sqlalchemy import select

    from app.models.chat import CoachConversation
    from app.models.user import User as UserModel
    from app.services import assistant

    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    setup = factory()
    user = UserModel(
        email=f"race-assistant-{uuid.uuid4()}@example.com",
        hashed_password=real_get_password_hash(PASSWORD),
    )
    setup.add(user)
    setup.commit()
    user_id = user.id
    setup.close()

    racers = 8
    barrier = threading.Barrier(racers)
    errors: list[BaseException] = []

    def open_one() -> None:
        session = factory()
        try:
            person = session.get(UserModel, user_id)
            assert person is not None
            assert assistant._find(session, person) is None
            barrier.wait(timeout=10)  # tất cả cùng tin "chưa có cuộc nào"
            assistant._open(session, person)
        except BaseException as exc:  # noqa: BLE001 — gom lại để khẳng định ngoài luồng
            errors.append(exc)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=racers) as pool:
        list(pool.map(lambda _: open_one(), range(racers)))

    assert not errors, f"lượt thua cuộc đua phải đọc lại, không được ném: {errors!r}"

    check = factory()
    rows = check.scalars(
        select(CoachConversation).where(
            CoachConversation.user_id == user_id, CoachConversation.attempt_id.is_(None)
        )
    ).all()
    check.close()
    assert len(rows) == 1, f"phải đúng một cuộc trợ lý, có {len(rows)}"
