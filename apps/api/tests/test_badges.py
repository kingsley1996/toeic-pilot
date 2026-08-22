"""Badge — điều kiện suy ra từ lịch sử, và bảng chỉ nhớ "đã xem chưa".

Bốn thứ được kiểm ở đây là bốn thứ hỏng im lặng:

  · danh sách mã ở service và union `BadgeCode` ở schema trôi khỏi nhau — mỗi
    nửa vẫn xanh với test của chính nó, còn frontend thì nhận một mã nó không
    biết vẽ, hoặc mất một badge mà không ai thấy thiếu;
  · dùng chuỗi ngày HIỆN TẠI thay vì chuỗi dài nhất, khiến badge biến mất vì
    nghỉ một hôm;
  · ghi hàng hai lần cho một badge, làm `awarded_at` nhảy về hôm nay và badge cũ
    lại sáng đèn "mới";
  · badge đọc số đo riêng thay vì dùng `gather_stats`, rồi nói khác trang hồ sơ.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.progression import BADGE_ICONS, BADGE_METRICS, DEFAULT_BADGE_RULES, UserBadge
from app.models.user import User
from app.models.vocabulary import VocabularyEntry, VocabularyReviewLog
from app.schemas.profile import BadgeIcon, BadgeMetric
from app.services import progression_config
from app.services.badges import evaluate, mark_seen, measure, record_new


def _user(db_session) -> uuid.UUID:
    user = User(
        email=f"badge-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("x" * 12),
    )
    db_session.add(user)
    db_session.flush()
    return user.id


def _review(db_session, user_id: uuid.UUID, when: datetime) -> None:
    """Một lượt ôn tại một thời điểm cụ thể — đủ để dựng lịch sử chuỗi ngày."""
    entry = VocabularyEntry(
        headword=f"w-{uuid.uuid4().hex[:8]}",
        part_of_speech="noun",
        meaning_en="x",
        meaning_vi="x",
        status="published",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add(
        VocabularyReviewLog(
            user_id=user_id,
            entry_id=entry.id,
            grade=4,
            interval_days=1,
            ease_factor=Decimal("2.5"),
            reviewed_at=when,
        )
    )
    db_session.flush()


def test_closed_sets_match_the_unions_the_frontend_compiles_against():
    """Tập đóng ở model và union ở schema phải kể cùng một danh sách.

    Từ khi huy hiệu là dữ liệu, `code` không còn kiểm được lúc biên dịch — đánh
    đổi có chủ ý để admin thêm huy hiệu mà không cần triển khai lại. Hai thứ CÒN
    đóng thì phải khớp tuyệt đối: `icon` vì frontend phải biết vẽ nó, và `metric`
    vì code phải biết đo nó. Lệch một phần tử là một huy hiệu không có hình, hoặc
    một luật không bao giờ mở — cả hai đều im lặng.
    """
    from typing import get_args

    assert set(BADGE_ICONS) == set(get_args(BadgeIcon))
    assert set(BADGE_METRICS) == set(get_args(BadgeMetric))


def test_default_rules_only_use_metrics_and_icons_that_exist():
    """Bộ mặc định phải hợp lệ theo chính hai tập đóng ở trên."""
    for _code, _label, _hint, icon, metric, target in DEFAULT_BADGE_RULES:
        assert icon in BADGE_ICONS
        assert metric in BADGE_METRICS
        assert target > 0


def test_first_review_opens_first_steps_and_nothing_else(db_session):
    user_id = _user(db_session)
    _review(db_session, user_id, datetime.now(tz=UTC))

    earned = {s.code for s in evaluate(db_session, user_id, "UTC") if s.earned}
    assert earned == {"first_steps"}


def test_streak_badge_uses_the_longest_streak_not_the_current_one(db_session):
    """Nghỉ một hôm không được lấy lại badge đã trao.

    Một badge đã đạt rồi biến mất là hình phạt cho việc nghỉ một ngày, và nó dạy
    người dùng rằng hệ thống lấy lại thứ đã cho. Bài này dựng bảy ngày liên tiếp
    rồi để đứt hẳn, nên `current_streak` bằng 0 trong khi `longest_streak` là 7.
    """
    user_id = _user(db_session)
    start = datetime.now(tz=UTC) - timedelta(days=30)
    for offset in range(7):
        _review(db_session, user_id, start + timedelta(days=offset))

    values = measure(db_session, user_id, "UTC")
    assert values["longest_streak"] == 7
    assert {s.code for s in evaluate(db_session, user_id, "UTC") if s.earned} >= {"streak_7"}


def test_progress_is_clamped_and_unearned_badges_still_come_back(db_session):
    """Badge chưa mở vẫn phải trả về, kèm tiến độ — đó là thứ nói "còn bao xa"."""
    user_id = _user(db_session)
    for _ in range(3):
        _review(db_session, user_id, datetime.now(tz=UTC))

    statuses = {s.code: s for s in evaluate(db_session, user_id, "UTC")}
    assert len(statuses) == len(DEFAULT_BADGE_RULES)
    assert statuses["first_steps"].progress == 1, "kẹp ở ngưỡng, không in 3/1"
    assert statuses["words_50"].earned is False
    assert statuses["words_50"].target == 50


def test_recording_twice_writes_one_row_and_keeps_the_first_timestamp(db_session):
    """`awarded_at` là LẦN ĐẦU hệ thống nhìn thấy, nên nó không được nhảy.

    Ghi lại mỗi lần đọc sẽ làm một badge cũ sáng đèn "mới" mãi mãi, và thông báo
    "bạn vừa mở badge mới" mất hết ý nghĩa.
    """
    user_id = _user(db_session)
    _review(db_session, user_id, datetime.now(tz=UTC))

    first = evaluate(db_session, user_id, "UTC")
    assert record_new(db_session, user_id, first) == 1
    stamp = db_session.scalars(select(UserBadge.awarded_at)).one()

    second = evaluate(db_session, user_id, "UTC")
    assert record_new(db_session, user_id, second) == 0
    rows = db_session.scalars(select(UserBadge)).all()
    assert len(rows) == 1
    assert rows[0].awarded_at == stamp


def test_marking_seen_turns_off_the_dot_and_is_safe_to_repeat(db_session):
    user_id = _user(db_session)
    _review(db_session, user_id, datetime.now(tz=UTC))
    record_new(db_session, user_id, evaluate(db_session, user_id, "UTC"))

    assert [s.seen for s in evaluate(db_session, user_id, "UTC") if s.earned] == [False]
    assert mark_seen(db_session, user_id) == 1
    assert mark_seen(db_session, user_id) == 0
    assert [s.seen for s in evaluate(db_session, user_id, "UTC") if s.earned] == [True]


def test_badges_are_read_and_seen_through_the_api(client, db_session):
    """Đường HTTP đầy-đủ: đọc ghi hàng, và `POST .../seen` tắt chấm đỏ.

    `GET` này CÓ ghi — cùng ngoại lệ có chủ ý như `/daily-tasks` — nên bài này
    đọc hai lần và khẳng định `unseen_count` không tự về 0: chỉ lần POST mới
    được tắt nó.
    """
    email = f"badge-api-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "x" * 12})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "x" * 12}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}

    empty = client.get("/api/v1/progression/badges", headers=headers).json()
    assert len(empty["badges"]) == len(DEFAULT_BADGE_RULES)
    assert empty["earned_count"] == 0

    user_id = db_session.scalars(select(User.id).where(User.email == email)).one()
    _review(db_session, user_id, datetime.now(tz=UTC))
    db_session.commit()

    first = client.get("/api/v1/progression/badges", headers=headers).json()
    assert first["earned_count"] == 1
    assert first["unseen_count"] == 1

    again = client.get("/api/v1/progression/badges", headers=headers).json()
    assert again["unseen_count"] == 1, "chỉ POST .../seen mới được tắt chấm đỏ"

    assert client.post("/api/v1/progression/badges/seen", headers=headers).status_code == 204
    after = client.get("/api/v1/progression/badges", headers=headers).json()
    assert after["unseen_count"] == 0
    assert after["earned_count"] == 1


def test_disabling_a_rule_removes_the_badge_without_touching_history(db_session):
    """Tắt một luật là ẩn huy hiệu, không phải xoá lịch sử của ai.

    Hàng `user_badge` ở lại nguyên vẹn, nên bật lại thì `awarded_at` vẫn là lần
    đầu hệ thống nhìn thấy — chứ không phải hôm bật lại. Nếu không giữ được tính
    chất đó thì mỗi lần admin thử tắt-bật là một lần cả hệ thống báo "huy hiệu
    mới" cho những người đã có nó từ lâu.
    """
    user_id = _user(db_session)
    _review(db_session, user_id, datetime.now(tz=UTC))
    record_new(db_session, user_id, evaluate(db_session, user_id, "UTC"))
    stamp = db_session.scalars(select(UserBadge.awarded_at)).one()

    rule = next(r for r in progression_config.badge_rules(db_session) if r.code == "first_steps")
    rule.enabled = False
    db_session.flush()
    assert [s.code for s in evaluate(db_session, user_id, "UTC")].count("first_steps") == 0

    rule.enabled = True
    db_session.flush()
    back = next(s for s in evaluate(db_session, user_id, "UTC") if s.code == "first_steps")
    assert back.earned is True
    assert back.awarded_at == stamp


def test_an_admin_defined_badge_works_like_any_other(db_session):
    """Huy hiệu do admin thêm không phải công dân hạng hai.

    Đây là lý do tồn tại của cả lát cấu hình này: thêm một luật mới chỉ là thêm
    một hàng, miễn là nó đo bằng một số đo đã có.
    """
    from app.models.progression import BadgeRule

    user_id = _user(db_session)
    for _ in range(3):
        _review(db_session, user_id, datetime.now(tz=UTC))
    progression_config.badge_rules(db_session)  # seed bộ mặc định trước
    db_session.add(
        BadgeRule(
            code="reviews_3",
            label="Ba lượt ôn",
            hint="Ôn 3 lượt",
            icon="star",
            metric="reviews",
            target=3,
            position=99,
        )
    )
    db_session.flush()

    fresh = next(s for s in evaluate(db_session, user_id, "UTC") if s.code == "reviews_3")
    assert fresh.earned is True
    assert fresh.label == "Ba lượt ôn"
    assert record_new(db_session, user_id, [fresh]) == 1
