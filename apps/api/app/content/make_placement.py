"""Lắp đề placement từ một đề full có sẵn — SPEC-PLACEMENT §1 path A.

    uv run python -m app.content.make_placement                # tạo/cập nhật draft
    uv run python -m app.content.make_placement --publish      # duyệt + xuất bản

Định mức 84 câu (§0 của spec) được cắt theo NGUYÊN CỤM: P1 6, P2 12 (đủ phủ
nhãn `question_type`), P3 4 cụm, P4 4 cụm, P5 20 (mỗi nhãn `grammar` ít nhất
một câu), P6 2 set, P7 chọn cụm nguyên cộng lại gần nhất 14. Cắt lệch phần dư
chấp nhận được; cắt cụm thì không — một nửa cuộc hội thoại không phải một câu
hỏi trắc nghiệm độc lập.

Số câu (`number`) đánh tuần tự 1..N theo part — đề mini không nhảy cóc kiểu
đề 200 câu, và số nhảy cóc phải là thứ có người nhìn thấy và đồng ý (ADR-007
§2.6); người duyệt thấy số liền mạch trong bảng duyệt.
"""

import argparse
from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.labels import QuestionLabel
from app.models.practice import PracticeTest, PracticeTestQuestion, Question

SOURCE_SLUG = "tp-test-09"
PLACEMENT_SLUG = "tp-placement-01"
TITLE = "Bài test đầu vào"
DESCRIPTION = (
    "84 câu rút từ đề mẫu, ~50 phút. Kết quả cho biết trình độ hiện tại "
    "(ước lượng) và những kỹ năng cần luyện — làm một lần mỗi tuần."
)
KIND = "mini"
TIME_LIMIT_SECONDS = 50 * 60


def _source_questions(db: Session) -> list[Question]:
    test = db.scalar(select(PracticeTest).where(PracticeTest.slug == SOURCE_SLUG))
    if test is None:
        raise SystemExit(f"không có đề nguồn {SOURCE_SLUG}")
    rows = db.execute(
        select(PracticeTestQuestion.position, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .where(PracticeTestQuestion.test_id == test.id)
        .order_by(PracticeTestQuestion.position)
    ).all()
    return [q for _, q in rows]


def _labels_of(db: Session, facet: str, ids: list[UUID]) -> dict[UUID, list[str]]:
    """question_id -> các mã nhãn của một facet. `question` không có
    relationship tới nhãn; truy vấn bảng nối một lần cho cả đề nguồn."""
    rows = db.execute(
        select(QuestionLabel.question_id, QuestionLabel.code).where(
            QuestionLabel.question_id.in_(ids), QuestionLabel.facet == facet
        )
    ).all()
    out: dict[UUID, list[str]] = {}
    for qid, code in rows:
        out.setdefault(qid, []).append(code)
    return out


def _pick_by_labels(
    questions: list[Question], labels: dict[UUID, list[str]], n: int
) -> list[Question]:
    """Phủ nhãn trước (mỗi mã một câu), phần dư ưu tiên mã phổ biến."""
    by_label: dict[str, list[Question]] = {}
    for q in questions:
        for code in labels.get(q.id, []):
            by_label.setdefault(code, []).append(q)
    picked: set[UUID] = set()
    out: list[Question] = []
    # Mã hiếm trước — một câu duy nhất của mã đó đáng hơn câu của mã đã dày.
    for code in sorted(by_label, key=lambda c: len(by_label[c])):
        for q in by_label[code]:
            if q.id not in picked:
                picked.add(q.id)
                out.append(q)
                break
    freq = Counter({c: len(qs) for c, qs in by_label.items()})
    while len(out) < n:
        grew = False
        for code, _ in freq.most_common():
            for q in by_label[code]:
                if q.id not in picked:
                    picked.add(q.id)
                    out.append(q)
                    grew = True
                    break
            if len(out) >= n:
                break
        if not grew:
            break
    return out


def _whole_sets(questions: list[Question], target: int, want: int) -> list[Question]:
    """Cụm NGUYÊN tới khi đủ `want` cụm hoặc hết `target` câu."""
    by_set: dict[UUID, list[Question]] = {}
    for q in questions:
        if q.set_id is not None:
            by_set.setdefault(q.set_id, []).append(q)
    out: list[Question] = []
    for set_id in by_set:
        if len(out) >= target:
            break
        group = by_set[set_id]
        if len(out) + len(group) <= target:
            out.extend(group)
            want -= 1
    return out


def _pick_part(
    part: int,
    questions: list[Question],
    type_labels: dict[UUID, list[str]],
    grammar_labels: dict[UUID, list[str]],
) -> list[Question]:
    if part == 1:
        return questions[:6]
    if part == 2:
        return _pick_by_labels(questions, type_labels, 12)
    if part in (3, 4):
        return _whole_sets(questions, 12, 4)
    if part == 5:
        return _pick_by_labels(questions, grammar_labels, 20)
    if part == 6:
        return _whole_sets(questions, 8, 2)
    # P7: cụm nguyên cộng lại gần 14 nhất mà không vượt.
    return _whole_sets(questions, 14, 99)


def build(db: Session, publish: bool) -> None:
    source = _source_questions(db)
    ids = [q.id for q in source]
    type_labels = _labels_of(db, "question_type", ids)
    grammar_labels = _labels_of(db, "grammar", ids)
    chosen: list[Question] = []
    report: list[tuple[int, int]] = []
    for part in range(1, 8):
        part_qs = [q for q in source if q.part == part]
        picked = _pick_part(part, part_qs, type_labels, grammar_labels)
        report.append((part, len(picked)))
        chosen.extend(picked)

    existing = db.scalar(select(PracticeTest).where(PracticeTest.slug == PLACEMENT_SLUG))
    if existing is not None and existing.status == "published":
        raise SystemExit("đề placement đã published — dựng lại là đổi đề dưới chân người học")
    if existing is None:
        existing = PracticeTest(
            slug=PLACEMENT_SLUG,
            title=TITLE,
            description=DESCRIPTION,
            kind=KIND,
            time_limit_seconds=TIME_LIMIT_SECONDS,
            score_scale_slug="default",
            is_placement=True,
        )
        db.add(existing)
        db.flush()
    existing.title = TITLE
    existing.description = DESCRIPTION
    existing.is_placement = True
    for row in db.scalars(
        select(PracticeTestQuestion).where(PracticeTestQuestion.test_id == existing.id)
    ):
        db.delete(row)
    for number, question in enumerate(chosen, start=1):
        db.add(
            PracticeTestQuestion(
                test_id=existing.id, question_id=question.id, position=number, number=number
            )
        )
    if publish:
        existing.status = "published"
    db.commit()

    print(f"{PLACEMENT_SLUG}: {len(chosen)} câu ({'published' if publish else 'draft'})")
    for part, count in report:
        print(f"  part {part}: {count}")
    grammar_codes = {code for q in chosen for code in grammar_labels.get(q.id, [])}
    print(f"  nhãn grammar: {len(grammar_codes)} mã")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="xuất bản sau khi lắp")
    args = parser.parse_args()
    with SessionLocal() as db:
        build(db, publish=args.publish)


if __name__ == "__main__":
    main()
