"""Gắn nhãn phân loại cho một đề đã nạp, lấy từ chính blueprint của nó.

    uv run python -m app.content.generate_exam label --slug tp-test-09

**Blueprint ĐÃ BIẾT nhãn, và trước bước này nó bị vứt đi.** `plan` quy định dạng
câu cho từng ô (`question_types`), điểm ngữ pháp (`grammars`), chủ đề cụm, dạng
ngữ liệu và cấu trúc đoạn. Nhưng tệp dán không có trường nhãn, `loader` không
mang nó trong payload, và `commit_part` không ghi — nên thông tin chính xác ấy
chết ở bước nạp, rồi `enrich_skills` gọi LLM để **suy lại đúng thứ vừa vứt**.
Tốn tiền là chuyện nhỏ; bản suy lại có thể sai, còn bản gốc thì không.

**`proposed_code` để NULL, khác hẳn `enrich_skills`.** Ở đó nhãn là máy ĐOÁN,
nên `proposed_code` giữ lại phỏng đoán để đo xem người duyệt phải sửa bao nhiêu —
đó là KPI độ đúng. Nhãn ở đây không phải phỏng đoán mà là QUY ĐỊNH: đề được sinh
ra *để* câu đó thuộc dạng đó. Ghi nó vào `proposed_code` sẽ nhồi vào mẫu số của
KPI hàng nghìn dòng không có máy nào đoán, và con số đó lập tức vô nghĩa.

**Không ghi đè hàng đã có.** Một nhãn đã nằm đó có thể là bản người duyệt vừa
sửa tay, và ghi đè bằng bản blueprint sẽ xoá việc của họ một cách im lặng. Chạy
lại lệnh này bao nhiêu lần cũng chỉ điền vào chỗ trống.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.exam import blueprint as bp
from app.content.exam_cli.paths import blueprint_path
from app.core.database import SessionLocal
from app.models.labels import QuestionLabel, QuestionSetLabel
from app.models.practice import PracticeTest, PracticeTestQuestion, Question
from app.services.labels import FACETS, LABELS

# Mã nhãn → mặt chứa nó. Tra ngược thay vì suy từ part, vì `slot.topic` mang ba
# nghĩa khác nhau tuỳ part — chủ đề ở Part 3, dạng lời nói ở Part 4, dạng ngữ
# liệu ở Part 7 — và đoán theo part là cách chắc chắn có ngày gán sai mặt. Khoá
# chính của bảng là `(owner_id, facet)`, nên một mã ghi nhầm mặt sẽ ĐÈ nhãn của
# mặt khác chứ không tạo hàng mới.
FACET_OF: dict[str, str] = {label.code: facet.key for facet in FACETS for label in facet.labels}
OWNER_OF: dict[str, str] = {facet.key: facet.owner for facet in FACETS}


def _valid(code: str, part: int, owner: str) -> str | None:
    """Mặt của `code` nếu nó dùng được ở đây, ngược lại None kèm im lặng.

    Ba phép kiểm giống `admin_ai._check`, vì ba kiểu sai đều im lặng: mã bịa, mã
    đúng nhưng sai tầng sở hữu, và mã hợp lệ ở part khác.
    """
    label = LABELS.get(code)
    facet = FACET_OF.get(code)
    if label is None or facet is None:
        return None
    if OWNER_OF[facet] != owner or part not in label.parts:
        return None
    return facet


def _question_codes(slot: bp.QuestionSlot, index: int) -> list[str]:
    """Nhãn cấp CÂU của câu thứ `index` trong ô.

    Ô một câu (Part 1, 2, 5) mang `question_type`/`grammar` ở dạng số ít; ô cụm
    (Part 3, 4, 6, 7) mang danh sách song song với các câu.
    """
    codes = []
    if slot.question_types:
        if index < len(slot.question_types):
            codes.append(slot.question_types[index])
    elif slot.question_type:
        codes.append(slot.question_type)
    if slot.grammars:
        if index < len(slot.grammars):
            codes.append(slot.grammars[index])
    elif slot.grammar:
        codes.append(slot.grammar)
    return [code for code in codes if code]


def apply_labels(
    db: Session, plan: bp.Blueprint, *, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """(số nhãn vừa ghi, số nhãn đã có nên bỏ qua, những chỗ không gán được).

    `dry_run` phải là THAM SỐ, không phải chuyện người gọi tự lo bằng `rollback`.
    Hàm này `commit()` ở cuối, nên gói nó trong `begin()/rollback()` để "thử xem"
    không hoàn lại được gì — việc ghi đã xong từ trước lúc rollback chạy. Tôi mắc
    đúng lỗi đó ngày 2026-09-03 và tưởng mình mới chỉ thử.
    """
    test = db.scalars(select(PracticeTest).where(PracticeTest.slug == plan.slug)).first()
    if test is None:
        raise SystemExit(f"chưa nạp đề {plan.slug!r} — chạy `load` trước")

    rows = db.execute(
        select(PracticeTestQuestion.number, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .where(PracticeTestQuestion.test_id == test.id)
    ).all()
    by_number = {number: question for number, question in rows}

    written = 0
    skipped = 0
    problems: list[str] = []

    for part_plan in plan.parts:
        for slot in part_plan.slots:
            count = max(len(slot.question_types), 1)
            questions = []
            for index in range(count):
                question = by_number.get(slot.number + index)
                if question is None:
                    problems.append(f"{slot.id}: chưa nạp câu {slot.number + index}")
                    continue
                questions.append((index, question))

            for index, question in questions:
                for code in _question_codes(slot, index):
                    facet = _valid(code, question.part, "question")
                    if facet is None:
                        problems.append(f"{slot.id} câu {question.part}: mã lạ {code!r}")
                        continue
                    if db.get(QuestionLabel, (question.id, facet)) is not None:
                        skipped += 1
                        continue
                    db.add(QuestionLabel(question_id=question.id, facet=facet, code=code))
                    written += 1

            # Nhãn cấp CỤM chỉ ghi khi các câu thật sự thuộc một cụm. Ô không có
            # `set_id` (Part 1, 2, 5) không có chỗ để treo chúng, và `slot.topic`
            # ở đó vốn cũng rỗng.
            owner = next((q.question_set for _, q in questions if q.set_id), None)
            if owner is None:
                continue
            for code in (slot.topic, slot.structure):
                if not code:
                    continue
                facet = _valid(code, part_plan.part, "set")
                if facet is None:
                    problems.append(f"{slot.id}: mã cụm lạ {code!r}")
                    continue
                if db.get(QuestionSetLabel, (owner.id, facet)) is not None:
                    skipped += 1
                    continue
                db.add(QuestionSetLabel(set_id=owner.id, facet=facet, code=code))
                written += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return written, skipped, problems


def cmd_label(args: argparse.Namespace) -> int:
    plan = bp.load(blueprint_path(args.slug))
    with SessionLocal() as db:
        written, skipped, problems = apply_labels(db, plan, dry_run=args.dry_run)
    verb = "sẽ ghi" if args.dry_run else "vừa ghi"
    print(f"{written} nhãn {verb} · {skipped} đã có nên bỏ qua")
    for line in problems[:20]:
        print(f"  ✗ {line}")
    if len(problems) > 20:
        print(f"  … và {len(problems) - 20} dòng nữa")
    return 1 if problems else 0
