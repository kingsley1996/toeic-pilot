"""Khu quản trị tầng AI: bấm chuông, xem thống kê, duyệt nhãn.

**Không endpoint nào ở đây chạy model.** API không import được `app.content`
(PHASE2-AUDIO §A4.1), nên nút "gắn nhãn" là một tiếng chuông Redis y hệt nút
sinh audio — nó trả 202 và không hứa nhãn đã có.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.ai_jobs import ring
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.ai import AiInteraction
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
    ModelTaskRow,
    ProviderDetail,
    ProviderModelDetail,
    QuestionLabelRow,
    SkillTagRequestAck,
    TestConnectionResult,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.services.ai_features import FEATURES
from app.services.ai_stats import collect
from app.services.labels import FACETS, LABELS, facets_for
from app.services.llm.pricing import known_models, rates_for
from app.services.llm.registry import load_registry

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


@router.get("/providers", response_model=list[ProviderDetail])
def list_providers(_: User = Depends(can_edit)) -> list[ProviderDetail]:
    """Mọi provider + model trong bảng giá, kèm base_url và trạng thái khoá.

    Nguồn duy nhất là `known_models()` (bảng giá) + `load_registry()`
    (llm_providers.json cho base_url/comment). Khoá có hay không được kiểm mà
    KHÔNG lộ giá trị: giao diện cần biết "khoá đã đặt chưa" để báo chỗ cần sửa,
    chứ không bao giờ được hiển thị khoá.
    """
    from app.core.config import settings
    from app.services.llm.openai_compatible import ENDPOINTS

    registry = load_registry(strict=False)
    by_provider: dict[str, ProviderDetail] = {}

    def configured(name: str, env_name: str) -> bool:
        if name == "ollama":
            return True  # model chạy máy, không cần khoá
        value = getattr(settings, f"{name}_api_key", None)
        if value:
            return True
        import os

        if os.environ.get(env_name):
            return True
        # CLI đọc `.env` trực tiếp (pydantic-settings không đưa vào os.environ).
        for candidate in (
            Path(__file__).parents[3] / ".env",
            Path(__file__).parents[4] / ".env",
        ):
            try:
                for line in candidate.read_text().splitlines():
                    raw = line.strip()
                    if raw.startswith(f"{env_name}=") and raw.split("=", 1)[1].strip():
                        return True
            except OSError:
                continue
        return False

    def detail(name: str, base_url: str | None, env_name: str | None) -> ProviderDetail:
        env = env_name or f"{name.upper()}_API_KEY"
        models = []
        for provider, model in known_models():
            if provider != name:
                continue
            rate_in, rate_out, rate_cached = rates_for(name, model)
            custom = registry.get(name)
            comment = None
            if custom:
                entry = custom.models.get(model)
                comment = entry.comment if entry else None
            models.append(
                ProviderModelDetail(
                    model=model,
                    rate_in=rate_in,
                    rate_out=rate_out,
                    rate_cached=rate_cached,
                    comment=comment,
                )
            )
        return ProviderDetail(
            provider=name,
            base_url=base_url,
            key_configured=configured(name, env),
            models=models,
        )

    for name, base_url in ENDPOINTS.items():
        by_provider[name] = detail(name, base_url, f"{name.upper()}_API_KEY")
    for name, custom in registry.items():
        by_provider[name] = detail(name, custom.base_url, custom.api_key_env)
    # ollama và openrouter là builtin không nằm trong ENDPOINTS.
    by_provider.setdefault("ollama", detail("ollama", settings.ollama_base_url, "OLLAMA_API_KEY"))
    by_provider.setdefault(
        "openrouter", detail("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY")
    )
    return [by_provider[name] for name in sorted(by_provider) if by_provider[name].models]


@router.get("/stats/models", response_model=list[ModelTaskRow])
def model_task_stats(
    _: User = Depends(can_edit), db: Session = Depends(get_db)
) -> list[ModelTaskRow]:
    """Hiệu quả từng model trong từng task (feature), từ sổ cái ai_interaction.

    Khác `/stats` (một con số gộp): trang so sánh cần tách theo (provider, model,
    feature) để trả lời "nên chọn model nào cho `exam_write`". Latency p50/p95
    tính riêng cho mỗi nhóm bằng cách nạp latency_ms của nhóm đó và lấy phân vị
    trong Python — `percentile_cont` chỉ có ở Postgres, còn bộ test chạy SQLite.
    """
    from dataclasses import dataclass, field
    from statistics import median, quantiles

    @dataclass
    class Group:
        calls: int = 0
        ok: int = 0
        error: int = 0
        refused: int = 0
        latency: list[int] = field(default_factory=list)

    rows = db.execute(
        select(
            AiInteraction.provider,
            AiInteraction.model,
            AiInteraction.feature,
            AiInteraction.status,
            AiInteraction.latency_ms,
        )
    ).all()

    groups: dict[tuple[str, str, str], Group] = {}
    for provider, model, feature, call_status, latency in rows:
        group = groups.setdefault((provider, model, feature), Group())
        group.calls += 1
        if call_status == "ok":
            group.ok += 1
            group.latency.append(int(latency))
        elif call_status == "error":
            group.error += 1
        else:
            group.refused += 1

    from decimal import Decimal

    out: list[ModelTaskRow] = []
    for (provider, model, feature), g in groups.items():
        lat = sorted(g.latency)
        p50 = int(median(lat)) if lat else None
        p95 = int(quantiles(lat, n=100)[94]) if len(lat) >= 95 else (p50 if p50 else None)
        out.append(
            ModelTaskRow(
                provider=provider,
                model=model,
                feature=feature,
                calls=g.calls,
                ok_calls=g.ok,
                error_calls=g.error,
                refused_calls=g.refused,
                success_rate=round(g.ok / g.calls, 4) if g.calls else 0.0,
                cost_usd=Decimal("0"),
                prompt_tokens=0,
                completion_tokens=0,
                latency_p50_ms=p50,
                latency_p95_ms=p95,
            )
        )
    out.sort(key=lambda r: (r.provider, r.model, r.feature))
    return out


@router.post("/test-connection", response_model=list[TestConnectionResult])
def test_connections(
    _: User = Depends(can_edit),
) -> list[TestConnectionResult]:
    """Gọi thật MỘT lượt model cho MỖI provider trong bảng giá.

    Trả về một kết quả mỗi model đã test — ok/latency hoặc lỗi. Đây là phép kiểm
    CONNECTION (khoá, endpoint, hạn mức, model tồn tại), không phải phép kiểm
    chất lượng: nội dung trả lời bị bỏ qua, chỉ latency và lỗi mới có nghĩa.

    Mỗi model một lượt gọi riêng để lỗi của model này không phủ lỗi của model
    khác (cùng provider nhưng một model 404 là chuyện có thật).
    """
    from app.services.llm.base import LLMRequest
    from app.services.llm.providers import build_providers

    pairs = known_models()
    provider_names = {p for p, _ in pairs}
    providers = build_providers(provider_names, strict=False)
    results: list[TestConnectionResult] = []
    for provider_name, model in pairs:
        provider = providers.get(provider_name)
        if provider is None:
            results.append(
                TestConnectionResult(
                    provider=provider_name, model=model, ok=False, error="thiếu khoá hoặc adapter"
                )
            )
            continue
        try:
            result = provider.complete(
                LLMRequest(system="", user="Reply with the word OK", max_tokens=5), model
            )
            results.append(
                TestConnectionResult(
                    provider=provider_name, model=model, ok=True, latency_ms=result.latency_ms
                )
            )
        except Exception as exc:  # noqa: BLE001 — lỗi kết nối là KẾT QUẢ, không phải lỗi endpoint
            results.append(
                TestConnectionResult(
                    provider=provider_name, model=model, ok=False, error=str(exc)[:300]
                )
            )
    return results


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
    `planning/docs/toeic_question_label_taxonomy.md`. Đây là nhóm (A) của luật phân
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
