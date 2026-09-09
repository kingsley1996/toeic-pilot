"""Quản trị module NGỮ PHÁP: chủ đề, bài học, và câu gắn vào bài.

Theo khuôn `admin_dictation`: editor viết, admin phát hành, publish là endpoint
riêng, PATCH phân biệt "không đụng tới" với "đặt về rỗng" qua `_apply`.

Hai cổng riêng của module này, cả hai chặn lỗi hỏng im lặng:

- Publish **chủ đề** đòi ≥1 bài đã publish — đừng mở trang trống. (Ngưỡng ≥12
  câu trong kho nhãn từng chặn ở đây đã BỎ 2026-09-06: lý thuyết đứng được một
  mình, chủ đề mỏng câu hỏi là quyết định biên tập chứ không phải lỗi.)
- Publish **bài học** đòi body không trống — trang lý thuyết rỗng hiện ra như
  bài hỏng chứ không như bài chưa soạn xong.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.routes._admin_content import _apply
from app.core import rate_limit
from app.core.database import get_db
from app.core.media import (
    VIDEO_KEY_PREFIX,
    public_video_url,
    upload_source_hash,
    video_storage_key_for,
)
from app.core.storage import StorageError, get_driver
from app.models import (
    GrammarLesson,
    GrammarLessonQuestion,
    GrammarTopic,
    Question,
    QuestionLabel,
    QuestionOption,
    User,
)
from app.models.validators import validate_question
from app.schemas.admin import (
    GrammarLessonAdmin,
    GrammarLessonCreate,
    GrammarLessonOrder,
    GrammarLessonQuestions,
    GrammarLessonUpdate,
    GrammarQuestionDraft,
    GrammarTopicAdmin,
    GrammarTopicCreate,
    GrammarTopicOrder,
    GrammarTopicUpdate,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.schemas.media import UploadTicket, VideoConfirm, VideoTicketRequest
from app.services.labels import FACETS

router = APIRouter(prefix="/admin", tags=["admin"])

can_edit = require_role("editor", "admin")
can_publish = require_role("admin")

# Mã grammar hợp lệ lấy từ registry — cùng nguồn `enrich_skills` và
# `bp.validate` dùng. Một danh sách chép tay ở đây sẽ là chỗ thứ hai phải sửa
# khi taxonomy đổi, và chỗ thứ hai sẽ không ai nhớ (`SPEC-GRAMMAR.md` §1).
GRAMMAR_CODES = {label.code for facet in FACETS if facet.key == "grammar" for label in facet.labels}


def _grammar_question_count(db: Session, code: str) -> int:
    """Số câu PUBLISHED mang nhãn grammar `code`, ở đúng part nhãn cho phép.

    Lọc `Question.status == published` ở đây chứ không chỉ đếm hàng
    `question_label`: một câu nháp mang nhãn không phải bài tập người học làm
    được, và cổng publish đo sai thì chủ đề lọt qua với số câu ảo.
    """
    return (
        db.scalar(
            select(func.count(Question.id))
            .join(QuestionLabel, QuestionLabel.question_id == Question.id)
            .where(
                QuestionLabel.facet == "grammar",
                QuestionLabel.code == code,
                Question.status == "published",
            )
        )
        or 0
    )


def _grammar_codes_by_question(db: Session, codes: list[str]) -> dict[str, int]:
    """Một truy vấn cho cả trang danh sách — đếm từng mã một là N+1."""
    if not codes:
        return {}
    rows = db.execute(
        select(QuestionLabel.code, func.count(func.distinct(Question.id)))
        .join(Question, Question.id == QuestionLabel.question_id)
        .where(
            QuestionLabel.facet == "grammar",
            QuestionLabel.code.in_(codes),
            Question.status == "published",
        )
        .group_by(QuestionLabel.code)
    ).all()
    return {code: count for code, count in rows}


def _topic_admin(db: Session, topic: GrammarTopic) -> GrammarTopicAdmin:
    lesson_count = (
        db.scalar(select(func.count(GrammarLesson.id)).where(GrammarLesson.topic_id == topic.id))
        or 0
    )
    return GrammarTopicAdmin(
        id=str(topic.id),
        code=topic.code,
        slug=topic.slug,
        title=topic.title,
        summary=topic.summary,
        position=topic.position,
        status=topic.status,
        lesson_count=lesson_count,
        question_count=_grammar_question_count(db, topic.code) if topic.code else 0,
    )


def _lesson_admin(db: Session, lesson: GrammarLesson) -> GrammarLessonAdmin:
    topic = db.get(GrammarTopic, lesson.topic_id)
    attached = list(
        db.scalars(
            select(GrammarLessonQuestion.question_id)
            .where(GrammarLessonQuestion.lesson_id == lesson.id)
            .order_by(GrammarLessonQuestion.position)
        )
    )
    return GrammarLessonAdmin(
        id=str(lesson.id),
        topic_id=str(lesson.topic_id),
        topic_title=topic.title if topic else "",
        slug=lesson.slug,
        title=lesson.title,
        kind=lesson.kind,
        body=lesson.body,
        position=lesson.position,
        status=lesson.status,
        question_count=len(attached),
        question_ids=[str(question_id) for question_id in attached],
        video_url=public_video_url(lesson.video_storage_key) if lesson.video_storage_key else None,
        video_duration_s=lesson.video_duration_s,
    )


def _check_code(code: str | None) -> None:
    if code is not None and code not in GRAMMAR_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"`{code}` không phải mã grammar của taxonomy. "
                f"Danh sách: {', '.join(sorted(GRAMMAR_CODES))}."
            ),
        )


# --- chủ đề ------------------------------------------------------------------


@router.get("/grammar/topics", response_model=Page[GrammarTopicAdmin])
def list_grammar_topics(
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[GrammarTopicAdmin]:
    total = count_rows(db, select(GrammarTopic.id))
    topics = list(
        db.scalars(
            select(GrammarTopic)
            .order_by(GrammarTopic.position, GrammarTopic.id)
            .limit(limit)
            .offset(offset)
        )
    )
    counts = _grammar_codes_by_question(db, [t.code for t in topics if t.code])
    lesson_counts: dict[uuid.UUID, int] = {
        topic_id: count
        for topic_id, count in db.execute(
            select(GrammarLesson.topic_id, func.count(GrammarLesson.id)).group_by(
                GrammarLesson.topic_id
            )
        ).all()
    }
    rows = [
        GrammarTopicAdmin(
            id=str(t.id),
            code=t.code,
            slug=t.slug,
            title=t.title,
            summary=t.summary,
            position=t.position,
            status=t.status,
            lesson_count=lesson_counts.get(t.id, 0),
            question_count=counts.get(t.code, 0) if t.code else 0,
        )
        for t in topics
    ]
    return page_of(rows, total, limit, offset)


@router.post(
    "/grammar/topics", response_model=GrammarTopicAdmin, status_code=status.HTTP_201_CREATED
)
def create_grammar_topic(
    body: GrammarTopicCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> GrammarTopicAdmin:
    _check_code(body.code)
    topic = GrammarTopic(
        code=body.code,
        slug=body.slug,
        title=body.title,
        summary=body.summary,
        position=body.position,
        status="draft",
        created_by=user.id,
    )
    db.add(topic)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Code hoặc slug đã tồn tại — mỗi mã grammar chỉ một chủ đề.",
        ) from None
    db.refresh(topic)
    return _topic_admin(db, topic)


@router.patch("/grammar/topics/{topic_id}", response_model=GrammarTopicAdmin)
def update_grammar_topic(
    topic_id: uuid.UUID,
    body: GrammarTopicUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> GrammarTopicAdmin:
    topic = db.get(GrammarTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if body.code is not None:
        _check_code(body.code)
    _apply(topic, body, ("code", "slug", "title", "summary", "position", "status"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Code hoặc slug đã tồn tại"
        ) from None
    db.refresh(topic)
    return _topic_admin(db, topic)


@router.post("/grammar/topics/{topic_id}/publish", response_model=GrammarTopicAdmin)
def publish_grammar_topic(
    topic_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> GrammarTopicAdmin:
    topic = db.get(GrammarTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    # Cổng duy nhất: đừng mở trang trống. Ngưỡng ≥12 câu từng chặn publish đã
    # BỎ — lý thuyết đứng được một mình, bài tập là lựa chọn biên tập chứ không
    # phải điều kiện tồn tại của chủ đề (SPEC-GRAMMAR §2, đổi 2026-09-06).
    published_lessons = (
        db.scalar(
            select(func.count(GrammarLesson.id)).where(
                GrammarLesson.topic_id == topic.id, GrammarLesson.status == "published"
            )
        )
        or 0
    )
    if not published_lessons:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chưa có bài nào đã publish — chủ đề mở ra sẽ là trang trống.",
        )
    topic.status = "published"
    topic.published_by = user.id
    topic.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(topic)
    return _topic_admin(db, topic)


@router.delete("/grammar/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grammar_topic(
    topic_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    topic = db.get(GrammarTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    # Lessons cascade theo ORM; attempt không bị chạm tới — nó tham chiếu
    # `question`, không tham chiếu chủ đề.
    db.delete(topic)
    db.commit()


@router.put("/grammar/topics/order", response_model=list[GrammarTopicAdmin])
def reorder_grammar_topics(
    body: GrammarTopicOrder,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> list[GrammarTopicAdmin]:
    """Gán lại thứ tự TOÀN BỘ chủ đề — cùng kiểu `StoryReorder`/order của lesson:
    một giao dịch gán 1..N, danh sách phải phủ đủ cây."""
    ids = [uuid.UUID(topic_id) for topic_id in body.topic_ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="topic_ids trùng nhau"
        )
    existing_ids = set(db.scalars(select(GrammarTopic.id)))
    missing = existing_ids - set(ids)
    unknown = set(ids) - existing_ids
    if missing or unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "order phải là ĐỦ số chủ đề — "
                f"thiếu: {', '.join(str(i) for i in missing)}; "
                f"không tồn tại: {', '.join(str(i) for i in unknown)}"
            ),
        )
    topics = list(db.scalars(select(GrammarTopic).where(GrammarTopic.id.in_(ids))))
    by_id = {topic.id: topic for topic in topics}
    for position, topic_id in enumerate(ids, start=1):
        by_id[topic_id].position = position
    db.commit()
    return [_topic_admin(db, by_id[topic_id]) for topic_id in ids]


# --- bài học -----------------------------------------------------------------


@router.get("/grammar/lessons", response_model=Page[GrammarLessonAdmin])
def list_grammar_lessons(
    topic_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[GrammarLessonAdmin]:
    query = select(GrammarLesson).order_by(GrammarLesson.position, GrammarLesson.id)
    total_query = select(GrammarLesson.id)
    if topic_id is not None:
        query = query.where(GrammarLesson.topic_id == topic_id)
        total_query = total_query.where(GrammarLesson.topic_id == topic_id)
    total = count_rows(db, total_query)
    lessons = list(db.scalars(query.limit(limit).offset(offset)))
    return page_of([_lesson_admin(db, lesson) for lesson in lessons], total, limit, offset)


@router.get("/grammar/lessons/{lesson_id}", response_model=GrammarLessonAdmin)
def get_grammar_lesson(
    lesson_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> GrammarLessonAdmin:
    """Một bài — trang soạn riêng cần nó, không phải tải cả danh sách rồi tìm."""
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return _lesson_admin(db, lesson)


@router.post(
    "/grammar/lessons", response_model=GrammarLessonAdmin, status_code=status.HTTP_201_CREATED
)
def create_grammar_lesson(
    body: GrammarLessonCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> GrammarLessonAdmin:
    if db.get(GrammarTopic, uuid.UUID(body.topic_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if body.kind not in ("theory", "practice"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="kind phải là 'theory' hoặc 'practice'",
        )
    lesson = GrammarLesson(
        topic_id=uuid.UUID(body.topic_id),
        slug=body.slug,
        title=body.title,
        kind=body.kind,
        body=body.body,
        position=body.position,
        status="draft",
        created_by=user.id,
    )
    db.add(lesson)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug đã tồn tại"
        ) from None
    db.refresh(lesson)
    return _lesson_admin(db, lesson)


@router.patch("/grammar/lessons/{lesson_id}", response_model=GrammarLessonAdmin)
def update_grammar_lesson(
    lesson_id: uuid.UUID,
    body: GrammarLessonUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> GrammarLessonAdmin:
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    if body.topic_id is not None and db.get(GrammarTopic, uuid.UUID(body.topic_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if body.kind is not None and body.kind not in ("theory", "practice"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="kind phải là 'theory' hoặc 'practice'",
        )
    if body.topic_id is not None:
        lesson.topic_id = uuid.UUID(body.topic_id)
    _apply(lesson, body, ("slug", "title", "kind", "body", "position", "status"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug đã tồn tại"
        ) from None
    db.refresh(lesson)
    return _lesson_admin(db, lesson)


@router.post("/grammar/lessons/{lesson_id}/publish", response_model=GrammarLessonAdmin)
def publish_grammar_lesson(
    lesson_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> GrammarLessonAdmin:
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    # Cổng publish phân nhánh theo KIND, vì hai loại hỏng khác nhau:
    # theory rỗng = trang chữ trống; practice không câu = mở ra một màn luyện
    # tập không có gì để làm — cả hai đều là trang hỏng với người học.
    if lesson.kind == "practice":
        attached = db.scalar(
            select(func.count(GrammarLessonQuestion.question_id))
            .join(Question, Question.id == GrammarLessonQuestion.question_id)
            .where(
                GrammarLessonQuestion.lesson_id == lesson.id,
                Question.status == "published",
            )
        )
        if not attached:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot publish: bài luyện tập chưa có câu PUBLISHED nào được gắn "
                "(câu nháp gắn vào cũng vô hình với người học). Gắn câu qua /questions trước.",
            )
    elif not lesson.body.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot publish: bài học không có lý thuyết. Một trang trống hiện "
            "ra với người học như bài hỏng, không như bài chưa soạn xong.",
        )
    lesson.status = "published"
    lesson.published_by = user.id
    lesson.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(lesson)
    return _lesson_admin(db, lesson)


@router.delete("/grammar/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grammar_lesson(
    lesson_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    db.delete(lesson)
    db.commit()


# --- câu của bài học ----------------------------------------------------------


@router.put("/grammar/lessons/{lesson_id}/questions", response_model=GrammarLessonAdmin)
def set_lesson_questions(
    lesson_id: uuid.UUID,
    body: GrammarLessonQuestions,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> GrammarLessonAdmin:
    """Gán TOÀN BỘ danh sách câu cho bài, xoá những câu không còn trong danh sách.

    PUT cả danh sách thay vì attach/detach từng câu: cùng lập luận với
    `StoryReorder` — một giao dịch gán lại 1..N, không trạng thái trung gian.
    """
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    ids = [uuid.UUID(qid) for qid in body.question_ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="question_ids trùng nhau"
        )
    if ids:
        found = set(db.scalars(select(Question.id).where(Question.id.in_(ids))))
        missing = [str(qid) for qid in ids if qid not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question not found: {', '.join(missing)}",
            )
    db.execute(delete(GrammarLessonQuestion).where(GrammarLessonQuestion.lesson_id == lesson.id))
    for position, question_id in enumerate(ids, start=1):
        db.add(
            GrammarLessonQuestion(lesson_id=lesson.id, question_id=question_id, position=position)
        )
    db.commit()
    return _lesson_admin(db, lesson)


@router.put("/grammar/topics/{topic_id}/lessons/order", response_model=list[GrammarLessonAdmin])
def reorder_grammar_lessons(
    topic_id: uuid.UUID,
    body: GrammarLessonOrder,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> list[GrammarLessonAdmin]:
    """Gán lại thứ tự TOÀN BỘ bài của chủ đề — cùng luật `StoryReorder`.

    Nhận cả danh sách chứ không nhận "đổi chỗ A và B": một giao dịch gán 1..N,
    không trạng thái trung gian hai bài cùng số. Đủ bài phải nằm trong danh sách
    — thiếu nghĩa là client đang làm việc với ảnh cũ của cây.
    """
    if db.get(GrammarTopic, topic_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    ids = [uuid.UUID(lesson_id) for lesson_id in body.lesson_ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="lesson_ids trùng nhau"
        )
    topic_lesson_ids = set(
        db.scalars(select(GrammarLesson.id).where(GrammarLesson.topic_id == topic_id))
    )
    missing = topic_lesson_ids - set(ids)
    unknown = set(ids) - topic_lesson_ids
    if missing or unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "order phải là ĐỦ số bài của chủ đề — "
                f"thiếu: {', '.join(str(i) for i in missing)}; "
                f"không thuộc chủ đề: {', '.join(str(i) for i in unknown)}"
            ),
        )
    existing = list(db.scalars(select(GrammarLesson).where(GrammarLesson.id.in_(ids))))
    by_id = {lesson.id: lesson for lesson in existing}
    for position, lesson_id in enumerate(ids, start=1):
        by_id[lesson_id].position = position
    db.commit()
    return [_lesson_admin(db, by_id[lesson_id]) for lesson_id in ids]


@router.get("/grammar/topics/{topic_id}/unattached-questions")
def list_unattached_questions(
    topic_id: uuid.UUID,
    lesson_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> list[dict[str, object]]:
    """Câu published mang nhãn của chủ đề, chưa gắn vào bài học NÀO KHÁC.

    §2: màn soạn phải liệt sẵn danh sách này để việc gắn rẻ nhất có thể. Không
    có nó, người soạn mở từng câu trong khu luyện thi và tự nhớ cái nào đã dùng
    — và "đã dùng rồi" là thứ không ai nhớ nổi khi kho lớn.

    `lesson_id` (khi sửa một bài practice): câu đang gắn ở CHÍNH bài đó được trả
    về kèm `attached: true` để picker tick sẵn; câu gắn ở bài khác vẫn bị loại —
    một câu nằm hai bài practice là hai màn drill trùng nội dung.
    """
    topic = db.get(GrammarTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if topic.code is None:
        return []  # không nhãn — không có gì để rút, danh sách rỗng là sự thật
    attached_elsewhere = select(GrammarLessonQuestion.question_id)
    here: set[uuid.UUID] = set()
    if lesson_id is not None:
        attached_elsewhere = attached_elsewhere.where(GrammarLessonQuestion.lesson_id != lesson_id)
        here = set(
            db.scalars(
                select(GrammarLessonQuestion.question_id).where(
                    GrammarLessonQuestion.lesson_id == lesson_id
                )
            )
        )
    query = (
        select(Question.id, Question.part, Question.prompt_text)
        .join(QuestionLabel, QuestionLabel.question_id == Question.id)
        .where(
            QuestionLabel.facet == "grammar",
            QuestionLabel.code == topic.code,
            Question.status == "published",
            Question.id.not_in(attached_elsewhere),
        )
        .order_by(Question.part, Question.id)
    )
    rows = db.execute(query.limit(limit).offset(offset)).all()
    return [
        {"id": str(qid), "part": part, "prompt_text": prompt, "attached": qid in here}
        for qid, part, prompt in rows
    ]


# --- video bài giảng (SPEC-GRAMMAR-VIDEO) -------------------------------------

# Hạn mức RIÊNG và chặt hơn mọi khu khác: một bài chỉ một video, nhu cầu thật là
# vài lần mỗi buổi soạn. Rộng hơn thế chỉ mời dùng bucket làm ổ đĩa.
VIDEO_TICKET_QUOTA = rate_limit.Quota(limit=5, window_seconds=600)


def _lesson_for_video(lesson_id: uuid.UUID, db: Session) -> GrammarLesson:
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


@router.post(
    "/grammar/lessons/{lesson_id}/video/ticket",
    response_model=UploadTicket,
    dependencies=[
        Depends(can_edit),
        Depends(rate_limit.rate_limit("grammar-video-ticket", VIDEO_TICKET_QUOTA)),
    ],
)
def grammar_video_ticket(
    lesson_id: uuid.UUID,
    body: VideoTicketRequest,
    db: Session = Depends(get_db),
) -> UploadTicket:
    """Vé upload video bài giảng — trình duyệt PUT thẳng object store (§2.1).

    Cùng bốn bước với avatar/feedback; byte KHÔNG đi qua FastAPI. Driver là
    `get_driver("video")` — chỉ tới S3/local, Cloudinary bị chặn ở `get_driver`
    vì băng thông video ăn credit Cloudinary là thứ ảnh đang sống bằng.
    """
    _lesson_for_video(lesson_id, db)
    storage_key = video_storage_key_for(upload_source_hash(str(uuid.uuid4())), ext=body.ext)
    return UploadTicket.of(get_driver("video").ticket(storage_key))


@router.put("/grammar/lessons/{lesson_id}/video", response_model=GrammarLessonAdmin)
def grammar_video_confirm(
    lesson_id: uuid.UUID,
    body: VideoConfirm,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> GrammarLessonAdmin:
    """Gắn video vừa tải lên vào bài. Ba kiểm, cùng khuôn `avatar_confirm`:

    1. khoá phải nằm dưới `grammar-video/` — không thì nó có thể trỏ vào vùng
       media người khác, và lệnh dọn mồ côi sau này xoá mất thứ đang được dùng;
    2. `verify()` hỏi lại nhà cung cấp — thiếu bước này là đường ghi một chuỗi
       tuỳ ý và người học sẽ thấy player vỡ (ADR-006 §2.3);
    3. bài phải `kind='theory'` — practice không có chỗ hiển thị video, chặn ở
       biên thay vì nuôi một cột không bao giờ đọc.
    """
    lesson = _lesson_for_video(lesson_id, db)
    if not body.storage_key.startswith(f"{VIDEO_KEY_PREFIX}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Khoá không thuộc vùng video bài giảng",
        )
    try:
        get_driver("video").verify(body.storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None
    if lesson.kind != "theory":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ bài lý thuyết có video bài giảng — bài luyện tập không có chỗ hiển thị.",
        )
    lesson.video_storage_key = body.storage_key
    lesson.video_duration_s = body.duration_s
    db.commit()
    db.refresh(lesson)
    return _lesson_admin(db, lesson)


@router.delete("/grammar/lessons/{lesson_id}/video", response_model=GrammarLessonAdmin)
def grammar_video_remove(
    lesson_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> GrammarLessonAdmin:
    """Gỡ video khỏi bài. Idempotent. File để MỒ CÔI cho `reconcile_media` dọn —
    xoá đồng nghĩa với một request chờ dịch vụ ngoài, đúng thứ avatar đã từ chối."""
    lesson = _lesson_for_video(lesson_id, db)
    lesson.video_storage_key = None
    lesson.video_duration_s = None
    db.commit()
    db.refresh(lesson)
    return _lesson_admin(db, lesson)


# --- kho câu hỏi cho bài luyện tập -------------------------------------------


@router.get("/grammar/question-bank")
def list_question_bank(
    search: str | None = None,
    code: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> list[dict[str, object]]:
    """Kho câu để picker của lesson practice CHỌN — không suy ra từ nhãn.

    Part 5 là hình dạng duy nhất dựng độc lập được: câu Part 6 bắt buộc thuộc
    một `question_set` (CHECK của `question.set_id`) và màn drill không có
    passage để đi kèm; Parts 1–2 không in gì ra chữ nào.

    `code` lọc theo nhãn grammar của chính câu; `search` tìm theo chữ trong
    prompt. Trả kèm `grammar_code` (có thể null — chưa gắn nhãn không phải sai
    nhãn) để picker hiện đúng thứ người đang lọc.
    """
    query = (
        select(Question.id, Question.part, Question.prompt_text, QuestionLabel.code)
        .outerjoin(
            QuestionLabel,
            and_(
                QuestionLabel.question_id == Question.id,
                QuestionLabel.facet == "grammar",
            ),
        )
        .where(
            Question.status == "published",
            Question.part == 5,
            Question.prompt_text.is_not(None),
        )
    )
    if search:
        query = query.where(Question.prompt_text.ilike(f"%{search}%"))
    if code:
        query = query.where(QuestionLabel.code == code)
    rows = db.execute(query.order_by(Question.id).limit(limit).offset(offset)).all()
    return [
        {"id": str(qid), "part": part, "prompt_text": prompt, "grammar_code": grammar_code}
        for qid, part, prompt, grammar_code in rows
    ]


@router.get("/grammar/labels")
def list_grammar_labels(_: User = Depends(can_edit)) -> list[dict[str, str]]:
    """Mã + tên tiếng Việt của facet grammar — dropdown filter cho picker.

    Đọc từ registry, không chép danh sách: cùng lý do mà `code` của topic bị
    kiểm bằng registry thay vì một tuple cứng ở đầu tệp này.
    """
    return [
        {"code": label.code, "label_vi": label.label_vi}
        for facet in FACETS
        if facet.key == "grammar"
        for label in facet.labels
    ]


@router.post("/grammar/questions", status_code=status.HTTP_201_CREATED)
def create_grammar_question(
    body: GrammarQuestionDraft, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> dict[str, object]:
    """Thêm TAY một câu vào kho ngữ pháp.

    Ghi thẳng `published`, khác luật "commit luôn ghi draft" của đường dán: màn
    này là người soạn ĐANG chọn từng câu cho một bài cụ thể, không phải máy đổ
    hàng loạt cần người duyệt; và câu draft thì vô hình với cả picker lẫn lesson
    — tạo ra là để dùng ngay. Cổng publish của BÀI vẫn chặn bài practice chưa có
    câu nào, nên thứ quyết định lên sóng vẫn là bước đó.

    `validate_question` chạy đúng như cửa commit của khu luyện thi: thiếu đáp án
    đúng, thừa phương án, trùng nhãn — 422 hết, không cho lọt.
    """
    question = Question(
        part=5,
        difficulty=body.difficulty,
        source="original",
        status="published",
        prompt_text=body.prompt_text,
        explanation=body.explanation,
        created_by=user.id,
    )
    question.options = [
        QuestionOption(label=o.label, content=o.content, is_correct=o.is_correct)
        for o in body.options
    ]
    problems = validate_question(question)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="; ".join(problems)
        )
    db.add(question)
    db.commit()
    return {"id": str(question.id), "part": 5, "prompt_text": question.prompt_text}
