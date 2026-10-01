"""Lắp graph: nối node thành luồng write → validate → verdict → evaluate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.content.exam.blueprint import Blueprint
from app.content.exam_agents.upgraded.evaluate import _evaluator_node
from app.content.exam_agents.upgraded.state import (
    DEFAULT_MAX_TOKENS,
    Node,
    RetryPolicy,
    SlotState,
    _Parts,
)
from app.content.exam_agents.upgraded.validate import (
    _content_check_node,
    _structural_check_node,
)
from app.content.exam_agents.upgraded.verdict import (
    _accept,
    _escalate,
    _route_after_evaluator,
    _route_after_verdict,
    _verdict_node,
)
from app.content.exam_agents.upgraded.write import _write_node
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier


def build(
    gateway: Gateway,
    tier: Tier,
    blueprint: Blueprint,
    workdir: Path,
    max_tokens: int | None = DEFAULT_MAX_TOKENS,
    verifier: Gateway | None = None,
    verify_all: bool = False,
    *,
    checkpointer: Any | None = None,
    retry_policy: RetryPolicy | None = None,
) -> Any:
    """Build compiled graph.

    `checkpointer` được inject để production có thể dùng persistent saver.
    Nếu không truyền, dùng InMemorySaver để chạy ngay.
    """

    parts = _Parts(blueprint)
    policy = retry_policy or RetryPolicy()

    builder = StateGraph(SlotState)

    # add_node của LangGraph 1.x khó chịu với node trả update-một-phần (dict)
    # thay vì state đầy đủ — pattern chuẩn của nó, nhưng generic chưa nới lỏng.
    # Cast một lần tại đây thay vì rải type: ignore khắp các node.
    def _node(fn: Node) -> Any:
        return fn

    builder.add_node(
        "write",
        _node(
            _write_node(
                gateway,
                tier,
                workdir,
                parts,
                max_tokens,
            )
        ),
    )

    builder.add_node(
        "structural_check",
        _node(_structural_check_node(parts)),
    )

    builder.add_node(
        "content_check",
        _node(
            _content_check_node(
                blueprint,
                workdir,
                parts,
                verifier,
                tier,
                verify_all,
            )
        ),
    )

    builder.add_node(
        "evaluator",
        _node(_evaluator_node(gateway, tier)),
    )

    builder.add_node(
        "verdict",
        _node(_verdict_node(policy)),
    )

    builder.add_node(
        "accept",
        _node(_accept),
    )

    builder.add_node(
        "escalate",
        _node(_escalate),
    )

    builder.add_edge(START, "write")
    builder.add_edge("write", "structural_check")
    builder.add_edge("structural_check", "content_check")
    builder.add_edge("content_check", "verdict")

    builder.add_conditional_edges(
        "verdict",
        _route_after_verdict,
        {
            "accept": "accept",
            "evaluator": "evaluator",
            "escalate": "escalate",
        },
    )

    builder.add_conditional_edges(
        "evaluator",
        _route_after_evaluator,
        {
            "write": "write",
            "escalate": "escalate",
        },
    )

    builder.add_edge("accept", END)
    builder.add_edge("escalate", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())
