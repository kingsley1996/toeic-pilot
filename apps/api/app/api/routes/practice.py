"""Đọc bộ đề, đề, và cấu trúc của một đề.

Công khai — không đòi đăng nhập. Danh sách đề là thứ người ta xem trước khi
quyết định có đăng ký hay không, và bắt đăng nhập để *nhìn* sẽ chặn đúng nhóm
người mà trang này tồn tại để thuyết phục. Bắt đầu làm bài thì mới cần tài
khoản, vì lúc đó mới có gì để lưu.

Đường dẫn gạch nối (`/test-collections`), không lồng dưới `/practice/`: cùng lý
do đã ghi cho `/dictation-topics` — một đường dẫn động khai kiểu UUID sẽ bắt mất
các đường tĩnh nằm sau nó, và 422 khi cố parse chữ thành UUID.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.practice import (
    Attempt,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    TestCollection,
)
from app.schemas.practice import (
    PART_TITLES,
    CollectionDetail,
    CollectionSummary,
    PartBreakdown,
    TestDetail,
    TestSummary,
    section_of,
)

router = APIRouter(tags=["practice"])

PUBLISHED = "published"


def _question_counts(db: Session, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not test_ids:
        return {}
    rows = db.execute(
        select(PracticeTestQuestion.test_id, func.count())
        .where(PracticeTestQuestion.test_id.in_(test_ids))
        .group_by(PracticeTestQuestion.test_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def _attempt_counts(db: Session, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Số lượt làm, ĐẾM chứ không lưu sẵn.

    Cùng luật với tiến độ dictation và thống kê hồ sơ: một bộ đếm ghi song song
    sẽ lệch khỏi lịch sử ngay lần đầu có một lượt bị xoá, và không có gì phát
    hiện ra.
    """
    if not test_ids:
        return {}
    rows = db.execute(
        select(Attempt.test_id, func.count())
        .where(Attempt.test_id.in_(test_ids))
        .group_by(Attempt.test_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def _summary(test: PracticeTest, questions: int, attempts: int) -> TestSummary:
    return TestSummary(
        id=str(test.id),
        slug=test.slug,
        title=test.title,
        description=test.description,
        kind=test.kind,
        time_limit_seconds=test.time_limit_seconds,
        question_count=questions,
        attempt_count=attempts,
    )


@router.get("/test-collections", response_model=list[CollectionSummary])
def list_collections(db: Session = Depends(get_db)) -> list[CollectionSummary]:
    collections = list(
        db.scalars(
            select(TestCollection)
            .where(TestCollection.status == PUBLISHED)
            .order_by(TestCollection.position, TestCollection.title)
        ).all()
    )
    if not collections:
        return []

    # Chỉ đếm đề ĐÃ PUBLISH. Đếm cả bản nháp thì thẻ bộ đề hứa 10 đề trong khi
    # người dùng bấm vào chỉ thấy 6, và không có gì giải thích chỗ chênh.
    tests = list(
        db.scalars(
            select(PracticeTest).where(
                PracticeTest.status == PUBLISHED,
                PracticeTest.collection_id.in_([c.id for c in collections]),
            )
        ).all()
    )
    attempts = _attempt_counts(db, [t.id for t in tests])

    by_collection: dict[uuid.UUID, list[PracticeTest]] = {}
    for test in tests:
        if test.collection_id is not None:
            by_collection.setdefault(test.collection_id, []).append(test)

    return [
        CollectionSummary(
            id=str(collection.id),
            slug=collection.slug,
            title=collection.title,
            description=collection.description,
            source_tag=collection.source_tag,
            year=collection.year,
            test_count=len(by_collection.get(collection.id, [])),
            attempt_count=sum(attempts.get(t.id, 0) for t in by_collection.get(collection.id, [])),
        )
        for collection in collections
    ]


@router.get("/test-collections/{slug}", response_model=CollectionDetail)
def read_collection(slug: str, db: Session = Depends(get_db)) -> CollectionDetail:
    collection = db.scalars(
        select(TestCollection).where(
            TestCollection.slug == slug, TestCollection.status == PUBLISHED
        )
    ).one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có bộ đề này")

    tests = list(
        db.scalars(
            select(PracticeTest)
            .where(
                PracticeTest.collection_id == collection.id,
                PracticeTest.status == PUBLISHED,
            )
            .order_by(PracticeTest.position, PracticeTest.title)
        ).all()
    )
    test_ids = [t.id for t in tests]
    questions = _question_counts(db, test_ids)
    attempts = _attempt_counts(db, test_ids)

    return CollectionDetail(
        id=str(collection.id),
        slug=collection.slug,
        title=collection.title,
        description=collection.description,
        source_tag=collection.source_tag,
        year=collection.year,
        test_count=len(tests),
        attempt_count=sum(attempts.get(test_id, 0) for test_id in test_ids),
        tests=[_summary(t, questions.get(t.id, 0), attempts.get(t.id, 0)) for t in tests],
    )


@router.get("/practice-tests/{slug}", response_model=TestDetail)
def read_test(slug: str, db: Session = Depends(get_db)) -> TestDetail:
    test = db.scalars(
        select(PracticeTest).where(PracticeTest.slug == slug, PracticeTest.status == PUBLISHED)
    ).one_or_none()
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có đề này")

    rows = db.execute(
        select(Question.part, func.count())
        .join(PracticeTestQuestion, PracticeTestQuestion.question_id == Question.id)
        .where(PracticeTestQuestion.test_id == test.id, Question.status == PUBLISHED)
        .group_by(Question.part)
    ).all()
    by_part = {int(row[0]): int(row[1]) for row in rows}

    # Liệt kê đủ BẢY part kể cả part chưa có câu nào. Chỉ trả về part có nội dung
    # sẽ khiến đề trông như chỉ có năm phần, và người học không có cách nào biết
    # phần nghe đang thiếu — họ sẽ tưởng đó là thiết kế.
    parts = [
        PartBreakdown(
            part=part,
            section=section_of(part),
            title=PART_TITLES[part],
            question_count=by_part.get(part, 0),
            has_content=by_part.get(part, 0) > 0,
        )
        for part in range(1, 8)
    ]

    attempts = _attempt_counts(db, [test.id])
    return TestDetail(
        **_summary(test, sum(by_part.values()), attempts.get(test.id, 0)).model_dump(),
        parts=parts,
    )
