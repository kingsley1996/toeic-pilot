"""Đồ thị viết → kiểm → phê cho MỘT ô của pipeline sinh đề (LangGraph).

Kết nối ba thứ **đã có sẵn** của pipeline, không viết lại cái nào:

1. **Viết** — `writer.write_slot` (prompt per-part, `temperature=0.8`,
   `with_backoff`, kiểm khối hoàn chỉnh). Lỗi của nó là dữ liệu, không phải
   ngoại lệ: `MissingBlock` thành `blocked`.
2. **Kiểm** — `checker.check_blueprint` với `gateway=None` (chỉ các tầng miễn
   phí: parser thật, luật hình, trùng lặp). Cùng hàm mà lệnh `check` chạy.
3. **Phê** — một lượt gọi `exam_verify` (model ChẤM chứ không viết), trả về
   gợi ý sửa cho lượt viết sau.

Vòng lặp có trần: `MAX_REVISIONS` vòng là dừng và giao người — đúng tinh thần
"escalate thay vì quay mãi".

Lý do đồ thị này tồn tại: pipeline hiện tại `write → check → prune` là một vòng
thủ công — ô bị loại được sinh lại từ đầu mà không biết vì sao bị loại. Đồ thị
biến vòng đó thành có nhớ: `fix_hint` của lời phê quay lại lượt viết sau.

Chạy:

    uv run python -m app.content.exam_agents.graph --slug tp-form-08 \
        [--model provider/model] [--limit N] [--revisions 3]
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.content.exam.writer import MissingBlock, save_slot, write_slot
from app.services.llm.base import LLMRequest
from app.services.llm.retry import with_backoff

# Trần vòng lặp. Ba vòng là chỗ dừng đúng: một ô hỏng cùng kiểu ba lần thì lỗi
# nằm ở prompt/brief, không nằm ở lượt viết — quay tiếp chỉ đốt quota.
MAX_REVISIONS = 3
RETRY_TRIES = 7
RETRY_DELAY = 6.0


class SlotState(TypedDict, total=False):
    """Trạng thái một ô. Dùng TypedDict chứ không dataclass: LangGraph merge
    update theo từng khoá, và `log` cần reducer để tích luỹ qua các vòng."""

    slot_id: str
    draft: str
    blocked: bool
    problems: list[str]
    flags: list[str]
    fix_hint: str | None
    revision: int
    outcome: str
    log: Annotated[list[str], operator.add]


class _Parts:
    """Tra slot + part theo id, một lần cho cả lượt chạy."""

    def __init__(self, blueprint: Any) -> None:
        self.by_id: dict[str, tuple[Any, int]] = {}
        for part in blueprint.parts:
            for slot in part.slots:
                self.by_id[slot.id] = (slot, part.part)

    def slot(self, slot_id: str) -> Any:
        return self.by_id[slot_id][0]

    def part(self, slot_id: str) -> int:
        return self.by_id[slot_id][1]


def _write_node(gateway: Any, tier: Any, workdir: Any, parts: _Parts) -> Any:
    """Viết lại ô. `write_slot` ném `MissingBlock` khi đầu ra bị cắt — biến thành
    trạng thái bị chặn thay vì để ngoại lệ làm đồ thị chết. `fix_hint` của critic
    đi kèm: đây là toàn bộ điểm của vòng lặp — sửa theo lý do, không sinh lại mù."""

    def write(state: dict[str, Any]) -> dict[str, Any]:
        slot = parts.slot(state["slot_id"])
        part = parts.part(state["slot_id"])
        update: dict[str, Any] = {"revision": state["revision"] + 1}
        hint = state.get("fix_hint")
        try:
            block = write_slot(gateway, slot, tier, part, fix_hint=hint)
        except MissingBlock as cut:
            update |= {
                "draft": "",
                "blocked": True,
                "problems": [str(cut)],
                "fix_hint": "Bị cắt giữa phần suy luận — viết ngắn hơn, đi thẳng vào khối.",
            }
            return update
        # Ghi xuống đĩa NGAY: hàng đợi là một truy vấn trên thư mục, ô đã ghi là
        # ô không phải trả tiền lại. `check` sau đó đọc từ đĩa — cùng hiện vật.
        save_slot(workdir, slot, block)
        update |= {"draft": block, "blocked": False, "problems": [], "flags": []}
        # Hint đã dùng xong: không xoá thì lượt sau đọc lại hint cũ của lỗi cũ.
        update["fix_hint"] = None
        return update

    return write


def _check_node(blueprint: Any, workdir: Any, parts: _Parts) -> Any:
    """Kiểm máy — KHÔNG gọi model. Nguồn DUY NHẤT được điền `blocked`.

    `check_blueprint` chạy trên toàn bộ part của ô (nó đọc tệp dán từ đĩa), với
    `gateway=None`: bỏ những tầng cần lượt gọi, giữ parser thật + luật hình +
    trùng lặp. Cùng hàm mà lệnh `check` chạy — bản kiểm riêng sẽ trôi khỏi
    parser thật. Chỉ lấy report của ô đang chạy.
    """

    def check(state: dict[str, Any]) -> dict[str, Any]:
        if state["blocked"]:  # lượt viết đã hỏng trước khi có khối — không có gì để kiểm
            return {}
        from app.content.exam.check import check_blueprint

        reports = check_blueprint(
            blueprint, workdir, gateway=None, only=parts.part(state["slot_id"])
        )
        report = next((r for r in reports if r.slot_id == state["slot_id"]), None)
        if report is None:
            return {"blocked": True, "problems": ["check không đọc được ô này"]}
        return {
            "blocked": report.blocked,
            "problems": list(report.problems),
            "flags": list(report.flags),
        }

    return check


def _critic_node(gateway: Any, tier: Any) -> Any:
    """Phê — MỘT lượt gọi. Model CHẤM chứ không viết lại: trả gợi ý sửa.

    feature=`exam_verify` vì nó là cùng loại việc với đối chiếu đáp án: đọc một
    ô đã có, trả nhận định. Muốn tách tier riêng thì thêm feature mới vào bảng
    giá, không phải sửa đồ thị."""

    def critic(state: dict[str, Any]) -> dict[str, Any]:
        result = with_backoff(
            lambda: gateway.run(
                LLMRequest(
                    system=(
                        "Bạn là người chấm đề TOEIC. Ô sau đây bị từ chối vì những "
                        "lý do liệt kê. Viết MỘT đoạn ngắn (tối đa 40 từ) chỉ cho "
                        "người viết phải sửa gì ở LƯỢT SAU. Không viết lại đề."
                    ),
                    user=(
                        "Lý do bị chặn:\n"
                        + "\n".join(f"- {p}" for p in state["problems"])
                        + f"\n\n---\n{state['draft'][:4000]}"
                    ),
                    max_tokens=200,
                    temperature=0.0,
                ),
                feature="exam_verify",
                tier=tier,
            ),
            tries=RETRY_TRIES,
            delay=RETRY_DELAY,
        )
        return {"fix_hint": result.text.strip()[:400] or None}

    return critic


def _after_check(state: dict[str, Any]) -> str:
    if not state["blocked"]:
        return "accept"
    if state["revision"] >= MAX_REVISIONS:
        return "escalate"
    return "critic"


def _after_critic(state: dict[str, Any]) -> str:
    # critic không đổi `blocked`; lượt viết sau sẽ sửa. Trần vòng đã được
    # `after_check` giữ — tới đây thì luôn quay lại viết.
    return "write"


def _accept(state: dict[str, Any]) -> dict[str, Any]:
    return {"outcome": "accepted"}


def _escalate(state: dict[str, Any]) -> dict[str, Any]:
    return {"outcome": "escalated"}


def build(gateway: Any, tier: Any, blueprint: Any, workdir: Any) -> Any:
    parts = _Parts(blueprint)

    builder = StateGraph(SlotState)
    # add_node của LangGraph 1.x khó chịu với node trả update-một-phần (dict)
    # thay vì state đầy đủ — pattern chuẩn của nó, nhưng generic chưa nới lỏng.
    # Cast một lần tại đây thay vì rải type: ignore khắp các node.
    def _node(fn: Any) -> Any:
        return fn

    builder.add_node("write", _node(_write_node(gateway, tier, workdir, parts)))
    builder.add_node("check", _node(_check_node(blueprint, workdir, parts)))
    builder.add_node("critic", _node(_critic_node(gateway, tier)))
    builder.add_node("accept", _node(_accept))
    builder.add_node("escalate", _node(_escalate))

    builder.add_edge(START, "write")
    builder.add_edge("write", "check")
    builder.add_conditional_edges("check", _after_check)
    builder.add_conditional_edges("critic", _after_critic)
    builder.add_edge("accept", END)
    builder.add_edge("escalate", END)
    return builder.compile(checkpointer=InMemorySaver())


def run_pending(
    gateway: Any,
    tier: Any,
    blueprint: Any,
    workdir: Any,
    limit: int | None = None,
    only: int | None = None,
) -> list[tuple[str, str]]:
    """Chạy đồ thị cho MỌI ô còn thiếu tệp dán. Trả về [(slot, outcome)]."""
    from app.content.exam.writer import pending

    graph = build(gateway, tier, blueprint, workdir)
    out: list[tuple[str, str]] = []
    slots = pending(blueprint, workdir)
    if only is not None:
        slots = [s for s in slots if parts_of(blueprint, s.id) == only]
    for index, slot in enumerate(slots, start=1):
        if limit is not None and index > limit:
            break
        final = graph.invoke(
            {"slot_id": slot.id, "revision": 0, "outcome": "pending"},
            config={"configurable": {"thread_id": slot.id}},
        )
        out.append((slot.id, final["outcome"]))
        print(f"  ✓ [{index}/{len(slots)}] {slot.id} → {final['outcome']}", flush=True)
    return out


def parts_of(blueprint: Any, slot_id: str) -> int:
    for part in blueprint.parts:
        if any(slot.id == slot_id for slot in part.slots):
            return part.part
    raise KeyError(slot_id)


def main(argv: list[str] | None = None) -> int:
    """Chạy đồ thị cho các ô còn thiếu. CLI song song với `write`."""
    import argparse

    from app.content.exam import blueprint as bp
    from app.content.generate_exam import _gateway, blueprint_path, workdir_for
    from app.services.llm.router import Tier

    parser = argparse.ArgumentParser(description="Vòng viết→kiểm→phê cho các ô còn thiếu.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--model", default=None, help="provider/model (vd `bai/gpt-5.6-sol`)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--part", type=int, default=None)
    parser.add_argument("--tier", default="cheap", choices=["cheap", "strong"])
    args = parser.parse_args(argv)

    blueprint = bp.load(blueprint_path(args.slug))
    gateway = _gateway(args.model)
    tier = Tier.STRONG if args.tier == "strong" else Tier.CHEAP

    results = run_pending(gateway, tier, blueprint, workdir_for(args.slug), args.limit, args.part)
    accepted = sum(1 for _, outcome in results if outcome == "accepted")
    escalated = sum(1 for _, outcome in results if outcome == "escalated")
    print(
        f"\n{len(results)} ô · {accepted} nhận · {escalated} giao người (hết {MAX_REVISIONS} vòng)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
