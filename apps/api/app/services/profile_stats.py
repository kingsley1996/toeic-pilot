"""Học viên này đã học được những gì — suy ra, không lưu.

Không có bảng thống kê nào ở đây và không nên có. Lý do đã viết hai lần trong
`ADR-001` và một lần nữa trên `StoryProgress`: một bộ đếm ghi song song với lịch
sử sẽ lệch khỏi lịch sử ngay lần đầu có một hàng bị xoá hoặc chấm lại, và không
có gì phát hiện ra sự bất đồng đó. Đếm lại từ đầu mỗi lần đọc thì chậm hơn nhưng
không bao giờ nói dối.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dictation import DictationAttempt
from app.models.vocabulary import (
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
)
from app.schemas.profile import LearningStats, StudyDay
from app.services.srs import MASTERY_MASTERED, ReviewState, mastery

PUBLISHED = "published"

# Cửa sổ tính chuỗi ngày. Chuỗi dài nhất báo cáo ở đây là chuỗi dài nhất TRONG
# một năm gần đây, không phải mọi thời điểm — giới hạn có chủ ý, vì phương án
# còn lại là kéo toàn bộ lịch sử ôn tập về Python ở mỗi lần mở trang hồ sơ.
STREAK_WINDOW_DAYS = 365

# Lưới hoạt động phủ đúng cửa sổ dùng để tính chuỗi ngày. Hai con số phải bằng
# nhau: lưới hiện một ngày mà phép tính chuỗi không nhìn thấy là lưới nói dối.
CALENDAR_DAYS = STREAK_WINDOW_DAYS


def _as_utc(value: datetime) -> datetime:
    """SQLite trả datetime naive kể cả với `DateTime(timezone=True)`.

    Postgres trả về có tz. Chuyển múi giờ trên một giá trị naive sẽ được Python
    hiểu là giờ địa phương của máy chủ, nên nó chỉ sai khi máy chủ không chạy
    UTC — nghĩa là chạy đúng ở CI rồi sai trên máy lập trình viên.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def compute_streaks(days: set[date], today: date) -> tuple[int, int]:
    """Chuỗi ngày hiện tại và chuỗi dài nhất, từ tập ngày ĐÃ ở múi giờ học viên.

    Hàm thuần, không chạm database — phần khó của tính năng này là số học lịch,
    và nó cần test được mà không dựng bảng nào.

    Chuỗi hiện tại tính cả trường hợp hôm nay chưa học: nếu hôm qua có học thì
    chuỗi vẫn còn nguyên, chỉ đứt khi hết ngày hôm nay mà vẫn chưa học. Cách
    ngược lại — đặt về 0 ngay lúc 00:01 — báo cho học viên rằng họ vừa mất chuỗi
    trong khi họ còn cả ngày để giữ nó.
    """
    if not days:
        return 0, 0

    ordered = sorted(days)

    longest = 1
    run = 1
    for previous, current in zip(ordered, ordered[1:]):
        run = run + 1 if current - previous == timedelta(days=1) else 1
        longest = max(longest, run)

    anchor = today if today in days else today - timedelta(days=1)
    current_streak = 0
    while anchor in days:
        current_streak += 1
        anchor -= timedelta(days=1)

    return current_streak, longest


def _local_days(stamps: list[datetime], zone: ZoneInfo) -> defaultdict[date, int]:
    counted: defaultdict[date, int] = defaultdict(int)
    for stamp in stamps:
        counted[_as_utc(stamp).astimezone(zone).date()] += 1
    return counted


def gather_stats(db: Session, user_id: uuid.UUID, timezone: str) -> LearningStats:
    try:
        zone = ZoneInfo(timezone)
    except Exception:
        # Múi giờ đã được kiểm ở tầng schema trước khi ghi, nên tới đây mà hỏng
        # nghĩa là hàng dữ liệu có từ trước hoặc IANA đã bỏ tên đó. Rơi về UTC
        # cho ra chuỗi ngày hơi lệch; ném 500 thì mất cả trang hồ sơ.
        zone = ZoneInfo("UTC")

    now = datetime.now(UTC)
    since = now - timedelta(days=STREAK_WINDOW_DAYS)
    today = now.astimezone(zone).date()

    # --- từ vựng: cùng mẫu số với `GET /vocabulary-progress`, tức là chỉ những
    # từ đã publish. Đếm cả từ draft sẽ cho ra một tổng mà học viên không bao giờ
    # nhìn thấy trong danh sách.
    published_ids = set(
        db.scalars(select(VocabularyEntry.id).where(VocabularyEntry.status == PUBLISHED)).all()
    )
    states = list(
        db.scalars(
            select(VocabularyReviewState).where(VocabularyReviewState.user_id == user_id)
        ).all()
    )
    mastered = sum(
        1
        for state in states
        if state.entry_id in published_ids
        and mastery(
            ReviewState(
                ease_factor=state.ease_factor,
                interval_days=state.interval_days,
                repetitions=state.repetitions,
                lapses=state.lapses,
            )
        )
        == MASTERY_MASTERED
    )
    # So sánh hạn trong SQL chứ không trong Python, cùng lý do đã ghi ở
    # `vocabulary_progress`: hai bên trả về datetime khác kiểu tz nhau.
    due = len(
        [
            entry_id
            for entry_id in db.scalars(
                select(VocabularyReviewState.entry_id).where(
                    VocabularyReviewState.user_id == user_id,
                    VocabularyReviewState.due_at <= now,
                )
            ).all()
            if entry_id in published_ids
        ]
    )

    reviews_total = (
        db.query(VocabularyReviewLog).filter(VocabularyReviewLog.user_id == user_id).count()
    )
    dictation_attempts = (
        db.query(DictationAttempt).filter(DictationAttempt.user_id == user_id).count()
    )
    # Đếm CÂU đã xong, không đếm lượt nộp: nộp đúng một câu ba lần vẫn là một câu.
    # Cùng định nghĩa với tiến độ bài dictation, nên hai nơi không thể nói khác nhau.
    dictation_completed = len(
        set(
            db.scalars(
                select(DictationAttempt.item_id).where(
                    DictationAttempt.user_id == user_id,
                    DictationAttempt.is_complete.is_(True),
                )
            ).all()
        )
    )

    review_days = _local_days(
        list(
            db.scalars(
                select(VocabularyReviewLog.reviewed_at).where(
                    VocabularyReviewLog.user_id == user_id,
                    VocabularyReviewLog.reviewed_at >= since,
                )
            ).all()
        ),
        zone,
    )
    dictation_days = _local_days(
        list(
            db.scalars(
                select(DictationAttempt.created_at).where(
                    DictationAttempt.user_id == user_id,
                    DictationAttempt.created_at >= since,
                )
            ).all()
        ),
        zone,
    )

    active = set(review_days) | set(dictation_days)
    current_streak, longest_streak = compute_streaks(active, today)

    calendar = [
        StudyDay(
            date=day,
            reviews=review_days.get(day, 0),
            dictation_items=dictation_days.get(day, 0),
        )
        for day in sorted(active)
    ]

    return LearningStats(
        vocabulary_total=len(published_ids),
        vocabulary_mastered=mastered,
        vocabulary_due=due,
        reviews_total=reviews_total,
        dictation_completed=dictation_completed,
        dictation_attempts=dictation_attempts,
        current_streak=current_streak,
        longest_streak=longest_streak,
        active_days=len(active),
        today=today,
        window_days=CALENDAR_DAYS,
        calendar=calendar,
    )
