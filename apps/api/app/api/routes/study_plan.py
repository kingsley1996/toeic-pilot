"""Kế hoạch học — `study_plan.py` (SPEC-PLACEMENT §5–§6).

GET trả kế hoạch hiện hành KÈM tiến độ suy từ bản ghi học thật (bài ngữ pháp
đã hoàn thành, phiên part đã làm) — không có cột tick nào để lệch thực tế.
GET cũng suy NGÀY cho từng mục chưa xong: `hôm nay (theo timezone profile) +
hạng_mục_chưa_xong // nhịp_buổi`. Ngày không lưu ở đâu cả — người học bỏ một
hôm thì lịch tự trôi, không có mục "quá hạn" giả. Người học xong sớm (hoặc
tăng `minutes_per_day`) thì lịch co lại — hàng đợi, không phải lịch cứng.

POST `/generate` sinh từ một lượt placement đã phân tích, qua planner V1
(rule) hoặc V2 (llm, chọn từ danh sách ứng viên) — V2 hỏng ở bất kỳ đâu thì
rơi về V1 thay vì báo lỗi cho người học.
"""

import uuid
from datetime import UTC, date, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_gateway
from app.core.database import get_db
from app.models import (
    Attempt,
    AttemptItem,
    GrammarLesson,
    GrammarLessonCompletion,
    PartSession,
    PartSessionItem,
    PlacementResult,
    PracticeTest,
    QuestionLabel,
    StudyPlan,
    StudyPlanItem,
    TestCollection,
    User,
    UserProfile,
)
from app.schemas.study_plan import (
    PlanEstimate,
    PlanEvaluationPublic,
    PlanFeasibility,
    PlanFocus,
    PlanItemKind,
    PlanMockOption,
    PlanPhase,
    PlanRetake,
    PlanTrendRow,
    PlanVersionPublic,
    StudyPlanItemPublic,
    StudyPlanPublic,
)
from app.services.progression import local_today
from app.services.study_planner import (
    DEFAULT_DAYS_PER_WEEK,
    DEFAULT_MINUTES_PER_DAY,
    EST_MINUTES,
    generate_plan,
    mock_link,
    mock_pool,
    pack_days,
    plan_insights,
    write_plan,
)

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


def _local_day(when: datetime, tz: str) -> date:
    """Ngày cục bộ của một timestamp — SQLite không trả `tzinfo`,Postgres có."""
    return local_today(when if when.tzinfo else when.replace(tzinfo=UTC), tz)


class GenerateFromPlacement(BaseModel):
    """Không gửi gì = dùng lượt placement phân tích gần nhất.

    `source`: `rule` (mặc định) hoặc `llm`. `llm` đi qua gateway — tính năng
    `study_plan` chưa cấu hình/tắt/hỏng thì rơi về `rule`, KHÔNG lỗi: một kế
    hoạch rule luôn tốt hơn một màn hình báo lỗi cho người học.
    """

    attempt_id: uuid.UUID | None = None
    source: str = Field(default="rule", pattern="^(rule|llm)$")
    # "Sinh lại" sau khi đổi đầu vào profile: không có cờ này thì trùng lượt +
    # trùng source luôn trả lại kế hoạch cũ (đúng cho bấm đúp, sai cho người
    # vừa đổi ngày thi) — lịch không bao giờ được trải lại.
    force: bool = False


class ItemTick(BaseModel):
    """Hai hành động trên MỘT endpoint vì cả hai cùng trả lại cả kế hoạch:
    `done` = khẳng định của người học; `test_id` = đổi đề thi thử trước khi
    nộp (chọn từ danh sách `mock_options` của payload)."""

    done: bool | None = None
    test_id: uuid.UUID | None = None


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
    # Kèm `created_at`: mục đã xong không còn trong hàng đợi để suy ngày từ
    # "hôm nay", nên ô tick trên lịch phải đứng đúng NGÀY THẬT nó hoàn thành —
    # nếu không, toàn bộ việc đã làm trôi về hôm nay và lịch thành hư cấu.
    done_lessons = {
        lesson_id: when
        for lesson_id, when in db.execute(
            select(GrammarLessonCompletion.lesson_id, GrammarLessonCompletion.created_at).where(
                GrammarLessonCompletion.user_id == user_id,
                GrammarLessonCompletion.revoked_at.is_(None),
            )
        ).all()
    }
    # Part drill: một phiên luyện của part đó SINH SAU lúc kế hoạch có — phiên
    # cũ hơn kế hoạch không đếm là tiến độ của lời khuyên kế hoạch đưa ra. Và
    # phiên phải có ít nhất MỘT câu trả lời: mở phiên rồi đóng không trả lời
    # câu nào là chưa luyện, không được tính xong. Ngày lấy là câu TRẢ LỜI ĐẦU
    # của phiên sớm nhất: phiên mở trước, trả lời sau thì ngày học là ngày trả
    # lời. `min()` trong SQL: Postgres trả tz-aware, SQLite naive — cả hai được
    # chuẩn hoá ở `_local_day` dưới.
    done_parts: dict[int, datetime] = {
        int(part): when
        for part, when in db.execute(
            select(PartSession.part, func.min(PartSessionItem.answered_at))
            .join(PartSessionItem, PartSessionItem.session_id == PartSession.id)
            .where(
                PartSession.user_id == user_id,
                PartSession.created_at >= plan.created_at,
                PartSessionItem.answered_at.is_not(None),
            )
            .group_by(PartSession.part)
        ).all()
    }
    # Đường tới bài học ngữ pháp là `topic/lesson`; kế hoạch chỉ lưu lesson id.
    # Nối thiếu bước này là mọi mục grammar trên plan dẫn vào "Không tải được
    # chủ đề này" — đã xảy ra thật, xem ROADMAP.
    lesson_topic = {
        lesson_id: str(topic_id)
        for lesson_id, topic_id in db.execute(
            select(GrammarLesson.id, GrammarLesson.topic_id).where(
                GrammarLesson.id.in_(
                    [item.ref_id for item in items if item.kind == "grammar_lesson"]
                )
            )
        ).all()
    }
    # Mục kiểm tra tự khép bằng BÀI NỘP, không bằng tick (API cũng từ chối
    # tick hai kind này): tuần thứ k hoàn thành khi có retake placement nộp
    # sau mốc sinh kế hoạch, lần theo thứ tự thời gian.
    retakes = list(
        db.scalars(
            select(Attempt.submitted_at)
            .join(PracticeTest, PracticeTest.id == Attempt.test_id)
            .where(
                Attempt.user_id == user_id,
                PracticeTest.kind == "placement",
                Attempt.status == "submitted",
                Attempt.id != plan.placement_attempt_id,
                Attempt.submitted_at.is_not(None),
                Attempt.submitted_at >= plan.created_at,
            )
            .order_by(Attempt.submitted_at)
        )
    )
    mock_refs = [item.ref_id for item in items if item.kind == "mock_test" and item.ref_id]
    mock_done: dict[uuid.UUID, datetime] = {}
    test_paths: dict[uuid.UUID, tuple[str, str | None]] = {}
    if mock_refs:
        for test_id, submitted in db.execute(
            select(Attempt.test_id, func.min(Attempt.submitted_at))
            .where(
                Attempt.user_id == user_id,
                Attempt.test_id.in_(mock_refs),
                Attempt.status == "submitted",
                Attempt.submitted_at.is_not(None),
                Attempt.submitted_at >= plan.created_at,
            )
            .group_by(Attempt.test_id)
        ).all():
            mock_done[test_id] = submitted
        # Đường tới đề thi thử: `learn/tests/{collection}/{test}` là route thật
        # của kho đề — thiếu collection thì fallback về cả kho, đừng bịa URL.
        for test_id, test_slug, coll_slug in db.execute(
            select(PracticeTest.id, PracticeTest.slug, TestCollection.slug)
            .outerjoin(TestCollection, TestCollection.id == PracticeTest.collection_id)
            .where(PracticeTest.id.in_(mock_refs))
        ).all():
            test_paths[test_id] = (test_slug, coll_slug)
    # Ngày của một mục KHÔNG lưu ở đâu cả — suy lúc đọc bằng `pack_days` trên
    # TOÀN BỘ vị trí (đã xong hay chưa đều chiếm chỗ), neo vào `starts_at` của
    # kế hoạch chứ không vào "hôm nay": tick một mục không được dịch chuyển
    # những mục còn lại — người học gọi lịch trôi theo từng cú bấm là "dồn
    # task", và họ đúng: lịch là lời hẹn đọc được, không phải khối nhảy. Bỏ
    # vài hôm thật thì mục quá hạn nằm lại quá khứ — nói thật, và có đường
    # tường minh "Dời lịch" (POST /repack) để xếp lại từ hôm nay.
    profile = db.get(UserProfile, user_id)
    tz = profile.timezone if profile else "UTC"
    today = local_today(datetime.now(UTC), tz)
    daily = (profile.minutes_per_day if profile else None) or DEFAULT_MINUTES_PER_DAY
    per_week = (profile.study_days_per_week if profile else None) or DEFAULT_DAYS_PER_WEEK
    anchor = plan.starts_at or _local_day(plan.created_at, tz)
    public_items: list[StudyPlanItemPublic] = []
    queue: list[tuple[int, int, str]] = []
    tests: list[tuple[int, int, str]] = []
    mini_seen = 0
    for item in items:
        when: datetime | None = (
            done_lessons.get(item.ref_id)
            if item.kind == "grammar_lesson"
            else done_parts.get(item.part)
            if item.kind == "part_drill"
            else None
        )
        if item.kind == "mini_test":
            mini_seen += 1
            when = retakes[mini_seen - 1] if mini_seen <= len(retakes) else None
        elif item.kind == "mock_test" and item.ref_id:
            when = mock_done.get(item.ref_id)
        # Hai nguồn xong giữ riêng: bản ghi học là sự kiện, `done_at` là khẳng
        # định của người học. Ngày hoàn thành ưu tiên sự kiện; tick tay đứng
        # ở NGÀY NÓ ĐƯỢC BẤM (quá khứ của nó là lúc người ta nhớ ra, không
        # phải lúc việc xảy ra).
        manual = item.done_at is not None
        done = when is not None or manual
        if item.kind in ("mini_test", "mock_test"):
            # Kiểm tra KHÔNG xếp theo hàng đợi — packer neo nó theo tuần
            # (retake đầu mỗi tuần, thi thử sát ngày thi); đã xong hay chưa
            # đều chiếm đúng ô đó, nếu không tick một bài sẽ dịch cả lịch.
            tests.append((item.position, EST_MINUTES[item.kind], item.kind))
        else:
            queue.append((item.position, EST_MINUTES[item.kind], item.kind))
        completed_on = None
        if when is not None:
            completed_on = _local_day(when, tz)
        elif item.done_at is not None:
            completed_on = _local_day(item.done_at, tz)
        slug_info = (
            test_paths.get(item.ref_id) if item.kind == "mock_test" and item.ref_id else None
        )
        public_items.append(
            StudyPlanItemPublic(
                position=item.position,
                kind=cast(PlanItemKind, item.kind),
                part=item.part,
                ref_id=str(item.ref_id) if item.ref_id else None,
                topic_id=lesson_topic.get(item.ref_id) if item.kind == "grammar_lesson" else None,
                label=item.label,
                reason=item.reason,
                phase=cast(PlanPhase | None, item.phase),
                est_minutes=EST_MINUTES[item.kind],
                test_slug=slug_info[0] if slug_info else None,
                collection_slug=slug_info[1] if slug_info else None,
                link=item.link,
                done=done,
                manual_done=manual,
                day=None,
                completed_on=completed_on,
            )
        )
    days = pack_days(queue, tests, anchor, daily, per_week, plan.exam_date)
    for pub in public_items:
        pub.day = days.get(pub.position)
    mock_options: list[PlanMockOption] = []
    if any(i.kind == "mock_test" for i in items):
        mock_options = [PlanMockOption(id=str(r[0]), title=r[3][:80]) for r in mock_pool(db)]
    insights = plan_insights(db, plan, profile, today)
    return StudyPlanPublic(
        id=str(plan.id),
        placement_attempt_id=str(plan.placement_attempt_id),
        target_score=plan.target_score,
        exam_date=plan.exam_date,
        source=plan.source,
        created_at=plan.created_at,
        items=public_items,
        # Đếm theo mục LÕI: UI chia cho số mục lõi, và nhịp nền tick tay thì
        # không nằm trong mẫu số đó — đếm cả hai là "8/3 mục đã xong", một lời
        # hứa hoàn thành bằng cách đánh dấu thứ không ai định khép. Mục kiểm
        # tra LÀ lời khuyên khép được (bằng bài nộp) nên nó nằm trong mẫu số.
        done_count=sum(
            1
            for i in public_items
            if i.done and i.kind in ("grammar_lesson", "part_drill", "mini_test", "mock_test")
        ),
        today=today,
        starts_at=anchor,
        minutes_per_day=daily,
        study_days_per_week=per_week,
        days_left=(plan.exam_date - today).days if plan.exam_date else None,
        estimate=(
            PlanEstimate(
                listening=insights.listening_scaled,
                reading=insights.reading_scaled,
                total=insights.estimated_total,
                band_low=insights.band_low,
                band_high=insights.band_high,
                cefr=insights.cefr,
            )
            if insights
            else None
        ),
        gap=insights.gap if insights else None,
        weeks_left=insights.weeks_left if insights else None,
        feasibility=cast(PlanFeasibility | None, insights.feasibility) if insights else None,
        top_focus=(
            [
                PlanFocus(
                    label=s.label_vi,
                    correct=s.correct,
                    total=s.total,
                    code=s.code,
                    part=s.part,
                )
                for s in insights.top_focus
            ]
            if insights
            else []
        ),
        why=insights.why if insights else None,
        mock_options=mock_options,
        version=plan.version,
        reason=plan.reason,
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
    `force=True` là lối thoát khi đầu vào profile đổi (ngày thi, phút/ngày):
    lịch được trải lại từ cùng một kết quả.
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
        forced = body is not None and body.force
        if same_or_older and same_source and not forced:
            return _plan_public(db, user.id, current)
    # §32: lý do của PHIÊN BẢN MỚI suy từ đúng hai hàng đang so — lượt đo khác,
    # hay đầu vào profile đổi. Cầm sẵn từ server để UI (và lịch sử) đọc được
    # "v3 mọc từ đâu" mà không phải đoán lại.
    profile = db.get(UserProfile, user.id)
    if current is None:
        reason = "Kế hoạch ban đầu"
    elif current.placement_attempt_id != attempt.id:
        reason = "Đo lại bằng bài kiểm tra đầu vào"
    elif current.target_score != (
        profile.target_score if profile else None
    ) or current.exam_date != (profile.exam_date if profile else None):
        reason = "Mục tiêu / ngày thi thay đổi"
    else:
        reason = "Sinh lại lịch theo thời gian học hiện tại"
    if body is not None and body.source == "llm":
        try:
            plan = _generate_llm(db, user.id, attempt, reason=reason)
        except Exception:  # noqa: BLE001 — mọi hỏng hóc của đường LLM rơi về rule
            plan = generate_plan(db, user.id, attempt, reason=reason)
        return _plan_public(db, user.id, plan)
    try:
        plan = generate_plan(db, user.id, attempt, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _plan_public(db, user.id, plan)


@router.post("/repack", response_model=StudyPlanPublic)
def repack(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StudyPlanPublic:
    """Dời móc neo của lịch về hôm nay — hành động TƯỜNG MINH thay cho lịch
    tự trôi. Nội dung và tick giữ nguyên; chỉ ngày của các mục chưa xảy ra
    đổi. Ai bỏ vài tuần mới cần nó, và khi cần thì phải tự bấm: đó là điểm
    khác biệt với cái lịch nhảy theo từng cú tick vừa bị người học bác."""
    plan = _current_plan(db, user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có kế hoạch học")
    profile = db.get(UserProfile, user.id)
    plan.starts_at = local_today(datetime.now(UTC), profile.timezone if profile else "UTC")
    db.commit()
    return _plan_public(db, user.id, plan)


@router.get("/versions", response_model=list[PlanVersionPublic])
def versions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[PlanVersionPublic]:
    """Lịch sử phiên bản kế hoạch (§29): bản cũ không bao giờ bị ghi đè, chỉ
    bị hạ `is_current`. `done_count` ở đây ĐẾM TICK TAY — các nguồn xong khác
    (bài nộp, bản ghi học) chỉ được suy cho kế hoạch HIỆN HÀNH lúc đọc; dựng
    lại chúng cho từng bản cũ là chạy lại cả `_plan_public` N lần để đổi lấy
    một dòng phụ trong UI."""
    plans = list(
        db.scalars(
            select(StudyPlan)
            .where(StudyPlan.user_id == user.id)
            .order_by(StudyPlan.version.desc(), StudyPlan.created_at.desc())
        )
    )
    if not plans:
        return []
    counts: dict[uuid.UUID, tuple[int, int]] = {
        pid: (int(total), int(ticked or 0))
        for pid, total, ticked in db.execute(
            select(
                StudyPlanItem.plan_id,
                func.count(),
                # `func.count(cột)` = đếm hàng KHÔNG NULL — SUM(boolean) không
                # tồn tại ở Postgres và chỉ chạy được trên SQLite của test.
                func.count(StudyPlanItem.done_at),
            )
            .where(StudyPlanItem.plan_id.in_([p.id for p in plans]))
            .group_by(StudyPlanItem.plan_id)
        ).all()
    }
    out: list[PlanVersionPublic] = []
    for plan in plans:
        total, ticked = counts.get(plan.id, (0, 0))
        out.append(
            PlanVersionPublic(
                id=str(plan.id),
                version=plan.version,
                reason=plan.reason,
                created_at=plan.created_at,
                is_current=plan.is_current,
                target_score=plan.target_score,
                exam_date=plan.exam_date,
                item_count=total,
                done_count=int(ticked or 0),
            )
        )
    return out


@router.get("/evaluation", response_model=PlanEvaluationPublic)
def evaluation(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> PlanEvaluationPublic:
    """§30–§31: đánh giá tiến bộ của kế hoạch hiện hành bằng SỰ KIỆN đã có,
    không bảng event riêng — attempt đã là học-kiện rồi, thêm một kho thứ hai
    là thêm một cách lệch nhau.

    - `retakes`: mọi phán quyết placement đã chốt, theo thời gian. Đây là
      chuỗi "đo lại" mà ô `mini_test` trên lịch tạo ra.
    - `trend`: từng kỹ năng top-priority — đúng/bao_nhiêu ở BÀI ĐẦU VÀO của
      kế hoạch này, và ở MỌI bài đã nộp sau đó (drill là câu thật có nhãn,
      nên độ chính xác theo nhãn tính được trên toàn bộ, không chỉ retake).
    - `new_diagnostic`: có phán quyết mới hơn ca mọc ra kế hoạch → lời khuyên
      hiện hành đang bám số cũ; UI nhắc dựng phiên bản mới (không tự làm:
      "re-plan tự động" viết lại lịch sau lưng người học là thứ spec cấm ở
      §38 cho tới khi V2 chạy bền).
    """
    plan = _current_plan(db, user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có kế hoạch học")
    results = list(
        db.scalars(
            select(PlacementResult)
            .where(
                PlacementResult.user_id == user.id,
                PlacementResult.estimator_version != "pending",
            )
            .order_by(PlacementResult.created_at)
        )
    )
    retakes = [
        PlanRetake(
            attempt_id=str(r.attempt_id),
            created_at=r.created_at,
            total_scaled=r.listening_scaled + r.reading_scaled,
            cefr=r.cefr_overall,
        )
        for r in results
    ]
    new_diagnostic = any(
        r.attempt_id != plan.placement_attempt_id
        and (r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=UTC))
        >= (plan.created_at if plan.created_at.tzinfo else plan.created_at.replace(tzinfo=UTC))
        for r in results
    )

    def _label_stats(attempt_ids: list[uuid.UUID]) -> dict[str, list[int]]:
        if not attempt_ids:
            return {}
        agg: dict[str, list[int]] = {}
        for code, is_correct in db.execute(
            select(QuestionLabel.code, AttemptItem.is_correct)
            .join(AttemptItem, AttemptItem.question_id == QuestionLabel.question_id)
            .where(AttemptItem.attempt_id.in_(attempt_ids))
        ).all():
            bucket = agg.setdefault(code, [0, 0])
            bucket[1] += 1
            bucket[0] += 1 if is_correct else 0
        return agg

    baseline = _label_stats([plan.placement_attempt_id])
    recent_ids = list(
        db.scalars(
            select(Attempt.id).where(
                Attempt.user_id == user.id,
                Attempt.status == "submitted",
                Attempt.submitted_at.is_not(None),
                Attempt.submitted_at >= plan.created_at,
                Attempt.id != plan.placement_attempt_id,
            )
        )
    )
    recent = _label_stats(recent_ids)

    profile = db.get(UserProfile, user.id)
    today = local_today(datetime.now(UTC), profile.timezone if profile else "UTC")
    insights = plan_insights(db, plan, profile, today)
    trend: list[PlanTrendRow] = []
    for s in insights.top_focus if insights else []:
        b = baseline.get(s.code, [0, 0])
        r = recent.get(s.code, [0, 0])
        trend.append(
            PlanTrendRow(
                code=s.code,
                label=s.label_vi,
                baseline_correct=b[0],
                baseline_total=b[1],
                recent_correct=r[0],
                recent_total=r[1],
            )
        )
    return PlanEvaluationPublic(retakes=retakes, trend=trend, new_diagnostic=new_diagnostic)


@router.patch("/items/{position}", response_model=StudyPlanPublic)
def tick_item(
    position: int,
    body: ItemTick,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudyPlanPublic:
    """Tick (hoặc bỏ tick) thủ công một mục của kế hoạch hiện hành.

    Cột riêng với tiến độ suy từ học thật: bỏ tick tay không được động vào bản
    ghi học, và mục đã học thật vẫn xong dù không ai tick — với mục đó checkbox
    bị khoá phía UI, vì "bỏ xong" một việc đã xảy ra là nói dối theo chiều
    ngược lại. Trả cả kế hoạch mới để client khỏi cần GET lại.
    """
    plan = _current_plan(db, user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có kế hoạch học")
    item = db.get(StudyPlanItem, (plan.id, position))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có mục này")
    if body.test_id is not None:
        _retarget_mock(db, plan, user.id, item, body.test_id)
        db.commit()
        return _plan_public(db, user.id, plan)
    if body.done is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cần `done` hoặc `test_id`",
        )
    if item.kind in ("mini_test", "mock_test"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mục kiểm tra tự ghi nhận bằng bài nộp, không tick tay được",
        )
    item.done_at = datetime.now(UTC) if body.done else None
    db.commit()
    return _plan_public(db, user.id, plan)


def _retarget_mock(
    db: Session, plan: StudyPlan, user_id: uuid.UUID, item: StudyPlanItem, test_id: uuid.UUID
) -> None:
    """Đổi đề của mục `mock_test`: một ô chưa nộp thì đích là lựa chọn, không
    phải lời hứa chốt. Đã nộp thì không đổi — lịch sử của một bài đã làm là
    bản ghi attempt, không phải con trỏ UI — VÀ "đã nộp" ở đây là attempt,
    không phải `done_at`: mock không bao giờ có tick tay."""
    if item.kind != "mock_test":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Chỉ mục thi thử mới đổi được đề"
        )
    submitted = item.ref_id is not None and db.scalar(
        select(func.count(Attempt.id)).where(
            Attempt.user_id == user_id,
            Attempt.test_id == item.ref_id,
            Attempt.status == "submitted",
            Attempt.submitted_at >= plan.created_at,
        )
    )
    if submitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Mục kiểm tra không đổi đích sau khi nộp"
        )
    row = next((r for r in mock_pool(db) if r[0] == test_id), None)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không có đề thi thử này (đề phải đã publish VÀ nằm trong bộ đề đã publish)",
        )
    item.ref_id = row[0]
    item.label = f"Thi thử — {row[3]}"[:160]
    item.link = mock_link(row[2], row[1])


def _generate_llm(
    db: Session, user_id: uuid.UUID, attempt: Attempt, *, reason: str | None = None
) -> StudyPlan:
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
    return write_plan(db, user_id, attempt, picks, source="llm", reason=reason)
