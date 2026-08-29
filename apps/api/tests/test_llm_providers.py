"""Builder provider dùng chung, và Gateway với nhà cung cấp thiếu adapter."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.ai_budget import Budget
from app.models.ai import AiInteraction
from app.models.ai_config import AiFeatureConfig
from app.services.llm.base import LLMError, LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.providers import build_providers
from app.services.llm.router import Tier

ROUTES = {Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")}


def test_GOOGLE_API_KEY_co_thi_dung_duoc_adapter(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_api_key", "khoá-giả")
    providers = build_providers({"google", "ollama"})
    assert set(providers) == {"google", "ollama"}
    assert providers["google"].name == "google"


def test_THIEU_KHOA_thi_STRONG_CHET_ngay(monkeypatch) -> None:
    """CLI pipeline: lượt chạy dài hàng chục phút — im lặng lúc dựng là đốt tiền."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_api_key", None)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        build_providers({"google"})


def test_DUONG_PHUC_VU_BOP_QUA_provider_thieu_khoa(monkeypatch) -> None:
    """Tính năng A trỏ sai không được phép kéo sập tính năng B."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_api_key", None)
    providers = build_providers({"google", "ollama"}, strict=False)
    assert set(providers) == {"ollama"}


def test_TEN_LA_thi_bao_ro_CACH_SUA(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_api_key", "k")
    with pytest.raises(RuntimeError, match="ENDPOINTS"):
        build_providers({"ratlatu"})
    assert build_providers({"ratlatu"}, strict=False) == {}


def test_GATEWAY_provider_thieu_la_LLMError_CHU_KHONG_KeyError(db_session, fake_redis) -> None:
    """KeyError là 500 không dấu vết; LLMError là 503 có một hàng trong sổ."""
    gw = Gateway(
        providers={},  # cố ý trống
        routes=ROUTES,
        budget=Budget(limit_micro=1_000_000),
        redis_client=fake_redis,  # type: ignore[arg-type]
        session_factory=sessionmaker(bind=db_session.get_bind()),
    )
    with pytest.raises(LLMError, match="adapter"):
        gw.run(LLMRequest(system="s", user="u"), feature="coach_explain", tier=Tier.CHEAP)

    rows = db_session.query(AiInteraction).all()
    assert len(rows) == 1
    assert rows[0].status == "error"


def test_GET_GATEWAY_builds_provider_ma_tinh_nang_dang_tro_vao(
    db_session: Session, monkeypatch
) -> None:
    """Đây là chỗ hụt thật: đường phục vụ từng chỉ biết ollama + openrouter."""
    from app.api.deps import get_gateway
    from app.core.config import settings

    db_session.add(
        AiFeatureConfig(
            feature="assistant_chat", provider="google", model="gemini-2.5-flash", enabled=True
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "google_api_key", "khoá-giả")

    gw = get_gateway(db_session)
    assert "google" in gw.providers
