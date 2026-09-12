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
    done_item = next(i for i in again["items"] if i["kind"] == "grammar_lesson")
    assert done_item["done"] is True
    # Tick đứng đúng NGÀY THẬT nó xong: `completed_on` từ chính hàng completion,
    # cùng `local_today(now, tz)` với `today` của response nên luôn bằng hôm
    # nay khi vừa học xong — và không trôi theo `today` khi ngày kế đến.
    assert done_item["completed_on"] == again["today"]


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


# --- lịch suy ra lúc đọc -----------------------------------------------------


def _learner_with_profile(client: TestClient, auth, db_session: Session):
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    profile = db_session.get(UserProfile, me)
    if profile is None:
        profile = UserProfile(user_id=me)
        db_session.add(profile)
    return me, profile


def test_distant_exam_date_fills_the_calendar_with_rhythm(
    client: TestClient, db_session: Session, auth
) -> None:
    """Ngày thi còn xa → sau các mục lõi là nhịp nền xen kẽ, lịch kín tới ngày thi.

    `done` của nhịp nền luôn False — nó không hứa một nội dung khép được, và
    một mục không bao giờ xong mà vẫn đếm "tiến độ" là đồng hồ hỏng.
    """
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    kinds = [i["kind"] for i in plan["items"]]
    fillers = [k for k in kinds if k in ("vocab_review", "dictation")]
    assert fillers, "40 ngày trống mà không có nhịp nền?"
    assert set(fillers) == {"vocab_review", "dictation"}
    # Mục lõi đứng trước: lời khuyên từ placement dẫn đường, nhịp nền lấp khoảng
    # còn lại — không phải ngược lại.
    assert kinds.index("part_drill") < kinds.index("vocab_review")
    days = sorted({i["day"] for i in plan["items"] if i["day"]})
    assert days and days[0] == plan["today"] and days == sorted(days)
    assert all(d >= plan["today"] for d in days)  # không ngày nào ở quá khứ
    filler = next(i for i in plan["items"] if i["kind"] == "vocab_review")
    assert filler["done"] is False


def test_two_weeks_before_the_exam_stays_short(
    client: TestClient, db_session: Session, auth
) -> None:
    """≤14 ngày: danh sách ngắn là chủ ý của SPEC §5 — nhịp nền KHÔNG được lấp
    kín hai tuần cuối thành lịch dày hơn lời khuyên tập trung."""
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=10)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert {i["kind"] for i in plan["items"]} <= {"grammar_lesson", "part_drill"}


def test_week_buffer_before_exam_still_has_content(
    client: TestClient, db_session: Session, auth
) -> None:
    """Ô đo dừng ở thi-7, nhưng những ngày cuối không được trắng lịch.

    Tuần buffer (giữa lần đo cuối/mock và ngày thi) từng không nhận mục nào —
    đề thi càng xa thì càng thấy rõ khoảng trống ngay trước kỳ thi. Chủ ý cũ
    chỉ là KHÔNG KỸ NĂNG MỚI sát ngày thi, không phải nghỉ luôn."""
    _me, profile = _learner_with_profile(client, auth, db_session)
    exam = date.today() + timedelta(days=60)
    profile.exam_date = exam
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    days = sorted(i["day"] for i in plan["items"] if i["day"])
    assert days, "plan rỗng"
    assert days[-1] <= exam.isoformat(), "không có mục nào hẹn sau ngày thi"
    tail_floor = (exam - timedelta(days=6)).isoformat()
    assert any(d > tail_floor for d in days), "sáu ngày cuối trước kỳ thi bị bỏ trống"


def test_far_exam_has_a_planning_horizon(client: TestClient, db_session: Session, auth) -> None:
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=400)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert len(plan["items"]) <= 120


def test_days_are_derived_at_read_time_not_stored(
    client: TestClient, db_session: Session, auth
) -> None:
    """Đổi `minutes_per_day` giữa hai lần GET — KHÔNG sinh lại — lịch đóng gói
    lại theo phút: bằng chứng ngày không lưu ở đâu ngoài packing lúc đọc, neo
    `starts_at`. Hoàn thành không dịch chuyển gì (test tick ở dưới); muốn đuổi
    kịp lịch sau vài hôm nghỉ thì "Dời lịch" là hành động tường minh.
    """
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    undone = [i for i in plan["items"] if not i["done"]]
    assert plan["minutes_per_day"] == 30
    assert undone[0]["day"] == plan["today"]
    # 30'/ngày và mục 30' → đúng MỘT mục một ngày (packing theo phút, không
    # phải "mọi người 3 buổi"): ngày thứ hai khác hôm nay.
    assert undone[1]["day"] != plan["today"]

    profile.minutes_per_day = 90
    db_session.commit()
    again = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert again["id"] == plan["id"]  # không sinh lại — chỉ cách đọc đổi
    assert again["minutes_per_day"] == 90
    undone = [i for i in again["items"] if not i["done"]]
    packed = [i for i in undone if i["day"] == again["today"]]
    total = sum(i["est_minutes"] for i in packed)
    assert len(packed) >= 2 and total <= 90, "90' một ngày phải nhét được nhiều mục 30'"


def test_rest_days_are_days_not_overdue(client: TestClient, db_session: Session, auth) -> None:
    """`study_days_per_week=2`: mỗi tuần chỉ 2 ngày CÓ mục, phần còn lại trống
    mà không hàng nào bị đánh dấu bỏ — ngày nghỉ là cấu hình, không phải lỗi."""
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    profile.minutes_per_day = 30
    profile.study_days_per_week = 2
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    days = sorted({i["day"] for i in plan["items"] if i["day"]})
    assert days[0] == plan["today"]
    offsets = sorted((date.fromisoformat(d) - date.fromisoformat(plan["today"])).days for d in days)
    # `days_per_week=2`: mỗi tuần chỉ ngày 0 và 1 có mục. Kiểm tra packing để
    # lịch KHÔNG nhét mục vào ngày 2–6 (ngày nghỉ) — đó là toàn bộ ý nghĩa của
    # cột mới: ai chọn 2 ngày/tuần không bị đếm "bỏ hôm" 5 ngày còn lại.
    for off in offsets:
        assert off % 7 < 2, f"mục rơi vào ngày nghỉ (offset {off}, tuần {off // 7 + 1})"
    # ...và retake tuần j neo đúng ngày học ĐẦU của tuần j (offset (j)*7).
    retake_days = [i["day"] for i in plan["items"] if i["kind"] == "mini_test" and i["day"]]
    assert retake_days, "exams xa phải có nhịp kiểm tra hằng tuần"
    for d in retake_days:
        off = (date.fromisoformat(d) - date.fromisoformat(plan["today"])).days
        assert off % 7 == 0, "mini_test phải rơi vào ngày học đầu tuần"


def test_force_regenerates_the_calendar_after_inputs_move(
    client: TestClient, db_session: Session, auth
) -> None:
    """Đổi ngày thi rồi bấm "Sinh lại": `force` cho lịch mới từ cùng kết quả;
    không force thì idempotence cũ vẫn đứng nguyên."""
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=20)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()

    same = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert same["id"] == plan["id"]

    profile.exam_date = date.today() + timedelta(days=60)
    db_session.commit()
    unchanged = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert unchanged["id"] == plan["id"], "không force thì đừng viết sau lưng"

    forced = client.post(
        "/api/v1/study-plan/generate", headers=auth("learner"), json={"force": True}
    ).json()
    assert forced["id"] != plan["id"]
    assert len(forced["items"]) > len(plan["items"]), "60 ngày phải kín hơn 20 ngày"


# --- tick thủ công -----------------------------------------------------------


def test_manual_tick_does_not_slide_the_calendar(
    client: TestClient, db_session: Session, auth
) -> None:
    """Tick tay ghi vào cột riêng `done_at`, NGÀY KHÔNG ĐỔI.

    Đây là điều người học bác ở bản trước: xong một mục mà cả lịch nhảy lên
    = "dồn task". Lịch neo `starts_at`, mọi vị trí đều chiếm chỗ dù đã xong
    hay chưa — bỏ tick rồi tick lại cũng trả đúng ngày cũ."""
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    # Một chủ đề grammar + lesson để plan có ≥2 mục (progress test trên dùng
    # cùng bộ dữ liệu này).
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
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    first = plan["items"][0]
    assert first["done"] is False and first["day"] == plan["today"]
    before_second = plan["items"][1]["day"]

    ticked = client.patch(
        f"/api/v1/study-plan/items/{first['position']}",
        json={"done": True},
        headers=auth("learner"),
    )
    assert ticked.status_code == 200
    body = ticked.json()
    item = next(i for i in body["items"] if i["position"] == first["position"])
    assert item["done"] is True and item["manual_done"] is True
    assert item["completed_on"] == body["today"]
    # Ngày của mục này GIỮ NGUYÊN sau khi tick (đúng cái ô nó được hẹn), và
    # mục sau cũng đứng nguyên — không có chuyện "trượt lên chiếm chỗ": đó là
    # cái làm lịch trông như bị dồn, và là lý do bản suy-theo-hôm-nay bị bác.
    assert item["day"] == first["day"]
    nxt = next(i for i in body["items"] if i["position"] == plan["items"][1]["position"])
    assert nxt["day"] == before_second, "tick không được dịch các mục khác"

    unticked = client.patch(
        f"/api/v1/study-plan/items/{first['position']}",
        json={"done": False},
        headers=auth("learner"),
    ).json()
    item = next(i for i in unticked["items"] if i["position"] == first["position"])
    assert item["done"] is False and item["manual_done"] is False
    assert (
        next(i for i in unticked["items"] if i["position"] == plan["items"][1]["position"])["day"]
        == before_second
    )


def test_tick_a_filler_is_the_only_way_it_ever_finishes(
    client: TestClient, db_session: Session, auth
) -> None:
    """Nhịp nền không có bản ghi học để suy — tick tay là đường khép duy nhất."""
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    profile = db_session.get(UserProfile, me) or _mk_profile(db_session, me)
    profile.exam_date = date.today() + timedelta(days=30)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    filler = next(i for i in plan["items"] if i["kind"] == "vocab_review")
    assert filler["done"] is False

    body = client.patch(
        f"/api/v1/study-plan/items/{filler['position']}",
        json={"done": True},
        headers=auth("learner"),
    ).json()
    done_filler = next(i for i in body["items"] if i["position"] == filler["position"])
    assert done_filler["done"] is True and done_filler["manual_done"] is True


def _mk_profile(db_session: Session, user_id: uuid.UUID) -> UserProfile:
    profile = UserProfile(user_id=user_id)
    db_session.add(profile)
    return profile


def test_tick_unknown_position_is_404(client: TestClient, db_session: Session, auth) -> None:
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={})
    assert (
        client.patch(
            "/api/v1/study-plan/items/999", json={"done": True}, headers=auth("learner")
        ).status_code
        == 404
    )


def test_done_count_ignores_the_rhythm(client: TestClient, db_session: Session, auth) -> None:
    """`done_count` đếm mục LÕI, không đếm nhịp nền.

    Mẫu số UI là số mục lõi; để tử số tính cả nhịp nền đã tick là "8/3 mục đã
    xong" — một kế hoạch 100% không thể với tới, hoặc tệ hơn là hoàn thành bằng
    cách đánh dấu thứ chưa ai định khép.
    """
    me = uuid.UUID(client.get("/api/v1/auth/me", headers=auth("learner")).json()["id"])
    build_world(db_session, me)
    profile = db_session.get(UserProfile, me) or _mk_profile(db_session, me)
    profile.exam_date = date.today() + timedelta(days=30)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    filler = next(i for i in plan["items"] if i["kind"] == "vocab_review")
    assert plan["done_count"] == 0
    client.patch(
        f"/api/v1/study-plan/items/{filler['position']}",
        json={"done": True},
        headers=auth("learner"),
    )
    after = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert after["done_count"] == 0, "tick một nhịp nền không được thành tiến độ kế hoạch"


# --- kiểm tra định kỳ: retake tuần + đề thi thử --------------------------------


def _publish_collection_with_forms(db: Session, n: int) -> list[PracticeTest]:
    """N collection published + M đề full inside — pool thi thử CHỈ nhận đề
    nằm trong collection published (đề orphan/archived là CTA 404)."""
    from app.models import TestCollection

    coll = TestCollection(
        slug=f"coll-{uuid.uuid4().hex[:6]}", title="Bộ đề thi thử", status="published", position=1
    )
    db.add(coll)
    db.flush()
    forms = []
    for i in range(n):
        form = PracticeTest(
            slug=f"form-{uuid.uuid4().hex[:6]}",
            title=f"Đề hoàn chỉnh {i}",
            kind="full",
            status="published",
            is_placement=False,
            collection_id=coll.id,
            time_limit_seconds=7200,
        )
        db.add(form)
        forms.append(form)
    db.commit()
    return forms


def _submit_retake(
    db: Session, learner_id: uuid.UUID, test_id: uuid.UUID, *, correct: bool = True
) -> None:
    """Một lượt nộp NỘP SAU khi kế hoạch sinh —packer và route đếm theo thời
    gian, không cần biết nội dung câu hỏi."""
    attempt = Attempt(
        user_id=learner_id,
        test_id=test_id,
        scope="full",
        review_mode="exam",
        status="submitted",
        elapsed_seconds=0,
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC),
    )
    db.add(attempt)
    db.flush()
    db.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=learner_id,
            estimator_version="v1",
            listening_raw=1,
            reading_raw=1,
            listening_scaled=60,
            reading_scaled=60,
            listening_low=0,
            listening_high=100,
            reading_low=0,
            reading_high=100,
            cefr_listening="A1",
            cefr_reading="A1",
            cefr_overall="A1",
        )
    )
    db.commit()


def test_weekly_checkin_closes_only_when_a_retake_lands(
    client: TestClient, db_session: Session, auth
) -> None:
    """Mục retake tự khép bằng BÀI NỘP và từ chối tick tay ở cả hai đầu."""
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    minis = [i for i in plan["items"] if i["kind"] == "mini_test"]
    assert minis and all(not i["done"] for i in minis)

    blocked = client.patch(
        f"/api/v1/study-plan/items/{minis[0]['position']}",
        json={"done": True},
        headers=auth("learner"),
    )
    assert blocked.status_code == 409, "tick một bài kiểm tra là xưng đã đo mà chưa đo"

    attempt = db_session.scalar(select(Attempt).where(Attempt.user_id == me))
    assert attempt is not None
    _submit_retake(db_session, me, attempt.test_id)
    after = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    closed = [i for i in after["items"] if i["kind"] == "mini_test"]
    assert closed[0]["done"] and not closed[0]["manual_done"]
    assert closed[0]["completed_on"] == after["today"]
    assert closed[1]["done"] is False, "một retake chỉ khép được MỘT tuần"
    assert any(i["kind"] == "mini_test" and i["done"] for i in after["items"])
    # Mẫu số §34 có mục kiểm tra: retake đầu là tiến độ THẬT, phải nhích đếm.
    assert after["done_count"] >= 1


def test_mock_test_lands_before_exam_and_closes_on_submission(
    client: TestClient, db_session: Session, auth
) -> None:
    me, profile = _learner_with_profile(client, auth, db_session)
    exam = date.today() + timedelta(days=40)
    profile.exam_date = exam
    db_session.commit()
    # Chưa có đề full publish → không có mục mock (N4: không hứa treo).
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert not any(i["kind"] == "mock_test" for i in plan["items"])

    full = _publish_collection_with_forms(db_session, 1)[0]
    forced = client.post(
        "/api/v1/study-plan/generate", headers=auth("learner"), json={"force": True}
    ).json()
    mock = next((i for i in forced["items"] if i["kind"] == "mock_test"), None)
    assert mock is not None, "có đề publish + còn 40 ngày thì phải có thi thử"
    assert mock["test_slug"] == full.slug
    assert mock["link"] and mock["link"].endswith("?plan=mock")
    assert mock["est_minutes"] == 125
    assert mock["day"] and date.fromisoformat(mock["day"]) <= exam - timedelta(days=5)
    assert forced["items"][-1]["kind"] == "mock_test", "mock đứng cuối hàng đợi"

    _submit_retake(db_session, me, full.id)
    after = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    done_mock = next(i for i in after["items"] if i["kind"] == "mock_test")
    assert done_mock["done"] and done_mock["completed_on"]
    blocked = client.patch(
        f"/api/v1/study-plan/items/{done_mock['position']}",
        json={"done": False},
        headers=auth("learner"),
    )
    assert blocked.status_code == 409


def test_plan_header_shows_estimate_gap_feasibility(
    client: TestClient, db_session: Session, auth
) -> None:
    """§34: màn kế hoạch phải nói được 'đang ở đâu, cách bao xa, có lịch này thì
    khả thi không' — mọi con số truy vấn được, không chuỗi nào bịa."""
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.target_score = 700
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    # build_world không gắn nhãn — top focus cần đúng mấy câu sai có mã.
    wrong = db_session.scalars(
        select(AttemptItem.question_id).where(AttemptItem.is_correct.is_(False))
    ).all()
    for qid in wrong:
        db_session.add(QuestionLabel(question_id=qid, facet="grammar", code="GRAMMAR_TENSE"))
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert plan["estimate"] is not None
    assert plan["estimate"]["total"] == 90  # 60 nghe + 30 đọc từ build_world
    assert plan["estimate"]["cefr"] == "A1"
    assert plan["gap"] == 610
    assert plan["weeks_left"] == 6
    assert plan["feasibility"] == "HIGH_RISK", "+610 điểm/6 tuần là không nổi"
    assert plan["top_focus"], "build_world có 3 câu grammar sai — phải có priority"
    assert "90" in (plan["why"] or "")
    first = (plan["why"] or "").splitlines()[0]
    assert first == "90 → 700 điểm · 6 tuần · 210 phút/tuần"
    assert "Kế hoạch ưu tiên những kỹ năng yếu nhất:" in plan["why"]

    profile.target_score = None
    db_session.commit()
    again = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert again["gap"] is None and again["feasibility"] is None
    assert again["estimate"] is not None, "không có mục tiêu thì ước lượng vẫn hiện"


def test_pack_days_gives_long_item_its_own_day() -> None:
    from app.services.study_planner import pack_days

    today = date(2026, 9, 12)
    out = pack_days(
        [(1, 30, "part_drill"), (2, 30, "part_drill"), (3, 15, "vocab_review")],
        [],
        today,
        60,
        3,
        None,
    )
    # Luật BỐN: hai drill cùng kind không chung ngày dù 60' nhét vừa hai 30'.
    assert out[1] == today and out[2] == today + timedelta(days=1)
    # vocab 15' đi cùng drill 30' = 45' ≤ 60' và khác kind → chung ngày 1.
    assert out[3] == out[2]


def test_profile_study_days_per_week_validates_and_roundtrips(client: TestClient, auth) -> None:
    bad = client.patch("/api/v1/profile", json={"study_days_per_week": 8}, headers=auth("learner"))
    assert bad.status_code == 422
    ok = client.patch("/api/v1/profile", json={"study_days_per_week": 5}, headers=auth("learner"))
    assert ok.status_code == 200
    assert ok.json()["study_days_per_week"] == 5


def test_items_carry_their_destination_and_taxonomy(
    client: TestClient, db_session: Session, auth
) -> None:
    """Mỗi mục mang ĐÍCH ĐẾN cụ thể (mig 085): drill kèm `?labels=`, retake về
    /learn/placement; nhãn drill nêu rõ DẠNG CÂU, không chỉ "Luyện Part 7".
    """
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    # build_world không gắn nhãn — gán question_type cho mấy câu sai P5 để
    # priority engine có DRILL kèm mã (grammar code sẽ đi hướng lesson).
    wrong = db_session.scalars(
        select(AttemptItem.question_id)
        .join(Attempt, Attempt.id == AttemptItem.attempt_id)
        .where(Attempt.user_id == me, AttemptItem.is_correct.is_(False))
    ).all()
    for qid in wrong:
        db_session.add(QuestionLabel(question_id=qid, facet="question_type", code="PART_5_GRAMMAR"))
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    drills = [i for i in plan["items"] if i["kind"] == "part_drill"]
    assert drills
    deep = [d for d in drills if d["link"] and "labels=" in d["link"]]
    assert deep, "drill từ priority phải mang bộ lọc nhãn"
    assert all(" — " in d["label"] for d in deep), "nhãn drill phải kèm tên dạng câu"
    # Xoay vòng: hai drill sâu không trùng nhãn (pool 1 phần thì chấp nhận lặp).
    mini = next(i for i in plan["items"] if i["kind"] == "mini_test")
    assert mini["link"] == "/learn/placement"
    # top_focus phải đủ dữ liệu để chip bấm mở đúng drill đã lọc.
    focus = plan["top_focus"][0]
    assert focus["code"] and focus["part"] >= 1


def test_topics_rotation_labels_vocabulary_by_subject(
    client: TestClient, db_session: Session, auth
) -> None:
    """Có catalogue từ vựng publish → nhãn nền mang TÊN CHỦ ĐỀ và link thẳng
    board; không còn cảnh 'Ôn từ vựng đến hạn' lặp hai ô một ngày."""
    from app.models import Topic

    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    for i, (slug, name) in enumerate([("travel", "Travel"), ("office", "Office")]):
        db_session.add(Topic(slug=slug, name=name, position=i, status="published"))
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    vocab = [i for i in plan["items"] if i["kind"] == "vocab_review"]
    assert len(vocab) >= 2
    # Hai catalogue quay trên bốn tuần thì nhãn LẶP LÀ ĐÚNG (Travel tuần 1 và
    # 3); cái phải cấm được là lặp TRONG MỘT NGÀY và một chuỗi vô hồn.
    named = [i for i in vocab if i["label"].startswith("Ôn từ vựng — ")]
    assert {i["label"] for i in named} == {"Ôn từ vựng — Travel", "Ôn từ vựng — Office"}
    assert any(i["link"] == "/learn/vocabulary/travel" for i in vocab)
    from collections import Counter

    vocab_per_day = Counter(i["day"] for i in vocab)
    assert all(v <= 1 for v in vocab_per_day.values()), "không hai board từ vựng cùng một ngày"


def test_repack_is_the_only_way_dates_move(client: TestClient, db_session: Session, auth) -> None:
    """ "Dời lịch" đổi móc neo — hành động tường minh duy nhất dịch chuyển ngày
    của các mục chưa xảy ra; tick và GET thì không."""
    _me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    undone_days = {i["position"]: i["day"] for i in plan["items"] if not i["done"]}

    again = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert {i["position"]: i["day"] for i in again["items"] if not i["done"]} == undone_days

    moved = client.post("/api/v1/study-plan/repack", headers=auth("learner")).json()
    assert moved["id"] == plan["id"], "dời lịch không sinh kế hoạch mới"
    assert moved["starts_at"] == moved["today"]
    assert moved["items"][0]["day"] == moved["today"]


def test_mock_test_target_is_a_choice_until_submitted(
    client: TestClient, db_session: Session, auth
) -> None:
    """Đề thi thử rút ngẫu nhiên lúc sinh và ĐỔI ĐƯỢC tới khi nộp; đã nộp là
    đóng — lịch sử của một bài đã làm không phải con trỏ UI."""
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    forms = _publish_collection_with_forms(db_session, 2)
    # Đề published nhưng KHÔNG collection — không được xuất hiện ở pool.
    orphan = PracticeTest(
        slug=f"orphan-{uuid.uuid4().hex[:6]}",
        title="Đề mồ côi",
        kind="full",
        status="published",
        is_placement=False,
        time_limit_seconds=7200,
    )
    db_session.add(orphan)
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    mock = next(i for i in plan["items"] if i["kind"] == "mock_test")
    assert mock["ref_id"] in [str(f.id) for f in forms], "phải rút từ kho đã publish"
    assert {o["id"] for o in plan["mock_options"]} == {str(f.id) for f in forms}
    ghost_ref = client.patch(
        f"/api/v1/study-plan/items/{mock['position']}",
        json={"test_id": str(orphan.id)},
        headers=auth("learner"),
    )
    assert ghost_ref.status_code == 404, "đề ngoài collection published không phải lựa chọn"

    switched = client.patch(
        f"/api/v1/study-plan/items/{mock['position']}",
        json={"test_id": str(forms[1].id)},
        headers=auth("learner"),
    )
    assert switched.status_code == 200
    row = next(i for i in switched.json()["items"] if i["kind"] == "mock_test")
    assert row["ref_id"] == str(forms[1].id)
    assert "Đề hoàn chỉnh 1" in row["label"]

    other = next(i for i in plan["items"] if i["kind"] == "part_drill")
    wrong = client.patch(
        f"/api/v1/study-plan/items/{other['position']}",
        json={"test_id": str(forms[0].id)},
        headers=auth("learner"),
    )
    assert wrong.status_code == 409, "chỉ mục thi thử mới đổi đề"
    ghost = client.patch(
        f"/api/v1/study-plan/items/{mock['position']}",
        json={"test_id": str(uuid.uuid4())},
        headers=auth("learner"),
    )
    assert ghost.status_code == 404
    empty = client.patch(
        f"/api/v1/study-plan/items/{mock['position']}",
        json={},
        headers=auth("learner"),
    )
    assert empty.status_code == 422

    # Nộp đề đã chọn → khép bằng attempt, và từ đó không đổi đích được nữa.
    _submit_retake(db_session, me, forms[1].id)
    after = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    done_mock = next(i for i in after["items"] if i["kind"] == "mock_test")
    assert done_mock["done"]
    locked = client.patch(
        f"/api/v1/study-plan/items/{done_mock['position']}",
        json={"test_id": str(forms[0].id)},
        headers=auth("learner"),
    )
    assert locked.status_code == 409


def _second_verdict(db_session: Session, me: uuid.UUID, attempt_id: uuid.UUID) -> None:
    """Phán quyết placement thứ hai — hàng thật qua đường DB, như cách
    `analyze` để lại sau một lượt đo lại."""
    base = db_session.get(PlacementResult, attempt_id)
    assert base is not None
    attempt = Attempt(
        user_id=me,
        test_id=db_session.get(Attempt, attempt_id).test_id,
        scope="full",
        review_mode="exam",
        status="submitted",
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC),
        elapsed_seconds=900,
    )
    db_session.add(attempt)
    db_session.flush()
    db_session.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=me,
            estimator_version="v1",
            listening_raw=30,
            reading_raw=25,
            listening_scaled=350,
            reading_scaled=250,
            listening_low=320,
            listening_high=380,
            reading_low=220,
            reading_high=280,
            cefr_listening="B1",
            cefr_reading="A2",
            cefr_overall="A2",
        )
    )
    db_session.commit()


def test_plan_versions_record_reason_and_keep_history(
    client: TestClient, db_session: Session, auth
) -> None:
    """§29+§32: mỗi lần sinh là một PHIÊN BẢN có LÝ DO, bản cũ nằm lại."""
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.target_score = 700
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()

    v1 = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert v1["version"] == 1 and v1["reason"] == "Kế hoạch ban đầu"
    tick = next(i for i in v1["items"] if i["kind"] == "vocab_review")
    client.patch(
        f"/api/v1/study-plan/items/{tick['position']}", headers=auth("learner"), json={"done": True}
    )

    profile.target_score = 800
    db_session.commit()
    v2 = client.post(
        "/api/v1/study-plan/generate", headers=auth("learner"), json={"force": True}
    ).json()
    assert v2["version"] == 2
    assert v2["reason"] == "Mục tiêu / ngày thi thay đổi", "reason phải đọc được diff THẬT"
    assert v2["id"] != v1["id"]

    att = uuid.UUID(v2["placement_attempt_id"])
    _second_verdict(db_session, me, att)
    new_att = db_session.scalar(
        select(PlacementResult).where(
            PlacementResult.user_id == me, PlacementResult.attempt_id != att
        )
    )
    assert new_att is not None
    v3 = client.post(
        "/api/v1/study-plan/generate",
        headers=auth("learner"),
        json={"attempt_id": str(new_att.attempt_id)},
    ).json()
    assert v3["version"] == 3 and v3["reason"] == "Đo lại bằng bài kiểm tra đầu vào"

    versions = client.get("/api/v1/study-plan/versions", headers=auth("learner")).json()
    assert [v["version"] for v in versions] == [3, 2, 1]
    assert versions[0]["is_current"] and not versions[2]["is_current"]
    assert versions[2]["item_count"] > 0
    assert versions[2]["done_count"] == 1, "tick tay của bản cũ phải còn đó"


def test_evaluation_exposes_series_trend_and_new_diagnostic(
    client: TestClient, db_session: Session, auth
) -> None:
    """§30–§31: chuỗi đo + trend theo nhãn + cờ "có số mới, lịch đang cũ"."""
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.target_score = 700
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    wrong = db_session.scalars(
        select(AttemptItem.question_id).where(AttemptItem.is_correct.is_(False))
    ).all()
    for qid in wrong:
        db_session.add(QuestionLabel(question_id=qid, facet="grammar", code="GRAMMAR_TENSE"))
    db_session.commit()

    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    ev = client.get("/api/v1/study-plan/evaluation", headers=auth("learner")).json()
    assert len(ev["retakes"]) == 1 and ev["retakes"][0]["total_scaled"] == 90
    assert ev["new_diagnostic"] is False
    assert [t["code"] for t in ev["trend"]] == [f["code"] for f in plan["top_focus"]]
    tense = next(t for t in ev["trend"] if t["code"] == "GRAMMAR_TENSE")
    assert tense["baseline_total"] >= 3 and tense["recent_total"] == 0

    att = uuid.UUID(plan["placement_attempt_id"])
    _second_verdict(db_session, me, att)
    second = db_session.scalar(
        select(PlacementResult).where(
            PlacementResult.user_id == me, PlacementResult.attempt_id != att
        )
    )
    assert second is not None
    # Nộp MỘT câu đúng trên đúng cái nhãn đó — đường "recent" phải đếm được
    # bằng chứng từ bài nộp mới, không chỉ từ bài đầu vào.
    first_wrong = wrong[0]
    db_session.add(
        AttemptItem(
            attempt_id=second.attempt_id,
            question_id=first_wrong,
            position=1,
            selected_option_id=None,
            is_correct=True,
        )
    )
    db_session.commit()

    again = client.get("/api/v1/study-plan/evaluation", headers=auth("learner")).json()
    assert again["new_diagnostic"] is True, "có phán quyết mới hơn ca mọc plan"
    tense2 = next(t for t in again["trend"] if t["code"] == "GRAMMAR_TENSE")
    assert tense2["recent_total"] >= 1 and tense2["recent_correct"] >= 1


def test_retake_analyze_creates_new_plan_version(
    client: TestClient, db_session: Session, auth
) -> None:
    """§32 tất định: đo lại xong → kế hoạch MỚI từ số mới, ngay khi phân tích.

    Ca cũ không bị sửa — nó thành phiên bản trước. Phân tích lại cùng một
    lượt KHÔNG được nở thêm phiên bản thứ ba."""
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.target_score = 700
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    assert plan["version"] == 1
    base = db_session.get(Attempt, uuid.UUID(plan["placement_attempt_id"]))
    assert base is not None
    base.test.is_placement = True  # route analyze đòi đúng loại đề
    db_session.commit()

    retake = Attempt(
        user_id=me,
        test_id=base.test_id,
        scope="full",
        review_mode="exam",
        status="submitted",
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC),
        elapsed_seconds=900,
    )
    db_session.add(retake)
    db_session.flush()
    first_option = {
        q.id: sorted(q.options, key=lambda o: o.label)[0].id
        for q in db_session.scalars(
            select(Question).where(Question.id.in_([it.question_id for it in base.items]))
        )
    }
    for it in base.items:
        db_session.add(
            AttemptItem(
                attempt_id=retake.id,
                question_id=it.question_id,
                position=it.position,
                selected_option_id=it.selected_option_id or first_option[it.question_id],
                is_correct=True,  # "làm tốt hơn" — kéo priority engine tính lại
            )
        )
    db_session.commit()

    r = client.post(f"/api/v1/placement/attempts/{retake.id}/analyze", headers=auth("learner"))
    assert r.status_code == 200
    again = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert again["version"] == 2
    assert again["placement_attempt_id"] == str(retake.id)
    assert again["reason"] == "Đo lại bằng bài kiểm tra đầu vào"
    assert again["estimate"]["total"] > plan["estimate"]["total"], "plan mới phải bám số MỚI"

    client.post(f"/api/v1/placement/attempts/{retake.id}/analyze", headers=auth("learner"))
    third = client.get("/api/v1/study-plan", headers=auth("learner")).json()
    assert third["version"] == 2, "analyze lại cùng lượt không nở phiên bản"
    versions = client.get("/api/v1/study-plan/versions", headers=auth("learner")).json()
    assert [v["version"] for v in versions] == [2, 1]


def test_evaluation_weeks_are_real_minutes_and_mocks_join_the_series(
    client: TestClient, db_session: Session, auth
) -> None:
    """§31: phút của tuần là `elapsed_seconds` THẬT, và điểm thi thử đứng
    cùng chuỗi đo với nhãn `mock` — hai loại sự kiện khác nhau nhưng cùng một
    câu hỏi "bạn đang ở đâu theo thời gian"."""
    me, profile = _learner_with_profile(client, auth, db_session)
    profile.target_score = 700
    profile.exam_date = date.today() + timedelta(days=40)
    db_session.commit()
    plan = client.post("/api/v1/study-plan/generate", headers=auth("learner"), json={}).json()
    base = db_session.get(Attempt, uuid.UUID(plan["placement_attempt_id"]))
    assert base is not None

    base.submitted_at = datetime.now(UTC) - timedelta(days=2)  # bài gốc TRƯỚC plan
    db_session.commit()
    drill = Attempt(
        user_id=me,
        test_id=base.test_id,
        scope="partial",
        review_mode="exam",
        status="submitted",
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC),
        elapsed_seconds=1200,
    )
    mock_test = PracticeTest(
        slug="t-full-eval",
        title="Đề thi thử kiểm chứng",
        kind="full",
        status="published",
        score_scale_slug="default",
        collection_id=None,
    )
    db_session.add(mock_test)
    db_session.flush()
    mock_att = Attempt(
        user_id=me,
        test_id=mock_test.id,
        scope="full",
        review_mode="exam",
        status="submitted",
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC),
        elapsed_seconds=7500,
        total_scaled=610,
    )
    db_session.add_all([drill, mock_att])
    db_session.commit()

    ev = client.get("/api/v1/study-plan/evaluation", headers=auth("learner")).json()
    wk = ev["weeks"][0]
    assert wk["index"] == 0
    assert wk["minutes"] == 20 + 125  # đúng hai lượt nộp, không phút bịa
    assert wk["attempts"] == 2
    kinds = [(r["kind"], r["total_scaled"]) for r in ev["retakes"]]
    assert ("mini", 90) in kinds and ("mock", 610) in kinds
