"""Một chỗ duy nhất mà mọi lượt gọi LLM đi qua.

Gộp bốn việc lại vì cả bốn phải xảy ra cùng nhau hoặc không việc nào có nghĩa:
kiểm hạn mức, chọn tầng, gọi, ghi sổ. Tách ra thì sẽ có một ngày ai đó gọi thẳng
adapter "cho nhanh" và lượt gọi đó không nằm trong hạn mức lẫn trong sổ cái —
tức là chi phí không đo được, đúng thứ `REVIEW-OPUS` §7d cảnh báo.

**Sổ cái ghi bằng phiên làm việc RIÊNG.** Tiền đã tiêu là một sự thật đã xảy ra;
nếu ghi chung phiên với request, một lỗi ở bước sau sẽ rollback và xoá luôn bản
ghi chi phí — hoá đơn vẫn tới nhưng sổ không có dòng nào. Factory được tiêm vào
chứ không gọi `SessionLocal()` thẳng, cùng lý do `AudioFactory` nhận
`duration_probe` và `joiner`: nếu không, không nhánh nào của lớp này chạy được
ngoài một máy đã dựng đầy đủ.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter

import redis
from sqlalchemy.orm import Session

from app.core.ai_budget import Budget, BudgetExceeded, BudgetUnavailable, micro_usd
from app.models.ai import AiInteraction
from app.services.llm.base import (
    FeatureDisabled,
    LLMError,
    LLMRequest,
    LLMResult,
    Provider,
    Usage,
)
from app.services.llm.pricing import cost_usd
from app.services.llm.router import Route, Tier, route_for

__all__ = ["Gateway"]


@dataclass(slots=True)
class Gateway:
    providers: Mapping[str, Provider]
    routes: Mapping[Tier, tuple[str, str]]
    budget: Budget
    redis_client: redis.Redis
    session_factory: Callable[[], Session]
    # Tra cấu hình theo TÍNH NĂNG. Trả `None` nghĩa là tính năng chưa được cấu
    # hình riêng và rơi về bảng tầng ở `routes`. Là một hàm tiêm vào chứ không
    # phải truy vấn thẳng, cùng lý do `session_factory` là seam: nếu không, mọi
    # test chạm gateway đều phải dựng một hàng cấu hình.
    resolve_feature: Callable[[str], tuple[str, str, bool] | None] | None = None

    def run(
        self,
        request: LLMRequest,
        *,
        feature: str,
        tier: Tier,
        user_id: uuid.UUID | None = None,
        prompt_version: str | None = None,
        request_id: str | None = None,
    ) -> LLMResult:
        route = route_for(tier, dict(self.routes))
        override = self.resolve_feature(feature) if self.resolve_feature else None
        if override is not None:
            provider_name, model, enabled = override
            if not enabled:
                # Ghi lại việc TỪ CHỐI. Bỏ hàng này thì không ai biết một tính
                # năng đã bị tắt bao lâu và chặn bao nhiêu lượt — và câu hỏi đó
                # luôn được hỏi ngay sau khi có người phàn nàn.
                self._record(
                    feature=feature,
                    route=route,
                    usage=Usage(),
                    cost=Decimal(0),
                    latency_ms=0,
                    status="refused",
                    error=f"tính năng {feature} đang tắt",
                    user_id=user_id,
                    prompt_version=prompt_version,
                    request_id=request_id,
                )
                raise FeatureDisabled(f"Tính năng {feature} đang tắt")
            route = Route(tier=tier, provider=provider_name, model=model)

        if user_id is not None:
            try:
                self.budget.check(self.redis_client, str(user_id))
            except (BudgetExceeded, BudgetUnavailable) as exc:
                # Lượt bị TỪ CHỐI vẫn là một hàng trong sổ. Bỏ nó đi thì không
                # có cách nào biết hạn mức đang cắn ai, cắn bao nhiêu lần —
                # tức là không biết con số đang đặt đúng hay quá chặt.
                self._record(
                    feature=feature,
                    route=route,
                    usage=Usage(),
                    cost=Decimal(0),
                    latency_ms=0,
                    status="refused",
                    error=str(exc),
                    user_id=user_id,
                    prompt_version=prompt_version,
                    request_id=request_id,
                )
                raise

        started = perf_counter()
        try:
            provider = self.providers.get(route.provider)
            if provider is None:
                # LLMError chứ không KeyError: một provider chưa dựng adapter
                # (thường là thiếu khoá trong .env) là lỗi cấu hình ở lượt gọi,
                # phải trả 503 có ghi sổ — KeyError thì là 500 không dấu vết.
                raise LLMError(
                    f"Chưa dựng adapter cho nhà cung cấp {route.provider!r} — "
                    f"kiểm khoá API của nó trong .env."
                )
            result = provider.complete(request, route.model)
        except LLMError as exc:
            # `error` là một KẾT QUẢ, không phải một sự vắng mặt. Chỉ ghi lượt
            # thành công thì tỉ lệ hỏng của nhà cung cấp là 0 trong mọi báo cáo.
            self._record(
                feature=feature,
                route=route,
                usage=Usage(),
                cost=Decimal(0),
                latency_ms=int((perf_counter() - started) * 1000),
                status="error",
                error=str(exc)[:2000],
                user_id=user_id,
                prompt_version=prompt_version,
                request_id=request_id,
            )
            raise

        cost = cost_usd(route.provider, result.model, result.usage)
        self._record(
            feature=feature,
            route=route,
            usage=result.usage,
            cost=cost,
            latency_ms=result.latency_ms or int((perf_counter() - started) * 1000),
            status="ok",
            error=None,
            retries=result.retries,
            user_id=user_id,
            prompt_version=prompt_version,
            request_id=request_id,
        )
        if user_id is not None:
            self.budget.charge(self.redis_client, str(user_id), micro_usd(cost))
        return result

    def note_cache_hit(
        self,
        *,
        feature: str,
        provider: str,
        model: str,
        user_id: uuid.UUID | None = None,
        prompt_version: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Ghi một lượt PHỤC VỤ TỪ CACHE — không gọi model, chi phí 0.

        Bỏ hàng này đi thì `cache_hit` mãi mãi rỗng, và câu hỏi "cache có làm chi
        phí giảm theo thời gian không" — đòn bẩy chi phí lớn thứ hai của cả tầng
        — không có số nào trả lời. Nó cũng làm mẫu số của mọi tỉ lệ khác sai:
        tỉ lệ hỏng tính trên số lượt GỌI sẽ khác hẳn tỉ lệ hỏng tính trên số lần
        người dùng thực sự yêu cầu.
        """
        session = self.session_factory()
        try:
            session.add(
                AiInteraction(
                    user_id=user_id,
                    feature=feature,
                    provider=provider,
                    model=model,
                    cost_usd=Decimal(0),
                    latency_ms=0,
                    status="ok",
                    cache_hit=True,
                    prompt_version=prompt_version,
                    request_id=request_id,
                )
            )
            session.commit()
        finally:
            session.close()

    def _record(
        self,
        *,
        feature: str,
        route: object,
        usage: Usage,
        cost: Decimal,
        latency_ms: int,
        status: str,
        error: str | None,
        user_id: uuid.UUID | None,
        prompt_version: str | None,
        request_id: str | None,
        retries: int = 0,
    ) -> None:
        provider = getattr(route, "provider", "?")
        model = getattr(route, "model", "?")
        session = self.session_factory()
        try:
            session.add(
                AiInteraction(
                    user_id=user_id,
                    feature=feature,
                    provider=provider,
                    model=model,
                    prompt_tokens=usage.prompt,
                    completion_tokens=usage.completion,
                    cached_tokens=usage.cached,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    status=status,
                    error=error,
                    prompt_version=prompt_version,
                    retries=retries,
                    request_id=request_id,
                )
            )
            session.commit()
        finally:
            session.close()
