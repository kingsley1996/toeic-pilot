import os

# Must run before app.core.database is imported: the module-level engine is built
# from settings.database_url at import time.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401 — registers every table on Base.metadata
from app.core.database import Base, get_db  # noqa: E402
from app.core.redis_client import get_redis  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    # StaticPool keeps every checkout on one connection; without it each connection
    # gets a private empty ":memory:" database and the tables vanish between calls.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeRedis:
    """Đủ dùng cho bộ đếm giới hạn tần suất, không hơn.

    Bộ test không dựng Redis, và bộ giới hạn cố ý **fail closed** — Redis là thứ
    duy nhất đứng giữa một tài khoản và hoá đơn Cloudinary, nên cho qua khi nó
    hỏng là mất tiền. Nghĩa là không có bản giả thì mọi test chạm endpoint có
    giới hạn đều nhận 503, và cám dỗ khi đó là bật `fail_open` — tức là tắt luôn
    thứ đang cần được test.
    """

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.values: dict[str, str] = {}

    def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key: str, seconds: int) -> bool:
        return True

    def ttl(self, key: str) -> int:
        return 60

    def setex(self, key: str, seconds: int, value: str) -> bool:
        self.values[key] = value
        return True

    def exists(self, key: str) -> int:
        return 1 if key in self.values else 0


@pytest.fixture()
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture()
def client(db_session: Session, fake_redis: FakeRedis) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
