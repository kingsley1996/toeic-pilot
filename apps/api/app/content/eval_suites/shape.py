"""Suite shape — cổng dạng của dòng giải thích backfill."""

from __future__ import annotations

from typing import Any

from app.content.backfill_explanations import check_shape
from app.content.eval_core import CaseFailure, SuiteReport, _prompt_version, _verdict


def _shape_code(detail: str) -> str:
    if detail.startswith("tưởng rớt mà đạt"):
        return "expectation_mismatch"
    if "rớt sai chỗ" in detail:
        return "wrong_failure_location"
    if "trả về rỗng" in detail:
        return "empty_output"
    if "xuống dòng" in detail:
        return "line_break"
    if "đoạn, cần đúng" in detail:
        return "segment_count"
    if "đoạn căn cứ" in detail:
        return "letter_in_evidence"
    if "phải mở đầu" in detail:
        return "wrong_segment_order"
    if detail.startswith("tưởng"):
        return "expectation_mismatch"
    return "unknown"


def eval_shape(cases: list[dict[str, Any]]) -> SuiteReport:
    report = SuiteReport(name="shape", version=_prompt_version("backfill_explanation"))
    for case in cases:
        cid = str(case.get("id", "?"))
        report.total += 1
        raw_labels = case.get("labels", [])
        if not isinstance(raw_labels, list):
            report.failures.append(CaseFailure(cid, "labels phải là mảng", "dataset"))
            continue
        problem = check_shape(str(case.get("text", "")), [str(x) for x in raw_labels])
        subs = [str(case["expect_problem"])] if case.get("expect_problem") else []
        actual = [problem] if problem else []
        failure = _verdict(cid, bool(case.get("expect_pass", True)), subs, actual)
        if failure is None:
            report.passed += 1
        else:
            failure.code = _shape_code(failure.detail)
            report.failures.append(failure)
    return report
