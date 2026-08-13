"""Gắn `skill_tag` cho câu hỏi — lát B của `AI-ENGINEERING-PLAN`.

Chạy NGOÀI LUỒNG phục vụ, y như `backfill_audio`, và vì cùng lý do: API không
được phép gọi model lúc có request. Hàng đợi cũng là một **truy vấn** — "câu nào
chưa có nhãn" — nên không có bảng job, không có trạng thái thử lại, và chạy lại
chỉ đơn giản là tìm thấy ít việc hơn.

Vòng thử lại nằm ở ĐÂY chứ không nằm trong gateway, nên **mỗi lượt gọi HTTP là
một hàng trong sổ cái**. Cách khác — gộp cả lượt hỏng lẫn lượt thành công vào
một hàng — làm chi phí của một hàng không còn tương ứng với một lượt gọi, và
đó là thứ khiến "một câu tốn bao nhiêu" trở nên khó cộng. Đổi lại, cột
`ai_interaction.retries` hiện chưa ai ghi vào; tỉ lệ phải thử lại tính được từ
số hàng `status='error'` của cùng `feature`.

    uv run python -m app.content.enrich_skills --dry-run
    uv run python -m app.content.enrich_skills --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Question, QuestionSet
from app.models.labels import QuestionLabel, QuestionSetLabel
from app.services.ai_features import resolver_for
from app.services.labels import Facet, codes_for, facets_for
from app.services.llm.base import (
    LLMError,
    LLMQuotaExhausted,
    LLMRequest,
    LLMResult,
    Provider,
)
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.router import Tier

FEATURE = "enrich_label"


@dataclass(slots=True)
class Outcome:
    facet: str
    code: str | None
    reason: str
    attempts: int


def _describe(question: Question) -> str:
    """Dựng phần mô tả câu hỏi cho prompt.

    Part 1 và 2 không in đề lẫn đáp án — đó là sự thật của đề thi, không phải dữ
    liệu thiếu. Nói thẳng điều đó cho model, vì bỏ trống sẽ khiến nó tưởng nội
    dung bị mất và đoán bừa.
    """
    lines = [f"Part {question.part}."]

    # NGỮ CẢNH DÙNG CHUNG nằm ở `question_set`, không ở câu hỏi (ADR-001 §A4.2,
    # §A4.3): part 3 và 4 treo lời thoại ở set, part 6 và 7 treo đoạn văn ở đó.
    # Bỏ qua nó thì model phải phân loại một câu Part 7 mà không có bài đọc —
    # "người viết ngụ ý gì" trở thành câu hỏi không thể trả lời, và câu trả lời
    # duy nhất còn lại là đoán theo số part. Nhãn khi ấy không mịn hơn `part`,
    # tức là nó không thêm gì cho thứ nó sinh ra để làm.
    group = question.question_set
    if group is not None:
        if group.title:
            lines.append(f"Nhóm câu hỏi: {group.title}")
        if group.audio_script:
            lines.append(
                f"Lời thoại của cả nhóm: {json.dumps(group.audio_script, ensure_ascii=False)}"
            )
        for index, passage in enumerate((group.passage, group.passage_2, group.passage_3), 1):
            if passage:
                lines.append(f"Đoạn văn {index}: {passage}")

    if question.prompt_text:
        lines.append(f"Đề bài: {question.prompt_text}")
    else:
        lines.append("Đề bài: (không in ra — phần này chỉ đọc bằng audio)")
    if question.audio_script:
        lines.append(f"Lời thoại: {json.dumps(question.audio_script, ensure_ascii=False)}")
    options = sorted(question.options, key=lambda o: o.label)
    if any(o.content for o in options):
        for opt in options:
            mark = " ← đáp án đúng" if opt.is_correct else ""
            lines.append(f"  {opt.label}. {opt.content}{mark}")
    else:
        correct = next((o.label for o in options if o.is_correct), "?")
        lines.append(f"  (các phương án chỉ đọc bằng audio; đáp án đúng là {correct})")
    if question.explanation:
        lines.append(f"Giải thích sẵn có: {question.explanation}")
    return "\n".join(lines)


def classify(gateway: Gateway, facet: Facet, part: int, described: str, tier: Tier) -> Outcome:
    """Gắn nhãn cho ĐÚNG MỘT mặt.

    Một lượt gọi một mặt, không gộp cả sáu vào một lượt. Gộp lại rẻ hơn về số
    lượt gọi nhưng khiến cả sáu mặt cùng sai khi model lạc một chỗ, và khiến
    việc thử lại phải làm lại toàn bộ thay vì đúng mặt hỏng. Nó cũng làm mất
    khả năng thu hẹp danh sách lựa chọn theo từng mặt — thứ giữ cho model không
    chọn `GRAMMAR_NOUN` cho một câu Part 3.
    """
    prompt = load("label_facet")
    allowed = codes_for(facet.key, part)
    menu = "\n".join(f"- {x.code}: {x.label_vi}" for x in allowed)
    system = prompt.render(facet_name=facet.label_vi, menu=menu)
    valid = {x.code for x in allowed}
    correction = ""

    for attempt in (1, 2):
        try:
            result = _with_backoff(
                lambda: gateway.run(
                    LLMRequest(system=system, user=described + correction, max_tokens=300),
                    feature=FEATURE,
                    tier=tier,
                    prompt_version=prompt.version,
                )
            )
        except LLMQuotaExhausted:
            raise
        except LLMError as exc:
            return Outcome(facet.key, None, f"gọi hỏng: {exc}", attempt)

        code, reason, problem = _parse(result.text, valid)
        if problem is None and code is not None:
            return Outcome(facet.key, code, reason, attempt)
        correction = (
            f"\n\nLần trước bạn trả lời không hợp lệ ({problem}). Chỉ trả về JSON đúng dạng."
        )
    return Outcome(facet.key, None, f"không hợp lệ sau 2 lần: {problem}", 2)


def _parse(text: str, valid: set[str]) -> tuple[str | None, str, str | None]:
    """Bóc JSON, rồi kiểm mã có nằm trong tập ĐÃ THU HẸP THEO PART không.

    Kiểm thứ hai mới quan trọng: `GRAMMAR_NOUN` là mã có thật, đúng kiểu chuỗi,
    và vẫn sai nếu câu đang xét thuộc Part 6 — Part 6 chỉ có năm điểm ngữ pháp.
    Nhận nó vào nghĩa là thống kê mọc thêm một nhóm cho thứ đề thi không kiểm.
    """
    body = text.strip()
    if body.startswith("```"):
        body = body.split("```")[1].removeprefix("json").strip()
    try:
        data = json.loads(body)
    except ValueError:
        return None, "", "không phải JSON"
    if not isinstance(data, dict):
        return None, "", "JSON không phải object"
    code = str(data.get("code", ""))
    reason = str(data.get("ly_do", ""))
    if code not in valid:
        return None, reason, f"mã {code!r} không hợp lệ với mặt/part này"
    return code, reason, None


def pending(session: Session, limit: int | None) -> list[Question]:
    """Hàng đợi vẫn là một TRUY VẤN: câu nào còn thiếu ít nhất một mặt.

    Không bảng job, không trạng thái retry — chạy lại chỉ tìm thấy ít việc hơn.
    Lọc thô ở SQL (chưa có nhãn nào, hoặc chưa đủ số mặt của part) rồi lọc tinh
    ở Python, vì "đủ mặt hay chưa" phụ thuộc part và bộ nhãn nằm trong mã.
    """
    stmt = (
        select(Question)
        .options(selectinload(Question.options), joinedload(Question.question_set))
        .order_by(Question.part, Question.id)
    )
    rows = list(session.scalars(stmt))
    have: dict[uuid.UUID, set[str]] = {}
    for question_id, facet in session.execute(
        select(QuestionLabel.question_id, QuestionLabel.facet)
    ):
        have.setdefault(question_id, set()).add(str(facet))

    todo = [
        q for q in rows if {f.key for f in facets_for(q.part, "question")} - have.get(q.id, set())
    ]
    return todo[:limit] if limit is not None else todo


def pending_sets(session: Session, limit: int | None = None) -> list[QuestionSet]:
    """Nhóm câu hỏi còn thiếu mặt ngữ liệu chung.

    Tách khỏi `pending` vì đây là một ĐƠN VỊ CÔNG VIỆC KHÁC: chủ đề của một hội
    thoại Part 3 được gắn một lần cho cả nhóm, không phải ba lần cho ba câu.
    """
    groups = list(session.scalars(select(QuestionSet)))
    have: dict[uuid.UUID, set[str]] = {}
    for set_id, facet in session.execute(select(QuestionSetLabel.set_id, QuestionSetLabel.facet)):
        have.setdefault(set_id, set()).add(str(facet))
    return [g for g in groups if {f.key for f in facets_for(g.part, "set")} - have.get(g.id, set())]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gắn skill_tag cho câu hỏi chưa có")
    parser.add_argument("--dry-run", action="store_true", help="in ra, không ghi")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tier", choices=["t1", "t2"], default="t2")
    args = parser.parse_args(argv)

    routes = {
        Tier.CHEAP: _split(settings.llm_tier_cheap),
        Tier.STRONG: _split(settings.llm_tier_strong),
    }
    try:
        providers = _providers_for({provider for provider, _ in routes.values()})
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    from app.core.ai_budget import Budget
    from app.core.redis_client import get_redis

    session = SessionLocal()
    try:
        gateway = Gateway(
            providers=providers,
            routes=routes,
            budget=Budget(limit_micro=settings.ai_daily_budget_micro_usd),
            redis_client=get_redis(),
            session_factory=SessionLocal,
            # Cấu hình theo tính năng ở `/admin/ai/providers` GHI ĐÈ bảng tầng.
            # Không nối dòng này thì màn cấu hình lưu được, hiện ra được, và
            # không ảnh hưởng gì tới thứ thật sự chạy — kiểu hỏng tệ nhất, vì
            # mọi thứ trông như đang hoạt động.
            resolve_feature=resolver_for(session),
        )
        tier = Tier(args.tier)
        tally: dict[str, int] = {}
        failures = 0

        groups = pending_sets(session, args.limit)
        questions = pending(session, args.limit)
        print(f"{len(groups)} nhóm và {len(questions)} câu còn thiếu nhãn.\n")

        try:
            for group in groups:
                described = _describe_set(group)
                for facet in facets_for(group.part, "set"):
                    if session.get(QuestionSetLabel, (group.id, facet.key)) is not None:
                        continue
                    outcome = classify(gateway, facet, group.part, described, tier)
                    if outcome.code is None:
                        failures += 1
                        print(f"  nhóm part {group.part}  ✗  {facet.key}: {outcome.reason}")
                        continue
                    tally[outcome.code] = tally.get(outcome.code, 0) + 1
                    print(f"  nhóm part {group.part}  →  {facet.key}: {outcome.code}")
                    if not args.dry_run:
                        session.add(
                            QuestionSetLabel(
                                set_id=group.id,
                                facet=facet.key,
                                code=outcome.code,
                                proposed_code=outcome.code,
                            )
                        )
                        session.commit()

            for question in questions:
                described = _describe(question)
                for facet in facets_for(question.part, "question"):
                    if session.get(QuestionLabel, (question.id, facet.key)) is not None:
                        continue
                    outcome = classify(gateway, facet, question.part, described, tier)
                    if outcome.code is None:
                        failures += 1
                        print(f"  part {question.part}  ✗  {facet.key}: {outcome.reason}")
                        continue
                    tally[outcome.code] = tally.get(outcome.code, 0) + 1
                    mark = "(thử lại)" if outcome.attempts > 1 else ""
                    print(f"  part {question.part}  →  {facet.key}: {outcome.code} {mark}")
                    if not args.dry_run:
                        session.add(
                            QuestionLabel(
                                question_id=question.id,
                                facet=facet.key,
                                code=outcome.code,
                                # Giữ nhãn MÁY đề xuất — cột duy nhất khiến KPI
                                # độ đúng tính được sau khi người duyệt sửa tay.
                                proposed_code=outcome.code,
                            )
                        )
                        # Ghi từng nhãn, không gom về cuối: một lượt 200 câu là
                        # hàng chục phút, và gom lại thì một lần ngắt cuốn theo
                        # toàn bộ việc đã làm.
                        session.commit()
        except LLMQuotaExhausted as exc:
            # DỪNG cả lượt chạy: hạn mức đã cạn thì mọi nhãn còn lại cũng hỏng y
            # hệt, và chạy tiếp chỉ tạo một bức tường lỗi giống nhau che mất
            # dòng nói lên nguyên nhân. Việc đã ghi vẫn còn nguyên.
            print(f"\nDỪNG: {exc}", file=sys.stderr)

        print(f"\nphân bố: {dict(sorted(tally.items(), key=lambda kv: -kv[1]))}")
        print(f"hỏng: {failures}")
        if args.dry_run:
            print("(dry-run — chưa ghi gì)")
    finally:
        session.close()
    return 0


def _describe_set(group: QuestionSet) -> str:
    lines = [f"Nhóm câu hỏi Part {group.part}."]
    if group.title:
        lines.append(f"Tiêu đề: {group.title}")
    if group.audio_script:
        lines.append(f"Lời thoại: {json.dumps(group.audio_script, ensure_ascii=False)}")
    for index, passage in enumerate((group.passage, group.passage_2, group.passage_3), 1):
        if passage:
            lines.append(f"Đoạn văn {index}: {passage}")
    return "\n".join(lines)


def _with_backoff(call: Callable[[], LLMResult], *, tries: int = 4) -> LLMResult:
    """Lùi rồi thử lại khi nhà cung cấp báo quá tải TẠM THỜI.

    `LLMQuotaExhausted` không đi qua đây — hạn mức ngày không hết đi trong ba
    mươi giây, và thử lại chỉ làm lượt chạy hỏng lâu hơn để hỏng. Lỗi 400 do
    prompt sai cũng vậy.
    """
    delay = 4.0
    last: LLMError | None = None
    for attempt in range(tries):
        try:
            return call()
        except LLMQuotaExhausted:
            raise
        except LLMError as exc:
            if not any(code in str(exc) for code in ("429", "500", "502", "503", "504")):
                raise
            last = exc
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
    raise last if last is not None else LLMError("hết lượt thử")


def _providers_for(names: set[str]) -> dict[str, Provider]:
    """Chỉ dựng adapter cho nhà cung cấp thật sự được cấu hình.

    Dựng hết rồi mới chọn sẽ bắt phải có khoá của MỌI nhà cung cấp mới chạy
    được — kể cả nhà cung cấp lượt chạy này không dùng tới.
    """
    built: dict[str, Provider] = {}
    for name in names:
        if name == "ollama":
            from app.services.llm.ollama import OllamaProvider

            built[name] = OllamaProvider(settings.ollama_base_url)
        elif name == "openrouter":
            from app.services.llm.openrouter import OpenRouterProvider

            if not settings.openrouter_api_key:
                raise RuntimeError("Thiếu OPENROUTER_API_KEY. Đặt vào .env ở gốc repo.")
            built[name] = OpenRouterProvider(settings.openrouter_api_key)
        else:
            raise RuntimeError(f"Chưa có adapter cho nhà cung cấp {name!r}")
    return built


def _split(value: str) -> tuple[str, str]:
    provider, _, model = value.partition("/")
    return provider, model


if __name__ == "__main__":
    raise SystemExit(main())
