"""Badge — suy ra từ lịch sử học, không phải từ sổ cái XP.

Đây là chỗ quyết định một người có badge hay không. `user_badge` KHÔNG quyết
định điều đó; nó chỉ nhớ lần đầu hệ thống nhìn thấy và người dùng đã xem chưa.

Hệ quả là **tài khoản cũ không cần backfill**: điều kiện đọc thẳng lịch sử ôn
tập, dictation và làm đề, nên chúng đúng ngay lần đọc đầu tiên. Đây cũng là chỗ
sinh ra bất đối xứng đã ghi ở USER-ROAD §0 và giao diện phải nói ra: một người
đã học 300 từ thấy badge "300 từ" ngay lập tức **nhưng vẫn ở level 1**, vì XP đo
hoạt động KỂ TỪ KHI RA MẮT còn badge ghi nhận thành tựu TRỌN ĐỜI.

Ba badge `level_*` là ngoại lệ có chủ ý: chúng đọc XP, nên với tài khoản cũ
chúng mở muộn hơn phần còn lại. Đó chính là bất đối xứng trên, hiện ra ở chỗ dễ
thấy nhất — cố tình, chứ không phải quên.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.storage import get_driver
from app.models.practice import Attempt
from app.models.profile import UserProfile
from app.models.progression import UserBadge
from app.services import progression, progression_config
from app.services.profile_stats import gather_stats

# Số đo mà một luật badge có thể so ngưỡng. Tập ĐÓNG, và đó là ranh giới giữa
# phần dữ liệu và phần code của tính năng này: admin thêm huy hiệu mới, đặt nhãn,
# đổi ngưỡng — nhưng chỉ đo được bằng những thứ ở đây, vì mỗi số đo là một phép
# đếm có thật ở dưới. Một luật trỏ tới số đo lạ sẽ đọc ra 0 và không bao giờ mở,
# chứ không mở sẵn: trao nhầm tệ hơn không trao.
METRIC_REVIEWS = "reviews"
METRIC_WORDS = "words_mastered"
METRIC_DICTATION = "dictation_items"
METRIC_TESTS = "tests_submitted"
METRIC_SCORE = "best_score"
METRIC_STREAK = "longest_streak"
METRIC_LEVEL = "level"


@dataclass
class BadgeStatus:
    code: str
    label: str
    hint: str
    icon: str
    image_url: str | None
    target: int
    progress: int
    earned: bool
    awarded_at: datetime | None
    seen: bool


def measure(db: Session, user_id: uuid.UUID, timezone: str) -> dict[str, int]:
    """Bảy số đo, mỗi số một lần đọc.

    Bốn số đầu lấy từ `gather_stats` chứ không đếm lại: đó là định nghĩa đang
    được trang hồ sơ in ra, và một định nghĩa thứ hai ở đây là chỗ badge "300 từ"
    mở ra trong khi trang hồ sơ vẫn ghi 299 — không ai gọi đó là lỗi, họ chỉ
    thấy hệ thống nói hai điều khác nhau.
    """
    stats = gather_stats(db, user_id, timezone)

    # Đếm lượt làm đề ĐÃ KẾT THÚC, kể cả lượt hết giờ: `submitted_at` NOT NULL
    # đúng cho cả `submitted` lẫn `expired` (CHECK trên `attempt` buộc như thế).
    # Một bài bị hết giờ vẫn là một bài đã làm xong; XP thì chỉ trao khi bấm nộp,
    # còn badge ghi nhận việc đã ngồi hết một lượt.
    tests = int(
        db.scalar(
            select(func.count())
            .select_from(Attempt)
            .where(Attempt.user_id == user_id, Attempt.submitted_at.is_not(None))
        )
        or 0
    )
    # `total_scaled` chỉ có ở lượt làm TRỌN đề có bảng quy đổi, nên không cần lọc
    # `scope` — nơi khác đã bảo đảm điều đó và lọc lại ở đây là dựng một luật thứ
    # hai phải giữ đồng bộ.
    best = int(
        db.scalar(
            select(func.coalesce(func.max(Attempt.total_scaled), 0)).where(
                Attempt.user_id == user_id
            )
        )
        or 0
    )
    # Level HIỂN THỊ, tức đã áp mốc nước cao: một huy hiệu "đạt level 10" không
    # được biến mất chỉ vì admin vừa nâng chuẩn sau khi người ta đã lên tới đó.
    profile = db.get(UserProfile, user_id)
    level = max(progression.level_of(db, user_id).level, profile.level_reached if profile else 1)

    return {
        METRIC_REVIEWS: stats.reviews_total,
        METRIC_WORDS: stats.vocabulary_mastered,
        METRIC_DICTATION: stats.dictation_completed,
        METRIC_TESTS: tests,
        METRIC_SCORE: best,
        # CHUỖI DÀI NHẤT, không phải chuỗi hiện tại. Một badge đã đạt rồi biến
        # mất vì hôm nay nghỉ là hình phạt cho việc nghỉ một ngày, và nó dạy
        # người dùng rằng hệ thống lấy lại thứ đã cho.
        METRIC_STREAK: stats.longest_streak,
        METRIC_LEVEL: level,
    }


def evaluate(db: Session, user_id: uuid.UUID, timezone: str) -> list[BadgeStatus]:
    """Trạng thái của mọi luật badge đang bật, kèm tiến độ tới ngưỡng.

    Trả về cả badge chưa mở: một trang chỉ hiện thứ đã đạt thì không nói được còn
    gì phía trước, mà đó mới là thứ khiến người ta quay lại.

    Luật đọc từ `badge_rule` chứ không từ một hằng số: nhãn, gợi ý, biểu tượng,
    ngưỡng và cả việc có huy hiệu đó hay không đều là cấu hình. Cái KHÔNG mở là
    `metric` — xem đầu tệp.
    """
    values = measure(db, user_id, timezone)
    rows = {
        row.code: row
        for row in db.scalars(select(UserBadge).where(UserBadge.user_id == user_id)).all()
    }

    statuses = []
    for rule in progression_config.badge_rules(db):
        progress = values.get(rule.metric, 0)
        row = rows.get(rule.code)
        statuses.append(
            BadgeStatus(
                code=rule.code,
                label=rule.label,
                hint=rule.hint,
                icon=rule.icon,
                # URL dựng ở đây chứ không ở tầng route: cùng một phép nối chuỗi
                # đó cần cho cả đường học lẫn đường quản trị, và hai bản sao của
                # nó sẽ lệch nhau đúng vào ngày đổi nhà cung cấp.
                image_url=(
                    get_driver("image").public_url(rule.image_storage_key)
                    if rule.image_storage_key
                    else None
                ),
                target=rule.target,
                # Kẹp lại để giao diện in "300/300" chứ không "412/300": con số
                # đáng nói ở đây là ngưỡng, không phải tổng tài sản.
                progress=min(progress, rule.target),
                earned=progress >= rule.target,
                awarded_at=row.awarded_at if row else None,
                seen=row.seen_at is not None if row else False,
            )
        )
    return statuses


def record_new(db: Session, user_id: uuid.UUID, statuses: list[BadgeStatus]) -> int:
    """Ghi hàng cho badge vừa đủ điều kiện mà chưa có. Trả về số hàng vừa ghi.

    Ghi trong một lần ĐỌC, cùng ngoại lệ có chủ ý như `daily_tasks.grant_rewards`
    và an toàn vì cùng một lý do: khoá chính `(user_id, code)` khiến lần ghi thứ
    hai không thể xảy ra, nên gọi lại bao nhiêu lần cũng ra một kết quả.

    SAVEPOINT chứ không `ON CONFLICT`: `ON CONFLICT` không chạy trên SQLite, mà
    bộ test mặc định là SQLite.
    """
    written = 0
    for status in statuses:
        if not status.earned or status.awarded_at is not None:
            continue
        try:
            with db.begin_nested():
                row = UserBadge(user_id=user_id, code=status.code, awarded_at=datetime.now(tz=UTC))
                db.add(row)
            status.awarded_at = row.awarded_at
            written += 1
        except IntegrityError:
            # Hai request song song cùng thấy badge mới — chuyện bình thường, và
            # không được biến thành lỗi trên một đường chỉ để đọc.
            continue
    return written


def mark_seen(db: Session, user_id: uuid.UUID) -> int:
    """Tắt chấm đỏ. Trả về số badge vừa đánh dấu.

    Đánh dấu MỌI badge chưa xem chứ không nhận danh sách mã: nút này bấm từ trang
    badge, nơi tất cả đang hiển thị cùng lúc, nên "đã xem" đúng nghĩa đen. Nhận
    danh sách mã sẽ mời phía gọi gửi thiếu, và một badge sót lại vĩnh viễn giữ
    chấm đỏ trên một trang không còn gì mới.
    """
    rows = list(
        db.scalars(
            select(UserBadge).where(UserBadge.user_id == user_id, UserBadge.seen_at.is_(None))
        ).all()
    )
    now = datetime.now(tz=UTC)
    for row in rows:
        row.seen_at = now
    # `flush` tường minh vì các session của dự án chạy `autoflush=False`
    # (`app/core/database.py`). Không có nó, một lần đọc tiếp theo TRONG CÙNG
    # giao dịch vẫn thấy `seen_at IS NULL` và đánh dấu lại lần nữa — hàng vẫn
    # đúng sau khi commit, nên lỗi này chỉ lộ ra ở chỗ đếm.
    db.flush()
    return len(rows)
