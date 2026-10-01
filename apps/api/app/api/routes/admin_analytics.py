"""Phân tích chất lượng đề cho màn admin: độ khó, taxonomy, media, so sánh liên đề.

Ba endpoint, toàn bộ là SELECT (+ đọc blueprint.json trên đĩa nếu có):

- `GET /tests` — một hàng mỗi đề, để màn hình chọn đề so sánh.
- `GET /tests/{slug}` — "khóa chất lượng" của một đề.
- `GET /compare?slugs=a,b` — cùng khóa đó cho nhiều đề, đặt cạnh nhau.

Độ khó "dự kiến" lấy từ blueprint (`hard` từng ô — cột `difficulty` trong DB
hiện mọi câu đều là 3 vì pipeline load không truyền, nên đếm nó chỉ để lộ ra
sự thật đó chứ không dùng làm thước đo). Độ khó "thực tế" là p-value từ
`attempt_item` của các lượt đã nộp — đề chưa ai làm thì `performance` trống,
không phải lỗi.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models import (
    Attempt,
    AttemptItem,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionLabel,
    QuestionOption,
    QuestionSet,
    QuestionSetLabel,
    User,
)
from app.models.practice import LISTENING_PARTS
from app.schemas.admin_analytics import (
    AnalyticsFlag,
    CompareOut,
    FacetCodeCount,
    FacetKey,
    PartKey,
    PerformanceKey,
    ReviewKey,
    TestAnalytics,
    TestAnalyticsRow,
)
from app.services.labels import FACETS

router = APIRouter(prefix="/admin/analytics", tags=["admin"])

can_edit = require_role("editor", "admin")

# Ngưỡng cờ lệch đáp án: cùng con số cổng `check_answer_spread` của pipeline
# dùng khi sinh đề, để dashboard và pipeline không cãi nhau về "lệch là gì".
ANSWER_SKEW_LIMIT = 0.4
COMPARE_MAX = 6

_FACET_VI = {facet.key: facet.label_vi for facet in FACETS}
_CODE_VI = {label.code: label.label_vi for facet in FACETS for label in facet.labels}
# Mặt nào xét trên những part nào: hợp các part của mọi mã trong mặt đó.
_FACET_PARTS = {
    facet.key: sorted({part for label in facet.labels for part in label.parts}) for facet in FACETS
}
_FACET_OWNER = {facet.key: facet.owner for facet in FACETS}

_GENERATED_DIR = Path(__file__).resolve().parents[3] / "content" / "generated"


def _blueprint_hard(slug: str) -> dict[int, int] | None:
    """Số ô `hard` theo part trong blueprint — None khi không có file.

    `hard` KHÔNG phải độ khó của câu hỏi: nó là ràng buộc sinh đề — mỗi ô phải
    có bấy nhiêu câu ghép chứng cứ từ hai chỗ tách rời (trục D1). P3/P4 bị ép
    cứng `hard=1` mọi ô nên con số này không phân biệt được câu nào khó hơn câu
    nào; dashboard hiện nó để đối chiếu blueprint chứ không dùng làm thước đo.
    """
    path = _GENERATED_DIR / slug / "blueprint.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    parts = data.get("parts") if isinstance(data, dict) else None
    if not isinstance(parts, list):
        return None
    out: dict[int, int] = {}
    for block in parts:
        if not isinstance(block, dict):
            continue
        part = block.get("part")
        for slot in block.get("slots", []):
            if isinstance(slot, dict) and slot.get("hard") and isinstance(part, int):
                out[part] = out.get(part, 0) + 1
    return out


def _test_or_404(db: Session, slug: str) -> PracticeTest:
    test = db.scalars(select(PracticeTest).where(PracticeTest.slug == slug)).one_or_none()
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có đề này")
    return test


def _analyze(db: Session, test: PracticeTest) -> TestAnalytics:
    qids = select(PracticeTestQuestion.question_id).where(PracticeTestQuestion.test_id == test.id)
    questions = db.scalars(select(Question).where(Question.id.in_(qids))).all()
    by_id = {question.id: question for question in questions}

    set_audio = {
        row.id: row.audio_asset_id is not None
        for row in db.scalars(
            select(QuestionSet).where(
                QuestionSet.id.in_({q.set_id for q in questions if q.set_id is not None} or {None})
            )
        ).all()
    }

    correct = db.execute(
        select(QuestionOption.question_id, QuestionOption.label).where(
            QuestionOption.question_id.in_(qids), QuestionOption.is_correct.is_(True)
        )
    ).all()

    parts: dict[int, PartKey] = {}
    for question in questions:
        key = parts.setdefault(
            question.part,
            PartKey(part=question.part, count=0, answers={}, difficulty={}),
        )
        key.count += 1
        level = str(question.difficulty)
        key.difficulty[level] = key.difficulty.get(level, 0) + 1
        if (question.audio_asset_id is not None) or (
            question.set_id is not None and set_audio.get(question.set_id, False)
        ):
            key.audio_covered += 1
        if question.image_asset_id is not None:
            key.image_covered += 1
        if (question.explanation or "").strip():
            key.explained += 1
    for question_id, label in correct:
        answered = by_id.get(question_id)
        if answered is not None:
            key = parts[answered.part]
            key.answers[label] = key.answers.get(label, 0) + 1

    hard = _blueprint_hard(test.slug)
    for part, key in parts.items():
        key.hard_planned = hard.get(part, 0) if hard is not None else None

    # --- taxonomy: nhãn câu + nhãn cụm, quy về "mỗi câu mang gì" ---------------
    q_labels = (
        db.execute(select(QuestionLabel).where(QuestionLabel.question_id.in_(qids))).scalars().all()
    )
    s_labels = (
        db.execute(
            select(QuestionSetLabel).where(
                QuestionSetLabel.set_id.in_(
                    {q.set_id for q in questions if q.set_id is not None} or {None}
                )
            )
        )
        .scalars()
        .all()
    )
    set_code: dict[tuple[object, str], QuestionSetLabel] = {
        (row.set_id, row.facet): row for row in s_labels
    }

    facets: list[FacetKey] = []
    reviewed = agree = 0
    total_labels = len(q_labels) + len(s_labels)
    for row in list(q_labels) + list(s_labels):
        if row.reviewed_at is not None:
            reviewed += 1
            if row.proposed_code is not None and row.code == row.proposed_code:
                agree += 1
    for facet_key in _FACET_VI:
        owner = _FACET_OWNER[facet_key]
        relevant = [q for q in questions if q.part in _FACET_PARTS[facet_key]]
        counts: dict[str, int] = {}
        if owner == "question":
            covered_qids = {row.question_id for row in q_labels if row.facet == facet_key}
            for row in q_labels:
                if row.facet == facet_key:
                    counts[row.code] = counts.get(row.code, 0) + 1
            covered = len(covered_qids & by_id.keys())
        else:
            for question in relevant:
                set_row = set_code.get((question.set_id, facet_key))
                if set_row is not None:
                    counts[set_row.code] = counts.get(set_row.code, 0) + 1
            covered = sum(1 for q in relevant if (q.set_id, facet_key) in set_code)
        facets.append(
            FacetKey(
                facet=facet_key,
                label_vi=_FACET_VI[facet_key],
                codes=[
                    FacetCodeCount(code=code, label_vi=_CODE_VI.get(code, code), count=count)
                    for code, count in sorted(counts.items(), key=lambda kv: -kv[1])
                ],
                missing=len(relevant) - covered,
            )
        )

    # --- p-value từ lượt đã nộp -------------------------------------------------
    attempt_ids = select(Attempt.id).where(
        Attempt.test_id == test.id, Attempt.status == "submitted"
    )
    items = db.execute(
        select(AttemptItem.question_id, AttemptItem.is_correct).where(
            AttemptItem.attempt_id.in_(attempt_ids),
            AttemptItem.question_id.in_(qids),
            AttemptItem.is_correct.is_not(None),
        )
    ).all()
    n_attempts = len(
        db.scalars(
            select(Attempt.id).where(Attempt.test_id == test.id, Attempt.status == "submitted")
        ).all()
    )
    per_part_hits: dict[int, list[int]] = {}
    for question_id, ok in items:
        item_q = by_id.get(question_id)
        if item_q is not None:
            per_part_hits.setdefault(item_q.part, []).append(1 if ok else 0)
    per_part = {
        str(part): (round(sum(hits) / len(hits), 3) if hits else None)
        for part, hits in per_part_hits.items()
    }
    all_hits = [h for hits in per_part_hits.values() for h in hits]
    performance = PerformanceKey(
        attempts=n_attempts,
        avg_p=round(sum(all_hits) / len(all_hits), 3) if all_hits else None,
        per_part=per_part,
    )

    # --- cờ --------------------------------------------------------------------
    flags: list[AnalyticsFlag] = []
    total = len(questions)
    if total >= 8:
        spread = {label: sum(p.answers.get(label, 0) for p in parts.values()) for label in "ABCD"}
        for label, count in spread.items():
            if count / total > ANSWER_SKEW_LIMIT:
                flags.append(
                    AnalyticsFlag(
                        code="ANSWER_SKEW",
                        message=f"Đáp án {label} chiếm {count}/{total} câu "
                        f"({count / total:.0%}), quá ngưỡng {ANSWER_SKEW_LIMIT:.0%}",
                    )
                )
    for key in parts.values():
        if key.part in LISTENING_PARTS and key.audio_covered < key.count:
            flags.append(
                AnalyticsFlag(
                    code="AUDIO_GAP",
                    message=f"Part {key.part} thiếu audio "
                    f"{key.count - key.audio_covered}/{key.count} câu",
                    part=key.part,
                )
            )
        if key.part == 1 and key.image_covered < key.count:
            flags.append(
                AnalyticsFlag(
                    code="IMAGE_GAP",
                    message=f"Part 1 thiếu ảnh {key.count - key.image_covered}/{key.count} câu",
                    part=1,
                )
            )
        if key.explained < key.count:
            flags.append(
                AnalyticsFlag(
                    code="EXPLANATION_GAP",
                    message=f"Part {key.part} thiếu giải thích "
                    f"{key.count - key.explained}/{key.count} câu",
                    part=key.part,
                )
            )
    for facet in facets:
        if facet.missing > 0:
            flags.append(
                AnalyticsFlag(
                    code="LABEL_GAP",
                    message=f"Mặt {facet.label_vi} thiếu nhãn {facet.missing} câu",
                )
            )

    return TestAnalytics(
        slug=test.slug,
        title=test.title,
        kind=test.kind,
        status=test.status,
        total=total,
        parts=[parts[part] for part in sorted(parts)],
        facets=facets,
        review=ReviewKey(labels_total=total_labels, reviewed=reviewed, agree=agree),
        performance=performance,
        flags=flags,
    )


@router.get("/tests", response_model=list[TestAnalyticsRow])
def list_analytics_tests(
    db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[TestAnalyticsRow]:
    """Một hàng mỗi đề + số câu, để màn hình chọn đề so sánh."""
    tests = db.scalars(select(PracticeTest).order_by(PracticeTest.slug)).all()
    rows: list[TestAnalyticsRow] = []
    for test in tests:
        total = len(
            db.scalars(
                select(PracticeTestQuestion.question_id).where(
                    PracticeTestQuestion.test_id == test.id
                )
            ).all()
        )
        rows.append(
            TestAnalyticsRow(
                slug=test.slug,
                title=test.title,
                kind=test.kind,
                status=test.status,
                total=total,
            )
        )
    return rows


@router.get("/tests/{slug}", response_model=TestAnalytics)
def test_key(
    slug: str, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> TestAnalytics:
    return _analyze(db, _test_or_404(db, slug))


@router.get("/compare", response_model=CompareOut)
def compare(
    slugs: str = Query(description="danh sách slug cách nhau bằng dấu phẩy, tối đa 6"),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> CompareOut:
    wanted = [slug.strip() for slug in slugs.split(",") if slug.strip()]
    if not wanted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Chưa chọn đề nào để so sánh"
        )
    if len(wanted) > COMPARE_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"So sánh tối đa {COMPARE_MAX} đề một lúc",
        )
    return CompareOut(tests=[_analyze(db, _test_or_404(db, slug)) for slug in wanted])
