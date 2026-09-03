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
from app.models.pet import DEFAULT_PET_SPECIES
from app.services import ruby

# Bắt buộc TEST_DATABASE_URL, không mặc định vào dev: các test ở đây DELETE
# full-table (pet_owned/pet_state/pet_species), chạy nhầm vào DB dev là mất
# toàn bộ bộ sưu tập thú (đã xảy ra 2026-08-30). CI set sẵn biến này.
POSTGRES_URL: str = os.environ.get("TEST_DATABASE_URL") or ""
if not POSTGRES_URL:
    pytest.skip(
        "cần TEST_DATABASE_URL — không chạy test phá dữ liệu trên DB dev",
        allow_module_level=True,
    )
BUYERS = 8
EGG_PRICE = 25
SEEDERS = 8

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


# --- gieo lười bảng loài (ADR-010 §6.3) ------------------------------------


def test_seeding_the_species_table_survives_a_tie(pg_engine):
    """Hai request đầu tiên sau một lần triển khai cùng gieo bảng loài.

    `all_species` là bảng gieo lười CUỐI CÙNG còn thiếu chốt chống đua, và nó
    nằm trên đường đọc nóng nhất của cả góc thú cưng: `ensure_pet` gọi nó ở mỗi
    lần mở bảng. Người thua cuộc đua vỡ khoá chính và mất nguyên một lượt học vì
    một cuộc đua trên bảng CẤU HÌNH.

    Hàng rào nằm GIỮA lần đọc và lần ghi, đúng bài học của hai bài trên: chặn
    trước khi gọi thì luồng đầu đọc-gieo-commit trọn vẹn xong trước khi luồng
    sau kịp đọc, nên chúng thấy bảng đã đầy và không bao giờ vào nhánh gieo —
    bài kiểm xanh y hệt cả khi chốt bị gỡ. Tôi đã đo đúng như thế trước khi dời
    hàng rào vào đây.

    Khe để chèn là vòng lặp trên `DEFAULT_PET_SPECIES`: nó chạy ngay sau lần đọc
    thấy bảng rỗng và ngay trước `commit`. Cùng kỹ thuật mà bài mua trứng dùng
    với `ruby.balance`.
    """
    from app.models import PetSpecies  # noqa: PLC0415 — chỉ tệp này cần
    from app.services import pet_species

    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM pet_owned"))
        conn.execute(text("DELETE FROM pet_state"))
        conn.execute(text("DELETE FROM pet_species"))

    barrier = threading.Barrier(SEEDERS)

    class _WaitBeforeSeeding(list):
        """Danh sách mặc định, nhưng dừng lại một nhịp ở lần duyệt đầu.

        Hết giờ nghĩa là các luồng khác không vào nổi tới đây — tức là có thứ gì
        đó đang nối tiếp hoá chúng, và đó cũng là một câu trả lời hợp lệ.
        """

        def __iter__(self):
            try:
                barrier.wait(timeout=1.5)
            except threading.BrokenBarrierError:
                pass
            return super().__iter__()

    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def seed() -> str:
        session = factory()
        try:
            return f"{len(pet_species.all_species(session))} loài"
        except Exception as exc:  # pragma: no cover - chính là thứ đang được kiểm
            return f"vỡ: {type(exc).__name__}"
        finally:
            session.close()

    with patch.object(pet_species, "DEFAULT_PET_SPECIES", _WaitBeforeSeeding(DEFAULT_PET_SPECIES)):
        with ThreadPoolExecutor(max_workers=SEEDERS) as pool:
            results = list(pool.map(lambda _: seed(), range(SEEDERS)))

    assert all(not r.startswith("vỡ") for r in results), results

    # Và bảng chỉ được gieo MỘT lần, không nhân đôi.
    session = factory()
    total = session.scalar(select(func.count()).select_from(PetSpecies))
    session.close()
    assert total == len(DEFAULT_PET_SPECIES)


def test_the_first_panel_open_never_collides_on_the_pet_row(pg_engine):
    """Lần mở bảng ĐẦU TIÊN của một tài khoản bắn hai request cùng lúc.

    `GET /pet` và `GET /pet/encounters` cùng đi qua `ensure_pet`, và trên một tài
    khoản chưa có hàng nào thì cả hai cùng thấy `None` và cùng dựng — người thua
    vỡ `pet_state_pkey` và nhận 500 ngay ở lần mở góc thú cưng đầu tiên của đời
    tài khoản đó.

    Bắt được nhờ một lượt chạy e2e đỏ ở chỗ chẳng liên quan (`SyntaxError:
    Unexpected token 'I', "Internal S"...`), không phải nhờ đọc mã: cuộc đua chỉ
    trúng khi hai request rơi vào đúng vài mili giây của nhau.

    Hàng rào nằm giữa lần đọc thấy `None` và lần ghi, đúng chỗ khe mở ra. Đã
    kiểm cả hai chiều: gỡ `try/except IntegrityError` trong `ensure_pet` thì bài
    này đỏ với đúng `IntegrityError` ấy.
    """
    # Vá ở SERVICE, không ở route. `ensure_pet` và `db_get_state` đã dời sang
    # `services/pet_state.py` khi việc học bắt đầu nuôi con thú — luồng học cần
    # gọi sang góc thú cưng, và để cả hai ở tầng route thì hai chiều khép thành
    # một vòng import. Vá `routes.pet` sau khi dời vẫn CHẠY và vẫn XANH: hàng rào
    # chỉ không bao giờ được gọi, nên cuộc đua không xảy ra và bài kiểm khẳng
    # định một thứ nó không còn kiểm nữa.
    from app.models import PetOwned, PetState  # noqa: PLC0415
    from app.services import pet_state  # noqa: PLC0415

    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    session = factory()
    user = User(email=f"pet-race-{uuid.uuid4().hex}@example.com", hashed_password="x")
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()

    barrier = threading.Barrier(SEEDERS)
    real_get = pet_state.db_get_state

    def read_then_wait(db, user_id_):
        # Ngay giữa "chưa có" và "dựng" — đúng khe mà hai request đầu tiên rơi vào.
        found = real_get(db, user_id_)
        try:
            barrier.wait(timeout=1.5)
        except threading.BrokenBarrierError:
            pass
        return found

    def open_panel() -> str:
        db = factory()
        try:
            pet_state.ensure_pet(db, user_id)
            return "ok"
        except Exception as exc:  # pragma: no cover - chính là thứ đang được kiểm
            return f"vỡ: {type(exc).__name__}"
        finally:
            db.close()

    with patch.object(pet_state, "db_get_state", side_effect=read_then_wait):
        with ThreadPoolExecutor(max_workers=SEEDERS) as pool:
            results = list(pool.map(lambda _: open_panel(), range(SEEDERS)))

    assert all(r == "ok" for r in results), results

    session = factory()
    states = session.scalar(
        select(func.count()).select_from(PetState).where(PetState.user_id == user_id)
    )
    owned = session.scalar(
        select(func.count()).select_from(PetOwned).where(PetOwned.user_id == user_id)
    )
    session.close()
    assert (states, owned) == (1, 1)

    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM pet_owned WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM pet_state WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
