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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.media import public_audio_url
from app.core.storage import StorageDriver, get_driver
from app.models.audio import AudioAsset
from app.models.image import ImageAsset
from app.models.practice import (
    Attempt,
    AttemptItem,
    AttemptPart,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionSet,
)
from app.models.user import User
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.schemas.practice import (
    PART_TITLES,
    AnswerSubmit,
    AttemptPartProgress,
    AttemptResult,
    AttemptStart,
    AttemptState,
    AttemptSummary,
    OptionPublic,
    PassagePublic,
    QuestionPublic,
    section_of,
)
from app.services import progression
from app.services.profile import ensure_profile
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


def _passages(
    stimulus: QuestionSet,
    images: dict[uuid.UUID, ImageAsset],
    image_driver: StorageDriver,
) -> list[PassagePublic]:
    """Các ô ngữ liệu theo đúng thứ tự, bỏ ô rỗng.

    Một ô được giữ khi nó có văn bản HOẶC có ảnh. Lọc theo mỗi văn bản như bản
    cũ sẽ làm một biểu đồ không kèm chú thích biến mất khỏi đề — và câu hỏi về
    nó vẫn còn nguyên đó.
    """
    slots = (
        (stimulus.passage, stimulus.passage_image_id),
        (stimulus.passage_2, stimulus.passage_2_image_id),
        (stimulus.passage_3, stimulus.passage_3_image_id),
    )
    out: list[PassagePublic] = []
    for text, image_id in slots:
        asset = images.get(image_id) if image_id else None
        if not text and asset is None:
            continue
        out.append(
            PassagePublic(
                text=text,
                image_url=image_driver.public_url(asset.storage_key) if asset else None,
                image_alt=asset.alt_text if asset else None,
                # Ghi công đi kèm ảnh ở MỌI nơi ảnh xuất hiện, không chỉ Part 1:
                # CC-BY cho dùng *với điều kiện* ghi công (ADR-004 §4.2).
                image_attribution=asset.attribution if asset else None,
                image_license=asset.license if asset else None,
            )
        )
    return out


def _state(db: Session, attempt: Attempt) -> AttemptState:
    rows = db.execute(
        # Lấy cả `number`: nó là con số người học nhìn thấy, còn `position` chỉ
        # là thứ tự trình bày. Hai thứ trùng nhau ở đề đầy đủ và khác nhau ở đề
        # rút gọn, nên dùng nhầm sẽ đúng cho tới đúng lúc nó sai (ADR-007 §2.6).
        select(PracticeTestQuestion.number, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .options(
            selectinload(Question.options),
            selectinload(Question.question_set),
        )
        .where(PracticeTestQuestion.test_id == attempt.test_id)
        .order_by(PracticeTestQuestion.position)
    ).all()

    answered_by_question = {item.question_id: item for item in attempt.items}
    in_scope = [(number, q) for number, q in rows if q.id in answered_by_question]

    # Lộ đáp án là quyết định TỪNG CÂU, không phải một cờ cho cả lượt làm.
    #
    # Nộp rồi thì lộ hết — không còn gì để đo. Đang làm ở chế độ Luyện tập thì
    # chỉ lộ câu người học đã chọn: Part 1 và 2 không in gì ra đề, nên "lộ" ở đó
    # có nghĩa là gửi kèm nguyên văn lời đọc, và gửi trước lúc họ bấm nghe thì
    # bài tập nghe không còn đo cái nó định đo. Luyện thi thì không lộ gì cả.
    #
    # Gác ở máy chủ chứ không phải ở giao diện: giấu bằng CSS vẫn để nguyên văn
    # nằm trong payload, mở tab Network là đọc được.
    submitted = attempt.status != "in_progress"
    practice = attempt.review_mode == "practice"
    correct_ids = (
        _correct_option_ids(db, [q.id for _, q in in_scope]) if submitted or practice else {}
    )

    # Nạp asset bằng MỘT truy vấn cho mỗi loại. `Question` chỉ có cột id chứ
    # không có relationship, nên không nạp trước ở đây thì thành N+1 — và với
    # một đề 200 câu đó là 200 lượt đi lại database cho mỗi lần mở bài.
    audio_ids = {q.audio_asset_id for _, q in in_scope if q.audio_asset_id} | {
        q.question_set.audio_asset_id
        for _, q in in_scope
        if q.question_set is not None and q.question_set.audio_asset_id
    }
    image_ids = {q.image_asset_id for _, q in in_scope if q.image_asset_id}
    # Ảnh ngữ liệu nạp cùng lượt với ảnh câu hỏi. Tra lẻ từng ô sẽ là ba lượt đi
    # lại database cho mỗi cụm Part 7, và một đề đầy đủ có hàng chục cụm.
    for _, question in in_scope:
        stimulus_set = question.question_set
        if stimulus_set is None:
            continue
        image_ids |= {
            asset_id
            for asset_id in (
                stimulus_set.passage_image_id,
                stimulus_set.passage_2_image_id,
                stimulus_set.passage_3_image_id,
            )
            if asset_id
        }
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

    # Số câu đọc từ đề, KHÔNG đánh lại từ 1. Luyện riêng Part 5 của một đề đầy
    # đủ phải hiện 101-130, vì đó là con số người học đọc thấy trong mọi tài
    # liệu — đánh lại từ 1 làm họ không đối chiếu được với sách.
    for number, question in in_scope:
        item = answered_by_question[question.id]
        reveal = submitted or (practice and item.selected_option_id is not None)
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
                image_attribution=image_asset.attribution if image_asset is not None else None,
                image_license=image_asset.license if image_asset is not None else None,
                set_id=str(stimulus.id) if stimulus is not None else None,
                set_title=stimulus.title if first_of_set and stimulus is not None else None,
                passages=(
                    _passages(stimulus, image_by_id, image_driver)
                    if first_of_set and stimulus is not None
                    else []
                ),
                options=[
                    OptionPublic(
                        id=str(option.id),
                        label=option.label,
                        content=option.content,
                        # Gác bằng ĐÚNG `reveal` đã dùng cho `correct_option_id`
                        # và `explanation`, không phải một luật thứ hai: hai luật
                        # cho cùng một câu hỏi "được lộ chưa" thì sẽ có ngày lệch,
                        # và cái lệch sẽ là cái lộ sớm.
                        content_vi=option.content_vi if reveal else None,
                        spoken_text=option.spoken_text if reveal else None,
                    )
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
        elapsed_seconds=attempt.elapsed_seconds,
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

    # Lọc `published` ở CẢ HAI tầng: câu, và cụm mà câu thuộc về.
    #
    # Lọc mỗi câu là chưa đủ, và chỗ hở im lặng: một câu đã xuất bản nằm dưới
    # một cụm còn nháp sẽ mang theo cả ngữ liệu lẫn bản thu của cụm đó ra ngoài
    # (`_passages` đọc thẳng từ `question_set`). Người học thấy một bài đọc chưa
    # ai duyệt, và nội dung đó trông hoàn toàn bình thường — không có gì để phát
    # hiện. Đúng hình dạng lỗ rò cây dictation đã có, và đó là lý do cây ấy lọc
    # `published` ở cả bốn tầng.
    #
    # `outerjoin` chứ không `join`: `question.set_id` là NULL ở Part 1, 2 và 5 —
    # câu đứng riêng, không có cụm nào để duyệt. `join` thường sẽ lặng lẽ loại
    # sạch ba part đó khỏi mọi lượt làm bài.
    rows = db.execute(
        select(PracticeTestQuestion.position, Question.id, Question.part)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .outerjoin(QuestionSet, QuestionSet.id == Question.set_id)
        .where(
            PracticeTestQuestion.test_id == test.id,
            Question.status == PUBLISHED,
            or_(Question.set_id.is_(None), QuestionSet.status == PUBLISHED),
        )
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


@router.get("", response_model=Page[AttemptSummary])
def list_attempts(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[AttemptSummary]:
    """Lịch sử làm bài của chính người đang đăng nhập, mới nhất trước.

    **Không tự chốt bài hết giờ ở đây.** `GET /{id}` có làm điều đó, và đúng —
    mở một lượt đã quá giờ thì nó phải được chấm. Nhưng làm thế trong danh sách
    nghĩa là một lần mở trang lịch sử ghi hàng chục hàng vào database, và một
    GET không nên có tác dụng phụ ở quy mô đó. Ở đây chỉ ĐỌC: `remaining_seconds`
    bằng 0 là dấu hiệu để giao diện nói "đã quá giờ", còn việc chốt để lần mở
    lượt đó lo.

    Đếm gộp bằng hai truy vấn, không phải hai truy vấn mỗi lượt: một trang lịch
    sử 50 lượt sẽ là một trăm lượt đi lại database cho mấy con số.
    """
    mine = select(Attempt).where(Attempt.user_id == current_user.id)
    total = count_rows(db, mine)
    attempts = (
        db.scalars(
            mine
            # Khoá phụ để thứ tự là TOÀN PHẦN. Hai lượt mở trong cùng một giây
            # có thứ tự không xác định, và với LIMIT/OFFSET thì đó là một lượt
            # xuất hiện hai lần còn một lượt biến mất.
            .order_by(Attempt.started_at.desc(), Attempt.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .unique()
        .all()
    )
    if not attempts:
        return page_of([], total, limit, offset)

    ids = [attempt.id for attempt in attempts]
    tallies = {
        attempt_id: (asked, answered, correct)
        for attempt_id, asked, answered, correct in db.execute(
            select(
                AttemptItem.attempt_id,
                func.count(AttemptItem.id),
                func.count(AttemptItem.selected_option_id),
                func.count(1).filter(AttemptItem.is_correct.is_(True)),
            )
            .where(AttemptItem.attempt_id.in_(ids))
            .group_by(AttemptItem.attempt_id)
        ).all()
    }

    out: list[AttemptSummary] = []
    for attempt in attempts:
        # `asked`, KHÔNG phải `total`: `total` ở hàm này là tổng số lượt của cả
        # danh sách, và gán đè lên nó ở đây làm `page_of` trả về số câu của lượt
        # cuối cùng. Một con số trông hợp lý và sai — kiểu hỏng không ai soi ra
        # khi đọc lướt.
        asked, answered, correct = tallies.get(attempt.id, (0, 0, 0))
        out.append(
            AttemptSummary(
                id=str(attempt.id),
                test_slug=attempt.test.slug,
                test_title=attempt.test.title,
                collection_slug=(
                    attempt.test.collection.slug if attempt.test.collection is not None else None
                ),
                status=attempt.status,
                scope=attempt.scope,
                review_mode=attempt.review_mode,
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
                question_count=asked,
                answered_count=answered,
                # Số câu đúng chỉ tồn tại sau khi chốt: `is_correct` được ghi ở
                # `_finalise`, nên với bài đang dở nó toàn NULL và một số 0 ở đây
                # sẽ đọc như "làm sai hết".
                correct_count=correct if attempt.status != "in_progress" else None,
                total_scaled=attempt.total_scaled,
                remaining_seconds=_remaining(attempt),
            )
        )
    return page_of(out, total, limit, offset)


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


def _result(attempt: Attempt) -> AttemptResult:
    """Kết quả của một lượt đã chốt.

    Tách khỏi endpoint nộp bài để `GET .../result` dùng chung: tải lại trang kết
    quả phải cho ra đúng những con số vừa thấy, và hai bản sao của phép dựng ấy
    sẽ trôi khỏi nhau ở đúng chỗ khó nhận ra nhất — dòng giải thích vì sao không
    có điểm quy đổi.
    """
    correct = sum(1 for item in attempt.items if item.is_correct)
    note = None
    if attempt.scope != "full":
        note = "Chỉ làm một phần của đề nên không quy đổi ra điểm TOEIC."
    elif attempt.test.kind != "full":
        # Nói ra CHÍNH XÁC vì sao, chứ không chỉ "không có điểm": người học vừa
        # làm đúng 6/10 và cần biết đó không phải kết quả tệ, chỉ là đề rút gọn
        # không có thang quy đổi.
        note = (
            "Đề rút gọn không quy đổi ra điểm TOEIC — thang điểm được dựng cho đề đầy đủ 200 câu."
        )
    elif attempt.total_scaled is None:
        note = "Đề này chưa có bảng quy đổi điểm, nên chỉ có số câu đúng."

    return AttemptResult(
        id=str(attempt.id),
        status=attempt.status,
        correct_count=correct,
        question_count=len(attempt.items),
        elapsed_seconds=attempt.elapsed_seconds,
        listening_raw=attempt.listening_raw,
        reading_raw=attempt.reading_raw,
        listening_scaled=attempt.listening_scaled,
        reading_scaled=attempt.reading_scaled,
        total_scaled=attempt.total_scaled,
        scale_note=note,
    )


@router.post("/{attempt_id}/submit", response_model=AttemptResult)
def submit_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptResult:
    attempt = _load(db, attempt_id, current_user)
    if attempt.status == "in_progress":
        _finalise(db, attempt, "submitted")

        # Chỉ trao khi lượt này VỪA chuyển sang nộp. Gọi lại `/submit` trên một
        # lượt đã nộp không vào nhánh này, và kể cả có vào thì
        # `uq_xp_event_source` cũng chặn — hai lớp, vì đây là nguồn XP lớn nhất
        # (30 điểm) nên trao trùng ở đây tốn hơn hẳn chỗ khác.
        try:
            progression.award(
                db,
                user_id=current_user.id,
                source_type="attempt_submit",
                source_id=attempt.id,
                amount=progression.xp_for(db, "attempt_submit"),
                timezone=ensure_profile(db, current_user).timezone,
            )
        except Exception:  # pragma: no cover - XP không được làm hỏng bài nộp
            pass

        db.commit()
        db.refresh(attempt)
    return _result(attempt)


@router.get("/{attempt_id}/result", response_model=AttemptResult)
def read_result(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptResult:
    """Kết quả của một lượt đã nộp.

    Tồn tại để tải lại trang không làm mất bảng kết quả: `POST /submit` trả kết
    quả đúng một lần, nên nếu không có đường đọc lại thì một lần F5 sẽ đưa người
    học sang màn xem đáp án mà không hiểu vì sao điểm biến mất.

    Lượt CHƯA nộp thì 409 chứ không trả kết quả rỗng: một bảng điểm toàn số 0
    cho bài đang làm dở là thứ đọc như bài đã bị chấm.
    """
    attempt = _load(db, attempt_id, current_user)
    if attempt.status == "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lượt làm này chưa nộp")
    return _result(attempt)
