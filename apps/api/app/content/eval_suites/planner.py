"""Suite planner — đo lớp chọn của planner bằng FakeProvider, không gọi model."""

from __future__ import annotations

import json
from typing import Any, cast

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content.eval_core import CaseFailure, EvalError, SuiteReport, _prompt_version
from app.core.ai_budget import Budget
from app.models.grammar import GrammarLesson, GrammarTopic
from app.services.llm.base import LLMError
from app.services.llm.fake import FakeProvider
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier
from app.services.planner_llm import llm_select


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
            try:
                items = llm_select(
                    gateway,
                    session,
                    weak=weak,
                    budget=budget,
                    target_score=None,
                    exam_date=None,
                    raw_summary="eval",
                )
            except LLMError:
                # Lỗi gọi ở suite là None (đường fallback đã ghi sổ) — suite đo
                # lớp CHỌN, không đo provider.
                items = None
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


class _NoRedis:
    """Redis giả cho eval offline — chạm vào là lỗi TO, không phải treo.

    `llm_select` không truyền user_id nên budget không bao giờ chạm Redis ở
    suite planner. Dùng client thật ở đây sẽ lặng lẽ KẾT NỐI được ở máy có
    Redis chạy (như CI) và hỏng ở máy không có — đúng loại test chập chờn theo
    môi trường (§11).
    """

    def __getattr__(self, name: str) -> Any:
        raise EvalError(f"eval offline gọi Redis.{name} — đường này phải chạy không Redis")
