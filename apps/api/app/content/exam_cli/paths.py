"""Thư mục làm việc của một đề, và gateway cho các lệnh sinh nội dung."""

from __future__ import annotations

from pathlib import Path

from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier

DEFAULT_ROOT = Path("content/generated")


def workdir_for(slug: str) -> Path:
    return DEFAULT_ROOT / slug


def blueprint_path(slug: str) -> Path:
    return workdir_for(slug) / "blueprint.json"


def _gateway(model: str | None = None) -> Gateway:
    """Dựng gateway y hệt `enrich_skills`, kể cả `resolve_feature`.

    Không nối `resolve_feature` thì màn cấu hình ở `/admin/ai/providers` lưu
    được, hiện ra được, và không ảnh hưởng gì tới thứ thật sự chạy — kiểu hỏng
    tệ nhất, vì mọi thứ trông như đang hoạt động.

    `model` (dạng `provider/model`) ghi đè cả hai tầng bằng đúng một model —
    đường đi mà wizard `interact` và `--model` dùng. `resolve_feature` vẫn chạy
    trước: một hàng `ai_feature_config` khớp feature sẽ thắng override này.
    """
    from app.content.enrich_skills import _providers_for, _split
    from app.core.ai_budget import Budget
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.redis_client import get_redis
    from app.services.ai_features import resolver_for

    routes = {
        Tier.CHEAP: _split(settings.llm_tier_cheap),
        Tier.STRONG: _split(settings.llm_tier_strong),
    }
    if model:
        routes = {tier: _split(model) for tier in routes}
    providers = _providers_for({provider for provider, _ in routes.values()})
    session = SessionLocal()
    return Gateway(
        providers=providers,
        routes=routes,
        budget=Budget(limit_micro=settings.ai_daily_budget_micro_usd),
        redis_client=get_redis(),
        session_factory=SessionLocal,
        resolve_feature=resolver_for(session),
    )
