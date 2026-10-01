"""State + policy cho graph upgraded: types dùng chung mọi node.

Không nhập gì trong package ngoài blueprint (kiểu) — module lá, mọi module
khác nhập từ đây nên nó không được nhập ngược lại bất cứ module nào.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

from app.content.exam.blueprint import Blueprint, QuestionSlot

# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

MAX_REVISIONS = 3
RETRY_TRIES = 7
RETRY_DELAY = 6.0

# Writer cần nhiều token hơn phần text nhìn thấy vì model có thể dùng token
# cho reasoning. Giữ None để writer tự quyết định theo part/slot.
DEFAULT_MAX_TOKENS: int | None = None

EVALUATOR_MAX_TOKENS = 4000

FindingSeverity = Literal["error", "warning", "info"]
FindingCategory = Literal[
    "structure",
    "grammar",
    "vocabulary",
    "logic",
    "distractor",
    "paraphrase",
    "difficulty",
    "source",
    "infrastructure",
]


class Finding(TypedDict, total=False):
    """Một finding chuẩn hóa xuyên suốt workflow.

    Dict thay vì Pydantic model để state dễ serialize/checkpoint và không
    phụ thuộc version cụ thể của LangGraph serializer.
    """

    code: str
    severity: FindingSeverity
    category: FindingCategory
    location: str
    message: str
    evidence: str
    expected: str
    suggested_fix: str


class RevisionPlan(TypedDict, total=False):
    summary: str
    findings: list[Finding]
    changes: list[str]
    preserve: list[str]
    risk: Literal["low", "medium", "high"]
    should_regenerate: bool


class ArtifactVersion(TypedDict, total=False):
    revision: int
    path: str
    content_hash: str
    created_at: str
    status: Literal["draft", "validated", "accepted", "escalated"]


class RunMetrics(TypedDict, total=False):
    llm_calls: int
    evaluator_calls: int
    revisions: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost: float
    structural_failures: int
    content_failures: int
    regressions: int


class SlotState(TypedDict, total=False):
    """State của một slot.

    LangGraph merge theo từng key. `log` dùng reducer để tích lũy qua các vòng.
    """

    slot_id: str
    part: int

    draft: str

    # Verdict hiện tại.
    blocked: bool
    fatal: bool
    outcome: str
    status: str

    # Structured quality findings.
    findings: list[Finding]
    previous_findings: list[Finding]
    fixed_findings: list[Finding]
    new_findings: list[Finding]
    persistent_findings: list[Finding]

    # LLM revision planning.
    revision_plan: RevisionPlan | None

    # Compatibility field: writer hiện có nhận fix_hint.
    # RevisionPlan là source of truth; fix_hint chỉ là adapter.
    fix_hint: str | None

    # Retry state.
    revision: int
    max_revisions: int
    repeated_error_count: int
    regression_count: int

    # Artifact history.
    artifacts: list[ArtifactVersion]

    # Non-blocking flags từ checker.
    flags: list[str]

    # Metrics/tracing.
    metrics: RunMetrics

    # Human-readable execution history.
    log: Annotated[list[str], operator.add]


NodeUpdate = dict[str, Any]
Node = Callable[[SlotState], NodeUpdate]


@dataclass(frozen=True)
class RetryPolicy:
    """Policy cho content revision, không phải network retry."""

    max_revisions: int = MAX_REVISIONS
    max_same_error: int = 2
    max_regressions: int = 1


class _Parts:
    """Tra slot + part theo id một lần cho cả lượt chạy."""

    def __init__(self, blueprint: Blueprint) -> None:
        self.by_id: dict[str, tuple[QuestionSlot, int]] = {}
        for part in blueprint.parts:
            for slot in part.slots:
                self.by_id[slot.id] = (slot, part.part)

    def slot(self, slot_id: str) -> QuestionSlot:
        return self.by_id[slot_id][0]

    def part(self, slot_id: str) -> int:
        return self.by_id[slot_id][1]
