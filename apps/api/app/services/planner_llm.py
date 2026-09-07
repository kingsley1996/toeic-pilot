"""Planner V2 — LLM chọn từ danh sách ứng viên, có gác cổng (SPEC §5).

Khuôn UC4 của AI-PLAN: model CHỌN và SẮP THỨ TỪ từ danh sách đã tra ra; tầng
ghi từ chối tham chiếu treo. Đầu ra không đạt schema → thử lại một lần → vẫn
hỏng thì trả `None`, nơi gọi rơi về planner V1 (rule) — một kế hoạch rule tốt
hơn một kế hoạch LLM bịa nội dung.

Model không thấy câu hỏi, đáp án hay chữ ký của người học: chỉ thấy tỉ lệ đúng
theo kỹ năng và danh sách ứng viên — dữ liệu tổng hợp, không phải dữ liệu thô.
"""

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GrammarLesson, GrammarTopic
from app.services.labels import Label
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.router import Tier
from app.services.study_planner import DraftItem

FEATURE = "study_plan"
PROMPT = load("plan_select")
# Trần 1200 từng bị cắt đúng chỗ; 2500 vẫn thiếu vì glm-5.3-flash là model
# SUY LUẬN — 8k ký tự nghĩ trước khi trả lời, hết hạn mức ở pha nghĩ. Trần
# phải gánh cả pha suy luận của model mạnh: 12k.
MAX_TOKENS = 12000
MIN_PICKS = 2
MAX_PICKS = 8


@dataclass(frozen=True, slots=True)
class Candidate:
    """Một ứng viên trình bày cho model — id là chuỗi ngắn, tự biết nghĩa."""

    id: str
    kind: str
    ref_id: uuid.UUID | None
    part: int
    label: str
    detail: str


def candidates_for(
    db: Session,
    weak: list[tuple[str, int, int]],
    budget: int,
) -> list[Candidate]:
    """Danh sách ứng viên TỪ các điểm yếu đã đo — không ứng viên ngoài điểm
    yếu, và không ứng viên trỏ nội dung không tồn tại (N4)."""
    out: list[Candidate] = []
    seen_parts: set[int] = set()
    for code, correct, count in weak:
        label = weak_code_label(code)
        if label is None:
            continue
        if code.startswith("GRAMMAR_"):
            topic = db.scalar(
                select(GrammarTopic).where(
                    GrammarTopic.code == code, GrammarTopic.status == "published"
                )
            )
            if topic is None:
                continue
            lesson = db.scalar(
                select(GrammarLesson)
                .where(GrammarLesson.topic_id == topic.id, GrammarLesson.status == "published")
                .order_by(GrammarLesson.position)
                .limit(1)
            )
            if lesson is None:
                continue
            out.append(
                Candidate(
                    id=f"g{len(out) + 1}",
                    kind="grammar_lesson",
                    ref_id=lesson.id,
                    part=5,
                    label=f"Ôn {topic.title}",
                    detail=f"chủ đề '{topic.title}', bạn đúng {correct}/{count} câu ở kỹ năng này",
                )
            )
            continue
        part = label.parts[0] if label.parts else None
        if part is None or part in seen_parts:
            continue
        seen_parts.add(part)
        out.append(
            Candidate(
                id=f"p{len(out) + 1}",
                kind="part_drill",
                ref_id=None,
                part=part,
                label=f"Luyện Part {part}",
                detail=f"part {part}, bạn đúng {correct}/{count} câu ở dạng '{label.label_vi}'",
            )
        )
        if len(out) >= budget * 2:
            break
    return out


def weak_code_label(code: str) -> "Label | None":
    """Tra registry nhãn — trả `Label` của `services.labels` hoặc None."""
    from app.services.labels import LABELS

    return LABELS.get(code)


def llm_select(
    gateway: Gateway,
    db: Session,
    *,
    weak: list[tuple[str, int, int]],
    budget: int,
    target_score: int | None,
    exam_date: object,
    raw_summary: str,
) -> list[DraftItem] | None:
    """Chạy model và trả danh sách mục đã kiểm. `None` = không dùng được, nơi
    gọi rơi về rule. Đảm bảo: mọi ref trỏ nội dung trong danh sách ứng viên."""
    candidates = candidates_for(db, weak, budget)
    if len(candidates) < MIN_PICKS:
        return None

    listing = "\n".join(
        f"- candidate_id: {c.id} | {c.kind} | {c.label} | {c.detail}" for c in candidates
    )
    goal = f"điểm mục tiêu {target_score}" if target_score else "chưa đặt điểm mục tiêu"
    deadline = f"ngày thi {exam_date}" if exam_date else "chưa có ngày thi"
    system = PROMPT.text
    user = PROMPT.render(candidates=listing, goal=goal, deadline=deadline, summary=raw_summary)
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "reason"],
                },
            }
        },
        "required": ["items"],
    }
    try:
        result = gateway.run(
            LLMRequest(
                system=system,
                user=user,
                max_tokens=MAX_TOKENS,
                schema=schema,
            ),
            feature=FEATURE,
            tier=Tier.STRONG,
            prompt_version=PROMPT.version,
        )
        picks = json.loads(result.text)["items"]
    except Exception:
        return None

    by_id = {c.id: c for c in candidates}
    items: list[DraftItem] = []
    seen_refs: set[object] = set()
    for pick in picks[: min(MAX_PICKS, budget)]:
        candidate = by_id.get(str(pick.get("id", "")))
        if candidate is None:
            continue
        # part_drill có ref_id=None — khoá chống trùng phải là part của nó,
        # không phải None (hai part_drill đều None thì khoá None nuốt cả hai).
        key: object = candidate.ref_id if candidate.ref_id is not None else candidate.part
        if key in seen_refs:
            continue
        seen_refs.add(key)
        items.append(
            DraftItem(
                kind=candidate.kind,
                part=candidate.part,
                ref_id=candidate.ref_id,
                label=candidate.label,
                reason=str(pick.get("reason", ""))[:300] or None,
            )
        )
    return items or None
