"""Planner V1 — rule-based, tất định (SPEC-PLACEMENT §5 + SPEC-STUDY-PLANNER).

LLM kể lại, hệ thống quyết định (AI-PLAN N1): kỹ năng yếu là con số truy vấn
ra, mục kế hoạch là bản ghi nội dung tra ra — không có gì ở đây để model "sáng
tạo". Đầu vào: kết quả placement + `user_profile` (target, exam_date,
minutes_per_day, study_days_per_week). Pipeline khớp §26 của spec: điểm mạnh/
yếu theo NHÃN (không phải theo part), priority tất định (§11–13), feasibility
theo nhịp điểm/tuần (§10), đường ống bốn phase (§15), và một nhịp kiểm tra:
mỗi tuần một lượt retake placement, một đề full thi thử trước ngày thi (§16).

N4 áp cho từng mục lõi: bài học không tồn tại thì mục không được ghi. Nhịp nền
(`vocab_review`, `dictation`) là ngoại lệ có chủ đích — nó trỏ module đã có
thật, không hứa nội dung cụ thể. Mục kiểm tra (`mini_test`, `mock_test`) cũng
tự khép BẰNG BÀI NỘP chứ không bằng tick: tick một bài kiểm tra là được phép
xưng "đã đo" mà chưa đo.

Mọi ngưỡng dưới đây là hằng số module — spec đòi "thresholds must be
configurable" (§6/§10); "configurable" ở repo này nghĩa là một dòng đổi được
có test giữ, không phải một bảng admin.
"""

import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    AttemptItem,
    DictationTopic,
    GrammarLesson,
    GrammarTopic,
    PlacementResult,
    PracticeTest,
    Question,
    QuestionLabel,
    StudyPlan,
    StudyPlanItem,
    TestCollection,
    Topic,
    UserProfile,
)
from app.services.labels import LABELS
from app.services.progression import local_today

# --- §5–6: skill profile ----------------------------------------------------
# Kỹ năng có mẫu số dưới ngưỡng này là nhiễu (1/2 có thể là trúng số) — không
# xếp mạnh, không xếp yếu, không vào priority.
MIN_SKILL_SAMPLE = 3
# Băng trạng thái, đọc từ trên xuống (§6 năm mức). Ngưỡng là ước lệ TOEIC-ish:
# 80% là đã vững, dưới 45% là lỗ hổng thật.
_STATUS_BANDS = ((0.80, "strong"), (0.65, "stable"), (0.45, "developing"), (0.0, "weak"))
# Số câu → trọng số tin cậy (§6: 1–2 rất thấp, 3–4 thấp, 5–7 vừa, 8+ cao).
_CONFIDENCE_BANDS = ((8, 1.0), (5, 0.8), (3, 0.5), (0, 0.2))

# --- §11–13: priority engine --------------------------------------------------
# `toeic_relevance` của spec đáng ra nằm trong metadata phân loại nhưng không
# có; proxy thành thật là SỨC NẶNG PHẦN: số câu mỗi part trong đề thi thật
# (cấu trúc công khai 6/25/39/32 — 30/16/54). P7 chiếm nửa bài Đọc nên lỗi P7
# đáng sửa hơn lỗi P1 — đó là tất cả những gì con số này nói.
_PART_RELEVANCE = {1: 0.06, 2: 0.25, 3: 0.39, 4: 0.32, 5: 0.30, 6: 0.16, 7: 0.54}
_TOP_PRIORITIES = 5  # §13: 3–5 kỹ năng, không hơn — 10 lỗi đều nhau là vô nghĩa
_MAINTENANCE_SLOTS = 1  # §23: skill mạnh chỉ ăn suất duy trì, không ăn ngân sách luyện

# --- §10: feasibility ----------------------------------------------------------
# Quy tắc ngón cái, deliberately coarse (SPEC-EXAM nói thẳng đường cong điểm
# không tuyến tính): ≤10 điểm/tuần là thoải mái, ≤25 là căng, hơn là bảo
# không nổi với lịch này. <2h học một TUẦN thì mọi nhịp điểm đều tụt một bậc.
_RATE_FEASIBLE = 10.0
_RATE_CHALLENGING = 25.0
_MIN_WEEKLY_MINUTES = 120
FEASIBILITY_LABELS = ("FEASIBLE", "CHALLENGING", "HIGH_RISK")

# --- §17–21: thời lượng --------------------------------------------------------
# Một mục = một buổi. Phút là ƯỚC LƯỢNG hiển thị + đơn vị packing, không phải
# đồng hồ đo; trần cứng nằm ở packing (`pack_days`), không ở đây.
EST_MINUTES = {
    "grammar_lesson": 30,
    "part_drill": 30,
    "vocab_review": 15,
    "dictation": 15,
    "mini_test": 75,  # 84 câu + xem lại đáp án
    "mock_test": 125,  # 200 câu, đúng khung giờ thi
}
# Mỗi mục là một buổi (~30 phút). Ít ngày thì danh sách ngắn đi, không dồn.
_ITEMS_FEW_DAYS = 6
_ITEMS_NORMAL = 10
# Ngưỡng "còn xa": hai tuần cuối danh sách ngắn là chủ ý của SPEC §5; nhịp
# tuần (retake + nền) chỉ lấp khi ngày thi còn XA hơn khung ấy.
_FILLER_MIN_DAYS = 14
# Không lập kế hoạch quá ba tháng — ai đổi ngày thi thì "Sinh lại" theo đầu
# vào mới; lịch trải tới 6 tháng là lời hứa quá tầm với.
_FILLER_MAX_DAYS = 90
_MAX_PLAN_ITEMS = 120
# Mock đứng trước ngày thi một khoảng để còn sửa gì đó sau nó; retake đầu
# không rơi vào tuần đầu vì tuần ấy còn đang học lời khuyên đầu tiên.
_MOCK_BUFFER_DAYS = 7
_RETAKE_COOLDOWN_DAYS = 7  # khớp gate placement — mỗi tuần đúng một retake
DEFAULT_MINUTES_PER_DAY = 30
DEFAULT_DAYS_PER_WEEK = 7


@dataclass(frozen=True, slots=True)
class DraftItem:
    """Một mục kế hoạch trước khi ghi — cả hai planner cùng trả hình dạng này."""

    kind: str
    part: int
    ref_id: uuid.UUID | None
    label: str
    reason: str | None
    phase: str = "weakness"
    # Đích đến do generator dựng (mig 085). None = mục chung loại, UI tự nối
    # theo kind (bảng fallback vẫn sống cho hàng cũ).
    link: str | None = None


def _drill_link(part: int, code: str | None) -> str:
    """Link drill KÈM BỘ LỌC NHÃN — nói "luyện suy luận P7" rồi thả người học
    trước bảy checkbox là đi được nửa đường; `?labels=` mở drill đã chọn đúng
    dạng câu của lời khuyên."""
    base = f"/learn/parts/{part}/drill"
    return f"{base}?labels={code}" if code else base


@dataclass(frozen=True, slots=True)
class SkillStat:
    """Một ô kỹ năng của skill profile (§5) — số liệu, không phải phán quyết."""

    code: str
    label_vi: str
    part: int
    correct: int
    total: int
    accuracy: float
    status: str
    confidence: float
    priority: float


def _smoothed_accuracy(correct: int, total: int) -> float:
    """§12: Laplace +1/+2 — mẫu nhỏ bị kéo về 50% thay vì tung hô 0% hay 100%."""
    return (correct + 1) / (total + 2)


def _confidence(total: int) -> float:
    for floor, weight in _CONFIDENCE_BANDS:
        if total >= floor:
            return weight
    return 0.2


def _status(accuracy: float) -> str:
    for floor, name in _STATUS_BANDS:
        if accuracy >= floor:
            return name
    return "weak"


def _skill_stats(db: Session, attempt: Attempt) -> list[SkillStat]:
    """Skill profile của một lượt placement: mọi mã nhãn đã gắn, có đủ mẫu thì
    chấm priority, không đủ mẫu thì `insufficient` (§5–6)."""
    rows = db.execute(
        select(QuestionLabel.code, AttemptItem.is_correct)
        .join(Question, Question.id == AttemptItem.question_id)
        .join(QuestionLabel, QuestionLabel.question_id == Question.id)
        .where(
            AttemptItem.attempt_id == attempt.id,
            QuestionLabel.facet.in_(("question_type", "grammar")),
        )
    ).all()
    tally: dict[str, list[int]] = {}
    for code, is_correct in rows:
        if code is None:
            continue
        entry = tally.setdefault(code, [0, 0])
        entry[0] += 1 if is_correct else 0
        entry[1] += 1
    stats: list[SkillStat] = []
    for code, (correct, total) in tally.items():
        label = LABELS.get(code)
        part = label.parts[0] if label and label.parts else 0
        if total < MIN_SKILL_SAMPLE or label is None:
            stats.append(
                SkillStat(
                    code,
                    label.label_vi if label else code,
                    part,
                    correct,
                    total,
                    0.0,
                    "insufficient",
                    0.0,
                    0.0,
                )
            )
            continue
        accuracy = correct / total
        smoothed = _smoothed_accuracy(correct, total)
        confidence = _confidence(total)
        relevance = _PART_RELEVANCE.get(part, 0.1)
        # improvement_potential (§12): giữa thang còn cửa tiến nhất; đã ≥80%
        # thì cửa hẹp dần nhưng không về 0 — floor 0.25 giữ duy trì khả năng
        # quay lại yếu ở mốc mẫu lớn.
        potential = max(0.25, 1.0 - abs(0.5 - smoothed) * 2.0)
        priority = (1.0 - smoothed) * confidence * relevance * potential
        stats.append(
            SkillStat(
                code,
                label.label_vi,
                part,
                correct,
                total,
                accuracy,
                _status(accuracy),
                confidence,
                priority,
            )
        )
    stats.sort(key=lambda s: (-s.priority, s.code))
    return stats


def _weak_parts(db: Session, attempt: Attempt) -> list[tuple[int, int, int]]:
    rows = db.execute(
        select(Question.part, AttemptItem.is_correct)
        .join(Question, Question.id == AttemptItem.question_id)
        .where(AttemptItem.attempt_id == attempt.id)
    ).all()
    tally: dict[int, list[int]] = {}
    for part, is_correct in rows:
        entry = tally.setdefault(int(part), [0, 0])
        entry[0] += 1 if is_correct else 0
        entry[1] += 1
    return sorted(
        (
            (part, correct, count)
            for part, (correct, count) in tally.items()
            if count >= MIN_SKILL_SAMPLE and correct / count < 0.5
        ),
        key=lambda item: item[1] / item[2],
    )


def weak_items(db: Session, attempt: Attempt) -> list[tuple[str, int, int]]:
    """Tên công khai của danh sách yếu cũ — planner LLM đọc cùng dữ liệu này."""
    return [
        (s.code, s.correct, s.total)
        for s in _skill_stats(db, attempt)
        if s.code in LABELS and s.total >= MIN_SKILL_SAMPLE and s.accuracy < 0.5
    ]


def budget_for(today: date, exam_date: date | None) -> int:
    """Số mục LÕI tối đa — tên công khai vì planner LLM dùng chung phép này."""
    if exam_date is None:
        return _ITEMS_NORMAL
    return _ITEMS_FEW_DAYS if (exam_date - today).days <= 14 else _ITEMS_NORMAL


def pace_per_day(minutes_per_day: int | None) -> int:
    """Mấy buổi một ngày, cho ước lượng sức chứa khi sinh nhịp nền.

    NULL → một buổi: chưa nhập không bị punished bằng lịch dày hơn người đã
    nhập. Trần 3 (90+ phút/ngày) giữ "Sinh lại" không nổ thành 480 phút.
    """
    return min(3, max(1, (minutes_per_day or DEFAULT_MINUTES_PER_DAY) // 30))


def _feasibility(gap: int | None, weeks_left: int | None, weekly_minutes: int) -> str | None:
    """§10 — phân loại bằng nhịp điểm/tuần, có tính sức chứa giờ.

    Không bao giờ trả "chắc chắn đạt": nhãn FEASIBLE chỉ nói nhịp hiện tại là
    bình thường theo quy tắc ngón cái, và quy tắc ngón cái không phải hứa.
    """
    if gap is None or weeks_left is None:
        return None
    if gap <= 0 or weeks_left <= 0:
        # Gap âm thì mục tiêu đã nằm trong tầm tay hôm nay; hết tuần thì
        # không còn lịch để mà khả thi — ca này hiếm, chọn chiều thẳng thắn.
        return "FEASIBLE" if gap <= 0 else "HIGH_RISK"
    rate = gap / weeks_left
    idx = 0 if rate <= _RATE_FEASIBLE else 1 if rate <= _RATE_CHALLENGING else 2
    if weekly_minutes < _MIN_WEEKLY_MINUTES and idx < 2:
        idx += 1
    return FEASIBILITY_LABELS[idx]


@dataclass(frozen=True, slots=True)
class PlanInsights:
    """Khối header §34 — mọi con số của nó truy vấn được, không con nào do
    model viết. `why` là template từ đúng các số này (§35)."""

    listening_scaled: int
    reading_scaled: int
    estimated_total: int
    band_low: int
    band_high: int
    cefr: str
    target_score: int | None
    gap: int | None
    weeks_left: int | None
    feasibility: str | None
    top_focus: list[SkillStat]
    why: str


def plan_insights(
    db: Session, plan: StudyPlan, profile: UserProfile | None, today: date
) -> PlanInsights | None:
    """Đọc phán quyết placement GỐC của kế hoạch + priority hiện hành. Trả None
    khi kế hoạch mất gốc (không xảy ra với dữ liệu bình thường; route chọn
    im lặng vì header không được phép làm hỏng cả màn lịch)."""
    raw = db.get(PlacementResult, plan.placement_attempt_id)
    attempt = db.get(Attempt, plan.placement_attempt_id)
    if raw is None or raw.estimator_version == "pending" or attempt is None:
        return None
    total = raw.listening_scaled + raw.reading_scaled
    # Mục tiêu của HEADER là mục tiêu HIỆN TẠI (profile là nguồn sự thật),
    # snapshot trên plan chỉ là fallback cho hồ sơ không còn tồn tại — "cách
    # mục tiêu 610 điểm" in ra sau khi người học đã xoá mục tiêu là bịa.
    target = profile.target_score if profile else plan.target_score
    gap = (target - total) if target is not None else None
    days_left = (plan.exam_date - today).days if plan.exam_date else None
    weeks_left = math.ceil(days_left / 7) if days_left is not None and days_left > 0 else None
    weekly = ((profile.minutes_per_day if profile else None) or DEFAULT_MINUTES_PER_DAY) * (
        (profile.study_days_per_week if profile else None) or DEFAULT_DAYS_PER_WEEK
    )
    focus = [s for s in _skill_stats(db, attempt) if s.priority > 0][:5]
    why = _why(raw, total, target, gap, weeks_left, weekly, focus, profile)
    return PlanInsights(
        listening_scaled=raw.listening_scaled,
        reading_scaled=raw.reading_scaled,
        estimated_total=total,
        band_low=raw.listening_low + raw.reading_low,
        band_high=raw.listening_high + raw.reading_high,
        cefr=raw.cefr_overall,
        target_score=target,
        gap=gap,
        weeks_left=weeks_left,
        feasibility=_feasibility(gap, weeks_left, weekly),
        top_focus=focus,
        why=why,
    )


def _why(
    raw: PlacementResult,
    total: int,
    target: int | None,
    gap: int | None,
    weeks_left: int | None,
    weekly: int,
    focus: list[SkillStat],
    profile: UserProfile | None,
) -> str:
    """§35 — giải thích bằng template từ số đã truy vấn. KHÔNG LLM: văn đều
    cho mọi người đọc thì không cần ai sáng tác, và một câu bịa số ở đây là
    kế hoạch mất uy tín nhanh hơn mọi tiết kiệm prompt nào."""
    parts = [
        f"Test đầu vào ước lượng bạn ở khoảng {total} điểm "
        f"(Nghe {raw.listening_scaled} · Đọc {raw.reading_scaled}, {raw.cefr_overall})."
    ]
    if target is not None and gap is not None and weeks_left:
        direction = "cách mục tiêu" if gap > 0 else "đã chạm mục tiêu"
        parts.append(
            f"Mục tiêu {target}, {direction} {abs(gap)} điểm, còn {weeks_left} tuần "
            f"với ~{weekly} phút học mỗi tuần."
        )
    elif profile is not None and profile.exam_date is None:
        parts.append(
            "Chưa có ngày thi nên kế hoạch chưa biết co giãn thế nào — nhập ngày thi để nó tính."
        )
    if focus:
        listed = "; ".join(f"{s.label_vi} (đúng {s.correct}/{s.total})" for s in focus)
        parts.append(
            f"Kỹ năng priority cao nhất theo độ yếu × độ tin cậy mẫu × sức nặng phần: {listed}."
        )
        parts.append("Kỹ năng đã mạnh chỉ nhận một suất duy trì, không ăn ngân sách luyện.")
    else:
        parts.append(
            "Chưa có kỹ năng nào đủ mẫu (≥3 câu) để kết luận — kế hoạch bám part "
            "yếu và nhịp kiểm tra."
        )
    parts.append("Con số là ước lượng, không phải điểm chính thức và không hứa kết quả.")
    return " ".join(parts)


def _filler_items(need: int) -> list[DraftItem]:
    """`need` buổi nhịp nền xen kẽ từ / phiên."""
    out: list[DraftItem] = []
    for i in range(need):
        if i % 2 == 0:
            out.append(
                DraftItem(
                    kind="vocab_review",
                    part=0,
                    ref_id=None,
                    label="Ôn từ vựng đến hạn",
                    reason="Nhịp nền theo lịch lặp lại — không phải mục riêng của kế hoạch",
                    phase="integrated",
                )
            )
        else:
            out.append(
                DraftItem(
                    kind="dictation",
                    part=0,
                    ref_id=None,
                    label="Chép chính tả",
                    reason="Nhịp nền rèn nghe — một buổi ngắn cũng tính",
                    phase="integrated",
                )
            )
    return out


def _week_cadence(
    weeks: int, daily_minutes: int, days_per_week: int, core_len: int
) -> list[DraftItem]:
    """Nhịp tuần cho `weeks` tuần: mỗi tuần một lượt kiểm tra lại + nền lấp.

    Vị trí sinh ra nhịp, ngày là việc của packer. Mỗi tuần dành một ngày cho
    lượt retake (75'), phần phút còn lại của tuần chia cho các buổi nền 15' —
    tính bằng PHÚT đúng như `pack_days` sẽ pack, để hai bên không lệch nhau
    một ngày nào. §20 "daily allocation" sống được với hàng đợi không ngày là
    nhờ phép chia này: tuần nào cũng có đúng một lần đo, các ngày kia là học.
    """
    out: list[DraftItem] = []
    filler_per_week = max(0, (daily_minutes * days_per_week - EST_MINUTES["mini_test"]) // 15)
    for w in range(1, weeks + 1):
        out.append(_mini_item(w))
        out.extend(_filler_items(filler_per_week))
        if core_len + len(out) >= _MAX_PLAN_ITEMS - 1:
            # "-1": chừa chỗ cuối cho đề thi thử — cắt phải NHịp, không cắt mock.
            break
    return out


def mock_pool(db: Session) -> list[tuple[uuid.UUID, str, str, str]]:
    """Đề thi thử DÙNG ĐƯỢC: published, nằm trong collection CŨNG published.

    "Test published" một mình là nghĩa sai: đề thuộc collection archived hoặc
    không đứng ở collection nào không hiện trên `/learn/tests` và không có
    đường `/learn/tests/{collection}/{test}` — biến nó thành lựa chọn thi thử
    là gửi người học tới một tường 404 ngay từ CTA của kế hoạch.
    """
    return [
        (r[0], r[1], r[2], r[3])
        for r in db.execute(
            select(PracticeTest.id, PracticeTest.slug, TestCollection.slug, PracticeTest.title)
            .join(TestCollection, TestCollection.id == PracticeTest.collection_id)
            .where(
                PracticeTest.kind == "full",
                PracticeTest.status == "published",
                TestCollection.status == "published",
            )
            .order_by(PracticeTest.position, PracticeTest.created_at)
        ).all()
    ]


def mock_link(coll_slug: str, test_slug: str) -> str:
    """Link vào đề với dấu `plan=mock`: màn chi tiết dùng nó để KHÓA chế độ —
    thi thử theo kế hoạch là mô phỏng đề thật, nên "Luyện tập" và việc bỏ
    chọn part bị chặn từ lúc vào, đúng như một buổi thi thật không cho chọn."""
    return f"/learn/tests/{coll_slug}/{test_slug}?plan=mock"


def _mock_item(db: Session, today: date, exam_date: date | None) -> DraftItem | None:
    """Một đề full thi thử, nếu còn ≥3 tuần và kho có đề đã publish (§16).

    Không có đề publish thì KHÔNG có mục — tham chiếu treo là N4, khác đúng
    một chỗ với "chưa có gì để hứa".
    """
    if exam_date is None or (exam_date - today).days < 21:
        return None
    rows = mock_pool(db)
    if not rows:
        return None
    # Rút ngẫu nhiên như `_placement_test`: "Sinh lại" là quay lại đề — kế
    # hoạch không bị ghim vĩnh viễn vào một form duy nhất của kho.
    test_id, test_slug, coll_slug, test_title = random.choice(rows)
    return DraftItem(
        kind="mock_test",
        part=0,
        ref_id=test_id,
        label=f"Thi thử — {test_title}",
        reason=(
            "Một lần đúng khung giờ thi, trước ngày thi "
            f"{_MOCK_BUFFER_DAYS} ngày — để còn sửa gì đó sau nó"
        ),
        phase="final",
        link=mock_link(coll_slug, test_slug),
    )


def _mini_item(w: int) -> DraftItem:
    """Một lượt kiểm tra lại — tuần w (1-based) của lịch."""
    return DraftItem(
        kind="mini_test",
        part=0,
        ref_id=None,
        label=f"Kiểm tra lại — tuần {w}",
        reason=(
            "Làm lại bài test đầu vào (tối đa một lần mỗi 7 ngày); nộp xong là "
            'ô này tự khép — bấm "Sinh lại" để kết quả mới dẫn kế hoạch'
        ),
        phase="final",
        link="/learn/placement",
    )


def _background_pools(db: Session) -> tuple[list[tuple[str, str]], list[tuple[uuid.UUID, str]]]:
    """Chủ đề từ vựng (slug, tên) và chủ đề chép (id, tên) đã publish — hai
    vòng xoay của nhịp nền. Nhãn khác nhau tuần sau tuần trước là có chủ đích: "Ôn từ vựng
    đến hạn" lặp 12 tuần đọc như máy hỏng, còn "Ôn từ vựng — Travel" thì mỗi
    tuần là một việc thật, bấm vào là thấy ngay bao nhiêu từ.
    """
    topics = db.execute(
        select(Topic.slug, Topic.name).where(Topic.status == "published").order_by(Topic.position)
    ).all()
    dtops = db.execute(
        select(DictationTopic.id, DictationTopic.name)
        .where(DictationTopic.status == "published")
        .order_by(DictationTopic.name)
    ).all()
    return [(r[0], r[1]) for r in topics], [(r[0], r[1]) for r in dtops]


def _weekly_schedule(
    db: Session,
    lessons: list[DraftItem],
    drill_pool: list[SkillStat],
    maintenance: DraftItem | None,
    profile: UserProfile | None,
    today: date,
    exam_date: date,
    days_left: int,
) -> list[DraftItem]:
    """Kế hoạch xoay vòng theo tuần thay vì "10 lời khuyên rồi tới đáy lịch".

    Mỗi tuần: `drills_per_week` buổi luyện round-robin từ hàng đợi priority
    (kỹ năng số 1 quay lại sau ~2 tuần — giãn cách chứ không dồn hết tuần
    đầu), một board từ vựng xoay chủ đề, một buổi chép chính tả xoay ngữ liệu,
    và MỘT lượt đo khép tuần; bài ngữ pháp rải vài tuần đầu (móng của §16).
    HAI TUẦN CUỐI không kỹ năng mới: chỉ đo + nền — §16 cấm nội dung lớn sát
    ngày thi, và §5 của SPEC-PLACEMENT đã chốt danh sách ngắn.
    """
    horizon = min(days_left, _FILLER_MAX_DAYS)
    weeks = max(0, (horizon - _MOCK_BUFFER_DAYS) // _RETAKE_COOLDOWN_DAYS)
    days_per_week = (profile.study_days_per_week if profile else None) or DEFAULT_DAYS_PER_WEEK
    drills_per_week = 3 if days_per_week >= 6 else 2 if days_per_week >= 4 else 1
    topics, dtops = _background_pools(db)
    out: list[DraftItem] = []
    for w in range(weeks):
        final_window = days_left - (w + 1) * 7 <= _FILLER_MIN_DAYS
        if not final_window:  # nước rút: không kỹ năng MỚI, chỉ còn đo + nền (§16)
            for i in range(min(drills_per_week, len(drill_pool))):
                s = drill_pool[(w * drills_per_week + i) % len(drill_pool)]
                out.append(
                    DraftItem(
                        kind="part_drill",
                        part=s.part,
                        ref_id=None,
                        label=f"Luyện Part {s.part} — {s.label_vi}",
                        reason=(
                            f"Vòng ưu tiên tuần {w + 1} — test đầu vào đúng {s.correct}/{s.total}"
                        ),
                        phase="weakness",
                        link=_drill_link(s.part, s.code or None),
                    )
                )
            if w < len(lessons):
                out.append(lessons[w])
        if not topics and not dtops:
            out.extend(_filler_items(2))  # bản cài không có catalogue nào: nhịp chung
        if topics:
            slug, name = topics[w % len(topics)]
            out.append(
                DraftItem(
                    kind="vocab_review",
                    part=0,
                    ref_id=None,
                    label=f"Ôn từ vựng — {name}",
                    reason="Xoay chủ đề từ vựng — một board, vài phút cũng tính",
                    phase="integrated",
                    link=f"/learn/vocabulary/{slug}",
                )
            )
        if dtops:
            dt_id, dt_name = dtops[w % len(dtops)]
            out.append(
                DraftItem(
                    kind="dictation",
                    part=0,
                    ref_id=None,
                    label=f"Chép chính tả — {dt_name}",
                    reason="Xoay ngữ liệu rèn nghe — một buổi ngắn cũng tính",
                    phase="integrated",
                    link=f"/learn/dictation/topics/{dt_id}",
                )
            )
        # Mini CUỐI block tuần: packer neo nó đầu tuần SAU (đo kết thúc tuần
        # học, không phải mở màn tuần); thứ tự position cũng nói vậy — tuần
        # đọc từ trái sang phải là học… học, đo.
        out.append(_mini_item(w + 1))
        if len(out) >= _MAX_PLAN_ITEMS - 6:
            break
    if maintenance is not None:
        out.append(maintenance)
    return out


def write_plan(
    db: Session,
    user_id: uuid.UUID,
    attempt: Attempt,
    items: list[DraftItem],
    *,
    source: str = "rule",
    with_cadence: bool = True,
) -> StudyPlan:
    """Ghi danh sách mục thành kế hoạch hiện hành — phần dùng chung của cả hai
    planner. Hạ kế hoạch cũ trong cùng giao dịch: hai kế hoạch hiện hành không
    bao giờ cùng tồn tại, dù hai request tới cạnh nhau.

    `with_cadence` chỉ đường LLM còn dùng (V2 chọn mục đơn lẻ rồi cần nhịp
    tuần + đề thi thử nối đuôi); V1 tự sinh lịch xoay vòng nên ghi `False`.
    """
    profile = db.get(UserProfile, user_id)

    today = local_today(datetime.now(UTC), profile.timezone if profile else "UTC")
    exam_date = profile.exam_date if profile else None
    days_left = (exam_date - today).days if exam_date else None
    items = list(items)

    # Nhịp tuần + đề thi thử cho đường không tự xếp lịch (V2): cùng một phép
    # cho mọi planner để so sánh ở /admin/planner-compare còn công bằng.
    if with_cadence and days_left is not None and days_left > _FILLER_MIN_DAYS:
        horizon = min(days_left, _FILLER_MAX_DAYS)
        weeks = max(0, (horizon - _MOCK_BUFFER_DAYS) // _RETAKE_COOLDOWN_DAYS)
        cadence = _week_cadence(
            weeks,
            (profile.minutes_per_day if profile else None) or DEFAULT_MINUTES_PER_DAY,
            (profile.study_days_per_week if profile else None) or DEFAULT_DAYS_PER_WEEK,
            len(items),
        )
        mock = _mock_item(db, today, exam_date)
        items = items + cadence + ([mock] if mock else [])
        if len(items) > _MAX_PLAN_ITEMS:
            items = items[:_MAX_PLAN_ITEMS]

    db.execute(
        update(StudyPlan)
        .where(StudyPlan.user_id == user_id, StudyPlan.is_current.is_(True))
        .values(is_current=False)
    )
    plan = StudyPlan(
        user_id=user_id,
        placement_attempt_id=attempt.id,
        target_score=profile.target_score if profile else None,
        exam_date=profile.exam_date if profile else None,
        source=source,
        # Lịch neo vào ngày sinh: tick một mục không được kéo cả lịch trôi.
        # "Dời lịch" (POST /repack) là cách tường minh duy nhất để đổi móc neo.
        starts_at=today,
        is_current=True,
    )
    db.add(plan)
    db.flush()
    for position, item in enumerate(items, start=1):
        db.add(
            StudyPlanItem(
                plan_id=plan.id,
                position=position,
                kind=item.kind,
                part=item.part,
                ref_id=item.ref_id,
                label=item.label,
                reason=item.reason,
                phase=item.phase,
                link=item.link,
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def generate_plan(db: Session, user_id: uuid.UUID, attempt: Attempt) -> StudyPlan:
    """Sinh kế hoạch hiện hành mới từ một lượt placement ĐÃ phân tích.

    Đường ống §26–§27 bản rule: skill profile (§5) → priority (§11) → hai
    hàng đợi: BÀI NGỮ PHÁP (móng, rải vài tuần đầu) và DRILL THEO NHÃN
    (round-robin suốt lịch, không dồn hết vào tuần đầu — đó chính là cái
    khiến "những ngày sau toàn nhịp nền"). Ngày thi còn xa → `_weekly_schedule
    trải đều tới ngày thi; ≤14 ngày hoặc chưa có ngày thi → danh sách ngắn
    phẳng của §5.
    """
    result = db.get(PlacementResult, attempt.id)
    if result is None or result.estimator_version == "pending":
        raise ValueError("lượt làm này chưa được phân tích")

    profile = db.get(UserProfile, user_id)
    exam_date = profile.exam_date if profile else None
    today = local_today(datetime.now(UTC), profile.timezone if profile else "UTC")
    days_left = (exam_date - today).days if exam_date else None

    # --- Pool lời khuyên: priority dẫn, không chia đều (§22), mạnh chỉ duy trì (§23).
    stats = [s for s in _skill_stats(db, attempt) if s.priority > 0]
    weak = [s for s in stats if s.status in ("weak", "developing")][:_TOP_PRIORITIES]
    lessons: list[DraftItem] = []
    drill_pool: list[SkillStat] = []
    for s in weak:
        if not s.code.startswith("GRAMMAR_"):
            drill_pool.append(s)
            continue
        topic = db.scalar(
            select(GrammarTopic).where(
                GrammarTopic.code == s.code, GrammarTopic.status == "published"
            )
        )
        if topic is None:
            continue  # N4: không có chủ đề thì không có mục
        lesson = db.scalar(
            select(GrammarLesson)
            .where(GrammarLesson.topic_id == topic.id, GrammarLesson.status == "published")
            .order_by(GrammarLesson.position)
            .limit(1)
        )
        if lesson is None:
            continue
        lessons.append(
            DraftItem(
                kind="grammar_lesson",
                part=5,
                ref_id=lesson.id,
                label=f"Ôn {topic.title}",
                reason=f"Đúng {s.correct}/{s.total} câu ngữ pháp dạng này — priority cao",
                phase="foundation",
                link=f"/learn/grammar/{topic.id}/{lesson.id}",
            )
        )

    # Part yếu TRẢI ĐỀU không dạng nào nổi bật — priority theo nhãn có thể bỏ
    # sót; hàng giả mang code rỗng (drill không pre-filter được, chỉ vào part).
    drilled_parts = {s.part for s in drill_pool}
    for part, correct, count in _weak_parts(db, attempt):
        if part in drilled_parts:
            continue
        drilled_parts.add(part)
        drill_pool.append(
            SkillStat(
                code="",
                label_vi=f"Part {part} (đều tay)",
                part=part,
                correct=correct,
                total=count,
                accuracy=correct / count,
                status="weak",
                confidence=1.0,
                priority=0.0,
            )
        )

    maintenance: DraftItem | None = None
    strong = [s for s in stats if s.status in ("strong", "stable")]
    if strong:
        best = max(strong, key=lambda s: _PART_RELEVANCE.get(s.part, 0.1))
        if best.part not in drilled_parts:
            maintenance = DraftItem(
                kind="part_drill",
                part=best.part,
                ref_id=None,
                label=f"Duy trì Part {best.part}",
                reason=(f"'{best.label_vi}' đúng {best.correct}/{best.total} — tập nhẹ giữ tay"),
                phase="integrated",
                link=_drill_link(best.part, best.code),
            )

    if exam_date is not None and days_left is not None and days_left > _FILLER_MIN_DAYS:
        items = _weekly_schedule(
            db, lessons, drill_pool, maintenance, profile, today, exam_date, days_left
        )
        mock = _mock_item(db, today, exam_date)
        # Mock đứng CUỐI hàng đợi: packer neo nó tuần trước ngày thi dù vị trí
        # nào, nhưng cuối vẫn là cuối — "nước rút" đọc đúng từ danh sách.
        items = items + ([mock] if mock else [])
        return write_plan(db, user_id, attempt, items, source="rule", with_cadence=False)

    # Danh sách phẳng: ≤14 ngày hoặc chưa có ngày thi — ngân sách ngắn của §5.
    budget = budget_for(today, exam_date)
    items = (lessons + _flat_drills(drill_pool, maintenance))[:budget]
    return write_plan(db, user_id, attempt, items, source="rule", with_cadence=False)


def _flat_drills(drill_pool: list[SkillStat], maintenance: DraftItem | None) -> list[DraftItem]:
    out = [
        DraftItem(
            kind="part_drill",
            part=s.part,
            ref_id=None,
            label=f"Luyện Part {s.part}{f' — {s.label_vi}' if s.code else ''}",
            reason=f"Yếu dạng này — đúng {s.correct}/{s.total} câu ở test đầu vào",
            phase="weakness",
            link=_drill_link(s.part, s.code or None),
        )
        for s in drill_pool
    ]
    if maintenance is not None:
        out.append(maintenance)
    return out


def _study_date(k: int, today: date, days_per_week: int) -> date:
    """Ngày học thứ `k` (0-based): mỗi tuần `days_per_week` ngày, tính từ hôm
    nay. k=0 là hôm nay; tuần nghỉ là các ngày KHÔNG phải số học."""
    return today + timedelta(days=(k // days_per_week) * 7 + (k % days_per_week))


def pack_days(
    needs: list[tuple[int, int, str]],
    tests: list[tuple[int, int, str]],
    today: date,
    daily_minutes: int,
    days_per_week: int,
    exam_date: date | None,
) -> dict[int, date]:
    """Trải mục lên lịch NGÀY THEO PHÚT (§20–21), trả {position: date}.

    Bốn luật. MỘT: một ngày không quá `daily_minutes` — hard rule của §20; mục
    dài hơn cả ngày (retake 75', đề thi thử 125') chiếm nguyên một ngày. HAI:
    một tuần chỉ `days_per_week` ngày học từ hôm nay — phần còn lại là NGÀY
    NGHỈ, nghỉ không bị đếm là bỏ. BA: bài kiểm tra KHÔNG đi hàng đợi — nó NEO
    (retake thứ j = ngày học đầu tuần j, thi thử = ngày cuối tuần trước ngày
    thi `_MOCK_BUFFER_DAYS`). BỐN: một ngày không lặp hai mục CÙNG KIND — đó
    là cái người học gọi là "toàn ôn từ vựng"; kể cả khi generator xếp hai
    tuần nền cạnh nhau (tuần nước rút chỉ còn nền), luật này chặn chúng chung
    một ô. Hàng đợi học len quanh các mốc đó; vị trí đã chiếm thì lùi ngày.

    Đã xong thì vẫn chiếm chỗ (ngày của lịch KHÔNG đổi khi tick — xem
    `study_plan.starts_at`).
    """
    out: dict[int, date] = {}
    used: dict[int, int] = {}
    kinds_on_day: dict[int, set[str]] = {}
    blocked: set[int] = set()

    mini_i = 0
    for position, minutes, kind in tests:
        if kind == "mini_test":
            mini_i += 1
            k = mini_i * days_per_week  # ngày học ĐẦU của tuần j (tuần 0 là tuần bắt đầu)
        else:
            target = (
                max(0, ((exam_date - timedelta(days=_MOCK_BUFFER_DAYS)) - today).days)
                if exam_date
                else mini_i * 7
            )
            k = (max(1, target // 7) + 1) * days_per_week - 1  # ngày học CUỐI của tuần đó
        while k in blocked or used.get(k):
            k += 1
        blocked.add(k)
        # Ngày của bài kiểm tra là NGÀY ĐỘC QUYỀN: đánh dấu đầy ngân sách để
        # không mục học nào được nhét chung — 75' của retake không có nghĩa
        # còn 15' cho vocab, hôm đó là hôm đo.
        used[k] = daily_minutes
        out[position] = _study_date(k, today, days_per_week)

    cursor = 0
    for position, minutes, kind in needs:
        while True:
            if cursor in blocked:
                cursor += 1
                continue
            day_used = used.get(cursor, 0)
            # Ngày TRỐNG luôn nhận mục kể cả khi nó dài hơn ngân sách: một
            # buổi 30' không cắt làm hai ngày 15', và nếu không có nhánh này
            # thì `minutes_per_day=5` làm cursor chạy mãi không dừng.
            if day_used == 0:
                break
            if kind in kinds_on_day.get(cursor, set()) or day_used + minutes > daily_minutes:
                cursor += 1
                continue
            break
        out[position] = _study_date(cursor, today, days_per_week)
        used[cursor] = used.get(cursor, 0) + minutes
        kinds_on_day.setdefault(cursor, set()).add(kind)
    return out
