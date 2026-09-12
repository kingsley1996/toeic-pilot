"""Dev-only: reset placement của admin@toeicpilot.io và chấm một phán quyết ~570.

Đi qua đúng máy thi (`open_attempt`) + `analyze` thật, chỉ khác là câu trả lời
được ĐẶT VÀO theo bài giải để tổng quy đổi chạm target. Xoá sạch plan cũ vì
chúng dựng từ phán quyết cũ.
"""

import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text

from app.api.routes.attempt import open_attempt
from app.core.database import SessionLocal
from app.models import (
    Attempt,
    AttemptItem,
    PlacementResult,
    PracticeTest,
    Question,
    StudyPlan,
    StudyPlanItem,
    User,
    UserProfile,
)
from app.models.practice import LISTENING_PARTS
from app.schemas.practice import AttemptStart
from app.services.placement import analyze
from app.services.scoring import raw_to_scaled

USER_ID = uuid.UUID("8620b22e-057a-49c2-9e84-eb027d359f1d")
TARGET_TOTAL = 570


def main() -> None:
    db = SessionLocal()
    user = db.get(User, USER_ID)
    assert user and user.email == "admin@toeicpilot.io", user

    old_attempts = list(
        db.scalars(select(Attempt.id).where(Attempt.user_id == USER_ID)).all()
    )
    old_plans = list(db.scalars(select(StudyPlan.id).where(StudyPlan.user_id == USER_ID)).all())
    for plan_id in old_plans:
        db.execute(delete(StudyPlanItem).where(StudyPlanItem.plan_id == plan_id))
    db.execute(delete(StudyPlan).where(StudyPlan.user_id == USER_ID))
    db.execute(delete(PlacementResult).where(PlacementResult.user_id == USER_ID))
    if old_attempts:
        ids = [str(a) for a in old_attempts]
        for table in ("coach_conversation", "planner_eval", "attempt_part"):
            db.execute(
                text(f"DELETE FROM {table} WHERE attempt_id::text = ANY(:ids)"),  # noqa: S608
                {"ids": ids},
            )
        db.execute(delete(AttemptItem).where(AttemptItem.attempt_id.in_(old_attempts)))
        db.execute(delete(Attempt).where(Attempt.id.in_(old_attempts)))
    db.commit()
    print(f"wiped: {len(old_plans)} plans, {len(old_attempts)} attempts")

    pool = list(
        db.scalars(
            select(PracticeTest).where(
                PracticeTest.is_placement.is_(True), PracticeTest.status == "published"
            )
        )
    )
    assert pool, "no published placement tests"
    rng = random.Random(570)
    test = rng.choice(pool)
    profile = db.get(UserProfile, USER_ID)
    attempt_state = open_attempt(
        db, test, AttemptStart(test_slug=test.slug, review_mode="exam", parts=[]), user
    )
    attempt = db.get(Attempt, uuid.UUID(attempt_state.id))
    db.add(
        PlacementResult(
            attempt_id=attempt.id,
            user_id=user.id,
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
            target_score=profile.target_score if profile else None,
        )
    )
    db.commit()
    print(f"attempt {attempt.id} on {test.slug} (scale {test.score_scale_slug})")

    rows = db.execute(
        select(AttemptItem, Question.part)
        .join(Question, Question.id == AttemptItem.question_id)
        .where(AttemptItem.attempt_id == attempt.id)
    ).all()
    question_ids = [item.question_id for item, _ in rows]
    options_by_q: dict = {}
    for q in db.scalars(select(Question).where(Question.id.in_(question_ids))):
        options_by_q[q.id] = (
            next(o.id for o in q.options if o.is_correct),
            [o.id for o in q.options if not o.is_correct],
        )
    scale = test.score_scale_slug
    # Một lượt đọc bảng quy đổi, hai tra cứu trong RAM — vòng brute force bên
    # dưới chạy hàng nghìn lần, mỗi lần một SELECT là treo cả script.
    table = {
        (r.section, r.raw_correct): r.scaled_score
        for r in db.execute(
            text(
                "SELECT section, raw_correct, scaled_score FROM score_conversion"
                " WHERE scale_slug = :slug"
            ),
            {"slug": scale},
        )
    }
    n_l = sum(1 for _i, part in rows if part in LISTENING_PARTS)
    n_r = len(rows) - n_l

    best = None
    for raw_l in range(n_l + 1):
        pct_l = round(raw_l / n_l * 100)
        s_l = table[("listening", pct_l)]
        for raw_r in range(n_r + 1):
            pct_r = round(raw_r / n_r * 100)
            s_r = table[("reading", pct_r)]
            key = (abs(s_l + s_r - TARGET_TOTAL), abs(pct_l - pct_r))
            if best is None or key < best[0]:
                best = (key, raw_l, raw_r, s_l, s_r, pct_l, pct_r)
    _, raw_l, raw_r, s_l, s_r, pct_l, pct_r = best
    print(f"sections {n_l}L/{n_r}R -> {raw_l}/{pct_l}% + {raw_r}/{pct_r}% = {s_l}+{s_r}", flush=True)

    listen = [item for item, part in rows if part in LISTENING_PARTS]
    read = [item for item, part in rows if part not in LISTENING_PARTS]
    for want, group in ((raw_l, listen), (raw_r, read)):
        winners = set(rng.sample(range(len(group)), want))
        for i, item in enumerate(group):
            correct_id, wrong_ids = options_by_q[item.question_id]
            item.selected_option_id = correct_id if i in winners else rng.choice(wrong_ids)
            item.is_correct = i in winners
    attempt.status = "submitted"
    attempt.submitted_at = datetime.now(UTC)
    attempt.elapsed_seconds = 1800
    attempt.listening_raw = raw_l
    attempt.reading_raw = raw_r
    db.commit()

    result = analyze(db, attempt)
    total = result.listening_scaled + result.reading_scaled
    print(
        f"VERDICT: {total} ({result.listening_scaled}L + {result.reading_scaled}R) "
        f"band {result.listening_low + result.reading_low}-{result.listening_high + result.reading_high} "
        f"CEFR {result.cefr_overall} (L {result.cefr_listening} / R {result.cefr_reading})"
    )
    print("study plans now:", db.scalar(
        select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == USER_ID)
    ))


if __name__ == "__main__":
    main()
