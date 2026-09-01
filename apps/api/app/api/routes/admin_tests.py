"""Quản trị ĐỀ và BỘ SƯU TẬP: tạo, sửa, lưu trữ, xoá, phát hành.

Câu hỏi và cụm nằm ở `admin_questions.py`; hai nửa dùng chung bảy helper ở
`_admin_tests_shared.py`.

Luật của ADR-005 vẫn xuyên suốt: parse không bao giờ ghi, và commit luôn ghi
`draft` — không có đường đi thẳng từ dán vào thành đã phát hành.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.routes._admin_tests_shared import (
    _archive,
    _as_admin,
    _blocked_by,
    _drop_empty_sets,
    _force_delete_guard,
    _rows,
    _test_or_404,
)
from app.core.database import get_db
from app.models import (
    Attempt,
    AttemptItem,
    AttemptPart,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionOption,
    TestCollection,
    User,
)
from app.models.practice import FULL_FORM_SECONDS
from app.schemas.admin import (
    ArchiveRequest,
    CollectionAdmin,
    CollectionCreate,
    CollectionUpdate,
    TestAdmin,
    TestCreate,
    TestUpdate,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of

router = APIRouter(prefix="/admin", tags=["admin"])

can_edit = require_role("editor", "admin")
can_publish = require_role("admin")


# --- bộ đề: tầng trên cùng của cây (bộ đề -> đề -> câu) ---------------------


def _collection_or_404(db: Session, slug: str) -> TestCollection:
    collection = db.scalars(select(TestCollection).where(TestCollection.slug == slug)).one_or_none()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có bộ đề này")
    return collection


def _collection_admin(db: Session, collection: TestCollection) -> CollectionAdmin:
    tests = db.scalars(
        select(PracticeTest).where(PracticeTest.collection_id == collection.id)
    ).all()
    return CollectionAdmin(
        id=str(collection.id),
        slug=collection.slug,
        title=collection.title,
        description=collection.description,
        source_tag=collection.source_tag,
        year=collection.year,
        status=collection.status,
        test_count=len(tests),
        published_test_count=sum(1 for test in tests if test.status == "published"),
    )


@router.get("/test-collections", response_model=list[CollectionAdmin])
def list_collections_admin(
    db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[CollectionAdmin]:
    collections = db.scalars(
        select(TestCollection).order_by(TestCollection.position, TestCollection.title)
    ).all()
    return [_collection_admin(db, collection) for collection in collections]


@router.post(
    "/test-collections", response_model=CollectionAdmin, status_code=status.HTTP_201_CREATED
)
def create_collection(
    body: CollectionCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> CollectionAdmin:
    collection = TestCollection(
        slug=body.slug,
        title=body.title,
        description=body.description,
        source_tag=body.source_tag,
        year=body.year,
        status="draft",
        created_by=user.id,
    )
    db.add(collection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Đã có bộ đề với slug {body.slug!r}"
        ) from None
    return _collection_admin(db, collection)


@router.patch("/test-collections/{slug}", response_model=CollectionAdmin)
def update_collection(
    slug: str,
    body: CollectionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> CollectionAdmin:
    """Đổi tên và phần mô tả của một bộ đề.

    `can_edit` chứ không phải `can_publish`: đây là việc biên tập — sửa một cái
    nhãn gõ sai — chứ không phải việc phát hành. Cùng ranh giới đã vẽ ở `PATCH
    /tests/{slug}`, và cũng vì thế `slug` không sửa được từ đây (xem
    `CollectionUpdate`).

    Sửa được cả khi bộ đề ĐÃ xuất bản, và đó là chủ ý: một lỗi chính tả trong
    tên chỉ lộ ra sau khi có người nhìn thấy nó, mà lúc đó chính là lúc bộ đề đã
    ra ngoài. Bắt gỡ xuất bản để sửa một chữ sẽ khiến bộ đề biến mất khỏi mắt
    học viên vì một dấu phẩy.
    """
    collection = _collection_or_404(db, slug)
    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(collection, field_name, value)
    db.commit()
    return _collection_admin(db, collection)


@router.post("/test-collections/{slug}/publish", response_model=CollectionAdmin)
def publish_collection(
    slug: str, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> CollectionAdmin:
    """Tầng thứ ba của cùng một cổng chặn.

    Bộ đề không xuất bản được khi chưa có đề nào đã xuất bản — nếu không, người
    học thấy một bộ đề mở ra rỗng không, và không có gì nói cho họ biết vì sao.
    Cùng luật với cây dictation lọc `published` ở cả bốn tầng.
    """
    collection = _collection_or_404(db, slug)
    tests = db.scalars(
        select(PracticeTest).where(PracticeTest.collection_id == collection.id)
    ).all()
    published = [test for test in tests if test.status == "published"]
    if not published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Bộ đề này chưa có đề nào đã xuất bản" if tests else "Bộ đề này chưa có đề nào"
            ),
        )

    collection.status = "published"
    collection.published_by = user.id
    collection.published_at = datetime.now(UTC)
    db.commit()
    return _collection_admin(db, collection)


def _purge_attempts_of_test(db: Session, test_id: uuid.UUID) -> None:
    """Xoá mọi lượt làm của một đề, trước khi xoá chính đề đó.

    `attempt_item.selected_option_id` là RESTRICT trỏ sang `question_option`, nên
    **option phải sống cho tới khi item biến mất**: xoá câu trước rồi mới xoá
    lượt làm là IntegrityError. Thứ tự: item/part (kèm attempt qua CASCADE của
    `items`) → attempt. `coach_conversation` tự đi theo attempt qua CASCADE của
    database.
    """
    attempt_ids = list(db.scalars(select(Attempt.id).where(Attempt.test_id == test_id)))
    if not attempt_ids:
        return
    db.query(AttemptItem).filter(AttemptItem.attempt_id.in_(attempt_ids)).delete(
        synchronize_session=False
    )
    db.query(AttemptPart).filter(AttemptPart.attempt_id.in_(attempt_ids)).delete(
        synchronize_session=False
    )
    db.query(Attempt).filter(Attempt.id.in_(attempt_ids)).delete(synchronize_session=False)
    db.flush()


@router.post("/test-collections/{slug}/archive", response_model=CollectionAdmin)
def archive_collection(
    slug: str,
    body: ArchiveRequest,
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> CollectionAdmin:
    collection = _collection_or_404(db, slug)
    _archive(collection, body.archived)
    db.commit()
    return _collection_admin(db, collection)


@router.delete("/test-collections/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    slug: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> None:
    """Xoá một bộ đề.

    Mặc định chỉ xoá được bộ đề RỖNG. `practice_test.collection_id` là **SET
    NULL**, nên xoá một bộ đề còn đề bên trong KHÔNG nổ lỗi và KHÔNG mất dữ liệu
    — nó chỉ lặng lẽ cắt đường của người học tới từng đề trong đó, vì đề không
    thuộc bộ nào thì không xuất hiện ở đâu. Đó là kiểu hỏng tệ nhất trong ba
    cấp: không có gì báo, và phải mở từng đề mới thấy. Nên chặn ở đây, và nói ra
    còn mấy đề.

    `force=true` xoá luôn mọi đề bên trong kèm câu hỏi và lượt làm (chỉ ngoài
    production) — cây ba tầng đi cả cây.
    """
    _force_delete_guard(force)
    collection = _collection_or_404(db, slug)
    tests = db.scalars(
        select(PracticeTest).where(PracticeTest.collection_id == collection.id)
    ).all()
    if tests and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bộ đề này còn {len(tests)} đề. Chuyển chúng sang bộ khác trước — xoá bộ đề "
                f"không xoá đề, nhưng đề không thuộc bộ nào thì người học không thấy nữa."
            ),
        )
    for test in tests:
        _delete_test_core(db, test, force=force)
    db.delete(collection)
    db.commit()


@router.get("/tests", response_model=Page[TestAdmin])
def list_tests(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[TestAdmin]:
    query = select(PracticeTest)
    tests = db.scalars(
        query.order_by(PracticeTest.created_at.desc(), PracticeTest.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return page_of([_as_admin(db, test) for test in tests], count_rows(db, query), limit, offset)


@router.post("/tests", response_model=TestAdmin, status_code=status.HTTP_201_CREATED)
def create_test(
    body: TestCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> TestAdmin:
    collection_id = None
    if body.collection_slug:
        collection = db.scalars(
            select(TestCollection).where(TestCollection.slug == body.collection_slug)
        ).one_or_none()
        if collection is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có bộ đề này")
        collection_id = collection.id

    test = PracticeTest(
        slug=body.slug,
        title=body.title,
        description=body.description,
        collection_id=collection_id,
        kind=body.kind,
        # Đề ĐẦY ĐỦ mặc định 120 phút. Không đặt thì người học vào phòng thi
        # thử mà không có đồng hồ, và cái thiếu đó không báo lỗi ở đâu cả —
        # giao diện chỉ lặng lẽ hiện "Không giới hạn giờ", đọc ra như một lựa
        # chọn của người soạn chứ không như một ô bị bỏ trống.
        #
        # Vẫn nhường giá trị người soạn nhập, kể cả 0: một đề đầy đủ dùng để ôn
        # không tính giờ là chuyện có thật, chỉ là không phải mặc định.
        time_limit_seconds=(
            FULL_FORM_SECONDS
            if body.time_limit_seconds is None and body.kind == "full"
            else body.time_limit_seconds
        ),
        # Không bao giờ publish thẳng từ lúc tạo, dù nội dung có sạch tới đâu.
        status="draft",
        created_by=user.id,
    )
    db.add(test)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Đã có đề với slug {body.slug!r}"
        ) from None
    return _as_admin(db, test)


@router.get("/tests/{slug}", response_model=TestAdmin)
def get_test(slug: str, db: Session = Depends(get_db), _: User = Depends(can_edit)) -> TestAdmin:
    return _as_admin(db, _test_or_404(db, slug))


@router.patch("/tests/{slug}", response_model=TestAdmin)
def update_test(
    slug: str,
    body: TestUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> TestAdmin:
    """Sửa vỏ đề, gồm cả chuyển đề sang bộ khác hoặc gỡ khỏi bộ.

    Phân biệt khoá VẮNG MẶT với khoá bằng null, qua `exclude_unset`: vắng nghĩa
    là đừng đụng tới, null nghĩa là xoá. Một phép gộp `giá trị or cũ` không phân
    biệt được hai thứ đó, và lỗi thì im lặng — lệnh gỡ đề khỏi bộ trả về 200 mà
    không đổi gì, nên không ai phát hiện cho tới lần tải lại trang.
    """
    test = _test_or_404(db, slug)
    changes = body.model_dump(exclude_unset=True)

    if "collection_slug" in changes:
        chosen = changes.pop("collection_slug")
        test.collection_id = _collection_or_404(db, chosen).id if chosen else None
    for field_name, value in changes.items():
        setattr(test, field_name, value)

    db.commit()
    return _as_admin(db, test)


@router.post("/tests/{slug}/archive", response_model=TestAdmin)
def archive_test(
    slug: str,
    body: ArchiveRequest,
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> TestAdmin:
    test = _test_or_404(db, slug)
    _archive(test, body.archived)
    db.commit()
    return _as_admin(db, test)


@router.delete("/tests/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(
    slug: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> None:
    """Xoá một đề cùng câu hỏi và cụm của nó.

    Hai điều dễ làm sai ở đây, và cả hai đều im lặng:

    **Câu hỏi phải xoá tay, không trông vào CASCADE.**
    `practice_test_question.test_id` là CASCADE nên hàng liên kết tự biến mất —
    nhưng `question` thì sống sót, và một câu không thuộc đề nào sẽ không hiện ở
    bất kỳ màn quản trị nào (`_link_or_409` giả định nó phải thuộc một đề). Nó
    nằm lại trong database vĩnh viễn, không ai với tới để xoá.

    **Nhưng chỉ xoá câu mà đề NÀY là đề duy nhất dùng nó.** Khoá chính của bảng
    liên kết là (test_id, question_id), nên một câu dùng chung cho hai đề là hợp
    lệ — xoá theo sẽ moi ruột đề còn lại.

    `force=true` xoá luôn mọi lượt làm bài (chỉ ngoài production): giai đoạn dev
    cần dọn sạch đề thử mà tài khoản thử đã làm qua; production thì lịch sử học
    viên là bất khả xâm phạm.
    """
    _force_delete_guard(force)
    test = _test_or_404(db, slug)
    _delete_test_core(db, test, force=force)
    db.commit()


def _delete_test_core(db: Session, test: PracticeTest, force: bool) -> None:
    """Xoá một đề cùng câu hỏi và cụm của nó, không commit.

    Hai điều dễ làm sai ở đây, và cả hai đều im lặng:

    **Câu hỏi phải xoá tay, không trông vào CASCADE.**
    `practice_test_question.test_id` là CASCADE nên hàng liên kết tự biến mất —
    nhưng `question` thì sống sót, và một câu không thuộc đề nào sẽ không hiện ở
    bất kỳ màn quản trị nào (`_link_or_409` giả định nó phải thuộc một đề). Nó
    nằm lại trong database vĩnh viễn, không ai với tới để xoá.

    **Nhưng chỉ xoá câu mà đề NÀY là đề duy nhất dùng nó.** Khoá chính của bảng
    liên kết là (test_id, question_id), nên một câu dùng chung cho hai đề là hợp
    lệ — xoá theo sẽ moi ruột đề còn lại.

    `force` xoá luôn mọi lượt làm bài; gọi hàm này với `force=True` chỉ hợp lệ
    SAU `_force_delete_guard`.
    """
    attempts = db.scalar(select(func.count(Attempt.id)).where(Attempt.test_id == test.id))
    if attempts:
        if not force:
            _blocked_by(attempts, "lượt làm bài", "đề")
        # Xoá lượt làm TRƯỚC khi xoá câu: `attempt_item.selected_option_id` là
        # RESTRICT trỏ sang option, nên option phải còn khi item bị xoá.
        _purge_attempts_of_test(db, test.id)

    rows = _rows(db, test.id)
    question_ids = [question.id for _, question in rows]
    if question_ids:
        # Câu nào còn được đề khác dùng thì để nguyên.
        shared = {
            question_id
            for question_id in db.scalars(
                select(PracticeTestQuestion.question_id).where(
                    PracticeTestQuestion.question_id.in_(question_ids),
                    PracticeTestQuestion.test_id != test.id,
                )
            )
        }
        doomed = [qid for qid in question_ids if qid not in shared]
        set_ids = {q.set_id for _, q in rows if q.set_id and q.id not in shared}

        # Gỡ liên kết TRƯỚC: `practice_test_question.question_id` là RESTRICT,
        # nên xoá câu khi hàng liên kết còn đó sẽ nổ IntegrityError.
        db.query(PracticeTestQuestion).filter(PracticeTestQuestion.test_id == test.id).delete(
            synchronize_session=False
        )
        db.flush()
        if doomed:
            # Xoá tay cả option: xoá hàng loạt (`Query.delete`) KHÔNG đi qua
            # cascade của ORM — để mặc nó thì phụ thuộc CASCADE của database,
            # còn một hàng mồ côi thì nằm lại mà không ai thấy.
            db.query(QuestionOption).filter(QuestionOption.question_id.in_(doomed)).delete(
                synchronize_session=False
            )
            db.query(Question).filter(Question.id.in_(doomed)).delete(synchronize_session=False)
            db.flush()
        _drop_empty_sets(db, set_ids)

    db.delete(test)


@router.post("/tests/{slug}/publish", response_model=TestAdmin)
def publish_test(
    slug: str, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> TestAdmin:
    """Xuất bản đề. Từ chối khi còn bất kỳ câu nào chưa xuất bản.

    Chặn ở tầng đề *và* tầng câu, cùng lý do cây dictation lọc `published` ở cả
    bốn tầng: một câu nháp nằm trong đề đã publish sẽ lọt ra, và nội dung đó
    trông hoàn toàn bình thường — không có gì để phát hiện.
    """
    test = _test_or_404(db, slug)
    rows = _rows(db, test.id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Đề này chưa có câu nào")

    unpublished = [link.number for link, question in rows if question.status != "published"]
    if unpublished:
        preview = ", ".join(str(number) for number in sorted(unpublished)[:10])
        more = f" và {len(unpublished) - 10} câu nữa" if len(unpublished) > 10 else ""
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Còn {len(unpublished)} câu chưa xuất bản: {preview}{more}",
        )

    test.status = "published"
    test.published_by = user.id
    test.published_at = datetime.now(UTC)
    db.commit()
    return _as_admin(db, test)
