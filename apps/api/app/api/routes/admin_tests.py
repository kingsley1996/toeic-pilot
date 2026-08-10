"""Soạn đề thi: tạo đề, dán từng part, sửa từng câu, xuất bản.

Quyết định đầy đủ: `planning/ADR-007-TEST-AUTHORING.md`. Bốn điều dễ phá nhất:

  §2.3  Parse KHÔNG ghi vào database. Dán -> xem trước -> commit là ba bước.
  §2.5  `question.source` không có giá trị mặc định ở bất kỳ tầng nào.
  §2.6  Số câu LƯU, không suy ra.
  §2.8  Cổng chặn ở hai tầng: câu và đề.

Tách khỏi `admin.py` vì file đó đã gần 1000 dòng, không phải vì luật nào khác —
`can_edit`/`can_publish` vẫn là cùng hai dependency, và `require_role` vẫn là
dependency chứ không bao giờ là một phép kiểm trong thân hàm.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_role
from app.core.database import get_db
from app.core.media import public_audio_url
from app.core.storage import StorageDriver, get_driver
from app.models import (
    ImageAsset,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionOption,
    QuestionSet,
    TestCollection,
    User,
)
from app.models.validators import validate_question
from app.schemas.admin import (
    CollectionAdmin,
    CollectionCreate,
    GroupDraft,
    ParseRequest,
    PassageAdmin,
    PassageImageAssign,
    QuestionAdmin,
    QuestionDraft,
    QuestionEdit,
    QuestionOptionDraft,
    SetAdmin,
    TestAdmin,
    TestCreate,
    TestPartCommit,
    TestPartParseResponse,
    TestPartSummary,
    TestUpdate,
)
from app.schemas.practice import PART_NUMBER_RANGES, PART_TITLES, section_of
from app.services.content_import import parse_reading_part

router = APIRouter(prefix="/admin", tags=["admin"])

can_edit = require_role("editor", "admin")
can_publish = require_role("admin")

READING_PARTS = (5, 6, 7)


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


# --- đề ---------------------------------------------------------------------


@router.get("/tests", response_model=list[TestAdmin])
def list_tests(db: Session = Depends(get_db), _: User = Depends(can_edit)) -> list[TestAdmin]:
    tests = db.scalars(select(PracticeTest).order_by(PracticeTest.created_at.desc())).all()
    return [_as_admin(db, test) for test in tests]


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
        time_limit_seconds=body.time_limit_seconds,
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


@router.get("/tests/{slug}/questions", response_model=list[QuestionAdmin])
def list_test_questions(
    slug: str, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[QuestionAdmin]:
    test = _test_or_404(db, slug)
    image_driver = get_driver("image")
    return [_question_admin(link, question, image_driver) for link, question in _rows(db, test.id)]


@router.post("/tests/{slug}/parts/{part}/parse", response_model=TestPartParseResponse)
def parse_part_paste(
    slug: str, part: int, body: ParseRequest, _: User = Depends(can_edit)
) -> TestPartParseResponse:
    """Phân tích nội dung dán và báo MỌI vấn đề. Không ghi gì (ADR-005 §3.4)."""
    if part not in READING_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lượt này mới làm Part {', '.join(map(str, READING_PARTS))}",
        )

    try:
        parsed = parse_reading_part(body.raw_text, part)
    except ValueError as problem:
        # 400 chứ không 500: nội dung dán sai định dạng là lỗi của dữ liệu vào,
        # và người dán cần đọc được câu giải thích chứ không phải "Internal
        # Server Error".
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(problem)
        ) from problem

    groups = [
        GroupDraft(
            line=group.line,
            title=group.title,
            passages=group.passages,
            problems=group.problems,
            questions=[
                QuestionDraft(
                    line=question.line,
                    prompt_text=question.prompt_text,
                    options=[
                        QuestionOptionDraft(
                            label=option.label,
                            content=option.content,
                            is_correct=option.is_correct,
                        )
                        for option in question.options
                    ],
                    source=question.source,
                    source_note=question.source_note,
                    explanation=question.explanation,
                    problems=question.problems,
                )
                for question in group.questions
            ],
        )
        for group in parsed
    ]
    ok = sum(
        1
        for group in groups
        if not group.problems and all(q.problems == [] for q in group.questions)
    )
    return TestPartParseResponse(
        part=part, ok_count=ok, error_count=len(groups) - ok, groups=groups
    )


@router.post("/tests/{slug}/parts", response_model=TestAdmin, status_code=status.HTTP_201_CREATED)
def commit_part(
    slug: str,
    body: TestPartCommit,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit),
) -> TestAdmin:
    """Ghi các cụm đã xem trước vào đề. Luôn ghi ở trạng thái `draft`."""
    if body.part not in READING_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lượt này mới làm Part {', '.join(map(str, READING_PARTS))}",
        )
    test = _test_or_404(db, slug)

    existing = _rows(db, test.id)
    next_position = max((link.position for link, _ in existing), default=0) + 1
    # Số câu tiếp nối trong khoảng của part, không phải nối vào cuối đề: câu Part
    # 5 thứ năm mang số 105 dù nó là câu được thêm sau cùng (ADR-007 §2.6).
    first, last = PART_NUMBER_RANGES[body.part]
    taken = {link.number for link, _ in existing}
    free = (number for number in range(first, last + 1) if number not in taken)

    created = 0
    for group in body.groups:
        if group.problems or any(question.problems for question in group.questions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cụm ở dòng {group.line} vẫn còn lỗi; sửa rồi phân tích lại",
            )

        stimulus: QuestionSet | None = None
        if body.part in (6, 7):
            passages = group.passages + [None, None, None]
            stimulus = QuestionSet(
                part=body.part,
                title=group.title,
                passage=passages[0],
                passage_2=passages[1],
                passage_3=passages[2],
                status="draft",
                created_by=user.id,
            )
            db.add(stimulus)
            db.flush()

        for draft in group.questions:
            try:
                number = next(free)
            except StopIteration:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Part {body.part} chỉ có {last - first + 1} chỗ "
                        f"({first}–{last}) và đã dùng hết"
                    ),
                ) from None

            question = Question(
                part=body.part,
                set_id=stimulus.id if stimulus is not None else None,
                prompt_text=draft.prompt_text,
                explanation=draft.explanation,
                # KHÔNG có giá trị mặc định ở đây, và không được thêm vào
                # (ADR-007 §2.5). Trình dán đã từ chối lô thiếu nó.
                source=draft.source,
                source_note=draft.source_note,
                status="draft",
                created_by=user.id,
                options=[
                    QuestionOption(
                        label=option.label, content=option.content, is_correct=option.is_correct
                    )
                    for option in draft.options
                ],
            )
            db.add(question)
            db.flush()

            problems = validate_question(question)
            if problems:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Câu ở dòng {draft.line}: {'; '.join(problems)}",
                )

            db.add(
                PracticeTestQuestion(
                    test_id=test.id,
                    question_id=question.id,
                    position=next_position,
                    number=number,
                )
            )
            next_position += 1
            created += 1

    if not created:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Không có câu nào để ghi"
        )
    db.commit()
    return _as_admin(db, test)


@router.get("/tests/{slug}/sets", response_model=list[SetAdmin])
def list_test_sets(
    slug: str, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[SetAdmin]:
    test = _test_or_404(db, slug)
    seen: dict[uuid.UUID, QuestionSet] = {}
    for _link, question in _rows(db, test.id):
        if question.question_set is not None:
            seen[question.question_set.id] = question.question_set
    driver = get_driver("image")
    images = _images_for(db, list(seen.values()))
    return [_set_admin(stimulus, images, driver) for stimulus in seen.values()]


@router.patch("/questions/{question_id}", response_model=QuestionAdmin)
def edit_question(
    question_id: uuid.UUID,
    body: QuestionEdit,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> QuestionAdmin:
    """Sửa một câu đã dán. Nửa sau của ADR-007 §2.3.

    Dán tạo hàng loạt; form sửa những thứ dán không diễn đạt được — đổi đáp án
    đúng, viết giải thích, sửa một lựa chọn gõ nhầm.
    """
    question = db.get(Question, question_id, options=[selectinload(Question.options)])
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có câu này")

    changes = body.model_dump(exclude_unset=True)

    contents = changes.pop("options", None)
    if contents:
        by_label = {option.label: option for option in question.options}
        for label, content in contents.items():
            if label not in by_label:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Câu này không có lựa chọn {label!r}",
                )
            by_label[label].content = content

    correct = changes.pop("correct_label", None)
    if correct:
        labels = {option.label for option in question.options}
        if correct not in labels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đáp án {correct!r} không có trong {sorted(labels)}",
            )
        for option in question.options:
            option.is_correct = option.label == correct

    for field_name, value in changes.items():
        setattr(question, field_name, value)

    problems = validate_question(question)
    if problems:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(problems))

    # Sửa một câu ĐÃ xuất bản sẽ đưa nó về nháp. Không phải để phiền: nội dung
    # đã tới tay người học vừa đổi, và người duyệt nó lần trước duyệt một thứ
    # khác. Cột `published_by` tồn tại để trả lời "ai cho cái này ra ngoài".
    if question.status == "published":
        question.status = "draft"
        question.published_by = None
        question.published_at = None

    db.commit()
    link = db.scalars(
        select(PracticeTestQuestion).where(PracticeTestQuestion.question_id == question.id)
    ).first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Câu này chưa thuộc đề nào"
        )
    return _question_admin(link, question, get_driver("image"))


@router.post("/question-sets/{set_id}/passage-image", response_model=SetAdmin)
def assign_passage_image(
    set_id: uuid.UUID,
    body: PassageImageAssign,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> SetAdmin:
    """Gắn hoặc gỡ ảnh cho một ô ngữ liệu (ADR-007 §2.3b)."""
    stimulus = db.get(QuestionSet, set_id)
    if stimulus is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có cụm này")
    # Chỉ Part 7 có ảnh. Part 6 là Text Completion: **một** đoạn văn có các chỗ
    # trống, và nội dung của nó là chữ — không có biểu đồ hay sơ đồ nào để gắn.
    # Cho phép gắn ở đây là mở một đường tạo ra cụm không tồn tại trong đề thật.
    if stimulus.part != 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Chỉ Part 7 có ảnh ngữ liệu; cụm này là Part {stimulus.part}. "
                "Part 6 là một đoạn văn có các chỗ trống, toàn chữ."
            ),
        )
    if body.slot not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ô ngữ liệu phải là 1, 2 hoặc 3"
        )

    column = _PASSAGE_IMAGE_COLUMNS[body.slot]
    if body.image_id is None:
        setattr(stimulus, column, None)
    else:
        asset = db.get(ImageAsset, uuid.UUID(body.image_id))
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có ảnh này")
        # Ảnh làm ngữ liệu BẮT BUỘC có chữ thay ảnh, khác với ảnh Part 1.
        #
        # Ở Part 1 nội dung ảnh chính là thứ không được mô tả quá kỹ — mô tả kỹ
        # là lộ đáp án. Ở Part 6/7 thì ngược hẳn: ảnh *là* ngữ liệu, nên thiếu
        # chữ thay ảnh là một câu hỏi mà người dùng máy đọc màn hình không trả
        # lời được. Đó không phải bất tiện, đó là không làm được bài.
        if not (asset.alt_text or "").strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Ảnh này chưa có chữ thay ảnh (alt text). Ảnh làm ngữ liệu bắt buộc "
                    "phải có, vì nó là nội dung người học cần đọc — thêm ở Thư viện ảnh "
                    "rồi quay lại."
                ),
            )
        setattr(stimulus, column, asset.id)

    db.commit()
    return _set_admin(stimulus, _images_for(db, [stimulus]), get_driver("image"))


@router.post("/questions/{question_id}/publish", response_model=QuestionAdmin)
def publish_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(can_publish),
) -> QuestionAdmin:
    question = db.get(Question, question_id, options=[selectinload(Question.options)])
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có câu này")

    problems = validate_question(question)
    if problems:
        # Từ chối NÊU RÕ vì sao. Một lời từ chối chỉ xong khi thứ nó đòi hỏi
        # nằm trong tầm với của người đang đọc nó.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="; ".join(problems))

    question.status = "published"
    question.published_by = user.id
    question.published_at = datetime.now(UTC)
    if question.question_set is not None:
        question.question_set.status = "published"
        question.question_set.published_by = user.id
        question.question_set.published_at = datetime.now(UTC)
    db.commit()

    link = db.scalars(
        select(PracticeTestQuestion).where(PracticeTestQuestion.question_id == question.id)
    ).first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Câu này chưa thuộc đề nào"
        )
    return _question_admin(link, question, get_driver("image"))


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


def _question_admin(
    link: PracticeTestQuestion, question: Question, image_driver: object
) -> QuestionAdmin:
    stimulus = question.question_set
    audio_id = question.audio_asset_id or (stimulus.audio_asset_id if stimulus else None)
    return QuestionAdmin(
        id=str(question.id),
        part=question.part,
        number=link.number,
        position=link.position,
        prompt_text=question.prompt_text,
        options=[
            QuestionOptionDraft(
                label=option.label, content=option.content or "", is_correct=option.is_correct
            )
            for option in sorted(question.options, key=lambda option: option.label)
        ],
        source=question.source,
        explanation=question.explanation,
        status=question.status,
        set_id=str(stimulus.id) if stimulus else None,
        # URL dựng bằng nối chuỗi, không gọi object store lúc có request.
        audio_url=public_audio_url(f"audio/{audio_id}") if audio_id else None,
        image_url=None,
        problems=validate_question(question),
    )


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


_PASSAGE_IMAGE_COLUMNS = {
    1: "passage_image_id",
    2: "passage_2_image_id",
    3: "passage_3_image_id",
}
_PASSAGE_TEXT_COLUMNS = {1: "passage", 2: "passage_2", 3: "passage_3"}


def _images_for(db: Session, sets: list[QuestionSet]) -> dict[uuid.UUID, ImageAsset]:
    ids = {
        asset_id
        for stimulus in sets
        for asset_id in (
            stimulus.passage_image_id,
            stimulus.passage_2_image_id,
            stimulus.passage_3_image_id,
        )
        if asset_id
    }
    if not ids:
        return {}
    return {
        asset.id: asset
        for asset in db.scalars(select(ImageAsset).where(ImageAsset.id.in_(ids))).all()
    }


def _set_admin(
    stimulus: QuestionSet, images: dict[uuid.UUID, ImageAsset], driver: StorageDriver
) -> SetAdmin:
    passages: list[PassageAdmin] = []
    for slot in (1, 2, 3):
        text = getattr(stimulus, _PASSAGE_TEXT_COLUMNS[slot])
        image_id = getattr(stimulus, _PASSAGE_IMAGE_COLUMNS[slot])
        asset = images.get(image_id) if image_id else None
        # Ô rỗng vẫn trả về: người soạn cần một chỗ trống để bấm vào mà gắn ảnh.
        passages.append(
            PassageAdmin(
                slot=slot,
                text=text,
                image_id=str(asset.id) if asset else None,
                image_url=driver.public_url(asset.storage_key) if asset else None,
                image_alt=asset.alt_text if asset else None,
            )
        )
    return SetAdmin(
        id=str(stimulus.id),
        part=stimulus.part,
        title=stimulus.title,
        status=stimulus.status,
        passages=passages,
    )
