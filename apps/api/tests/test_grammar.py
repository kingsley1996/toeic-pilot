"""Admin ngữ pháp (G1 — SPEC-GRAMMAR.md §7).

Trọng tâm là hai cổng hỏng im lặng của §8: publish chủ đề phải đo bằng TRUY VẤN
THẬT vào kho nhãn (một chủ đề 4 câu vẫn chấm được và trông hoàn toàn bình
thường), và câu nháp không được tính vào ngưỡng.
"""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    GrammarAttempt,
    GrammarLesson,
    GrammarLessonCompletion,
    GrammarTopic,
    Question,
    QuestionOption,
    User,
    XpEvent,
)
from app.models.labels import QuestionLabel
from app.services.profile_stats import gather_stats


def a_labeled_question(db: Session, code: str, *, status: str = "published") -> Question:
    question = Question(
        part=5,
        difficulty=2,
        source="original",
        status=status,
        prompt_text="The report ____ by the manager yesterday.",
    )
    question.options = [
        QuestionOption(label="A", content="reviewed", is_correct=False),
        QuestionOption(label="B", content="was reviewed", is_correct=True),
        QuestionOption(label="C", content="reviewing", is_correct=False),
        QuestionOption(label="D", content="review", is_correct=False),
    ]
    db.add(question)
    db.commit()
    db.add(QuestionLabel(question_id=question.id, facet="grammar", code=code))
    db.commit()
    return question


def make_topic(client: TestClient, auth: Callable[[str], dict[str, str]], **over: object) -> dict:
    body = {"code": "GRAMMAR_TENSE", "slug": "thi", "title": "Thì"} | over
    response = client.post("/api/v1/admin/grammar/topics", json=body, headers=auth("editor"))
    assert response.status_code == 201, response.text
    return response.json()


def test_a_code_outside_the_taxonomy_is_refused(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`code` là khoá ngoại LOGIC — kiểm bằng registry, không bằng danh sách chép tay."""
    response = client.post(
        "/api/v1/admin/grammar/topics",
        json={"code": "GRAMMAR_BANANA", "slug": "x", "title": "X"},
        headers=auth("editor"),
    )
    assert response.status_code == 422
    assert "GRAMMAR_BANANA" in response.json()["detail"]


def test_duplicate_code_is_a_conflict(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    make_topic(client, auth)
    response = client.post(
        "/api/v1/admin/grammar/topics",
        json={"code": "GRAMMAR_TENSE", "slug": "thi-2", "title": "Thì 2"},
        headers=auth("editor"),
    )
    assert response.status_code == 409


def test_publish_below_threshold_is_refused_with_the_real_count(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth)
    for _ in range(3):
        a_labeled_question(db_session, "GRAMMAR_TENSE")
    response = client.post(
        f"/api/v1/admin/grammar/topics/{topic['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 409
    assert "3/12" in response.json()["detail"]


def test_draft_questions_do_not_count_toward_the_threshold(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Cổng đo câu PUBLISHED. Câu nháp mang nhãn không phải bài tập ai làm được."""
    topic = make_topic(client, auth)
    for _ in range(12):
        a_labeled_question(db_session, "GRAMMAR_TENSE", status="draft")
    response = client.post(
        f"/api/v1/admin/grammar/topics/{topic['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 409
    assert "0/12" in response.json()["detail"]


def test_publish_at_threshold_succeeds(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth)
    for _ in range(12):
        a_labeled_question(db_session, "GRAMMAR_TENSE")
    response = client.post(
        f"/api/v1/admin/grammar/topics/{topic['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["question_count"] == 12


def test_an_editor_cannot_publish(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth)
    for _ in range(12):
        a_labeled_question(db_session, "GRAMMAR_TENSE")
    response = client.post(
        f"/api/v1/admin/grammar/topics/{topic['id']}/publish", headers=auth("editor")
    )
    assert response.status_code == 403


def test_a_lesson_without_theory_cannot_publish(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth)
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": topic["id"], "slug": "hien-tai-hoan-thanh", "title": "HTHT"},
        headers=auth("editor"),
    ).json()
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 409
    client.patch(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}",
        json={"body": "## Thì hiện tại hoàn thành\n\n`have + V3`"},
        headers=auth("editor"),
    )
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 200


def test_setting_lesson_questions_replaces_and_orders(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth)
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": topic["id"], "slug": "l1", "title": "Bài 1", "body": "x"},
        headers=auth("editor"),
    ).json()
    q1 = a_labeled_question(db_session, "GRAMMAR_TENSE")
    q2 = a_labeled_question(db_session, "GRAMMAR_TENSE")

    response = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/questions",
        json={"question_ids": [str(q2.id), str(q1.id)]},
        headers=auth("editor"),
    )
    assert response.json()["question_count"] == 2

    response = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/questions",
        json={"question_ids": [str(q1.id)]},
        headers=auth("editor"),
    )
    assert response.json()["question_count"] == 1

    response = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/questions",
        json={"question_ids": [str(q1.id), str(q1.id)]},
        headers=auth("editor"),
    )
    assert response.status_code == 422


def test_unattached_lists_labelled_questions_not_in_any_lesson(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """§2: màn soạn phải liệt sẵn "chưa gắn vào bài nào" để việc gắn rẻ nhất."""
    topic = make_topic(client, auth)
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": topic["id"], "slug": "l1", "title": "Bài 1", "body": "x"},
        headers=auth("editor"),
    ).json()
    q1 = a_labeled_question(db_session, "GRAMMAR_TENSE")
    q2 = a_labeled_question(db_session, "GRAMMAR_TENSE")
    a_labeled_question(db_session, "GRAMMAR_VOICE")  # nhãn khác — không liên quan
    client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/questions",
        json={"question_ids": [str(q1.id)]},
        headers=auth("editor"),
    )
    rows = client.get(
        f"/api/v1/admin/grammar/topics/{topic['id']}/unattached-questions",
        headers=auth("editor"),
    ).json()
    assert [r["id"] for r in rows] == [str(q2.id)]


def test_deleting_a_topic_takes_its_lessons_with_it(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth)
    client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": topic["id"], "slug": "l1", "title": "Bài 1", "body": "x"},
        headers=auth("editor"),
    )
    response = client.delete(f"/api/v1/admin/grammar/topics/{topic['id']}", headers=auth("admin"))
    assert response.status_code == 204
    assert db_session.get(GrammarTopic, uuid.UUID(topic["id"])) is None
    assert db_session.scalars(select(GrammarLesson)).all() == []


def test_a_learner_is_refused_everywhere(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    for method, path in [
        ("get", "/api/v1/admin/grammar/topics"),
        ("post", "/api/v1/admin/grammar/topics"),
        ("put", "/api/v1/admin/grammar/lessons/00000000-0000-0000-0000-000000000000/questions"),
    ]:
        assert client.request(method, path, json={}, headers=auth("learner")).status_code == 403


# --- G2: cây learner, mỗi tầng lọc `published` độc lập -----------------------


def make_published_topic_with_lesson(
    client: TestClient,
    db_session: Session,
    auth: Callable[[str], dict[str, str]],
    *,
    topic_status: str,
    lesson_status: str,
    marker: str,
) -> tuple[str, str]:
    """Dựng topic + lesson qua API thật, rồi hạ status bằng DB — đúng cách một
    bài published nằm dưới chủ đề draft xuất hiện trong đời thực."""
    topic = make_topic(client, auth, code="GRAMMAR_TENSE", slug=f"thi-{marker}", title="Thì")
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={
            "topic_id": topic["id"],
            "slug": f"bai-{marker}",
            "title": "Bài 1",
            "body": "## Thì\n\n`have + V3`",
        },
        headers=auth("editor"),
    ).json()
    db_session.get(GrammarTopic, uuid.UUID(topic["id"])).status = topic_status
    db_session.get(GrammarLesson, uuid.UUID(lesson["id"])).status = lesson_status
    db_session.commit()
    return topic["id"], lesson["id"]


def test_a_published_lesson_under_a_draft_topic_is_invisible(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Ca không hiển nhiên mà cây dictation đã học bằng cách hỏng: kiểm cả tầng
    CHA ở endpoint bài học, không chỉ ở danh sách."""
    _, lesson_id = make_published_topic_with_lesson(
        client, db_session, auth, topic_status="draft", lesson_status="published", marker="g1"
    )
    assert client.get(f"/api/v1/grammar-lessons/{lesson_id}").status_code == 404


def test_a_draft_lesson_under_a_published_topic_is_invisible(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic_id, lesson_id = make_published_topic_with_lesson(
        client, db_session, auth, topic_status="published", lesson_status="draft", marker="g2"
    )
    assert client.get(f"/api/v1/grammar-lessons/{lesson_id}").status_code == 404
    body = client.get(f"/api/v1/grammar-topics/{topic_id}").json()
    assert body["lessons"] == []
    assert body["lesson_count"] == 0


def test_the_full_path_opens_when_both_levels_are_published(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic_id, lesson_id = make_published_topic_with_lesson(
        client,
        db_session,
        auth,
        topic_status="published",
        lesson_status="published",
        marker="g3",
    )
    topics = client.get("/api/v1/grammar-topics").json()
    assert [t["id"] for t in topics] == [topic_id]
    assert topics[0]["lesson_count"] == 1
    detail = client.get(f"/api/v1/grammar-lessons/{lesson_id}").json()
    assert detail["body"].startswith("##")
    assert detail["topic_title"] == "Thì"


# --- G3: luyện tập cuối chủ đề ------------------------------------------------


def make_published_topic(db: Session, marker: str) -> GrammarTopic:
    """Topic published cắm thẳng DB — cổng ngưỡng là chuyện G1, đã test ở trên."""
    topic = GrammarTopic(
        code="GRAMMAR_TENSE", slug=f"thi-{marker}", title="Thì", status="published", position=0
    )
    db.add(topic)
    db.commit()
    return topic


def test_attempt_grades_records_and_reveals_answer_only_after_submit(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _, lesson_id, questions = make_practice_lesson(client, db_session, auth, "pr2", n_questions=1)
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    question = questions[0]
    options = {o.label: o for o in question.options}

    rows = client.get(f"/api/v1/grammar-lessons/{lesson_id}").json()["questions"]
    assert "is_correct" not in rows[0]["options"][0]

    result = client.post(
        "/api/v1/grammar-attempts",
        json={"question_id": str(question.id), "option_id": str(options["A"].id)},
        headers=auth("learner"),
    ).json()
    assert result["is_correct"] is False
    assert result["correct_option_id"] == str(options["B"].id)

    # Sai rồi đúng: cả hai lượt đều nằm trong lịch sử, và `completed` bật lên.
    client.post(
        "/api/v1/grammar-attempts",
        json={"question_id": str(question.id), "option_id": str(options["B"].id)},
        headers=auth("learner"),
    )
    rows = client.get(f"/api/v1/grammar-lessons/{lesson_id}", headers=auth("learner")).json()[
        "questions"
    ]
    assert rows[0]["completed"] is True
    assert db_session.query(GrammarAttempt).count() == 2


def test_attempt_requires_an_account(client: TestClient, db_session: Session) -> None:
    question = a_labeled_question(db_session, "GRAMMAR_TENSE")
    option = question.options[0]
    response = client.post(
        "/api/v1/grammar-attempts",
        json={"question_id": str(question.id), "option_id": str(option.id)},
    )
    assert response.status_code == 401


def test_attempt_rejects_an_option_from_another_question(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Chấm theo `option_id` mà không kiểm câu sở hữu là cho phép nộp đáp án câu khác."""
    q1 = a_labeled_question(db_session, "GRAMMAR_TENSE")
    q2 = a_labeled_question(db_session, "GRAMMAR_TENSE")
    response = client.post(
        "/api/v1/grammar-attempts",
        json={"question_id": str(q1.id), "option_id": str(q2.options[0].id)},
        headers=auth("learner"),
    )
    assert response.status_code == 404


# --- tiến độ: Hoàn thành bài + thanh tổng ------------------------------------


def test_complete_is_idempotent_and_shows_up_everywhere(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic_id, lesson_id = make_published_topic_with_lesson(
        client,
        db_session,
        auth,
        topic_status="published",
        lesson_status="published",
        marker="cp1",
    )
    headers = auth("learner")
    for _ in range(2):
        response = client.post(f"/api/v1/grammar-lessons/{lesson_id}/complete", headers=headers)
        assert response.status_code == 204
    assert db_session.query(GrammarLessonCompletion).count() == 1

    topic = client.get(f"/api/v1/grammar-topics/{topic_id}", headers=headers).json()
    assert topic["completed_lesson_count"] == 1
    assert topic["lessons"][0]["completed"] is True

    lesson = client.get(f"/api/v1/grammar-lessons/{lesson_id}", headers=headers).json()
    assert lesson["completed"] is True
    assert lesson["next_lesson"] is None

    listed = client.get("/api/v1/grammar-topics", headers=headers).json()
    assert [t["completed_lesson_count"] for t in listed if t["id"] == topic_id] == [1]


def test_anonymous_sees_zeroes_and_complete_needs_an_account(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic_id, lesson_id = make_published_topic_with_lesson(
        client,
        db_session,
        auth,
        topic_status="published",
        lesson_status="published",
        marker="cp2",
    )
    listed = client.get("/api/v1/grammar-topics").json()
    assert [t["completed_lesson_count"] for t in listed if t["id"] == topic_id] == [0]
    assert client.get(f"/api/v1/grammar-lessons/{lesson_id}").json()["completed"] is False
    assert client.post(f"/api/v1/grammar-lessons/{lesson_id}/complete").status_code == 401


def test_next_lesson_follows_position_not_click_order(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth, code="GRAMMAR_TENSE", slug="thi-nx", title="Thì")
    ids = []
    for position, slug in enumerate(["bai-b", "bai-a"], start=1):
        lesson = client.post(
            "/api/v1/admin/grammar/lessons",
            json={
                "topic_id": topic["id"],
                "slug": slug,
                "title": slug,
                "body": "x",
                "position": position,
            },
            headers=auth("editor"),
        ).json()
        ids.append(lesson["id"])
    for lesson_id in ids:
        client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    db_session.get(GrammarTopic, uuid.UUID(topic["id"])).status = "published"
    db_session.commit()
    first = client.get(f"/api/v1/grammar-lessons/{ids[0]}").json()
    assert first["next_lesson"]["id"] == ids[1]


# --- G4: bài luyện tập là một lesson, tiến độ suy từ lượt làm -----------------


def make_practice_lesson(
    client: TestClient,
    db_session: Session,
    auth: Callable[[str], dict[str, str]],
    marker: str,
    *,
    n_questions: int,
) -> tuple[str, str, list]:
    """Topic published + lesson practice với `n_questions` câu đã gắn."""
    topic = make_published_topic(db_session, marker)
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={
            "topic_id": str(topic.id),
            "slug": f"luyen-{marker}",
            "title": "Luyện tập 1",
            "kind": "practice",
        },
        headers=auth("editor"),
    ).json()
    questions = [a_labeled_question(db_session, "GRAMMAR_NOUN") for _ in range(n_questions)]
    client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/questions",
        json={"question_ids": [str(q.id) for q in questions]},
        headers=auth("editor"),
    )
    return str(topic.id), lesson["id"], questions


def test_practice_lesson_publish_requires_questions(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_published_topic(db_session, "g4a")
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": str(topic.id), "slug": "luyen-k", "title": "Rỗng", "kind": "practice"},
        headers=auth("editor"),
    ).json()
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 409
    assert "chưa có câu PUBLISHED" in response.json()["detail"]


def test_practice_completes_by_button_like_any_lesson(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Practice có nút Hoàn thành như mọi lesson — dấu tay của người học, không
    suy từ số câu đúng. Và bỏ được dấu."""
    _, lesson_id, _ = make_practice_lesson(client, db_session, auth, "g4b", n_questions=2)
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    headers = auth("learner")
    assert (
        client.get(f"/api/v1/grammar-lessons/{lesson_id}", headers=headers).json()["completed"]
        is False
    )
    assert (
        client.post(f"/api/v1/grammar-lessons/{lesson_id}/complete", headers=headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/grammar-lessons/{lesson_id}", headers=headers).json()["completed"]
        is True
    )
    assert (
        client.delete(f"/api/v1/grammar-lessons/{lesson_id}/complete", headers=headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/grammar-lessons/{lesson_id}", headers=headers).json()["completed"]
        is False
    )


def test_practice_lesson_publish_counts_only_published_questions(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Gắn toàn câu nháp mà publish được thì bài mở ra một màn drill rỗng."""
    topic = make_published_topic(db_session, "g4x")
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": str(topic.id), "slug": "luyen-x", "title": "X", "kind": "practice"},
        headers=auth("editor"),
    ).json()
    draft_q = a_labeled_question(db_session, "GRAMMAR_NOUN", status="draft")
    client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/questions",
        json={"question_ids": [str(draft_q.id)]},
        headers=auth("editor"),
    )
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 409


def test_practice_lesson_counts_in_topic_progress(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic_id, lesson_id, questions = make_practice_lesson(
        client, db_session, auth, "g4d", n_questions=1
    )
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    detail = client.get(f"/api/v1/grammar-topics/{topic_id}").json()
    assert detail["lesson_count"] == 1
    assert detail["completed_lesson_count"] == 0
    assert detail["lessons"][0]["kind"] == "practice"

    option = {o.label: o for o in questions[0].options}["B"]
    client.post(
        "/api/v1/grammar-attempts",
        json={"question_id": str(questions[0].id), "option_id": str(option.id)},
        headers=auth("learner"),
    )
    # Làm đúng chưa đủ — tiến độ là dấu tay: phải bấm Hoàn thành.
    assert (
        client.get(f"/api/v1/grammar-topics/{topic_id}", headers=auth("learner")).json()[
            "completed_lesson_count"
        ]
        == 0
    )
    client.post(f"/api/v1/grammar-lessons/{lesson_id}/complete", headers=auth("learner"))
    detail = client.get(f"/api/v1/grammar-topics/{topic_id}", headers=auth("learner")).json()
    assert detail["completed_lesson_count"] == 1
    listed = client.get("/api/v1/grammar-topics", headers=auth("learner")).json()
    assert [t for t in listed if t["id"] == topic_id][0]["completed_lesson_count"] == 1


def test_lesson_order_reassigns_positions(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = make_topic(client, auth, code="GRAMMAR_TENSE", slug="thi-ord", title="Thì")
    ids = []
    for slug in ["a", "b", "c"]:
        lesson = client.post(
            "/api/v1/admin/grammar/lessons",
            json={"topic_id": topic["id"], "slug": slug, "title": slug, "body": "x"},
            headers=auth("editor"),
        ).json()
        ids.append(lesson["id"])
    response = client.put(
        f"/api/v1/admin/grammar/topics/{topic['id']}/lessons/order",
        json={"lesson_ids": [ids[2], ids[0], ids[1]]},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    assert [lesson["position"] for lesson in response.json()] == [1, 2, 3]
    assert [lesson["id"] for lesson in response.json()] == [ids[2], ids[0], ids[1]]

    # Thiếu một bài = client đang dùng ảnh cũ của cây → 404, không âm thầm bỏ.
    response = client.put(
        f"/api/v1/admin/grammar/topics/{topic['id']}/lessons/order",
        json={"lesson_ids": ids[:2]},
        headers=auth("editor"),
    )
    assert response.status_code == 404


def test_question_bank_filters_by_grammar_label(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    a_labeled_question(db_session, "GRAMMAR_TENSE")
    a_labeled_question(db_session, "GRAMMAR_TENSE")
    a_labeled_question(db_session, "GRAMMAR_VOICE")
    rows = client.get(
        "/api/v1/admin/grammar/question-bank?code=GRAMMAR_TENSE", headers=auth("editor")
    ).json()
    assert len(rows) == 2
    assert {r["grammar_code"] for r in rows} == {"GRAMMAR_TENSE"}
    everything = client.get("/api/v1/admin/grammar/question-bank", headers=auth("editor")).json()
    assert len(everything) == 3
    labels = client.get("/api/v1/admin/grammar/labels", headers=auth("editor")).json()
    assert {"code": "GRAMMAR_TENSE", "label_vi": "Thì"} in labels


# --- topic không mã + order chủ đề --------------------------------------------


def test_a_topic_without_code_is_theory_only(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Bài nền tảng ngoài taxonomy: tạo không cần code, publish cần ≥1 bài."""
    topic = client.post(
        "/api/v1/admin/grammar/topics",
        json={"slug": "cau-dieu-kien", "title": "Câu điều kiện"},
        headers=auth("editor"),
    )
    assert topic.status_code == 201
    body = topic.json()
    assert body["code"] is None and body["question_count"] == 0

    response = client.post(
        f"/api/v1/admin/grammar/topics/{body['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 409  # trang trống

    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": body["id"], "slug": "cdk-1", "title": "Loại 0 & 1", "body": "## Nếu"},
        headers=auth("editor"),
    ).json()
    client.post(f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin"))
    response = client.post(
        f"/api/v1/admin/grammar/topics/{body['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 200

    # Không nhãn → không có màn luyện tập theo nhãn, và unattached trả rỗng.
    assert client.get(f"/api/v1/grammar-topics/{body['id']}/practice").status_code == 404
    assert (
        client.get(
            f"/api/v1/admin/grammar/topics/{body['id']}/unattached-questions",
            headers=auth("editor"),
        ).json()
        == []
    )


def test_topic_order_reassigns_positions(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    t1 = make_topic(client, auth, code="GRAMMAR_TENSE", slug="o1", title="Thì")
    t2 = make_topic(client, auth, code="GRAMMAR_VOICE", slug="o2", title="Thể")
    response = client.put(
        "/api/v1/admin/grammar/topics/order",
        json={"topic_ids": [t2["id"], t1["id"]]},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    assert [t["position"] for t in response.json()] == [1, 2]
    # Thiếu một chủ đề = ảnh cũ của cây → 404.
    assert (
        client.put(
            "/api/v1/admin/grammar/topics/order",
            json={"topic_ids": [t1["id"]]},
            headers=auth("editor"),
        ).status_code
        == 404
    )


def test_next_topic_present_on_every_lesson_not_just_the_last(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Sidebar hiện đường kế ở MỌI bài — kiểm trên bài ĐẦU (vẫn còn next_lesson)."""
    t1 = make_topic(client, auth, code="GRAMMAR_TENSE", slug="nt1", title="Thì", position=1)
    t2 = make_topic(client, auth, code="GRAMMAR_VOICE", slug="nt2", title="Thể", position=2)
    lessons1 = []
    for position, slug in enumerate(["a", "b"], start=1):
        lessons1.append(
            client.post(
                "/api/v1/admin/grammar/lessons",
                json={
                    "topic_id": t1["id"],
                    "slug": slug,
                    "title": slug,
                    "body": "x",
                    "position": position,
                },
                headers=auth("editor"),
            ).json()
        )
    l2 = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": t2["id"], "slug": "c", "title": "c", "body": "x", "position": 1},
        headers=auth("editor"),
    ).json()
    for lesson in [*lessons1, l2]:
        client.post(f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin"))
    for topic in (t1, t2):
        db_session.get(GrammarTopic, uuid.UUID(topic["id"])).status = "published"
    db_session.commit()

    first = client.get(f"/api/v1/grammar-lessons/{lessons1[0]['id']}").json()
    assert first["next_lesson"]["id"] == lessons1[1]["id"]  # không phải bài cuối
    assert first["next_topic"]["topic_id"] == t2["id"]
    assert first["next_topic"]["lesson_id"] == l2["id"]


# --- G5: XP, việc hôm nay, chuỗi ngày (SPEC-GRAMMAR §7) -----------------------


def _submit(
    client: TestClient, auth: Callable[[str], dict[str, str]], question: Question, label: str
) -> None:
    option = next(o for o in question.options if o.label == label)
    response = client.post(
        "/api/v1/grammar-attempts",
        json={"question_id": str(question.id), "option_id": str(option.id)},
        headers=auth("learner"),
    )
    assert response.status_code == 200


def _xp_rows(db_session: Session) -> list[XpEvent]:
    return db_session.query(XpEvent).filter_by(source_type="grammar_attempt").all()


def test_a_correct_attempt_awards_xp_once_per_question(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Sai → 0, đúng → 2, đúng LẠI câu đó vẫn → 1 hàng XP.

    `source_id` là uuid tất định từ (người, câu), không phải id lượt: đường nộp
    bài ghi mọi lượt, và khoá bằng id lượt biến "làm lại cho thuộc" thành máy in
    XP — thứ mà dictation không phải lo vì nó không có nút làm lại miễn phí.
    """
    _, lesson_id, questions = make_practice_lesson(client, db_session, auth, "xp1", n_questions=2)
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    q1, q2 = questions

    _submit(client, auth, q1, "A")  # sai
    assert _xp_rows(db_session) == []
    _submit(client, auth, q1, "B")  # đúng
    assert [e.amount for e in _xp_rows(db_session)] == [2]
    _submit(client, auth, q1, "B")  # đúng lại — không thưởng lần hai
    assert len(_xp_rows(db_session)) == 1
    _submit(client, auth, q2, "B")  # câu khác, người khác... cùng người — một hàng mới
    assert len(_xp_rows(db_session)) == 2


def test_grammar_lessons_fill_a_daily_task(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Việc là "học 3 bài", đo bằng bấm hoàn thành — lý thuyết cũng tính."""
    topic_id, lesson_id, _ = make_practice_lesson(client, db_session, auth, "xp2", n_questions=1)
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    lessons = [lesson_id]
    for n in (2, 3):
        body = {
            "topic_id": topic_id,
            "slug": f"bai-{n}",
            "title": f"Bài {n}",
            "body": "x",
            "position": n,
        }
        lessons.append(
            client.post("/api/v1/admin/grammar/lessons", json=body, headers=auth("editor")).json()[
                "id"
            ]
        )
    for lesson in lessons:
        client.post(f"/api/v1/admin/grammar/lessons/{lesson}/publish", headers=auth("admin"))
        client.post(f"/api/v1/grammar-lessons/{lesson}/complete", headers=auth("learner"))

    tasks = client.get("/api/v1/daily-tasks", headers=auth("learner")).json()["tasks"]
    grammar = next(t for t in tasks if t["kind"] == "grammar_lesson_complete")
    assert (grammar["progress"], grammar["done"]) == (3, True)


def test_grammar_task_target_clamps_to_what_is_left(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Còn 2 bài chưa học thì mục tiêu là 2, không phải 3 mãi mãi không với tới.

    Và khi KHÔNG còn bài nào, mục tiêu giữ nguyên 3 — thà việc đóng vĩnh viễn
    còn hơn phần thưởng ăn sẵn mỗi ngày (`or slot.target`, như kẹp từ vựng).
    """
    topic_id, lesson_id, _ = make_practice_lesson(client, db_session, auth, "xp4", n_questions=1)
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    second = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": topic_id, "slug": "bai-2", "title": "Bài 2", "body": "x", "position": 2},
        headers=auth("editor"),
    ).json()["id"]
    client.post(f"/api/v1/admin/grammar/lessons/{second}/publish", headers=auth("admin"))

    def grammar_task() -> dict:
        tasks = client.get("/api/v1/daily-tasks", headers=auth("learner")).json()["tasks"]
        return next(t for t in tasks if t["kind"] == "grammar_lesson_complete")

    assert grammar_task()["target"] == 2  # cả giáo trình còn đúng 2 bài
    client.post(f"/api/v1/grammar-lessons/{lesson_id}/complete", headers=auth("learner"))
    client.post(f"/api/v1/grammar-lessons/{second}/complete", headers=auth("learner"))
    task = grammar_task()
    assert (task["progress"], task["done"]) == (2, True)


def test_a_grammar_only_day_counts_as_studied(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Một câu ngữ pháp duy nhất cũng là một ngày học — chuỗi không phân biệt module."""
    _, lesson_id, questions = make_practice_lesson(client, db_session, auth, "xp3", n_questions=1)
    client.post(f"/api/v1/admin/grammar/lessons/{lesson_id}/publish", headers=auth("admin"))
    _submit(client, auth, questions[0], "B")

    learner = db_session.scalar(select(User).where(User.email == "learner@example.com"))
    assert learner is not None
    stats = gather_stats(db_session, learner.id, "UTC")
    assert stats.current_streak == 1
    assert stats.calendar[-1].grammar == 1
