"""Bộ eval AI — một tệp case + một lệnh chạy (guides §7–§10, AI-PRODUCTION-PLAN P0).

Chạy OFFLINE, không mạng, không khoá API: chỉ L1 (schema) + L2 (tất định).
Suite `retrieval` dựng SQLite memory từ chính `content/kb/*.md` rồi ép đường
lexical (stub `embed_query`), nên nó đồng thời chứng minh đường rơi vector→lexical.

L3 (giám khảo LLM) thuộc lát sau — flag `--judge` ở đây mới chỉ giữ cổng
"judge phải khác model sinh": gọi live mà trùng model thì từ chối ngay.

    uv run python -m app.content.eval_ai --suite all
    uv run python -m app.content.eval_ai --suite coach --against 'coach_explain@abc123'
    uv run python -m app.content.eval_ai --suite retrieval --report eval/reports/latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.content.eval_core import (
    EvalError,
    SuiteReport,
    _manifest_status,
    _report_json,
    diff_against,
    load_baseline,
    load_cases,
    load_thresholds,
    write_manifest,
)
from app.content.eval_suites.coach import eval_coach, judge_coach
from app.content.eval_suites.exam import eval_exam
from app.content.eval_suites.planner import eval_planner
from app.content.eval_suites.retrieval import eval_retrieval
from app.content.eval_suites.shape import eval_shape
from app.core.config import _API_DIR

EVAL_DIR = _API_DIR / "eval"
DATASETS = EVAL_DIR / "datasets"
KB_DIR = _API_DIR / "content" / "kb"

SUITES = ("coach", "shape", "retrieval", "planner", "exam")


def run_suite(
    name: str, datasets: Path, kb_dir: Path, retrieval_mode: str = "lexical"
) -> SuiteReport:
    if name == "coach":
        cases = load_cases(datasets / "coach_explain.jsonl", {"id", "question", "reply"})
        return eval_coach(cases)
    if name == "shape":
        cases = load_cases(datasets / "explanation_shape.jsonl", {"id", "labels", "text"})
        return eval_shape(cases)
    if name == "retrieval":
        cases = load_cases(datasets / "retrieval.jsonl", {"id", "query", "relevant_refs"})
        return eval_retrieval(cases, kb_dir, retrieval_mode)
    if name == "planner":
        cases = load_cases(datasets / "planner.jsonl", {"id", "weak", "budget"})
        return eval_planner(cases)
    if name == "exam":
        cases = load_cases(datasets / "exam_slots.jsonl", {"id", "part", "paste", "expect_blocked"})
        return eval_exam(cases)
    raise EvalError(f"không có suite {name!r} (có: {', '.join(SUITES)})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bộ eval AI offline (L1+L2, không mạng)")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="all")
    parser.add_argument("--datasets", type=Path, default=DATASETS)
    parser.add_argument("--kb-dir", type=Path, default=KB_DIR)
    parser.add_argument("--against", default=None, help="nhãn lần chạy, vd prompt version")
    parser.add_argument("--report", type=Path, default=None, help="ghi tóm tắt JSON")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="report baseline để so hồi quy: case MỚI RỚT là chặn (§4)",
    )
    parser.add_argument(
        "--fail-under",
        action="store_true",
        help="chặn theo eval/thresholds.json thay vì chặn mọi case rớt (chế độ CI)",
    )
    parser.add_argument("--judge", default=None, help="model giám khảo, dạng provider/model")
    parser.add_argument("--gen-model", default=None, help="model đã sinh (để kiểm khác judge)")
    parser.add_argument(
        "--retrieval-mode",
        choices=["lexical", "vector"],
        default="lexical",
        help="lexical: offline CI; vector: đường production thật, cần keys",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="ghim hash dataset hiện tại vào manifest rồi thoát",
    )
    args = parser.parse_args(argv)

    if args.write_manifest:
        target = write_manifest(args.datasets)
        print(f"đã ghim manifest: {target}")
        return 0

    if args.judge is not None:
        if args.gen_model is None:
            print("--judge cần --gen-model để kiểm judge khác model sinh.", file=sys.stderr)
            return 2
        if args.judge == args.gen_model:
            print(
                f"từ chối: judge ({args.judge}) trùng model sinh — "
                "model chấm bài của chính nó thì thiên vị.",
                file=sys.stderr,
            )
            return 2
        try:
            from app.content.exam_cli.paths import _gateway

            gateway = _gateway(args.judge)
        except RuntimeError as exc:
            print(f"không dựng được gateway: {exc}", file=sys.stderr)
            return 2
        try:
            cases = load_cases(args.datasets / "coach_explain.jsonl", {"id", "question", "reply"})
        except EvalError as exc:
            print(f"eval hỏng: {exc}", file=sys.stderr)
            return 2
        report = judge_coach(cases, gateway)
        extra = f" · {report.summary}" if report.summary else ""
        print(f"[judge-coach [{report.version}]] {report.passed}/{report.total} đồng ý{extra}")
        for failure in report.failures:
            print(f"  bất đồng [{failure.kind}] {failure.id} — {failure.detail}")
        return 1 if report.failures else 0

    names = list(SUITES) if args.suite == "all" else [args.suite]
    try:
        reports = [
            run_suite(name, args.datasets, args.kb_dir, args.retrieval_mode) for name in names
        ]
    except EvalError as exc:
        print(f"eval hỏng: {exc}", file=sys.stderr)
        return 2

    against = f" · đối chiếu: {args.against}" if args.against else ""
    print(f"eval AI{against}")
    manifest_version, manifest_match = _manifest_status(args.datasets)
    if not manifest_match:
        print(
            f"chú ý: dataset lệch manifest ({manifest_version}) — "
            "chạy --write-manifest sau khi sửa case xong",
            file=sys.stderr,
        )
    failed = 0
    for report in reports:
        at = f" [{report.version}]" if report.version else ""
        extra = f" · {report.summary}" if report.summary else ""
        print(f"[{report.name}{at}] {report.passed}/{report.total} đạt{extra}")
        for failure in report.failures:
            print(f"  rớt [{failure.kind}] {failure.id} — {failure.detail}")
            failed += 1
    floors: dict[str, float] = {}
    if args.fail_under:
        try:
            floors = load_thresholds(EVAL_DIR / "thresholds.json")
        except EvalError as exc:
            print(f"eval hỏng: {exc}", file=sys.stderr)
            return 2
        thin: list[str] = []
        for report in reports:
            floor = floors.get(report.name, 1.0)
            rate = report.passed / report.total if report.total else 1.0
            mark = "qua" if rate >= floor else "TỤT"
            print(f"  ngưỡng {report.name}: {rate:.0%} (cần ≥{floor:.0%}) — {mark}")
            if rate < floor:
                thin.append(report.name)
        if thin:
            print(f"TỤT NGƯỠNG: {', '.join(thin)}", file=sys.stderr)
            return 1
    if args.baseline is not None:
        try:
            baseline = load_baseline(args.baseline)
        except EvalError as exc:
            print(f"eval hỏng: {exc}", file=sys.stderr)
            return 2
        lines, has_new = diff_against(baseline, reports)
        print(f"so với baseline {args.baseline}:")
        for line in lines:
            print(f"  {line}")
        if has_new:
            print("HỒI QUY: có case mới rớt so với baseline", file=sys.stderr)
            return 1
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                _report_json(
                    reports,
                    against=args.against,
                    suite_arg=args.suite,
                    floors=floors,
                    datasets=args.datasets,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    print(f"TỔNG: {sum(r.passed for r in reports)}/{sum(r.total for r in reports)} đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
