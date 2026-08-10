"""Raw-to-scaled score conversion (ADR-001 A6.2).

The conversion lives in the database rather than in code because TOEIC curves
differ per form and a scoring mistake should be fixable without a release. These
tests cover the seeded default curve and the refusal to guess.
"""

import pytest
from sqlalchemy.orm import Session

from app.content.seed_scores import ANCHORS, DEFAULT_SLUG, expand, seed_scales
from app.models import (
    Attempt,
    AttemptItem,
    PracticeTest,
    Question,
    QuestionOption,
    QuestionSet,
    ScoreScale,
)
from app.models.practice import GROUPED_PARTS
from app.models.scoring import MAX_SECTION_SCORE, MIN_SECTION_SCORE
from app.services.scoring import ScaleNotFoundError, count_raw, raw_to_scaled, score_attempt
from tests.test_domain_model import make_audio, make_question, make_user

# --- the curve itself -----------------------------------------------------


@pytest.mark.parametrize("section", ["listening", "reading"])
def test_the_curve_covers_every_possible_raw_score(section: str) -> None:
    table = expand(ANCHORS[section])
    assert sorted(table) == list(range(101))


@pytest.mark.parametrize("section", ["listening", "reading"])
def test_the_curve_never_goes_backwards(section: str) -> None:
    # More correct answers must never produce a lower score. Interpolating
    # between badly ordered anchors is the easy way to break this.
    scores = [expand(ANCHORS[section])[raw] for raw in range(101)]
    assert scores == sorted(scores)


@pytest.mark.parametrize("section", ["listening", "reading"])
def test_every_score_is_in_range_and_a_multiple_of_five(section: str) -> None:
    for raw, scaled in expand(ANCHORS[section]).items():
        assert MIN_SECTION_SCORE <= scaled <= MAX_SECTION_SCORE, raw
        assert scaled % 5 == 0, (raw, scaled)


def test_expand_rejects_anchors_that_leave_the_valid_range() -> None:
    with pytest.raises(ValueError, match="out-of-range"):
        expand(((0, 5), (100, 900)))


# --- seeding --------------------------------------------------------------


def test_seeding_creates_the_whole_table(db_session: Session) -> None:
    counts = seed_scales(db_session)
    assert counts == {"total": 202, "inserted": 202, "updated": 0, "unchanged": 0}


def test_seeding_twice_changes_nothing(db_session: Session) -> None:
    seed_scales(db_session)
    second = seed_scales(db_session)
    assert second["inserted"] == 0
    assert second["unchanged"] == 202


def test_the_seeded_scale_says_it_is_an_approximation(db_session: Session) -> None:
    # ETS publishes no official table. Anyone reading a score off this needs to
    # be able to find out where the number came from.
    seed_scales(db_session)
    note = db_session.get(ScoreScale, DEFAULT_SLUG).source_note
    assert "NOT an official" in note


# --- lookup ---------------------------------------------------------------


def test_a_perfect_paper_scores_990(db_session: Session) -> None:
    seed_scales(db_session)
    listening = raw_to_scaled(db_session, DEFAULT_SLUG, "listening", 100)
    reading = raw_to_scaled(db_session, DEFAULT_SLUG, "reading", 100)
    assert listening + reading == 990


def test_a_blank_paper_scores_the_floor(db_session: Session) -> None:
    seed_scales(db_session)
    assert raw_to_scaled(db_session, DEFAULT_SLUG, "listening", 0) == MIN_SECTION_SCORE


def test_an_unknown_scale_raises_rather_than_guessing(db_session: Session) -> None:
    # A silently wrong score is worse than a visible failure: it gets stored on
    # the attempt and the learner has no way to tell it is wrong.
    seed_scales(db_session)
    with pytest.raises(ScaleNotFoundError):
        raw_to_scaled(db_session, "form-2019-b", "listening", 50)


def test_an_unknown_section_is_rejected(db_session: Session) -> None:
    with pytest.raises(ValueError, match="section must be one of"):
        raw_to_scaled(db_session, DEFAULT_SLUG, "speaking", 50)


# --- scoring an attempt ---------------------------------------------------


def build_attempt(session: Session) -> Attempt:
    seed_scales(session)
    user = make_user(session)
    test = PracticeTest(slug="mock-1", title="Mock 1", kind="full")
    session.add(test)
    session.flush()
    attempt = Attempt(user_id=user.id, test_id=test.id)
    session.add(attempt)
    session.flush()
    return attempt


def add_item(session: Session, attempt: Attempt, part: int, position: int, correct: bool) -> None:
    extra: dict[str, object] = {}
    if part in GROUPED_PARTS:
        # Parts 3, 4, 6 and 7 are meaningless without their shared stimulus, and
        # the schema refuses to store one without it.
        stimulus = QuestionSet(part=part, audio_asset_id=make_audio(session, f"s{part}").id)
        session.add(stimulus)
        session.flush()
        extra["set_id"] = stimulus.id
    question = make_question(session, part=part, **extra)
    session.flush()
    session.add(
        AttemptItem(
            attempt_id=attempt.id,
            question_id=question.id,
            position=position,
            is_correct=correct,
        )
    )


def test_counting_splits_listening_from_reading(db_session: Session) -> None:
    attempt = build_attempt(db_session)
    add_item(db_session, attempt, part=3, position=1, correct=True)
    add_item(db_session, attempt, part=4, position=2, correct=True)
    add_item(db_session, attempt, part=5, position=3, correct=True)
    add_item(db_session, attempt, part=7, position=4, correct=False)
    db_session.flush()

    assert count_raw(db_session, attempt) == {"listening": 2, "reading": 1}


def test_an_unanswered_item_counts_as_wrong_not_as_absent(db_session: Session) -> None:
    attempt = build_attempt(db_session)
    add_item(db_session, attempt, part=5, position=1, correct=True)
    question = make_question(db_session, part=5)
    db_session.flush()
    db_session.add(AttemptItem(attempt_id=attempt.id, question_id=question.id, position=2))
    db_session.flush()

    assert count_raw(db_session, attempt) == {"listening": 0, "reading": 1}


def test_scoring_fills_in_raw_and_scaled(db_session: Session) -> None:
    attempt = build_attempt(db_session)
    add_item(db_session, attempt, part=3, position=1, correct=True)
    add_item(db_session, attempt, part=5, position=2, correct=True)
    db_session.flush()

    score_attempt(db_session, attempt)

    assert attempt.listening_raw == 1
    assert attempt.reading_raw == 1
    assert attempt.total_scaled == attempt.listening_scaled + attempt.reading_scaled


def test_a_partial_attempt_cannot_be_scaled(db_session: Session) -> None:
    # A section score computed from one part would look like a TOEIC score
    # without being one, and would land in the learner's progress chart as if it
    # were.
    seed_scales(db_session)
    user = make_user(db_session)
    test = PracticeTest(slug="mock-partial", title="Mock", kind="full")
    db_session.add(test)
    db_session.flush()
    attempt = Attempt(user_id=user.id, test_id=test.id, scope="partial")
    db_session.add(attempt)
    db_session.flush()

    with pytest.raises(ValueError, match="only a full-scope attempt"):
        score_attempt(db_session, attempt)


def test_the_test_chooses_the_scale(db_session: Session) -> None:
    attempt = build_attempt(db_session)
    assert attempt.test is not None
    assert attempt.test.score_scale_slug == DEFAULT_SLUG


def test_options_are_not_consulted_when_scoring(db_session: Session) -> None:
    # is_correct is stored, not re-derived: content can be corrected after a
    # learner has sat the test, and their past result must not move.
    attempt = build_attempt(db_session)
    question = make_question(db_session, part=5)
    db_session.flush()
    db_session.add(
        AttemptItem(attempt_id=attempt.id, question_id=question.id, position=1, is_correct=True)
    )
    db_session.flush()
    # Rewrite the answer key underneath them.
    for option in db_session.query(QuestionOption).filter(Question.id == question.id).all():
        option.is_correct = False
    db_session.flush()

    assert count_raw(db_session, attempt)["reading"] == 1
