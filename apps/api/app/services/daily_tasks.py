"""Ba việc hôm nay — suy ra từ hoạt động, không có bảng nào.

Mục tiêu của tính năng này là *mở lên là biết làm gì*. Nên nó luôn đúng ba dòng,
luôn cùng thứ tự, mỗi ngày. Không có menu, không có lựa chọn, không có việc nào
xuất hiện rồi biến mất tuỳ tình trạng.

**Mục tiêu là một số CỐ ĐỊNH được kẹp bởi tình trạng, không phải chính tình
trạng.** Đây là chỗ dễ làm sai nhất và nó hỏng theo kiểu không ai báo: đặt mục
tiêu là "ôn hết số từ đến hạn" thì số đến hạn GIẢM DẦN khi bạn ôn, nên thanh
tiến độ chạy tới rồi lùi lại, và với một số lịch SM-2 thì việc không bao giờ
đóng được. Con số động ở đây là **cái kẹp**, không phải cái đích.

Tiến độ đếm hoạt động TRONG NGÀY, nên nó chỉ tăng.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dictation import DictationAttempt
from app.models.grammar import GrammarLesson, GrammarLessonCompletion, GrammarTopic
from app.models.practice import Attempt, AttemptItem
from app.models.vocabulary import (
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
)
from app.services import progression, progression_config

# Ba loại việc mà hệ thống biết ĐO. Đây là tập đóng và nó khác hẳn với danh sách
# khe: khe là dữ liệu (admin thêm, sửa, tắt), còn loại việc là code — thêm một
# loại nghĩa là viết thêm một phép đếm ở dưới.
KIND_REVIEW = "vocabulary_review"
KIND_DICTATION = "dictation_complete"
KIND_TEST = "attempt_answer"
KIND_GRAMMAR = "grammar_lesson_complete"


@dataclass(frozen=True)
class DailyTask:
    """Một khe đã đo xong cho hôm nay.

    `slot_id` là uuid của HÀNG cấu hình, không phải một mã chuỗi. Nó đi vào
    `xp_event.source_id`, nên đổi nhãn hay đổi mục tiêu của một khe không biến
    ngày đã thưởng thành ngày chưa thưởng.
    """

    slot_id: uuid.UUID
    kind: str
    label: str
    target: int
    progress: int
    done: bool
    xp: int


def day_bounds(day: date, timezone: str) -> tuple[datetime, datetime]:
    """Nửa khoảng [đầu ngày, đầu ngày kế) theo múi giờ người học, quy về UTC.

    So sánh trong SQL phải là hai mốc UTC chứ không phải một phép quy đổi múi giờ
    trên từng hàng: quy đổi trong `WHERE` bỏ qua chỉ mục, và tệ hơn, nó là một
    định nghĩa "ngày" thứ hai cạnh định nghĩa mà `compute_streaks` dùng.
    """
    try:
        zone = ZoneInfo(timezone)
    except Exception:
        zone = ZoneInfo("UTC")
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    return start_local.astimezone(UTC), (start_local + timedelta(days=1)).astimezone(UTC)


def _reviews_today(db: Session, user_id: uuid.UUID, lo: datetime, hi: datetime) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(VocabularyReviewLog)
            .where(
                VocabularyReviewLog.user_id == user_id,
                VocabularyReviewLog.reviewed_at >= lo,
                VocabularyReviewLog.reviewed_at < hi,
            )
        )
        or 0
    )


def _reviewable(db: Session, user_id: uuid.UUID, now: datetime, target: int) -> int:
    """Số từ có thể ôn ngay bây giờ — dùng làm CÁI KẸP, không phải mục tiêu.

    Đếm cả từ đã đến hạn lẫn từ chưa từng gặp: một học viên mới không có gì "đến
    hạn" nhưng vẫn có hàng trăm từ để học, và một mục tiêu bằng 0 ở ngày đầu tiên
    là cách chắc chắn nhất để họ không quay lại.
    """
    due = int(
        db.scalar(
            select(func.count())
            .select_from(VocabularyReviewState)
            .where(VocabularyReviewState.user_id == user_id, VocabularyReviewState.due_at <= now)
        )
        or 0
    )
    if due >= target:
        return due

    # Chưa đủ từ đến hạn thì bù bằng từ chưa gặp. Chỉ cần biết "còn gì để học
    # không", nên đếm tới đúng mục tiêu rồi thôi — đếm toàn bộ kho từ ở mỗi lần
    # mở dashboard là một phép đếm bảng lớn cho một con số sẽ bị kẹp ngay sau đó.
    seen = select(VocabularyReviewState.entry_id).where(VocabularyReviewState.user_id == user_id)
    unseen = int(
        db.scalar(
            select(func.count()).select_from(
                select(VocabularyEntry.id)
                .where(VocabularyEntry.status == "published", VocabularyEntry.id.notin_(seen))
                .limit(target)
                .subquery()
            )
        )
        or 0
    )
    return due + unseen


def _dictation_today(db: Session, user_id: uuid.UUID, lo: datetime, hi: datetime) -> int:
    """Số CÂU riêng biệt hoàn thành hôm nay.

    `DISTINCT item_id` chứ không đếm lượt: gõ lại một câu đã đúng thì không phải
    một câu mới, và đếm lượt biến việc này thành "bấm ba lần" thay vì "làm ba câu".
    """
    return int(
        db.scalar(
            select(func.count(func.distinct(DictationAttempt.item_id))).where(
                DictationAttempt.user_id == user_id,
                DictationAttempt.is_complete.is_(True),
                DictationAttempt.created_at >= lo,
                DictationAttempt.created_at < hi,
            )
        )
        or 0
    )


def _answers_today(db: Session, user_id: uuid.UUID, lo: datetime, hi: datetime) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AttemptItem)
            .join(Attempt, Attempt.id == AttemptItem.attempt_id)
            .where(
                Attempt.user_id == user_id,
                AttemptItem.answered_at.is_not(None),
                AttemptItem.answered_at >= lo,
                AttemptItem.answered_at < hi,
            )
        )
        or 0
    )


def _grammar_today(db: Session, user_id: uuid.UUID, lo: datetime, hi: datetime) -> int:
    """Số bài ngữ pháp BẤM HOÀN THÀNH hôm nay.

    Đếm hàng completion chứ không đếm câu làm được: việc là "học ba BÀI", và phần
    lớn giáo trình là lý thuyết không có câu hỏi nào — đo theo attempt thì người
    học hết phần lý thuyết mà thanh tiến độ không nhích. Chỉ hàng ĐANG hiệu lực
    và chỉ ngày `created_at` của nó: gỡ dấu thì thanh lùi (tự tay họ), còn bấm
    lại một bài cũ không biến thành "bài của hôm nay" lần thứ hai.
    """
    return int(
        db.scalar(
            select(func.count())
            .select_from(GrammarLessonCompletion)
            .where(
                GrammarLessonCompletion.user_id == user_id,
                GrammarLessonCompletion.revoked_at.is_(None),
                GrammarLessonCompletion.created_at >= lo,
                GrammarLessonCompletion.created_at < hi,
            )
        )
        or 0
    )


def _grammar_available(db: Session, user_id: uuid.UUID, target: int) -> int:
    """Số bài còn chưa học — CÁI KẸP, cùng lập luận với `_reviewable`.

    Kho bài là hữu hạn (khác kho câu hỏi thi, vốn chỉ lớn dần): mục tiêu 3 bài
    khi cả giáo trình còn 2 bài chưa học là một việc không bao giờ xong. Hết
    sạch thì kẹp trả về 0 và `tasks_for` giữ nguyên mục tiêu — thà một việc đóng
    vĩnh viễn còn hơn một phần thưởng ăn sẵn mỗi ngày.
    """
    completed = select(GrammarLessonCompletion.lesson_id).where(
        GrammarLessonCompletion.user_id == user_id,
        GrammarLessonCompletion.revoked_at.is_(None),
    )
    available = (
        select(GrammarLesson.id)
        .join(GrammarTopic, GrammarTopic.id == GrammarLesson.topic_id)
        .where(
            GrammarLesson.status == "published",
            GrammarTopic.status == "published",
            GrammarLesson.id.notin_(completed),
        )
        .limit(target)
        .subquery()
    )
    return int(db.scalar(select(func.count()).select_from(available)) or 0)


def tasks_for(
    db: Session, user_id: uuid.UUID, timezone: str, now: datetime | None = None
) -> tuple[date, list[DailyTask]]:
    """Các khe đang bật, đã đo cho hôm nay.

    Số khe do cấu hình quyết định chứ không còn cố định là ba. Bộ mặc định vẫn là
    ba, và đó vẫn là lựa chọn sản phẩm đúng — "mở lên là biết làm gì" hỏng dần
    khi danh sách dài ra. Nhưng nó là một mặc định, không phải một giới hạn của
    code.

    **Đổi cấu hình có hiệu lực NGAY, kể cả giữa ngày.** Hệ quả đã biết và được
    chấp nhận: nâng mục tiêu lúc 2 giờ chiều làm một việc đã xong mở lại
    (10/10 thành 10/15). XP đã trao thì không mất — `uq_xp_event_source` lo phần
    đó — nhưng thanh tiến độ lùi, đúng thứ §6.2 cảnh báo. Giao diện quản trị nói
    thẳng điều này ngay cạnh ô nhập.
    """
    when = now or datetime.now(tz=UTC)
    day = progression.local_today(when, timezone)
    lo, hi = day_bounds(day, timezone)

    # Đo MỘT LẦN cho mỗi loại, dù có bao nhiêu khe cùng loại: hai khe "ôn từ" với
    # hai mục tiêu khác nhau là chuyện hợp lệ, và đếm lại cho từng khe là chạy
    # cùng một truy vấn hai lần cho cùng một con số.
    measured: dict[str, int] = {}
    tasks: list[DailyTask] = []
    for slot in progression_config.slots(db):
        if slot.kind not in measured:
            measured[slot.kind] = _measure(db, user_id, slot.kind, lo, hi, when)
        progress = measured[slot.kind]

        target = slot.target
        if slot.kind == KIND_REVIEW:
            # Kẹp xuống theo số từ thật sự có, không bao giờ kẹp lên. Con số động
            # ở đây là CÁI KẸP, không phải cái đích — xem chú thích đầu tệp.
            target = min(slot.target, _reviewable(db, user_id, when, slot.target)) or slot.target
        elif slot.kind == KIND_GRAMMAR:
            # Cùng cái kẹp, cộng `progress`: mục tiêu là "học hết phần còn lại,
            # tối đa 3". Không cộng thì học xong bài CUỐI cùng lúc kẹp còn 2 sẽ
            # làm target nhảy về 3 đúng khoảnh khắc việc đáng ra xong — và việc
            # đóng vĩnh viễn ngay khi người ta vừa hoàn thành giáo trình.
            available = _grammar_available(db, user_id, slot.target)
            target = min(slot.target, available + progress) or slot.target

        tasks.append(
            DailyTask(
                slot_id=slot.id,
                kind=slot.kind,
                label=slot.label,
                target=target,
                progress=progress,
                done=progress >= target,
                xp=slot.xp,
            )
        )
    return day, tasks


def _measure(
    db: Session, user_id: uuid.UUID, kind: str, lo: datetime, hi: datetime, when: datetime
) -> int:
    if kind == KIND_REVIEW:
        return _reviews_today(db, user_id, lo, hi)
    if kind == KIND_DICTATION:
        return _dictation_today(db, user_id, lo, hi)
    if kind == KIND_TEST:
        return _answers_today(db, user_id, lo, hi)
    if kind == KIND_GRAMMAR:
        return _grammar_today(db, user_id, lo, hi)
    # Một khe mang loại việc mà code không biết đo. Không thể xảy ra qua giao diện
    # quản trị (danh sách đóng, kiểm ở tầng schema), nhưng nếu có thì nó phải là
    # một việc KHÔNG BAO GIỜ xong chứ không phải một việc xong sẵn: trao XP cho
    # thứ không đo được là tệ hơn hẳn so với hiển thị 0.
    return 0


def grant_rewards(
    db: Session, user_id: uuid.UUID, timezone: str, day: date, tasks: list[DailyTask]
) -> int:
    """Trao XP cho những việc đã xong mà chưa trao. Trả về tổng vừa trao.

    Ghi trong một lần ĐỌC, và đó là một ngoại lệ có chủ ý đối với "GET không đổi
    trạng thái". Hai phương án còn lại đều tệ hơn: đặt logic daily task vào cả ba
    đường ghi nóng (mỗi lượt ôn phải đếm lại tiến độ ba khe), hoặc bắt người dùng
    bấm một nút "nhận thưởng" — thêm đúng một bước rối vào tính năng tồn tại để
    bớt rối.

    An toàn vì **tất định và bất biến**: `source_id` sinh từ (người, ngày, khe),
    nên `uq_xp_event_source` chặn lần trao thứ hai. Gọi lại bao nhiêu lần cũng
    ra cùng một kết quả — kể cả khi React gọi hai lần lúc dựng.
    """
    granted = 0
    for task in tasks:
        if not task.done:
            continue
        granted += progression.award(
            db,
            user_id=user_id,
            source_type="daily_task",
            source_id=progression.task_source_id(user_id, day, str(task.slot_id)),
            amount=task.xp,
            timezone=timezone,
        )
    return granted
