"""Khu quản trị tầng AI: bấm chuông, xem thống kê, duyệt nhãn.

**Không endpoint nào ở đây chạy model.** API không import được `app.content`
(PHASE2-AUDIO §A4.1), nên nút "gắn nhãn" là một tiếng chuông Redis y hệt nút
sinh audio — nó trả 202 và không hứa nhãn đã có.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.ai_jobs import ring
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.ai_config import AiFeatureConfig
from app.models.labels import QuestionLabel, QuestionSetLabel
from app.models.practice import PracticeTest, PracticeTestQuestion, Question
from app.models.user import User
from app.schemas.ai import (
    AiFeatureRow,
    AiFeatureWrite,
    FacetCatalog,
    KnownModel,
    LabelCatalogItem,
    LabelValue,
    LabelWrite,
    LlmStatsPublic,
    QuestionLabelRow,
    SkillTagRequestAck,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.services.ai_features import FEATURES
from app.services.ai_stats import collect
from app.services.labels import FACETS, LABELS, facets_for
from app.services.llm.pricing import known_models

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])

can_edit = require_role("editor", "admin")


@router.post(
    "/skill-tags/requests",
    response_model=SkillTagRequestAck,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_skill_tags(
    _: User = Depends(can_edit),
    client: redis.Redis = Depends(get_redis),
) -> SkillTagRequestAck:
    """Đánh chuông cho worker gắn nhãn. **Không** gắn nhãn ở đây.

    202 chứ không 200: nó không hứa nhãn đã có. Không ghi bảng nào — hàng đợi
    vẫn là *câu hỏi* "câu nào còn thiếu nhãn", nên bấm mười lần không tạo mười
    job. Redis chết vẫn trả 202 với `queued=false`, vì vòng quét định kỳ của
    worker tìm được đúng ngần ấy việc.
    """
    return SkillTagRequestAck(queued=ring(client))


@router.get("/features", response_model=list[AiFeatureRow])
def list_features(_: User = Depends(can_edit), db: Session = Depends(get_db)) -> list[AiFeatureRow]:
    """Mảng trần: danh sách tính năng bị chặn trên bởi chính mã nguồn.

    Nhóm (A) của luật phân trang ở `schemas/common.py` — bọc `Page` quanh bốn
    hàng cố định bắt giao diện xử lý một trường hợp không thể xảy ra.
    """
    rows = {row.feature: row for row in db.scalars(select(AiFeatureConfig))}
    names = (
        {
            user_id: email
            for user_id, email in db.execute(
                select(User.id, User.email).where(
                    User.id.in_([r.updated_by for r in rows.values() if r.updated_by])
                )
            ).all()
        }
        if rows
        else {}
    )
    return [
        AiFeatureRow(
            key=feature.key,
            label_vi=feature.label_vi,
            description_vi=feature.description_vi,
            provider=rows[feature.key].provider if feature.key in rows else None,
            model=rows[feature.key].model if feature.key in rows else None,
            enabled=rows[feature.key].enabled if feature.key in rows else True,
            configured=feature.key in rows,
            updated_at=rows[feature.key].updated_at if feature.key in rows else None,
            updated_by=(names.get(rows[feature.key].updated_by) if feature.key in rows else None),
        )
        for feature in FEATURES
    ]


@router.get("/models", response_model=list[KnownModel])
def list_models(_: User = Depends(can_edit)) -> list[KnownModel]:
    """Chỉ model có trong bảng giá.

    Cho gõ tay tên model nghĩa là một lần gõ nhầm làm mọi lượt gọi của tính năng
    đó hỏng ngay — `cost_usd` ném lỗi với model lạ chứ không ghi 0. Hành vi đó
    đúng, nhưng nó phải hỏng ở chỗ CHỌN chứ không ở chỗ CHẠY.
    """
    return [KnownModel(provider=p, model=m) for p, m in known_models()]


@router.put("/features/{feature}", response_model=AiFeatureRow)
def set_feature(
    feature: str,
    body: AiFeatureWrite,
    editor: User = Depends(can_edit),
    db: Session = Depends(get_db),
) -> AiFeatureRow:
    """Đổi nhà cung cấp/model của một tính năng, hoặc tắt hẳn nó.

    **Không có trường khoá API ở đây, và sẽ không bao giờ có.** Một ô nhập khoá
    trên giao diện là một khoá sẽ lọt vào log, ảnh chụp màn hình và bản sao lưu.
    """
    if not any(f.key == feature for f in FEATURES):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Không có tính năng {feature!r}"
        )
    if (body.provider, body.model) not in known_models():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Chưa có giá cho {body.provider}/{body.model} — thêm vào bảng giá trước",
        )

    row = db.get(AiFeatureConfig, feature)
    if row is None:
        row = AiFeatureConfig(feature=feature)
        db.add(row)
    row.provider = body.provider
    row.model = body.model
    row.enabled = body.enabled
    row.updated_by = editor.id
    db.commit()
    db.refresh(row)

    spec = next(f for f in FEATURES if f.key == feature)
    return AiFeatureRow(
        key=spec.key,
        label_vi=spec.label_vi,
        description_vi=spec.description_vi,
        provider=row.provider,
        model=row.model,
        enabled=row.enabled,
        configured=True,
        updated_at=row.updated_at,
        updated_by=editor.email,
    )


@router.get("/stats", response_model=LlmStatsPublic)
def llm_stats(_: User = Depends(can_edit), db: Session = Depends(get_db)) -> LlmStatsPublic:
    return LlmStatsPublic.model_validate(collect(db), from_attributes=True)


@router.get("/labels/catalog", response_model=list[FacetCatalog])
def label_catalog(_: User = Depends(can_edit)) -> list[FacetCatalog]:
    """Mảng trần, không bọc `Page`.

    Bộ nhãn bị chặn trên bởi chính miền — 72 mã khai báo trong mã nguồn, sinh từ
    `planning/toeic_question_label_taxonomy.md`. Đây là nhóm (A) của luật phân
    trang ở `schemas/common.py`: bọc lại "cho nhất quán" bắt giao diện xử lý một
    trường hợp không thể xảy ra.
    """
    return [
        FacetCatalog(
            key=facet.key,
            label_vi=facet.label_vi,
            owner=facet.owner,
            labels=[
                LabelCatalogItem(code=x.code, label_vi=x.label_vi, parts=list(x.parts))
                for x in facet.labels
            ],
        )
        for facet in FACETS
    ]


def _values(
    rows: list[QuestionLabel] | list[QuestionSetLabel], names: dict[uuid.UUID, str]
) -> list[LabelValue]:
    return [
        LabelValue(
            facet=row.facet,
            code=row.code,
            proposed_code=row.proposed_code,
            reviewed_at=row.reviewed_at,
            reviewed_by=names.get(row.reviewed_by) if row.reviewed_by else None,
        )
        for row in rows
    ]


@router.get("/labels", response_model=Page[QuestionLabelRow])
def list_labels(
    _: User = Depends(can_edit),
    db: Session = Depends(get_db),
    state: str = Query("all", pattern="^(all|unlabelled|unreviewed|disagreeing)$"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[QuestionLabelRow]:
    """Câu hỏi kèm nhãn của chính nó và nhãn của ngữ liệu dùng chung.

    `disagreeing` là bộ lọc đáng giá nhất: những mặt người đã sửa khác nhãn máy
    đề xuất. Mỗi hàng ở đó là một lần máy sai, và đọc mười hàng như thế nói
    nhiều hơn một con số phần trăm.
    """
    query = select(Question)
    labelled = select(QuestionLabel.question_id)
    if state == "unlabelled":
        query = query.where(Question.id.not_in(labelled))
    elif state == "unreviewed":
        query = query.where(
            Question.id.in_(
                select(QuestionLabel.question_id).where(QuestionLabel.reviewed_at.is_(None))
            )
        )
    elif state == "disagreeing":
        query = query.where(
            Question.id.in_(
                select(QuestionLabel.question_id).where(
                    QuestionLabel.reviewed_at.is_not(None),
                    QuestionLabel.proposed_code.is_not(None),
                    QuestionLabel.code != QuestionLabel.proposed_code,
                )
            )
        )
    # `id` làm khoá phụ: `part` không phải thứ tự toàn phần, nên thiếu nó thì với
    # LIMIT/OFFSET một hàng có thể hiện ở hai trang còn hàng khác biến mất.
    rows = list(db.scalars(query.order_by(Question.part, Question.id).limit(limit).offset(offset)))
    ids = [q.id for q in rows]
    set_ids = [q.set_id for q in rows if q.set_id is not None]

    q_labels = list(db.scalars(select(QuestionLabel).where(QuestionLabel.question_id.in_(ids))))
    s_labels = list(
        db.scalars(select(QuestionSetLabel).where(QuestionSetLabel.set_id.in_(set_ids)))
    )
    names = _reviewer_names(db, q_labels, s_labels)
    numbers = _numbers_for(db, ids)

    # Hai tên khác nhau cho hai vòng lặp khác kiểu. Dùng lại `row` thì mypy khoá
    # kiểu ở lần gán đầu và vòng thứ hai báo lỗi — nhưng quan trọng hơn: đây
    # đúng họ với lỗi `total` bị che trong `list_attempts`, nơi một cái tên dùng
    # lại đã trả về sai con số mà không ai thấy trên bản diff.
    by_question: dict[uuid.UUID, list[QuestionLabel]] = {}
    for q_label in q_labels:
        by_question.setdefault(q_label.question_id, []).append(q_label)
    by_set: dict[uuid.UUID, list[QuestionSetLabel]] = {}
    for s_label in s_labels:
        by_set.setdefault(s_label.set_id, []).append(s_label)

    return page_of(
        [
            QuestionLabelRow(
                id=q.id,
                part=q.part,
                question_number=numbers.get(q.id, (None, None, None))[0],
                prompt_text=q.prompt_text,
                test_slug=numbers.get(q.id, (None, None, None))[1],
                test_title=numbers.get(q.id, (None, None, None))[2],
                set_id=q.set_id,
                labels=_values(by_question.get(q.id, []), names),
                set_labels=_values(by_set.get(q.set_id, []) if q.set_id else [], names),
            )
            for q in rows
        ],
        count_rows(db, query),
        limit,
        offset,
    )


def _reviewer_names(
    db: Session, q_labels: list[QuestionLabel], s_labels: list[QuestionSetLabel]
) -> dict[uuid.UUID, str]:
    """Tra tên người kiểm một lượt cho cả trang — tra từng hàng là N+1."""
    ids = {r.reviewed_by for r in q_labels if r.reviewed_by} | {
        r.reviewed_by for r in s_labels if r.reviewed_by
    }
    if not ids:
        return {}
    return {
        user_id: email
        for user_id, email in db.execute(select(User.id, User.email).where(User.id.in_(ids))).all()
    }


def _numbers_for(
    db: Session, ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int | None, str | None, str | None]]:
    """Số câu và đề chứa nó, tra một lượt cho cả trang."""
    if not ids:
        return {}
    rows = db.execute(
        select(
            PracticeTestQuestion.question_id,
            PracticeTestQuestion.number,
            PracticeTest.slug,
            PracticeTest.title,
        )
        .join(PracticeTest, PracticeTest.id == PracticeTestQuestion.test_id)
        .where(PracticeTestQuestion.question_id.in_(ids))
    ).all()
    return {qid: (int(number), slug, title) for qid, number, slug, title in rows}


def _check(facet: str, code: str, part: int, owner: str) -> None:
    """Nhãn phải có thật, phải thuộc đúng mặt, và phải hợp lệ với part này.

    Ba phép kiểm chứ không một, vì ba kiểu sai khác nhau đều im lặng: một mã
    bịa làm `GROUP BY` mọc thêm nhóm; một mã đúng nhưng sai mặt sẽ ghi đè nhãn
    của mặt khác qua khoá chính; và một mã hợp lệ với part khác — `GRAMMAR_NOUN`
    có ở Part 5 mà không có ở Part 6 — sẽ tạo ra thống kê cho một thứ đề thi
    không kiểm ở đó.
    """
    label = LABELS.get(code)
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nhãn {code!r} không có trong bộ phân loại",
        )
    match = next((f for f in FACETS if f.key == facet), None)
    if match is None or label not in match.labels:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nhãn {code!r} không thuộc mặt {facet!r}",
        )
    if match.owner != owner:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Mặt {facet!r} thuộc về {match.owner}, không phải {owner}",
        )
    if part not in label.parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nhãn {code!r} không dùng cho Part {part}",
        )


@router.patch("/labels/{question_id}", response_model=LabelValue)
def review_question_label(
    question_id: uuid.UUID,
    body: LabelWrite,
    reviewer: User = Depends(can_edit),
    db: Session = Depends(get_db),
) -> LabelValue:
    """Xác nhận hoặc sửa nhãn của MỘT mặt trên một câu hỏi.

    **`proposed_code` không bị đụng tới.** Đó là điều khiến KPI độ đúng đo được:
    giữ lại nhãn máy đề xuất sau khi người sửa là cách duy nhất biết người đó đã
    phải sửa hay chỉ xác nhận.
    """
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có câu hỏi này")
    _check(body.facet, body.code, question.part, "question")

    row = db.get(QuestionLabel, (question_id, body.facet))
    if row is None:
        row = QuestionLabel(question_id=question_id, facet=body.facet, code=body.code)
        db.add(row)
    else:
        row.code = body.code
    row.reviewed_at = datetime.now(UTC)
    # Người kiểm lấy từ PHIÊN ĐĂNG NHẬP, không từ body: để client tự khai là mở
    # đường ghi tên người khác vào việc mình làm.
    row.reviewed_by = reviewer.id
    db.commit()
    return LabelValue(
        facet=row.facet,
        code=row.code,
        proposed_code=row.proposed_code,
        reviewed_at=row.reviewed_at,
        reviewed_by=reviewer.email,
    )


@router.patch("/set-labels/{set_id}", response_model=LabelValue)
def review_set_label(
    set_id: uuid.UUID,
    body: LabelWrite,
    reviewer: User = Depends(can_edit),
    db: Session = Depends(get_db),
) -> LabelValue:
    """Nhãn của ngữ liệu dùng chung — sửa MỘT lần cho cả nhóm câu.

    Đây chính là lý do bốn mặt này không treo trên câu: sửa chủ đề một hội thoại
    Part 3 là một thao tác, không phải ba thao tác phải nhớ làm cho đủ.
    """
    from app.models.practice import QuestionSet

    group = db.get(QuestionSet, set_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có nhóm này")
    _check(body.facet, body.code, group.part, "set")

    row = db.get(QuestionSetLabel, (set_id, body.facet))
    if row is None:
        row = QuestionSetLabel(set_id=set_id, facet=body.facet, code=body.code)
        db.add(row)
    else:
        row.code = body.code
    row.reviewed_at = datetime.now(UTC)
    row.reviewed_by = reviewer.id
    db.commit()
    return LabelValue(
        facet=row.facet,
        code=row.code,
        proposed_code=row.proposed_code,
        reviewed_at=row.reviewed_at,
        reviewed_by=reviewer.email,
    )


__all__ = ["facets_for", "router"]
