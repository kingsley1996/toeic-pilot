"""Phiên luyện theo part — `practice_parts.py`.

Ba thứ đáng pin, cả ba đều là kiểu hỏng im lặng:

- Đếm và chốt câu dùng CÙNG bộ lọc hai tầng (câu published + set published);
  hub hứa 12 câu mà phiên chỉ giao 8 là lệch không ai báo.
- Đáp án không được nằm trong payload của câu CHƯA trả lời — kể cả trong bản
  xem lại, nơi câu đã trả lời mới được lộ.
- Câu của phiên là SNAPSHOT: tạo xong rồi xoá nhãn / thêm câu mới vào kho cũng
  không đổi được danh sách của phiên đã có.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    GrammarTopic,
    PartTactics,
    Question,
    QuestionLabel,
    QuestionOption,
    QuestionSet,
)


def a_question(
    db: Session,
    part: int,
    *,
    status: str = "published",
    label: str | None = None,
    stimulus: QuestionSet | None = None,
) -> Question:
    question = Question(
        part=part,
        difficulty=2,
        source="original",
        status=status,
        prompt_text=f"The report ____ number {uuid.uuid4().hex[:6]}.",
        set_id=stimulus.id if stimulus else None,
        explanation="Was reviewed — past passive.",
    )
    question.options = [
        QuestionOption(label="A", content="reviewed", is_correct=False),
        QuestionOption(label="B", content="was reviewed", is_correct=True),
    ]
    db.add(question)
    db.commit()
    if label is not None:
        db.add(QuestionLabel(question_id=question.id, facet="grammar", code=label))
        db.commit()
    return question


def a_set(db: Session, part: int, status: str = "published") -> QuestionSet:
    stimulus = QuestionSet(part=part, title=f"Ngữ liệu {part}", status=status, passage="Read me.")
    db.add(stimulus)
    db.commit()
    return stimulus


def create_session(client: TestClient, auth, part: int, **body: object) -> dict:
    response = client.post(
        f"/api/v1/practice/parts/{part}/sessions",
        json=body,
        headers=auth("learner"),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_list_parts_counts_only_open_questions(client: TestClient, db_session: Session) -> None:
    a_question(db_session, 5)
    a_question(db_session, 5, status="draft")
    draft_set = a_set(db_session, 7, status="draft")
    a_question(db_session, 7, stimulus=draft_set)

    parts = {p["part"]: p for p in client.get("/api/v1/practice/parts").json()}
    assert len(parts) == 7
    assert parts[5]["question_count"] == 1
    assert parts[7]["question_count"] == 0  # published nhưng dưới set nháp


def test_labels_carry_vi_titles_and_grammar_slugs(client: TestClient, db_session: Session) -> None:
    db_session.add(
        GrammarTopic(code="GRAMMAR_TENSE", slug="thi", title="Thì", status="published", position=1)
    )
    db_session.commit()
    a_question(db_session, 5, label="GRAMMAR_TENSE")

    labels = client.get("/api/v1/practice/parts").json()[4]["labels"]
    tense = next(row for row in labels if row["code"] == "GRAMMAR_TENSE")
    assert tense["count"] == 1
    assert tense["grammar_topic_slug"] == "thi"


def test_tactics_404_until_seeded(client: TestClient, db_session: Session) -> None:
    assert client.get("/api/v1/practice/parts/3/tactics").status_code == 404
    db_session.add(PartTactics(part=3, body="## Đọc trước đáp án"))
    db_session.commit()
    body = client.get("/api/v1/practice/parts/3/tactics").json()["body"]
    assert body.startswith("##")


def test_session_snapshots_questions_and_hides_answers(
    client: TestClient, db_session: Session, auth
) -> None:
    for _ in range(3):
        a_question(db_session, 5)
    sess = create_session(client, auth, 5)
    raw = client.get(f"/api/v1/practice/parts/sessions/{sess['id']}", headers=auth("learner")).text
    assert '"is_correct":true' not in raw and '"is_correct":false' not in raw
    assert '"correct_option_id":"' not in raw  # chưa câu nào trả lời → không gì được lộ

    # Câu của phiên là SNAPSHOT: kho lớn thêm không đổi danh sách đã chốt.
    a_question(db_session, 5)
    again = client.get(
        f"/api/v1/practice/parts/sessions/{sess['id']}", headers=auth("learner")
    ).json()
    assert len(again["items"]) == 3


def test_session_answer_flow(client: TestClient, db_session: Session, auth) -> None:
    q1 = a_question(db_session, 5, label="GRAMMAR_TENSE")
    a_question(db_session, 5)
    sess = create_session(client, auth, 5)
    sid = sess["id"]
    assert len(sess["items"]) == 2

    # Thứ tự câu là random — chọn đúng item của q1.
    item = next(i for i in sess["items"] if i["question"]["id"] == str(q1.id))
    wrong, right = item["question"]["options"]
    result = client.post(
        f"/api/v1/practice/parts/sessions/{sid}/answers",
        json={"question_id": item["question"]["id"], "option_id": wrong["id"]},
        headers=auth("learner"),
    ).json()
    assert result["is_correct"] is False
    assert result["correct_option_id"] == right["id"]
    assert result["explanation"] == "Was reviewed — past passive."
    assert [lab["code"] for lab in result["labels"]] == ["GRAMMAR_TENSE"]

    # Lần hai bị chặn — phiên là lịch sử, không phải bảng tính lại.
    again = client.post(
        f"/api/v1/practice/parts/sessions/{sid}/answers",
        json={"question_id": item["question"]["id"], "option_id": right["id"]},
        headers=auth("learner"),
    )
    assert again.status_code == 409

    # Câu ngoài phiên → 404.
    stray = client.post(
        f"/api/v1/practice/parts/sessions/{sid}/answers",
        json={"question_id": str(uuid.uuid4()), "option_id": str(right["id"])},
        headers=auth("learner"),
    )
    assert stray.status_code == 404

    # Trả lời nốt câu còn lại → phiên tự chốt.
    other = next(i for i in sess["items"] if i is not item)
    last = client.post(
        f"/api/v1/practice/parts/sessions/{sid}/answers",
        json={
            "question_id": other["question"]["id"],
            "option_id": other["question"]["options"][1]["id"],
        },
        headers=auth("learner"),
    )
    assert last.status_code == 200, last.text
    final = client.get(f"/api/v1/practice/parts/sessions/{sid}", headers=auth("learner")).json()
    assert final["finished_at"] is not None, [i["is_correct"] for i in final["items"]]
    # Xem lại: câu đã trả lời được lộ đáp án + giải thích.
    answered_items = [i for i in final["items"] if i["is_correct"] is not None]
    assert len(answered_items) == 2
    assert all(i["correct_option_id"] and i["explanation"] for i in answered_items)


def test_session_list_and_ownership(client: TestClient, db_session: Session, auth) -> None:
    a_question(db_session, 2)
    sess = create_session(client, auth, 2)

    rows = client.get("/api/v1/practice/parts/sessions", headers=auth("learner")).json()
    assert [r["id"] for r in rows] == [sess["id"]]
    assert rows[0]["total"] == 1 and rows[0]["answered"] == 0

    # Người khác không thấy, không mở được — 404, không phải 403.
    other = client.get("/api/v1/practice/parts/sessions", headers=auth("admin")).json()
    assert other == []
    denied = client.get(f"/api/v1/practice/parts/sessions/{sess['id']}", headers=auth("admin"))
    assert denied.status_code == 404


def test_session_label_filter_and_empty_bank(client: TestClient, db_session: Session, auth) -> None:
    a_question(db_session, 5, label="GRAMMAR_TENSE")
    a_question(db_session, 5, label="GRAMMAR_VOICE")

    sess = create_session(client, auth, 5, labels=["GRAMMAR_TENSE"])
    assert len(sess["items"]) == 1
    assert len(sess["label_titles"]) == 1

    # Nhiều nhãn = HỢP của câu — khuôn checkbox khu luyện thi.
    both = create_session(client, auth, 5, labels=["GRAMMAR_TENSE", "GRAMMAR_VOICE"])
    assert len(both["items"]) == 2

    empty = client.post(
        "/api/v1/practice/parts/5/sessions",
        json={"labels": ["GRAMMAR_COMPARISON"]},
        headers=auth("learner"),
    )
    assert empty.status_code == 409


def test_null_set_questions_survive_the_set_filter(
    client: TestClient, db_session: Session, auth
) -> None:
    """Part 1/2/5 có `set_id` NULL — lọc set kiểu `IN` sẽ nuốt chúng."""
    a_question(db_session, 2)
    sess = create_session(client, auth, 2)
    assert len(sess["items"]) == 1


def test_passage_travels_once_per_session_set(
    client: TestClient, db_session: Session, auth
) -> None:
    stimulus = a_set(db_session, 7)
    a_question(db_session, 7, stimulus=stimulus)
    a_question(db_session, 7, stimulus=stimulus)

    sess = create_session(client, auth, 7)
    assert sum(1 for i in sess["items"] if i["question"]["passages"]) == 1


def test_session_takes_whole_bank_and_timer_expires(
    client: TestClient, db_session: Session, auth
) -> None:
    """Đồng hồ là MÁY CHỦ tính từ `created_at` — hết giờ thì đọc/ghi đều chốt."""
    from datetime import UTC, datetime, timedelta

    from app.models import PartSession

    for _ in range(4):
        a_question(db_session, 5)
    sess = create_session(client, auth, 5, time_limit_minutes=5)
    assert len(sess["items"]) == 4  # toàn bộ kho, không cắt
    assert sess["remaining_seconds"] is not None and sess["remaining_seconds"] > 240

    # Xoay đồng hồ về quá khứ qua DB — cùng đường `attempt` từng được test.
    row = db_session.get(PartSession, uuid.UUID(sess["id"]))
    row.created_at = datetime.now(UTC) - timedelta(minutes=6)
    db_session.commit()

    detail = client.get(
        f"/api/v1/practice/parts/sessions/{sess['id']}", headers=auth("learner")
    ).json()
    assert detail["expired"] is True and detail["finished_at"] is not None
    assert detail["remaining_seconds"] is None

    refused = client.post(
        f"/api/v1/practice/parts/sessions/{sess['id']}/answers",
        json={
            "question_id": sess["items"][0]["question"]["id"],
            "option_id": sess["items"][0]["question"]["options"][0]["id"],
        },
        headers=auth("learner"),
    )
    assert refused.status_code == 409


def test_listening_text_revealed_only_after_answering(
    client: TestClient, db_session: Session, auth
) -> None:
    """Part 1/2 không in chữ lúc làm — lời đọc và lời thoại chỉ về SAU lần chọn."""
    question = Question(
        part=2,
        difficulty=2,
        source="original",
        status="published",
        audio_script=[{"voice": "uk_female_1", "text": "The meeting starts at nine."}],
    )
    question.options = [
        QuestionOption(label="A", content=None, spoken_text="Yes, it does.", is_correct=False),
        QuestionOption(label="B", content=None, spoken_text="No, it does not.", is_correct=True),
    ]
    db_session.add(question)
    db_session.commit()

    sess = create_session(client, auth, 2)
    raw = client.get(f"/api/v1/practice/parts/sessions/{sess['id']}", headers=auth("learner")).text
    assert "meeting starts at nine" not in raw and "Yes, it does" not in raw

    item = sess["items"][0]
    result = client.post(
        f"/api/v1/practice/parts/sessions/{sess['id']}/answers",
        json={
            "question_id": item["question"]["id"],
            "option_id": item["question"]["options"][0]["id"],
        },
        headers=auth("learner"),
    ).json()
    assert result["spoken"][item["question"]["options"][0]["id"]] == "Yes, it does."
    assert result["transcript"] == [{"speaker": "Woman", "text": "The meeting starts at nine."}]

    again = client.get(
        f"/api/v1/practice/parts/sessions/{sess['id']}", headers=auth("learner")
    ).json()
    assert again["items"][0]["question"]["transcript"]
    assert again["items"][0]["question"]["options"][0]["spoken_text"] == "Yes, it does."
