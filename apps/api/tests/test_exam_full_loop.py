"""Vòng ngoài của `full`: chạy lại phần hỏng, và dừng khi không tiến thêm."""

from __future__ import annotations

from pathlib import Path

from app.content.exam_agents.full import MAX_PASSES, _after_slotloop


def test_loop_stops_when_done():
    assert _after_slotloop({"remaining": 0, "retry": [], "passes": 1}) == "balance"


def test_loop_continues_while_slots_remain():
    state = {"remaining": 5, "retry": [], "passes": 1, "stalled": False}
    assert _after_slotloop(state) == "slotloop"


def test_a_slot_that_escalated_brings_the_loop_back():
    """Ô `escalated` giữ tệp dán nên `pending` không trả nó về — `retry` mới là
    thứ đưa nó vào lượt sau. Không có nhánh này thì "tự chạy lại phần hỏng"
    không xảy ra, mà mọi thứ khác vẫn trông bình thường."""
    state = {"remaining": 0, "retry": ["p5-17"], "passes": 1, "stalled": False}
    assert _after_slotloop(state) == "slotloop"


def test_no_progress_stops_the_loop(capsys):
    """Chốt chặn quan trọng nhất: một ô hỏng vĩnh viễn không được biến lượt chạy
    thành vô tận. `stalled` bật khi không ô nào ĐẠT và không tệp nào mới."""
    state = {"remaining": 3, "retry": ["p5-17"], "passes": 1, "stalled": True}
    assert _after_slotloop(state) == "balance"
    assert "không tiến thêm" in capsys.readouterr().out


def test_pass_ceiling_stops_the_loop(capsys):
    assert (
        _after_slotloop(
            {"remaining": 3, "retry": ["p5-17"], "passes": MAX_PASSES, "stalled": False}
        )
        == "balance"
    )
    assert f"{MAX_PASSES} lượt" in capsys.readouterr().out


def test_artwork_waits_until_the_paper_is_complete():
    """Vẽ trên đề còn thiếu ô là vẽ hai lần."""
    from app.content.exam_agents.full import _artwork_node

    node = _artwork_node(Path("."))
    assert "bỏ qua" in (node({"slug": "x", "remaining": 4}) or {})["artwork"]
