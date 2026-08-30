"""Kiểm đồ thị write→check→critic KHÔNG gọi model thật.

Cùng quy tắc với demo cũ: cái được kiểm là cấu trúc vòng lặp (bắt lỗi, quay lại,
trần vòng, escalate), không phải chất lượng model. Lượt gọi model được thay bằng
hàm fake qua seam `gateway` — `write_slot` và `critic` đều đi qua `gateway.run`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.content.exam_agents.graph import MAX_REVISIONS, build


@dataclass
class FakeResult:
    text: str


@dataclass
class FakeGateway:
    """Model giả: lần viết đầu trả khối hỏng, sau khi nhận hint thì trả khối tốt.

    Đo được hai thứ: (1) `fix_hint` của critic có đi TỚI lượt viết sau không,
    (2) trần vòng lặp dừng đúng chỗ thay vì quay mãi.
    """

    calls: list[str] = field(default_factory=list)
    good_block: str = (
        "[QUESTION]\nThe manager ------- the report before noon.\n"
        "(A) reviews\n(B) prevents\n(C) accompanies\n(D) suggests\n"
        "Answer: A\nSource: original\n"
    )

    def run(self, request: object, feature: str = "", tier: object = None) -> FakeResult:
        self.calls.append(feature)
        if feature == "exam_write":
            # Lượt viết THỨ TRỰC TIẾP tuỳ theo đã nhận hint chưa — mô phỏng
            # "người viết sửa theo lời phê".
            return FakeResult(self.good_block)
        if feature == "exam_verify":
            return FakeResult("Thêm chi tiết vào câu hỏi thứ hai.")
        raise AssertionError(f"feature lạ: {feature}")


class _Slot:
    id = "p5-01"
    number = 1
    question_type = "PART_5_VOCABULARY"
    grammar = ""
    context = "kiểm"
    voice = ""
    people = ""
    voices: list[str] = []
    graphic = ""
    grammars: list[str] = []
    passages: list[str] = []
    structure = ""
    question_types: list[str] = []


class _Part:
    part = 5
    slots: list = [_Slot()]


class _Blueprint:
    slug = "graph-test"
    seed = 1
    parts: list = [_Part()]


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "graph-test"
    d.mkdir()
    return d


def test_pass_first_try(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Khối tốt qua kiểm ngay: outcome accepted, đúng một lượt viết."""

    from app.content.exam import blueprint as bp

    monkeypatch.setattr(bp, "load", lambda path: _Blueprint())
    gw = FakeGateway()
    # `write_slot` thật gọi gateway.run(feature="exam_write") — khối tốt thì
    # check cũng phải pass (Part 5 một câu, đủ 4 đáp án, đúng source).
    graph = build(gw, tier=None, blueprint=_Blueprint(), workdir=workdir)
    final = graph.invoke(
        {"slot_id": "p5-01", "revision": 0, "outcome": "pending"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert final["outcome"] == "accepted"
    assert gw.calls.count("exam_write") == 1
    assert "exam_verify" not in gw.calls


def test_escalates_after_max_revisions(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Khối luôn hỏng: đồ thị dừng ở trần, giao người — KHÔNG quay mãi."""

    from app.content.exam import blueprint as bp

    monkeypatch.setattr(bp, "load", lambda path: _Blueprint())
    gw = FakeGateway()
    gw.good_block = "không phải khối"  # MissingBlock mỗi lượt viết
    graph = build(gw, tier=None, blueprint=_Blueprint(), workdir=workdir)
    final = graph.invoke(
        {"slot_id": "p5-01", "revision": 0, "outcome": "pending"},
        config={"configurable": {"thread_id": "t2"}},
    )
    assert final["outcome"] == "escalated"
    assert gw.calls.count("exam_write") == MAX_REVISIONS


def test_hint_reaches_next_write(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lượt viết hỏng → critic phê → lượt viết sau nhận `fix_hint`.

    Đây là thứ pipeline hiện tại KHÔNG có và đồ thị này tồn tại để có: ô bị loại
    phải được sửa theo lý do, không phải sinh lại mù. Model giả sẽ chỉ viết khối
    tốt khi `fix_hint` đã tới user prompt của nó — tức là đồ thị phải thực sự
    đưa lời phê vòng lại, không chỉ tăng biến đếm.
    """

    from app.content.exam import blueprint as bp

    monkeypatch.setattr(bp, "load", lambda path: _Blueprint())

    seen_prompts: list[str] = []

    class HintGateway(FakeGateway):
        def run(self, request: object, feature: str = "", tier: object = None) -> FakeResult:
            prompt = getattr(request, "user", "")
            seen_prompts.append(prompt)
            if feature == "exam_write":
                if "LƯU Ý SỬA" in prompt:  # hint của critic đã tới lượt viết
                    return FakeResult(self.good_block)
                return FakeResult("không phải khối")  # MissingBlock
            return FakeResult("Bỏ phần giải thích dài, viết khối gọn hơn.")

    gw = HintGateway()
    graph = build(gw, tier=None, blueprint=_Blueprint(), workdir=workdir)
    final = graph.invoke(
        {"slot_id": "p5-01", "revision": 0, "outcome": "pending"},
        config={"configurable": {"thread_id": "t3"}},
    )
    assert final["outcome"] == "accepted"
    # Lượt viết thứ hai phải mang hint từ critic
    writes = [p for p in seen_prompts if "Part 5" in p or "Part" in p]
    assert len(writes) == 2
    assert "LƯU Ý SỬA" in writes[1]
