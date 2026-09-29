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
from app.services.llm.gateway import Tally


@dataclass
class FakeResult:
    text: str


@dataclass
class FakeGateway:
    """Model giả: lần viết đầu trả khối hỏng, sau khi nhận hint thì trả khối tốt.

    Đo được hai thứ: (1) `fix_hint` của critic có đi TỚI lượt viết sau không,
    (2) trần vòng lặp dừng đúng chỗ thay vì quay mãi.

    Mang cả `tally` vì `run_pending` in chi phí sau mỗi part — một fake thiếu bề
    mặt của thứ nó thay thế làm test đỏ ở chỗ không liên quan gì tới nó.
    """

    calls: list[str] = field(default_factory=list)
    tally: Tally = field(default_factory=Tally)
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
    # Một dòng cho MỖI vòng, kèm lý do. Không có nó thì người đọc phải chạy
    # `check` lần nữa để biết điều đồ thị vừa biết — và không phân biệt được
    # "ba vòng hỏng cùng kiểu" (lỗi ở brief) với "ba kiểu khác nhau".
    assert len(final["log"]) == MAX_REVISIONS
    assert all("vòng " in line for line in final["log"])


def test_escalation_prints_why(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Giao người thì lý do phải HIỆN RA, không chỉ nằm trong state.

    Bản đầu tích luỹ `log` qua một reducer rồi không ai đọc: `run_pending` chỉ
    lấy `outcome`. Trạng thái đúng mà không in ra thì người vận hành vẫn phải
    chạy `check` lần nữa, nên test này kiểm ĐẦU RA chứ không kiểm state.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam_agents.graph import run_pending

    monkeypatch.setattr(bp, "load", lambda path: _Blueprint())
    gw = FakeGateway()
    gw.good_block = "không phải khối"
    run_pending(gw, tier=None, blueprint=_Blueprint(), workdir=workdir)
    printed = capsys.readouterr().out
    assert "escalated" in printed
    assert "vòng 1:" in printed and f"vòng {MAX_REVISIONS}:" in printed


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


def test_part1_photo_lands_in_own_file(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Part 1 trả về [PHOTO] + [QUESTION]: mô tả ảnh phải tách thành
    `photos/<slot>.txt`, tệp dán chỉ còn khối [QUESTION].

    `cmd_write` làm việc đó; graph phải làm Y HỆT — không tách thì mô tả ảnh
    nằm nguyên trong tệp dán, parser từ chối dòng lạ sau đáp án, và `photo`
    command không có mô tả để vẽ."""

    from app.content.exam import blueprint as bp

    monkeypatch.setattr(bp, "load", lambda path: _Blueprint())

    # Thay slot thành Part 1
    class _SlotP1(_Slot):
        id = "p1-01"
        question_type = "PART_1_PERSON_DESCRIPTION"
        voice = "au_female_1"
        people = "one"

    class _PartP1:
        part = 1
        slots = [_SlotP1()]

    class _BlueprintP1(_Blueprint):
        parts = [_PartP1()]

    class PhotoGateway(FakeGateway):
        def run(self, request: object, feature: str = "", tier: object = None) -> FakeResult:
            return FakeResult(
                "[PHOTO]\nA photograph of a single woman at a desk.\n\n"
                "[QUESTION]\nvoice: au_female_1\n"
                "(A) The woman is talking on the phone.\n"
                "(B) The woman is asleep.\n"
                "(C) Two women are dancing.\n"
                "(D) The desk is on fire.\n"
                "Answer: A\nSource: original\n"
            )

    graph = build(PhotoGateway(), tier=None, blueprint=_BlueprintP1(), workdir=workdir)
    final = graph.invoke(
        {"slot_id": "p1-01", "revision": 0, "outcome": "pending"},
        config={"configurable": {"thread_id": "t4"}},
    )
    assert final["outcome"] == "accepted"
    paste = (workdir / "paste" / "p1-01.txt").read_text()
    assert "[PHOTO]" not in paste
    assert paste.startswith("[QUESTION]")
    photo = (workdir / "photos" / "p1-01.txt").read_text()
    assert "single woman" in photo


def test_a_failed_call_does_not_kill_the_whole_run(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Một ô hỏng ở LƯỢT GỌI không được dừng những ô còn lại.

    Gặp thật trên `tp-form-08`: `p3-11` là ô có hình đầu tiên, phần suy luận
    vượt trần đầu ra, và `LLMError` xuyên qua LangGraph giết luôn 62 ô còn lại.
    Mười ô vừa xong chỉ sống sót nhờ đồ thị ghi đĩa sau TỪNG ô. `check.py` đã có
    đúng luật này kèm lý do, nhưng `write` chưa được áp.

    Ô hỏng đi thẳng tới `escalate`, không quay lại critic: `with_backoff` đã thử
    bảy lần, nên không có bản nháp nào để chấm và ba vòng viết lại sẽ hỏng y hệt.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam_agents.graph import run_pending
    from app.services.llm.base import LLMError

    def _slot(slot_id: str) -> _Slot:
        slot = _Slot()
        slot.id = slot_id  # type: ignore[misc]  # che thuộc tính lớp
        return slot

    class _TwoSlotPart:
        part = 5
        slots = [_slot("p5-01"), _slot("p5-02")]

    class _TwoSlotBlueprint:
        slug = "graph-test"
        seed = 1
        parts = [_TwoSlotPart()]

    class FailsFirstWrite(FakeGateway):
        def run(self, request: object, feature: str = "", tier: object = None) -> FakeResult:
            if feature == "exam_write" and "exam_write" not in self.calls:
                self.calls.append(feature)
                raise LLMError("bai: hết hạn mức đầu ra khi đang suy luận (24940 ký tự)")
            return super().run(request, feature, tier)

    monkeypatch.setattr(bp, "load", lambda path: _TwoSlotBlueprint())
    gw = FailsFirstWrite()
    results = run_pending(gw, tier=None, blueprint=_TwoSlotBlueprint(), workdir=workdir)

    assert results == [("p5-01", "escalated"), ("p5-02", "accepted")]
    # Đúng hai lượt viết: ô hỏng KHÔNG được viết lại ba lần, và critic không chạy.
    assert gw.calls.count("exam_write") == 2
    assert "exam_verify" not in gw.calls
    # Lý do phải HIỆN RA, không chỉ nằm trong state — cùng lập luận với
    # `test_escalation_prints_why`.
    assert "hết hạn mức đầu ra" in capsys.readouterr().out


def test_second_question_problems_are_not_hidden_by_a_clean_first(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Node kiểm phải gộp CẢ BA báo cáo của ô, không chỉ lấy báo cáo đầu.

    Gặp thật trên `tp-form-16`: `p3-01` được nhận trong khi câu 33 đỏ (2/3
    nhiễu lạc đề) — node check lấy `next()` báo cáo đầu (câu 32 sạch) rồi
    accept, lỗi riêng của câu 2/3 không bao giờ tới được critic. Cụm ba câu
    nhân lỗi ra ba báo cáo để NGƯỜI đọc từng câu, còn máy phải gộp lại.
    """

    from app.content.exam import blueprint as bp

    class _SlotP3(_Slot):
        id = "p3-01"
        question_type = ""
        topic = "PART_3_COMPANY_EVENT_OR_PROJECT"
        voices = ["us_female_1", "au_male_1"]
        question_types = [
            "PART_3_TOPIC_OR_PURPOSE",
            "PART_3_CONVERSATION_DETAIL",
            "PART_3_FUTURE_ACTION",
        ]
        hard = 0
        implication_kind = 0

    class _PartP3:
        part = 3
        slots = [_SlotP3()]

    class _BlueprintP3(_Blueprint):
        parts = [_PartP3()]

    class SecondQuestionBad(FakeGateway):
        def run(self, request: object, feature: str = "", tier: object = None) -> FakeResult:
            if feature == "exam_write":
                return FakeResult(
                    "[SCRIPT]\n"
                    "voice: us_female_1\n"
                    "Hi Tom, the printer on the third floor is jammed again. "
                    "Could you take a look after lunch?\n"
                    "voice: au_male_1\n"
                    "Sure. I will bring the toolbox and clear the paper tray. "
                    "It should take ten minutes.\n"
                    "voice: us_female_1\n"
                    "Thanks. The client report must go out before three o'clock today.\n"
                    "\n"
                    "[QUESTION]\n"
                    "Why is the woman talking to Tom?\n"
                    "(A) To report a jammed printer\n"
                    "(B) To cancel a lunch meeting\n"
                    "(C) To order a new toolbox\n"
                    "(D) To delay the client report\n"
                    "Answer: A\nSource: original\n"
                    "[QUESTION]\n"
                    "What will Tom do after lunch?\n"
                    "(A) Clear the paper tray\n"
                    "(B) Water the office plants\n"
                    "(C) Feed the neighbours cat\n"
                    "(D) Book flight tickets\n"
                    "Answer: A\nSource: original\n"
                    "[QUESTION]\n"
                    "When must the report go out?\n"
                    "(A) Before three o'clock\n"
                    "(B) After the toolbox arrives\n"
                    "(C) During the lunch break\n"
                    "(D) Before the jammed printer\n"
                    "Answer: A\nSource: original\n"
                )
            return FakeResult("Nhại lời thoại trong đáp án nhiễu.")

    monkeypatch.setattr(bp, "load", lambda path: _BlueprintP3())
    graph = build(SecondQuestionBad(), tier=None, blueprint=_BlueprintP3(), workdir=workdir)
    final = graph.invoke(
        {"slot_id": "p3-01", "revision": 0, "outcome": "pending"},
        config={"configurable": {"thread_id": "t5"}},
    )
    assert final["outcome"] == "escalated"
    assert any("nhiễu" in line for line in final["log"])
