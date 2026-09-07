"""So sánh planner V1 (rule) và V2 (llm) trên cùng đầu vào — SPEC-PLACEMENT §5.

    uv run python -m app.content.eval_planner --user <uuid>     # một người
    uv run python -m app.content.eval_planner --latest 5        # các lượt gần nhất

Không ghi kế hoạch — chỉ chạy phần CHỌN của hai planner trên cùng dữ liệu yếu
và in bảng đối chiếu: số mục, phủ bao nhiêu % điểm yếu, ref có treo không,
chi phí + độ trễ của đường LLM. Kết quả là thứ quyết định "LLM có đáng không"
(N5: đo trước khi tối ưu), nên nó in ra màn hình thay vì giấu trong DB.
"""

import argparse
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Attempt, GrammarLesson, GrammarTopic, PlacementResult, UserProfile
from app.services.labels import LABELS
from app.services.llm.gateway import Gateway
from app.services.study_planner import DraftItem, budget_for, weak_items


def _rule_select(
    db: Session, attempt: Attempt, weak: list[tuple[str, int, int]], budget: int
) -> list[DraftItem]:
    """Chạy lại logic chọn của V1 — cùng thứ tự ưu tiên, không ghi DB."""
    position = 1
    drilled: set[int] = set()
    items: list[DraftItem] = []
    for code, correct, count in weak:
        if position > budget:
            break
        label = LABELS[code]
        topic = None
        if code.startswith("GRAMMAR_"):
            topic = db.scalar(
                select(GrammarTopic).where(
                    GrammarTopic.code == code, GrammarTopic.status == "published"
                )
            )
        if topic is not None:
            lesson = db.scalar(
                select(GrammarLesson)
                .where(GrammarLesson.topic_id == topic.id, GrammarLesson.status == "published")
                .order_by(GrammarLesson.position)
                .limit(1)
            )
            if lesson is None:
                continue
            items.append(
                DraftItem(
                    kind="grammar_lesson",
                    part=5,
                    ref_id=lesson.id,
                    label=f"Ôn {topic.title}",
                    reason=f"Đúng {correct}/{count} câu ở kỹ năng này",
                )
            )
            position += 1
            continue
        part = label.parts[0] if label.parts else None
        if part is not None and part not in drilled:
            drilled.add(part)
            items.append(
                DraftItem(
                    kind="part_drill",
                    part=part,
                    ref_id=None,
                    label=f"Luyện Part {part}",
                    reason=f"Yếu dạng '{label.label_vi}' — đúng {correct}/{count} câu",
                )
            )
            position += 1
    return items


def _coverage(rule_items: list[DraftItem], llm_items: list[DraftItem]) -> float:
    """V2 phủ bao nhiêu phần trăm mục V1 (theo nội dung, không theo thứ tự)."""
    if not rule_items:
        return 1.0
    rule_keys = {(i.kind, i.label) for i in rule_items}
    llm_keys = {(i.kind, i.label) for i in llm_items}
    return len(rule_keys & llm_keys) / len(rule_keys)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", help="uuid người học; bỏ thì lấy các lượt gần nhất")
    parser.add_argument("--latest", type=int, default=3, help="số lượt gần nhất (mặc định 3)")
    args = parser.parse_args(argv)

    from app.api.deps import get_gateway

    with SessionLocal() as db:
        query = (
            select(Attempt)
            .join(PlacementResult, PlacementResult.attempt_id == Attempt.id)
            .where(PlacementResult.estimator_version != "pending")
        )
        if args.user:
            query = query.where(Attempt.user_id == uuid.UUID(args.user))
        attempts = list(
            db.scalars(query.order_by(PlacementResult.created_at.desc()).limit(args.latest))
        )
        if not attempts:
            print("Không có lượt placement nào đã phân tích.")
            return 1

        gateway: Gateway = get_gateway(db)
        for attempt in attempts:
            weak = weak_items(db, attempt)
            profile = db.get(UserProfile, attempt.user_id)
            today = datetime.now(UTC).date()
            budget = budget_for(today, profile.exam_date if profile else None)
            print(
                f"\n=== lượt {str(attempt.id)[:8]}… | điểm yếu: {len(weak)} | trần {budget} mục ==="
            )

            rule_items = _rule_select(db, attempt, weak, budget)
            print(f"V1 rule: {len(rule_items)} mục — {[i.label for i in rule_items]}")

            started = datetime.now(UTC)
            llm_items = None
            note = ""
            try:
                from app.services.planner_llm import llm_select

                llm_items = llm_select(
                    gateway,
                    db,
                    weak=weak,
                    budget=budget,
                    target_score=profile.target_score if profile else None,
                    exam_date=profile.exam_date if profile else None,
                    raw_summary=f"Nghe {attempt.listening_raw}/42, Đọc {attempt.reading_raw}/42",
                )
            except Exception as exc:  # noqa: BLE001 — báo cáo, không chết giữa chừng
                note = f" ({exc})"
            latency = (datetime.now(UTC) - started).total_seconds()
            if llm_items is None:
                print(f"V2 llm : KHÔNG dùng được{note} — {latency:.1f}s")
                continue
            dangling = [i for i in llm_items if i.kind == "grammar_lesson" and i.ref_id is None]
            print(f"V2 llm : {len(llm_items)} mục — {[i.label for i in llm_items]}")
            print(
                f"  phủ {(_coverage(rule_items, llm_items) * 100):.0f}% mục V1 | "
                f"ref treo: {len(dangling)} | {latency:.1f}s"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
