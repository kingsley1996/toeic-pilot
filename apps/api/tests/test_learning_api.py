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
    VocabularyTopic,
)
from app.services.srs import GRADE_FORGOT, GRADE_GOOD, GRADE_HARD
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

    headwords = [row["headword"] for row in client.get("/api/v1/vocabulary").json()["items"]]
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
    assert client.get("/api/v1/dictation").json()["total"] == 1


def test_the_transcript_ships_with_the_item_for_client_side_grading(
    client: TestClient, db_session: Session
) -> None:
    """The answer key is sent on purpose, and this test is the record of that.

    It used to assert the opposite. Grading moved to the client so feedback is
    instant, which requires the answer in the browser — the trade is written up
    on `DictationDetail.transcript`. Pinning it here means the day someone needs
    the answer hidden again, they change a decision rather than discover one.
    """
    item = make_dictation(db_session)
    body = client.get(f"/api/v1/dictation/{item.id}").json()
    assert body["transcript"] == "The report is due Friday."
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


# --- vocabulary progress ---------------------------------------------------


def test_vocabulary_progress_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/vocabulary-progress").status_code == 401


def test_progress_path_is_not_swallowed_by_the_entry_id_route(
    client: TestClient, headers: dict[str, str]
) -> None:
    """`/vocabulary/{entry_id}` would parse "progress" as a UUID and 422.

    The hyphenated path is what avoids it; a 422 here means someone moved the
    endpoint under `/vocabulary/` and the route order started mattering.
    """
    assert client.get("/api/v1/vocabulary-progress", headers=headers).status_code == 200


def test_a_word_never_reviewed_counts_as_new(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    make_word(db_session, "invoice", marker="a")

    body = client.get("/api/v1/vocabulary-progress", headers=headers).json()
    assert (body["total"], body["new"], body["learning"], body["mastered"]) == (1, 1, 0, 0)
    assert body["due"] == 0, "a word never reviewed is not due, it is unstarted"
    assert body["entries"][0]["mastery"] == "new"


def test_a_short_interval_is_learning_and_a_long_one_is_mastered(
    client: TestClient, db_session: Session, learner: User, headers: dict[str, str]
) -> None:
    learning = make_word(db_session, "invoice", marker="a")
    mastered = make_word(db_session, "warehouse", marker="b")
    for entry, interval in ((learning, 6), (mastered, 21)):
        db_session.add(
            VocabularyReviewState(
                user_id=learner.id,
                entry_id=entry.id,
                interval_days=interval,
                repetitions=3,
                due_at=datetime.now(UTC) + timedelta(days=interval),
            )
        )
    db_session.commit()

    body = client.get("/api/v1/vocabulary-progress", headers=headers).json()
    assert (body["learning"], body["mastered"], body["new"]) == (1, 1, 0)
    by_id = {row["entry_id"]: row["mastery"] for row in body["entries"]}
    assert by_id[str(learning.id)] == "learning"
    assert by_id[str(mastered.id)] == "mastered"


def test_forgetting_a_mastered_word_demotes_it(
    client: TestClient, db_session: Session, learner: User, headers: dict[str, str]
) -> None:
    """A lapse resets the interval to one day, so mastery has to follow it down.

    Keying off `repetitions` instead would leave the word claiming to be
    mastered forever — the count only ever grows.
    """
    entry = make_word(db_session, "invoice", marker="a")
    db_session.add(
        VocabularyReviewState(
            user_id=learner.id,
            entry_id=entry.id,
            interval_days=1,
            repetitions=0,
            lapses=1,
            due_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db_session.commit()

    body = client.get("/api/v1/vocabulary-progress", headers=headers).json()
    assert body["mastered"] == 0
    assert body["entries"][0]["mastery"] == "learning"


def test_progress_counts_only_the_topic_being_viewed(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    """The denominator must match the list, or "12/40" can never reach 40."""
    topic = Topic(slug="business", name="Business", status="published")
    db_session.add(topic)
    inside = make_word(db_session, "invoice", marker="a")
    make_word(db_session, "elsewhere", marker="b")
    db_session.flush()
    db_session.add(VocabularyTopic(entry_id=inside.id, topic_id=topic.id))
    db_session.commit()

    listed = client.get("/api/v1/vocabulary?topic=business").json()["items"]
    body = client.get("/api/v1/vocabulary-progress?topic=business", headers=headers).json()
    assert body["total"] == len(listed) == 1


def test_draft_words_are_not_counted(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    make_word(db_session, "invoice", status="published", marker="a")
    make_word(db_session, "unfinished", status="draft", marker="b")

    assert client.get("/api/v1/vocabulary-progress", headers=headers).json()["total"] == 1


def test_another_learners_progress_does_not_leak(
    client: TestClient, db_session: Session, learner: User, headers: dict[str, str]
) -> None:
    entry = make_word(db_session, "invoice", marker="a")
    other = User(email="other@example.com", hashed_password="x", role="learner")
    db_session.add(other)
    db_session.flush()
    db_session.add(
        VocabularyReviewState(
            user_id=other.id,
            entry_id=entry.id,
            interval_days=40,
            repetitions=5,
            due_at=datetime.now(UTC) + timedelta(days=40),
        )
    )
    db_session.commit()

    body = client.get("/api/v1/vocabulary-progress", headers=headers).json()
    assert body["mastered"] == 0, "another learner's mastery must not show here"
    assert body["new"] == 1


# --- gõ lại từ -------------------------------------------------------------


def test_recall_needs_authentication(client: TestClient, db_session: Session) -> None:
    entry = make_word(db_session)
    assert (
        client.post(f"/api/v1/vocabulary/{entry.id}/recall", json={"typed": "x"}).status_code == 401
    )


def test_a_correct_answer_records_a_review(
    client: TestClient, db_session: Session, headers: dict[str, str], learner: User
) -> None:
    """Gõ lại là MỘT lượt ôn, không phải một luồng song song.

    Nếu nó không ghi `vocabulary_review_log` thì lịch sử sẽ khuyết đúng những
    lần học viên làm nghiêm túc nhất, và sau này không hiệu chỉnh lại được.
    """
    entry = make_word(db_session, "invoice", marker="a")
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall", json={"typed": "Invoice "}, headers=headers
    ).json()

    assert body["verdict"] == "correct"
    assert body["grade"] == GRADE_GOOD
    assert body["interval_days"] == 1
    state = db_session.get(VocabularyReviewState, (learner.id, entry.id))
    assert state is not None and state.repetitions == 1
    assert db_session.query(VocabularyReviewLog).count() == 1


def test_a_wrong_answer_is_graded_as_forgotten_and_reveals_the_word(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    entry = make_word(db_session, "invoice", marker="a")
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall", json={"typed": "warehouse"}, headers=headers
    ).json()

    assert body["verdict"] == "wrong"
    assert body["grade"] == GRADE_FORGOT
    assert body["expected"] == "invoice", "phải trả về đáp án để giao diện đối chiếu"
    # KHÔNG phải lapse: từ này chưa từng được học, và trượt lần đầu gặp không
    # phải là quên. Bản đầu của test này khẳng định `== 1` — nó mã hoá đúng cái
    # bug mà `srs.review` vừa sửa, và chỉ lộ ra khi tôi tự đóng vai người học
    # mới rồi thấy 20/20 thẻ đầu tiên đều bị ghi là "đã quên".
    assert body["lapses"] == 0


def test_claiming_easy_on_a_wrong_answer_does_not_raise_the_grade(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    """Cái bẫy mà thẻ lật tự chấm không chặn được.

    Client hoàn toàn có thể gửi `easy: true` kèm một bài gõ sai. Server chấm
    trước, xét lời khai sau — nên điểm vẫn là 0.
    """
    entry = make_word(db_session, "invoice", marker="a")
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall",
        json={"typed": "nonsense", "easy": True},
        headers=headers,
    ).json()

    assert body["grade"] == GRADE_FORGOT


def test_a_typo_is_graded_between_right_and_wrong(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    entry = make_word(db_session, "warehouse", marker="a")
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall", json={"typed": "warehouze"}, headers=headers
    ).json()

    assert body["verdict"] == "typo"
    assert body["grade"] == GRADE_HARD
    assert body["lapses"] == 0, "gõ nhầm không phải là quên"


def test_recall_on_a_draft_entry_is_404(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    entry = make_word(db_session, "unfinished", status="draft", marker="b")
    response = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall", json={"typed": "unfinished"}, headers=headers
    )
    assert response.status_code == 404


def test_recall_moves_the_word_out_of_new_in_progress(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    """Hai tính năng phải khớp nhau: gõ đúng một từ thì tiến độ phải đổi theo."""
    entry = make_word(db_session, "invoice", marker="a")
    assert client.get("/api/v1/vocabulary-progress", headers=headers).json()["new"] == 1

    client.post(f"/api/v1/vocabulary/{entry.id}/recall", json={"typed": "invoice"}, headers=headers)
    body = client.get("/api/v1/vocabulary-progress", headers=headers).json()
    assert (body["new"], body["learning"]) == (0, 1)


def test_saying_i_dont_know_is_recorded_as_such_not_as_a_wrong_guess(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    """Điểm vẫn 0, nhưng câu chuyện được kể đúng.

    Không có lối này thì cách duy nhất để đi tiếp là bịa một câu trả lời — app
    dạy người ta đoán bừa, và `vocabulary_review_log` đầy những lần "đã thử" mà
    thật ra chưa từng thử.
    """
    entry = make_word(db_session, "invoice", marker="a")
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall",
        json={"typed": "", "give_up": True},
        headers=headers,
    ).json()

    assert body["verdict"] == "unknown"
    assert body["grade"] == GRADE_FORGOT
    assert body["expected"] == "invoice"
    assert body["lapses"] == 0, "chưa học thì chưa quên được"


def test_giving_up_beats_a_lucky_guess(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    """Gõ đúng NHƯNG bấm 'chưa biết' thì vẫn là chưa biết.

    Cờ này do người học chủ động bật, nên nó thắng kết quả chấm — ngược hẳn với
    `easy`, thứ chỉ được xét sau khi server xác nhận là đúng.
    """
    entry = make_word(db_session, "invoice", marker="a")
    body = client.post(
        f"/api/v1/vocabulary/{entry.id}/recall",
        json={"typed": "invoice", "give_up": True},
        headers=headers,
    ).json()
    assert body["verdict"] == "unknown"
    assert body["grade"] == GRADE_FORGOT


def test_a_typing_session_can_exclude_words_never_seen(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> None:
    """`include_new=false` là thứ giữ cho chế độ gõ có thể trả lời được.

    Với người mới thì 20/20 thẻ đều là từ mới; bắt họ tự viết ra một từ chưa
    từng thấy thì không có câu trả lời đúng nào tồn tại.
    """
    make_word(db_session, "invoice", marker="a")
    make_word(db_session, "deadline", marker="b")

    full = client.get("/api/v1/vocabulary-review/session", headers=headers).json()
    assert full["new_count"] == 2

    typing = client.get(
        "/api/v1/vocabulary-review/session?include_new=false", headers=headers
    ).json()
    assert typing["new_count"] == 0
    assert typing["cards"] == []


def test_excluding_new_words_still_returns_words_already_met(
    client: TestClient, db_session: Session, learner: User, headers: dict[str, str]
) -> None:
    entry = make_word(db_session, "invoice", marker="a")
    db_session.add(
        VocabularyReviewState(
            user_id=learner.id,
            entry_id=entry.id,
            interval_days=1,
            repetitions=1,
            due_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db_session.commit()

    body = client.get("/api/v1/vocabulary-review/session?include_new=false", headers=headers).json()
    assert body["due_count"] == 1
    assert body["cards"][0]["headword"] == "invoice"
