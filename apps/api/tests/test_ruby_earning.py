"""Ruby chảy vào từ ba đường học đã có (ADR-011 lát 2).

Thứ đang được ghim ở đây không phải "có cộng điểm không" mà là **ruby trả cho
việc LÀM XONG, không trả cho khối lượng** — nếu một trong ba đường này trượt
xuống mức "mỗi lượt một ít" thì ruby thành XP thứ hai và cả ADR-011 mất nghĩa.
"""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Attempt, DictationItem, Topic, User, VocabularyEntry, VocabularyTopic
from app.models.vocabulary import VocabularyReviewState
from app.services import ruby
from app.services.srs import MASTERED_INTERVAL_DAYS
from tests.test_attempts import published_test, start
from tests.test_dictation_tree import auth as dictation_auth
from tests.test_dictation_tree import build_tree

# --- dictation: xong CẢ BÀI, không phải từng câu ---------------------------


def _user_id(db: Session, email: str) -> uuid.UUID:
    user = db.query(User).filter(User.email == email).one()
    return user.id


def _type(client: TestClient, headers: dict[str, str], item_id: str, text: str) -> dict:
    return client.post(
        f"/api/v1/dictation/{item_id}/attempts",
        json={"submitted_text": text},
        headers=headers,
    ).json()


def test_finishing_a_story_pays_once_and_only_at_the_end(
    client: TestClient, db_session: Session
) -> None:
    """Câu đầu không trả gì; câu cuối trả cả bài; gõ lại không trả thêm.

    Câu cuối là chỗ dễ hỏng im lặng nhất: lượt vừa nộp còn nằm trong giao dịch,
    nên nếu nhánh này đếm sau `commit` thì bài nào cũng dừng ở "còn một câu" và
    không bao giờ trả ruby.
    """
    story = build_tree(db_session, marker="ruby")
    headers = dictation_auth(client, db_session, "ruby-story@example.com")
    user_id = _user_id(db_session, "ruby-story@example.com")
    items = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()["items"]

    assert _type(client, headers, items[0]["id"], "first sentence here")["is_complete"] is True
    assert ruby.balance(db_session, user_id) == 0

    assert _type(client, headers, items[1]["id"], "second sentence here")["is_complete"] is True
    assert ruby.balance(db_session, user_id) == 5

    _type(client, headers, items[1]["id"], "second sentence here")
    assert ruby.balance(db_session, user_id) == 5


def test_a_standalone_sentence_is_not_a_finished_story(
    client: TestClient, db_session: Session
) -> None:
    """Câu lẻ không có gì để "xong". Trả ruby cho nó là trả theo từng lượt nhỏ —
    đúng cái §1 cấm, và đường rẻ nhất để biến ruby thành XP thứ hai."""
    story = build_tree(db_session, marker="lone")
    loose = db_session.query(DictationItem).filter(DictationItem.story_id == story.id).first()
    assert loose is not None
    loose.story_id = None
    loose.position = None
    db_session.commit()

    headers = dictation_auth(client, db_session, "ruby-lone@example.com")
    _type(client, headers, str(loose.id), "first sentence here")
    assert ruby.balance(db_session, _user_id(db_session, "ruby-lone@example.com")) == 0


# --- từ vựng: thuộc TRỌN một chủ đề ----------------------------------------


def _topic_with_two_words(db: Session) -> Topic:
    topic = Topic(slug="ruby-topic", name="Ruby topic", position=0)
    db.add(topic)
    db.flush()
    for headword in ("contract", "invoice"):
        entry = VocabularyEntry(
            headword=headword,
            part_of_speech="noun",
            meaning_en=headword,
            meaning_vi=headword,
            status="published",
        )
        db.add(entry)
        db.flush()
        db.add(VocabularyTopic(entry_id=entry.id, topic_id=topic.id))
    db.commit()
    return topic


def test_mastering_the_last_word_of_a_topic_pays_once(
    client: TestClient, db_session: Session
) -> None:
    """Từ áp chót không trả gì; từ cuối trả cả chủ đề; ôn thêm không trả nữa."""
    topic = _topic_with_two_words(db_session)
    headers = dictation_auth(client, db_session, "ruby-topic@example.com")
    user_id = _user_id(db_session, "ruby-topic@example.com")
    entries = [row.entry_id for row in db_session.query(VocabularyTopic).all()]

    def master(entry_id: uuid.UUID) -> None:
        response = client.post(
            f"/api/v1/vocabulary/{entry_id}/review",
            json={"grade": 6},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    master(entries[0])
    assert ruby.balance(db_session, user_id) == 0

    master(entries[1])
    assert ruby.balance(db_session, user_id) == 15

    master(entries[1])
    assert ruby.balance(db_session, user_id) == 15
    assert topic.slug == "ruby-topic"


def test_a_topic_is_not_mastered_by_a_passing_grade(
    client: TestClient, db_session: Session
) -> None:
    """ "Thuộc" là `interval_days` đã tới ngưỡng, không phải "vừa trả lời đúng".

    Grade 4 là một lượt ôn đạt, và nó KHÔNG được đóng chủ đề — nếu nó đóng thì
    ruby quay về thưởng khối lượng, chỉ là khối lượng đắt hơn một chút.
    """
    _topic_with_two_words(db_session)
    headers = dictation_auth(client, db_session, "ruby-grade@example.com")
    user_id = _user_id(db_session, "ruby-grade@example.com")
    for row in db_session.query(VocabularyTopic).all():
        client.post(
            f"/api/v1/vocabulary/{row.entry_id}/review",
            json={"grade": 4},
            headers=headers,
        )
    assert ruby.balance(db_session, user_id) == 0
    assert (
        db_session.query(VocabularyReviewState).first().interval_days < MASTERED_INTERVAL_DAYS  # type: ignore[union-attr]
    )


# --- lượt làm đề: xong ĐỀ, và đo bằng độ đầy đủ ----------------------------


def _submit(client: TestClient, headers: dict[str, str], slug: str, *, answer: bool) -> None:
    started = start(client, headers, slug)
    assert started.status_code == 201, started.text
    attempt = started.json()
    if answer:
        for question in attempt["questions"]:
            client.patch(
                f"/api/v1/attempts/{attempt['id']}/questions/{question['id']}",
                json={"selected_option_id": question["options"][0]["id"]},
                headers=headers,
            )
    done = client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=headers)
    assert done.status_code == 200, done.text


def test_finishing_a_test_pays_once_per_test_not_per_attempt(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """`source_id` là ĐỀ, nên làm lại đề cũ không in thêm ruby.

    Đây là toàn bộ cơ chế chống cày của nguồn đắt nhất trong bảng, và nó nằm ở
    khoá duy nhất chứ không ở một đoạn `if` ai đó phải nhớ viết.
    """
    admin = auth("admin")
    published_test(client, admin, "ruby-mini")
    learner = auth("learner")
    user_id = _user_id(db_session, "learner@example.com")

    _submit(client, learner, "ruby-mini", answer=True)
    assert ruby.balance(db_session, user_id) == 8  # đề `kind='mini'`

    _submit(client, learner, "ruby-mini", answer=True)
    assert ruby.balance(db_session, user_id) == 8


def test_clicking_through_without_answering_pays_nothing(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Ngưỡng là ĐỘ ĐẦY ĐỦ, không phải điểm số (ADR-011 §2).

    Trả theo điểm là phạt người học yếu vì họ yếu. Trả cho mọi lượt nộp thì bấm
    bừa qua 200 câu trong hai phút cũng lấy đủ. Ngưỡng "đã trả lời ≥ 80%" chặn
    đường thứ hai mà không đụng tới người thứ nhất — và một lượt nộp trắng vẫn
    được ghi nhận bình thường, chỉ là không sinh ruby.
    """
    admin = auth("admin")
    published_test(client, admin, "ruby-blank")
    learner = auth("learner")
    user_id = _user_id(db_session, "learner@example.com")

    _submit(client, learner, "ruby-blank", answer=False)
    assert ruby.balance(db_session, user_id) == 0
    assert db_session.query(Attempt).filter(Attempt.status == "submitted").count() == 1
