"""Registry `llm_providers.json` — thêm provider mới KHÔNG cần sửa mã.

Kiểm ba luồng thật: giá quay về `cost_usd`, danh sách model của admin, và adapter
được dựng ở cả hai chế độ strict/lenient.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.ai_budget import Budget
from app.models.ai import AiInteraction
from app.models.ai_config import AiFeatureConfig
from app.services.llm.base import LLMRequest, Usage
from app.services.llm.gateway import Gateway
from app.services.llm.pricing import UnknownModel, cost_usd, known_models
from app.services.llm.providers import build_providers
from app.services.llm.registry import load_registry
from app.services.llm.router import Tier

ROUTES = {Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")}

VALID = {
    "providers": {
        "mistral": {
            "base_url": "https://api.mistral.ai/v1",
            "api_key_env": "MISTRAL_API_KEY",
            "models": {"mistral-large-latest": {"rate_in": 2.0, "rate_out": 6.0}},
        }
    }
}


def write_registry(tmp_path, payload, name="llm_providers.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def registry_file(tmp_path, monkeypatch):
    from app.core.config import settings

    def use(payload, **kwargs):
        path = write_registry(tmp_path, payload, **kwargs)
        monkeypatch.setattr(settings, "llm_providers_file", path)
        return path

    return use


def test_FILE_MAU_DINH_KEM_phai_load_duoc() -> None:
    """File ship theo repo là ví dụ sống — hỏng parse là hỏng tài liệu."""
    registry = load_registry(strict=True)
    assert "mistral" in registry
    assert "mistral-large-latest" in registry["mistral"].models
    # Z.AI/GLM và B.AI — provider thêm vào bằng FILE, không sửa mã: đây là phép
    # kiểm rằng quy trình "thêm provider mới" thật sự không chạm tệp .py nào.
    assert "zai" in registry
    assert ("zai", "glm-5.3-flash") in known_models()
    assert "bai" in registry
    assert ("bai", "glm-5.3-flash") in known_models()


def test_GIA_CUA_MODEL_CUSTOM_di_vao_cost_usd(registry_file) -> None:
    registry_file(VALID)
    usage = Usage(prompt=1_000_000, completion=1_000_000)
    assert cost_usd("mistral", "mistral-large-latest", usage) == Decimal("8.000000")


def test_MODEL_LA_VAN_BI_TU_CHOI_khi_file_khong_co(registry_file) -> None:
    """File custom KHÔNG phải lối né bảng giá — thiếu giá vẫn từ chối (N4)."""
    registry_file(VALID)
    with pytest.raises(UnknownModel, match="không-ở-đâu-cả"):
        cost_usd("mistral", "không-ở-đâu-cả", Usage(prompt=1, completion=1))


def test_known_models_BAO_GOM_CAC_MODEL_CUSTOM(registry_file) -> None:
    registry_file(VALID)
    assert ("mistral", "mistral-large-latest") in known_models()


def test_BUILD_PROVIDER_custom_can_khoa_trong_ENV(registry_file, monkeypatch) -> None:
    registry_file(VALID)
    monkeypatch.setenv("MISTRAL_API_KEY", "khoá-giả")
    built = build_providers({"mistral", "ollama"})
    assert set(built) == {"mistral", "ollama"}
    assert built["mistral"].name == "mistral"


def test_THIEU_KHOA_strict_CHET_VOI_TEN_BIEN(registry_file, monkeypatch) -> None:
    registry_file(VALID)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        build_providers({"mistral"})
    assert build_providers({"mistral"}, strict=False) == {}


def test_GHI_DE_BUILTIN_BI_TU_CHOI_o_HAI_CHE_DO(registry_file, monkeypatch) -> None:
    registry_file({"providers": {"google": {"base_url": "https://x/v1"}}})
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    with pytest.raises(ValueError, match="builtin"):
        load_registry(strict=True)
    # Lenient: bỏ mục ghi đè, không chết cả file.
    assert load_registry(strict=False) == {}


def test_FILE_SAI_lenient_la_EMPTY_strict_LA_LOI(registry_file, tmp_path) -> None:
    # Ghi nội dung hỏng vào file TMP, không bao giờ vào file ship theo repo —
    # bản đầu của test này ghi thẳng `settings.llm_providers_file` và phá đúng
    # file mẫu đang được commit. Đó là lý do helper luôn trỏ sang tmp_path.
    path = registry_file({})
    path.write_text("{ không phải json", encoding="utf-8")
    with pytest.raises(ValueError, match="llm_providers.json"):
        load_registry(strict=True)
    assert load_registry(strict=False) == {}
    assert build_providers({"mistral"}, strict=False) == {}


def test_GET_GATEWAY_builds_CUSTOM_provider_tu_hang_feature(
    db_session, registry_file, monkeypatch
) -> None:
    from app.api.deps import get_gateway

    registry_file(VALID)
    monkeypatch.setenv("MISTRAL_API_KEY", "khoá-giả")
    db_session.add(
        AiFeatureConfig(feature="coach_explain", provider="mistral", model="mistral-large-latest")
    )
    db_session.commit()

    gw = get_gateway(db_session)
    assert "mistral" in gw.providers


def test_SO_CAI_van_ghi_DUNG_GIA_custom(db_session, fake_redis, registry_file, monkeypatch) -> None:
    """Lượt gọi tới model custom phải ghi sổ với đúng giá trong file.

    FakeProvider cắm dưới khoá "mistral" — providers chỉ là một bản đồ tên →
    adapter, không kiểm adapter đến từ đâu, nên không cần mạng nào ở đây.
    """
    from app.services.llm.fake import FakeProvider

    registry_file(VALID)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    gw = Gateway(
        providers={"mistral": FakeProvider(reply="trả lời giả")},
        routes={Tier.STRONG: ("mistral", "mistral-large-latest")},
        budget=Budget(limit_micro=100_000_000),
        redis_client=fake_redis,  # type: ignore[arg-type]
        session_factory=sessionmaker(bind=db_session.get_bind()),
    )
    gw.run(LLMRequest(system="s", user="u"), feature="coach_explain", tier=Tier.STRONG)

    row = db_session.query(AiInteraction).one()
    assert row.status == "ok"
    assert row.provider == "mistral" and row.model == "mistral-large-latest"
    # FakeProvider mặc định 100 token vào / 20 ra: (100×2 + 20×6)/1e6.
    assert float(row.cost_usd) == pytest.approx(0.00032)
