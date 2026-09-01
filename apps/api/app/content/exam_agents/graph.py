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
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.content.exam.blueprint import Blueprint, QuestionSlot
from app.content.exam.prompts._registry import exam_prompt
from app.content.exam.writer import MissingBlock, max_tokens_for, save_slot, write_slot
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier

# Trần vòng lặp. Ba vòng là chỗ dừng đúng: một ô hỏng cùng kiểu ba lần thì lỗi
# nằm ở prompt/brief, không nằm ở lượt viết — quay tiếp chỉ đốt quota.
MAX_REVISIONS = 3
RETRY_TRIES = 7
RETRY_DELAY = 6.0
# Rộng hơn nhiều so với đoạn 40 từ node phê xin: model bắt buộc suy luận
# (GLM 5.3 không tắt được) tiêu trần vào phần nghĩ rồi mới trả lời, nên trần
# bằng cỡ câu trả lời làm nó chết đói — sau khi khâu viết đã tốn một lượt gọi.
CRITIC_MAX_TOKENS = 4000


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
    # Hỏng ở chính lượt gọi, không ở nội dung — viết lại không cứu được.
    fatal: bool
    outcome: str
    log: Annotated[list[str], operator.add]


# Cập nhật MỘT PHẦN của state: LangGraph gộp theo từng khoá, nên giá trị khác
# kiểu theo khoá và `Any` ở đây là mô tả đúng, không phải chỗ tắt kiểm tra.
NodeUpdate = dict[str, Any]
Node = Callable[[SlotState], NodeUpdate]


class _Parts:
    """Tra slot + part theo id, một lần cho cả lượt chạy."""

    def __init__(self, blueprint: Blueprint) -> None:
        self.by_id: dict[str, tuple[QuestionSlot, int]] = {}
        for part in blueprint.parts:
            for slot in part.slots:
                self.by_id[slot.id] = (slot, part.part)

    def slot(self, slot_id: str) -> QuestionSlot:
        return self.by_id[slot_id][0]

    def part(self, slot_id: str) -> int:
        return self.by_id[slot_id][1]


def _write_node(
    gateway: Gateway, tier: Tier, workdir: Path, parts: _Parts, max_tokens: int | None = None
) -> Node:
    """Viết lại ô. `write_slot` ném `MissingBlock` khi đầu ra bị cắt — biến thành
    trạng thái bị chặn thay vì để ngoại lệ làm đồ thị chết. `fix_hint` của critic
    đi kèm: đây là toàn bộ điểm của vòng lặp — sửa theo lý do, không sinh lại mù.

    Sau khi viết, tách `[PHOTO]`/`[GRAPHIC]` ra hiện vật riêng (photos/, graphics/)
    Y HỆT `cmd_write` làm: parser từ chối dòng lạ sau đáp án, và bảng là dữ liệu
    để vẽ — hai thứ đó không phải dòng để dán."""

    def write(state: SlotState) -> NodeUpdate:
        from app.content.exam.writer import GRAPHIC_MARKER, split_all, split_photo
        from app.services.llm.base import LLMError, LLMQuotaExhausted

        slot = parts.slot(state["slot_id"])
        part = parts.part(state["slot_id"])
        update: NodeUpdate = {"revision": state["revision"] + 1}
        hint = state.get("fix_hint")
        try:
            block = write_slot(
                gateway,
                slot,
                tier,
                part,
                fix_hint=hint,
                max_tokens=max_tokens or max_tokens_for(part, slot),
            )
        except LLMQuotaExhausted:
            # Hạn mức NGÀY không tự hết, nên đi tiếp chỉ sinh ra đúng lỗi này cho
            # mọi ô còn lại và chôn mất dòng nói nguyên nhân. Dừng hẳn, giữ lại
            # những ô đã viết. Cùng cách xử lý mà `check` đã dùng.
            raise
        except LLMError as failure:
            # Một ô hỏng KHÔNG được giết cả lượt chạy: chặng này chạy hàng giờ
            # trên 103 ô, và để một lỗi 503 — hay một trần đầu ra quá hẹp cho
            # riêng ô có hình — vứt hết phần còn lại là cách chắc chắn nhất
            # khiến không ai chạy nó qua đêm.
            #
            # `fatal` chứ không quay lại critic: `with_backoff` đã thử bảy lần,
            # nên hỏng ở đây là hỏng của lượt gọi chứ không của nội dung, và
            # không có bản nháp nào để chấm. Ba vòng viết lại sẽ hỏng y hệt.
            update |= {
                "draft": "",
                "blocked": True,
                "fatal": True,
                "problems": [str(failure)],
                "log": [f"vòng {update['revision']}: {failure}"],
            }
            return update
        except MissingBlock as cut:
            # Cũng ghi vào `log`: lượt viết hỏng thì node `check` không chạy, nên
            # không có nó thì một ô bị cắt ba lần sẽ bị giao người mà không in ra
            # dòng nào — đúng cái lỗ mà bản in lý do sinh ra để bịt.
            update |= {
                "draft": "",
                "blocked": True,
                "problems": [str(cut)],
                "fix_hint": "Bị cắt giữa phần suy luận — viết ngắn hơn, đi thẳng vào khối.",
                "log": [f"vòng {update['revision']}: {cut}"],
            }
            return update
        # Ghi xuống đĩa NGAY: hàng đợi là một truy vấn trên thư mục, ô đã ghi là
        # ô không phải trả tiền lại. `check` sau đó đọc từ đĩa — cùng hiện vật.
        # Trước khi lưu, tách hai hiện vật đi kèm — đúng đường của `cmd_write`,
        # không có nó thì Part 1 mất mô tả ảnh và Part 3/4 mất bảng dữ liệu.
        photo, block = split_photo(block)
        if photo:
            photo_path = workdir / "photos" / f"{slot.id}.txt"
            photo_path.parent.mkdir(parents=True, exist_ok=True)
            photo_path.write_text(photo + "\n")
        tables, block = split_all(block, GRAPHIC_MARKER)
        for order, table in enumerate(tables, start=1):
            suffix = "" if len(tables) == 1 else f"-{order}"
            table_path = workdir / "graphics" / f"{slot.id}{suffix}.txt"
            table_path.parent.mkdir(parents=True, exist_ok=True)
            table_path.write_text(table + "\n")
        save_slot(workdir, slot, block)
        update |= {"draft": block, "blocked": False, "problems": [], "flags": []}
        # Hint đã dùng xong: không xoà thì lượt sau đọc lại hint cũ của lỗi cũ.
        update["fix_hint"] = None
        return update

    return write


def _check_node(
    blueprint: Blueprint,
    workdir: Path,
    parts: _Parts,
    verifier: Gateway | None = None,
    tier: Tier = Tier.CHEAP,
    verify_all: bool = False,
) -> Node:
    """Nguồn DUY NHẤT được điền `blocked`.

    `check_blueprint` chạy trên toàn bộ part của ô (nó đọc tệp dán từ đĩa), rồi
    chỉ lấy report của ô đang chạy. Cùng hàm mà lệnh `check` chạy — bản kiểm
    riêng sẽ trôi khỏi parser thật.

    **Hai lượt, và thứ tự là chỗ tiết kiệm.** Lượt đầu `gateway=None`: parser
    thật, luật hình, trùng lặp — không tốn gì. Chỉ ô nào SẠCH mới đi tiếp lượt
    hai (`verifier`), nơi có `verify_answer` và `count_workable_options`. Ô đã
    hỏng ở lượt đầu không cần hỏi model "đáp án có đúng không" — nó còn chưa
    đọc được. Gộp một lượt thì mỗi ô hỏng vẫn tốn hai lượt gọi, nhân với ba
    vòng viết lại.

    `verifier=None` giữ nguyên hành vi cũ: hoàn toàn miễn phí.
    """

    def check(state: SlotState) -> NodeUpdate:
        if state["blocked"]:  # lượt viết đã hỏng trước khi có khối — không có gì để kiểm
            return {}
        from app.content.exam.check import check_blueprint

        part = parts.part(state["slot_id"])
        reports = check_blueprint(blueprint, workdir, gateway=None, only=part, quiet=True)
        report = next((r for r in reports if r.slot_id == state["slot_id"]), None)
        # Tầng trả tiền chỉ ĐỔI được kết cục ở ô có hình: phán quyết luật hình
        # là findings duy nhất thành `problem`, còn `verify_answer` và
        # `count_workable_options` chỉ sinh cờ. Chạy nó ở ô khác là trả tiền cho
        # một thứ không chặn được gì — `verify_all` là chỗ bắt buộc nếu muốn.
        wants_paid = verify_all or bool(parts.slot(state["slot_id"]).graphic)
        if report is not None and not report.problems and verifier is not None and wants_paid:
            # `slot_id`, KHÔNG phải `only=part`: lượt này gọi model, và
            # `only=part` khiến ô thứ k kéo theo cả k ô đã viết — chi phí cộng
            # dồn thành bình phương (đo được 8,2× trên một đề). Lượt miễn phí ở
            # trên vẫn quét cả part, vì phép dò trùng cần thế và nó không tốn gì.
            paid = check_blueprint(
                blueprint,
                workdir,
                gateway=verifier,
                tier=tier,
                ambiguity=True,
                only=part,
                quiet=True,
                slot_id=state["slot_id"],
            )
            report = next((r for r in paid if r.slot_id == state["slot_id"]), report)
        if report is None:
            return {
                "blocked": True,
                "problems": ["check không đọc được ô này"],
                "log": [f"vòng {state['revision']}: check không đọc được ô này"],
            }
        # Ghi MỘT dòng mỗi vòng vào `log`. Đó là thứ trả lời câu hỏi thật sự
        # đáng hỏi khi một ô bị giao người: ba vòng hỏng CÙNG một kiểu (lỗi ở
        # brief) hay ba kiểu khác nhau (model chao đảo)? Chỉ nhìn vòng cuối thì
        # hai ca ấy giống hệt nhau.
        summary = "; ".join(report.problems) if report.problems else "sạch"
        # Chỉ in khi SẮP viết lại. Vòng cuối đi thẳng tới escalate, và ở đó
        # `run_pending` đã in cả `log` — in ở đây nữa là lặp.
        if report.blocked and state["revision"] < MAX_REVISIONS:
            print(f"      ↻ vòng {state['revision']}: {summary[:110]}", flush=True)
        return {
            "blocked": report.blocked,
            "problems": list(report.problems),
            "flags": list(report.flags),
            "log": [f"vòng {state['revision']}: {summary}"],
        }

    return check


def _critic_node(gateway: Gateway, tier: Tier) -> Node:
    """Phê — MỘT lượt gọi. Model CHẤM chứ không viết lại: trả gợi ý sửa.

    feature=`exam_verify` vì nó là cùng loại việc với đối chiếu đáp án: đọc một
    ô đã có, trả nhận định. Muốn tách tier riêng thì thêm feature mới vào bảng
    giá, không phải sửa đồ thị."""

    def critic(state: SlotState) -> NodeUpdate:
        result = with_backoff(
            lambda: gateway.run(
                LLMRequest(
                    system=exam_prompt("critic").render(),
                    user=(
                        "Lý do bị chặn:\n"
                        + "\n".join(f"- {p}" for p in state["problems"])
                        + f"\n\n---\n{state['draft'][:4000]}"
                    ),
                    max_tokens=CRITIC_MAX_TOKENS,
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
    if state.get("fatal") or state["revision"] >= MAX_REVISIONS:
        return "escalate"
    return "critic"


def _after_critic(state: dict[str, Any]) -> str:
    # critic không đổi `blocked`; lượt viết sau sẽ sửa. Trần vòng đã được
    # `after_check` giữ — tới đây thì luôn quay lại viết.
    return "write"


def _accept(state: SlotState) -> NodeUpdate:
    return {"outcome": "accepted"}


def _escalate(state: SlotState) -> NodeUpdate:
    return {"outcome": "escalated"}


def build(
    gateway: Gateway,
    tier: Tier,
    blueprint: Blueprint,
    workdir: Path,
    max_tokens: int | None = None,
    verifier: Gateway | None = None,
    verify_all: bool = False,
) -> Any:  # đồ thị đã biên dịch là kiểu của LangGraph — `Any` với mypy vì thư viện không có stub
    parts = _Parts(blueprint)

    builder = StateGraph(SlotState)

    # add_node của LangGraph 1.x khó chịu với node trả update-một-phần (dict)
    # thay vì state đầy đủ — pattern chuẩn của nó, nhưng generic chưa nới lỏng.
    # Cast một lần tại đây thay vì rải type: ignore khắp các node.
    def _node(fn: Node) -> Any:
        return fn

    builder.add_node("write", _node(_write_node(gateway, tier, workdir, parts, max_tokens)))
    builder.add_node(
        "check", _node(_check_node(blueprint, workdir, parts, verifier, tier, verify_all))
    )
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
    gateway: Gateway,
    tier: Tier,
    blueprint: Blueprint,
    workdir: Path,
    limit: int | None = None,
    only: int | None = None,
    max_tokens: int | None = None,
    verifier: Gateway | None = None,
    verify_all: bool = False,
    retry: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Chạy đồ thị cho MỌI ô còn thiếu tệp dán. Trả về [(slot, outcome)].

    `max_tokens` đi thẳng vào `write_slot`: model suy luận tiêu một phần lớn trần
    cho phần suy nghĩ trước khi viết — trần mặc định 6000 từng bị một lượt eat
    22 975 ký tự suy nghĩ và không kịp trả lời."""
    import threading
    from itertools import groupby
    from time import perf_counter

    def heartbeat(label: str, stop: threading.Event, since: float) -> None:
        """In một dòng mỗi phút trong lúc một ô đang chạy.

        Một lượt viết ô có hình mất 5–6 phút đo được, và trong quãng đó KHÔNG có
        gì để in: dòng `✓` chờ ô xong, dòng `↻` chờ khâu kiểm, còn sổ cái chỉ
        được ghi khi lượt gọi kết thúc. Im lặng năm phút không phân biệt được
        với treo — và đã bị đọc nhầm thành treo hai lần.
        """
        while not stop.wait(60):
            print(f"      … {label} vẫn đang chạy ({perf_counter() - since:.0f}s)", flush=True)

    from app.content.exam.writer import pending

    graph = build(gateway, tier, blueprint, workdir, max_tokens, verifier, verify_all)
    out: list[tuple[str, str]] = []
    # Ô `escalated` viết được rồi mới trượt kiểm, nên nó GIỮ tệp dán và
    # `pending` vĩnh viễn không trả nó về. Vòng ngoài nêu tên chúng ở `retry`,
    # để `pending` giữ nguyên nghĩa "cái gì còn thiếu" — trộn hai nghĩa vào một
    # hàm là cách làm hỏng cơ chế phục hồi duy nhất của cả pipeline.
    wanted = {slot.id for slot in pending(blueprint, workdir)} | set(retry or ())
    # Duyệt theo thứ tự blueprint chứ không nối đuôi: `groupby` bên dưới dựa vào
    # việc các ô cùng part nằm liền nhau.
    slots = [slot for part in blueprint.parts for slot in part.slots if slot.id in wanted]
    if only is not None:
        slots = [s for s in slots if parts_of(blueprint, s.id) == only]
    if limit is not None:
        slots = slots[:limit]

    # Gom theo part để in mốc: `pending` trả ô theo thứ tự blueprint nên các ô
    # cùng part đã nằm liền nhau, groupby là đủ — không cần sắp lại.
    groups = [
        (part, list(items))
        for part, items in groupby(slots, key=lambda slot: parts_of(blueprint, slot.id))
    ]
    if not slots:
        # Im lặng ở đây đọc ra như hỏng. "0 ô nhận" không phân biệt được "đã đủ
        # rồi" với "tìm không ra ô nào", và hai ca đó cần hai hành động ngược
        # nhau: một cái là đi tiếp, một cái là đi tìm lỗi.
        scope = f"part {only}" if only is not None else "cả đề"
        print(f"  {scope}: đã đủ ô, không còn gì để viết", flush=True)
        return out

    total = len(slots)
    done = 0
    run_started = perf_counter()
    for part, items in groups:
        print(f"\n── part {part} · {len(items)} ô ──", flush=True)
        part_started = perf_counter()
        accepted = escalated = 0
        for slot in items:
            done += 1
            started = perf_counter()
            # `invoke` chạy tới khi ô accept/escalate, có thể là ba vòng viết
            # lại. Không báo trước thì màn hình câm hàng chục phút trong khi tệp
            # dán đã nằm trên đĩa từ lâu — đọc ra như treo.
            print(f"  → [{done}/{total}] {slot.id} …", flush=True)
            stop = threading.Event()
            # daemon: nhịp tim không bao giờ được giữ tiến trình sống lại.
            threading.Thread(target=heartbeat, args=(slot.id, stop, started), daemon=True).start()
            try:
                final = graph.invoke(
                    {"slot_id": slot.id, "revision": 0, "fatal": False, "outcome": "pending"},
                    config={"configurable": {"thread_id": slot.id}},
                )
            finally:
                stop.set()
            outcome = final["outcome"]
            out.append((slot.id, outcome))
            accepted += outcome == "accepted"
            escalated += outcome == "escalated"
            print(
                f"  ✓ [{done}/{total}] {slot.id} → {outcome} ({perf_counter() - started:.0f}s)",
                flush=True,
            )
            # Giao người mà không nói vì sao là bắt người đọc chạy `check` lần nữa để
            # biết điều đồ thị vừa biết — nghịch với chính lý do đồ thị tồn tại.
            if outcome == "escalated":
                for line in final.get("log", []):
                    print(f"      {line}", flush=True)
            # Cờ KHÔNG chặn nạp (xem `check_blueprint`: phép đếm phương án là
            # phép nhiễu nhất, chỉ `prune` mới nên quyết theo nó) — nhưng không
            # in ra thì `--verify` tính xong rồi vứt, tức là trả tiền cho một
            # kết quả không ai thấy.
            for flag in final.get("flags", []):
                print(f"      ⚠ {flag}", flush=True)
        # Ước lượng tính từ nhịp THẬT của lượt chạy này, không từ một hằng số:
        # nhịp phụ thuộc model, part và số vòng viết lại, nên đoán trước là sai.
        elapsed = perf_counter() - run_started
        left = (elapsed / done) * (total - done) if done else 0.0
        tail = f" · còn {total - done} ô, ước {left / 60:.0f} phút" if done < total else ""
        print(
            f"  part {part}: {accepted} nhận · {escalated} giao người"
            f" · {(perf_counter() - part_started) / 60:.1f} phút{tail}",
            flush=True,
        )
        print(f"           {gateway.tally.line()}", flush=True)
    return out


def parts_of(blueprint: Blueprint, slot_id: str) -> int:
    for part in blueprint.parts:
        if any(slot.id == slot_id for slot in part.slots):
            return part.part
    raise KeyError(slot_id)


def main(argv: list[str] | None = None) -> int:
    """Chạy đồ thị cho các ô còn thiếu. CLI song song với `write`."""
    import argparse

    from app.content.exam import blueprint as bp
    from app.content.exam_cli.paths import _gateway, blueprint_path, workdir_for
    from app.services.llm.router import Tier

    parser = argparse.ArgumentParser(description="Vòng viết→kiểm→phê cho các ô còn thiếu.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--model", default=None, help="provider/model (vd `bai/gpt-5.6-sol`)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--part", type=int, default=None)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="trần đầu ra mỗi lượt viết; model suy luận cần rộng (mặc định 6000)",
    )
    parser.add_argument("--tier", default="cheap", choices=["cheap", "strong"])
    parser.add_argument(
        "--verify",
        action="store_true",
        help="bật hai tầng kiểm dùng model (đối chiếu đáp án + đếm phương án dùng "
        "được) cho những ô đã sạch ở tầng miễn phí — tốn thêm ~2 lượt gọi mỗi ô",
    )
    args = parser.parse_args(argv)

    blueprint = bp.load(blueprint_path(args.slug))
    gateway = _gateway(args.model)
    tier = Tier.STRONG if args.tier == "strong" else Tier.CHEAP

    results = run_pending(
        gateway,
        tier,
        blueprint,
        workdir_for(args.slug),
        args.limit,
        args.part,
        args.max_tokens,
        verifier=gateway if args.verify else None,
    )
    accepted = sum(1 for _, outcome in results if outcome == "accepted")
    escalated = sum(1 for _, outcome in results if outcome == "escalated")
    print(
        f"\n{len(results)} ô · {accepted} nhận · {escalated} giao người (hết {MAX_REVISIONS} vòng)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
