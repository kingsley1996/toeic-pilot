"""Sổ cái ruby: kiếm một lần, tiêu không âm (ADR-011 lát 1 và 4).

Cuộc đua khi TIÊU là thứ duy nhất trong tài liệu này không kiểm được trên SQLite;
nó nằm ở `tests/test_ruby_race.py`, có `Barrier` và chạy trên Postgres.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RubyEvent, RubyRule, User
from app.models.ruby import DEFAULT_RUBY_RULES
from app.services import ruby


def _user(db: Session, email: str = "learner@example.com") -> User:
    user = User(email=email, hashed_password="x", role="learner")
    db.add(user)
    db.commit()
    return user


def test_the_rule_table_seeds_itself_on_first_read(db_session: Session) -> None:
    """Gieo LƯỜI, không gieo trong migration — cùng khuôn `pet_species`.

    Hệ quả phải nói ra: bảng rỗng nghĩa là "chưa từng cấu hình". Xoá hết rồi đọc
    lại thì bộ mặc định quay về, nên muốn bỏ một nguồn thì TẮT nó.
    """
    assert db_session.scalar(select(func.count(RubyRule.source_type))) == 0
    assert len(ruby.rules(db_session)) == len(DEFAULT_RUBY_RULES)

    db_session.query(RubyRule).delete()
    db_session.commit()
    assert len(ruby.rules(db_session)) == len(DEFAULT_RUBY_RULES)


def test_finishing_the_same_story_twice_pays_once(db_session: Session) -> None:
    """Khoá duy nhất LÀM LUÔN việc chống cày, thay cho một đoạn `if` phải nhớ viết.

    Đây là lý do bảng mức thưởng không cần trần ngày: nội dung tự giới hạn tốc độ.
    """
    user = _user(db_session)
    story = uuid.uuid4()

    first = ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=story)
    second = ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=story)
    db_session.commit()

    assert first == 5 and second == 0
    assert db_session.scalar(select(func.count(RubyEvent.id))) == 1
    assert ruby.balance(db_session, user.id) == 5


def test_a_second_story_pays_again(db_session: Session) -> None:
    """Khoá là (người, nguồn, thứ sinh ra nó) — không phải "một lần mỗi loại"."""
    user = _user(db_session)
    ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=uuid.uuid4())
    ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=uuid.uuid4())
    db_session.commit()
    assert ruby.balance(db_session, user.id) == 10


def test_a_daily_source_needs_a_deterministic_id(db_session: Session) -> None:
    """Postgres coi mọi NULL là khác nhau, nên `source_id` NULL không bị khoá chặn.

    Các khoản lặp theo ngày sinh uuid tất định từ (người, ngày, nguồn); gọi lại
    bao nhiêu lần trong ngày cũng chỉ trao một lần, còn hôm sau thì trao tiếp.
    """
    user = _user(db_session)
    today, tomorrow = date(2026, 8, 27), date(2026, 8, 28)

    def gift(day: date) -> int:
        return ruby.earn(
            db_session,
            user_id=user.id,
            source_type="daily_gift",
            source_id=ruby.daily_source_id(user.id, day, "daily_gift"),
        )

    assert gift(today) == 3
    assert gift(today) == 0
    assert gift(tomorrow) == 3
    db_session.commit()
    assert ruby.balance(db_session, user.id) == 6


def test_lowering_a_rate_never_claws_back_what_was_granted(db_session: Session) -> None:
    """Mỗi hàng giữ số ruby ĐÃ TRAO lúc đó. Cùng tính chất khiến mức XP an toàn để sửa."""
    user = _user(db_session)
    ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=uuid.uuid4())

    rule = db_session.get(RubyRule, "story_complete")
    assert rule is not None
    rule.amount = 1
    db_session.commit()

    ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=uuid.uuid4())
    db_session.commit()
    assert ruby.balance(db_session, user.id) == 6


def test_a_disabled_source_pays_nothing_and_raises_nothing(db_session: Session) -> None:
    """Tắt một nguồn là quyết định vận hành, không phải sự cố.

    Ném lỗi ở đây là để một luật gamification làm hỏng một lượt học — đúng thứ
    `progression.award` đã cấm.
    """
    user = _user(db_session)
    ruby.rules(db_session)
    rule = db_session.get(RubyRule, "daily_gift")
    assert rule is not None
    rule.enabled = False
    db_session.commit()

    assert (
        ruby.earn(db_session, user_id=user.id, source_type="daily_gift", source_id=uuid.uuid4())
        == 0
    )
    assert ruby.balance(db_session, user.id) == 0


def test_earn_refuses_a_spend_source(db_session: Session) -> None:
    """Mua trứng phải đi qua `spend`, nơi có khoá. Một đường tiêu không khoá là §5."""
    user = _user(db_session)
    with pytest.raises(ValueError, match="đường tiêu"):
        ruby.earn(db_session, user_id=user.id, source_type="egg", source_id=uuid.uuid4())


def test_spending_writes_a_negative_row_rather_than_subtracting(db_session: Session) -> None:
    """Lịch sử phải trả lời được "tôi có 40 ruby, giờ còn 10"."""
    user = _user(db_session)
    ruby.earn(db_session, user_id=user.id, source_type="attempt_full", source_id=uuid.uuid4())
    db_session.commit()

    left = ruby.spend(
        db_session, user_id=user.id, source_type="egg", source_id=uuid.uuid4(), amount=20
    )
    db_session.commit()

    assert left == 5 and ruby.balance(db_session, user.id) == 5
    # Hai hàng trong cùng một giây thì `created_at` bằng nhau (SQLite chỉ có độ
    # phân giải giây), nên thứ tự giữa chúng là ổn định chứ không có nghĩa; thứ
    # được ghim ở đây là CẢ HAI còn nguyên, không phải một phép trừ tại chỗ.
    assert sorted(e.amount for e in ruby.history(db_session, user.id)) == [-20, 25]


def test_spending_more_than_the_balance_is_refused(db_session: Session) -> None:
    user = _user(db_session)
    ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=uuid.uuid4())
    db_session.commit()

    with pytest.raises(ruby.NotEnoughRuby) as exc:
        ruby.spend(
            db_session, user_id=user.id, source_type="egg", source_id=uuid.uuid4(), amount=20
        )
    assert exc.value.needed == 20 and exc.value.available == 5
    assert ruby.balance(db_session, user.id) == 5


def test_two_spends_in_one_request_see_each_other(db_session: Session) -> None:
    """Session chạy `autoflush=False`, nên không `flush` thì lần tiêu thứ hai đọc
    ra số dư CŨ và cả hai cùng lọt — cuộc đua của §5 thu nhỏ vào một luồng."""
    user = _user(db_session)
    ruby.earn(db_session, user_id=user.id, source_type="attempt_full", source_id=uuid.uuid4())

    ruby.spend(db_session, user_id=user.id, source_type="egg", source_id=uuid.uuid4(), amount=20)
    with pytest.raises(ruby.NotEnoughRuby):
        ruby.spend(
            db_session, user_id=user.id, source_type="egg", source_id=uuid.uuid4(), amount=20
        )


def test_history_is_newest_first(db_session: Session) -> None:
    user = _user(db_session)
    base = datetime(2026, 8, 20, tzinfo=UTC)
    for offset in range(3):
        ruby.earn(
            db_session,
            user_id=user.id,
            source_type="story_complete",
            source_id=uuid.uuid4(),
            now=base + timedelta(days=offset),
        )
    db_session.commit()
    rows = ruby.history(db_session, user.id)
    assert [r.created_at.day for r in rows] == [22, 21, 20]


# --- màn quản trị (lát 5) --------------------------------------------------


def test_only_an_admin_can_price_the_economy(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`admin`, không phải `editor`: đặt giá cho cả nền kinh tế là quyền vận hành.

    Kiểm bằng dependency chứ không bằng một `if` trong thân hàm — một `if` là thứ
    người ta quên chép sang route kế tiếp.
    """
    assert client.get("/api/v1/admin/ruby/rules", headers=auth("learner")).status_code == 403
    assert client.get("/api/v1/admin/ruby/rules", headers=auth("editor")).status_code == 403
    assert client.get("/api/v1/admin/ruby/rules", headers=auth("admin")).status_code == 200


def test_editing_a_rate_takes_effect_without_a_deploy(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    headers = auth("admin")
    assert client.get("/api/v1/admin/ruby/rules", headers=headers).json()[0]["amount"] == 5
    changed = client.patch(
        "/api/v1/admin/ruby/rules/story_complete", json={"amount": 9}, headers=headers
    )
    assert changed.status_code == 200 and changed.json()["amount"] == 9

    user = _user(db_session, "another@example.com")
    assert (
        ruby.earn(db_session, user_id=user.id, source_type="story_complete", source_id=uuid.uuid4())
        == 9
    )


def test_a_disabled_rule_stays_visible_in_admin(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Giấu hàng đã tắt ở đây thì cách duy nhất bật lại là sửa database."""
    headers = auth("admin")
    client.patch("/api/v1/admin/ruby/rules/daily_gift", json={"enabled": False}, headers=headers)
    rows = client.get("/api/v1/admin/ruby/rules", headers=headers).json()
    assert any(row["source_type"] == "daily_gift" and row["enabled"] is False for row in rows)
