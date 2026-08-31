"""Đồ thị đầy đủ: plan → (write → check → critic)× cho MỌI ô của đề.

So với `graph.py` (chỉ vòng per-slot), đồ thị này thêm node đầu tiên —
**plan** — và một node điều phối **next** chạy vòng qua các ô còn thiếu. Nói
cách khác: từ một dòng lệnh với chỉ `--slug`, ra một đề đầy đủ tệp dán.

Node plan TÁI DÙNG nguyên logic của `cmd_plan` (builder per-part + model sinh
bối cảnh + fallback về bảng cấu hình) qua một seam nhỏ: `plan_blueprint()`.
`cmd_plan` và node này cùng gọi nó — hai bản sao của "cách dựng blueprint" sẽ
trôi khỏi nhau, và cái trôi là cái không ai chạy bằng tay.

Chạy:

    uv run python -m app.content.exam_agents.full --slug tp-form-08 \
        [--model provider/model] [--limit N] [--skip-plan]

`--skip-plan` khi blueprint đã có (chạy lại giữa chừng) — node plan vẫn chạy
nhưng chỉ load, không gọi model.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.content.exam.blueprint import Blueprint
from app.content.exam_agents.graph import (
    run_pending,
)
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier

RETRY_TRIES = 7
RETRY_DELAY = 6.0


class FullState(TypedDict, total=False):
    """Trạng thái của đồ thị full. Khác `SlotState`: đây là trạng thái CỦA ĐỀ,
    không phải của một ô — vòng per-slot chạy bên trong node `slotloop`."""

    slug: str
    planned: bool
    limit: int | None
    only: int | None
    accepted: int
    escalated: int
    max_tokens: int | None
    verify: bool  # bật hai tầng kiểm dùng model trong vòng per-slot
    balanced: str | None  # phân bố đáp án sau khi cân
    spread: list[str]  # lệch phân bố trên CẢ đề, rỗng là đạt
    current: str | None  # ô đang chạy
    current_outcome: str | None
    log: Annotated[list[str], operator.add]


# Cùng lý do như `graph.py`: cập nhật một phần, giá trị khác kiểu theo khoá.
FullUpdate = dict[str, Any]
FullNode = Callable[[FullState], FullUpdate]


def plan_blueprint(
    slug: str,
    title: str,
    seed: int,
    model: str | None,
    tier: Tier,
    parts: list[int] | None = None,
) -> str:
    """Dựng/merge blueprint cho `slug`, đúng logic của `cmd_plan`.

    Tách từ `cmd_plan` thành hàm để cả CLI lẫn node graph gọi một đường — hai
    bản sao của "cách dựng blueprint" sẽ trôi khỏi nhau. Trả về path đã lưu.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam_cli.paths import _gateway, blueprint_path
    from app.content.exam_cli.plan import (
        _graphic_hosts,
        _override_contexts,
        _scene_hosts,
        generate_part1_scenes,
        generate_part_graphics,
        generate_part_scenes,
    )

    path = blueprint_path(slug)
    existing = bp.load(path) if path.exists() else None
    builders = {
        1: bp.build_part1,
        2: bp.build_part2,
        3: bp.build_part3,
        4: bp.build_part4,
        5: bp.build_part5,
        6: bp.build_part6,
        7: bp.build_part7,
    }
    for part_number in parts or range(1, 8):
        # Bảy hàm dựng có chữ ký khác nhau (Part 1 và 3/4 nhận thêm tham số),
        # nên chỉ chốt được KIỂU TRẢ VỀ — vẫn hơn `Any` trần.
        builder: Callable[..., Blueprint] = builders[part_number]
        built = builder(slug, title, seed)
        if model:
            try:
                gateway = _gateway(model)
                if part_number == 1:
                    scenes = generate_part1_scenes(gateway, tier)
                    built = bp.build_part1(slug, title, seed, scenes)
                else:
                    contexts = generate_part_scenes(gateway, tier, part_number, _scene_hosts(built))
                    if part_number in (3, 4, 7):
                        # Bối cảnh model phải áp TRƯỚC: `_graphic_hosts` đọc `context`,
                        # và bản của bảng sắp bị dập đè ở dòng dưới.
                        _override_contexts(built, contexts)
                        graphics = generate_part_graphics(
                            gateway, tier, part_number, _graphic_hosts(built)
                        )
                        built = builder(slug, title, seed, graphics)
                    _override_contexts(built, contexts)
            except Exception as failure:  # noqa: BLE001 — rơi về bảng là đường đúng
                print(
                    f"  plan part {part_number}: không sinh bằng model ({failure}) — dùng bảng.",
                    flush=True,
                )
        plan = bp.merge(existing, built)
        problems = bp.validate(plan)
        if problems:
            raise RuntimeError("; ".join(problems))
        bp.save(plan, path)
        existing = plan
    return str(path)


def _plan_node(gateway: Gateway, tier: Tier, model: str | None) -> FullNode:
    def plan(state: FullState) -> FullUpdate:

        from app.content.exam_cli.paths import blueprint_path

        slug = state["slug"]
        path = blueprint_path(slug)
        if path.exists():
            # Blueprint đã có: chạy lại giữa chừng — không đốt quota plan lần nữa.
            print(f"  plan: đã có {path} — bỏ qua", flush=True)
            return {"planned": True}
        saved = plan_blueprint(slug, f"TOEIC Pilot — {slug}", 20260822, model, tier)
        print(f"  plan: {saved}", flush=True)
        return {"planned": True}

    return plan


def _slotloop_node(gateway: Gateway, tier: Tier, workdir: Path) -> FullNode:
    def slotloop(state: FullState) -> FullUpdate:
        from pathlib import Path

        from app.content.exam import blueprint as bp
        from app.content.exam_cli.paths import blueprint_path

        slug = state["slug"]
        blueprint = bp.load(blueprint_path(slug))
        result = run_pending(
            gateway,
            tier,
            blueprint,
            Path(str(workdir)),
            limit=state.get("limit"),
            only=state.get("only"),
            max_tokens=state.get("max_tokens"),
            verifier=gateway if state.get("verify") else None,
        )
        accepted = sum(1 for _, outcome in result if outcome == "accepted")
        escalated = sum(1 for _, outcome in result if outcome == "escalated")
        return {"accepted": accepted, "escalated": escalated}

    return slotloop


def _has_paste(blueprint: Any, workdir: Path, only: int | None) -> bool:
    """Có tệp dán nào trong phạm vi đang xét không."""
    from app.content.exam.writer import paste_path

    return any(
        paste_path(workdir, slot).exists()
        for part in blueprint.parts
        if only is None or part.part == only
        for slot in part.slots
    )


def _balance_node(workdir: Path) -> FullNode:
    """Cân lại vị trí đáp án trên CẢ đề. GHI ĐÈ tệp dán, nên phải chạy trước `load`.

    Không đặt được trong vòng per-slot: phân bố đáp án là thuộc tính của cả đề, và
    ô đang viết không biết những ô kia đã dùng chữ cái nào. Đo được trên một lượt
    chạy thật: 29/30 câu đáp án (A) — mọi câu đều hợp lệ nên không phép kiểm từng
    câu nào thấy.
    """

    def balance(state: FullState) -> FullUpdate:
        from app.content.exam import balance as balancer
        from app.content.exam import blueprint as bp
        from app.content.exam_cli.paths import blueprint_path

        blueprint = bp.load(blueprint_path(state["slug"]))
        # Điều kiện là "CÓ TỆP ĐỂ CÂN", không phải "lượt này có viết gì không".
        # Một part viết xong bởi lượt chạy sau đó bị chết giữa chừng thì chưa bao
        # giờ được cân, và điều kiện theo lượt chạy khiến nó KHÔNG BAO GIỜ cân
        # được nữa qua `full` — mỗi lần chạy lại đều thấy "không ô nào được viết".
        # Cân lại là vô hại: đích tính từ seed nên chạy hai lần ra cùng kết quả.
        if not _has_paste(blueprint, workdir, state.get("only")):
            print("  balance: chưa có tệp dán nào — bỏ qua", flush=True)
            return {}
        tally = balancer.balance(blueprint, workdir, state.get("only"))
        total = sum(tally.values()) or 1
        line = "  ".join(f"{k}={v} ({v / total * 100:.0f}%)" for k, v in tally.items())
        print(f"  balance: {line}", flush=True)
        return {"balanced": line}

    return balance


def _spread_node(workdir: Path) -> FullNode:
    """Kiểm phân bố đáp án trên CẢ đề, sau khi đã cân."""

    def spread(state: FullState) -> FullUpdate:
        from app.content.exam import blueprint as bp
        from app.content.exam import check as checker
        from app.content.exam.writer import pending
        from app.content.exam_cli.paths import blueprint_path

        blueprint = bp.load(blueprint_path(state["slug"]))
        left = pending(blueprint, workdir)
        if left:
            # Phân bố là số liệu của CẢ đề, nên trên một đề còn thiếu ô nó đang
            # báo về chỗ thiếu chứ không về nội dung. Một cảnh báo luôn kêu là
            # một cảnh báo người ta học cách bỏ qua.
            print(f"  spread: còn {len(left)} ô chưa viết — chưa kiểm phân bố", flush=True)
            return {}
        problems = checker.check_answer_spread(workdir, blueprint)
        for problem in problems:
            print(f"  ✗ CẢ ĐỀ: {problem}", flush=True)
        if not problems:
            print("  spread: phân bố đáp án đạt", flush=True)
        return {"spread": problems}

    return spread


def build_full(
    gateway: Gateway, tier: Tier, model: str | None, workdir: Path
) -> Any:  # đồ thị đã biên dịch — kiểu của LangGraph
    builder = StateGraph(FullState)

    def _node(fn: FullNode) -> Any:
        return fn

    builder.add_node("plan", _node(_plan_node(gateway, tier, model)))
    builder.add_node("slotloop", _node(_slotloop_node(gateway, tier, workdir)))
    builder.add_node("balance", _node(_balance_node(workdir)))
    builder.add_node("spread", _node(_spread_node(workdir)))

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "slotloop")
    builder.add_edge("slotloop", "balance")
    builder.add_edge("balance", "spread")
    builder.add_edge("spread", END)
    return builder.compile(checkpointer=InMemorySaver())


def main(argv: list[str] | None = None) -> int:
    """Một dòng lệnh: plan (nếu chưa có) rồi chạy vòng per-slot cho tới khi đủ."""
    import argparse

    from app.content.exam_cli.paths import _gateway, workdir_for
    from app.services.llm.router import Tier

    parser = argparse.ArgumentParser(description="Sinh trọn đề: plan + vòng viết→kiểm→phê.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--model", default=None, help="provider/model (vd `bai/glm-5.3-flash`)")
    parser.add_argument("--limit", type=int, default=None, help="chỉ viết N ô lượt này")
    parser.add_argument("--part", type=int, default=None, help="chỉ sinh một part")
    parser.add_argument("--tier", default="cheap", choices=["cheap", "strong"])
    parser.add_argument(
        "--verify",
        action="store_true",
        help="bật hai tầng kiểm dùng model cho những ô đã sạch ở tầng miễn phí "
        "— tốn thêm ~2 lượt gọi mỗi ô",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="trần đầu ra mỗi lượt viết; model suy luận cần rộng (mặc định 6000)",
    )
    parser.add_argument(
        "--seed", type=int, default=20260822, help="seed cho blueprint (cùng seed = cùng chủ đề)"
    )
    args = parser.parse_args(argv)

    tier = Tier.STRONG if args.tier == "strong" else Tier.CHEAP
    gateway = _gateway(args.model)
    workdir = workdir_for(args.slug)

    graph = build_full(gateway, tier, args.model, workdir)
    final = graph.invoke(
        {
            "slug": args.slug,
            "planned": False,
            "limit": args.limit,
            "only": args.part,
            "max_tokens": args.max_tokens,
            "verify": args.verify,
            "accepted": 0,
            "escalated": 0,
            "balanced": None,
            "spread": [],
        },
        config={"configurable": {"thread_id": args.slug}},
    )
    print(f"\nXong: {final['accepted']} ô nhận · {final['escalated']} giao người · đề ở {workdir}")
    if final.get("balanced"):
        print(f"Phân bố đáp án: {final['balanced']}")
    if final.get("spread"):
        print(f"Phân bố CẢ ĐỀ còn lệch: {len(final['spread'])} vấn đề — xem dòng ✗ ở trên")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
