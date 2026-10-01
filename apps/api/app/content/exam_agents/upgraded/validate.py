"""Node validate: structural (deterministic, miễn phí) rồi content check.

Tầng free chạy trước. Paid verification chỉ chạy khi free layer sạch —
thứ tự này là chỗ tiết kiệm, đừng đảo.
"""

from __future__ import annotations

from pathlib import Path

from app.content.exam.blueprint import Blueprint
from app.content.exam_agents.upgraded.findings import (
    _dedupe_findings,
    _diff_findings,
    _flags_to_findings,
    _merge_reports,
    _problems_to_findings,
    _same_error_count,
)
from app.content.exam_agents.upgraded.state import (
    MAX_REVISIONS,
    Finding,
    Node,
    NodeUpdate,
    SlotState,
    _Parts,
)
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier


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


def _content_check_node(
    blueprint: Blueprint,
    workdir: Path,
    parts: _Parts,
    verifier: Gateway | None = None,
    tier: Tier = Tier.CHEAP,
    verify_all: bool = False,
) -> Node:
    """Dùng checker hiện có làm source of truth cho validation pipeline.

    Tầng free chạy trước. Paid verification chỉ chạy khi free layer sạch.
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

        report = _merge_reports(
            [r for r in reports if r.slot_id == slot_id]
        )

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
                    "content_failures": (
                        state.get("metrics", {}).get("content_failures", 0) + 1
                    ),
                },
                "log": [
                    f"vòng {state['revision']}: check không đọc được ô này"
                ],
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
                    flag_findings.extend(
                        _flags_to_findings(paid_report.flags)
                    )

        blocked = any(
            finding.get("severity") == "error"
            for finding in findings
        )

        previous = state.get("previous_findings", [])
        fixed, new, persistent = _diff_findings(previous, findings)

        repeated = _same_error_count(previous, findings)

        metrics = dict(state.get("metrics", {}))
        metrics["content_failures"] = (
            metrics.get("content_failures", 0) + int(blocked)
        )
        metrics["regressions"] = (
            metrics.get("regressions", 0)
            + int(bool(new and fixed))
        )

        summary = (
            "; ".join(
                finding.get("message", "")
                for finding in findings
                if finding.get("severity") == "error"
            )
            or "sạch"
        )

        if blocked and state["revision"] < state.get(
            "max_revisions", MAX_REVISIONS
        ):
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
                        *[
                            f.get("message", "")
                            for f in flag_findings
                        ],
                    ]
                )
            ),
            "metrics": metrics,
            "status": "evaluating" if not blocked else "revising",
            "log": [
                f"vòng {state['revision']}: {summary}"
            ],
        }

    return check
