"""Ba nguồn ruby lặp theo NGÀY (ADR-011 lát 3).

Tách khỏi `ruby.py` vì kia là sổ cái — kiếm, tiêu, số dư — còn đây là chính sách:
hôm nay đã học gì chưa, ba việc đã xong cả chưa, chuỗi ngày vừa chạm mốc nào.
Chính sách sẽ đổi nhiều lần; sổ cái thì không được đổi.

Cả ba đều dùng `source_id` TẤT ĐỊNH, nên gọi lại bao nhiêu lần cũng chỉ trao một
lần — Postgres coi mọi NULL là khác nhau, nên `uq_ruby_event_source` không tự
chặn được nếu để trống.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dictation import DictationAttempt
from app.models.ruby import RubyEvent
from app.models.vocabulary import VocabularyReviewLog
from app.services import ruby
from app.services.daily_tasks import DailyTask, day_bounds

# Mốc chuỗi ngày trả thưởng. Bảy vì một tuần là đơn vị người ta tự đếm.
STREAK_STEP = 7


def studied_today(db: Session, user_id: uuid.UUID, timezone: str, day: date) -> bool:
    """Hôm nay đã có một hoạt động HỌC thật chưa.

    Cùng định nghĩa "có học" mà `compute_streaks` dùng — một lượt ôn từ hoặc một
    lượt gõ dictation — chứ không phải "đã mở app". Hai định nghĩa sẽ lệch nhau,
    và cái lệch sẽ là một nút quà sáng lên vào ngày người ta chưa học gì.

    `EXISTS` chứ không `COUNT`: câu hỏi là có hay không, và ngày nào có thì hàng
    đầu tiên đã trả lời xong.
    """
    lo, hi = day_bounds(day, timezone)
    reviewed = db.scalar(
        select(
            select(VocabularyReviewLog.id)
            .where(
                VocabularyReviewLog.user_id == user_id,
                VocabularyReviewLog.reviewed_at >= lo,
                VocabularyReviewLog.reviewed_at < hi,
            )
            .exists()
        )
    )
    if reviewed:
        return True
    return bool(
        db.scalar(
            select(
                select(DictationAttempt.id)
                .where(
                    DictationAttempt.user_id == user_id,
                    DictationAttempt.created_at >= lo,
                    DictationAttempt.created_at < hi,
                )
                .exists()
            )
        )
    )


@dataclass(frozen=True)
class GiftState:
    """Quà hôm nay: mở được chưa, đã nhận chưa, và bao nhiêu."""

    amount: int
    unlocked: bool
    claimed: bool

    @property
    def available(self) -> bool:
        return self.unlocked and not self.claimed


def gift_state(
    db: Session, user_id: uuid.UUID, timezone: str, now: datetime | None = None
) -> tuple[date, GiftState]:
    """Trạng thái quà hôm nay. Chỉ ĐỌC — nhận quà là một `POST`.

    Quà mở sau khi ngày hôm nay đã tính vào chuỗi ngày, không mở sẵn lúc vào app
    (ADR-011 §2). Nhìn từ phía người dùng nó vẫn là "vào nhận quà mỗi ngày", chỉ
    khác ở chỗ nút sáng lên sau bài đầu tiên — và nó cho cái nút một câu để nói:
    *học xong một chút là mở được quà*. Thưởng cho việc mở app mà không học là
    dạy đúng cái hành vi không muốn.
    """
    when = now or datetime.now(UTC)
    day = ruby.local_today(when, timezone)
    source_id = ruby.daily_source_id(user_id, day, "daily_gift")
    claimed = bool(
        db.scalar(
            select(
                select(RubyEvent.id)
                .where(RubyEvent.user_id == user_id, RubyEvent.source_id == source_id)
                .exists()
            )
        )
    )
    return day, GiftState(
        amount=ruby.amount_for(db, "daily_gift"),
        unlocked=studied_today(db, user_id, timezone, day),
        claimed=claimed,
    )


def claim_gift(db: Session, user_id: uuid.UUID, timezone: str, now: datetime | None = None) -> int:
    """Nhận quà hôm nay. Trả về số ruby vừa nhận, 0 nếu chưa mở được hoặc đã nhận.

    Không ném lỗi khi bấm hai lần: `source_id` tất định nên lần thứ hai bị khoá
    duy nhất từ chối, và một cú bấm đúp không phải là một sự cố người dùng cần
    đọc thông báo.
    """
    day, state = gift_state(db, user_id, timezone, now)
    if not state.unlocked:
        return 0
    return ruby.earn(
        db,
        user_id=user_id,
        source_type="daily_gift",
        source_id=ruby.daily_source_id(user_id, day, "daily_gift"),
    )


def grant_all_tasks_done(db: Session, user_id: uuid.UUID, day: date, tasks: list[DailyTask]) -> int:
    """Ruby cho việc xong CẢ BA việc, không cho từng việc (ADR-011 §2).

    XP đã trả cho từng khe rồi. Hai phần thưởng cùng hình dạng trên cùng một hành
    động là chỗ người dùng thôi phân biệt được hai đơn vị — nên ruby chỉ trả cho
    việc đóng trọn một ngày.

    Danh sách rỗng không phải là "xong hết": `all([])` là `True`, và một tài
    khoản không có khe nào bật sẽ được trả mỗi ngày mà chẳng làm gì.
    """
    if not tasks or not all(task.done for task in tasks):
        return 0
    return ruby.earn(
        db,
        user_id=user_id,
        source_type="daily_all",
        source_id=ruby.daily_source_id(user_id, day, "daily_all"),
    )


def grant_streak_milestone(db: Session, user_id: uuid.UUID, current_streak: int) -> int:
    """Ruby khi chuỗi ngày chạm bội số của bảy. Mỗi MỐC một lần, vĩnh viễn.

    `source_id` sinh từ số mốc chứ không từ ngày: mốc 7 trả đúng một lần trong
    đời tài khoản, mốc 14 trả tiếp. Đứt chuỗi rồi gây lại tới 7 thì không được
    trả lần nữa — cố ý, vì phần thưởng đánh dấu việc đi XA hơn, và trả lại theo
    ngày sẽ biến nó thành một nguồn thu đều đặn cho người cứ bảy ngày nghỉ một
    lần.

    Đọc `current_streak` chứ không `longest_streak`: đây là phần thưởng cho việc
    ĐANG giữ chuỗi. Huy hiệu chuỗi ngày mới là thứ phải đọc `longest_streak`, vì
    một huy hiệu biến mất khi nghỉ một hôm là phạt người ta vì đã nghỉ.
    """
    if current_streak < STREAK_STEP:
        return 0
    milestone = current_streak // STREAK_STEP
    return ruby.earn(
        db,
        user_id=user_id,
        source_type="streak_week",
        source_id=uuid.uuid5(uuid.NAMESPACE_URL, f"ruby-streak:{user_id}:{milestone}"),
    )


def total_earned(db: Session, user_id: uuid.UUID) -> int:
    """Tổng ruby đã KIẾM, không trừ phần đã tiêu. Dùng cho thống kê, không cho ví."""
    total = db.scalar(
        select(func.coalesce(func.sum(RubyEvent.amount), 0)).where(
            RubyEvent.user_id == user_id, RubyEvent.amount > 0
        )
    )
    return int(total or 0)
