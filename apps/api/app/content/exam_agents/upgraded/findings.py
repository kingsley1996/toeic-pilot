"""Findings helpers: chuẩn hóa, khử trùng, diff qua các vòng, adapter.

Thuần hàm, không gọi LLM, không đọc đĩa — chỉ biến đổi dữ liệu. Node nào
cũng dùng nên nằm riêng để `write`/`validate`/`evaluate` không nhập nhau.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.content.exam_agents.upgraded.state import Finding, FindingCategory


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

    fixed = [
        finding
        for key, finding in previous_map.items()
        if key not in current_map
    ]
    new = [
        finding
        for key, finding in current_map.items()
        if key not in previous_map
    ]
    persistent = [
        finding
        for key, finding in current_map.items()
        if key in previous_map
    ]

    return fixed, new, persistent


def _same_error_count(
    previous: list[Finding],
    current: list[Finding],
) -> int:
    previous_keys = {_finding_key(f) for f in previous}
    return sum(
        1
        for finding in current
        if _finding_key(finding) in previous_keys
    )


def _merge_reports(mine: list[Any]) -> Any | None:
    """Gộp report từng câu của MỘT slot thành verdict cho cả slot.

    Một Part 3/4 có thể có nhiều report. Slot chỉ sạch khi TẤT CẢ câu sạch.
    """

    if not mine:
        return None

    from app.content.exam.check import SlotReport

    # KHÔNG truyền blocked: nó là property suy từ problems (check.py:81),
    # truyền vào là TypeError và content_check chết ở slot đầu tiên.
    return SlotReport(
        slot_id=mine[0].slot_id,
        number=mine[0].number,
        problems=list(
            dict.fromkeys(
                p
                for report in mine
                for p in report.problems
            )
        ),
        flags=list(
            dict.fromkeys(
                flag
                for report in mine
                for flag in report.flags
            )
        ),
    )
