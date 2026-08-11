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
from app.core.media import LOGICAL_VOICE_ACCENTS, public_audio_url, script_fingerprint
from app.core.storage import StorageDriver, get_driver
from app.models import (
    AudioAsset,
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
    MediaAssign,
    ParseRequest,
    PassageAdmin,
    PassageImageAssign,
    QuestionAdmin,
    QuestionDraft,
    QuestionEdit,
    QuestionOptionDraft,
    SetAdmin,
    SetEdit,
    TestAdmin,
    TestCreate,
    TestPartCommit,
    TestPartParseResponse,
    TestPartSummary,
    TestUpdate,
    TurnDraft,
    VoiceOption,
)
from app.schemas.practice import PART_NUMBER_RANGES, PART_TITLES, section_of
from app.services.content_import import parse_listening_part, parse_reading_part

router = APIRouter(prefix="/admin", tags=["admin"])

can_edit = require_role("editor", "admin")
can_publish = require_role("admin")

READING_PARTS = (5, 6, 7)
LISTENING_PARTS = (1, 2, 3, 4)
# Part 3, 4, 6, 7 gom nhiều câu dưới một ngữ liệu dùng chung; ba part còn lại
# thì mỗi câu đứng riêng (ADR-001 §A2).
GROUPED_PARTS = (3, 4, 6, 7)


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


@router.get("/voices", response_model=list[VoiceOption])
def list_voices(_: User = Depends(can_edit)) -> list[VoiceOption]:
    """Các giọng dùng được, cho ô chọn giọng lúc sửa lời thoại.

    Đi qua API chứ không chép sang frontend: chép là hai danh sách, và cái chép
    sẽ trôi khỏi `LOGICAL_VOICE_ACCENTS` mà không gì báo — người soạn chọn một
    giọng có trong dropdown rồi ăn 400 từ chính server vừa gửi dropdown đó.

    `LOGICAL_VOICE_ACCENTS` nằm ở `app/core/media.py` chứ không ở
    `app/content/tts.py` chính vì lúc này: không gì với tới được từ `app.main`
    mà import `app.content` (A4.1).
    """
    return [
        VoiceOption(name=name, accent=accent)
        for name, accent in sorted(LOGICAL_VOICE_ACCENTS.items())
    ]


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
    if part not in (*LISTENING_PARTS, *READING_PARTS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Part phải từ 1 đến 7")

    try:
        parsed = (
            parse_listening_part(body.raw_text, part)
            if part in LISTENING_PARTS
            else parse_reading_part(body.raw_text, part)
        )
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
            script=[TurnDraft(text=turn.text, voice=turn.voice) for turn in group.script],
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
                    script=[
                        TurnDraft(text=turn.text, voice=turn.voice) for turn in question.script
                    ],
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
    if body.part not in (*LISTENING_PARTS, *READING_PARTS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Part phải từ 1 đến 7")
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
        if body.part in GROUPED_PARTS:
            passages = group.passages + [None, None, None]
            stimulus = QuestionSet(
                part=body.part,
                title=group.title,
                passage=passages[0],
                passage_2=passages[1],
                passage_3=passages[2],
                # Part 3 và 4 gắn bản thu ở CỤM, không ở từng câu (ADR-001 A4.3):
                # một bài nói dùng chung cho ba câu, nên lời thoại cũng vậy.
                audio_script=(
                    [{"text": turn.text, "voice": turn.voice} for turn in group.script] or None
                ),
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
                # Part 1 và 2: lời thoại nằm trên chính câu, vì mỗi câu là một
                # bản thu riêng và không có cụm nào để treo nó lên.
                audio_script=(
                    [{"text": turn.text, "voice": turn.voice} for turn in draft.script] or None
                ),
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

            # Lọc bỏ lỗi thiếu media: lúc vừa dán thì chưa ai gắn audio hay ảnh
            # được, và chặn ở đây sẽ khiến Part 1-4 không bao giờ ghi vào được.
            # Cổng chặn thật nằm ở bước xuất bản, nơi `validate_question` chạy
            # đầy đủ — cùng luật đã áp cho vocabulary và dictation.
            problems = _authoring_problems(question)
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

    # Lời thoại chỉ nằm trên CÂU ở Part 1 và 2. Part 3/4 treo nó ở cụm vì cả cụm
    # dùng chung một bản thu, nên ghi vào đây sẽ tạo ra một lời thoại thứ hai mà
    # không bản thu nào ứng với — và người soát sẽ tin vào cái sai.
    if "audio_script" in changes:
        if question.part in (3, 4):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Part 3 và 4 dùng chung một bản thu cho cả cụm nên lời thoại ở cụm; "
                    f"sửa tại PATCH /admin/question-sets/{question.set_id}"
                ),
            )
        if question.part not in (1, 2):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Part {question.part} không có bản thu nên không có lời thoại",
            )
        changes["audio_script"] = _script_or_400(body.audio_script or [])

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

    # Cùng bộ lọc như lúc ghi, và vì cùng một lý do: bản thu chưa gắn thì mọi
    # câu Part 1-4 đều "thiếu audio", nên soát đủ ở đây sẽ khiến một lỗi chính
    # tả trong lời thoại không sửa được cho tới khi đã thu xong — tức là phải
    # thu lại. Cổng chặn thật vẫn ở bước xuất bản.
    problems = _authoring_problems(question)
    if problems:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(problems))

    # Sửa một câu ĐÃ xuất bản sẽ đưa nó về nháp. Không phải để phiền: nội dung
    # đã tới tay người học vừa đổi, và người duyệt nó lần trước duyệt một thứ
    # khác. Cột `published_by` tồn tại để trả lời "ai cho cái này ra ngoài".
    _demote(question)

    db.commit()
    link = db.scalars(
        select(PracticeTestQuestion).where(PracticeTestQuestion.question_id == question.id)
    ).first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Câu này chưa thuộc đề nào"
        )
    return _question_admin(link, question, get_driver("image"))


@router.patch("/question-sets/{set_id}", response_model=SetAdmin)
def edit_set(
    set_id: uuid.UUID,
    body: SetEdit,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> SetAdmin:
    """Sửa một cụm đã dán: tên cụm và lời thoại.

    Lời thoại phải sửa được. Không có endpoint này thì sai một chữ trong bài nói
    Part 3 chỉ còn cách xoá cả cụm rồi dán lại — kéo theo mất số câu đã cấp và
    bản thu đã gắn.

    Nó cũng là thứ làm cảnh báo `audio_may_be_stale` chạy được ở Part 3/4. Bản
    thu ứng với LỜI THOẠI, không ứng với chữ trên từng câu; chừng nào lời thoại
    còn bất biến thì `updated_at` của cụm không bao giờ vượt `audio_attached_at`
    và cảnh báo im lặng vĩnh viễn — đúng, nhưng vô dụng.
    """
    stimulus = db.get(QuestionSet, set_id)
    if stimulus is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có cụm này")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return _set_admin(stimulus, _images_for(db, [stimulus]), get_driver("image"))

    if "audio_script" in changes:
        if stimulus.part not in (3, 4):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Part {stimulus.part} không có bản thu nên không có lời thoại",
            )
        stimulus.audio_script = _script_or_400(body.audio_script or [])
    if "title" in changes:
        stimulus.title = body.title

    # Hạ cả cụm LẪN các câu thuộc nó về nháp. Sửa lời thoại là sửa thứ người học
    # đang nghe, và người duyệt lần trước đã duyệt một bài nói khác — trong khi
    # cổng xuất bản chỉ soát từng câu, nên không hạ câu xuống thì cụm về nháp mà
    # các câu vẫn nằm trong đề đã phát hành.
    _demote(stimulus)
    for question in db.scalars(select(Question).where(Question.set_id == stimulus.id)):
        _demote(question)

    db.commit()
    db.refresh(stimulus)
    return _set_admin(stimulus, _images_for(db, [stimulus]), get_driver("image"))


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
    # Part 3, 4 và 7 — không phải chỉ Part 7.
    #
    # Vài cụm cuối Part 3 và Part 4 có một hình đi kèm (bảng giá, lịch trình, sơ
    # đồ mặt bằng) và một câu trong cụm nói "Look at the graphic". Hình đó là
    # ngữ liệu DÙNG CHUNG của cả cụm, đúng như đoạn văn của Part 7: đề in nó một
    # lần cạnh cả ba câu. Nên nó về `question_set`, không về `question` — chỗ
    # ảnh Part 1 ở, nơi mỗi câu có ảnh riêng.
    #
    # Part 6 vẫn không: Text Completion là **một** đoạn văn có các chỗ trống,
    # toàn chữ. Part 1 cũng không, vì ảnh của nó ở trên câu.
    if stimulus.part not in (3, 4, 7):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Part {stimulus.part} không có ảnh ngữ liệu. "
                "Part 1 gắn ảnh trên CÂU; Part 6 là một đoạn văn có chỗ trống, toàn chữ."
            ),
        )
    # Part 7 tối đa ba ngữ liệu (email, thư trả lời, lịch trình). Part 3 và 4
    # chỉ có đúng một hình — mở ba ô ở đó là mời người soạn điền vào hai ô không
    # tồn tại trong đề thật, cùng lỗi đã sửa cho Part 6.
    max_slot = 3 if stimulus.part == 7 else 1
    if body.slot not in range(1, max_slot + 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Ô ngữ liệu phải là 1, 2 hoặc 3"
                if max_slot == 3
                else f"Cụm Part {stimulus.part} chỉ có một hình, nên ô phải là 1"
            ),
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


@router.post("/questions/{question_id}/audio", response_model=QuestionAdmin)
def assign_question_audio(
    question_id: uuid.UUID,
    body: MediaAssign,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> QuestionAdmin:
    """Gắn bản thu cho một câu — Part 1 và 2, nơi mỗi câu là một clip riêng."""
    question = db.get(Question, question_id, options=[selectinload(Question.options)])
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có câu này")
    if question.part not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Part {question.part} gắn bản thu ở CỤM, không ở từng câu — "
                "một bài nói dùng chung cho nhiều câu (ADR-001 §A4.3)."
            ),
        )
    question.audio_asset_id = _asset_or_404(db, AudioAsset, body.asset_id)
    # Ghi lại lời thoại tại lúc gắn, để sau này biết bản thu còn ứng với nó
    # không. Không phải cổng chặn: hash của file tải lên băm một id ngẫu nhiên
    # nên không suy ngược ra lời thoại được, và thứ duy nhất làm được là cho
    # người ta NHÌN THẤY (ADR-007 §2.7).
    _record_attachment(question, attached=bool(body.asset_id))
    db.commit()
    return _question_admin(_link_or_409(db, question.id), question, get_driver("image"))


@router.post("/question-sets/{set_id}/audio", response_model=SetAdmin)
def assign_set_audio(
    set_id: uuid.UUID,
    body: MediaAssign,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> SetAdmin:
    """Gắn bản thu cho cả cụm — Part 3 và 4."""
    stimulus = db.get(QuestionSet, set_id)
    if stimulus is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có cụm này")
    if stimulus.part not in (3, 4):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cụm Part {stimulus.part} không mang bản thu",
        )
    stimulus.audio_asset_id = _asset_or_404(db, AudioAsset, body.asset_id)
    _record_attachment(stimulus, attached=bool(body.asset_id))
    db.commit()
    return _set_admin(stimulus, _images_for(db, [stimulus]), get_driver("image"))


@router.post("/questions/{question_id}/image", response_model=QuestionAdmin)
def assign_question_image(
    question_id: uuid.UUID,
    body: MediaAssign,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> QuestionAdmin:
    """Gắn bức ảnh của câu Part 1, chọn từ thư viện (ADR-007 §2.4)."""
    question = db.get(Question, question_id, options=[selectinload(Question.options)])
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có câu này")
    if question.part != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ Part 1 có ảnh trên câu; câu này là Part {question.part}",
        )
    question.image_asset_id = _asset_or_404(db, ImageAsset, body.asset_id)
    db.commit()
    return _question_admin(_link_or_409(db, question.id), question, get_driver("image"))


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
    link: PracticeTestQuestion,
    question: Question,
    image_driver: StorageDriver,
    assets: dict[uuid.UUID, AudioAsset | ImageAsset] | None = None,
) -> QuestionAdmin:
    stimulus = question.question_set
    # Ai đang giữ bản thu của câu này: chính nó (Part 1, 2) hay cụm (Part 3, 4).
    owner: Question | QuestionSet = (
        stimulus if question.part in (3, 4) and stimulus is not None else question
    )
    lookup: dict[uuid.UUID, AudioAsset | ImageAsset] = assets or {}
    audio_id = question.audio_asset_id or (stimulus.audio_asset_id if stimulus else None)
    audio = lookup.get(audio_id) if audio_id else None
    image = lookup.get(question.image_asset_id) if question.image_asset_id else None
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
        # URL dựng từ `storage_key` THẬT, nối chuỗi, không gọi object store lúc
        # có request. Bản đầu nối id của asset vào `audio/` — một URL trông hợp
        # lệ và luôn 404, mà 404 của audio thì chỉ lộ ra khi có người bấm phát.
        audio_url=public_audio_url(audio.storage_key) if audio else None,
        image_url=image_driver.public_url(image.storage_key) if image else None,
        # Part 3/4 treo bản thu VÀ lời thoại ở cụm, nên ba trường dưới phải đọc
        # từ cụm. Đọc từ câu thì chúng luôn rỗng và `audio_may_be_stale` luôn
        # False — cảnh báo đúng luật mà không bao giờ hiện, ở đúng chỗ người
        # soạn nhìn vào nhiều nhất là danh sách câu.
        audio_script=_turns(owner.audio_script),
        audio_attached_at=owner.audio_attached_at,
        updated_at=owner.updated_at,
        audio_may_be_stale=_may_be_stale(owner),
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


def _images_for(db: Session, sets: list[QuestionSet]) -> dict[uuid.UUID, ImageAsset | AudioAsset]:
    """Ảnh ngữ liệu VÀ bản thu của các cụm, nạp một lượt.

    Tra lẻ từng ô sẽ là bốn lượt đi lại database cho mỗi cụm, và một đề đầy đủ
    có hàng chục cụm.
    """
    image_ids = {
        asset_id
        for stimulus in sets
        for asset_id in (
            stimulus.passage_image_id,
            stimulus.passage_2_image_id,
            stimulus.passage_3_image_id,
        )
        if asset_id
    }
    audio_ids = {s.audio_asset_id for s in sets if s.audio_asset_id}
    return _load_assets(db, image_ids, audio_ids)


def _assets_for(db: Session, questions: list[Question]) -> dict[uuid.UUID, ImageAsset | AudioAsset]:
    image_ids = {q.image_asset_id for q in questions if q.image_asset_id}
    audio_ids = {q.audio_asset_id for q in questions if q.audio_asset_id} | {
        q.question_set.audio_asset_id
        for q in questions
        if q.question_set is not None and q.question_set.audio_asset_id
    }
    return _load_assets(db, image_ids, audio_ids)


def _load_assets(
    db: Session, image_ids: set[uuid.UUID], audio_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ImageAsset | AudioAsset]:
    out: dict[uuid.UUID, ImageAsset | AudioAsset] = {}
    if image_ids:
        out.update(
            {a.id: a for a in db.scalars(select(ImageAsset).where(ImageAsset.id.in_(image_ids)))}
        )
    if audio_ids:
        out.update(
            {a.id: a for a in db.scalars(select(AudioAsset).where(AudioAsset.id.in_(audio_ids)))}
        )
    return out


def _set_admin(
    stimulus: QuestionSet,
    images: dict[uuid.UUID, ImageAsset | AudioAsset],
    driver: StorageDriver,
) -> SetAdmin:
    passages: list[PassageAdmin] = []
    for slot in (1, 2, 3):
        text = getattr(stimulus, _PASSAGE_TEXT_COLUMNS[slot])
        image_id = getattr(stimulus, _PASSAGE_IMAGE_COLUMNS[slot])
        found = images.get(image_id) if image_id else None
        # Thu hẹp kiểu tường minh: bản đồ asset chứa cả ảnh lẫn audio, và một
        # `image_id` trỏ vào bản thu là dữ liệu hỏng chứ không phải chuyện bình
        # thường — bỏ qua còn hơn dựng một ô ngữ liệu không có chữ thay ảnh.
        asset = found if isinstance(found, ImageAsset) else None
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
    audio = images.get(stimulus.audio_asset_id) if stimulus.audio_asset_id else None
    return SetAdmin(
        id=str(stimulus.id),
        part=stimulus.part,
        title=stimulus.title,
        status=stimulus.status,
        passages=passages,
        audio_url=public_audio_url(audio.storage_key) if audio else None,
        audio_script=_turns(stimulus.audio_script),
        audio_attached_at=stimulus.audio_attached_at,
        updated_at=stimulus.updated_at,
        audio_may_be_stale=_may_be_stale(stimulus),
    )


def _asset_or_404(db: Session, model: type, asset_id: str | None) -> uuid.UUID | None:
    if asset_id is None:
        return None
    asset = db.get(model, uuid.UUID(asset_id))
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có asset này")
    return uuid.UUID(asset_id)


def _link_or_409(db: Session, question_id: uuid.UUID) -> PracticeTestQuestion:
    link = db.scalars(
        select(PracticeTestQuestion).where(PracticeTestQuestion.question_id == question_id)
    ).first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Câu này chưa thuộc đề nào"
        )
    return link


def _turns(script: list[dict[str, str]] | None) -> list[TurnDraft]:
    return [TurnDraft(text=turn["text"], voice=turn["voice"]) for turn in script or []]


def _authoring_problems(question: Question) -> list[str]:
    """Lỗi nội dung, trừ những lỗi chỉ media mới chữa được.

    Lúc đang soạn thì chưa ai gắn audio hay ảnh được, nên chặn vì thiếu chúng sẽ
    khiến Part 1-4 không bao giờ ghi hay sửa được. Cổng chặn đầy đủ nằm ở bước
    xuất bản, nơi `validate_question` chạy trọn vẹn — cùng luật đã áp cho
    vocabulary và dictation.
    """
    return [
        problem
        for problem in validate_question(question)
        if "audio" not in problem and "photograph" not in problem
    ]


def _demote(row: Question | QuestionSet) -> None:
    """Đưa nội dung đã xuất bản về nháp sau khi sửa.

    Không phải để phiền: thứ đã tới tay người học vừa đổi, và người duyệt nó lần
    trước duyệt một thứ khác. `published_by` tồn tại để trả lời "ai cho cái này
    ra ngoài", nên giữ lại tên người duyệt bản cũ là ghi sai chính câu đó.
    """
    if row.status == "published":
        row.status = "draft"
        row.published_by = None
        row.published_at = None


def _script_or_400(turns: list[TurnDraft]) -> list[dict[str, str]] | None:
    """Đổi lời thoại từ form sang hình dạng lưu, từ chối giọng không có thật.

    Tên giọng sai không gây lỗi gì ở đây — nó chỉ nổ ở bước sinh audio, cách chỗ
    gõ vào hàng ngày, trong một lô dài mà một clip hỏng dễ trôi qua. Chặn ngay
    lúc gõ, khi người soạn còn nhớ mình vừa gõ gì.

    Kiểm theo `LOGICAL_VOICE_ACCENTS` ở `app/core/media.py` chứ không theo
    `LOGICAL_VOICES` của `app/content/tts.py`: không gì với tới được từ
    `app.main` mà import `app.content` (A4.1), và đó chính là lý do bảng tên
    giọng đã được dời sang `core`.

    Danh sách rỗng trả về None, không phải `[]`: cột nullable, và "không có lời
    thoại" chỉ nên có một cách viết trong database.
    """
    cleaned: list[dict[str, str]] = []
    for index, turn in enumerate(turns, start=1):
        text = turn.text.strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lượt nói {index} không có chữ nào",
            )
        if turn.voice not in LOGICAL_VOICE_ACCENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Lượt nói {index}: không có giọng {turn.voice!r}. "
                    f"Các giọng dùng được: {', '.join(sorted(LOGICAL_VOICE_ACCENTS))}"
                ),
            )
        cleaned.append({"text": text, "voice": turn.voice})
    return cleaned or None


def _record_attachment(row: Question | QuestionSet, *, attached: bool) -> None:
    """Chốt "bản thu này được gắn cho lời thoại nào" ngay lúc gắn."""
    row.audio_attached_at = datetime.now(UTC) if attached else None
    row.audio_script_hash = _fingerprint(row.audio_script) if attached else None


def _fingerprint(script: list[dict[str, str]] | None) -> str | None:
    return script_fingerprint([(turn["text"], turn["voice"]) for turn in script or []])


def _may_be_stale(row: Question | QuestionSet) -> bool:
    """Bản thu đang gắn có còn ứng với lời thoại hiện tại không.

    Chưa gắn gì thì không có gì để lệch. Còn lại là một phép so vân tay, không
    phải so hai mốc thời gian: `audio_attached_at` do đồng hồ Python ghi còn
    `updated_at` do đồng hồ database ghi, nên phiên bản cũ của hàm này phụ thuộc
    hai chiếc đồng hồ khớp nhau, và trên SQLite — độ phân giải một giây — sửa
    ngay sau khi gắn thì nó im lặng. Chi tiết ở `script_fingerprint`.

    Đổi lại còn chính xác hơn: nó chỉ kêu khi thứ bản thu ứng với thật sự đổi.
    Sửa một dấu phẩy trong phần giải thích không còn báo lệch oan, mà cảnh báo
    oan là cách nhanh nhất dạy người ta bấm bỏ qua mọi cảnh báo.
    """
    if row.audio_asset_id is None:
        return False
    return row.audio_script_hash != _fingerprint(row.audio_script)
