"""Runner + CLI: chạy graph cho các slot pending/retry, in tiến độ."""

from __future__ import annotations

import threading
from pathlib import Path
from time import perf_counter
from typing import Any

from app.content.exam.blueprint import Blueprint
from app.content.exam_agents.upgraded.assemble import build
from app.content.exam_agents.upgraded.state import MAX_REVISIONS, RetryPolicy
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier


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
    *,
    checkpointer: Any | None = None,
    max_revisions: int = MAX_REVISIONS,
) -> list[tuple[str, str]]:
    """Chạy graph cho các slot pending/retry.

    Trả về [(slot_id, outcome)].
    """

    from itertools import groupby

    from app.content.exam.writer import pending

    graph = build(
        gateway,
        tier,
        blueprint,
        workdir,
        max_tokens,
        verifier,
        verify_all,
        checkpointer=checkpointer,
        retry_policy=RetryPolicy(
            max_revisions=max_revisions,
        ),
    )

    wanted = {
        slot.id
        for slot in pending(blueprint, workdir)
    } | set(retry or ())

    slots = [
        slot
        for part in blueprint.parts
        for slot in part.slots
        if slot.id in wanted
    ]

    if only is not None:
        slots = [
            slot
            for slot in slots
            if parts_of(blueprint, slot.id) == only
        ]

    if limit is not None:
        slots = slots[:limit]

    groups = [
        (part, list(items))
        for part, items in groupby(
            slots,
            key=lambda slot: parts_of(blueprint, slot.id),
        )
    ]

    if not slots:
        scope = f"part {only}" if only is not None else "cả đề"
        print(
            f"  {scope}: đã đủ ô, không còn gì để viết",
            flush=True,
        )
        return []

    out: list[tuple[str, str]] = []
    total = len(slots)
    done = 0
    run_started = perf_counter()

    def heartbeat(
        label: str,
        stop: threading.Event,
        since: float,
    ) -> None:
        while not stop.wait(60):
            print(
                f"      … {label} vẫn đang chạy "
                f"({perf_counter() - since:.0f}s)",
                flush=True,
            )

    for part, items in groups:
        print(
            f"\n── part {part} · {len(items)} ô ──",
            flush=True,
        )

        part_started = perf_counter()
        accepted = 0
        escalated = 0

        for slot in items:
            done += 1
            started = perf_counter()

            print(
                f"  → [{done}/{total}] {slot.id} …",
                flush=True,
            )

            stop = threading.Event()

            threading.Thread(
                target=heartbeat,
                args=(slot.id, stop, started),
                daemon=True,
            ).start()

            final: dict[str, Any]

            try:
                final = graph.invoke(
                    {
                        "slot_id": slot.id,
                        "part": part,
                        "revision": 0,
                        "max_revisions": max_revisions,
                        "fatal": False,
                        "blocked": False,
                        "outcome": "pending",
                        "status": "pending",
                        "findings": [],
                        "previous_findings": [],
                        "fixed_findings": [],
                        "new_findings": [],
                        "persistent_findings": [],
                        "revision_plan": None,
                        "fix_hint": None,
                        "artifacts": [],
                        "flags": [],
                        "metrics": {},
                    },
                    config={
                        "configurable": {
                            "thread_id": slot.id,
                        }
                    },
                )

            finally:
                stop.set()

            outcome = final.get("outcome", "escalated")

            out.append((slot.id, outcome))

            if outcome == "accepted":
                accepted += 1
            else:
                escalated += 1

            print(
                f"  ✓ [{done}/{total}] {slot.id} → {outcome} "
                f"({perf_counter() - started:.0f}s)",
                flush=True,
            )

            if outcome == "escalated":
                for line in final.get("log", []):
                    print(
                        f"      {line}",
                        flush=True,
                    )

                for finding in final.get("findings", []):
                    if finding.get("severity") == "error":
                        print(
                            "      ✗ "
                            f"[{finding.get('code')}] "
                            f"{finding.get('message')}",
                            flush=True,
                        )

                for flag in final.get("flags", []):
                    print(
                        f"      ⚠ {flag}",
                        flush=True,
                    )

        elapsed = perf_counter() - run_started
        left = (
            (elapsed / done) * (total - done)
            if done
            else 0.0
        )

        tail = (
            f" · còn {total - done} ô, "
            f"ước {left / 60:.0f} phút"
            if done < total
            else ""
        )

        print(
            f"  part {part}: {accepted} nhận · "
            f"{escalated} giao người · "
            f"{(perf_counter() - part_started) / 60:.1f} phút"
            f"{tail}",
            flush=True,
        )

        print(
            f"           {gateway.tally.line()}",
            flush=True,
        )

    return out


def parts_of(
    blueprint: Blueprint,
    slot_id: str,
) -> int:
    for part in blueprint.parts:
        if any(
            slot.id == slot_id
            for slot in part.slots
        ):
            return part.part

    raise KeyError(slot_id)


def main(
    argv: list[str] | None = None,
) -> int:
    """CLI song song với `write`."""

    import argparse

    from app.content.exam import blueprint as bp
    from app.content.exam_cli.paths import (
        _gateway,
        blueprint_path,
        workdir_for,
    )

    parser = argparse.ArgumentParser(
        description=(
            "Production-grade vòng "
            "write → validate → evaluate → revise."
        )
    )

    parser.add_argument(
        "--slug",
        required=True,
    )

    parser.add_argument(
        "--model",
        default=None,
        help="provider/model, ví dụ bai/gpt-5.6-sol",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--part",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--revisions",
        type=int,
        default=MAX_REVISIONS,
        help=f"số revision tối đa (mặc định {MAX_REVISIONS})",
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=(
            "trần output mỗi lượt viết; nếu bỏ qua, "
            "writer tự chọn theo part/slot"
        ),
    )

    parser.add_argument(
        "--tier",
        default="cheap",
        choices=["cheap", "strong"],
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "bật paid checker cho ô có hình đã sạch ở tầng deterministic "
            "(như bản graph cũ) — evaluator vẫn chạy khi revise"
        ),
    )

    args = parser.parse_args(argv)

    if args.revisions < 1:
        parser.error("--revisions phải >= 1")

    blueprint = bp.load(
        blueprint_path(args.slug)
    )

    gateway = _gateway(args.model)

    tier = (
        Tier.STRONG
        if args.tier == "strong"
        else Tier.CHEAP
    )

    results = run_pending(
        gateway,
        tier,
        blueprint,
        workdir_for(args.slug),
        args.limit,
        args.part,
        args.max_tokens,
        verifier=gateway if args.verify else None,
        # Giữ ngữ nghĩa bản cũ: paid check chỉ ô có hình. Đấu verify_all=True
        # là trả tiền cho cả 103 ô mà không báo trước.
        verify_all=False,
        max_revisions=args.revisions,
    )

    accepted = sum(
        1
        for _, outcome in results
        if outcome == "accepted"
    )

    escalated = sum(
        1
        for _, outcome in results
        if outcome == "escalated"
    )

    print(
        f"\n{len(results)} ô · "
        f"{accepted} nhận · "
        f"{escalated} giao người "
        f"(tối đa {args.revisions} revision)"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
