"""So sánh planner V1/V2 — `admin_planner.py` (SPEC-PLACEMENT §5).

Một màn, hai endpoint: GET đọc các lượt so sánh đã LƯU + tổng hợp sổ gọi
model; POST chạy so sánh trên một lượt placement — POST là lượt gọi model
thật (tiền + ~54 giây), nên nó là hành động có nút bấm, không phải tác dụng
phụ của việc mở trang.

`require_role("admin")`: chi phí model chạy trên tiền của hệ, và danh sách
người học là dữ liệu người dùng.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models import Attempt, PlacementResult, PlannerEval, StudyPlan, User, UserProfile
from app.services.study_planner import budget_for, weak_items

router = APIRouter(prefix="/admin/planner-compare", tags=["admin"])

can_view = require_role("admin")

FEATURE = "study_plan"


class AttemptOption(BaseModel):
    attempt_id: str
    email: str
    started_at: str
    cefr_overall: str | None
    weak_count: int
    plan_source: str | None


class EvalItem(BaseModel):
    label: str
    kind: str
    reason: str | None


class EvalRow(BaseModel):
    id: str
    attempt_id: str
    email: str
    weak_count: int
    v1_items: list[EvalItem]
    v2_items: list[EvalItem] | None
    coverage: float | None
    dangling: int
    model: str | None
    cost_usd: float | None
    latency_ms: int
    error: str | None
    created_at: str


class LlmStats(BaseModel):
    ok: int
    error: int
    avg_cost_usd: float | None
    avg_latency_ms: int | None
    avg_completion_tokens: int | None


class ComparePayload(BaseModel):
    attempts: list[AttemptOption]
    rows: list[EvalRow]
    stats: LlmStats


def _item(v: dict[str, Any]) -> EvalItem:
    return EvalItem(label=v.get("label", ""), kind=v.get("kind", ""), reason=v.get("reason"))


def _row(db: Session, ev: PlannerEval) -> EvalRow:
    user = db.get(User, ev.user_id)
    return EvalRow(
        id=str(ev.id),
        attempt_id=str(ev.attempt_id),
        email=user.email if user else "?",
        weak_count=ev.weak_count,
        v1_items=[_item(i) for i in ev.v1_items],
        v2_items=[_item(i) for i in ev.v2_items] if ev.v2_items else None,
        coverage=float(ev.coverage) if ev.coverage is not None else None,
        dangling=ev.dangling,
        model=ev.model,
        cost_usd=float(ev.cost_usd) if ev.cost_usd is not None else None,
        latency_ms=ev.latency_ms,
        error=ev.error,
        created_at=ev.created_at.isoformat(),
    )


@router.get("", response_model=ComparePayload)
def compare_data(
    limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
    _: User = Depends(can_view),
) -> ComparePayload:
    """Các lượt placement đã phân tích gần nhất (để chọn chạy) + kết quả đã lưu
    + tổng hợp sổ gọi model."""
    analyzed = db.execute(
        select(
            Attempt,
            PlacementResult.cefr_overall,
            User.email,
        )
        .join(PlacementResult, PlacementResult.attempt_id == Attempt.id)
        .join(User, User.id == Attempt.user_id)
        .where(PlacementResult.estimator_version != "pending")
        .order_by(PlacementResult.created_at.desc())
        .limit(limit)
    ).all()
    current_plans = {
        p.placement_attempt_id: p.source
        for p in db.scalars(select(StudyPlan).where(StudyPlan.is_current.is_(True))).all()
    }
    options = []
    for attempt, cefr, email in analyzed:
        weak = weak_items(db, attempt)
        options.append(
            AttemptOption(
                attempt_id=str(attempt.id),
                email=email,
                started_at=attempt.started_at.isoformat(),
                cefr_overall=cefr,
                weak_count=len(weak),
                plan_source=current_plans.get(attempt.id),
            )
        )

    rows = [
        _row(db, ev)
        for ev in db.scalars(
            select(PlannerEval).order_by(PlannerEval.created_at.desc()).limit(limit)
        )
    ]

    # Sổ gọi model của TÍNH NĂNG này — nơi duy nhất trả lời "V2 tốn bao nhiêu,
    # hỏng bao nhiêu lần" trên quy mô, không chỉ trên các lượt so sánh thủ công.
    from app.models import AiInteraction

    stats_rows = db.execute(
        select(
            AiInteraction.status,
            func.avg(AiInteraction.cost_usd),
            func.avg(AiInteraction.latency_ms),
            func.avg(AiInteraction.completion_tokens),
            func.count(),
        )
        .where(AiInteraction.feature == FEATURE)
        .group_by(AiInteraction.status)
    ).all()
    by_status = {r[0]: r for r in stats_rows}
    ok_row = by_status.get("ok")

    def _num(value: Any) -> float | None:
        return float(value) if value is not None else None

    stats = LlmStats(
        ok=int(ok_row[4]) if ok_row else 0,
        error=int(by_status["error"][4]) if "error" in by_status else 0,
        avg_cost_usd=_num(ok_row[1]) if ok_row else None,
        avg_latency_ms=int(ok_row[2]) if ok_row and ok_row[2] is not None else None,
        avg_completion_tokens=int(ok_row[3]) if ok_row and ok_row[3] is not None else None,
    )
    return ComparePayload(attempts=options, rows=rows, stats=stats)


class RunRequest(BaseModel):
    attempt_id: str


@router.post("/run", response_model=EvalRow, status_code=status.HTTP_201_CREATED)
def run_compare(
    body: RunRequest,
    db: Session = Depends(get_db),
    _: User = Depends(can_view),
) -> EvalRow:
    """Chạy so sánh trên một lượt: V1 (miễn phí) + V2 (gọi model thật). Kết
    quả LƯU — trang đọc chỉ đọc, không ai mở trang là tốn một lượt gọi."""
    from app.api.deps import get_gateway
    from app.content.eval_planner import _rule_select
    from app.services.planner_llm import llm_select

    attempt = db.get(Attempt, uuid.UUID(body.attempt_id))
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    weak = weak_items(db, attempt)
    profile = db.get(UserProfile, attempt.user_id)
    today = datetime.now(UTC).date()
    budget = budget_for(today, profile.exam_date if profile else None)

    started = datetime.now(UTC)
    v2_items: list[Any] | None = None
    error: str | None = None
    try:
        v2_items = llm_select(
            get_gateway(db),
            db,
            weak=weak,
            budget=budget,
            target_score=profile.target_score if profile else None,
            exam_date=profile.exam_date if profile else None,
            raw_summary=f"Nghe {attempt.listening_raw}/42, Đọc {attempt.reading_raw}/42",
        )
    except Exception as exc:  # noqa: BLE001 — lỗi model là một KẾT QUẢ so sánh
        error = str(exc)
    latency = int((datetime.now(UTC) - started).total_seconds() * 1000)

    # Model/cost lấy từ sổ gọi — nơi duy nhất ghi được chúng, và lượt gọi vừa
    # rồi là lượt mới nhất của tính năng này.
    from app.models import AiInteraction

    last_call = db.scalar(
        select(AiInteraction)
        .where(AiInteraction.feature == FEATURE)
        .order_by(AiInteraction.created_at.desc())
        .limit(1)
    )
    model = last_call.model if last_call else None
    cost = float(last_call.cost_usd) if last_call and last_call.cost_usd is not None else None
    if last_call is not None and last_call.status != "ok":
        error = error or last_call.error

    rule_items = _rule_select(db, attempt, weak, budget)
    coverage = None
    dangling = 0
    if rule_items and v2_items is not None:
        rule_keys = {(i.kind, i.label) for i in rule_items}
        llm_keys = {(i.kind, i.label) for i in v2_items}
        coverage = len(rule_keys & llm_keys) / len(rule_keys)
        dangling = sum(1 for i in v2_items if i.kind == "grammar_lesson" and i.ref_id is None)

    ev = PlannerEval(
        attempt_id=attempt.id,
        user_id=attempt.user_id,
        weak_count=len(weak),
        v1_items=[{"label": i.label, "kind": i.kind, "reason": i.reason} for i in rule_items],
        v2_items=(
            [{"label": i.label, "kind": i.kind, "reason": i.reason} for i in v2_items]
            if v2_items is not None
            else None
        ),
        coverage=coverage,
        dangling=dangling,
        source="llm" if v2_items is not None else "rule_fallback",
        model=model,
        cost_usd=cost,
        latency_ms=latency,
        error=error,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return _row(db, ev)
