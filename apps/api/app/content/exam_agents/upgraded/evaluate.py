"""Node evaluate: LLM judge + parse RevisionPlan + adapter ra fix_hint.

Model CHẤM chứ không rewrite. `_revision_prompt_adapter` sống ở đây (nó là
sản phẩm của revision planning); node `write` nhập về để đưa vào writer cũ.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Literal

from app.content.exam.prompts._registry import exam_prompt
from app.content.exam_agents.upgraded.state import (
    EVALUATOR_MAX_TOKENS,
    RETRY_DELAY,
    RETRY_TRIES,
    Finding,
    Node,
    NodeUpdate,
    RevisionPlan,
    SlotState,
)
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier


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
            # Cắt như critic cũ (4000 ký tự): draft P3/P4 nguyên văn vừa tốn
            # input vừa làm evaluator sa đà vào văn bản thay vì lỗi.
            + "\n\n--- DRAFT ---\n"
            + state["draft"][:4000]
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

        metrics: dict[str, Any] = dict(state.get("metrics", {}))
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
            if value == "low":
                risk = "low"
            elif value == "high":
                risk = "high"
            else:
                risk = "medium"
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
