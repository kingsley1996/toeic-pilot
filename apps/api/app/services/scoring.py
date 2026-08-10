"""Turn a finished attempt into a TOEIC score.

The conversion itself lives in the database (`score_scale` / `score_conversion`)
rather than here, because TOEIC curves differ per form and a scoring mistake
should be fixable by editing a row rather than by shipping a release. This module
only knows how to look one up and how to count what a learner got right.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice import (
    LISTENING_PARTS,
    Attempt,
    AttemptItem,
    PracticeTestQuestion,
    Question,
)
from app.models.scoring import SECTIONS, ScoreConversion

_READING_PARTS = (5, 6, 7)

DEFAULT_SCALE_SLUG = "default"


class ScaleNotFoundError(LookupError):
    """No conversion row for this (scale, section, raw count).

    Raised rather than falling back to an interpolation or a zero: a silently
    wrong score is worse than a visible failure, because the learner has no way
    to tell it is wrong and it is stored permanently on the attempt.
    """


def raw_to_scaled(session: Session, scale_slug: str, section: str, raw_correct: int) -> int:
    if section not in SECTIONS:
        raise ValueError(f"section must be one of {SECTIONS}, got {section!r}")

    scaled = session.scalar(
        select(ScoreConversion.scaled_score).where(
            ScoreConversion.scale_slug == scale_slug,
            ScoreConversion.section == section,
            ScoreConversion.raw_correct == raw_correct,
        )
    )
    if scaled is None:
        raise ScaleNotFoundError(
            f"scale {scale_slug!r} has no {section} row for {raw_correct} correct; "
            f"seed it with: uv run python -m app.content.seed_scores"
        )
    return scaled


def count_raw(session: Session, attempt: Attempt) -> dict[str, int]:
    """Count correct answers per section.

    Reads the stored `is_correct` rather than re-deriving it from the selected
    option: content can be corrected after a learner has sat the test, and a past
    result must keep the verdict it had at the time.
    """
    rows = session.execute(
        select(Question.part, AttemptItem.is_correct)
        .join(Question, Question.id == AttemptItem.question_id)
        .where(AttemptItem.attempt_id == attempt.id)
    ).all()

    counts = {"listening": 0, "reading": 0}
    for part, is_correct in rows:
        if is_correct:
            counts["listening" if part in LISTENING_PARTS else "reading"] += 1
    return counts


def score_attempt(session: Session, attempt: Attempt) -> Attempt:
    """Fill in the raw and scaled scores on a submitted attempt.

    Only meaningful for a full test: a partial run covers a subset of parts, so
    a section score computed from it would be a number that looks like a TOEIC
    score without being one — and it would land in the learner's progress chart
    as if it were.
    """
    if attempt.scope != "full":
        raise ValueError(
            "only a full-scope attempt can be scaled; a partial run covers some parts "
            "and has no section score"
        )

    # `scope == "full"` chỉ trả lời "có làm hết đề này không", KHÔNG trả lời
    # "đề này có phải một đề đầy đủ không". Hai câu đó khác nhau, và nhầm chúng
    # là một sinh ra đúng thứ docstring trên vừa cảnh báo:
    #
    #   Đề rút gọn 10 câu, toàn Part 5, làm đúng 6 -> scope='full'
    #   -> reading_raw = 6 đem tra bảng dựng cho 100 câu -> chạm sàn
    #   -> listening_raw = 0 cho một phần đề KHÔNG HỀ CÓ  -> chạm sàn
    #   -> "Nghe 5 · Đọc 5 · Tổng 10"
    #
    # Ba con số trông y hệt điểm TOEIC. Người học làm đúng 60% và được báo là
    # chạm sàn, kèm một điểm Nghe cho phần họ chưa từng nghe.
    if attempt.test.kind != "full":
        raise ValueError(
            f"a {attempt.test.kind!r} test has no TOEIC conversion: the scale is built for "
            f"a 200-question form, so a shorter test would be read as a near-zero raw score"
        )

    counts = count_raw(session, attempt)

    # Và một đề tự khai là `full` nhưng thiếu hẳn một phần thì cũng không quy
    # đổi được: điểm 5 của phần vắng mặt là điểm sàn cho một bài chưa từng thi.
    for section, raw in counts.items():
        if raw == 0 and not _has_section(session, attempt, section):
            raise ValueError(f"test has no {section} questions; there is no {section} score")

    scale = attempt.test.score_scale_slug

    attempt.listening_raw = counts["listening"]
    attempt.reading_raw = counts["reading"]
    attempt.listening_scaled = raw_to_scaled(session, scale, "listening", counts["listening"])
    attempt.reading_scaled = raw_to_scaled(session, scale, "reading", counts["reading"])
    attempt.total_scaled = attempt.listening_scaled + attempt.reading_scaled
    return attempt


def _has_section(session: Session, attempt: Attempt, section: str) -> bool:
    """Đề này có câu nào thuộc phần Nghe / Đọc không.

    Hỏi ĐỀ chứ không hỏi lượt làm: một người bỏ trống cả phần Nghe vẫn phải
    nhận điểm sàn của phần đó — đó là kết quả thật. Còn một đề không có phần
    Nghe thì không có gì để chấm.
    """
    parts = LISTENING_PARTS if section == "listening" else _READING_PARTS
    return bool(
        session.scalar(
            select(Question.id)
            .join(PracticeTestQuestion, PracticeTestQuestion.question_id == Question.id)
            .where(
                PracticeTestQuestion.test_id == attempt.test_id,
                Question.part.in_(parts),
            )
            .limit(1)
        )
    )
