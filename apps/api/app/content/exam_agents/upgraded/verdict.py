"""Verdict + routing + terminal nodes.

LLM không quyết định workflow: verdict là code (fatal → hết vòng →
lỗi lặp → regression → revise), router chỉ đọc outcome/status đã chốt.
"""

from __future__ import annotations

from app.content.exam_agents.upgraded.state import (
    Node,
    NodeUpdate,
    RetryPolicy,
    SlotState,
)


def _verdict_node(policy: RetryPolicy) -> Node:
    def verdict(state: SlotState) -> NodeUpdate:
        if state.get("fatal"):
            return {
                "status": "escalated",
                "outcome": "escalated",
            }

        findings = state.get("findings", [])
        errors = [
            finding
            for finding in findings
            if finding.get("severity") == "error"
        ]

        if not errors:
            return {
                "blocked": False,
                "status": "accepted",
                "outcome": "accepted",
            }

        if state["revision"] >= policy.max_revisions:
            return {
                "status": "escalated",
                "outcome": "escalated",
            }

        # Nếu cùng một lỗi lặp quá nhiều lần, tiếp tục generate thường
        # chỉ đốt quota mà không thay đổi nguyên nhân.
        if state.get("repeated_error_count", 0) >= policy.max_same_error:
            return {
                "status": "escalated",
                "outcome": "escalated",
                "log": [
                    "Escalate: cùng finding lặp quá ngưỡng."
                ],
            }

        if state.get("regression_count", 0) > policy.max_regressions:
            return {
                "status": "escalated",
                "outcome": "escalated",
                "log": [
                    "Escalate: revision tạo regression liên tiếp."
                ],
            }

        return {
            "status": "revising",
            "outcome": "pending",
        }

    return verdict


def _route_after_verdict(state: SlotState) -> str:
    if state.get("outcome") == "accepted":
        return "accept"

    if state.get("outcome") == "escalated":
        return "escalate"

    return "evaluator"


def _route_after_evaluator(state: SlotState) -> str:
    # revision_plan None = evaluator không có gì để lên kế hoạch (vd draft
    # rỗng sau MissingBlock) — viết lại mù thay vì chết AttributeError.
    if (state.get("revision_plan") or {}).get("should_regenerate", True):
        return "write"

    return "escalate"


def _accept(state: SlotState) -> NodeUpdate:
    artifacts = list(state.get("artifacts", []))

    if artifacts:
        artifacts[-1] = {
            **artifacts[-1],
            "status": "accepted",
        }

    return {
        "outcome": "accepted",
        "status": "accepted",
        "blocked": False,
        "artifacts": artifacts,
        "log": [
            f"accepted ở revision {state['revision']}"
        ],
    }


def _escalate(state: SlotState) -> NodeUpdate:
    artifacts = list(state.get("artifacts", []))

    if artifacts:
        artifacts[-1] = {
            **artifacts[-1],
            "status": "escalated",
        }

    return {
        "outcome": "escalated",
        "status": "escalated",
        "blocked": True,
        "artifacts": artifacts,
        "log": [
            (
                f"escalated ở revision {state['revision']} "
                f"vì {len(state.get('findings', []))} finding(s)"
            )
        ],
    }
