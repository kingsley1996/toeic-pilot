"""Thống kê tầng AI, suy ra từ sổ cái — không có bảng tổng nào ghi song song.

Cùng luật đã áp cho `StoryProgress` và `user_progress` (nguyên tắc N3): một bảng
tổng sẽ lệch khỏi sổ cái ngay lần đầu có ai xoá một hàng, và không gì phát hiện
ra. Ở đây `ai_interaction` là sổ cái, và mọi con số dưới đây là một câu truy vấn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.ai import AiInteraction
from app.models.labels import QuestionLabel
from app.models.practice import Question
from app.services.labels import FACETS, LABELS

__all__ = ["FacetAccuracy", "FacetShare", "LlmStats", "collect"]


@dataclass(slots=True)
class Row:
    key: str
    calls: int
    cost_usd: Decimal
    prompt_tokens: int
    completion_tokens: int


@dataclass(slots=True)
class FacetAccuracy:
    facet: str
    label_vi: str
    labelled: int
    reviewed: int
    agreeing: int


@dataclass(slots=True)
class FacetShare:
    facet: str
    code: str
    label_vi: str
    count: int
    share: float


@dataclass(slots=True)
class LlmStats:
    total_calls: int = 0
    ok_calls: int = 0
    error_calls: int = 0
    refused_calls: int = 0
    cost_usd: Decimal = Decimal(0)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    latency_p50_ms: int = 0
    latency_p95_ms: int = 0
    by_feature: list[Row] = field(default_factory=list)
    by_model: list[Row] = field(default_factory=list)
    facets: list[FacetAccuracy] = field(default_factory=list)
    distribution: list[FacetShare] = field(default_factory=list)
    questions_total: int = 0
    questions_labelled: int = 0
    budget_hit_users: int = 0


def _rows(session: Session, column: InstrumentedAttribute[str]) -> list[Row]:
    stmt = (
        select(
            column,
            func.count(AiInteraction.id),
            func.coalesce(func.sum(AiInteraction.cost_usd), 0),
            func.coalesce(func.sum(AiInteraction.prompt_tokens), 0),
            func.coalesce(func.sum(AiInteraction.completion_tokens), 0),
        )
        .group_by(column)
        .order_by(func.count(AiInteraction.id).desc())
    )
    return [
        Row(str(key), int(calls), Decimal(str(cost)), int(pin), int(pout))
        for key, calls, cost, pin, pout in session.execute(stmt)
    ]


def _percentile(session: Session, fraction: float) -> int:
    """Trung vị và đuôi, bằng XẾP HẠNG GẦN NHẤT chứ không nội suy.

    Không dùng `avg`: một lượt gọi 60 giây kẹt hàng đợi kéo trung bình lên và
    che mất chuyện 90% số lượt vẫn nhanh. Đuôi mới là thứ người dùng cảm thấy.

    Không dùng `percentile_cont` dù nó đúng hơn: hàm đó **chỉ có ở Postgres**,
    còn bộ test chạy trên SQLite — nên một truy vấn thống kê viết bằng nó sẽ
    xanh ở production và nổ ở test, tức là nó chỉ được kiểm ở đúng nơi không cần
    kiểm. `ORDER BY ... LIMIT 1 OFFSET k` chạy trên cả hai và rẻ khi có index.
    """
    total = int(
        session.scalar(select(func.count(AiInteraction.id)).where(AiInteraction.status == "ok"))
        or 0
    )
    if total == 0:
        return 0
    index = min(int(total * fraction), total - 1)
    value = session.scalar(
        select(AiInteraction.latency_ms)
        .where(AiInteraction.status == "ok")
        .order_by(AiInteraction.latency_ms.asc())
        .limit(1)
        .offset(index)
    )
    return int(value or 0)


def _facet_stats(session: Session) -> tuple[list[FacetAccuracy], list[FacetShare]]:
    """Độ đúng và phân bố, tính RIÊNG cho từng mặt phân loại.

    Gộp sáu mặt vào một con số che mất thứ quyết định phải sửa prompt nào: máy
    có thể đoán rất tốt dạng câu hỏi mà rất tệ điểm ngữ pháp, và một con số
    trung bình 80% không nói được điều đó.

    Không còn ngưỡng "nhãn nhỏ nhất ≥5%, lớn nhất ≤30%" như bộ nhãn cũ. Ngưỡng
    ấy hiệu chỉnh cho 6–8 nhãn; với 72 mã thì mọi mã đều dưới 5% và bảng cảnh
    báo sẽ đỏ toàn bộ — một cảnh báo luôn bật là một cảnh báo không ai đọc.
    Phân bố vẫn được trả về để người đọc tự thấy mặt nào đang lệch.
    """
    rows = session.execute(
        select(
            QuestionLabel.facet,
            QuestionLabel.code,
            func.count(QuestionLabel.question_id),
            func.count(QuestionLabel.reviewed_at),
            func.count(QuestionLabel.reviewed_at).filter(
                QuestionLabel.code == QuestionLabel.proposed_code
            ),
        ).group_by(QuestionLabel.facet, QuestionLabel.code)
    ).all()

    per_facet: dict[str, list[int]] = {}
    shares: list[FacetShare] = []
    for facet, code, count, reviewed, agreeing in rows:
        bucket = per_facet.setdefault(str(facet), [0, 0, 0])
        bucket[0] += int(count)
        bucket[1] += int(reviewed)
        bucket[2] += int(agreeing)
        shares.append(
            FacetShare(
                facet=str(facet),
                code=str(code),
                label_vi=LABELS[str(code)].label_vi if str(code) in LABELS else str(code),
                count=int(count),
                share=0.0,
            )
        )

    names = {facet.key: facet.label_vi for facet in FACETS}
    accuracy = [
        FacetAccuracy(
            facet=key, label_vi=names.get(key, key), labelled=v[0], reviewed=v[1], agreeing=v[2]
        )
        for key, v in per_facet.items()
    ]
    for share in shares:
        total = per_facet[share.facet][0]
        share.share = round(share.count / total, 4) if total else 0.0
    shares.sort(key=lambda s: (s.facet, -s.count))
    accuracy.sort(key=lambda a: a.facet)
    return accuracy, shares


def collect(session: Session, *, window_days: int = 30) -> LlmStats:
    since = datetime.now(UTC) - timedelta(days=window_days)
    stats = LlmStats()

    # Đếm theo trạng thái bằng một group_by thay vì tám cột `case` trong một
    # select: cùng số lần đi database, mà đọc được và không phụ thuộc thứ tự cột.
    by_status = {
        str(status): int(count)
        for status, count in session.execute(
            select(AiInteraction.status, func.count(AiInteraction.id)).group_by(
                AiInteraction.status
            )
        ).all()
    }
    stats.ok_calls = by_status.get("ok", 0)
    stats.error_calls = by_status.get("error", 0)
    stats.refused_calls = by_status.get("refused", 0)
    stats.total_calls = sum(by_status.values())

    sums = session.execute(
        select(
            func.coalesce(func.sum(cast(AiInteraction.cost_usd, Numeric(14, 6))), 0),
            func.coalesce(func.sum(AiInteraction.prompt_tokens), 0),
            func.coalesce(func.sum(AiInteraction.completion_tokens), 0),
            func.coalesce(func.sum(AiInteraction.cached_tokens), 0),
        )
    ).one()
    stats.cost_usd = Decimal(str(sums[0]))
    stats.prompt_tokens = int(sums[1])
    stats.completion_tokens = int(sums[2])
    stats.cached_tokens = int(sums[3])

    stats.latency_p50_ms = _percentile(session, 0.5)
    stats.latency_p95_ms = _percentile(session, 0.95)
    stats.by_feature = _rows(session, AiInteraction.feature)
    stats.by_model = _rows(session, AiInteraction.model)
    stats.facets, stats.distribution = _facet_stats(session)
    stats.questions_total = int(session.scalar(select(func.count(Question.id))) or 0)
    stats.questions_labelled = int(
        session.scalar(select(func.count(func.distinct(QuestionLabel.question_id)))) or 0
    )

    stats.budget_hit_users = int(
        session.scalar(
            select(func.count(func.distinct(AiInteraction.user_id))).where(
                AiInteraction.status == "refused", AiInteraction.created_at >= since
            )
        )
        or 0
    )
    return stats
