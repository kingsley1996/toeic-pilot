"""Placement — SPEC-PLACEMENT. Đáng pin: cooldown, cổng đúng người, snapshot
kết quả không tính lại, CEFR trần C1 và không phát minh C2."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
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
    UserProfile,
)
from app.services.placement import CEFR_BANDS, _scaled_range, cefr_of
from app.services.scoring import raw_to_scaled


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
            listening_scaled=250,
            reading_scaled=250,
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

    # Lượt pending (đang dở): trình độ của nó CHƯA tồn tại. Lượt phải thật sự
    # còn dở — một lượt đã nộp mà chưa ai mở phân tích không phải "đang làm dở".
    attempt = _placement_attempt(db_session, _placement_test(db_session), me, status="in_progress")
    db_session.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=me,
            estimator_version="pending",
            listening_raw=0,
            reading_raw=0,
            listening_scaled=0,
            reading_scaled=0,
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
    detail = client.get(f"/api/v1/attempts/{attempt.id}", headers=auth("learner")).json()
    picked = detail["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt.id}/questions/{picked['id']}",
        json={"selected_option_id": picked["options"][0]["id"]},
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
    attempt = _placement_attempt(
        db_session, _placement_test(db_session), me, status="submitted", answer=True
    )
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
    db: Session,
    test: PracticeTest,
    user_id: uuid.UUID | None,
    status: str = "submitted",
    answer: bool = False,
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
        item = AttemptItem(attempt_id=attempt.id, question_id=question.id, position=position)
        if answer:
            correct = next(o for o in question.options if o.is_correct)
            item.selected_option_id = correct.id
            item.is_correct = True
        db.add(item)
    db.commit()
    return attempt


def test_scaled_range_rescales_the_mini_form_onto_the_hundred_question_table(
    db_session: Session,
) -> None:
    """Dải phải QUÂY quanh điểm quy đổi thật, và điều đó chỉ đúng khi số câu
    của đề 84 câu được quy về thang 100 TRƯỚC khi tra bảng.

    Bỏ phép ×100/n đi thì hàm vẫn trả `low <= high` — phép kiểm duy nhất đang
    có — nhưng cả dải tụt xuống một bậc đơn vị: 21/42 tra thẳng ra 85–140
    trong khi điểm thật là 255, tức màn kết quả nói một trình độ khác hẳn.
    """
    seed_scales(db_session)
    db_session.commit()

    center = raw_to_scaled(db_session, "default", "listening", 50)
    low, high = _scaled_range(db_session, "default", "listening", 21, 42)
    assert low < center < high
    # ±~75 điểm ở giữa thang là con số cả §0 của spec dựa vào để chọn 84 câu.
    assert 100 <= high - low <= 200

    # Và ở cực trên, TRUNG ĐIỂM của dải không phải điểm quy đổi: đường cong dốc
    # khác nhau từng khúc và dải bị kẹp ở n, nên trung điểm luôn bị kéo về giữa
    # thang. Đó là lý do `listening_scaled` tồn tại thay vì để giao diện tự
    # lấy trung điểm.
    top = raw_to_scaled(db_session, "default", "listening", 95)
    low, high = _scaled_range(db_session, "default", "listening", 40, 42)
    assert top - (low + high) / 2 > 10


def test_total_scaled_is_the_real_conversion_not_the_midpoint_of_the_band(
    client: TestClient, db_session: Session, auth
) -> None:
    """`total_scaled` là điểm quy đổi tại tỉ lệ đúng thật, cộng hai section.

    Trung điểm của dải là một con số KHÁC: đường cong dốc khác nhau từng khúc
    và dải bị kẹp ở 0 và n, nên ở hai cực nó lệch hơn 20 điểm mỗi section và
    luôn kéo về giữa thang.
    """
    seed_scales(db_session)
    make_placement_test(db_session)
    db_session.commit()
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    attempt = _placement_attempt(db_session, _placement_test(db_session), me, answer=True)

    result = client.post(
        f"/api/v1/placement/attempts/{attempt.id}/analyze", headers=auth("learner")
    ).json()
    assert result["total_scaled"] == result["listening_scaled"] + result["reading_scaled"]
    assert result["total_band"]["low"] == (
        result["listening_band"]["low"] + result["reading_band"]["low"]
    )
    assert result["total_band"]["low"] <= result["total_scaled"] <= result["total_band"]["high"]


def test_start_writes_the_baseline_and_analyze_keeps_it(
    client: TestClient, db_session: Session, auth
) -> None:
    """Cả giá trị của hàng "pending" là để mốc tự khai sống sót qua `analyze`.

    Nếu `analyze` tạo hàng mới thay vì điền vào chỗ, `self_reported_score` mất
    và triệu chứng duy nhất là khối so sánh trên màn kết quả BIẾN MẤT — không
    lỗi, không log. Mục tiêu ôn thi cũng phải chạy về `user_profile`: đó là
    lời khẳng định "một nguồn sự thật" của SPEC §5.
    """
    seed_scales(db_session)
    make_placement_test(db_session)
    db_session.commit()
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    exam_day = (datetime.now(UTC) + timedelta(days=60)).date().isoformat()

    opened = client.post(
        "/api/v1/placement/start",
        json={"self_reported_score": 550, "target_score": 800, "exam_date": exam_day},
        headers=auth("learner"),
    )
    assert opened.status_code == 201
    attempt_id = opened.json()["in_progress_attempt_id"]
    assert attempt_id

    profile = db_session.get(UserProfile, me)
    db_session.refresh(profile)
    assert profile.target_score == 800 and profile.exam_date.isoformat() == exam_day

    detail = client.get(f"/api/v1/attempts/{attempt_id}", headers=auth("learner")).json()
    first = detail["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt_id}/questions/{first['id']}",
        json={"selected_option_id": first["options"][0]["id"]},
        headers=auth("learner"),
    )
    client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=auth("learner"))

    result = client.post(
        f"/api/v1/placement/attempts/{attempt_id}/analyze", headers=auth("learner")
    ).json()
    assert result["self_reported_score"] == 550
    assert result["target_score"] == 800
    # Và cổng prefill lại từ profile, không từ một bản chép thứ hai.
    gate = client.get("/api/v1/placement/gate", headers=auth("learner")).json()
    assert gate["profile_target_score"] == 800 and gate["profile_exam_date"] == exam_day


def test_start_returns_the_running_attempt_and_refuses_a_second_result(
    client: TestClient, db_session: Session, auth
) -> None:
    seed_scales(db_session)
    make_placement_test(db_session)
    db_session.commit()

    first = client.post("/api/v1/placement/start", json={}, headers=auth("learner")).json()
    again = client.post("/api/v1/placement/start", json={}, headers=auth("learner")).json()
    # Lượt đang dở thì trả lại chính nó — hai lượt song song là hai phán quyết
    # cho cùng một tuần.
    assert again["in_progress_attempt_id"] == first["in_progress_attempt_id"]

    attempt_id = first["in_progress_attempt_id"]
    detail = client.get(f"/api/v1/attempts/{attempt_id}", headers=auth("learner")).json()
    picked = detail["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt_id}/questions/{picked['id']}",
        json={"selected_option_id": picked["options"][0]["id"]},
        headers=auth("learner"),
    )
    client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=auth("learner"))
    client.post(f"/api/v1/placement/attempts/{attempt_id}/analyze", headers=auth("learner"))

    blocked = client.post("/api/v1/placement/start", json={}, headers=auth("learner"))
    assert blocked.status_code == 409


def test_a_placement_attempt_with_no_answers_never_becomes_a_verdict(
    client: TestClient, db_session: Session, auth
) -> None:
    """Mở bài rồi đóng tab tới hết giờ KHÔNG được thành trình độ A1.

    `_finalise` chấm ô trống là sai — đúng cho đề thi — nên một lượt như thế ra
    0 câu đúng, và ghi nó lại là gán cho người ta một trình độ họ chưa từng làm
    bài để có, rồi khoá cổng bảy ngày vì nó.
    """
    seed_scales(db_session)
    make_placement_test(db_session)
    db_session.commit()

    opened = client.post("/api/v1/placement/start", json={}, headers=auth("learner")).json()
    attempt_id = uuid.UUID(opened["in_progress_attempt_id"])
    attempt = db_session.get(Attempt, attempt_id)
    attempt.status = "expired"
    attempt.submitted_at = datetime.now(UTC)
    db_session.commit()

    refused = client.post(
        f"/api/v1/placement/attempts/{attempt_id}/analyze", headers=auth("learner")
    )
    assert refused.status_code == 409

    # Và nó không tiêu mất cooldown: lượt bỏ dở được dọn ở lần bấm tiếp theo.
    again = client.post("/api/v1/placement/start", json={}, headers=auth("learner"))
    assert again.status_code == 201
    assert again.json()["in_progress_attempt_id"] != str(attempt_id)
    assert db_session.get(PlacementResult, attempt_id) is None


def test_the_placement_form_cannot_be_opened_through_the_attempt_machine(
    client: TestClient, db_session: Session, auth
) -> None:
    """Vào thẳng `POST /attempts` là đi vòng qua cooldown VÀ qua hàng "pending"
    giữ mốc tự khai; lượt sinh ra không nằm trong cổng nhưng vẫn chấm được."""
    test = make_placement_test(db_session)
    db_session.commit()

    denied = client.post(
        "/api/v1/attempts",
        json={"test_slug": test.slug, "review_mode": "exam", "parts": []},
        headers=auth("learner"),
    )
    assert denied.status_code == 409


def test_cefr_refuses_a_score_that_falls_between_two_bands() -> None:
    """Khe giữa hai băng phải NỔ, không rơi âm thầm về A1.

    Hôm nay không có khe nào vì mọi điểm quy đổi là bội của 5 và các băng liền
    nhau ở bội 5. Một bảng quy đổi tương lai trả 452 thì đó là người đọc gần
    B2, và trả về "A1" cho họ là nói dối có số liệu.
    """
    with pytest.raises(ValueError):
        cefr_of("reading", 452)
