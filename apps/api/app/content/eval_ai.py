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
from typing import Any, cast

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content.eval_core import (
    CaseFailure,
    EvalError,
    SuiteReport,
    _manifest_status,
    _prompt_version,
    _report_json,
    diff_against,
    load_baseline,
    load_cases,
    load_thresholds,
    write_manifest,
)
from app.content.eval_suites.coach import eval_coach, judge_coach
from app.content.eval_suites.retrieval import _NoRedis, eval_retrieval
from app.content.eval_suites.shape import eval_shape
from app.core.ai_budget import Budget
from app.core.config import _API_DIR
from app.models.grammar import GrammarLesson, GrammarTopic
from app.services.llm.fake import FakeProvider
from app.services.llm.gateway import Gateway  # planner dời ở commit sau thì gỡ
from app.services.llm.router import Tier
from app.services.planner_llm import llm_select

EVAL_DIR = _API_DIR / "eval"
DATASETS = EVAL_DIR / "datasets"
KB_DIR = _API_DIR / "content" / "kb"

SUITES = ("coach", "shape", "retrieval", "planner")


def _seed_planner(session: Session, seeds: Any) -> None:
    """Gieo chủ đề + 1 bài published mỗi chủ đề — ứng viên mà model được chọn."""
    if not isinstance(seeds, list):
        raise EvalError("seed_topics phải là mảng")
    for index, seed in enumerate(seeds):
        if not isinstance(seed, dict) or "code" not in seed or "title" not in seed:
            raise EvalError(f"seed_topics[{index}] thiếu code/title")
        topic = GrammarTopic(
            code=str(seed["code"]),
            slug=f"eval-{str(seed['code']).lower().replace('_', '-')}",
            title=str(seed["title"]),
            status=str(seed.get("status", "published")),
        )
        session.add(topic)
        session.flush()
        session.add(
            GrammarLesson(
                topic_id=topic.id,
                slug=f"eval-{topic.slug}-bai-1",
                title=f"{topic.title} 1",
                status="published",
            )
        )


def _planner_case(cid: str, case: dict[str, Any]) -> CaseFailure | None:
    """Chạy `llm_select` thật với FakeProvider — đo lớp CHỌN, không đo model."""
    raw_weak = case.get("weak", [])
    if not isinstance(raw_weak, list):
        return CaseFailure(cid, "weak phải là mảng", "dataset", "invalid_weak")
    weak: list[tuple[str, int, int]] = []
    for entry in raw_weak:
        if not isinstance(entry, list) or len(entry) != 3:
            return CaseFailure(cid, f"weak entry hỏng: {entry!r}", "dataset", "invalid_weak")
        code, correct, total = entry
        weak.append((str(code), int(correct), int(total)))
    budget = case.get("budget")
    if not isinstance(budget, int) or isinstance(budget, bool):
        return CaseFailure(cid, "budget phải là số nguyên", "dataset", "invalid_budget")

    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:")
    try:
        for name in ("grammar_topic", "grammar_lesson", "ai_interaction"):
            Base.metadata.tables[name].create(engine)
        with Session(engine) as session:
            try:
                _seed_planner(session, case.get("seed_topics", []))
                session.commit()
            except EvalError as exc:
                return CaseFailure(cid, str(exc), "dataset", "invalid_seed")
            reply = case.get("reply")
            if isinstance(reply, dict):
                text = json.dumps(reply, ensure_ascii=False)
            else:
                text = str(reply or "")
            fake = FakeProvider(reply=text)
            gateway = Gateway(
                providers={"fake": fake},
                # fake-1 có giá 0 trong bảng giá — đúng model cho eval offline.
                routes={Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")},
                budget=Budget(limit_micro=1_000_000_000),
                # Ép offline: chạm Redis là lỗi ngay, không kết nối lặng lẽ.
                redis_client=cast(redis.Redis, _NoRedis()),
                session_factory=lambda: Session(engine),
            )
            items = llm_select(
                gateway,
                session,
                weak=weak,
                budget=budget,
                target_score=None,
                exam_date=None,
                raw_summary="eval",
            )
            if case.get("expect_no_call") and fake.seen:
                return CaseFailure(
                    cid, f"gọi model thừa ({len(fake.seen)} lượt)", "system", "unexpected_call"
                )
            if bool(case.get("expect_none", False)):
                if items is not None:
                    return CaseFailure(
                        cid, f"tưởng None mà ra {len(items)} mục", "system", "unexpected_items"
                    )
                return None
            if items is None:
                return CaseFailure(cid, "tưởng có mục mà ra None", "system", "unexpected_none")
            for item in items:
                if item.kind == "grammar_lesson" and item.ref_id is None:
                    return CaseFailure(
                        cid, f"ref treo ở {item.label}", "system", "dangling_reference"
                    )
            raw_expected = case.get("expected", [])
            if not isinstance(raw_expected, list):
                return CaseFailure(cid, "expected phải là mảng", "dataset", "invalid_expected")
            want: list[tuple[str, int, str]] = []
            for exp in raw_expected:
                if not isinstance(exp, dict):
                    return CaseFailure(
                        cid, f"expected entry hỏng: {exp!r}", "dataset", "invalid_expected"
                    )
                want.append((str(exp.get("kind")), int(exp.get("part", 0)), str(exp.get("label"))))
            got = [(item.kind, item.part, item.label) for item in items]
            if got != want:
                return CaseFailure(
                    cid, f"chọn sai: được {got}, muốn {want}", "system", "wrong_selection"
                )
            return None
    finally:
        engine.dispose()


def eval_planner(cases: list[dict[str, Any]]) -> SuiteReport:
    report = SuiteReport(name="planner", version=_prompt_version("plan_select"))
    for case in cases:
        cid = str(case.get("id", "?"))
        report.total += 1
        failure = _planner_case(cid, case)
        if failure is None:
            report.passed += 1
        else:
            report.failures.append(failure)
    return report


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
