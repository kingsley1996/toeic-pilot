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
import hashlib
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content.backfill_explanations import check_shape
from app.core.ai_budget import Budget
from app.core.config import _API_DIR
from app.models import Question, QuestionOption
from app.models.grammar import GrammarLesson, GrammarTopic
from app.services import embeddings
from app.services.coach import CoachContext, check_output, describe, parse_output
from app.services.embeddings import EmbeddingUnavailable
from app.services.knowledge import search_knowledge, sync_knowledge
from app.services.llm.base import LLMRequest
from app.services.llm.fake import FakeProvider
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.retry import with_backoff as _with_backoff
from app.services.llm.router import Tier
from app.services.planner_llm import llm_select

EVAL_DIR = _API_DIR / "eval"
DATASETS = EVAL_DIR / "datasets"
KB_DIR = _API_DIR / "content" / "kb"

SUITES = ("coach", "shape", "retrieval", "planner")


class EvalError(RuntimeError):
    """Case hay cấu hình hỏng — lỗi của người viết eval, không phải của hệ thống."""


# Case hỏng vì dataset viết sai KHÁC system hỏng vì sản phẩm sai. Gộp hai thứ
# thì một case viết hỏng trông như regression của model (§2.3).
FailureKind = Literal["dataset", "system", "judge", "infrastructure"]


@dataclass(slots=True)
class CaseFailure:
    id: str
    detail: str
    kind: FailureKind = "system"


@dataclass(slots=True)
class SuiteReport:
    name: str
    passed: int = 0
    total: int = 0
    failures: list[CaseFailure] = field(default_factory=list)
    version: str = ""
    # Dòng tóm tắt metric riêng của suite (vd recall/MRR) — in kèm, không chặn.
    summary: str = ""
    # Số máy đọc được, để so baseline (§4): {"recall": 1.0, "mrr": 0.92}.
    metrics: dict[str, float] = field(default_factory=dict)


def load_cases(path: Path, required: set[str]) -> list[dict[str, Any]]:
    """Đọc JSONL, mỗi dòng một case. Hỏng ở dòng nào thì nói đúng dòng đó."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvalError(f"không đọc được {path}: {exc}") from exc
    cases: list[dict[str, Any]] = []
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except ValueError as exc:
            raise EvalError(f"{path}:{lineno}: không phải JSON ({exc})") from exc
        if not isinstance(data, dict):
            raise EvalError(f"{path}:{lineno}: mỗi dòng phải là một object")
        missing = required - set(data)
        if missing:
            raise EvalError(f"{path}:{lineno}: thiếu {sorted(missing)}")
        cases.append(data)
    if not cases:
        raise EvalError(f"{path}: không có case nào")
    return cases


def _verdict(
    cid: str, expect_pass: bool, expect_subs: list[str], actual: list[str]
) -> CaseFailure | None:
    """So kết quả thật với kỳ vọng của case. `None` nghĩa là case đúng như viết."""
    if expect_pass:
        if not actual:
            return None
        return CaseFailure(cid, f"tưởng đạt mà rớt: {'; '.join(actual)}")
    if not actual:
        return CaseFailure(cid, "tưởng rớt mà đạt")
    joined = " ".join(actual)
    missing = [s for s in expect_subs if s not in joined]
    if missing:
        return CaseFailure(cid, f"rớt sai chỗ (thiếu {missing}): {joined}")
    return None


def _prompt_version(name: str) -> str:
    try:
        return load(name).version
    except Exception:  # noqa: BLE001 — mọi lý do đều thành "unknown"
        return "unknown"


def _coach_context(case: dict[str, Any]) -> CoachContext:
    """Dựng ngữ cảnh từ case inline — object transient, không chạm database."""
    raw = case.get("question")
    if not isinstance(raw, dict):
        raise EvalError(f"case {case.get('id', '?')}: question phải là object")
    options = raw.get("options")
    if not isinstance(options, list) or not options:
        raise EvalError(f"case {case.get('id', '?')}: question thiếu options")
    correct_label = str(raw.get("correct", ""))
    built: dict[str, QuestionOption] = {}
    for opt in options:
        if not isinstance(opt, dict):
            raise EvalError(f"case {case.get('id', '?')}: option phải là object")
        built[str(opt.get("label", ""))] = QuestionOption(
            label=str(opt.get("label", "")),
            content=str(opt.get("content") or ""),
            is_correct=str(opt.get("label", "")) == correct_label,
        )
    if correct_label not in built:
        raise EvalError(f"case {case.get('id', '?')}: correct không nằm trong options")
    chosen_label = case.get("chosen")
    chosen = built.get(str(chosen_label)) if chosen_label is not None else None
    if chosen_label is not None and chosen is None:
        raise EvalError(f"case {case.get('id', '?')}: chosen không nằm trong options")
    raw_labels = case.get("labels", {})
    if not isinstance(raw_labels, dict):
        raise EvalError(f"case {case.get('id', '?')}: labels phải là object")
    question = Question(part=int(raw.get("part", 5)), prompt_text=str(raw.get("prompt_text") or ""))
    # Gán options để `describe()` dựng được ngữ cảnh cho judge — check_output
    # không cần tới chúng, nhưng đường judge thì cần.
    question.options = list(built.values())
    return CoachContext(
        question=question,
        chosen=chosen,
        correct=built[correct_label],
        labels={str(k): str(v) for k, v in raw_labels.items()},
        distractor_share=None,
    )


def eval_coach(cases: list[dict[str, Any]]) -> SuiteReport:
    report = SuiteReport(name="coach", version=_prompt_version("coach_explain"))
    for case in cases:
        cid = str(case.get("id", "?"))
        report.total += 1
        try:
            ctx = _coach_context(case)
        except EvalError as exc:
            report.failures.append(CaseFailure(cid, str(exc), "dataset"))
            continue
        reply = case.get("reply")
        text = json.dumps(reply, ensure_ascii=False) if isinstance(reply, dict) else str(reply)
        body, problem = parse_output(text)
        if body is None:
            actual = [problem or "không đọc được"]
        else:
            actual = check_output(body, ctx)
        subs = [str(s) for s in case.get("expect_problems", []) or []]
        failure = _verdict(cid, bool(case.get("expect_pass", True)), subs, actual)
        if failure is None:
            report.passed += 1
        else:
            report.failures.append(failure)
    return report


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
            report.failures.append(failure)
    return report


def _offline_embed(text: str) -> list[float]:
    """Ép đường lexical: suite này đo lexical, vector thuộc về P1."""
    del text
    raise EmbeddingUnavailable("eval offline — chỉ đo lexical")


class _NoRedis:
    """Redis giả cho eval offline — chạm vào là lỗi TO, không phải treo.

    `llm_select` không truyền user_id nên budget không bao giờ chạm Redis ở
    suite planner. Dùng client thật ở đây sẽ lặng lẽ KẾT NỐI được ở máy có
    Redis chạy (như CI) và hỏng ở máy không có — đúng loại test chập chờn theo
    môi trường (§11).
    """

    def __getattr__(self, name: str) -> Any:
        raise EvalError(f"eval offline gọi Redis.{name} — đường này phải chạy không Redis")


def _mean_or_none(xs: list[float]) -> float | None:
    """Trung bình, hoặc None khi không có quan sát nào — không có số liệu
    KHÁC đạt điểm tuyệt đối (§2.2)."""
    return sum(xs) / len(xs) if xs else None


# Top-K của suite retrieval — case đòi nhiều ref hơn số này là case viết hỏng
# (§2.1), không phải retriever hỏng. Đổi số này thì đổi cả dataset.
RETRIEVAL_LIMIT = 4


def eval_retrieval(cases: list[dict[str, Any]], kb_dir: Path) -> SuiteReport:
    """Đồng bộ KB thật vào SQLite memory rồi đo Recall — top-4 phải chứa mọi ref.

    Kèm MRR trung bình để so cấu hình retrieval với nhau (lexical vs vector,
    P1.2): cổng chặn vẫn là recall từng case, MRR chỉ là số so sánh.
    """
    if not kb_dir.is_dir():
        raise EvalError(f"không thấy thư mục KB {kb_dir}")
    engine = create_engine("sqlite:///:memory:")
    from app.core.database import Base

    Base.metadata.tables["knowledge_chunk"].create(engine)
    previous = embeddings.embed_query
    embeddings.embed_query = _offline_embed
    try:
        with Session(engine) as session:
            synced = sync_knowledge(session, kb_dir)
            session.commit()
            version = f"{len(synced.created)} mục"
            report = SuiteReport(name="retrieval", version=version)
            recalls: list[float] = []
            rrs: list[float] = []
            for case in cases:
                cid = str(case.get("id", "?"))
                report.total += 1
                rows = search_knowledge(session, str(case.get("query", "")), limit=RETRIEVAL_LIMIT)
                got = [chunk.ref for _, chunk in rows]
                raw_want = case.get("relevant_refs", [])
                if not isinstance(raw_want, list) or not raw_want:
                    report.failures.append(
                        CaseFailure(cid, "relevant_refs phải là mảng", "dataset")
                    )
                    continue
                want = [str(r) for r in raw_want]
                if len(want) > RETRIEVAL_LIMIT:
                    report.failures.append(
                        CaseFailure(
                            cid,
                            f"đòi {len(want)} ref trong top-{RETRIEVAL_LIMIT} — case viết hỏng",
                            "dataset",
                        )
                    )
                    continue
                ranks = [got.index(r) for r in want if r in got]
                recalls.append(len(ranks) / len(want))
                rrs.append(1 / (min(ranks) + 1) if ranks else 0.0)
                missing = [r for r in want if r not in got]
                if not missing:
                    report.passed += 1
                else:
                    report.failures.append(CaseFailure(cid, f"thiếu {missing}, top-4 là {got}"))
            recall = _mean_or_none(recalls)
            mrr = _mean_or_none(rrs)
            if recall is None or mrr is None:
                report.summary = "recall n/a · MRR n/a"
            else:
                report.summary = f"recall {recall:.2f} · MRR {mrr:.2f}"
                report.metrics = {"recall": recall, "mrr": mrr}
    finally:
        embeddings.embed_query = previous
        engine.dispose()
    return report


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
        return CaseFailure(cid, "weak phải là mảng", "dataset")
    weak: list[tuple[str, int, int]] = []
    for entry in raw_weak:
        if not isinstance(entry, list) or len(entry) != 3:
            return CaseFailure(cid, f"weak entry hỏng: {entry!r}", "dataset")
        code, correct, total = entry
        weak.append((str(code), int(correct), int(total)))
    budget = case.get("budget")
    if not isinstance(budget, int) or isinstance(budget, bool):
        return CaseFailure(cid, "budget phải là số nguyên", "dataset")

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
                return CaseFailure(cid, str(exc), "dataset")
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
                return CaseFailure(cid, f"gọi model thừa ({len(fake.seen)} lượt)")
            if bool(case.get("expect_none", False)):
                if items is not None:
                    return CaseFailure(cid, f"tưởng None mà ra {len(items)} mục")
                return None
            if items is None:
                return CaseFailure(cid, "tưởng có mục mà ra None")
            for item in items:
                if item.kind == "grammar_lesson" and item.ref_id is None:
                    return CaseFailure(cid, f"ref treo ở {item.label}")
            raw_expected = case.get("expected", [])
            if not isinstance(raw_expected, list):
                return CaseFailure(cid, "expected phải là mảng", "dataset")
            want: list[tuple[str, int, str]] = []
            for exp in raw_expected:
                if not isinstance(exp, dict):
                    return CaseFailure(cid, f"expected entry hỏng: {exp!r}", "dataset")
                want.append((str(exp.get("kind")), int(exp.get("part", 0)), str(exp.get("label"))))
            got = [(item.kind, item.part, item.label) for item in items]
            if got != want:
                return CaseFailure(cid, f"chọn sai: được {got}, muốn {want}")
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


JUDGE_FEATURE = "eval_judge"

# Trần rộng tay: model suy luận (Gemini thinking, GLM không tắt được) đốt trần
# vào phần nghĩ trước khi viết — trần bằng cỡ câu trả lời làm nó chết đói giữa
# chừng và trả JSON cụt (đo thật: trần 300 cho ra `{"dat": true, "ly_` rồi dừng).
# Cùng bẫy đã ghi ở `backfill_explanations.MAX_TOKENS` và `CRITIC_MAX_TOKENS`.
# Rộng tay không tốn thêm: tiền tính theo token thật sự sinh ra.
JUDGE_MAX_TOKENS = 4000


def _parse_judge(text: str) -> tuple[bool | None, str]:
    """Đọc verdict của giám khảo. `None` nghĩa là judge nói không rõ ràng."""
    body = text.strip()
    if body.startswith("```"):
        body = body.split("```")[1].removeprefix("json").strip()
    try:
        data = json.loads(body)
    except ValueError:
        return None, "judge không trả JSON"
    if not isinstance(data, dict) or not isinstance(data.get("dat"), bool):
        return None, 'judge thiếu trường "dat" boolean'
    return bool(data["dat"]), str(data.get("ly_do", ""))


def judge_coach(cases: list[dict[str, Any]], gateway: Gateway) -> SuiteReport:
    """Giám khảo chấm lại reply ghi sẵn, so với kỳ vọng của case.

    Không đo model sinh — đo judge: trên case curated, judge phải đồng ý với
    cổng tất định. Bất đồng là tín hiệu hiệu chuẩn (judge sai hoặc case sai),
    không phải tín hiệu bỏ qua.
    """
    prompt = load("judge_coach")
    report = SuiteReport(name="judge-coach", version=prompt.version)
    # Schema khai đầy đủ kiểu + cấm field lạ — model trả thừa/thiếu là hỏng
    # validation, không phải hỏng lặng lẽ (§3). Parser bên dưới vẫn giữ làm
    # lớp phòng thủ thứ hai cho provider không tôn trọng schema.
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"dat": {"type": "boolean"}, "ly_do": {"type": "string"}},
        "required": ["dat", "ly_do"],
        "additionalProperties": False,
    }
    for case in cases:
        cid = str(case.get("id", "?"))
        report.total += 1
        try:
            ctx = _coach_context(case)
        except EvalError as exc:
            report.failures.append(CaseFailure(cid, str(exc), "dataset"))
            continue
        reply = case.get("reply")
        if isinstance(reply, dict):
            reply_text = json.dumps(reply, ensure_ascii=False)
        else:
            reply_text = str(reply)
        try:
            # Thử lại khi quá tải tạm thời (503); hết hạn mức ngày thì
            # `with_backoff` không chạm vào — chờ bao lâu cũng vẫn hỏng.
            # Mỗi lượt thử là một hàng trong sổ cái, đúng luật của gateway.
            result = _with_backoff(
                lambda: gateway.run(
                    LLMRequest(
                        system=prompt.render(described=describe(ctx), reply=reply_text),
                        user="Chấm lời giải trên.",
                        max_tokens=JUDGE_MAX_TOKENS,
                        schema=schema,
                    ),
                    feature=JUDGE_FEATURE,
                    tier=Tier.STRONG,
                    prompt_version=prompt.version,
                )
            )
        except Exception as exc:  # noqa: BLE001 — một case judge hỏng không giết cả lượt
            # Lỗi gọi (timeout, 503, quota, key) là hạ tầng, KHÁC judge chấm sai
            # (§12): sập provider không được đọc thành regression chất lượng.
            report.failures.append(CaseFailure(cid, f"judge gọi hỏng: {exc}", "infrastructure"))
            continue
        verdict, note = _parse_judge(result.text)
        if verdict is None:
            report.failures.append(CaseFailure(cid, note, "judge"))
        elif verdict != bool(case.get("expect_pass", True)):
            report.failures.append(
                CaseFailure(cid, f"judge bất đồng (verdict={verdict}): {note}", "judge")
            )
        else:
            report.passed += 1
    return report


def run_suite(name: str, datasets: Path, kb_dir: Path) -> SuiteReport:
    if name == "coach":
        cases = load_cases(datasets / "coach_explain.jsonl", {"id", "question", "reply"})
        return eval_coach(cases)
    if name == "shape":
        cases = load_cases(datasets / "explanation_shape.jsonl", {"id", "labels", "text"})
        return eval_shape(cases)
    if name == "retrieval":
        cases = load_cases(datasets / "retrieval.jsonl", {"id", "query", "relevant_refs"})
        return eval_retrieval(cases, kb_dir)
    if name == "planner":
        cases = load_cases(datasets / "planner.jsonl", {"id", "weak", "budget"})
        return eval_planner(cases)
    raise EvalError(f"không có suite {name!r} (có: {', '.join(SUITES)})")


def load_thresholds(path: Path) -> dict[str, float]:
    """Ngưỡng chặn theo suite — thiếu entry nghĩa là đòi 100%."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvalError(f"không đọc được {path}: {exc}") from exc
    except ValueError as exc:
        raise EvalError(f"{path}: không phải JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise EvalError(f"{path}: phải là một object")
    out: dict[str, float] = {}
    for key, value in data.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvalError(f"{path}: ngưỡng {key!r} phải là số")
        out[str(key)] = float(value)
    return out


def _git_sha() -> str:
    """SHA ngắn của HEAD — fail-soft vì eval phải chạy được cả ngoài git."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except Exception:  # noqa: BLE001 — mọi lý do đều thành "unknown"
        return "unknown"
    return out.stdout.strip() or "unknown"


def _dataset_hashes(datasets: Path) -> dict[str, str]:
    """SHA256 từng tệp dataset — report nào cũng truy được nó chấm cái gì."""
    hashes: dict[str, str] = {}
    for name in ("coach_explain", "explanation_shape", "retrieval", "planner"):
        path = datasets / f"{name}.jsonl"
        try:
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        except OSError:
            hashes[name] = "missing"
    return hashes


def _report_json(
    reports: list[SuiteReport],
    *,
    against: str | None,
    suite_arg: str,
    floors: dict[str, float],
) -> dict[str, Any]:
    """Report reproducible (§5): đọc report này là biết đã chấm cái gì,
    bằng gì, trên mã nào — không cần hỏi người chạy."""
    return {
        "run": {
            "id": uuid.uuid4().hex[:12],
            "at": datetime.now(UTC).isoformat(),
            "git_sha": _git_sha(),
            "suite_arg": suite_arg,
            "against": against,
            "thresholds": floors,
        },
        "datasets": _dataset_hashes(DATASETS),
        "suites": [
            {
                "name": r.name,
                "version": r.version,
                "summary": r.summary,
                "metrics": r.metrics,
                "passed": r.passed,
                "total": r.total,
                "failures": [{"id": f.id, "kind": f.kind, "detail": f.detail} for f in r.failures],
            }
            for r in reports
        ],
    }


def diff_against(baseline: dict[str, Any], reports: list[SuiteReport]) -> tuple[list[str], bool]:
    """So lượt chạy hiện tại với một report baseline (§4).

    Trả về (các dòng in, có_case_mới_rớt). Case rớt MỚI là regression và chặn;
    case đã hết rớt chỉ là tin tốt để đọc. Delta metric chỉ là số so sánh —
    chặn tuyệt đối vẫn do ngưỡng (--fail-under) quyết.
    """
    raw_suites = baseline.get("suites", [])
    old: dict[str, dict[str, Any]] = (
        {s["name"]: s for s in raw_suites} if isinstance(raw_suites, list) else {}
    )
    lines: list[str] = []
    new_failures = False
    for report in reports:
        prev = old.get(report.name)
        if not isinstance(prev, dict):
            lines.append(f"[{report.name}] chưa có baseline — bỏ qua so sánh")
            continue
        old_ids = {f["id"] for f in prev.get("failures", []) if isinstance(f, dict)}
        new_ids = {f.id for f in report.failures}
        fresh = sorted(new_ids - old_ids)
        fixed = sorted(old_ids - new_ids)
        if fresh:
            new_failures = True
        old_total = int(prev.get("total", 0) or 0)
        old_passed = int(prev.get("passed", 0) or 0)
        line = f"[{report.name}] {old_passed}/{old_total} → {report.passed}/{report.total}"
        old_metrics = prev.get("metrics", {})
        if isinstance(old_metrics, dict) and old_metrics and report.metrics:
            deltas = " · ".join(
                f"{k} {float(old_metrics.get(k, 0.0)):.2f}→{v:.2f}"
                for k, v in sorted(report.metrics.items())
            )
            line += f" · {deltas}"
        if not fresh and not fixed:
            line += " (không đổi)"
        lines.append(line)
        for cid in fresh:
            lines.append(f"  MỚI RỚT: {cid}")
        for cid in fixed:
            lines.append(f"  đã hết rớt: {cid}")
    return lines, new_failures


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvalError(f"không đọc được baseline {path}: {exc}") from exc
    except ValueError as exc:
        raise EvalError(f"baseline {path} không phải JSON ({exc})") from exc
    if not isinstance(data, dict) or "suites" not in data:
        raise EvalError(f"baseline {path} thiếu 'suites'")
    return data


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
    args = parser.parse_args(argv)

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
        print(f"[judge-coach [{report.version}]] {report.passed}/{report.total} đồng ý")
        for failure in report.failures:
            print(f"  bất đồng [{failure.kind}] {failure.id} — {failure.detail}")
        return 1 if report.failures else 0

    names = list(SUITES) if args.suite == "all" else [args.suite]
    try:
        reports = [run_suite(name, args.datasets, args.kb_dir) for name in names]
    except EvalError as exc:
        print(f"eval hỏng: {exc}", file=sys.stderr)
        return 2

    against = f" · đối chiếu: {args.against}" if args.against else ""
    print(f"eval AI{against}")
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
                _report_json(reports, against=args.against, suite_arg=args.suite, floors=floors),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    print(f"TỔNG: {sum(r.passed for r in reports)}/{sum(r.total for r in reports)} đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
