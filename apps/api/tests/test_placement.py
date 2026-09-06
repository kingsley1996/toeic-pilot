"""Placement — SPEC-PLACEMENT. Đáng pin: cooldown, cổng đúng người, snapshot
kết quả không tính lại, CEFR trần C1 và không phát minh C2."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.seed_scores import seed_scales
from app.models import (
    Attempt,
    AttemptItem,
    PlacementResult,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionOption,
)
from app.services.placement import CEFR_BANDS, cefr_of


def make_placement_test(db: Session) -> PracticeTest:
    test = PracticeTest(
        slug=f"place-{uuid.uuid4().hex[:8]}",
        title="Placement",
        kind="mini",
        status="published",
        is_placement=True,
        time_limit_seconds=3000,
    )
    db.add(test)
    # Hai câu đại diện hai section — analyze cần cả Nghe lẫn Đọc (N4).
    for part in (1, 5):
        question = Question(
            part=part,
            difficulty=2,
            source="original",
            status="published",
            prompt_text=f"Pick {part}.",
        )
        question.options = [
            QuestionOption(label="A", content="a", is_correct=False),
            QuestionOption(label="B", content="b", is_correct=True),
        ]
        db.add(question)
        db.flush()
        db.add(
            PracticeTestQuestion(
                test_id=test.id, question_id=question.id, position=part, number=part
            )
        )
    return test


def test_cefr_bands_match_ets_table_and_c1_is_ceiling() -> None:
    assert cefr_of("listening", 495) == "C1"
    assert cefr_of("listening", 460) == "B2"
    assert cefr_of("reading", 275) == "B1"
    assert cefr_of("reading", 100) == "A1"
    # Điểm 0 dồn về băng thấp nhất — không có "A0".
    assert cefr_of("listening", 0) == "A1"
    # Bảng ETS không có C2 cho TOEIC L&R — không phát minh ra băng.
    assert "C2" not in CEFR_BANDS


def test_gate_and_cooldown(client: TestClient, db_session: Session, auth) -> None:
    make_placement_test(db_session)
    db_session.commit()

    gate = client.get("/api/v1/placement/gate", headers=auth("learner")).json()
    assert gate["can_start"] is True and gate["latest_attempt_id"] is None

    me = client.get("/api/v1/auth/me", headers=auth("learner")).json()
    attempt = _placement_attempt(db_session, _placement_test(db_session), uuid.UUID(me["id"]))
    db_session.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=uuid.UUID(me["id"]),
            estimator_version="v1",
            listening_raw=10,
            reading_raw=10,
            listening_low=0,
            listening_high=100,
            reading_low=0,
            reading_high=100,
            cefr_listening="A2",
            cefr_reading="A2",
            cefr_overall="A2",
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    gate = client.get("/api/v1/placement/gate", headers=auth("learner")).json()
    assert gate["can_start"] is False and gate["next_available_at"] is not None
    assert gate["latest_attempt_id"]


def test_gate_carries_latest_result_and_hides_pending(
    client: TestClient, db_session: Session, auth
) -> None:
    seed_scales(db_session)
    make_placement_test(db_session)
    db_session.commit()
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])

    # Lượt pending (đang dở): trình độ của nó CHƯA tồn tại.
    attempt = _placement_attempt(db_session, _placement_test(db_session), me)
    db_session.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=me,
            estimator_version="pending",
            listening_raw=0,
            reading_raw=0,
            listening_low=0,
            listening_high=0,
            reading_low=0,
            reading_high=0,
            cefr_listening="A1",
            cefr_reading="A1",
            cefr_overall="A1",
        )
    )
    db_session.commit()
    gate = client.get("/api/v1/placement/gate", headers=auth("learner")).json()
    assert gate["in_progress_attempt_id"] is not None and gate["latest_cefr_overall"] is None

    # Nộp + phân tích: kết quả hiện lên, lượt dở biến mất.
    client.patch(
        f"/api/v1/attempts/{attempt.id}/questions/"
        f"{client.get(f'/api/v1/attempts/{attempt.id}', headers=auth('learner')).json()['questions'][0]['id']}",
        json={"selected_option_id": None},
        headers=auth("learner"),
    )
    client.post(f"/api/v1/attempts/{attempt.id}/submit", headers=auth("learner"))
    result = client.post(
        f"/api/v1/placement/attempts/{attempt.id}/analyze", headers=auth("learner")
    ).json()
    gate = client.get("/api/v1/placement/gate", headers=auth("learner")).json()
    assert gate["in_progress_attempt_id"] is None
    assert gate["latest_cefr_overall"] == result["cefr_overall"]
    assert gate["latest_total_low"] <= gate["latest_total_high"]


def test_analyze_requires_own_finished_placement_attempt(
    client: TestClient, db_session: Session, auth
) -> None:
    seed_scales(db_session)
    make_placement_test(db_session)
    db_session.commit()
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    attempt = _placement_attempt(db_session, _placement_test(db_session), me, status="submitted")
    db_session.commit()

    # Cổng đúng người: 404 cho người khác, không phải 403.
    denied = client.post(f"/api/v1/placement/attempts/{attempt.id}/analyze", headers=auth("admin"))
    assert denied.status_code == 404

    result = client.post(
        f"/api/v1/placement/attempts/{attempt.id}/analyze", headers=auth("learner")
    ).json()
    assert result["estimator_version"] == "v1"
    assert result["listening_band"]["low"] <= result["listening_band"]["high"]
    assert result["cefr_overall"] in ("A1", "A2", "B1", "B2", "C1")

    # Gọi lại cùng lượt: phán quyết không đổi, không chấm lại.
    again = client.post(
        f"/api/v1/placement/attempts/{attempt.id}/analyze", headers=auth("learner")
    ).json()
    assert again["created_at"] == result["created_at"]


def _placement_test(db: Session) -> PracticeTest:
    return db.scalar(select(PracticeTest).where(PracticeTest.is_placement.is_(True)))


def _placement_attempt(
    db: Session, test: PracticeTest, user_id: uuid.UUID | None, status: str = "submitted"
):
    attempt = Attempt(
        user_id=user_id,
        test_id=test.id,
        scope="full",
        review_mode="exam",
        status=status,
        elapsed_seconds=0,
        resumed_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC) if status == "submitted" else None,
    )
    db.add(attempt)
    db.flush()
    questions = db.execute(
        select(Question, PracticeTestQuestion.position)
        .join(PracticeTestQuestion, PracticeTestQuestion.question_id == Question.id)
        .where(PracticeTestQuestion.test_id == test.id)
        .order_by(PracticeTestQuestion.position)
    ).all()
    for position, (question, _pos) in enumerate(questions, start=1):
        db.add(AttemptItem(attempt_id=attempt.id, question_id=question.id, position=position))
    db.commit()
    return attempt
