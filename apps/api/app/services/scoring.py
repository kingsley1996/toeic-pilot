"""Turn a finished attempt into a TOEIC score.

The conversion itself lives in the database (`score_scale` / `score_conversion`)
rather than here, because TOEIC curves differ per form and a scoring mistake
should be fixable by editing a row rather than by shipping a release. This module
only knows how to look one up and how to count what a learner got right.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice import LISTENING_PARTS, Attempt, AttemptItem, Question
from app.models.scoring import SECTIONS, ScoreConversion

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

    Only meaningful for a full test: a part-practice run covers one part, so a
    section score computed from it would be a number that looks like a TOEIC
    score without being one — and it would land in the learner's progress chart
    as if it were.
    """
    if attempt.mode != "full_test":
        raise ValueError(
            "only a full_test attempt can be scaled; part practice covers one part "
            "and has no section score"
        )
    if attempt.test is None:
        raise ValueError("a full_test attempt must reference a practice_test")

    counts = count_raw(session, attempt)
    scale = attempt.test.score_scale_slug

    attempt.listening_raw = counts["listening"]
    attempt.reading_raw = counts["reading"]
    attempt.listening_scaled = raw_to_scaled(session, scale, "listening", counts["listening"])
    attempt.reading_scaled = raw_to_scaled(session, scale, "reading", counts["reading"])
    attempt.total_scaled = attempt.listening_scaled + attempt.reading_scaled
    return attempt
