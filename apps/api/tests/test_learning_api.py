"""Learner-facing endpoints.

The recurring check is that draft content stays invisible. It is the only thing
between half-written material and a learner's screen, and it fails by simply
showing the content — no error, no log line.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.media import source_hash
from app.core.security import create_access_token
from app.models import (
    DictationAttempt,
    DictationItem,
    Topic,
    User,
    VocabularyAudio,
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
)
from app.services.srs import GRADE_FORGOT, GRADE_GOOD
from tests.test_domain_model import make_audio


@pytest.fixture()
def learner(db_session: Session) -> User:
    user = User(email="learner@example.com", hashed_password="x", role="learner")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def headers(learner: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(learner.id))}"}


def make_word(
    session: Session,
    headword: str = "invoice",
    *,
    status: str = "published",
    marker: str = "a",
) -> VocabularyEntry:
    entry = VocabularyEntry(
        headword=headword,
        part_of_speech="noun",
        phonetic="/ˈɪnvɔɪs/",
        meaning_en="a bill",
        meaning_vi="hóa đơn",
        status=status,
    )
    session.add(entry)
    session.flush()
    for index, accent in enumerate(("en-US", "en-GB", "en-AU", "en-CA")):
        voice = f"v{index}"
        digest = source_hash(headword, voice, "edge-tts", "1")
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
    session.commit()
    return entry


def make_dictation(
    session: Session,
    transcript: str = "The report is due Friday.",
    *,
    status: str = "published",
    marker: str = "d",
) -> DictationItem:
    asset = make_audio(session, marker=marker)
    session.flush()
    item = DictationItem(
        audio_asset_id=asset.id, transcript=transcript, difficulty=3, status=status
    )
    session.add(item)
    session.commit()
    return item


# --- topics ---------------------------------------------------------------


def test_only_published_topics_are_listed(client: TestClient, db_session: Session) -> None:
    db_session.add(Topic(slug="business", name="Business", status="published"))
    db_session.add(Topic(slug="secret", name="Not ready", status="draft"))
    db_session.commit()

    slugs = [topic["slug"] for topic in client.get("/api/v1/topics").json()]
    assert slugs == ["business"]


# --- vocabulary -----------------------------------------------------------


def test_draft_vocabulary_is_invisible(client: TestClient, db_session: Session) -> None:
    make_word(db_session, "invoice", status="published", marker="a")
    make_word(db_session, "unfinished", status="draft", marker="b")

    headwords = [row["headword"] for row in client.get("/api/v1/vocabulary").json()]
    assert headwords == ["invoice"]


def test_a_draft_entry_is_404_even_by_id(client: TestClient, db_session: Session) -> None:
    entry = make_word(db_session, "unfinished", status="draft")
    assert client.get(f"/api/v1/vocabulary/{entry.id}").status_code == 404


def test_detail_returns_all_four_accents(client: TestClient, db_session: Session) -> None:
    entry = make_word(db_session)
    body = client.get(f"/api/v1/vocabulary/{entry.id}").json()
    assert [clip["accent"] for clip in body["headword_audio"]] == [
        "en-AU",
        "en-CA",
        "en-GB",
        "en-US",
    ]
    assert all(clip["url"].endswith(".mp3") for clip in body["headword_audio"])


# --- review session -------------------------------------------------------


def test_a_new_learner_gets_new_cards(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    make_word(db_session, "invoice", marker="a")
    make_word(db_session, "deadline", marker="b")

    body = client.get("/api/v1/vocabulary-review/session", headers=headers).json()
    assert body["new_count"] == 2
    assert body["due_count"] == 0
    assert all(card["is_new"] for card in body["cards"])


def test_the_session_needs_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/vocabulary-review/session").status_code == 401


def test_reviewing_writes_both_the_state_and_the_log(
    client: TestClient, db_session: Session, headers: dict[str, str], learner: User
) -> None:
    entry = make_word(db_session)

    response = client.post(
        f"/api/v1/vocabulary/{entry.id}/review", json={"grade": GRADE_GOOD}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["interval_days"] == 1

    state = db_session.get(VocabularyReviewState, (learner.id, entry.id))
    assert state is not None and state.repetitions == 1
    # The log is what makes it possible to retune the algorithm later.
    assert db_session.query(VocabularyReviewLog).count() == 1


def test_forgetting_records_a_lapse(
    client: TestClient, db_session: Session, headers: dict[str, str], learner: User
) -> None:
    entry = make_word(db_session)
    client.post(
        f"/api/v1/vocabulary/{entry.id}/review", json={"grade": GRADE_GOOD}, headers=headers
    )
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/review", json={"grade": GRADE_FORGOT}, headers=headers
    ).json()

    assert body["lapses"] == 1
    assert body["repetitions"] == 0
    assert db_session.query(VocabularyReviewLog).count() == 2


def test_a_grade_outside_the_four_buttons_is_rejected(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    entry = make_word(db_session)
    response = client.post(
        f"/api/v1/vocabulary/{entry.id}/review", json={"grade": 2}, headers=headers
    )
    assert response.status_code == 422


def test_a_card_reviewed_today_is_not_due_again(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    entry = make_word(db_session)
    client.post(
        f"/api/v1/vocabulary/{entry.id}/review", json={"grade": GRADE_GOOD}, headers=headers
    )
    body = client.get("/api/v1/vocabulary-review/session", headers=headers).json()
    assert body["due_count"] == 0
    assert body["new_count"] == 0


def test_an_overdue_card_comes_back(
    client: TestClient, db_session: Session, headers: dict[str, str], learner: User
) -> None:
    entry = make_word(db_session)
    db_session.add(
        VocabularyReviewState(
            user_id=learner.id,
            entry_id=entry.id,
            interval_days=1,
            repetitions=1,
            due_at=datetime.now(UTC) - timedelta(days=2),
        )
    )
    db_session.commit()

    body = client.get("/api/v1/vocabulary-review/session", headers=headers).json()
    assert body["due_count"] == 1
    assert body["cards"][0]["is_new"] is False


def test_a_draft_entry_never_enters_a_session(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    make_word(db_session, "unfinished", status="draft")
    assert client.get("/api/v1/vocabulary-review/session", headers=headers).json()["cards"] == []


# --- dictation ------------------------------------------------------------


def test_draft_dictation_is_invisible(client: TestClient, db_session: Session) -> None:
    make_dictation(db_session, "The report is due Friday.", marker="d")
    make_dictation(db_session, "Not ready yet at all.", status="draft", marker="e")
    assert len(client.get("/api/v1/dictation").json()) == 1


def test_the_transcript_is_not_sent_before_the_answer(
    client: TestClient, db_session: Session
) -> None:
    # Sending the answer to the browser would make the exercise pointless.
    item = make_dictation(db_session)
    body = client.get(f"/api/v1/dictation/{item.id}").json()
    assert "transcript" not in body
    assert body["word_count"] == 5
    assert body["audio_url"].endswith(".mp3")


def test_submitting_returns_the_diff_and_the_answer(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    item = make_dictation(db_session, "The report is due Friday.")
    body = client.post(
        f"/api/v1/dictation/{item.id}/attempts",
        json={"submitted_text": "the report is due friday"},
        headers=headers,
    ).json()

    assert body["accuracy"] == "100.00"
    assert body["transcript"] == "The report is due Friday."
    assert all(word["op"] == "match" for word in body["diff"])


def test_a_wrong_word_is_reported_in_the_diff(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    item = make_dictation(db_session, "Please send the invoice.")
    body = client.post(
        f"/api/v1/dictation/{item.id}/attempts",
        json={"submitted_text": "please send the invoise"},
        headers=headers,
    ).json()

    ops = {(word["op"], word["word"]) for word in body["diff"]}
    assert ("missing", "invoice") in ops
    assert ("extra", "invoise") in ops


def test_the_raw_submission_is_stored_unchanged(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    # Normalisation belongs to the grader, and the grader will change; keeping
    # only the normalised text would make re-grading impossible.
    item = make_dictation(db_session)
    client.post(
        f"/api/v1/dictation/{item.id}/attempts",
        json={"submitted_text": "  The REPORT,  is due friday!  "},
        headers=headers,
    )
    stored = db_session.query(DictationAttempt).one()
    assert stored.submitted_text == "  The REPORT,  is due friday!  "


def test_submitting_needs_authentication(client: TestClient, db_session: Session) -> None:
    item = make_dictation(db_session)
    response = client.post(
        f"/api/v1/dictation/{item.id}/attempts", json={"submitted_text": "anything"}
    )
    assert response.status_code == 401


def test_a_draft_item_cannot_be_attempted(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    item = make_dictation(db_session, status="draft")
    response = client.post(
        f"/api/v1/dictation/{item.id}/attempts",
        json={"submitted_text": "anything"},
        headers=headers,
    )
    assert response.status_code == 404
