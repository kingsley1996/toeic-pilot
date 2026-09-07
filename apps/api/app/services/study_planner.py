"""Planner V1 — rule-based, tất định (SPEC-PLACEMENT §5).

LLM kể lại, hệ thống quyết định (AI-PLAN N1): kỹ năng yếu là con số truy vấn
ra, mục kế hoạch là bản ghi nội dung tra ra — không có gì ở đây để model "sáng
tạo". Đầu vào: kết quả placement + `user_profile` (target, exam_date) snapshot
lúc sinh. Nhịp mục theo thời gian còn lại tới ngày thi: ít ngày → danh sách
ngắn hơn, tập trung nhất.

N4 áp cho từng mục: bài học không tồn tại thì mục không được ghi.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    AttemptItem,
    GrammarLesson,
    GrammarTopic,
    PlacementResult,
    Question,
    QuestionLabel,
    StudyPlan,
    StudyPlanItem,
    UserProfile,
)
from app.services.labels import LABELS

# Kỹ năng có mẫu số dưới ngưỡng này thì tỉ lệ của nó là nhiễu (1/2 có thể là
# trúng số) — không xếp mạnh, không xếp yếu.
MIN_SKILL_SAMPLE = 3
WEAK_RATIO = 0.5
# Mỗi mục là một buổi (~30 phút). Ít ngày thì danh sách ngắn đi, không dồn.
_ITEMS_FEW_DAYS = 6
_ITEMS_NORMAL = 10


@dataclass(frozen=True, slots=True)
class DraftItem:
    """Một mục kế hoạch trước khi ghi — cả hai planner cùng trả hình dạng này."""

    kind: str
    part: int
    ref_id: uuid.UUID | None
    label: str
    reason: str | None


def budget_for(today: date, exam_date: date | None) -> int:
    """Số mục tối đa — tên công khai vì planner LLM dùng chung phép này."""
    if exam_date is None:
        return _ITEMS_NORMAL
    return _ITEMS_FEW_DAYS if (exam_date - today).days <= 14 else _ITEMS_NORMAL


def weak_items(db: Session, attempt: Attempt) -> list[tuple[str, int, int]]:
    """Tên công khai của `_weak_skills` — planner LLM đọc cùng dữ liệu này."""
    return _weak_skills(db, attempt)


def _weak_skills(db: Session, attempt: Attempt) -> list[tuple[str, int, int]]:
    """(mã nhãn, đúng, tổng) của kỹ năng yếu, nhiều câu nhất trước. Cả hai
    facet: `question_type` cho dạng câu, `grammar` cho ngữ pháp P5/6."""
    rows = db.execute(
        select(QuestionLabel.code, QuestionLabel.facet, AttemptItem.is_correct)
        .join(Question, Question.id == AttemptItem.question_id)
        .join(QuestionLabel, QuestionLabel.question_id == Question.id)
        .where(
            AttemptItem.attempt_id == attempt.id,
            QuestionLabel.facet.in_(("question_type", "grammar")),
        )
    ).all()
    tally: dict[str, list[int]] = {}
    for code, _facet, is_correct in rows:
        if code is None:
            continue
        entry = tally.setdefault(code, [0, 0])
        entry[0] += 1 if is_correct else 0
        entry[1] += 1
    return sorted(
        (
            (code, correct, count)
            for code, (correct, count) in tally.items()
            if code in LABELS and count >= MIN_SKILL_SAMPLE and correct / count < WEAK_RATIO
        ),
        key=lambda item: (-item[2], item[0]),
    )


def _drill_part_for_skill(code: str) -> int | None:
    """Part cần luyện cho một dạng câu yếu — `Label.parts` khai sẵn ở registry
    (`PART_7_INFORMATION_RETRIEVAL` → part 7). Mã ngoài registry → None."""
    label = LABELS.get(code)
    return label.parts[0] if label and label.parts else None


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
            if count >= MIN_SKILL_SAMPLE and correct / count < WEAK_RATIO
        ),
        key=lambda item: item[1] / item[2],
    )


def write_plan(
    db: Session,
    user_id: uuid.UUID,
    attempt: Attempt,
    items: list[DraftItem],
    *,
    source: str = "rule",
) -> StudyPlan:
    """Ghi danh sách mục thành kế hoạch hiện hành — phần dùng chung của cả hai
    planner. Hạ kế hoạch cũ trong cùng giao dịch: hai kế hoạch hiện hành không
    bao giờ cùng tồn tại, dù hai request tới cạnh nhau."""
    profile = db.get(UserProfile, user_id)

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
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def generate_plan(db: Session, user_id: uuid.UUID, attempt: Attempt) -> StudyPlan:
    """Sinh kế hoạch hiện hành mới từ một lượt placement ĐÃ phân tích."""
    result = db.get(PlacementResult, attempt.id)
    if result is None or result.estimator_version == "pending":
        raise ValueError("lượt làm này chưa được phân tích")

    profile = db.get(UserProfile, user_id)
    exam_date = profile.exam_date if profile else None
    today = datetime.now(UTC).date()
    budget = budget_for(today, exam_date)
    position = 1
    drilled_parts: set[int] = set()
    items: list[DraftItem] = []

    # 1. Kỹ năng yếu, yếu nhất trước. Mã `grammar` → bài học đầu tiên của chủ
    #    đề cùng mã; mã `question_type` → drill part khai trong registry. Mục
    #    không map được chỗ ôn thì bỏ (N4) — nhưng KHÔNG để một weakness có
    #    chỗ luyện nằm ngoài kế hoạch chỉ vì nó không phải ngữ pháp.
    weak = _weak_skills(db, attempt)
    for code, correct, count in weak:
        if position > budget:
            break
        label = LABELS[code]
        topic = None
        if code.startswith("GRAMMAR_"):
            topic = db.scalar(
                select(GrammarTopic).where(
                    GrammarTopic.code == code, GrammarTopic.status == "published"
                )
            )
        if topic is not None:
            lesson = db.scalar(
                select(GrammarLesson)
                .where(GrammarLesson.topic_id == topic.id, GrammarLesson.status == "published")
                .order_by(GrammarLesson.position)
                .limit(1)
            )
            if lesson is None:
                continue
            items.append(
                DraftItem(
                    kind="grammar_lesson",
                    part=5,
                    ref_id=lesson.id,
                    label=f"Ôn {topic.title}",
                    reason=f"Đúng {correct}/{count} câu ở kỹ năng này",
                )
            )
            position += 1
            continue
        # question_type (hoặc mã grammar không có chủ đề): drill part của nó.
        part = label.parts[0] if label.parts else None
        if part is not None and part not in drilled_parts:
            drilled_parts.add(part)
            items.append(
                DraftItem(
                    kind="part_drill",
                    part=part,
                    ref_id=None,
                    label=f"Luyện Part {part}",
                    reason=f"Yếu dạng '{label.label_vi}' — đúng {correct}/{count} câu",
                )
            )
            position += 1

    # 2. Part yếu TỔNG THỂ (cả part <50%) mà chưa được drill từ vòng 1 — dạng
    #    câu yếu đã kéo part đó vào rồi, đây là part yếu đều mà không có một
    #    dạng nào nổi bật.
    for part, correct, count in _weak_parts(db, attempt):
        if position > budget:
            break
        if part in drilled_parts:
            continue
        drilled_parts.add(part)
        items.append(
            DraftItem(
                kind="part_drill",
                part=part,
                ref_id=None,
                label=f"Luyện Part {part}",
                reason=f"Đúng {correct}/{count} câu ở part này",
            )
        )
        position += 1

    return write_plan(db, user_id, attempt, items, source="rule")
