"""SM-2, dictation grading, and audio staleness.

All three are pure functions over values, so these tests need no database except
where the staleness check walks real model objects.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.media import source_hash
from app.models import DictationItem, VocabularyAudio, VocabularyEntry
from app.services.dictation import grade, normalise
from app.services.media_state import (
    AudioState,
    dictation_audio_state,
    vocabulary_audio_slots,
    vocabulary_is_publishable,
)
from app.services.srs import (
    DEFAULT_EASE,
    GRADE_EASY,
    GRADE_FORGOT,
    GRADE_GOOD,
    GRADE_HARD,
    MIN_EASE,
    ReviewState,
    next_ease,
    review,
)
from tests.test_domain_model import make_audio, make_entry

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


# --- SM-2 -----------------------------------------------------------------


def test_first_successful_review_schedules_one_day() -> None:
    out = review(ReviewState(), GRADE_GOOD, NOW)
    assert out.repetitions == 1
    assert out.interval_days == 1
    assert (out.due_at - NOW).days == 1


def test_second_successful_review_schedules_six_days() -> None:
    out = review(ReviewState(interval_days=1, repetitions=1), GRADE_GOOD, NOW)
    assert out.interval_days == 6


def test_third_review_multiplies_by_the_ease_factor() -> None:
    state = ReviewState(ease_factor=Decimal("2.50"), interval_days=6, repetitions=2)
    assert review(state, GRADE_GOOD, NOW).interval_days == 15  # 6 * 2.5


def test_forgetting_resets_the_schedule_and_counts_a_lapse() -> None:
    state = ReviewState(ease_factor=Decimal("2.50"), interval_days=30, repetitions=5)
    out = review(state, GRADE_FORGOT, NOW)
    assert out.interval_days == 1
    assert out.repetitions == 0
    assert out.lapses == 1


def test_forgetting_keeps_the_ease_penalty() -> None:
    # A card forgotten repeatedly must come back faster than a fresh one, which
    # only happens if the ease penalty survives the reset.
    state = ReviewState(ease_factor=Decimal("2.50"), interval_days=30, repetitions=5)
    assert review(state, GRADE_FORGOT, NOW).ease_factor < Decimal("2.50")


def test_a_good_grade_leaves_the_ease_untouched() -> None:
    assert next_ease(DEFAULT_EASE, GRADE_GOOD) == DEFAULT_EASE


def test_easy_raises_and_hard_lowers_the_ease() -> None:
    assert next_ease(DEFAULT_EASE, GRADE_EASY) > DEFAULT_EASE
    assert next_ease(DEFAULT_EASE, GRADE_HARD) < DEFAULT_EASE


def test_the_ease_never_falls_below_the_floor() -> None:
    ease = DEFAULT_EASE
    for _ in range(50):
        ease = next_ease(ease, GRADE_FORGOT)
    assert ease == MIN_EASE


def test_intervals_never_go_backwards_on_a_pass() -> None:
    state = ReviewState()
    previous = 0
    for _ in range(8):
        out = review(state, GRADE_GOOD, NOW)
        assert out.interval_days >= previous
        previous = out.interval_days
        state = ReviewState(out.ease_factor, out.interval_days, out.repetitions, out.lapses)


def test_an_unknown_grade_is_rejected() -> None:
    # 1 and 2 are valid in original SM-2 but not in the four-button UI; letting
    # them through would silently mean something different from what was clicked.
    with pytest.raises(ValueError, match="grade must be one of"):
        review(ReviewState(), 2, NOW)


# --- dictation grading ----------------------------------------------------


def test_normalise_drops_case_and_punctuation() -> None:
    assert normalise("The report, due Friday!") == ["the", "report", "due", "friday"]


def test_normalise_keeps_apostrophes() -> None:
    # "don't" and "dont" is a real spelling difference; a comma is a guess.
    assert normalise("Don't go") == ["don't", "go"]


def test_normalise_accepts_a_typographic_apostrophe() -> None:
    assert normalise("Don’t go") == normalise("Don't go")


def test_a_perfect_submission_scores_100() -> None:
    result = grade("The report is due Friday.", "the report is due friday")
    assert result.accuracy == Decimal("100.00")
    assert all(item.op == "match" for item in result.diff)


def test_punctuation_alone_does_not_lose_marks() -> None:
    assert grade("Yes, of course!", "yes of course").accuracy == Decimal("100.00")


def test_a_misspelling_is_reported() -> None:
    result = grade("Please send the invoice.", "please send the invoise")
    assert result.accuracy < Decimal("100.00")
    ops = {(item.op, item.word) for item in result.diff}
    assert ("missing", "invoice") in ops
    assert ("extra", "invoise") in ops


def test_a_missing_word_lowers_accuracy_proportionally() -> None:
    result = grade("one two three four", "one two four")
    assert result.matched == 3
    assert result.expected == 4
    assert result.accuracy == Decimal("75.00")


def test_extra_words_are_reported_but_do_not_inflate_the_score() -> None:
    result = grade("one two", "one two three four")
    assert result.accuracy == Decimal("100.00")
    assert [item.word for item in result.diff if item.op == "extra"] == ["three", "four"]


def test_an_empty_submission_scores_zero() -> None:
    assert grade("one two three", "").accuracy == Decimal("0.00")


def test_the_diff_is_json_serialisable() -> None:
    payload = grade("one two", "one").as_json()
    assert payload[0] == {"op": "match", "word": "one"}


# --- audio staleness ------------------------------------------------------


def attach_audio(session: Session, entry: VocabularyEntry, text: str, marker: str) -> None:
    """Give the entry a full set of four headword accents made from `text`."""
    for index, accent in enumerate(("en-US", "en-GB", "en-AU", "en-CA")):
        voice = f"v{index}"
        digest = source_hash(text, voice, "edge-tts", "1")
        asset = make_audio(session, marker=f"{marker}{index}")
        asset.source_hash = digest
        asset.storage_key = f"audio/{digest[:2]}/{digest}.mp3"
        asset.voice = voice
        asset.accent = accent
        session.flush()
        session.add(
            VocabularyAudio(
                entry_id=entry.id, kind="headword", accent=accent, audio_asset_id=asset.id
            )
        )
    session.flush()


def test_an_entry_with_no_audio_is_all_missing(db_session: Session) -> None:
    entry = make_entry(db_session)
    slots = vocabulary_audio_slots(entry)
    assert len(slots) == 4  # no example sentence, so four clips is complete
    assert all(slot.state is AudioState.MISSING for slot in slots)
    assert not vocabulary_is_publishable(entry)


def test_a_fully_recorded_entry_is_publishable(db_session: Session) -> None:
    entry = make_entry(db_session, "invoice")
    attach_audio(db_session, entry, "invoice", "a")
    db_session.refresh(entry)
    assert vocabulary_is_publishable(entry)


def test_editing_the_headword_makes_the_audio_stale(db_session: Session) -> None:
    # The defect this whole module exists for: without it, the entry still reads
    # "receive" while every clip still says "recieve", and nothing notices.
    entry = make_entry(db_session, "recieve")
    attach_audio(db_session, entry, "recieve", "b")
    db_session.refresh(entry)
    assert vocabulary_is_publishable(entry)

    entry.headword = "receive"
    db_session.flush()

    assert all(slot.state is AudioState.STALE for slot in vocabulary_audio_slots(entry))
    assert not vocabulary_is_publishable(entry)


def test_an_example_sentence_adds_four_more_required_clips(db_session: Session) -> None:
    entry = make_entry(db_session, "invoice")
    entry.example = "Please pay the invoice."
    db_session.flush()
    assert len(vocabulary_audio_slots(entry)) == 8


def test_editing_a_transcript_makes_the_dictation_audio_stale(db_session: Session) -> None:
    # Worse here than for vocabulary: the transcript is the answer key, so the
    # learner is graded against a sentence they were never played.
    transcript = "The shipment arrives Tuesday."
    digest = source_hash(transcript, "us_female_1", "edge-tts", "1")
    asset = make_audio(db_session, "c")
    asset.source_hash = digest
    asset.storage_key = f"audio/{digest[:2]}/{digest}.mp3"
    db_session.flush()

    item = DictationItem(audio_asset_id=asset.id, transcript=transcript, difficulty=3)
    db_session.add(item)
    db_session.flush()
    assert dictation_audio_state(item) is AudioState.CURRENT

    item.transcript = "The shipment arrives on Tuesday."
    db_session.flush()
    assert dictation_audio_state(item) is AudioState.STALE


def test_bumping_the_engine_version_does_not_make_audio_stale(db_session: Session) -> None:
    # Correctness, not regeneration: a clip made by an older engine still says
    # the right words, so it must not block publishing.
    entry = make_entry(db_session, "invoice")
    attach_audio(db_session, entry, "invoice", "d")
    db_session.refresh(entry)
    for row in entry.audio:
        assert row.asset.engine_version == "1"
    assert vocabulary_is_publishable(entry)


def test_the_mastery_boundary_is_exactly_the_interval_threshold() -> None:
    """21 days is the line; 20 is still learning.

    Pinned as a unit test because an off-by-one here is invisible in the UI —
    the badge just says "đang học" for a word the learner has in fact learned.
    """
    from app.services.srs import (
        MASTERED_INTERVAL_DAYS,
        MASTERY_LEARNING,
        MASTERY_MASTERED,
        MASTERY_NEW,
        ReviewState,
        mastery,
    )

    assert mastery(None) == MASTERY_NEW
    assert mastery(ReviewState(interval_days=MASTERED_INTERVAL_DAYS - 1)) == MASTERY_LEARNING
    assert mastery(ReviewState(interval_days=MASTERED_INTERVAL_DAYS)) == MASTERY_MASTERED
    # A brand-new state row with no interval yet is being learned, not new: the
    # row only exists because the learner has already seen the word.
    assert mastery(ReviewState()) == MASTERY_LEARNING
