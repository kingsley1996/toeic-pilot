"""Dashboard phân tích chất lượng đề: khóa của một đề + so sánh liên đề.

Dữ liệu dựng tay đủ nhỏ để đọc: 2 đề, vài câu mỗi part, đáp án đúng dồn về A
ở đề thứ hai để cờ ANSWER_SKEW có cái để bắt.
"""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    AttemptItem,
    PracticeTestQuestion,
    QuestionLabel,
    User,
)
from tests.test_domain_model import make_question, make_test


def _link(db: Session, test, question, position: int, number: int) -> None:
    db.add(
        PracticeTestQuestion(
            test_id=test.id, question_id=question.id, position=position, number=number
        )
    )


def _seed(db: Session, slug: str, *, skew_a: bool = False):
    test = make_test(db)
    test.slug = slug
    test.title = slug
    pos = 1
    p5_questions = []
    # P5: 6 câu, đáp án đúng A B C D A B xen kẽ — hoặc dồn hết về A.
    for i in range(6):
        q = make_question(db, part=5, correct=1)
        db.flush()
        q.explanation = f"giải thích {i}"
        _link(db, test, q, pos, 100 + pos)
        pos += 1
        p5_questions.append((q, "A" if skew_a else "ABCD"[i % 4]))
    # Tắt hết trước rồi mới bật đáp án đúng: SQLite kiểm tra partial unique
    # index theo từng hàng trong UPDATE nhiều hàng, bật B=True khi A còn True
    # là nổ ngay dù trạng thái cuối vẫn hợp lệ.
    for q, _ in p5_questions:
        for opt in q.options:
            opt.is_correct = False
    db.flush()
    for q, want in p5_questions:
        for opt in q.options:
            opt.is_correct = opt.label == want
    db.flush()
    # P2: 2 câu không lời giải, không nhãn — để cờ EXPLANATION_GAP/LABEL_GAP bắt.
    for _ in range(2):
        q = make_question(db, part=2, correct=1)
        db.flush()
        q.explanation = None
        _link(db, test, q, pos, pos)
        pos += 1
    db.commit()
    return test


def _label(db: Session, question, code: str, *, reviewed: bool = True) -> None:
    db.add(
        QuestionLabel(
            question_id=question.id,
            facet="question_type",
            code=code,
            proposed_code=code,
            reviewed_at=datetime.now(UTC) if reviewed else None,
        )
    )
    db.commit()


def test_list_and_key(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    test = _seed(db_session, "tp-analytics-a")
    from sqlalchemy import select

    questions = db_session.scalars(
        select(PracticeTestQuestion.question_id).where(PracticeTestQuestion.test_id == test.id)
    ).all()
    from app.models import Question

    first = db_session.get(Question, questions[0])
    assert first is not None
    _label(db_session, first, "PART_5_GRAMMAR")

    rows = client.get("/api/v1/admin/analytics/tests", headers=auth("editor"))
    assert rows.status_code == 200
    row = next(r for r in rows.json() if r["slug"] == "tp-analytics-a")
    assert row["total"] == 8

    key = client.get("/api/v1/admin/analytics/tests/tp-analytics-a", headers=auth("editor"))
    assert key.status_code == 200
    body = key.json()
    assert body["total"] == 8
    p5 = next(p for p in body["parts"] if p["part"] == 5)
    assert p5["count"] == 6
    assert p5["answers"] == {"A": 2, "B": 2, "C": 1, "D": 1}
    assert p5["explained"] == 6
    p2 = next(p for p in body["parts"] if p["part"] == 2)
    assert p2["explained"] == 0
    qt = next(f for f in body["facets"] if f["facet"] == "question_type")
    codes = {c["code"]: c["count"] for c in qt["codes"]}
    assert codes == {"PART_5_GRAMMAR": 1}
    assert body["review"]["reviewed"] == 1
    assert body["performance"]["attempts"] == 0
    assert body["performance"]["avg_p"] is None
    flag_codes = {f["code"] for f in body["flags"]}
    assert {"EXPLANATION_GAP", "LABEL_GAP", "AUDIO_GAP"} <= flag_codes


def test_skew_flag_and_pvalue(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    from sqlalchemy import select

    test = _seed(db_session, "tp-analytics-b", skew_a=True)
    qids = db_session.scalars(
        select(PracticeTestQuestion.question_id).where(PracticeTestQuestion.test_id == test.id)
    ).all()
    learner = User(email="learner-a@example.com", hashed_password="x", role="learner")
    db_session.add(learner)
    db_session.flush()
    attempt = Attempt(
        user_id=learner.id,
        test_id=test.id,
        scope="full",
        status="submitted",
        submitted_at=datetime.now(UTC),
    )
    db_session.add(attempt)
    db_session.flush()
    for i, qid in enumerate(qids):
        db_session.add(
            AttemptItem(
                attempt_id=attempt.id,
                question_id=qid,
                position=i + 1,
                is_correct=(i % 2 == 0),
            )
        )
    db_session.commit()

    body = client.get("/api/v1/admin/analytics/tests/tp-analytics-b", headers=auth("admin")).json()
    assert any(f["code"] == "ANSWER_SKEW" and "A" in f["message"] for f in body["flags"]), body[
        "flags"
    ]
    assert body["performance"]["attempts"] == 1
    assert body["performance"]["avg_p"] == pytest.approx(0.5)


def test_blueprint_hard_read_from_disk(
    client: TestClient,
    db_session: Session,
    auth: Callable[[str], dict[str, str]],
    tmp_path,
    monkeypatch,
) -> None:
    """Ô `hard` trong blueprint phải hiện lên dashboard, không lặng lẽ None.

    Hồi quy cho lỗi đường dẫn sai một cấp (`parents[2]` thay vì `parents[3]`)
    khiến mọi part báo `hard_planned: None` dù file có thật.
    """
    import json

    import app.api.routes.admin_analytics as analytics

    _seed(db_session, "tp-bp-hard")
    slug_dir = tmp_path / "tp-bp-hard"
    slug_dir.mkdir()
    (slug_dir / "blueprint.json").write_text(
        json.dumps(
            {
                "slug": "tp-bp-hard",
                "parts": [
                    {"part": 5, "slots": [{"id": "p5-01", "hard": 0}]},
                    {"part": 2, "slots": [{"id": "p2-01", "hard": 1}]},
                ],
            }
        )
    )
    monkeypatch.setattr(analytics, "_GENERATED_DIR", tmp_path)
    body = client.get("/api/v1/admin/analytics/tests/tp-bp-hard", headers=auth("editor")).json()
    by_part = {p["part"]: p["hard_planned"] for p in body["parts"]}
    assert by_part == {5: 0, 2: 1}


def test_compare_and_auth(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _seed(db_session, "tp-analytics-c1")
    _seed(db_session, "tp-analytics-c2")
    headers = auth("editor")
    out = client.get(
        "/api/v1/admin/analytics/compare?slugs=tp-analytics-c1,tp-analytics-c2",
        headers=headers,
    )
    assert out.status_code == 200
    assert [t["slug"] for t in out.json()["tests"]] == [
        "tp-analytics-c1",
        "tp-analytics-c2",
    ]
    nope = client.get("/api/v1/admin/analytics/compare?slugs=nope", headers=headers)
    assert nope.status_code == 404
    assert client.get("/api/v1/admin/analytics/compare?slugs=", headers=headers).status_code == 400
    assert client.get("/api/v1/admin/analytics/tests").status_code == 401
    assert (
        client.get(
            "/api/v1/admin/analytics/tests/tp-analytics-c1", headers=auth("learner")
        ).status_code
        == 403
    )
