"""Bài test đầu vào — `placement.py` (SPEC-PLACEMENT).

Máy thi là máy thi thật (`POST /attempts` tái nguyên vẹn); ở đây chỉ có ba
thứ: CỔNG (được làm lại không — cooldown 7 ngày), mốc tự khai trước khi làm,
và PHÁN QUYẾT sau khi nộp (ước lượng v1 + CEFR). Điểm placement là ước lượng,
không bao giờ ghi vào `total_scaled` của lượt làm — hai thang khác nhau.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.attempt import start_attempt
from app.core.database import get_db
from app.models import Attempt, PlacementResult, PracticeTest, User
from app.schemas.placement import (
    PlacementBand,
    PlacementGate,
    PlacementResultPublic,
    PlacementStart,
)
from app.schemas.practice import AttemptStart
from app.services import attempt_skills
from app.services.placement import analyze

router = APIRouter(prefix="/placement", tags=["placement"])

RETAKE_COOLDOWN_DAYS = 7
# Định mức dày enough: một kỹ năng dưới 3 câu thì tỉ lệ của nó là nhiễu
# (1/2 hay 2/3 đều có thể là trúng số), không đáng xếp vào mạnh hay yếu.
MIN_SKILL_SAMPLE = 3


def _placement_test(db: Session) -> PracticeTest:
    test = db.scalar(
        select(PracticeTest).where(
            PracticeTest.is_placement.is_(True), PracticeTest.status == "published"
        )
    )
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có đề placement nào được xuất bản"
        )
    return test


def _own_attempt(db: Session, attempt_id: uuid.UUID, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


def _aware(dt: datetime) -> datetime:
    # SQLite trả naive (giá trị là UTC); Postgres trả aware. Chuẩn hoá một chỗ.
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _gate(db: Session, user: User) -> PlacementGate:
    last = db.scalar(
        select(PlacementResult)
        .where(PlacementResult.user_id == user.id)
        .order_by(PlacementResult.created_at.desc())
        .limit(1)
    )
    running = db.scalar(
        select(PlacementResult).where(
            PlacementResult.user_id == user.id,
            PlacementResult.estimator_version == "pending",
        )
    )
    can_start = last is None or datetime.now(UTC) - _aware(last.created_at) >= timedelta(
        days=RETAKE_COOLDOWN_DAYS
    )
    next_at = None
    if last is not None and not can_start:
        next_at = _aware(last.created_at) + timedelta(days=RETAKE_COOLDOWN_DAYS)
    # "pending" là lượt đang dở chứ không phải kết quả: trình độ của nó
    # chưa tồn tại, hiện hàng đó là hiện một phán quyết chưa từng có.
    result = None if last is None or last.estimator_version == "pending" else last
    return PlacementGate(
        can_start=can_start,
        next_available_at=next_at,
        in_progress_attempt_id=str(running.attempt_id) if running else None,
        latest_attempt_id=str(last.attempt_id) if last else None,
        # Dải tổng = cộng hai dải section. Trên đề thật hai section không độc
        # lập tới vậy, nhưng làm tròn thêm ở đây là thêm sai số giả.
        latest_cefr_overall=result.cefr_overall if result else None,
        latest_total_low=(result.listening_low + result.reading_low) if result else None,
        latest_total_high=(result.listening_high + result.reading_high) if result else None,
    )


@router.get("/gate", response_model=PlacementGate)
def gate(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PlacementGate:
    return _gate(db, user)


@router.post("/start", response_model=PlacementGate, status_code=status.HTTP_201_CREATED)
def start(
    body: PlacementStart,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlacementGate:
    """Mở lượt placement + ghi mốc tự khai. Lượt đang dở thì trả lại lượt đó —
    tạo lượt thứ hai song song là hai phán quyết cho cùng một tuần."""
    gate_now = _gate(db, user)
    if gate_now.in_progress_attempt_id:
        return gate_now
    if not gate_now.can_start:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Được làm lại mỗi {RETAKE_COOLDOWN_DAYS} ngày một lần.",
        )
    test = _placement_test(db)
    state = start_attempt(
        AttemptStart(test_slug=test.slug, review_mode="exam", parts=[]), db=db, current_user=user
    )
    # Hàng kết quả "pending" cầm mốc tự khai cho tới khi nộp bài, khi đó
    # `analyze` điền phán quyết thật vào đúng hàng này.
    db.add(
        PlacementResult(
            attempt_id=uuid.UUID(state.id),
            user_id=user.id,
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
            self_reported_score=body.self_reported_score,
            target_score=body.target_score,
        )
    )
    db.commit()
    return _gate(db, user)


@router.post("/attempts/{attempt_id}/analyze", response_model=PlacementResultPublic)
def analyze_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlacementResultPublic:
    attempt = _own_attempt(db, attempt_id, user)
    if attempt.test.is_placement is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Không phải lượt làm placement"
        )
    if attempt.status == "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phiên chưa nộp")
    row = analyze(db, attempt)

    skills = attempt_skills.skill_breakdown(db, attempt)
    ranked = [s for s in skills if s.count >= MIN_SKILL_SAMPLE]
    strengths = [s.name for s in ranked if s.correct / s.count >= 0.7]
    weaknesses = [s.name for s in ranked if s.correct / s.count < 0.5]
    return PlacementResultPublic(
        attempt_id=str(attempt.id),
        estimator_version=row.estimator_version,
        listening_raw=row.listening_raw,
        reading_raw=row.reading_raw,
        listening_band=PlacementBand(low=row.listening_low, high=row.listening_high),
        reading_band=PlacementBand(low=row.reading_low, high=row.reading_high),
        cefr_listening=row.cefr_listening,
        cefr_reading=row.cefr_reading,
        cefr_overall=row.cefr_overall,
        self_reported_score=row.self_reported_score,
        target_score=row.target_score,
        created_at=row.created_at,
        strengths=strengths,
        weaknesses=weaknesses,
    )
