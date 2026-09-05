"""Learning GRAMMAR — cây chủ đề → bài học → lý thuyết, và bài LUYỆN TẬP như một
loại lesson với câu gắn tay (SPEC-GRAMMAR G2 + G4).

Đọc công khai như cây dictation: lý thuyết ngữ pháp không có tiến độ ẩn sau
account, và cổng chặn nội dung là `status`, không phải đăng nhập. NỘP bài thì
cần tài khoản — `grammar_attempt` là dữ liệu của một người cụ thể.

Bất biến dictation đã trả giá để học, ghi lại ở `learning-domain.md`: **mỗi tầng
lọc `published` độc lập**. Một bài published nằm dưới chủ đề draft vẫn lọt ra nếu
endpoint bài chỉ kiểm bài — và nội dung trông hoàn toàn bình thường, nên không ai
báo cáo được. `tests/test_grammar.py` pin cả hai chiều. Cùng luật đó áp cho CÂU:
câu nháp mang nhãn không được xuất hiện trong luyện tập.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.core.database import get_db
from app.models import (
    GrammarAttempt,
    GrammarLesson,
    GrammarLessonCompletion,
    GrammarLessonQuestion,
    GrammarTopic,
    Question,
    QuestionOption,
    User,
)
from app.schemas.learning import (
    GrammarLessonDetail,
    GrammarLessonSummary,
    GrammarNextTopic,
    GrammarPracticeOption,
    GrammarPracticeQuestion,
    GrammarPracticeResult,
    GrammarPracticeSubmit,
    GrammarTopicDetail,
    GrammarTopicPublic,
)
from app.services import progression
from app.services.profile import ensure_profile

router = APIRouter(tags=["learning"])

PUBLISHED = "published"


def _lesson_completion(
    db: Session, user: User | None, lessons: Sequence[tuple[uuid.UUID, str]]
) -> dict[uuid.UUID, bool]:
    """Bài nào của `lessons` đã hoàn thành với người học này.

    Một nguồn duy nhất cho cả hai loại: hàng `grammar_lesson_completion` — người
    học BẤM "Hoàn thành" (và bấm "Bỏ hoàn thành" để thu lại). Practice từng có
    tiến độ suy từ số câu đúng, đã đổi: bài luyện tập cũng là một bài học, có
    cùng quyền tự quyết như mọi bài khác; làm đúng hết câu mà chưa kịp bấm, hoặc
    bấm khi muốn tự ôn thêm, đều là quyết định của người học, không phải lỗi.

    Tham số `kind` giữ trong chữ ký vì hai loại có thể sẽ lại phân nhánh — thêm
    đối số rồi bỏ còn hơn gọi nhầm mà không ai biết.
    """
    result = {lesson_id: False for lesson_id, _ in lessons}
    if user is None or not lessons:
        return result
    marked = db.scalars(
        select(GrammarLessonCompletion.lesson_id).where(
            GrammarLessonCompletion.user_id == user.id,
            GrammarLessonCompletion.revoked_at.is_(None),
            GrammarLessonCompletion.lesson_id.in_([lesson_id for lesson_id, _ in lessons]),
        )
    )
    for lesson_id in marked:
        result[lesson_id] = True
    return result


def _summary(lesson: GrammarLesson, completed: bool) -> GrammarLessonSummary:
    return GrammarLessonSummary(
        id=str(lesson.id),
        slug=lesson.slug,
        title=lesson.title,
        kind=lesson.kind,
        position=lesson.position,
        completed=completed,
    )


def _published_lessons(db: Session, topic_id: uuid.UUID) -> list[GrammarLesson]:
    return list(
        db.scalars(
            select(GrammarLesson)
            .where(GrammarLesson.topic_id == topic_id, GrammarLesson.status == PUBLISHED)
            .order_by(GrammarLesson.position, GrammarLesson.id)
        )
    )


@router.get("/grammar-topics", response_model=list[GrammarTopicPublic])
def list_grammar_topics(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[GrammarTopicPublic]:
    topics = db.scalars(
        select(GrammarTopic)
        .where(GrammarTopic.status == PUBLISHED)
        .order_by(GrammarTopic.position, GrammarTopic.id)
    ).all()
    lessons = db.scalars(select(GrammarLesson).where(GrammarLesson.status == PUBLISHED)).all()
    completion = _lesson_completion(db, user, [(lesson.id, lesson.kind) for lesson in lessons])
    return [
        GrammarTopicPublic(
            id=str(topic.id),
            code=topic.code,
            slug=topic.slug,
            title=topic.title,
            summary=topic.summary,
            lesson_count=sum(1 for lesson in lessons if lesson.topic_id == topic.id),
            completed_lesson_count=sum(
                1 for lesson in lessons if lesson.topic_id == topic.id and completion[lesson.id]
            ),
        )
        for topic in topics
    ]


@router.get("/grammar-topics/{topic_id}", response_model=GrammarTopicDetail)
def get_grammar_topic(
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GrammarTopicDetail:
    topic = db.get(GrammarTopic, topic_id)
    if topic is None or topic.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    lessons = _published_lessons(db, topic.id)
    completion = _lesson_completion(db, user, [(lesson.id, lesson.kind) for lesson in lessons])
    summaries = [_summary(lesson, completion[lesson.id]) for lesson in lessons]
    return GrammarTopicDetail(
        id=str(topic.id),
        code=topic.code,
        slug=topic.slug,
        title=topic.title,
        summary=topic.summary,
        lesson_count=len(summaries),
        completed_lesson_count=sum(1 for s in summaries if s.completed),
        lessons=summaries,
    )


def _practice_questions(
    db: Session, lesson_id: uuid.UUID, user: User | None
) -> list[GrammarPracticeQuestion]:
    """Câu của một bài practice, theo `position` của bảng nối."""
    rows = db.execute(
        select(Question, GrammarLessonQuestion.position)
        .join(GrammarLessonQuestion, GrammarLessonQuestion.question_id == Question.id)
        .where(
            GrammarLessonQuestion.lesson_id == lesson_id,
            Question.status == PUBLISHED,
        )
        .order_by(GrammarLessonQuestion.position)
    ).all()
    questions = [question for question, _ in rows]
    correct: set[uuid.UUID] = set()
    if user is not None and questions:
        correct = set(
            db.scalars(
                select(GrammarAttempt.question_id)
                .where(
                    GrammarAttempt.user_id == user.id,
                    GrammarAttempt.is_correct.is_(True),
                    GrammarAttempt.question_id.in_([q.id for q in questions]),
                )
                .distinct()
            )
        )
    return [
        GrammarPracticeQuestion(
            id=str(question.id),
            part=question.part,
            prompt_text=question.prompt_text,
            options=[
                GrammarPracticeOption(id=str(o.id), label=o.label, content=o.content)
                for o in sorted(question.options, key=lambda o: o.label)
            ],
            completed=question.id in correct,
        )
        for question in questions
    ]


@router.get("/grammar-lessons/{lesson_id}", response_model=GrammarLessonDetail)
def get_grammar_lesson(
    lesson_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GrammarLessonDetail:
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None or lesson.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    # Tầng cha được kiểm LẠI ở đây, không phải chỉ ở endpoint danh sách: đây là
    # đường duy nhất một bài lọt qua khi chủ đề của nó bị hạ về draft sau khi
    # người học đã bấm vào — URL cũ, bookmark cũ, nội dung lẽ ra đã ẩn.
    topic = db.get(GrammarTopic, lesson.topic_id)
    if topic is None or topic.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    ordered = _published_lessons(db, topic.id)
    completion = _lesson_completion(db, user, [(item.id, item.kind) for item in ordered])
    next_lesson: GrammarLessonSummary | None = None
    for index, candidate in enumerate(ordered):
        if candidate.id == lesson.id and index + 1 < len(ordered):
            next_lesson = _summary(ordered[index + 1], completion[ordered[index + 1].id])
            break
    next_topic: GrammarNextTopic | None = None
    # Tính VÔ ĐIỀU KIỆN, không chỉ khi là bài cuối: sidebar lesson luôn hiện
    # "chủ đề kế tiếp" để người học thấy đường đi còn lại của khóa học, không
    # phải đợi tới bài cuối mới biết mình sắp ra đâu.
    later = db.scalars(
        select(GrammarTopic)
        .where(
            GrammarTopic.status == PUBLISHED,
            or_(
                GrammarTopic.position > topic.position,
                and_(GrammarTopic.position == topic.position, GrammarTopic.id > topic.id),
            ),
        )
        .order_by(GrammarTopic.position, GrammarTopic.id)
    ).all()
    for next_topic_candidate in later:
        first = db.scalars(
            select(GrammarLesson)
            .where(
                GrammarLesson.topic_id == next_topic_candidate.id,
                GrammarLesson.status == PUBLISHED,
            )
            .order_by(GrammarLesson.position, GrammarLesson.id)
            .limit(1)
        ).first()
        if first is not None:
            next_topic = GrammarNextTopic(
                topic_id=str(next_topic_candidate.id),
                topic_title=next_topic_candidate.title,
                lesson_id=str(first.id),
                lesson_title=first.title,
            )
            break
    return GrammarLessonDetail(
        id=str(lesson.id),
        topic_id=str(topic.id),
        topic_title=topic.title,
        slug=lesson.slug,
        title=lesson.title,
        kind=lesson.kind,
        body=lesson.body,
        questions=_practice_questions(db, lesson.id, user) if lesson.kind == "practice" else [],
        completed=completion[lesson.id],
        next_lesson=next_lesson,
        next_topic=next_topic,
    )


@router.post("/grammar-lessons/{lesson_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def complete_grammar_lesson(
    lesson_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Bấm "Hoàn thành" — mọi loại lesson như nhau. Idempotent theo PK (user, lesson).

    Bấm lại một bài đã gỡ dấu KHÔNG dời `created_at`: ngày của bằng chứng cũ là
    ngày cũ, và đó cũng là lúc "bấm lại bài cũ" hết tính là bài của hôm nay
    trong daily task.
    """
    lesson = db.get(GrammarLesson, lesson_id)
    if lesson is None or lesson.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    topic = db.get(GrammarTopic, lesson.topic_id)
    if topic is None or topic.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    row = db.get(GrammarLessonCompletion, (user.id, lesson.id))
    if row is None:
        db.add(GrammarLessonCompletion(user_id=user.id, lesson_id=lesson.id))
    else:
        row.revoked_at = None
    db.commit()


@router.delete("/grammar-lessons/{lesson_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def unmark_grammar_lesson(
    lesson_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Bấm "Bỏ hoàn thành" — ĐÁNH DẤU `revoked_at`, không xoá.

    Dấu tay thì gỡ được, nhưng bằng chứng "hôm đó có học" phải ở lại: streak và
    ruby đọc những ngày này, và một hàng xoá được sẽ viết lại chuỗi của người ta
    sau lưng họ. `grammar_attempt` vẫn nguyên — đã làm câu nào thì câu đó vẫn
    nằm trong lịch sử, đúng như mọi số liệu học tập khác ở dự án này.
    """
    row = db.get(GrammarLessonCompletion, (user.id, lesson_id))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(tz=UTC)
    db.commit()


# --- nộp bài ------------------------------------------------------------------


@router.post("/grammar-attempts", response_model=GrammarPracticeResult)
def submit_grammar_attempt(
    body: GrammarPracticeSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GrammarPracticeResult:
    """Chấm MỘT câu. Ghi mọi lượt, không chỉ lượt đầu — tiến độ đếm lần ĐÚNG,
    làm lại câu đã đúng không bỏ được gì, và giấu các lượt sai đi sẽ làm lịch
    sử thành ảnh tự hoạ."""
    question = db.get(Question, uuid.UUID(body.question_id))
    if question is None or question.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    option = db.get(QuestionOption, uuid.UUID(body.option_id))
    if option is None or option.question_id != question.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Option not found for this question"
        )
    correct = next((o for o in question.options if o.is_correct), None)
    if correct is None:  # pragma: no cover — `validate_question` chặn từ cửa ghi
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Question has no correct option"
        )
    is_correct = option.id == correct.id
    db.add(
        GrammarAttempt(
            user_id=user.id, question_id=question.id, option_id=option.id, is_correct=is_correct
        )
    )
    # Chỉ câu ĐÚNG mới có XP, và mỗi (người, câu) chỉ một lần — `source_id` tất
    # định, không phải id lượt. XP hỏng thì lượt chấm vẫn chạy (invariant của
    # `services/progression`).
    if is_correct:
        try:
            progression.award(
                db,
                user_id=user.id,
                source_type="grammar_attempt",
                source_id=progression.grammar_source_id(user.id, question.id),
                amount=progression.xp_for(db, "grammar_attempt"),
                timezone=ensure_profile(db, user).timezone,
            )
        except Exception:  # pragma: no cover - XP không được làm hỏng việc học
            pass
    db.commit()
    return GrammarPracticeResult(
        is_correct=is_correct,
        correct_option_id=str(correct.id),
        explanation=question.explanation,
    )
