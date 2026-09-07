"""Kế hoạch học — `study_plan.py` (SPEC-PLACEMENT §5–§6).

GET trả kế hoạch hiện hành KÈM tiến độ suy từ bản ghi học thật (bài ngữ pháp
đã hoàn thành, phiên part đã làm) — không có cột tick nào để lệch thực tế.
POST `/generate` sinh từ một lượt placement đã phân tích, qua planner V1
(rule) hoặc V2 (llm, chọn từ danh sách ứng viên) — V2 hỏng ở bất kỳ đâu thì
rơi về V1 thay vì báo lỗi cho người học.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_gateway
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
    UserProfile,
)
from app.schemas.study_plan import StudyPlanItemPublic, StudyPlanPublic
from app.services.study_planner import generate_plan, write_plan

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


class GenerateFromPlacement(BaseModel):
    """Không gửi gì = dùng lượt placement phân tích gần nhất.

    `source`: `rule` (mặc định) hoặc `llm`. `llm` đi qua gateway — tính năng
    `study_plan` chưa cấu hình/tắt/hỏng thì rơi về `rule`, KHÔNG lỗi: một kế
    hoạch rule luôn tốt hơn một màn hình báo lỗi cho người học.
    """

    attempt_id: uuid.UUID | None = None
    source: str = Field(default="rule", pattern="^(rule|llm)$")


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
        source_attempt = db.get(Attempt, current.placement_attempt_id)
        # `started_at` hai lượt so trong cùng một DB nên luôn cùng múi; trùng
        # lượt thì bằng nhau — rơi vào cả hai nhánh "không sinh mới". `source`
        # không thể None: kế hoạch luôn trỏ lượt placement có thật (N4), nhưng
        # `db.get` trả Optional nên phải chốt trước khi so.
        #
        # Không sinh mới chỉ khi MỌI thứ không đổi: lượt cũ hơn hoặc bằng, VÀ
        # cùng source. Đổi source (rule ↔ llm) là muốn nhìn planner khác đọc
        # cùng một kết quả — sinh lại.
        same_or_older = source_attempt is not None and (
            source_attempt.id == attempt.id or attempt.started_at <= source_attempt.started_at
        )
        same_source = body is not None and current.source == body.source
        if same_or_older and same_source:
            return _plan_public(db, user.id, current)
    if body is not None and body.source == "llm":
        try:
            plan = _generate_llm(db, user.id, attempt)
        except Exception:  # noqa: BLE001 — mọi hỏng hóc của đường LLM rơi về rule
            plan = generate_plan(db, user.id, attempt)
        return _plan_public(db, user.id, plan)
    try:
        plan = generate_plan(db, user.id, attempt)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _plan_public(db, user.id, plan)


def _generate_llm(db: Session, user_id: uuid.UUID, attempt: Attempt) -> StudyPlan:
    """Planner V2: LLM chọn từ danh sách ứng viên. Hỏng ở bất kỳ bước nào →
    ném ra để nơi gọi rơi về V1."""
    from datetime import UTC, datetime

    from app.services.planner_llm import llm_select
    from app.services.study_planner import budget_for, weak_items

    profile = db.get(UserProfile, user_id)
    weak = weak_items(db, attempt)
    if not weak:
        raise ValueError("không có điểm yếu nào đủ mẫu số để lập kế hoạch")
    raw = db.get(PlacementResult, attempt.id)
    summary = (
        f"Nghe {raw.listening_raw}/{42 if raw.listening_raw else '?'} câu, "
        f"Đọc {raw.reading_raw}/{42 if raw.reading_raw else '?'} câu"
        if raw
        else "không có tóm tắt"
    )
    picks = llm_select(
        get_gateway(db),
        db,
        weak=weak,
        budget=budget_for(datetime.now(UTC).date(), profile.exam_date if profile else None),
        target_score=profile.target_score if profile else None,
        exam_date=profile.exam_date if profile else None,
        raw_summary=summary,
    )
    if picks is None:
        raise ValueError("LLM không trả được lựa chọn hợp lệ")
    return write_plan(db, user_id, attempt, picks, source="llm")
