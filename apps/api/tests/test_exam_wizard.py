"""Wizard sinh đề — phần tách khỏi questionary (không cần TTY để kiểm)."""

from __future__ import annotations

from app.content.exam_wizard import State, _blueprint_summary, _known_slugs


def test_known_slugs_liet_ke_theo_blueprint(tmp_path, monkeypatch) -> None:
    import app.content.exam_wizard as w
    from app.content.exam.blueprint import Blueprint, PartPlan
    from app.content.exam.blueprint import save as save_blueprint

    monkeypatch.setattr(w, "DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(w, "blueprint_path", lambda slug: tmp_path / slug / "blueprint.json")
    plan = Blueprint(slug="tp-form-07", title="Đề 07", seed=1, parts=[PartPlan(part=5)])
    save_blueprint(plan, tmp_path / "tp-form-07" / "blueprint.json")
    assert _known_slugs() == ["tp-form-07"]


def test_blueprint_summary_tao_duoc_khi_chua_co(tmp_path, monkeypatch) -> None:
    import app.content.exam_wizard as w

    monkeypatch.setattr(w, "DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(w, "blueprint_path", lambda slug: tmp_path / slug / "blueprint.json")
    state = State(slug="khong-ton-tai")
    assert _blueprint_summary(state) == "chưa có blueprint"
