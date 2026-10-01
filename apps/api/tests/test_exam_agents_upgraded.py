"""Khóa refactor graph_upgraded -> package `upgraded/`: API công khai và 2
hồi quy đã từng vỡ (merge TypeError, route None, revision kẹt 0).

Không gọi model thật: fake gateway + workdir tạm, như test_exam_agents_graph.
"""

from __future__ import annotations

from app.content.exam.check import SlotReport


def test_merge_reports_derives_blocked_without_kwarg():
    from app.content.exam_agents.upgraded.findings import _merge_reports

    ok = SlotReport(slot_id="p5-01", number=1, problems=[], flags=[])
    bad = SlotReport(slot_id="p5-01", number=1, problems=["sai nhãn"], flags=[])
    assert _merge_reports([ok]) is not None
    assert _merge_reports([ok]).blocked is False
    merged = _merge_reports([ok, bad])
    assert merged.blocked is True
    assert merged.problems == ["sai nhãn"]
    assert _merge_reports([]) is None


def test_route_after_evaluator_tolerates_missing_plan():
    from app.content.exam_agents.upgraded.verdict import _route_after_evaluator

    assert _route_after_evaluator({"revision_plan": None}) == "write"
    assert _route_after_evaluator({}) == "write"
    assert (
        _route_after_evaluator({"revision_plan": {"should_regenerate": False}})
        == "escalate"
    )


def test_shim_reexports_public_surface():
    import app.content.exam_agents.graph_upgraded as shim
    from app.content.exam_agents.upgraded.runner import run_pending as direct

    assert shim.run_pending is direct
    for name in ("build", "main", "parts_of", "run_pending", "RetryPolicy", "SlotState"):
        assert name in shim.__all__
        assert getattr(shim, name) is not None
