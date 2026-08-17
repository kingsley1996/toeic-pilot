"""SM-2 spaced repetition.

Pure arithmetic, no database: the caller reads the current state, calls `review`,
and writes the result. That split is what makes the algorithm testable without a
session and re-runnable over historical logs when the parameters change.

Grades follow the four-button convention rather than SM-2's original 0-5 scale.
The original distinguishes three flavours of "forgot" that no learner can report
reliably, so 0/1/2 collapse to one button; the surviving values keep their
original arithmetic meaning. Grade 6 ("thành thạo") is a deliberate extension: it
is the one place where the learner asserts "I own this word", and the engine
honours that by jumping the interval straight to the mastered threshold — the
same state SM-2 would reach only after weeks of passing reviews.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

GRADE_FORGOT = 0
GRADE_HARD = 3
GRADE_GOOD = 4
GRADE_EASY = 5
# "Thành thạo": học viên khẳng định đã thuộc. Không phải một mức chất lượng của
# SM-2 gốc — là quyết định chủ động đưa thẻ thẳng lên mốc MASTERED.
GRADE_MASTERED = 6

GRADES = (GRADE_FORGOT, GRADE_HARD, GRADE_GOOD, GRADE_EASY, GRADE_MASTERED)

# Below 1.30 the interval stops growing meaningfully and the card churns forever.
MIN_EASE = Decimal("1.30")
DEFAULT_EASE = Decimal("2.50")

# A grade below this counts as a lapse: the card goes back to the start.
PASSING_GRADE = 3

FIRST_INTERVAL_DAYS = 1
SECOND_INTERVAL_DAYS = 6

# Session policy rather than algorithm, but it belongs next to the algorithm
# it shapes. An uncapped supply of new cards is the reliable way to build a
# review backlog the learner meets a fortnight later and abandons.
NEW_CARDS_PER_DAY = 20
MAX_SESSION_CARDS = 100

# A word counts as learned once its interval reaches three weeks. The threshold
# is Anki's "mature card" line and is measured in INTERVAL, not repetitions:
# repetitions only counts how many times the word came up, while the interval is
# what the algorithm actually believes about the memory. It also demotes
# correctly — a lapse resets the interval to one day, so a word that was learned
# and then forgotten stops claiming to be learned.
MASTERED_INTERVAL_DAYS = 21

MASTERY_NEW = "new"
MASTERY_LEARNING = "learning"
MASTERY_MASTERED = "mastered"
MASTERY_LEVELS = (MASTERY_NEW, MASTERY_LEARNING, MASTERY_MASTERED)


@dataclass(frozen=True)
class ReviewState:
    ease_factor: Decimal = DEFAULT_EASE
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


@dataclass(frozen=True)
class ReviewOutcome:
    ease_factor: Decimal
    interval_days: int
    repetitions: int
    lapses: int
    due_at: datetime


def next_ease(current: Decimal, grade: int) -> Decimal:
    """SM-2's ease update, floored.

    EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))

    A grade of 4 leaves the ease untouched, 5 raises it, 3 lowers it slightly.
    """
    q = Decimal(grade)
    five_minus_q = Decimal(5) - q
    delta = Decimal("0.1") - five_minus_q * (Decimal("0.08") + five_minus_q * Decimal("0.02"))
    updated = (current + delta).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(updated, MIN_EASE)


def mastery(state: ReviewState | None) -> str:
    """How far along one word is, derived rather than stored.

    `None` means the learner has never reviewed the word, which is genuinely
    different from having reviewed it and got it wrong: the first is `new`, the
    second is `learning` with the interval knocked back to a day. A stored
    column would have to be kept in step with every review and would drift the
    first time a review row was deleted, exactly as `StoryProgress` avoids.
    """
    if state is None:
        return MASTERY_NEW
    if state.interval_days >= MASTERED_INTERVAL_DAYS:
        return MASTERY_MASTERED
    return MASTERY_LEARNING


def review(state: ReviewState, grade: int, now: datetime) -> ReviewOutcome:
    """Apply one review and return the new state.

    `now` is a parameter rather than read from the clock so the result is
    reproducible in tests and when replaying a review log.
    """
    if grade not in GRADES:
        raise ValueError(f"grade must be one of {GRADES}, got {grade}")

    ease = next_ease(state.ease_factor, grade)

    if grade < PASSING_GRADE:
        # Forgetting resets the schedule but keeps the ease penalty, so a card
        # that has been forgotten repeatedly comes back faster than a fresh one.
        #
        # A lapse is FORGETTING, and you cannot forget what you never learned.
        # Failing a word on first sight used to count as one, which is wrong on
        # its own terms (Anki counts lapses only once a card has left the
        # learning stage) and wrong for what the column is FOR: `lapses` is
        # documented on the model as the signal AI Coach reads to name a
        # weakness. Counting first contact there would tell the coach a learner
        # keeps forgetting words they have simply never been taught.
        #
        # Điều kiện là `repetitions` hoặc `lapses`, KHÔNG phải `interval_days`.
        # Một thẻ trượt ngay lần đầu cũng được đặt `interval = 1`, nên lấy
        # interval làm dấu hiệu "đã từng học" sẽ tính lapse cho lần trượt thứ
        # hai của một từ chưa bao giờ đúng lần nào. `lapses > 0` mới là thứ
        # phân biệt được "interval = 1 vì vừa quên" với "interval = 1 vì chưa
        # từng thuộc".
        learned_before = state.repetitions > 0 or state.lapses > 0
        return ReviewOutcome(
            ease_factor=ease,
            interval_days=FIRST_INTERVAL_DAYS,
            repetitions=0,
            lapses=state.lapses + 1 if learned_before else state.lapses,
            due_at=now + timedelta(days=FIRST_INTERVAL_DAYS),
        )

    if grade == GRADE_MASTERED:
        # "Thành thạo" = học viên khẳng định đã thuộc, và engine tôn trọng điều
        # đó bằng cách nhảy thẳng lên mốc đã-thuộc thay vì bắt chờ ba tuần. Đây
        # là lần duy nhất điểm không đo chất lượng của TRÍ NHỚ mà đo một quyết
        # định — nên interval đặt CỨNG ở ngưỡng, không nhân với hệ số cũ.
        # Ease vẫn đi công thức chuẩn (chỉ số càng thấp càng thấy dễ), và lần
        # này vẫn tính là một lượt pass: `repetitions` nhích lên.
        ease = next_ease(state.ease_factor, GRADE_EASY)
        return ReviewOutcome(
            ease_factor=ease,
            interval_days=MASTERED_INTERVAL_DAYS,
            repetitions=state.repetitions + 1,
            lapses=state.lapses,
            due_at=now + timedelta(days=MASTERED_INTERVAL_DAYS),
        )

    repetitions = state.repetitions + 1
    if repetitions == 1:
        interval = FIRST_INTERVAL_DAYS
    elif repetitions == 2:
        interval = SECOND_INTERVAL_DAYS
    else:
        grown = Decimal(state.interval_days) * ease
        interval = max(1, int(grown.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    return ReviewOutcome(
        ease_factor=ease,
        interval_days=interval,
        repetitions=repetitions,
        lapses=state.lapses,
        due_at=now + timedelta(days=interval),
    )
