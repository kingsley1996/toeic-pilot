"""Kế hoạch học — planner V1 rule-based (SPEC-PLACEMENT §5–§6).

Đáng pin: kế hoạch hiện hành DUY NHẤT (hai generate kế nhau hạ kế hoạch cũ),
tiến độ SUY từ bản ghi học thật chứ không có cột tick, ngân sách mục co theo
exam_date, và N4 — kỹ năng không có nội dung thì không thành mục.
"""

import time
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.seed_scores import seed_scales
from app.models import (
    Attempt,
    AttemptItem,
    GrammarLesson,
    GrammarTopic,
    PlacementResult,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionLabel,
    QuestionOption,
    StudyPlan,
    UserProfile,
)


def make_question(db: Session, part: int, answer_a_correct: bool) -> Question:
    question = Question(
        part=part,
        difficulty=2,
        source="original",
        status="published",
        prompt_text=f"Q{part}.",
    )
    question.options = [
        QuestionOption(label="A", content="a", is_correct=answer_a_correct),
        QuestionOption(label="B", content="b", is_correct=not answer_a_correct),
    ]
    db.add(question)
    db.flush()
    return question


def build_world(db: Session, learner_id: uuid.UUID) -> Attempt:
    """Câu part 1 trả lời ĐÚNG, BA câu part 5 trả lời SAI — đủ mẫu số 3 câu
    để `MIN_SKILL_SAMPLE` xếp part 5 và nhãn grammar của nó vào nhóm yếu."""
    seed_scales(db)
    test = PracticeTest(
        slug=f"place-{uuid.uuid4().hex[:8]}",
        title="Placement",
        kind="placement",
        status="published",
        is_placement=True,
        time_limit_seconds=3000,
    )
    db.add(test)
    db.flush()
    ok = make_question(db, 1, answer_a_correct=True)
    weak_qs = [make_question(db, 5, answer_a_correct=False) for _ in range(3)]
    db.add(PracticeTestQuestion(test_id=test.id, question_id=ok.id, position=1, number=1))
    for position, weak in enumerate(weak_qs, start=2):
        db.add(
            PracticeTestQuestion(
                test_id=test.id, question_id=weak.id, position=position, number=position
            )
        )

    attempt = Attempt(
        user_id=learner_id,
        test_id=test.id,
        scope="full",
        review_mode="exam",
        status="submitted",
        elapsed_seconds=0,
        resumed_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC),
    )
    db.add(attempt)
    db.flush()
    db.add(AttemptItem(attempt_id=attempt.id, question_id=ok.id, position=1, is_correct=True))
    for position, weak in enumerate(weak_qs, start=2):
        db.add(
            AttemptItem(
                attempt_id=attempt.id, question_id=weak.id, position=position, is_correct=False
            )
        )
    db.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=learner_id,
            estimator_version="v1",
            listening_raw=1,
            reading_raw=0,
            listening_scaled=60,
            reading_scaled=30,
            listening_low=0,
            listening_high=100,
            reading_low=0,
            reading_high=50,
            cefr_listening="A1",
            cefr_reading="A1",
            cefr_overall="A1",
        )
    )
    db.commit()
    return attempt


def make_weak_topic_with_lesson(db: Session) -> GrammarTopic:
    """Chủ đề + bài học published — giả định bám mã nhãn nào đó của câu yếu."""
    topic = GrammarTopic(
        code=None,
        slug=f"weak-{uuid.uuid4().hex[:6]}",
        title="Chủ đề yếu",
        status="published",
        position=1,
    )
    db.add(topic)
    db.flush()
    db.add(
        GrammarLesson(
            topic_id=topic.id,
            slug=f"lesson-{uuid.uuid4().hex[:6]}",
            title="Bài ôn",
            kind="theory",
            body="Nội dung",
            status="published",
            position=1,
        )
    )
    db.commit()
    return topic


def test_generate_creates_current_plan_and_progress_solves_it(
    client: TestClient, db_session: Session, auth
) -> None:
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)

    # Gắn chủ đề có bài học cho MÃ nhãn grammar của câu yếu (weak question).
    from app.models import QuestionLabel

    weak_question = db_session.scalar(select(Question).where(Question.part == 5).limit(1))
    db_session.add(
        QuestionLabel(question_id=weak_question.id, facet="grammar", code="GRAMMAR_TENSE")
    )
    make_weak_topic_with_lesson(db_session)
    topic = db_session.scalar(select(GrammarTopic).where(GrammarTopic.code == "GRAMMAR_TENSE"))
    if topic is None:
        db_session.add(
            GrammarTopic(
                code="GRAMMAR_TENSE",
                slug="thi",
                title="Thì",
                status="published",
                position=1,
            )
        )
        db_session.flush()
        db_session.add(
            GrammarLesson(
                topic_id=db_session.scalar(
                    select(GrammarTopic).where(GrammarTopic.code == "GRAMMAR_TENSE")
                ).id,
                slug="thi-01",
                title="Thì 1",
                kind="theory",
                body="Nội dung",
                status="published",
                position=1,
            )
        )
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert plan["items"], "phải có ít nhất một mục (part 5 yếu)"
    assert plan["done_count"] == 0
    kinds = {i["kind"] for i in plan["items"]}
    assert kinds <= {"grammar_lesson", "part_drill"}

    # Bấm lại cùng lượt: KHÔNG sinh mới — cùng plan id (idempotent).
    plan2 = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert plan2["id"] == plan["id"]
    current_count = len(
        db_session.scalars(
            select(StudyPlan).where(StudyPlan.user_id == me, StudyPlan.is_current.is_(True))
        ).all()
    )
    assert current_count == 1


def test_older_result_click_cannot_replace_newer_plan(
    client: TestClient, db_session: Session, auth
) -> None:
    """Bấm 'Tạo kế hoạch học' từ kết quả CŨ không được thay kế hoạch sinh từ
    kết quả mới hơn — xem lại lịch sử không được viết lại hiện tại."""
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    attempt_old = build_world(db_session, me)
    # Gắn nhãn cho lượt cũ có mục sinh ra.
    for q in db_session.scalars(select(Question).where(Question.part == 5)).all():
        db_session.add(QuestionLabel(question_id=q.id, facet="grammar", code="GRAMMAR_TENSE"))
    db_session.commit()
    # Sinh kế hoạch cho lượt CŨ; nội dung của nó không được kiểm ở đây, chỉ cần
    # nó tồn tại để lượt mới có cái mà thay thế.
    client.post(
        "/api/v1/study-plan/generate",
        headers=auth("learner"),
        json={"attempt_id": str(attempt_old.id)},
    )

    # Lượt placement MỚI hơn (bài retake) → sinh lại.
    time.sleep(0.02)  # đảm bảo started_at mới hơn
    attempt_new = build_world(db_session, me)
    second = client.post(
        "/api/v1/study-plan/generate",
        headers=auth("learner"),
        json={"attempt_id": str(attempt_new.id)},
    ).json()
    assert second["placement_attempt_id"] == str(attempt_new.id)

    # Bấm lại từ lượt CŨ: kế hoạch hiện hành giữ nguyên.
    stale = client.post(
        "/api/v1/study-plan/generate",
        headers=auth("learner"),
        json={"attempt_id": str(attempt_old.id)},
    ).json()
    assert stale["placement_attempt_id"] == str(attempt_new.id)


def test_progress_reflects_real_completions(client: TestClient, db_session: Session, auth) -> None:
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    weak_questions = db_session.scalars(select(Question).where(Question.part == 5)).all()
    for weak_question in weak_questions:
        db_session.add(
            QuestionLabel(question_id=weak_question.id, facet="grammar", code="GRAMMAR_TENSE")
        )
    topic = GrammarTopic(
        code="GRAMMAR_TENSE",
        slug=f"thi-{uuid.uuid4().hex[:4]}",
        title="Thì",
        status="published",
        position=1,
    )
    db_session.add(topic)
    db_session.flush()
    lesson = GrammarLesson(
        topic_id=topic.id,
        slug=f"thi-{uuid.uuid4().hex[:4]}",
        title="Thì 1",
        kind="theory",
        body="Nội dung",
        status="published",
        position=1,
    )
    db_session.add(lesson)
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    lesson_item = next(i for i in plan["items"] if i["kind"] == "grammar_lesson")
    assert lesson_item["done"] is False

    # Học xong bài → tiến độ nhích, KHÔNG cần chạm kế hoạch.
    from app.models import GrammarLessonCompletion

    db_session.add(GrammarLessonCompletion(user_id=me, lesson_id=uuid.UUID(lesson_item["ref_id"])))
    db_session.commit()
    again = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert again["done_count"] == 1
    assert next(i for i in again["items"] if i["kind"] == "grammar_lesson")["done"] is True


def test_exam_date_shrinks_the_budget(client: TestClient, db_session: Session, auth) -> None:
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    profile = db_session.get(UserProfile, me)
    if profile is None:
        profile = UserProfile(user_id=me)
        db_session.add(profile)
    profile.exam_date = date.today() + timedelta(days=5)
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert len(plan["items"]) <= 6


def test_generate_without_any_placement_is_409(client: TestClient, auth) -> None:
    refused = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={})
    assert refused.status_code == 409


def test_part_drill_needs_at_least_one_answer(
    client: TestClient, db_session: Session, auth
) -> None:
    """Mở phiên rồi đóng không trả lời câu nào KHÔNG tính là xong mục drill."""
    from datetime import UTC as dt_UTC
    from datetime import datetime as dt_datetime

    from app.models import PartSession, PartSessionItem

    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    weak_questions = db_session.scalars(select(Question).where(Question.part == 5)).all()
    for weak_question in weak_questions:
        db_session.add(
            QuestionLabel(question_id=weak_question.id, facet="grammar", code="GRAMMAR_TENSE")
        )
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    drill = next(i for i in plan["items"] if i["kind"] == "part_drill")
    part = drill["part"]

    now = dt_datetime.now(dt_UTC)
    empty_session = PartSession(user_id=me, part=part, labels=[], created_at=now)
    db_session.add(empty_session)
    db_session.flush()
    answered_session = PartSession(user_id=me, part=part, labels=[], created_at=now)
    db_session.add(answered_session)
    db_session.flush()
    # Phiên trống: không item nào. Phiên thứ hai: một câu đã trả lời.
    db_session.add(
        PartSessionItem(
            session_id=answered_session.id,
            question_id=db_session.scalar(
                select(Question).where(Question.part == part).limit(1)
            ).id,
            position=1,
            answered_at=now,
        )
    )
    db_session.commit()

    again = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    drill_after = next(i for i in again["items"] if i["kind"] == "part_drill")
    assert drill_after["done"] is True


def test_llm_planner_picks_from_candidates_and_falls_back(
    client: TestClient, db_session: Session, auth, fake_redis, monkeypatch
) -> None:
    """V2 chọn từ ứng viên và DÙNG được; hỏng thì rơi về V1 — kế hoạch vẫn có."""
    import json as _json

    from app.services.llm.fake import FakeProvider
    from tests.test_enrich_skills import gateway_with  # type: ignore[attr-defined]

    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    for q in db_session.scalars(select(Question).where(Question.part == 5)).all():
        db_session.add(QuestionLabel(question_id=q.id, facet="grammar", code="GRAMMAR_TENSE"))
        # Một nhãn question_type cho part 5 — LLM cần ÍT NHẤT HAI ứng viên
        # (MIN_PICKS) để không rơi về rule trong kịch bản thành công.
        db_session.add(
            QuestionLabel(question_id=q.id, facet="question_type", code="PART_5_GRAMMAR")
        )
    make_weak_topic_with_lesson(db_session)
    db_session.add(
        GrammarTopic(
            code="GRAMMAR_TENSE",
            slug=f"thi-{uuid.uuid4().hex[:4]}",
            title="Thì",
            status="published",
            position=1,
        )
    )
    db_session.flush()
    topic = db_session.scalar(select(GrammarTopic).where(GrammarTopic.code == "GRAMMAR_TENSE"))
    db_session.add(
        GrammarLesson(
            topic_id=topic.id,
            slug=f"thi-{uuid.uuid4().hex[:4]}",
            title="Thì 1",
            kind="theory",
            body="Nội dung",
            status="published",
            position=1,
        )
    )
    db_session.commit()

    # Model trả đúng JSON: chọn 1 ứng viên grammar + 1 ứng viên part.
    def reply(request):
        picks = []
        for line in request.user.splitlines():
            if "candidate_id: g" in line:
                picks.append(
                    {"id": line.split("candidate_id: ")[1].split(" ")[0], "reason": "yếu nhất"}
                )
            elif "candidate_id: p" in line:
                picks.append(
                    {"id": line.split("candidate_id: ")[1].split(" ")[0], "reason": "part yếu"}
                )
        return _json.dumps({"items": picks})

    provider = FakeProvider(reply=reply)
    gw = gateway_with(db_session, fake_redis, provider)
    monkeypatch.setattr("app.api.routes.study_plan.get_gateway", lambda db: gw)

    plan = client.post(
        "/api/v1/study-plan/generate", headers=auth("learner"), json={"source": "llm"}
    ).json()
    assert plan["source"] == "llm"
    assert len(plan["items"]) == 2
    assert all(i["reason"] for i in plan["items"])

    # Model trả rác: rơi về rule, kế hoạch vẫn có và source là rule.
    # Thế giới MỚI — vì kế hoạch llm của lượt này đã tồn tại, POST lại cùng
    # lượt + cùng source là no-op đúng nghĩa (trả cái cũ, không gọi provider).
    broken = FakeProvider(reply="không phải json")
    gw2 = gateway_with(db_session, fake_redis, broken)
    monkeypatch.setattr("app.api.routes.study_plan.get_gateway", lambda db: gw2)
    fresh = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    attempt_fresh = build_world(db_session, fresh)
    fresh_qids = [
        row[0]
        for row in db_session.execute(
            select(Question.id)
            .join(QuestionLabel, QuestionLabel.question_id == Question.id, isouter=True)
            .where(Question.part == 5, QuestionLabel.question_id.is_(None))
        ).all()
    ]
    for qid in fresh_qids:
        db_session.add(QuestionLabel(question_id=qid, facet="grammar", code="GRAMMAR_TENSE"))
        db_session.add(QuestionLabel(question_id=qid, facet="question_type", code="PART_5_GRAMMAR"))
    db_session.commit()
    fallback = client.post(
        "/api/v1/study-plan/generate",
        headers=auth("learner"),
        json={"source": "llm", "attempt_id": str(attempt_fresh.id)},
    ).json()
    assert fallback["source"] == "rule"
    assert fallback["items"]
