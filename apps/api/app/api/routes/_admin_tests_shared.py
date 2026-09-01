"""Những mảnh dùng chung giữa `admin_tests` và `admin_questions`.

Bảy helper, và tất cả đều trả lời một câu hỏi ở tầng ĐỀ mà cả hai nửa đều phải
hỏi: đề này có tồn tại không, ai được xoá nó, xoá rồi thì cụm rỗng đi đâu.

Cho một router import router kia thì hai tệp lại dính vào nhau và việc tách chỉ
còn là đổi tên — `REFACTOR-LONG-FILES.md` §2. Tiền tố `_` để `app/main.py`
không nhầm đây là một mô-đun route.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import (
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionSet,
    TestCollection,
)
from app.models.validators import validate_question
from app.schemas.admin import (
    TestAdmin,
    TestPartSummary,
)
from app.schemas.practice import PART_TITLES, section_of


def _test_or_404(db: Session, slug: str) -> PracticeTest:
    test = db.scalars(select(PracticeTest).where(PracticeTest.slug == slug)).one_or_none()
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có đề này")
    return test


def _rows(db: Session, test_id: uuid.UUID) -> list[tuple[PracticeTestQuestion, Question]]:
    return [
        (link, question)
        for link, question in db.execute(
            select(PracticeTestQuestion, Question)
            .join(Question, Question.id == PracticeTestQuestion.question_id)
            .options(selectinload(Question.options), selectinload(Question.question_set))
            .where(PracticeTestQuestion.test_id == test_id)
            .order_by(PracticeTestQuestion.position)
        ).all()
    ]


# --- đề ---------------------------------------------------------------------


def _archive(row: Question | PracticeTest | TestCollection, archived: bool) -> None:
    """Cất đi, hoặc lấy lại về nháp.

    Lấy lại KHÔNG trả về `published`: thứ vừa được cất đi phải qua cổng xuất bản
    một lần nữa, vì lý do nó bị cất có thể chính là lý do nó không nên xuất hiện.
    """
    row.status = "archived" if archived else "draft"
    if archived:
        row.published_by = None
        row.published_at = None


def _blocked_by(count: int | None, what: str, noun: str) -> None:
    """Từ chối xoá, và chỉ đúng lối thoát.

    Lời từ chối chỉ xong khi thứ nó đòi hỏi nằm trong tầm với của người đang đọc
    — nên câu này nói tên trạng thái, và giao diện có nút Lưu trữ ngay cạnh nút
    Xoá. Bài học đã trả giá một lần với dictation, nơi 409 bảo "chuyển sang
    archived" trong khi màn quản trị không có nút archive nào.
    """
    if count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Không xoá được: {count} {what} đang tham chiếu {noun} này. "
                f"Lưu trữ thay vì xoá — nó biến mất khỏi mắt người học mà không "
                f"làm mồ côi lịch sử làm bài."
            ),
        )


def _force_delete_guard(force: bool) -> None:
    """Cờ `force` chỉ tồn tại cho môi trường dev — nơi nội dung thử thay đổi
    hàng ngày và lịch sử làm bài của tài khoản thử không đáng giữ.

    Ở production nó là 403: dữ liệu học viên là thật, và RESTRICT tồn tại chính
    là để không ai xoá nhầm nó. Đừng nới luật này thành "chỉ cảnh báo".
    """
    if force and settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Xoá cưỡng chế chỉ khả dụng ngoài môi trường production.",
        )


def _drop_empty_sets(db: Session, set_ids: set[uuid.UUID]) -> None:
    """Xoá những cụm vừa mất hết câu.

    Một cụm rỗng không hiện ở màn nào và không ai với tới được, nên để lại là
    tích rác — cùng lý do phải xoá câu tay thay vì trông vào CASCADE của đề.
    """
    for set_id in set_ids:
        remaining = db.scalar(select(func.count(Question.id)).where(Question.set_id == set_id))
        if not remaining:
            stimulus = db.get(QuestionSet, set_id)
            if stimulus is not None:
                db.delete(stimulus)
    db.flush()


def _as_admin(db: Session, test: PracticeTest) -> TestAdmin:
    rows = _rows(db, test.id)
    collection_slug = test.collection.slug if test.collection else None

    parts: list[TestPartSummary] = []
    for part in sorted({question.part for _, question in rows}):
        in_part = [question for _, question in rows if question.part == part]
        parts.append(
            TestPartSummary(
                part=part,
                title=PART_TITLES[part],
                section=section_of(part),
                question_count=len(in_part),
                published_count=sum(1 for q in in_part if q.status == "published"),
                problem_count=sum(1 for q in in_part if validate_question(q)),
            )
        )

    return TestAdmin(
        id=str(test.id),
        slug=test.slug,
        title=test.title,
        description=test.description,
        kind=test.kind,
        status=test.status,
        time_limit_seconds=test.time_limit_seconds,
        collection_slug=collection_slug,
        question_count=len(rows),
        parts=parts,
    )
