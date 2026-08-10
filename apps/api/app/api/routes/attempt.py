"""Làm bài: bắt đầu, lưu từng câu, nộp.

Ba luật chạy xuyên suốt, và cả ba đều hỏng âm thầm nếu ai đó bỏ:

**Đáp án không rời máy chủ khi đang thi.** `DictationDetail` cố ý gửi đáp án
xuống trình duyệt vì chấm ở client cho phản hồi tức thì, và tài liệu ghi rõ điều
đó chấp nhận được cho tự học nhưng **không** cho thứ gì được chấm điểm. Bài thi
thử thì có điểm, và điểm nằm lại trong lịch sử người học — nên `correct_option_id`
chỉ xuất hiện ở chế độ Luyện tập hoặc sau khi đã nộp.

**Thời gian do máy chủ tính.** Trình duyệt đếm ngược cho mượt, nhưng đồng hồ máy
khách chỉnh được; một bài thi tin vào nó là một bài thi không có giới hạn.

**Hết giờ thì tự nộp, ở lần chạm tiếp theo.** Không có tiến trình nền nào ở đây
(A2.5 cố ý tránh job queue), nên hết giờ được phát hiện khi có request — và
request đầu tiên sau khi hết giờ sẽ chốt bài thay vì nhận thêm đáp án.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.media import public_audio_url
from app.core.storage import get_driver
from app.models.audio import AudioAsset
from app.models.image import ImageAsset
from app.models.practice import (
    Attempt,
    AttemptItem,
    AttemptPart,
    PracticeTest,
    PracticeTestQuestion,
    Question,
)
from app.models.user import User
from app.schemas.practice import (
    PART_TITLES,
    AnswerSubmit,
    AttemptPartProgress,
    AttemptResult,
    AttemptStart,
    AttemptState,
    OptionPublic,
    QuestionPublic,
    section_of,
)
from app.services.scoring import score_attempt

router = APIRouter(prefix="/attempts", tags=["attempt"])

PUBLISHED = "published"
LISTENING_PARTS = (1, 2, 3, 4)


def _remaining(attempt: Attempt) -> int | None:
    """Số giây còn lại, hoặc None khi đề không giới hạn thời gian."""
    limit = attempt.test.time_limit_seconds
    if limit is None:
        return None
    used = attempt.elapsed_seconds
    if attempt.status == "in_progress" and attempt.resumed_at is not None:
        started = attempt.resumed_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        used += int((datetime.now(UTC) - started).total_seconds())
    return max(limit - used, 0)


def _finalise(db: Session, attempt: Attempt, new_status: str) -> None:
    """Chốt bài: dừng đồng hồ, chấm, quy đổi nếu quy đổi được."""
    remaining = _remaining(attempt)
    limit = attempt.test.time_limit_seconds
    if limit is not None:
        attempt.elapsed_seconds = limit - (remaining or 0)
    elif attempt.resumed_at is not None:
        started = attempt.resumed_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        attempt.elapsed_seconds += int((datetime.now(UTC) - started).total_seconds())
    attempt.resumed_at = None
    attempt.status = new_status
    attempt.submitted_at = datetime.now(UTC)

    correct_ids = _correct_option_ids(db, [item.question_id for item in attempt.items])
    for item in attempt.items:
        # Câu bỏ trống được chấm là SAI, không phải bỏ qua: ô trống ở cuối part 7
        # nghĩa là hết giờ, và đó là một dữ kiện chứ không phải dữ liệu thiếu.
        item.is_correct = (
            item.selected_option_id is not None
            and item.selected_option_id == correct_ids.get(item.question_id)
        )

    # Chỉ quy đổi khi làm CẢ ĐỀ. `scoring.py` từ chối quy đổi một lượt làm một
    # phần, vì một con số trông như điểm TOEIC mà không phải điểm TOEIC sẽ nằm
    # vĩnh viễn trong biểu đồ tiến bộ của người học.
    if attempt.scope == "full":
        try:
            score_attempt(db, attempt)
        except (ValueError, LookupError):
            # Thiếu bảng quy đổi thì để trống, KHÔNG nội suy. Giao diện nói ra
            # lý do; một điểm sai âm thầm thì không ai phát hiện được.
            pass


def _correct_option_ids(db: Session, question_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not question_ids:
        return {}
    questions = db.scalars(
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.id.in_(question_ids))
    ).all()
    return {
        question.id: option.id
        for question in questions
        for option in question.options
        if option.is_correct
    }


def _load(db: Session, attempt_id: uuid.UUID, user: User) -> Attempt:
    attempt = db.scalars(
        select(Attempt)
        .options(selectinload(Attempt.items), selectinload(Attempt.parts))
        .where(Attempt.id == attempt_id)
    ).one_or_none()
    if attempt is None or attempt.user_id != user.id:
        # 404 chứ không 403 cho lượt làm của người khác: xác nhận "có tồn tại
        # nhưng không phải của bạn" là tiết lộ nhiều hơn cần thiết.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có lượt làm này")
    return attempt


def _state(db: Session, attempt: Attempt) -> AttemptState:
    rows = db.execute(
        select(PracticeTestQuestion.position, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .options(
            selectinload(Question.options),
            selectinload(Question.question_set),
        )
        .where(PracticeTestQuestion.test_id == attempt.test_id)
        .order_by(PracticeTestQuestion.position)
    ).all()

    answered_by_question = {item.question_id: item for item in attempt.items}
    in_scope = [(pos, q) for pos, q in rows if q.id in answered_by_question]

    reveal = attempt.review_mode == "practice" or attempt.status != "in_progress"
    correct_ids = _correct_option_ids(db, [q.id for _, q in in_scope]) if reveal else {}

    # Nạp asset bằng MỘT truy vấn cho mỗi loại. `Question` chỉ có cột id chứ
    # không có relationship, nên không nạp trước ở đây thì thành N+1 — và với
    # một đề 200 câu đó là 200 lượt đi lại database cho mỗi lần mở bài.
    audio_ids = {q.audio_asset_id for _, q in in_scope if q.audio_asset_id} | {
        q.question_set.audio_asset_id
        for _, q in in_scope
        if q.question_set is not None and q.question_set.audio_asset_id
    }
    image_ids = {q.image_asset_id for _, q in in_scope if q.image_asset_id}
    audio_by_id = {
        a.id: a
        for a in (
            db.scalars(select(AudioAsset).where(AudioAsset.id.in_(audio_ids))).all()
            if audio_ids
            else []
        )
    }
    image_by_id = {
        i.id: i
        for i in (
            db.scalars(select(ImageAsset).where(ImageAsset.id.in_(image_ids))).all()
            if image_ids
            else []
        )
    }

    image_driver = get_driver("image")
    questions: list[QuestionPublic] = []
    seen_sets: set[uuid.UUID] = set()

    for number, (_, question) in enumerate(in_scope, start=1):
        item = answered_by_question[question.id]
        stimulus = question.question_set
        # Ngữ liệu chỉ đi kèm câu ĐẦU của cụm: lặp lại trên cả ba câu là ba lần
        # cùng một đoạn văn trên đường truyền, và client sẽ phải tự khử trùng lặp.
        first_of_set = stimulus is not None and stimulus.id not in seen_sets
        if stimulus is not None:
            seen_sets.add(stimulus.id)

        audio_asset = None
        if question.audio_asset_id is not None:
            audio_asset = audio_by_id.get(question.audio_asset_id)
        elif first_of_set and stimulus is not None and stimulus.audio_asset_id is not None:
            audio_asset = audio_by_id.get(stimulus.audio_asset_id)
        image_asset = image_by_id.get(question.image_asset_id) if question.image_asset_id else None

        questions.append(
            QuestionPublic(
                number=number,
                id=str(question.id),
                part=question.part,
                prompt_text=question.prompt_text,
                audio_url=(
                    public_audio_url(audio_asset.storage_key) if audio_asset is not None else None
                ),
                image_url=(
                    image_driver.public_url(image_asset.storage_key)
                    if image_asset is not None
                    else None
                ),
                image_alt=image_asset.alt_text if image_asset is not None else None,
                set_id=str(stimulus.id) if stimulus is not None else None,
                set_title=stimulus.title if first_of_set and stimulus is not None else None,
                passages=(
                    [
                        text
                        for text in (stimulus.passage, stimulus.passage_2, stimulus.passage_3)
                        if text
                    ]
                    if first_of_set and stimulus is not None
                    else []
                ),
                options=[
                    OptionPublic(id=str(option.id), label=option.label, content=option.content)
                    for option in sorted(question.options, key=lambda o: o.label)
                ],
                selected_option_id=(
                    str(item.selected_option_id) if item.selected_option_id else None
                ),
                flagged=item.flagged,
                correct_option_id=(
                    str(correct_ids[question.id]) if reveal and question.id in correct_ids else None
                ),
                explanation=question.explanation if reveal else None,
            )
        )

    parts: list[AttemptPartProgress] = []
    for part in sorted({q.part for q in questions}):
        numbers = [q.number for q in questions if q.part == part]
        parts.append(
            AttemptPartProgress(
                part=part,
                title=PART_TITLES[part],
                section=section_of(part),
                answered=sum(
                    1 for q in questions if q.part == part and q.selected_option_id is not None
                ),
                total=len(numbers),
                first_number=min(numbers),
                last_number=max(numbers),
            )
        )

    return AttemptState(
        id=str(attempt.id),
        test_slug=attempt.test.slug,
        test_title=attempt.test.title,
        review_mode=attempt.review_mode,
        scope=attempt.scope,
        status=attempt.status,
        time_limit_seconds=attempt.test.time_limit_seconds,
        remaining_seconds=_remaining(attempt),
        answered_count=sum(1 for q in questions if q.selected_option_id is not None),
        question_count=len(questions),
        parts=parts,
        questions=questions,
    )


def _expire_if_out_of_time(db: Session, attempt: Attempt) -> None:
    if attempt.status != "in_progress":
        return
    remaining = _remaining(attempt)
    if remaining is not None and remaining <= 0:
        _finalise(db, attempt, "expired")
        db.commit()


@router.post("", response_model=AttemptState, status_code=status.HTTP_201_CREATED)
def start_attempt(
    body: AttemptStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptState:
    if body.review_mode not in ("exam", "practice"):
        raise HTTPException(status_code=400, detail="Chế độ làm bài không hợp lệ")

    test = db.scalars(
        select(PracticeTest).where(
            PracticeTest.slug == body.test_slug, PracticeTest.status == PUBLISHED
        )
    ).one_or_none()
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có đề này")

    rows = db.execute(
        select(PracticeTestQuestion.position, Question.id, Question.part)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .where(PracticeTestQuestion.test_id == test.id, Question.status == PUBLISHED)
        .order_by(PracticeTestQuestion.position)
    ).all()

    chosen = sorted({p for p in body.parts if 1 <= p <= 7})
    available = sorted({int(row[2]) for row in rows})
    # Chọn đúng tất cả các part CÓ NỘI DUNG cũng là làm cả đề. Coi đó là "một
    # phần" sẽ khiến bài không được quy đổi điểm dù người học đã làm hết những
    # gì đề có.
    full = not chosen or chosen == available
    selected = rows if full else [row for row in rows if int(row[2]) in chosen]
    if not selected:
        raise HTTPException(status_code=400, detail="Không có câu hỏi nào trong phần đã chọn")

    attempt = Attempt(
        user_id=current_user.id,
        test_id=test.id,
        scope="full" if full else "partial",
        review_mode=body.review_mode,
        status="in_progress",
        elapsed_seconds=0,
        resumed_at=datetime.now(UTC),
    )
    if not full:
        attempt.parts = [AttemptPart(part=part) for part in chosen]
    db.add(attempt)
    db.flush()

    # Tạo hàng cho MỌI câu ngay từ đầu, kể cả câu chưa trả lời. Câu bỏ trống phải
    # tồn tại dưới dạng một hàng chứ không phải một hàng thiếu — đó là cách duy
    # nhất phân biệt "chưa làm tới" với "không có trong đề".
    for position, (_, question_id, _part) in enumerate(selected, start=1):
        db.add(AttemptItem(attempt_id=attempt.id, question_id=question_id, position=position))
    db.commit()
    db.refresh(attempt)
    return _state(db, attempt)


@router.get("/{attempt_id}", response_model=AttemptState)
def read_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptState:
    attempt = _load(db, attempt_id, current_user)
    _expire_if_out_of_time(db, attempt)
    return _state(db, attempt)


@router.patch("/{attempt_id}/questions/{question_id}", response_model=AttemptState)
def save_answer(
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    body: AnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptState:
    attempt = _load(db, attempt_id, current_user)
    _expire_if_out_of_time(db, attempt)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Lượt làm này đã kết thúc")

    item = next((i for i in attempt.items if i.question_id == question_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Câu này không thuộc lượt làm")

    if body.flagged is not None:
        item.flagged = body.flagged
    else:
        # Chuỗi từ JSON sang UUID ở đúng biên: cột là UUID, và để chuỗi lọt
        # vào sẽ chỉ hỏng khi Postgres so sánh, tức là ở một chỗ rất xa đây.
        item.selected_option_id = (
            uuid.UUID(body.selected_option_id) if body.selected_option_id else None
        )
        item.answered_at = datetime.now(UTC)
    db.commit()
    db.refresh(attempt)
    return _state(db, attempt)


@router.post("/{attempt_id}/submit", response_model=AttemptResult)
def submit_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptResult:
    attempt = _load(db, attempt_id, current_user)
    if attempt.status == "in_progress":
        _finalise(db, attempt, "submitted")
        db.commit()
        db.refresh(attempt)

    correct = sum(1 for item in attempt.items if item.is_correct)
    note = None
    if attempt.scope != "full":
        note = "Chỉ làm một phần của đề nên không quy đổi ra điểm TOEIC."
    elif attempt.total_scaled is None:
        note = "Đề này chưa có bảng quy đổi điểm, nên chỉ có số câu đúng."

    return AttemptResult(
        id=str(attempt.id),
        status=attempt.status,
        correct_count=correct,
        question_count=len(attempt.items),
        listening_raw=attempt.listening_raw,
        reading_raw=attempt.reading_raw,
        listening_scaled=attempt.listening_scaled,
        reading_scaled=attempt.reading_scaled,
        total_scaled=attempt.total_scaled,
        scale_note=note,
    )
