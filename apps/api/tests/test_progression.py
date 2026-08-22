"""Level, sổ cái XP và trần mỗi ngày.

Ba thứ được kiểm ở đây là ba thứ hỏng im lặng: trao XP hai lần cho một hoạt
động, trần chặn nhầm chính hoạt động thay vì chỉ chặn điểm, và "hôm nay" tính
theo UTC thay vì theo múi giờ người học.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.progression import PROGRESSION_DEFAULTS
from app.models.user import User
from app.services.leveling import curve_thresholds, frame_for_level, level_from_xp
from app.services.progression import (
    award,
    daily_cap,
    local_today,
    task_source_id,
    total_xp,
    xp_awarded_on,
)

# Bảng ngưỡng mặc định, sinh từ đúng bộ tham số mà lần đọc đầu tiên sẽ ghi vào
# `progression_setting`. Dựng ở đây để các bài số học chạy được mà không cần
# database — đường cong vẫn là số học thuần, chỉ có tham số là dữ liệu.
DEFAULT_THRESHOLDS = curve_thresholds(
    coefficient=float(PROGRESSION_DEFAULTS["curve_coefficient"]),  # type: ignore[arg-type]
    exponent=float(PROGRESSION_DEFAULTS["curve_exponent"]),  # type: ignore[arg-type]
    break_at=int(PROGRESSION_DEFAULTS["curve_break"]),  # type: ignore[call-overload]
    linear_step=int(PROGRESSION_DEFAULTS["curve_linear_step"]),  # type: ignore[call-overload]
    max_level=int(PROGRESSION_DEFAULTS["max_level"]),  # type: ignore[call-overload]
)

DEFAULT_FRAME_LEVELS = [(5, "bronze"), (10, "silver"), (20, "gold"), (30, "master")]


def test_level_curve_is_monotonic_and_joins_without_a_step():
    """Ngưỡng phải tăng đều, và chỗ nối hai đoạn không được có bước nhảy.

    Một bậc đột ngột rẻ hơn hoặc đắt hơn hẳn ngay tại điểm gãy đọc ra là lỗi
    tính toán chứ không như một lựa chọn thiết kế.
    """
    thresholds = DEFAULT_THRESHOLDS[1:40]
    assert thresholds == sorted(thresholds)
    assert thresholds[0] == 0

    steps = [b - a for a, b in zip(thresholds, thresholds[1:], strict=False)]
    # Bước ngay trước và ngay sau điểm gãy (level 20) không được lệch quá gấp đôi.
    before, after = steps[17], steps[19]
    assert 0.5 < before / after < 2.0


@pytest.mark.parametrize(
    ("xp", "level"),
    # Ngưỡng lấy từ chính bộ mặc định: 40 XP là level 2, 154 XP là level 5.
    # Đổi đường cong thì bảng này phải đổi theo, và đó là chủ ý — một bài test
    # tự suy ngưỡng từ công thức sẽ xanh với mọi công thức, kể cả công thức sai.
    [(0, 1), (39, 1), (40, 2), (153, 4), (154, 5), (10**9, 99)],
)
def test_level_from_xp(xp, level):
    assert level_from_xp(xp, DEFAULT_THRESHOLDS).level == level


def test_negative_xp_is_clamped_not_raised():
    """Số liệu lạ không được làm hỏng trang hồ sơ."""
    assert level_from_xp(-500, DEFAULT_THRESHOLDS).level == 1


def test_frame_tiers_open_at_the_documented_levels():
    assert frame_for_level(4, DEFAULT_FRAME_LEVELS) is None
    assert frame_for_level(5, DEFAULT_FRAME_LEVELS) == "bronze"
    assert frame_for_level(10, DEFAULT_FRAME_LEVELS) == "silver"
    assert frame_for_level(20, DEFAULT_FRAME_LEVELS) == "gold"
    assert frame_for_level(30, DEFAULT_FRAME_LEVELS) == "master"


def test_today_follows_the_learner_timezone_not_utc():
    """23:00 ở Hà Nội là hôm nay của họ, không phải hôm qua của UTC.

    Cùng bẫy mà `compute_streaks` đã phải xử lý: một ngày kết thúc lúc 17:00 UTC
    ở Hà Nội, nên đếm theo UTC là cắt ngày của mọi người học buổi tối.
    """
    when = datetime(2026, 8, 21, 16, 30, tzinfo=UTC)  # 23:30 giờ Việt Nam
    assert local_today(when, "Asia/Ho_Chi_Minh").isoformat() == "2026-08-21"
    assert local_today(when, "UTC").isoformat() == "2026-08-21"

    later = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)  # 01:00 ngày 22 giờ Việt Nam
    assert local_today(later, "Asia/Ho_Chi_Minh").isoformat() == "2026-08-22"
    assert local_today(later, "UTC").isoformat() == "2026-08-21"


def test_unknown_timezone_falls_back_instead_of_raising():
    assert local_today(datetime(2026, 8, 21, 12, tzinfo=UTC), "Mars/Olympus").isoformat()


def test_task_source_id_is_deterministic_and_scoped():
    """uuid tất định là thứ làm ràng buộc chống trùng có hiệu lực với daily task.

    Postgres coi mọi NULL là khác nhau, nên `source_id` để trống thì hai lần trao
    cho cùng một task sẽ lọt cả hai.
    """
    user = uuid.uuid4()
    day = datetime(2026, 8, 21, tzinfo=UTC).date()
    assert task_source_id(user, day, "review") == task_source_id(user, day, "review")
    assert task_source_id(user, day, "review") != task_source_id(user, day, "dictation")
    assert task_source_id(user, day, "review") != task_source_id(uuid.uuid4(), day, "review")


def _user(db_session) -> uuid.UUID:
    user = User(
        email=f"xp-{uuid.uuid4().hex[:8]}@example.com", hashed_password=get_password_hash("x" * 12)
    )
    db_session.add(user)
    db_session.flush()
    return user.id


def test_award_is_idempotent_for_one_activity(db_session):
    """Cùng một hoạt động trao hai lần chỉ sinh MỘT hàng.

    Không có phép kiểm này, một lần bấm đúp là XP nhân đôi — và vì sổ cái bất
    biến, không có cách sửa nào ngoài xoá hàng, tức phá đúng thứ làm nó đáng tin.
    """
    user_id = _user(db_session)
    source = uuid.uuid4()
    first = award(
        db_session,
        user_id=user_id,
        source_type="vocabulary_review",
        source_id=source,
        amount=2,
        timezone="UTC",
    )
    second = award(
        db_session,
        user_id=user_id,
        source_type="vocabulary_review",
        source_id=source,
        amount=2,
        timezone="UTC",
    )
    assert first == 2
    assert second == 0
    assert total_xp(db_session, user_id) == 2


def test_cap_trims_the_last_award_instead_of_dropping_it(db_session):
    """Chạm trần thì cắt phần vượt, không bỏ cả lần trao.

    Trao 3 trong 5 điểm còn lại đúng hơn trao 0: người dùng thấy thanh nhích
    chậm dần rồi dừng, chứ không thấy nó đứng khựng giữa chừng.
    """
    user_id = _user(db_session)
    day = datetime.now(tz=UTC).date()
    cap = daily_cap(db_session)
    for _ in range(cap // 30):
        award(
            db_session,
            user_id=user_id,
            source_type="attempt_submit",
            source_id=uuid.uuid4(),
            amount=30,
            timezone="UTC",
        )
    assert xp_awarded_on(db_session, user_id, day) == cap

    over = award(
        db_session,
        user_id=user_id,
        source_type="vocabulary_review",
        source_id=uuid.uuid4(),
        amount=2,
        timezone="UTC",
    )
    assert over == 0
    assert xp_awarded_on(db_session, user_id, day) == cap


# --- daily task -------------------------------------------------------------


def test_daily_task_target_does_not_move_as_you_work(db_session):
    """Mục tiêu là số CỐ ĐỊNH đã kẹp, không phải tình trạng hiện thời.

    Đây là cái bẫy chính của tính năng này. Nếu mục tiêu là "ôn hết số từ đến
    hạn" thì nó GIẢM khi bạn ôn, thanh tiến độ chạy tới rồi lùi, và với một số
    lịch SM-2 thì việc không bao giờ đóng được — hỏng mà không có gì báo.
    """
    from app.models.vocabulary import VocabularyEntry, VocabularyReviewLog
    from app.services.daily_tasks import KIND_REVIEW, tasks_for

    user_id = _user(db_session)
    for i in range(30):
        db_session.add(
            VocabularyEntry(
                headword=f"w{i}",
                part_of_speech="noun",
                meaning_en="x",
                meaning_vi="x",
                status="published",
            )
        )
    db_session.flush()

    _, before = tasks_for(db_session, user_id, "UTC")
    target_before = next(t for t in before if t.kind == KIND_REVIEW).target

    entry = db_session.scalars(select(VocabularyEntry).limit(1)).first()
    assert entry is not None
    db_session.add(
        VocabularyReviewLog(
            user_id=user_id, entry_id=entry.id, grade=4, interval_days=1, ease_factor=Decimal("2.5")
        )
    )
    db_session.flush()

    _, after = tasks_for(db_session, user_id, "UTC")
    slot = next(t for t in after if t.kind == KIND_REVIEW)
    assert slot.target == target_before, "mục tiêu không được đổi khi người học làm việc"
    assert slot.progress == 1, "tiến độ phải tăng"


def test_daily_task_reward_is_granted_once(db_session):
    """Đọc lại `/daily-tasks` không trao XP lần thứ hai.

    Lần đọc này CÓ ghi, nên tính tất định của `source_id` là thứ duy nhất đứng
    giữa một lần dựng lại của React và việc nhân đôi phần thưởng.
    """
    from app.services.daily_tasks import DailyTask, grant_rewards

    user_id = _user(db_session)
    day = datetime.now(tz=UTC).date()
    done = [
        DailyTask(
            slot_id=uuid.uuid4(),
            kind="vocabulary_review",
            label="Ôn từ vựng",
            target=10,
            progress=10,
            done=True,
            xp=10,
        )
    ]

    assert grant_rewards(db_session, user_id, "UTC", day, done) == 10
    assert grant_rewards(db_session, user_id, "UTC", day, done) == 0
    assert total_xp(db_session, user_id) == 10


def test_unfinished_task_earns_nothing(db_session):
    from app.services.daily_tasks import DailyTask, grant_rewards

    user_id = _user(db_session)
    day = datetime.now(tz=UTC).date()
    partial = [
        DailyTask(
            slot_id=uuid.uuid4(),
            kind="vocabulary_review",
            label="Ôn từ vựng",
            target=10,
            progress=9,
            done=False,
            xp=10,
        )
    ]
    assert grant_rewards(db_session, user_id, "UTC", day, partial) == 0
    assert total_xp(db_session, user_id) == 0
