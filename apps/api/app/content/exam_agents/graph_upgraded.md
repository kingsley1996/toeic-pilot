# TOEIC Pilot — Production-Grade LangGraph Graph

> BẢN CHÍNH của vòng per-slot (`graph.py` cũ đã đổi tên thành
> `graph_legacy.py`). Code chạy thực tế nằm ở package `upgraded/`
> (`state/findings/write/validate/evaluate/verdict/assemble/runner`),
> `graph_upgraded.py` chỉ là shim re-export. Phần "Source" cuối file này là
> bản copy lúc tách module — đọc code thật ở `upgraded/`, đừng đọc copy.

Bản nâng cấp trực tiếp từ graph write → check → critic → write. File chạy thực tế nằm ở `graph_upgraded.py`.

## Thay đổi chính

- Structured `Finding` thay cho `problems: list[str>`.
- `RevisionPlan` thay cho `fix_hint` tự do; vẫn adapter về `fix_hint` để tương thích writer.
- Tách structural check / existing content checker / LLM evaluator / verdict.
- Phân biệt LLM/infrastructure failure với content failure.
- Detect persistent findings và regression.
- Artifact version metadata + content hash.
- Checkpointer được inject; mặc định `InMemorySaver` để chạy ngay.
- Retry policy có `max_same_error` và `max_regressions`.
- CLI giữ tương thích với flow cũ và thêm `--revisions`.

## Source

```python
"""Production-grade LangGraph graph cho MỘT ô của pipeline sinh đề TOEIC.

Kiến trúc:

    START
      ↓
    write
      ↓
    structural_check   (deterministic, miễn phí)
      ↓
    content_check      (check_blueprint hiện có, miễn phí)
      ↓
    evaluate           (LLM judge, chỉ khi cần)
      ↓
    verdict
      ├── accept
      ├── revision_plan
      │       ↓
      │      write
      └── escalate

Các nguyên tắc:
- Giữ nguyên writer/checker hiện có thay vì nhân bản business logic.
- LLM không quyết định toàn bộ workflow; routing do code quyết định.
- Findings có cấu trúc thay cho problems/fix_hint là chuỗi tự do.
- Transport failure và content failure được tách biệt.
- Revision có trần và phát hiện lỗi lặp/regression.
- Artifact được version hóa; state giữ metadata để trace.
- Checkpointer được INJECT từ bên ngoài. Mặc định vẫn dùng InMemorySaver
  để chạy ngay mà không cần thêm dependency; production có thể truyền
  Postgres/SQLite checkpointer vào build().
- Không yêu cầu thay đổi các API hiện có của writer/checker.

Chạy:

    uv run python -m app.content.exam_agents.graph \
        --slug tp-form-08 \
        [--model provider/model] \
        [--limit N] \
        [--part N] \
        [--revisions 3] \
        [--max-tokens N] \
        [--tier cheap|strong] \
        [--verify]

Nếu muốn persistence production, truyền checkpointer vào build():

    graph = build(..., checkpointer=my_checkpointer)

State được thiết kế để có thể checkpoint/replay, còn filesystem vẫn là
artifact store tương thích với pipeline hiện tại.
"""

from __future__ import annotations

import hashlib
import operator
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal

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


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _finding_key(finding: Finding) -> tuple[str, str]:
    return (
        finding.get("code", ""),
        finding.get("location", ""),
    )


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Finding] = []

    for finding in findings:
        key = (
            finding.get("code", ""),
            finding.get("location", ""),
            finding.get("message", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)

    return out


def _problems_to_findings(
    problems: list[str],
    *,
    category: FindingCategory = "logic",
) -> list[Finding]:
    """Adapter từ SlotReport.problems cũ sang structured findings."""

    return [
        {
            "code": "CHECKER_PROBLEM",
            "severity": "error",
            "category": category,
            "location": "slot",
            "message": problem,
            "suggested_fix": problem,
        }
        for problem in problems
    ]


def _flags_to_findings(flags: list[str]) -> list[Finding]:
    return [
        {
            "code": "CHECKER_FLAG",
            "severity": "warning",
            "category": "logic",
            "location": "slot",
            "message": flag,
        }
        for flag in flags
    ]


def _diff_findings(
    previous: list[Finding],
    current: list[Finding],
) -> tuple[list[Finding], list[Finding], list[Finding]]:
    """Return fixed, new, persistent findings.

    So sánh theo code + location, vì message có thể thay đổi giữa các vòng.
    """

    previous_map = {_finding_key(f): f for f in previous}
    current_map = {_finding_key(f): f for f in current}

    fixed = [finding for key, finding in previous_map.items() if key not in current_map]
    new = [finding for key, finding in current_map.items() if key not in previous_map]
    persistent = [finding for key, finding in current_map.items() if key in previous_map]

    return fixed, new, persistent


def _same_error_count(
    previous: list[Finding],
    current: list[Finding],
) -> int:
    previous_keys = {_finding_key(f) for f in previous}
    return sum(1 for finding in current if _finding_key(finding) in previous_keys)


def _merge_reports(mine: list[Any]) -> Any | None:
    """Gộp report từng câu của MỘT slot thành verdict cho cả slot.

    Một Part 3/4 có thể có nhiều report. Slot chỉ sạch khi TẤT CẢ câu sạch.
    """

    if not mine:
        return None

    from app.content.exam.check import SlotReport

    return SlotReport(
        slot_id=mine[0].slot_id,
        number=mine[0].number,
        blocked=any(bool(r.blocked) for r in mine),
        problems=list(dict.fromkeys(p for report in mine for p in report.problems)),
        flags=list(dict.fromkeys(flag for report in mine for flag in report.flags)),
    )


# ---------------------------------------------------------------------------
# Blueprint index
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Node: WRITE
# ---------------------------------------------------------------------------


def _revision_prompt_adapter(plan: RevisionPlan | None) -> str | None:
    """Chuyển RevisionPlan thành fix_hint để tương thích writer hiện có."""

    if not plan:
        return None

    changes = plan.get("changes", [])
    preserve = plan.get("preserve", [])

    lines: list[str] = []

    if plan.get("summary"):
        lines.append(f"Mục tiêu sửa: {plan['summary']}")

    if changes:
        lines.append("Phải sửa:")
        lines.extend(f"- {change}" for change in changes)

    if preserve:
        lines.append("Phải giữ nguyên:")
        lines.extend(f"- {item}" for item in preserve)

    return "\n".join(lines)[:1200] or None


def _write_node(
    gateway: Gateway,
    tier: Tier,
    workdir: Path,
    parts: _Parts,
    max_tokens: int | None = DEFAULT_MAX_TOKENS,
) -> Node:
    """Generate/re-generate slot.

    Writer vẫn là business logic hiện có. Graph chỉ điều phối và đưa revision
    context vào writer.
    """

    def write(state: SlotState) -> NodeUpdate:
        from app.content.exam.writer import GRAPHIC_MARKER, split_all, split_photo
        from app.services.llm.base import LLMError, LLMQuotaExhausted

        slot = parts.slot(state["slot_id"])
        part = parts.part(state["slot_id"])

        revision = state.get("revision", 0) + 1
        plan = state.get("revision_plan")
        hint = _revision_prompt_adapter(plan)

        metrics = dict(state.get("metrics", {}))
        metrics["revisions"] = revision
        metrics["llm_calls"] = metrics.get("llm_calls", 0) + 1

        update: NodeUpdate = {
            "revision": revision,
            "part": part,
            "status": "writing",
            "blocked": False,
            "fatal": False,
            "findings": [],
            "previous_findings": state.get("findings", []),
            "fix_hint": hint,
            "metrics": metrics,
        }

        started = perf_counter()

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
            # Đây là run-level failure. Không giả vờ rằng revision có thể cứu quota.
            raise

        except LLMError as failure:
            # Transport/model failure sau khi with_backoff đã thử đủ lần.
            # Không đưa vào critic loop.
            update |= {
                "draft": "",
                "blocked": True,
                "fatal": True,
                "outcome": "escalated",
                "status": "escalated",
                "findings": [
                    {
                        "code": "LLM_ERROR",
                        "severity": "error",
                        "category": "infrastructure",
                        "location": "write",
                        "message": str(failure),
                    }
                ],
                "log": [f"vòng {revision}: LLM error: {failure}"],
            }
            return update

        except MissingBlock as cut:
            # Đây là content-generation failure: có thể thử revision.
            update |= {
                "draft": "",
                "blocked": True,
                "fatal": False,
                "findings": [
                    {
                        "code": "MISSING_BLOCK",
                        "severity": "error",
                        "category": "structure",
                        "location": "slot",
                        "message": str(cut),
                        "suggested_fix": (
                            "Viết ngắn hơn, đi thẳng vào block và không bỏ dở "
                            "ở giữa nội dung bắt buộc."
                        ),
                    }
                ],
                "fix_hint": ("Bị cắt giữa phần suy luận — viết ngắn hơn, đi thẳng vào khối."),
                "log": [f"vòng {revision}: {cut}"],
            }
            return update

        elapsed_ms = (perf_counter() - started) * 1000
        metrics["latency_ms"] = metrics.get("latency_ms", 0.0) + elapsed_ms

        # Persist artifact immediately, giống pipeline cũ.
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

        artifact: ArtifactVersion = {
            "revision": revision,
            "path": str(workdir),
            "content_hash": _content_hash(block),
            "created_at": _now_iso(),
            "status": "draft",
        }

        return {
            "draft": block,
            "blocked": False,
            "fatal": False,
            "status": "validating",
            "outcome": "pending",
            "findings": [],
            "revision_plan": None,
            "fix_hint": None,
            "artifacts": state.get("artifacts", []) + [artifact],
            "metrics": metrics,
            "log": [f"vòng {revision}: write xong ({elapsed_ms / 1000:.1f}s)"],
        }

    return write


# ---------------------------------------------------------------------------
# Node: STRUCTURAL CHECK
# ---------------------------------------------------------------------------


def _structural_check_node(
    parts: _Parts,
) -> Node:
    """Structural checks rẻ và deterministic trước checker/model."""

    def check(state: SlotState) -> NodeUpdate:
        if state.get("fatal"):
            return {}

        draft = state.get("draft", "")
        findings: list[Finding] = []

        if not draft.strip():
            findings.append(
                {
                    "code": "EMPTY_DRAFT",
                    "severity": "error",
                    "category": "structure",
                    "location": "slot",
                    "message": "Draft rỗng.",
                }
            )

        # Đây là sanity check tối thiểu; parser chính vẫn thuộc check_blueprint.
        # Không cố tái tạo parser của pipeline ở đây.
        if draft and "[QUESTION]" not in draft:
            # Một số loại slot có format riêng, nên đây chỉ là warning.
            findings.append(
                {
                    "code": "QUESTION_MARKER_MISSING",
                    "severity": "warning",
                    "category": "structure",
                    "location": "slot",
                    "message": "Không tìm thấy [QUESTION]; parser chính sẽ quyết định.",
                }
            )

        return {
            "findings": _dedupe_findings(findings),
            "status": "validating",
            "metrics": {
                **state.get("metrics", {}),
                "structural_failures": (
                    state.get("metrics", {}).get("structural_failures", 0)
                    + sum(f["severity"] == "error" for f in findings)
                ),
            },
            "log": [
                f"vòng {state['revision']}: structural "
                f"{'fail' if any(f['severity'] == 'error' for f in findings) else 'pass'}"
            ],
        }

    return check


# ---------------------------------------------------------------------------
# Node: CONTENT CHECK
# ---------------------------------------------------------------------------


def _content_check_node(
    blueprint: Blueprint,
    workdir: Path,
    parts: _Parts,
    verifier: Gateway | None = None,
    tier: Tier = Tier.CHEAP,
    verify_all: bool = False,
) -> Node:
    """Dùng checker hiện có làm source of truth cho validation pipeline.

    Tầng free chạy trước. Paid verification chỉ chạy khi free check sạch.
    """

    def check(state: SlotState) -> NodeUpdate:
        if state.get("fatal"):
            return {}

        from app.content.exam.check import check_blueprint

        slot_id = state["slot_id"]
        part = parts.part(slot_id)

        reports = check_blueprint(
            blueprint,
            workdir,
            gateway=None,
            only=part,
            quiet=True,
        )

        report = _merge_reports([r for r in reports if r.slot_id == slot_id])

        # Nếu structural validator đã có error, vẫn chạy parser/checker để
        # giữ source-of-truth hiện có, nhưng không trả tiền cho evaluator.
        if report is None:
            finding_list = [
                {
                    "code": "CHECK_NOT_FOUND",
                    "severity": "error",
                    "category": "structure",
                    "location": "slot",
                    "message": "check không đọc được ô này.",
                }
            ]
            return {
                "blocked": True,
                "findings": finding_list,
                "metrics": {
                    **state.get("metrics", {}),
                    "content_failures": (state.get("metrics", {}).get("content_failures", 0) + 1),
                },
                "log": [f"vòng {state['revision']}: check không đọc được ô này"],
            }

        checker_findings = _problems_to_findings(report.problems)
        flag_findings = _flags_to_findings(report.flags)

        findings = _dedupe_findings(
            [
                *state.get("findings", []),
                *checker_findings,
            ]
        )

        # Paid verifier chỉ chạy khi free layer sạch.
        wants_paid = verify_all or bool(parts.slot(slot_id).graphic)

        if not report.problems and verifier is not None and wants_paid:
            paid = check_blueprint(
                blueprint,
                workdir,
                gateway=verifier,
                tier=tier,
                ambiguity=True,
                only=part,
                quiet=True,
                slot_id=slot_id,
            )

            pmine = [r for r in paid if r.slot_id == slot_id]

            if pmine:
                paid_report = _merge_reports(pmine)

                if paid_report is not None:
                    findings = _dedupe_findings(
                        [
                            *findings,
                            *_problems_to_findings(paid_report.problems),
                        ]
                    )
                    flag_findings.extend(_flags_to_findings(paid_report.flags))

        blocked = any(finding.get("severity") == "error" for finding in findings)

        previous = state.get("previous_findings", [])
        fixed, new, persistent = _diff_findings(previous, findings)

        repeated = _same_error_count(previous, findings)

        metrics = dict(state.get("metrics", {}))
        metrics["content_failures"] = metrics.get("content_failures", 0) + int(blocked)
        metrics["regressions"] = metrics.get("regressions", 0) + int(bool(new and fixed))

        summary = (
            "; ".join(
                finding.get("message", "")
                for finding in findings
                if finding.get("severity") == "error"
            )
            or "sạch"
        )

        if blocked and state["revision"] < state.get("max_revisions", MAX_REVISIONS):
            print(
                f"      ↻ vòng {state['revision']}: {summary[:160]}",
                flush=True,
            )

        return {
            "blocked": blocked,
            "findings": findings,
            "fixed_findings": fixed,
            "new_findings": new,
            "persistent_findings": persistent,
            "repeated_error_count": repeated,
            "regression_count": metrics["regressions"],
            "flags": list(
                dict.fromkeys(
                    [
                        *state.get("flags", []),
                        *report.flags,
                        *[f.get("message", "") for f in flag_findings],
                    ]
                )
            ),
            "metrics": metrics,
            "status": "evaluating" if not blocked else "revising",
            "log": [f"vòng {state['revision']}: {summary}"],
        }

    return check


# ---------------------------------------------------------------------------
# Node: LLM EVALUATOR / REVISION PLANNER
# ---------------------------------------------------------------------------


def _evaluator_node(
    gateway: Gateway,
    tier: Tier,
) -> Node:
    """LLM judge.

    Model CHẤM chứ không rewrite. Kết quả được chuyển thành revision plan.
    """

    def evaluate(state: SlotState) -> NodeUpdate:
        findings = state.get("findings", [])

        # Không cần tốn model nếu deterministic checker đã phát hiện lỗi
        # cấu trúc rõ ràng và không có nội dung để đánh giá.
        if not state.get("draft"):
            return {}

        error_findings = [finding for finding in findings if finding.get("severity") == "error"]

        user = (
            "Bạn là evaluator cho nội dung TOEIC.\n\n"
            "Nhiệm vụ: CHỈ đánh giá, KHÔNG viết lại item.\n"
            "Hãy xác định lỗi nào cần sửa để lượt writer tiếp theo sửa đúng.\n\n"
            "Các lỗi hiện tại:\n"
            + "\n".join(
                f"- [{f.get('code')}] {f.get('location')}: {f.get('message')}"
                for f in error_findings
            )
            + "\n\n--- DRAFT ---\n"
            + state["draft"]
            + "\n\n"
            "Trả lời ngắn gọn theo cấu trúc:\n"
            "SUMMARY:\n"
            "CHANGES:\n"
            "- ...\n"
            "PRESERVE:\n"
            "- ...\n"
            "RISK: low|medium|high\n"
        )

        started = perf_counter()

        result = with_backoff(
            lambda: gateway.run(
                LLMRequest(
                    system=exam_prompt("critic").render(),
                    user=user,
                    max_tokens=EVALUATOR_MAX_TOKENS,
                    temperature=0.0,
                ),
                feature="exam_verify",
                tier=tier,
            ),
            tries=RETRY_TRIES,
            delay=RETRY_DELAY,
        )

        elapsed_ms = (perf_counter() - started) * 1000

        text = result.text.strip()

        plan = _parse_revision_plan(
            text=text,
            findings=error_findings,
        )

        metrics = dict(state.get("metrics", {}))
        metrics["evaluator_calls"] = metrics.get("evaluator_calls", 0) + 1
        metrics["llm_calls"] = metrics.get("llm_calls", 0) + 1
        metrics["latency_ms"] = metrics.get("latency_ms", 0.0) + elapsed_ms

        return {
            "revision_plan": plan,
            "fix_hint": _revision_prompt_adapter(plan),
            "status": "revising",
            "metrics": metrics,
            "log": [f"vòng {state['revision']}: evaluator xong ({elapsed_ms / 1000:.1f}s)"],
        }

    return evaluate


def _parse_revision_plan(
    *,
    text: str,
    findings: list[Finding],
) -> RevisionPlan:
    """Parse output evaluator theo format nhẹ.

    Không ép dependency parser mới. Nếu model trả format không hoàn hảo,
    findings vẫn đủ để writer có context và workflow không bị chết.
    """

    summary = ""
    changes: list[str] = []
    preserve: list[str] = []
    risk: Literal["low", "medium", "high"] = "medium"

    section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        upper = line.upper()

        if upper.startswith("SUMMARY:"):
            section = "summary"
            summary = line.split(":", 1)[1].strip()
            continue

        if upper.startswith("CHANGES:"):
            section = "changes"
            continue

        if upper.startswith("PRESERVE:"):
            section = "preserve"
            continue

        if upper.startswith("RISK:"):
            value = line.split(":", 1)[1].strip().lower()
            risk = value if value in {"low", "medium", "high"} else "medium"
            continue

        if line.startswith("-"):
            value = line[1:].strip()
            if section == "changes":
                changes.append(value)
            elif section == "preserve":
                preserve.append(value)

    if not summary:
        summary = "Sửa các lỗi quality findings hiện tại."

    if not changes:
        changes = [
            finding.get("suggested_fix") or finding.get("message") or "Sửa finding tương ứng."
            for finding in findings
        ]

    if not preserve:
        preserve = [
            "Giữ correct answer nếu finding không yêu cầu đổi đáp án.",
            "Giữ intent và format TOEIC của slot.",
        ]

    return {
        "summary": summary[:800],
        "findings": findings,
        "changes": changes[:10],
        "preserve": preserve[:10],
        "risk": risk,
        "should_regenerate": True,
    }


# ---------------------------------------------------------------------------
# Verdict / routing
# ---------------------------------------------------------------------------


def _verdict_node(policy: RetryPolicy) -> Node:
    def verdict(state: SlotState) -> NodeUpdate:
        if state.get("fatal"):
            return {
                "status": "escalated",
                "outcome": "escalated",
            }

        findings = state.get("findings", [])
        errors = [finding for finding in findings if finding.get("severity") == "error"]

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
                "log": ["Escalate: cùng finding lặp quá ngưỡng."],
            }

        if state.get("regression_count", 0) > policy.max_regressions:
            return {
                "status": "escalated",
                "outcome": "escalated",
                "log": ["Escalate: revision tạo regression liên tiếp."],
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
    if state.get("revision_plan", {}).get("should_regenerate", True):
        return "write"

    return "escalate"


# ---------------------------------------------------------------------------
# Terminal nodes
# ---------------------------------------------------------------------------


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
        "log": [f"accepted ở revision {state['revision']}"],
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


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_pending(
    gateway: Gateway,
    tier: Tier,
    blueprint: Blueprint,
    workdir: Path,
    limit: int | None = None,
    only: int | None = None,
    max_tokens: int | None = DEFAULT_MAX_TOKENS,
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

    wanted = {slot.id for slot in pending(blueprint, workdir)} | set(retry or ())

    slots = [slot for part in blueprint.parts for slot in part.slots if slot.id in wanted]

    if only is not None:
        slots = [slot for slot in slots if parts_of(blueprint, slot.id) == only]

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
                f"      … {label} vẫn đang chạy ({perf_counter() - since:.0f}s)",
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
                f"  ✓ [{done}/{total}] {slot.id} → {outcome} ({perf_counter() - started:.0f}s)",
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
                            f"      ✗ [{finding.get('code')}] {finding.get('message')}",
                            flush=True,
                        )

            for flag in final.get("flags", []):
                print(
                    f"      ⚠ {flag}",
                    flush=True,
                )

        elapsed = perf_counter() - run_started
        left = (elapsed / done) * (total - done) if done else 0.0

        tail = f" · còn {total - done} ô, ước {left / 60:.0f} phút" if done < total else ""

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


# ---------------------------------------------------------------------------
# Helpers / CLI
# ---------------------------------------------------------------------------


def parts_of(
    blueprint: Blueprint,
    slot_id: str,
) -> int:
    for part in blueprint.parts:
        if any(slot.id == slot_id for slot in part.slots):
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
        description=("Production-grade vòng write → validate → evaluate → revise.")
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
        help=("trần output mỗi lượt viết; nếu bỏ qua, writer tự chọn theo part/slot"),
    )

    parser.add_argument(
        "--tier",
        default="cheap",
        choices=["cheap", "strong"],
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help=("bật paid checker/evaluator cho slot sạch ở tầng deterministic"),
    )

    args = parser.parse_args(argv)

    if args.revisions < 1:
        parser.error("--revisions phải >= 1")

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
        verify_all=args.verify,
        max_revisions=args.revisions,
    )

    accepted = sum(1 for _, outcome in results if outcome == "accepted")

    escalated = sum(1 for _, outcome in results if outcome == "escalated")

    print(
        f"\n{len(results)} ô · "
        f"{accepted} nhận · "
        f"{escalated} giao người "
        f"(tối đa {args.revisions} revision)"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
