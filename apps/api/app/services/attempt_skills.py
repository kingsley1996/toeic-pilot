"""Chia kết quả một lượt thi theo KỸ NĂNG, lấy từ nhãn của từng câu.

`question_label` đã mang dạng câu cho mọi câu của đề, nhưng cho tới giờ nó chỉ
được dùng ở màn quản trị. Người học mới là người cần nó: "Part 7 được 60%"
không nói được nên luyện gì, còn "câu hỏi suy luận 4/14" thì nói được.

**Gộp theo TÊN, không theo mã.** Facet `question_type` có 40 mã, trung bình 5
câu mỗi mã trên một đề 200 câu — quá mỏng để nói lên điều gì trong một lượt
thi. Nhưng phần lớn trong đó là CÙNG một kỹ năng bị tách theo part:
`PART_3_TOPIC_OR_PURPOSE`, `PART_4_TOPIC_OR_PURPOSE` và `PART_7_TOPIC_OR_PURPOSE`
đều là "câu hỏi về chủ đề, mục đích". Gộp theo `label_vi` còn 33 kỹ năng, và
nhóm đầu có 9–23 câu mỗi kỹ năng — đủ dày để một tỉ lệ có nghĩa.

Đếm cả câu BỎ TRỐNG vào mẫu số: người không kịp làm mười câu suy luận cuối bài
vẫn là người chưa nắm dạng đó, và bỏ chúng ra khỏi mẫu số sẽ báo một tỉ lệ đẹp
cho phần họ chưa từng đọc.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.labels import QuestionLabel
from app.models.practice import Attempt, AttemptItem
from app.schemas.practice import SkillScore
from app.services.labels import LABELS

_FACET = "question_type"


def skill_breakdown(session: Session, attempt: Attempt) -> list[SkillScore]:
    """(kỹ năng, số đúng, tổng số câu) cho lượt này, nhiều câu nhất trước."""
    rows = session.execute(
        select(QuestionLabel.code, AttemptItem.is_correct)
        .join(QuestionLabel, QuestionLabel.question_id == AttemptItem.question_id)
        .where(AttemptItem.attempt_id == attempt.id, QuestionLabel.facet == _FACET)
    ).all()

    tally: dict[str, list[int]] = {}
    for code, is_correct in rows:
        label = LABELS.get(code)
        # Mã lạ thì bỏ qua chứ không hiện mã thô: một chuỗi như
        # `PART_7_IMPLICATION` trên màn hình người học là rác, còn thiếu một
        # dòng thì không ai mất gì.
        if label is None:
            continue
        entry = tally.setdefault(label.label_vi, [0, 0])
        entry[0] += 1 if is_correct else 0
        entry[1] += 1

    return [
        SkillScore(name=name, correct=correct, count=count)
        for name, (correct, count) in sorted(tally.items(), key=lambda item: (-item[1][1], item[0]))
    ]
