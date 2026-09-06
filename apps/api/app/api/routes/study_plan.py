"""Kế hoạch học — `study_plan.py` (SPEC-PLACEMENT §5–§6).

GET trả kế hoạch hiện hành KÈM tiến độ suy từ bản ghi học thật (bài ngữ pháp
đã hoàn thành, phiên part đã làm) — không có cột tick nào để lệch thực tế.
POST `/generate` sinh từ một lượt placement đã phân tích; đi qua planner V1
(rule-based), lượt llm có cột `source` sẵn nhưng chưa có đường ghi (lát 3).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import (
    Attempt,
    GrammarLessonCompletion,
    PartSession,
    PartSessionItem,
    PlacementResult,
    StudyPlan,
    StudyPlanItem,
    User,
)
from app.schemas.study_plan import StudyPlanItemPublic, StudyPlanPublic
from app.services.study_planner import generate_plan

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


class GenerateFromPlacement(BaseModel):
    """Không gửi gì = dùng lượt placement phân tích gần nhất."""

    attempt_id: uuid.UUID | None = None


def _current_plan(db: Session, user_id: uuid.UUID) -> StudyPlan | None:
    return db.scalar(
        select(StudyPlan)
        .where(StudyPlan.user_id == user_id, StudyPlan.is_current.is_(True))
        .order_by(StudyPlan.created_at.desc())
        .limit(1)
    )


def _plan_public(db: Session, user_id: uuid.UUID, plan: StudyPlan) -> StudyPlanPublic:
    items = list(
        db.scalars(
            select(StudyPlanItem)
            .where(StudyPlanItem.plan_id == plan.id)
            .order_by(StudyPlanItem.position)
        )
    )
    # Bài ngữ pháp: hoàn thành là hàng có thật; revoked_at không NULL là đã bỏ.
    done_lessons = {
        lid
        for (lid,) in db.execute(
            select(GrammarLessonCompletion.lesson_id).where(
                GrammarLessonCompletion.user_id == user_id,
                GrammarLessonCompletion.revoked_at.is_(None),
            )
        ).all()
    }
    # Part drill: một phiên luyện của part đó SINH SAU lúc kế hoạch có — phiên
    # cũ hơn kế hoạch không đếm là tiến độ của lời khuyên kế hoạch đưa ra. Và
    # phiên phải có ít nhất MỘT câu trả lời: mở phiên rồi đóng không trả lời
    # câu nào là chưa luyện, không được tính xong.
    answered_sessions = select(PartSessionItem.session_id).where(
        PartSessionItem.answered_at.is_not(None)
    )
    done_parts = {
        int(part)
        for (part,) in db.execute(
            select(PartSession.part)
            .where(
                PartSession.user_id == user_id,
                PartSession.created_at >= plan.created_at,
                PartSession.id.in_(answered_sessions),
            )
            .distinct()
        ).all()
    }
    public_items = [
        StudyPlanItemPublic(
            position=item.position,
            kind=item.kind,
            part=item.part,
            ref_id=str(item.ref_id) if item.ref_id else None,
            label=item.label,
            reason=item.reason,
            done=(
                item.ref_id in done_lessons
                if item.kind == "grammar_lesson"
                else item.part in done_parts
            ),
        )
        for item in items
    ]
    return StudyPlanPublic(
        id=str(plan.id),
        placement_attempt_id=str(plan.placement_attempt_id),
        target_score=plan.target_score,
        exam_date=plan.exam_date,
        source=plan.source,
        created_at=plan.created_at,
        items=public_items,
        done_count=sum(1 for i in public_items if i.done),
    )


@router.get("", response_model=StudyPlanPublic | None)
def get_plan(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StudyPlanPublic | None:
    plan = _current_plan(db, user.id)
    return _plan_public(db, user.id, plan) if plan else None


@router.post("/generate", response_model=StudyPlanPublic, status_code=status.HTTP_201_CREATED)
def generate(
    body: GenerateFromPlacement | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudyPlanPublic:
    """Sinh kế hoạch từ lượt placement chỉ định, hoặc lượt phân tích gần nhất.

    KHÔNG sinh lại mù quáng: trùng lượt với kế hoạch hiện hành → trả lại kế
    hoạch cũ; lượt chỉ định CŨ hơn → cũng trả lại kế hoạch cũ. Bấm "Tạo kế
    hoạch" từ một kết quả cũ không được phép thay kế hoạch sinh từ kết quả
    mới hơn — đúng một lời khuyên cho một thời điểm, không viết lại sau lưng.
    """
    attempt_id = body.attempt_id if body else None
    if attempt_id is not None:
        attempt = db.get(Attempt, attempt_id)
        if attempt is None or attempt.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    else:
        attempt = db.scalar(
            select(Attempt)
            .join(PlacementResult, PlacementResult.attempt_id == Attempt.id)
            .where(
                Attempt.user_id == user.id,
                PlacementResult.estimator_version != "pending",
            )
            .order_by(PlacementResult.created_at.desc())
            .limit(1)
        )
        if attempt is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chưa có bài test đầu vào nào được phân tích",
            )
    current = _current_plan(db, user.id)
    if current is not None:
        source = db.get(Attempt, current.placement_attempt_id)
        # `started_at` hai lượt so trong cùng một DB nên luôn cùng múi; trùng
        # lượt thì bằng nhau — rơi vào cả hai nhánh "không sinh mới". `source`
        # không thể None: kế hoạch luôn trỏ lượt placement có thật (N4), nhưng
        # `db.get` trả Optional nên phải chốt trước khi so.
        if source is not None and (
            source.id == attempt.id or attempt.started_at <= source.started_at
        ):
            return _plan_public(db, user.id, current)
    try:
        plan = generate_plan(db, user.id, attempt)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _plan_public(db, user.id, plan)
