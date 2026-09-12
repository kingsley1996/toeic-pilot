"""Bài test đầu vào — `placement.py` (SPEC-PLACEMENT).

Máy thi là máy thi thật (`POST /attempts` tái nguyên vẹn); ở đây chỉ có ba
thứ: CỔNG (được làm lại không — cooldown 7 ngày), mốc tự khai trước khi làm,
và PHÁN QUYẾT sau khi nộp (ước lượng v1 + CEFR). Điểm placement là ước lượng,
không bao giờ ghi vào `total_scaled` của lượt làm — hai thang khác nhau.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.attempt import open_attempt
from app.core.database import get_db
from app.models import (
    Attempt,
    AttemptItem,
    PlacementResult,
    PracticeTest,
    StudyPlan,
    StudyPlanItem,
    User,
    UserProfile,
)
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
    """Một đề đầu vào, rút NGẪU NHIÊN trong nhóm admin đang bật.

    Trước đây đúng một đề được published mỗi thời điểm, và lý do cũ vẫn đáng
    nhắc: hai người làm hai đề khác nhau mà điểm vẫn được đặt cạnh nhau. Đổi
    sang nhóm là chấp nhận đánh đổi ấy để lấy hai thứ — người làm lại sau bảy
    ngày không gặp đúng đề cũ, và một đề bị lộ không kéo theo cả hệ.

    Cái giữ cho việc so sánh còn nghĩa là **bảng quy đổi**: điểm scaled tính
    bằng `score_conversion` của chính đề đã làm, nên hai form khác nhau vẫn quy
    về một thang. Đề nào vào nhóm mà thiếu bảng quy đổi đúng thì đó là chỗ hỏng,
    không phải phép rút ngẫu nhiên.

    `placement_result` trỏ `attempt_id`, và `attempt` giữ `test_id` — nên "ai
    làm đề nào" luôn tra được, kể cả sau khi một đề bị lưu trữ.
    """
    pool = list(
        db.scalars(
            select(PracticeTest).where(
                PracticeTest.is_placement.is_(True), PracticeTest.status == "published"
            )
        )
    )
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có đề placement nào được xuất bản"
        )
    # `random`, không `func.random()`: một câu ORDER BY ngẫu nhiên ở database
    # quét cả bảng và không test được mà không giả lập driver. Nhóm này có vài
    # hàng, nên rút ở Python vừa rẻ vừa thay được trong bài test.
    return random.choice(pool)


def _own_attempt(db: Session, attempt_id: uuid.UUID, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


def _aware(dt: datetime) -> datetime:
    # SQLite trả naive (giá trị là UTC); Postgres trả aware. Chuẩn hoá một chỗ.
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _pending(db: Session, user: User) -> PlacementResult | None:
    return db.scalar(
        select(PlacementResult).where(
            PlacementResult.user_id == user.id,
            PlacementResult.estimator_version == "pending",
        )
    )


def _answered(db: Session, attempt: Attempt) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(AttemptItem)
            .where(
                AttemptItem.attempt_id == attempt.id,
                AttemptItem.selected_option_id.is_not(None),
            )
        )
        or 0
    )


def _settle_pending(db: Session, user: User) -> None:
    """Kết một hàng "pending" mà lượt của nó đã hết vòng đời.

    Cùng luật với "hết giờ thì chốt ở lần chạm tiếp theo" của máy thi: không có
    tiến trình nền nào ở đây, nên một lượt bỏ dở chỉ được dọn khi có người gõ
    cửa. Chỉ gọi từ POST — nó ghi.

    Hai lối ra, và sự khác nhau giữa chúng là điều đáng nhớ: một lượt đã chốt
    mà KHÔNG có câu trả lời nào thì bị xoá, không thành phán quyết. Chấm nó ra
    A1 với 0 câu đúng — `_finalise` chấm ô trống là sai, đúng cho đề thi — rồi
    khoá người ta bảy ngày với một trình độ họ chưa từng làm bài để có.
    """
    row = _pending(db, user)
    if row is None:
        return
    attempt = db.get(Attempt, row.attempt_id)
    if attempt is None:
        db.delete(row)
        db.commit()
        return
    if attempt.status == "in_progress":
        return
    if _answered(db, attempt) == 0:
        db.delete(row)
        db.commit()
        return
    analyze(db, attempt)


def _open_checkin_exists(db: Session, user_id: uuid.UUID) -> bool:
    """Kế hoạch HIỆN HÀNH còn ô `mini_test` chưa khép không?

    Đây là cái cổng thứ hai của lượt đo lại (sau cooldown): từ bản "retest dựa
    theo kế hoạch", một người đã có phán quyết chỉ được bấm làm lại khi lịch
    của họ hẹn một ô kiểm tra còn mở. Ô khép đúng cách `_plan_public` đếm —
    lượt placement nộp sau `plan.created_at` khép lần lượt từng ô — nên con số
    ở đây và dấu ✓ trên lịch không thể lệch nhau.

    Không có kế hoạch, hoặc kế hoạch không hẹn ô nào (thi ≤14 ngày → nước rút
    không đo lại, hay đã đo hết các tuần) → trả False: người học phải tạo /
    "Sinh lại" kế hoạch để mở nhịp đo mới, chứ không đo tùy hứng.
    """
    plan = db.scalar(
        select(StudyPlan)
        .where(StudyPlan.user_id == user_id, StudyPlan.is_current.is_(True))
        .order_by(StudyPlan.created_at.desc())
        .limit(1)
    )
    if plan is None:
        return False
    mini_slots = db.scalar(
        select(func.count())
        .select_from(StudyPlanItem)
        .where(StudyPlanItem.plan_id == plan.id, StudyPlanItem.kind == "mini_test")
    )
    if not mini_slots:
        return False
    retakes = db.scalar(
        select(func.count(Attempt.id))
        .join(PracticeTest, PracticeTest.id == Attempt.test_id)
        .where(
            Attempt.user_id == user_id,
            PracticeTest.kind == "placement",
            Attempt.status == "submitted",
            Attempt.submitted_at.is_not(None),
            # Seed loại tường minh, đúng như `_plan_public`: trên SQLite
            # `created_at` chỉ chính xác tới GIÂY, một kế hoạch sinh trong cùng
            # giây với lượt seed sẽ đếm lượt đó là retake nếu chỉ so `>=` —
            # ô kiểm tra bị "khép" ngay khi vừa sinh ra.
            Attempt.id != plan.placement_attempt_id,
            Attempt.submitted_at >= plan.created_at,
        )
    )
    return mini_slots > (retakes or 0)


def _gate(db: Session, user: User) -> PlacementGate:
    # Cooldown đếm giữa hai PHÁN QUYẾT, không giữa hai lần bấm nút. Một hàng
    # "pending" là lượt chưa có kết quả; tính nó vào cooldown nghĩa là mở nhầm
    # bài rồi đóng tab đã tiêu mất bảy ngày.
    result = db.scalar(
        select(PlacementResult)
        .where(
            PlacementResult.user_id == user.id,
            PlacementResult.estimator_version != "pending",
        )
        .order_by(PlacementResult.created_at.desc())
        .limit(1)
    )
    pending = _pending(db, user)
    # Chỉ lượt CÒN DỞ mới là "đang làm dở". Đọc mỗi hàng pending thì một lượt
    # đã nộp mà chưa ai mở phân tích vẫn hiện nút "Tiếp tục" — bấm vào chỉ để
    # nhìn một bài đã chốt.
    running = pending
    if pending is not None:
        attempt = db.get(Attempt, pending.attempt_id)
        if attempt is None or attempt.status != "in_progress":
            running = None
    cooldown_ok = result is None or datetime.now(UTC) - _aware(result.created_at) >= timedelta(
        days=RETAKE_COOLDOWN_DAYS
    )
    # Lượt ĐẦU (chưa phán quyết) luôn được bấm; từ phán quyết thứ hai trở đi
    # còn cần một ô kiểm tra còn mở của kế hoạch — retest là nhịp của kế
    # hoạch, không phải nút tự do.
    checkin_scheduled = result is None or _open_checkin_exists(db, user.id)
    can_start = cooldown_ok and checkin_scheduled
    next_at = None
    if result is not None and not cooldown_ok:
        next_at = _aware(result.created_at) + timedelta(days=RETAKE_COOLDOWN_DAYS)
    profile = db.get(UserProfile, user.id)
    return PlacementGate(
        can_start=can_start,
        cooldown_ok=cooldown_ok,
        checkin_scheduled=checkin_scheduled,
        next_available_at=next_at,
        in_progress_attempt_id=str(running.attempt_id) if running else None,
        latest_attempt_id=str(result.attempt_id) if result else None,
        # Dải tổng = cộng hai dải section. Trên đề thật hai section không độc
        # lập tới vậy, nhưng làm tròn thêm ở đây là thêm sai số giả.
        latest_cefr_overall=result.cefr_overall if result else None,
        latest_total_low=(result.listening_low + result.reading_low) if result else None,
        latest_total_high=(result.listening_high + result.reading_high) if result else None,
        latest_total_scaled=((result.listening_scaled + result.reading_scaled) if result else None),
        # Prefill từ profile — người dùng thấy giá trị cũ, đổi thì ghi về.
        profile_target_score=profile.target_score if profile else None,
        profile_exam_date=profile.exam_date if profile else None,
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
    _settle_pending(db, user)
    gate_now = _gate(db, user)
    if gate_now.in_progress_attempt_id:
        return gate_now
    if not gate_now.can_start:
        # Hai lý do, hai câu khác nhau — gộp một là nói dối một nửa: người đã
        # có kế hoạch mà còn chờ 7 ngày đừng bị bảo "hãy tạo kế hoạch", và
        # người chưa có ô hẹn đừng tưởng chờ thêm bảy ngày là được đo.
        detail = (
            f"Được làm lại mỗi {RETAKE_COOLDOWN_DAYS} ngày một lần."
            if not gate_now.cooldown_ok
            else "Lượt đo lại theo nhịp của kế hoạch học — hãy tạo hoặc "
            '"Sinh lại" kế hoạch để mở ô kiểm tra.'
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    test = _placement_test(db)
    # Mục tiêu điền ở đây là NGUỒN DUY NHẤT: ghi thẳng về user_profile — form
    # đã prefill giá trị cũ nên submit là một hành động người dùng nhìn thấy.
    profile = db.get(UserProfile, user.id)
    if profile is not None:
        if body.target_score is not None:
            profile.target_score = body.target_score
        if body.exam_date is not None:
            profile.exam_date = body.exam_date
    # `open_attempt`, không phải route `POST /attempts`: route ấy nay từ chối đề
    # placement, vì đi thẳng vào nó là đi vòng qua cả cổng lẫn hàng "pending".
    state = open_attempt(
        db, test, AttemptStart(test_slug=test.slug, review_mode="exam", parts=[]), user
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
            listening_scaled=0,
            reading_scaled=0,
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
    if not attempt.test.is_placement:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Không phải lượt làm placement"
        )
    if attempt.status == "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phiên chưa nộp")
    # Không phán quyết trên một lượt không có câu trả lời nào. `_finalise` chấm
    # ô trống là SAI (đúng cho đề thi), nên một lượt mở ra rồi bỏ đó tới hết giờ
    # sẽ ra A1 với 0 câu đúng — một trình độ người ta chưa từng làm bài để có,
    # ghi vĩnh viễn và khoá cổng bảy ngày.
    if _answered(db, attempt) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bài này không có câu trả lời nào nên không xếp được trình độ.",
        )
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
        listening_scaled=row.listening_scaled,
        reading_scaled=row.reading_scaled,
        total_scaled=row.listening_scaled + row.reading_scaled,
        listening_band=PlacementBand(low=row.listening_low, high=row.listening_high),
        reading_band=PlacementBand(low=row.reading_low, high=row.reading_high),
        total_band=PlacementBand(
            low=row.listening_low + row.reading_low,
            high=row.listening_high + row.reading_high,
        ),
        cefr_listening=row.cefr_listening,
        cefr_reading=row.cefr_reading,
        cefr_overall=row.cefr_overall,
        self_reported_score=row.self_reported_score,
        target_score=row.target_score,
        elapsed_seconds=attempt.elapsed_seconds,
        created_at=row.created_at,
        strengths=strengths,
        weaknesses=weaknesses,
    )
