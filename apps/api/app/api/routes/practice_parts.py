"""Luyện theo part rời — `practice_parts.py` (ROADMAP §3, SPEC-GRAMMAR §3 P1).

Bốn thứ: danh sách part kèm nhãn đo từ kho thật, trang chiến thuật từ
`part_tactics`, và PHIÊN luyện theo khuôn khu luyện thi: tạo phiên (câu chốt
lúc bắt đầu, có snapshot), trả lời từng câu (phản hồi tức thì, lần đầu là lần
cuối), xem lại danh sách và từng phiên cũ.

Không XP, không streak cho drill part — có chủ đích, lần này. `grammar_attempt`
đã được nối vào cả hai vì đó là cam kết của SPEC-GRAMMAR G5; luyện part chưa có
cam kết nào, và một nguồn XP mới là quyết định sản phẩm chứ không phải việc nối
dây còn thừa.

Phân tầng `published` theo đúng bài học dictation/grammar: câu published nằm
dưới set nháp thì passage của nó cũng là nháp — lọc một tầng là rò nội dung.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.api.routes._transcript import transcript_of
from app.core.database import get_db
from app.core.media import public_audio_url, public_video_url
from app.core.storage import get_driver
from app.models import (
    AudioAsset,
    GrammarTopic,
    ImageAsset,
    PartSession,
    PartSessionItem,
    PartTactics,
    Question,
    QuestionLabel,
    QuestionOption,
    QuestionSet,
    User,
)
from app.schemas.practice import (
    OptionPublic,
    PartAnswerResult,
    PartDrillQuestion,
    PartLabelCount,
    PartSessionAnswer,
    PartSessionCreate,
    PartSessionDetail,
    PartSessionItemPublic,
    PartSessionSummary,
    PartSummary,
    PartTacticsPublic,
    PassagePublic,
)
from app.services.labels import LABELS

router = APIRouter(tags=["practice"])

PUBLISHED = "published"


def _open_filters() -> tuple[Any, ...]:
    """Câu published VÀ không nằm dưới set nháp — một định nghĩa cho mọi phép
    đếm, mọi mẫu câu, và mọi lần chốt câu vào phiên."""
    return (
        Question.status == PUBLISHED,
        or_(
            Question.set_id.is_(None),
            Question.set_id.in_(select(QuestionSet.id).where(QuestionSet.status == PUBLISHED)),
        ),
    )


def _grammar_slugs(db: Session) -> dict[str, str]:
    rows = db.execute(
        select(GrammarTopic.code, GrammarTopic.slug).where(GrammarTopic.code.isnot(None))
    ).all()
    return {code: slug for code, slug in rows if code is not None}


def _label_row(code: str, count: int, grammar_slugs: dict[str, str]) -> PartLabelCount:
    label = LABELS.get(code)
    return PartLabelCount(
        code=code,
        title=label.label_vi if label else code,
        count=count,
        grammar_topic_slug=grammar_slugs.get(code),
    )


def _label_counts(db: Session, part: int) -> list[PartLabelCount]:
    """Nhãn của một part, đếm từ câu published — cùng bộ lọc với danh sách câu."""
    rows = db.execute(
        select(
            QuestionLabel.code,
            func.count(func.distinct(QuestionLabel.question_id)),
        )
        .join(Question, Question.id == QuestionLabel.question_id)
        .where(Question.part == part, *_open_filters())
        .group_by(QuestionLabel.code)
        .order_by(func.count(func.distinct(QuestionLabel.question_id)).desc())
    ).all()
    slugs = _grammar_slugs(db)
    return [_label_row(code, count, slugs) for code, count in rows]


def _question_labels(db: Session, question_id: uuid.UUID) -> list[PartLabelCount]:
    codes = list(
        db.scalars(select(QuestionLabel.code).where(QuestionLabel.question_id == question_id))
    )
    slugs = _grammar_slugs(db)
    return [_label_row(code, 0, slugs) for code in codes]


@router.get("/practice/parts", response_model=list[PartSummary])
def list_parts(db: Session = Depends(get_db)) -> list[PartSummary]:
    """Bảy part, số câu và nhãn ĐO THẬT — nguồn số liệu cho hub. Danh sách công
    khai (khuôn khu luyện thi): khách phải xem được luyện những gì; chiến thuật
    và phiên mới đòi tài khoản."""
    counts: dict[int, int] = {
        part: n
        for part, n in db.execute(
            select(Question.part, func.count(Question.id))
            .where(*_open_filters())
            .group_by(Question.part)
        ).all()
    }
    return [
        PartSummary(
            part=part,
            question_count=counts.get(part, 0),
            labels=_label_counts(db, part),
        )
        for part in range(1, 8)
    ]


@router.get("/practice/parts/{part}/tactics", response_model=PartTacticsPublic)
def get_tactics(
    part: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> PartTacticsPublic:
    """Trang chiến thuật — nội dung, nên đòi đăng nhập; danh sách part phía trên
    nó thì công khai để khách biết có gì để luyện."""
    row = db.get(PartTactics, part)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tactics not found")
    # URL sinh ở máy chủ từ khoá, không trả khoá thô — nhà cung cấp là một biến
    # cấu hình (cùng lý do `video_url` của grammar).
    return PartTacticsPublic(
        part=row.part,
        body=row.body,
        video_url=public_video_url(row.video_storage_key) if row.video_storage_key else None,
    )


def _question_payloads(
    db: Session, questions: list[Question], part: int
) -> dict[uuid.UUID, PartDrillQuestion]:
    """Serialize một loạt câu: audio/ảnh/passage/nhãn, batch hết, không N+1.

    Passage chỉ gắn vào câu ĐẦU của mỗi set trong danh sách — client nhóm lại
    theo `set_id`. Luật này lấy từ `attempt.py`: lặp đoạn văn trên ba câu là ba
    lần cùng một payload.
    """
    set_ids = {q.set_id for q in questions if q.set_id is not None}
    audio_ids = {q.audio_asset_id for q in questions if q.audio_asset_id is not None}
    image_ids = {q.image_asset_id for q in questions if q.image_asset_id is not None}
    sets = (
        {s.id: s for s in db.scalars(select(QuestionSet).where(QuestionSet.id.in_(set_ids)))}
        if set_ids
        else {}
    )
    for group in sets.values():
        # Audio của Part 3/4 nằm trên SET; ảnh passage nằm trên SET. Không gom
        # thì mọi câu cụm đều nhận `audio_url: null` — cái hỏng im lặng mà
        # `_question_admin` từng dính.
        if group.audio_asset_id is not None:
            audio_ids.add(group.audio_asset_id)
        for img in (
            group.passage_image_id,
            group.passage_2_image_id,
            group.passage_3_image_id,
        ):
            if img is not None:
                image_ids.add(img)
    audio_by_id = (
        {a.id: a for a in db.scalars(select(AudioAsset).where(AudioAsset.id.in_(audio_ids)))}
        if audio_ids
        else {}
    )
    image_by_id = (
        {a.id: a for a in db.scalars(select(ImageAsset).where(ImageAsset.id.in_(image_ids)))}
        if image_ids
        else {}
    )
    labels_by_question: dict[uuid.UUID, list[PartLabelCount]] = {}
    if questions:
        rows = db.execute(
            select(QuestionLabel.question_id, QuestionLabel.code).where(
                QuestionLabel.question_id.in_([q.id for q in questions])
            )
        ).all()
        part_labels = {lab.code: lab for lab in _label_counts(db, part)}
        for qid, code in rows:
            if code in part_labels:
                labels_by_question.setdefault(qid, []).append(part_labels[code])

    image_driver = get_driver("image")
    seen_sets: set[uuid.UUID] = set()
    out: dict[uuid.UUID, PartDrillQuestion] = {}
    for q in questions:
        stimulus = sets.get(q.set_id) if q.set_id is not None else None
        first_of_set = stimulus is not None and stimulus.id not in seen_sets
        if stimulus is not None:
            seen_sets.add(stimulus.id)

        audio_asset = None
        if q.audio_asset_id is not None:
            audio_asset = audio_by_id.get(q.audio_asset_id)
        elif first_of_set and stimulus is not None and stimulus.audio_asset_id is not None:
            audio_asset = audio_by_id.get(stimulus.audio_asset_id)

        passages: list[PassagePublic] = []
        if first_of_set and stimulus is not None:
            for text, img_id in (
                (stimulus.passage, stimulus.passage_image_id),
                (stimulus.passage_2, stimulus.passage_2_image_id),
                (stimulus.passage_3, stimulus.passage_3_image_id),
            ):
                asset = image_by_id.get(img_id) if img_id else None
                if not text and asset is None:
                    continue
                passages.append(
                    PassagePublic(
                        text=text,
                        image_url=image_driver.public_url(asset.storage_key) if asset else None,
                        image_alt=asset.alt_text if asset else None,
                        image_attribution=asset.attribution if asset else None,
                        image_license=asset.license if asset else None,
                    )
                )

        question_image = image_by_id.get(q.image_asset_id) if q.image_asset_id is not None else None
        out[q.id] = PartDrillQuestion(
            id=str(q.id),
            part=q.part,
            prompt_text=q.prompt_text,
            audio_url=public_audio_url(audio_asset.storage_key) if audio_asset else None,
            image_url=(
                image_driver.public_url(question_image.storage_key) if question_image else None
            ),
            set_id=str(stimulus.id) if first_of_set and stimulus is not None else None,
            passages=passages,
            options=[
                OptionPublic(id=str(o.id), label=o.label, content=o.content, content_vi=None)
                for o in sorted(q.options, key=lambda o: o.label)
            ],
            labels=labels_by_question.get(q.id, []),
        )
    return out


def _own_session(db: Session, session_id: uuid.UUID, user: User) -> PartSession:
    sess = db.get(PartSession, session_id)
    # 404 chứ không 403: phiên của người khác không tồn tại đối với bạn.
    if sess is None or sess.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return sess


def _remaining(sess: PartSession) -> int | None:
    if sess.time_limit_seconds is None:
        return None
    created = sess.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return max(sess.time_limit_seconds - int((datetime.now(UTC) - created).total_seconds()), 0)


def _expire_if_out_of_time(db: Session, sess: PartSession) -> None:
    """Hết giờ là chốt phiên tại chỗ đọc.

    Không có cron nào chạy một mình trên free tier — nếu không đẩy hạn vào mọi
    đường đọc/ghi thì một phiên không ai mở vẫn "đang làm" vĩnh viễn, và lịch
    sử nói dối.
    """
    if sess.finished_at is None and sess.time_limit_seconds is not None and _remaining(sess) == 0:
        sess.finished_at = datetime.now(UTC)
        sess.expired = True
        db.commit()
        db.refresh(sess)


def _session_detail(db: Session, sess: PartSession) -> PartSessionDetail:
    items = list(
        db.scalars(
            select(PartSessionItem)
            .where(PartSessionItem.session_id == sess.id)
            .order_by(PartSessionItem.position)
        )
    )
    questions = (
        list(
            db.scalars(
                select(Question)
                .where(Question.id.in_([i.question_id for i in items]))
                .options(selectinload(Question.options))
            )
        )
        if items
        else []
    )
    payloads = _question_payloads(db, questions, sess.part)
    # Lộ theo TỪNG câu: chưa trả lời thì không có gì để lộ; đã trả lời thì
    # người ta đang xem lại — đúng mục đích tồn tại của phiên. Lời đọc và lời
    # thoại đi kèm cùng luật đó, và cụm chỉ lộ lời thoại khi CẢ cụm đã trả
    # lời — lộ sau câu đầu là lộ luôn đáp án hai câu sau.
    by_qid = {q.id: q for q in questions}
    set_ids = {q.set_id for q in questions if q.set_id is not None}
    sets = (
        {s.id: s for s in db.scalars(select(QuestionSet).where(QuestionSet.id.in_(set_ids)))}
        if set_ids
        else {}
    )
    answered_ids = {i.question_id for i in items if i.answered_at is not None}
    set_answered = {
        sid: all(
            i.question_id in answered_ids for i in items if by_qid[i.question_id].set_id == sid
        )
        for sid in set_ids
    }
    out_items: list[PartSessionItemPublic] = []
    for item in items:
        payload = payloads.get(item.question_id)
        if payload is None:  # pragma: no cover — item luôn trỏ câu còn sống
            continue
        answered = item.answered_at is not None
        question = by_qid[item.question_id]
        correct = next((o for o in question.options if o.is_correct), None)
        if answered:
            spoken = {str(o.id): o.spoken_text for o in question.options if o.spoken_text}
            for po in payload.options:
                po.spoken_text = spoken.get(po.id)
            if question.set_id is None:
                payload.transcript = transcript_of(question.audio_script)
            elif payload.set_id is not None:  # câu ĐẦU của cụm mang lời thoại
                payload.transcript = (
                    transcript_of(sets[question.set_id].audio_script)
                    if set_answered.get(question.set_id)
                    else []
                )
        out_items.append(
            PartSessionItemPublic(
                position=item.position,
                question=payload,
                selected_option_id=str(item.option_id) if item.option_id else None,
                is_correct=item.is_correct,
                correct_option_id=str(correct.id) if answered and correct else None,
                explanation=question.explanation if answered else None,
            )
        )
    return PartSessionDetail(
        id=str(sess.id),
        part=sess.part,
        labels=list(sess.labels),
        label_titles=[LABELS[c].label_vi if c in LABELS else c for c in sess.labels],
        created_at=sess.created_at,
        finished_at=sess.finished_at,
        expired=sess.expired,
        time_limit_seconds=sess.time_limit_seconds,
        remaining_seconds=None if sess.finished_at else _remaining(sess),
        items=out_items,
    )


@router.post(
    "/practice/parts/{part}/sessions",
    response_model=PartSessionDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    part: int,
    body: PartSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PartSessionDetail:
    """Chốt một phiên: TOÀN BỘ câu published của part (+ nhãn), snapshot vào item.

    Mẫu ở SERVER chứ không ở client: client tự chọn câu thì "lịch sử phiên"
    chỉ là lời kể của bên dễ nói dối nhất. Số câu không còn là lựa chọn —
    người học chỉnh đồng hồ, không chỉnh đề.
    """
    if not 1 <= part <= 7:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    query = select(Question).where(Question.part == part, *_open_filters()).order_by(func.random())
    if body.labels:
        query = query.where(
            Question.id.in_(
                select(QuestionLabel.question_id).where(QuestionLabel.code.in_(body.labels))
            )
        )
    questions = list(db.scalars(query))
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phần này chưa có câu hỏi nào — thử nhãn khác.",
        )
    sess = PartSession(
        user_id=user.id,
        part=part,
        labels=body.labels,
        time_limit_seconds=body.time_limit_minutes * 60 if body.time_limit_minutes else None,
    )
    db.add(sess)
    db.flush()
    for position, question in enumerate(questions, start=1):
        db.add(PartSessionItem(session_id=sess.id, question_id=question.id, position=position))
    db.commit()
    db.refresh(sess)
    return _session_detail(db, sess)


@router.get("/practice/parts/sessions", response_model=list[PartSessionSummary])
def list_sessions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[PartSessionSummary]:
    """Lịch sử phiên của chính mình, mới nhất trước."""
    sessions = list(
        db.scalars(
            select(PartSession)
            .where(PartSession.user_id == user.id)
            .order_by(PartSession.created_at.desc())
            .limit(50)
        )
    )
    for sess in sessions:
        _expire_if_out_of_time(db, sess)
    if not sessions:
        return []
    stats = {
        sid: (total, answered, correct)
        for sid, total, answered, correct in db.execute(
            select(
                PartSessionItem.session_id,
                func.count(),
                func.count(PartSessionItem.answered_at),
                func.sum(case((PartSessionItem.is_correct.is_(True), 1), else_=0)),
            )
            .where(PartSessionItem.session_id.in_([s.id for s in sessions]))
            .group_by(PartSessionItem.session_id)
        ).all()
    }
    out: list[PartSessionSummary] = []
    for sess in sessions:
        total, answered, correct = stats.get(sess.id, (0, 0, 0))
        out.append(
            PartSessionSummary(
                id=str(sess.id),
                part=sess.part,
                labels=list(sess.labels),
                label_titles=[LABELS[c].label_vi if c in LABELS else c for c in sess.labels],
                created_at=sess.created_at,
                finished_at=sess.finished_at,
                total=total,
                answered=answered,
                correct=int(correct or 0),
            )
        )
    return out


@router.get("/practice/parts/sessions/{session_id}", response_model=PartSessionDetail)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PartSessionDetail:
    sess = _own_session(db, session_id, user)
    _expire_if_out_of_time(db, sess)
    return _session_detail(db, sess)


@router.post("/practice/parts/sessions/{session_id}/answers", response_model=PartAnswerResult)
def answer(
    session_id: uuid.UUID,
    body: PartSessionAnswer,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PartAnswerResult:
    """Trả lời một câu của phiên. Lần ĐẦU là lần cuối — phản hồi tức thì nên
    câu đã trả lời là đóng; làm lại thì mở phiên mới."""
    sess = _own_session(db, session_id, user)
    _expire_if_out_of_time(db, sess)
    item = db.get(PartSessionItem, (sess.id, uuid.UUID(body.question_id)))
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not in this session"
        )
    if sess.finished_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phiên đã kết thúc" + (" vì hết giờ." if sess.expired else "."),
        )
    if item.answered_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Câu này đã được trả lời trong phiên"
        )
    option = db.get(QuestionOption, uuid.UUID(body.option_id))
    if option is None or option.question_id != item.question_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Option not found for this question"
        )
    question = db.get(Question, item.question_id)
    if question is None:  # pragma: no cover — item FK RESTRICT, câu không xoá được
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    correct = next((o for o in question.options if o.is_correct), None)
    if correct is None:  # pragma: no cover — `validate_question` chặn từ cửa ghi
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Question has no correct option"
        )
    item.option_id = option.id
    item.is_correct = option.id == correct.id
    item.answered_at = datetime.now(UTC)
    # Flush TRƯỚC khi đếm: session chạy `autoflush=False`, SELECT bên dưới mà
    # không flush thì thấy câu này vẫn unanswered — phiên không bao giờ tự chốt.
    db.flush()
    remaining = db.scalar(
        select(func.count())
        .select_from(PartSessionItem)
        .where(PartSessionItem.session_id == sess.id, PartSessionItem.answered_at.is_(None))
    )
    if not remaining and sess.finished_at is None:
        sess.finished_at = datetime.now(UTC)
    # Lời đọc/ lời thoại của CHÍNH câu vừa trả lời — client cần nó ngay để hiện
    # mà không nạp lại cả phiên (một phiên Part 5 là 127 câu).
    spoken = {str(o.id): o.spoken_text for o in question.options if o.spoken_text}
    transcript = transcript_of(question.audio_script) if question.set_id is None else []
    if question.set_id is not None:
        open_in_set = db.scalar(
            select(func.count())
            .select_from(PartSessionItem)
            .join(Question, Question.id == PartSessionItem.question_id)
            .where(
                PartSessionItem.session_id == sess.id,
                Question.set_id == question.set_id,
                PartSessionItem.answered_at.is_(None),
            )
        )
        if not open_in_set:
            stimulus = db.get(QuestionSet, question.set_id)
            transcript = transcript_of(stimulus.audio_script) if stimulus else []
    db.commit()
    return PartAnswerResult(
        is_correct=item.is_correct,
        correct_option_id=str(correct.id),
        explanation=question.explanation,
        labels=_question_labels(db, question.id),
        spoken=spoken,
        transcript=transcript,
    )


@router.post("/practice/parts/sessions/{session_id}/finish", response_model=PartSessionDetail)
def finish(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PartSessionDetail:
    """Chốt phiên sớm (bỏ dở cũng tính) — `finished_at` chỉ ghi một lần."""
    sess = _own_session(db, session_id, user)
    _expire_if_out_of_time(db, sess)
    if sess.finished_at is None:
        sess.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(sess)
    return _session_detail(db, sess)
