"""Constraints and content rules of the domain schema (ADR-001).

The point of these tests is the malformed cases. A schema that accepts a part 3
question with no conversation attached, or a question with no correct answer, is
a schema that fails in front of a learner rather than at seed time.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.media import AUDIO_ACCENTS
from app.models import (
    Attempt,
    AttemptItem,
    AudioAsset,
    DictationAttempt,
    DictationItem,
    PracticeTest,
    Question,
    QuestionOption,
    QuestionSet,
    Topic,
    User,
    VocabularyAudio,
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
    VocabularyTopic,
)
from app.models.validators import expected_option_count, validate_question


def make_audio(session: Session, marker: str = "a") -> AudioAsset:
    digest = (marker * 64)[:64]
    asset = AudioAsset(
        storage_key=f"audio/{digest[:2]}/{digest}.mp3",
        source_hash=digest,
        mime_type="audio/mpeg",
        size_bytes=1024,
        duration_ms=1000,
        source="tts",
        engine="edge-tts",
        engine_version="1",
        voice="us_female_1",
        accent="en-US",
    )
    session.add(asset)
    session.flush()
    return asset


def make_user(session: Session, email: str = "learner@example.com") -> User:
    user = User(email=email, hashed_password="x")
    session.add(user)
    session.flush()
    return user


def make_entry(session: Session, headword: str = "invoice", pos: str = "noun") -> VocabularyEntry:
    entry = VocabularyEntry(
        headword=headword,
        part_of_speech=pos,
        meaning_en="a bill",
        meaning_vi="hóa đơn",
        status="published",
    )
    session.add(entry)
    session.flush()
    return entry


def make_question(
    session: Session,
    part: int = 5,
    *,
    correct: int = 1,
    options: int | None = None,
    **kwargs: object,
) -> Question:
    question = Question(
        part=part,
        prompt_text=None if part == 2 else "The report ____ due on Friday.",
        difficulty=3,
        source="original",
        status="published",
        **kwargs,
    )
    count = expected_option_count(part) if options is None else options
    for index in range(count):
        question.options.append(
            QuestionOption(
                label="ABCD"[index],
                content=None if part == 2 else f"option {index}",
                is_correct=index < correct,
            )
        )
    session.add(question)
    return question


# --- vocabulary -----------------------------------------------------------


def test_same_headword_with_different_part_of_speech_coexists(db_session: Session) -> None:
    # "book" the noun and "book" the verb are separate entries.
    make_entry(db_session, "book", "noun")
    make_entry(db_session, "book", "verb")
    db_session.commit()
    assert db_session.query(VocabularyEntry).count() == 2


def test_headword_and_part_of_speech_are_unique_together(db_session: Session) -> None:
    make_entry(db_session, "book", "noun")
    db_session.commit()
    # make_entry flushes, so the violation surfaces there rather than at commit.
    with pytest.raises(IntegrityError):
        make_entry(db_session, "book", "noun")


def test_a_fully_recorded_entry_has_eight_audio_rows(db_session: Session) -> None:
    # Four TOEIC accents times {headword, example} — the reason a single FK
    # column on the entry could never have worked (PHASE2-AUDIO A6).
    entry = make_entry(db_session)
    for index, accent in enumerate(AUDIO_ACCENTS):
        for kind in ("headword", "example"):
            asset = make_audio(db_session, marker=f"{index}{kind[0]}")
            db_session.add(
                VocabularyAudio(
                    entry_id=entry.id, kind=kind, accent=accent, audio_asset_id=asset.id
                )
            )
    db_session.commit()
    assert db_session.query(VocabularyAudio).count() == 8


def test_the_same_accent_cannot_be_recorded_twice_for_one_kind(db_session: Session) -> None:
    entry = make_entry(db_session)
    first = make_audio(db_session, "b")
    second = make_audio(db_session, "c")
    db_session.add(
        VocabularyAudio(entry_id=entry.id, kind="headword", accent="en-US", audio_asset_id=first.id)
    )
    db_session.commit()
    db_session.add(
        VocabularyAudio(
            entry_id=entry.id, kind="headword", accent="en-US", audio_asset_id=second.id
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_accent_is_constrained_to_the_four_toeic_values(db_session: Session) -> None:
    entry = make_entry(db_session)
    asset = make_audio(db_session, "d")
    db_session.add(
        VocabularyAudio(entry_id=entry.id, kind="headword", accent="en-IE", audio_asset_id=asset.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_topic_membership_is_many_to_many(db_session: Session) -> None:
    entry = make_entry(db_session, "contract")
    for slug in ("business", "legal"):
        topic = Topic(slug=slug, name=slug.title(), status="published")
        db_session.add(topic)
        db_session.flush()
        db_session.add(VocabularyTopic(entry_id=entry.id, topic_id=topic.id))
    db_session.commit()
    assert db_session.query(VocabularyTopic).count() == 2


def test_review_state_and_log_are_kept_separately(db_session: Session) -> None:
    # The state is overwritten on every review; without the log there is no way
    # to retune the algorithm or show a forgetting trend.
    user = make_user(db_session)
    entry = make_entry(db_session)
    now = datetime.now(UTC)
    db_session.add(
        VocabularyReviewState(
            user_id=user.id,
            entry_id=entry.id,
            interval_days=1,
            repetitions=1,
            due_at=now + timedelta(days=1),
        )
    )
    for grade in (5, 3):
        db_session.add(
            VocabularyReviewLog(
                user_id=user.id,
                entry_id=entry.id,
                grade=grade,
                interval_days=1,
                ease_factor=Decimal("2.50"),
            )
        )
    db_session.commit()

    assert db_session.query(VocabularyReviewState).count() == 1
    assert db_session.query(VocabularyReviewLog).count() == 2


def test_ease_factor_cannot_drop_below_the_sm2_floor(db_session: Session) -> None:
    user = make_user(db_session)
    entry = make_entry(db_session)
    db_session.add(
        VocabularyReviewState(
            user_id=user.id,
            entry_id=entry.id,
            ease_factor=Decimal("1.00"),
            due_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- dictation ------------------------------------------------------------


def test_dictation_stores_the_transcript_separately_from_the_tts_text(
    db_session: Session,
) -> None:
    # audio_asset.source_text exists to re-derive audio; dictation_item.transcript
    # is the answer key. They drift the moment either is edited.
    asset = make_audio(db_session)
    asset.source_text = "The shipment arrives Tuesday"
    item = DictationItem(
        audio_asset_id=asset.id,
        transcript="The shipment arrives Tuesday.",
        difficulty=3,
        status="published",
    )
    db_session.add(item)
    db_session.commit()
    assert item.transcript != asset.source_text


def test_dictation_attempt_keeps_the_raw_submission(db_session: Session) -> None:
    asset = make_audio(db_session)
    item = DictationItem(audio_asset_id=asset.id, transcript="Hello there.", difficulty=1)
    user = make_user(db_session)
    db_session.add(item)
    db_session.flush()
    attempt = DictationAttempt(
        user_id=user.id,
        item_id=item.id,
        submitted_text="  hello   there  ",
        accuracy=Decimal("100.00"),
        word_diff={"matched": 2, "missed": 0},
    )
    db_session.add(attempt)
    db_session.commit()

    stored = db_session.query(DictationAttempt).one()
    assert stored.submitted_text == "  hello   there  "
    assert stored.word_diff == {"matched": 2, "missed": 0}


# --- questions ------------------------------------------------------------


def test_a_grouped_part_cannot_exist_without_its_stimulus(db_session: Session) -> None:
    # Part 3 is a conversation. A part 3 question with no conversation is not a
    # question, and the database should say so at seed time.
    make_question(db_session, part=3)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_a_standalone_part_needs_no_stimulus(db_session: Session) -> None:
    make_question(db_session, part=5)
    db_session.commit()
    assert db_session.query(Question).count() == 1


def test_at_most_one_option_can_be_correct(db_session: Session) -> None:
    make_question(db_session, part=5, correct=2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_a_question_with_no_correct_option_still_inserts(db_session: Session) -> None:
    # Documents the gap the partial unique index leaves open, and why
    # validate_question exists at all (ADR-001 B4).
    question = make_question(db_session, part=5, correct=0)
    db_session.commit()

    assert db_session.query(Question).count() == 1
    assert "no option is marked correct" in validate_question(question)


def test_deleting_a_question_deletes_its_options(db_session: Session) -> None:
    question = make_question(db_session, part=5)
    db_session.commit()
    db_session.delete(question)
    db_session.commit()
    assert db_session.query(QuestionOption).count() == 0


def test_question_source_is_constrained(db_session: Session) -> None:
    # Provenance matters legally: real TOEIC material is ETS copyright.
    question = make_question(db_session, part=5)
    question.source = "scraped-from-somewhere"
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- attempts -------------------------------------------------------------


def test_part_practice_must_not_reference_a_test(db_session: Session) -> None:
    user = make_user(db_session)
    test = PracticeTest(slug="mock-1", title="Mock 1", kind="full")
    db_session.add(test)
    db_session.flush()
    db_session.add(Attempt(user_id=user.id, mode="part_practice", part=5, test_id=test.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_full_test_must_reference_a_test(db_session: Session) -> None:
    user = make_user(db_session)
    db_session.add(Attempt(user_id=user.id, mode="full_test", test_id=None))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_an_unanswered_item_is_recorded_not_omitted(db_session: Session) -> None:
    # Blanks at the end of part 7 mean the learner ran out of time. That is the
    # signal; it must survive as a row, not as a missing row.
    user = make_user(db_session)
    question = make_question(db_session, part=5)
    attempt = Attempt(user_id=user.id, mode="part_practice", part=5)
    db_session.add(attempt)
    db_session.flush()
    attempt.items.append(AttemptItem(question_id=question.id, position=1))
    db_session.commit()

    item = db_session.query(AttemptItem).one()
    assert item.selected_option_id is None
    assert item.is_correct is None


def test_a_question_cannot_be_served_twice_in_one_attempt(db_session: Session) -> None:
    user = make_user(db_session)
    question = make_question(db_session, part=5)
    attempt = Attempt(user_id=user.id, mode="part_practice", part=5)
    db_session.add(attempt)
    db_session.flush()
    attempt.items.append(AttemptItem(question_id=question.id, position=1))
    attempt.items.append(AttemptItem(question_id=question.id, position=2))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_scaled_scores_are_stored_on_the_attempt(db_session: Session) -> None:
    # Stored rather than derived, so correcting the conversion table later cannot
    # rewrite a learner's past results.
    user = make_user(db_session)
    test = PracticeTest(slug="mock-2", title="Mock 2", kind="full")
    db_session.add(test)
    db_session.flush()
    attempt = Attempt(
        user_id=user.id,
        mode="full_test",
        test_id=test.id,
        listening_raw=80,
        reading_raw=70,
        listening_scaled=395,
        reading_scaled=325,
        total_scaled=720,
    )
    db_session.add(attempt)
    db_session.commit()
    assert db_session.query(Attempt).one().total_scaled == 720


# --- validators (ADR-001 B4) ---------------------------------------------


def test_a_well_formed_question_has_no_problems(db_session: Session) -> None:
    question = make_question(db_session, part=5)
    assert validate_question(question) == []


def test_part_2_expects_three_unprinted_options(db_session: Session) -> None:
    asset = make_audio(db_session)
    question = make_question(db_session, part=2, audio_asset_id=asset.id)
    assert validate_question(question) == []
    assert expected_option_count(2) == 3


def test_part_2_with_four_options_is_rejected(db_session: Session) -> None:
    asset = make_audio(db_session)
    question = make_question(db_session, part=2, options=4, audio_asset_id=asset.id)
    assert any("exactly 3 options" in problem for problem in validate_question(question))


def test_part_2_must_not_print_its_prompt(db_session: Session) -> None:
    asset = make_audio(db_session)
    question = make_question(db_session, part=2, audio_asset_id=asset.id)
    question.prompt_text = "Where is the meeting?"
    assert any("prints no prompt" in problem for problem in validate_question(question))


def test_a_question_whose_part_disagrees_with_its_set_is_rejected(db_session: Session) -> None:
    # No composite FK can enforce this while set_id stays nullable.
    asset = make_audio(db_session)
    stimulus = QuestionSet(part=4, audio_asset_id=asset.id, status="published")
    db_session.add(stimulus)
    db_session.flush()
    question = make_question(db_session, part=3, set_id=stimulus.id)
    question.question_set = stimulus
    assert any("but its set is part 4" in problem for problem in validate_question(question))


def test_part_1_without_a_photograph_is_rejected(db_session: Session) -> None:
    asset = make_audio(db_session)
    question = make_question(db_session, part=1, audio_asset_id=asset.id)
    assert "part 1 questions need a photograph" in validate_question(question)


def test_part_5_needs_neither_audio_nor_a_photograph(db_session: Session) -> None:
    question = make_question(db_session, part=5)
    assert validate_question(question) == []


def test_validator_reports_every_problem_at_once(db_session: Session) -> None:
    question = make_question(db_session, part=3, correct=0, options=2)
    problems = validate_question(question)
    assert len(problems) >= 3, problems


def test_validator_rejects_an_out_of_range_part() -> None:
    assert validate_question(Question(part=9)) == ["part must be between 1 and 7, got 9"]


def test_uuid_primary_keys_are_generated(db_session: Session) -> None:
    question = make_question(db_session, part=5)
    db_session.commit()
    assert isinstance(question.id, uuid.UUID)
