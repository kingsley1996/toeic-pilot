"""Suite coach + judge — đo lời giải thích câu làm sai và người chấm nó."""

from __future__ import annotations

import json
from typing import Any

from app.content.eval_core import CaseFailure, EvalError, SuiteReport, _prompt_version, _verdict
from app.models import Question, QuestionOption
from app.services.coach import CoachContext, check_output, describe, parse_output
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.retry import with_backoff as _with_backoff
from app.services.llm.router import Tier

JUDGE_FEATURE = "eval_judge"

# Trần rộng tay: model suy luận (Gemini thinking, GLM không tắt được) đốt trần
# vào phần nghĩ trước khi viết — trần bằng cỡ câu trả lời làm nó chết đói giữa
# chừng và trả JSON cụt (đo thật: trần 300 cho ra `{"dat": true, "ly_` rồi dừng).
# Cùng bẫy đã ghi ở `backfill_explanations.MAX_TOKENS` và `CRITIC_MAX_TOKENS`.
# Rộng tay không tốn thêm: tiền tính theo token thật sự sinh ra.
JUDGE_MAX_TOKENS = 4000


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


def _coach_code(detail: str) -> str:
    """Mã hoá lỗi coach từ chuỗi assert. "Tưởng rớt mà đạt" thuần (không vấn đề
    nào) là lỗi kỳ vọng; còn lại đọc vấn đề cụ thể kể cả sau tiền tố "tưởng đạt"."""
    if detail.startswith("tưởng rớt mà đạt"):
        return "expectation_mismatch"
    if "rớt sai chỗ" in detail:
        return "wrong_failure_location"
    if "chữ cái đáp án đúng" in detail:
        return "wrong_correct_answer"
    if "phương án đã chọn" in detail:
        return "missing_distractor_ref"
    if "tiếng Việt" in detail:
        return "wrong_language"
    if "giảng về" in detail:
        return "wrong_grammar_point"
    if "thiếu trường" in detail:
        return "missing_field"
    if "không phải JSON" in detail or "không đọc được" in detail:
        return "invalid_output"
    if "dài " in detail:
        return "bad_length"
    if detail.startswith("tưởng"):
        return "expectation_mismatch"
    return "unknown"


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
            failure.code = _coach_code(failure.detail)
            report.failures.append(failure)
    return report


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
    matrix = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    extra_attempts = [0]
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
        tries = [0]

        def _call() -> Any:
            tries[0] += 1
            return gateway.run(
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

        try:
            # Thử lại khi quá tải tạm thời (503); hết hạn mức ngày thì
            # `with_backoff` không chạm vào — chờ bao lâu cũng vẫn hỏng.
            # Mỗi lượt thử là một hàng trong sổ cái, đúng luật của gateway.
            result = _with_backoff(_call)
        except Exception as exc:  # noqa: BLE001 — một case judge hỏng không giết cả lượt
            # Lỗi gọi (timeout, 503, quota, key) là hạ tầng, KHÁC judge chấm sai
            # (§12): sập provider không được đọc thành regression chất lượng.
            report.failures.append(
                CaseFailure(cid, f"judge gọi hỏng: {exc}", "infrastructure", "provider_error")
            )
            continue
        extra_attempts[0] += max(0, tries[0] - 1)
        verdict, note = _parse_judge(result.text)
        if verdict is None:
            report.failures.append(CaseFailure(cid, note, "judge", "judge_unparseable"))
            continue
        expected = bool(case.get("expect_pass", True))
        # Ma trận hiệu chuẩn judge (§8): đo JUDGE so với kỳ vọng curated, không
        # phải đo chất lượng app — FP/FN ở đây là judge sai, không phải model sai.
        if verdict and expected:
            matrix["tp"] += 1
        elif verdict and not expected:
            matrix["fp"] += 1
        elif not verdict and expected:
            matrix["fn"] += 1
        else:
            matrix["tn"] += 1
        if verdict != expected:
            report.failures.append(
                CaseFailure(
                    cid, f"judge bất đồng (verdict={verdict}): {note}", "judge", "judge_disagree"
                )
            )
        else:
            report.passed += 1
    judged = matrix["tp"] + matrix["fp"] + matrix["fn"] + matrix["tn"]
    if judged:
        prec = matrix["tp"] / (matrix["tp"] + matrix["fp"]) if matrix["tp"] + matrix["fp"] else 0.0
        rec = matrix["tp"] / (matrix["tp"] + matrix["fn"]) if matrix["tp"] + matrix["fn"] else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        report.metrics = {
            "agreement": (matrix["tp"] + matrix["tn"]) / judged,
            "judge_precision": prec,
            "judge_recall": rec,
            "judge_f1": f1,
        }
        report.summary = (
            f"đồng ý {(matrix['tp'] + matrix['tn']) / judged:.0%} "
            f"(TP{matrix['tp']}/FP{matrix['fp']}/FN{matrix['fn']}/TN{matrix['tn']})"
        )
    if extra_attempts[0]:
        # Chất lượng ổn mà thử lại tăng là tín hiệu vận hành, không phải tín hiệu
        # chất lượng (§13): tách hai số này ngay ở tóm tắt.
        sep = " · " if report.summary else ""
        report.summary += f"{sep}thử lại {extra_attempts[0]} lượt"
    return report
