"""Tiêu ruby đồng thời không bao giờ tạo ra số dư âm (ADR-011 §5, lát 4).

Cần Postgres THẬT: khoá tư vấn là thứ đang được kiểm, và SQLite không có nó.
Bỏ qua sạch sẽ khi không nối được, đúng khuôn `tests/test_concurrency.py`.

Bài học quan trọng nhất của tệp kia áp nguyên vào đây: **bắn N luồng không kiểm
được chuyện đua**. Luồng đầu commit xong trước khi các luồng sau tới chỗ đọc số
dư, nên chúng đọc ra con số ĐÃ TRỪ và tự chối — bài kiểm xanh y hệt cả khi khoá
bị gỡ. Hàng rào phải nằm GIỮA lần đọc số dư và lần ghi, đúng chỗ tệp kia đặt nó — đặt
trước lúc lấy khoá thì không đủ, và tôi đã đo: gỡ khoá đi bài kiểm vẫn xanh, vì
luồng đầu kịp đọc-ghi-commit trọn vẹn trước khi luồng sau xin được kết nối.

Hàng rào ở giữa lại có một vấn đề riêng: khi khoá CÓ mặt, luồng đang cầm khoá
đứng chờ những luồng đang xếp hàng chờ chính nó — khoá chết. Nên nó chờ có hạn
giờ và coi việc vỡ hàng rào là câu trả lời hợp lệ: *"các luồng khác không tới
được, tức là có thứ gì đó đang nối tiếp hoá chúng"*. Không khoá thì cả tám cùng
đọc thấy 30, hàng rào đầy ngay, cả tám cùng ghi −25 và số dư còn −170.

Đã kiểm cả hai chiều: cho `_lock_user` thành no-op thì bài kiểm đỏ với đúng con
số ấy; trả khoá về thì xanh.
"""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import RubyEvent, User  # noqa: F401 — đăng ký bảng lên metadata
from app.services import ruby

POSTGRES_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://toeic:toeic@localhost:5432/toeic"
)
BUYERS = 8
EGG_PRICE = 25

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(POSTGRES_URL, pool_size=BUYERS + 4, max_overflow=8)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable at {POSTGRES_URL}: {exc}")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def rich_learner(pg_engine):
    """Một người có đúng 30 ruby — đủ cho MỘT quả trứng 25, không đủ cho hai."""
    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    session = factory()
    user = User(email=f"ruby-race-{uuid.uuid4().hex}@example.com", hashed_password="x")
    session.add(user)
    session.commit()
    session.add(
        RubyEvent(user_id=user.id, amount=30, source_type="topic_mastered", source_id=uuid.uuid4())
    )
    session.commit()
    user_id = user.id
    session.close()

    yield user_id

    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM ruby_event WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})


def _buy(pg_engine, user_id: uuid.UUID) -> str:
    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        ruby.spend(
            session,
            user_id=user_id,
            source_type="egg",
            source_id=uuid.uuid4(),
            amount=EGG_PRICE,
        )
        session.commit()
        return "bought"
    except ruby.NotEnoughRuby:
        session.rollback()
        return "refused"
    finally:
        session.close()


def test_simultaneous_purchases_never_overdraw(pg_engine, rich_learner):
    """Tám lần mở trứng cùng lúc với 30 ruby: đúng một quả, số dư còn 5."""
    barrier = threading.Barrier(BUYERS)
    real_balance = ruby.balance

    def read_then_wait(session, user_id):
        # Ngay giữa "kiểm" và "ghi" — đúng khe mà §5 mô tả. Hết giờ nghĩa là các
        # luồng khác không vào nổi tới đây, tức là khoá đang làm việc của nó.
        value = real_balance(session, user_id)
        try:
            barrier.wait(timeout=1.5)
        except threading.BrokenBarrierError:
            pass
        return value

    with patch("app.services.ruby.balance", side_effect=read_then_wait):
        with ThreadPoolExecutor(max_workers=BUYERS) as pool:
            outcomes = list(pool.map(lambda _: _buy(pg_engine, rich_learner), range(BUYERS)))

    assert outcomes.count("bought") == 1, f"chỉ được một quả trứng, nhận: {outcomes}"

    with pg_engine.connect() as conn:
        balance = conn.execute(
            text("SELECT coalesce(sum(amount), 0) FROM ruby_event WHERE user_id = :u"),
            {"u": rich_learner},
        ).scalar_one()
        spent = conn.execute(
            text("SELECT count(*) FROM ruby_event WHERE user_id = :u AND amount < 0"),
            {"u": rich_learner},
        ).scalar_one()
    assert balance == 30 - EGG_PRICE
    assert spent == 1


def test_earning_concurrently_still_pays_once(pg_engine, rich_learner):
    """Đường KIẾM không cần khoá — ràng buộc duy nhất tự làm việc đó.

    Ghim ở đây vì nó là lý do `earn` được phép rẻ hơn `spend`: cùng một
    `source_id` thì chỉ một hàng lọt, dù bao nhiêu luồng cùng ghi.
    """
    story = uuid.uuid4()
    barrier = threading.Barrier(BUYERS, timeout=30)
    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def finish() -> int:
        session = factory()
        try:
            barrier.wait()
            granted = ruby.earn(
                session, user_id=rich_learner, source_type="story_complete", source_id=story
            )
            session.commit()
            return granted
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=BUYERS) as pool:
        grants = list(pool.map(lambda _: finish(), range(BUYERS)))

    assert sum(1 for g in grants if g > 0) == 1, f"một bài chỉ trả một lần: {grants}"
    session = factory()
    rows = session.scalar(
        select(func.count(RubyEvent.id)).where(
            RubyEvent.user_id == rich_learner, RubyEvent.source_type == "story_complete"
        )
    )
    session.close()
    assert rows == 1
