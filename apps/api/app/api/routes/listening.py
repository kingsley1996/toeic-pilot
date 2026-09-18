"""Endpoint Listening Lab: bài nghe user tự tạo từ URL YouTube.

Ownership là biên an ninh ở mọi endpoint: bài của user này không bao giờ hiện
hay chấm cho user khác — thiếu test là thiếu cả tính năng (mọi route dưới đây
đều có case 404-chéo trong `tests/test_listening_api.py`).

Không `reward_study`/XP ở slice này: cổng thưởng của dictation cũ gắn với
`is_complete` của NÓ, móc chung vào đây là trả thưởng hai lần cho một định
nghĩa "đúng" — cùng cái bẫy đã ghi ở `learning_dictation.submit_dictation`.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import Quota, rate_limit
from app.models import (
    ListeningAttempt,
    ListeningContent,
    ListeningSegment,
    User,
)
from app.schemas.learning import WordDiff
from app.schemas.listening import (
    ListeningAttemptResult,
    ListeningAttemptSubmit,
    ListeningCaptionsPublic,
    ListeningCaptionsRequest,
    ListeningContentCreate,
    ListeningContentCreated,
    ListeningContentPublic,
    ListeningContentSummary,
    ListeningSegmentPublic,
)
from app.services import dictation as dictation_grader
from app.services.listening_source import SourceError, resolve_source
from app.services.listening_transcript import (
    TranscriptValidation,
    is_speakable,
    parse_srt_vtt,
    segments_to_vtt,
    validate_transcript,
)
from app.services.listening_youtube_captions import (
    CAPTIONS_UNAVAILABLE,
    CaptionError,
    fetch_youtube_captions,
)

router = APIRouter(tags=["learning"])

# Gọi YouTube InnerTube mỗi lần; trần chống loop, không phải hoá đơn.
CAPTIONS_QUOTA = Quota(limit=30, window_seconds=60 * 10)


def _to_public(content: ListeningContent) -> ListeningContentPublic:
    return ListeningContentPublic(
        id=str(content.id),
        source_type=content.source_type,
        source_url=content.source_url,
        external_id=content.external_id,
        title=content.title,
        duration_seconds=content.duration_seconds,
        transcript_status=content.transcript_status,
        segments=[
            ListeningSegmentPublic(
                id=str(seg.id),
                index=seg.segment_index,
                start=float(seg.start_seconds),
                end=float(seg.end_seconds),
                text=seg.text,
            )
            for seg in content.segments
        ],
        created_at=content.created_at,
    )


def _get_owned_content(db: Session, user_id: uuid.UUID, content_id: uuid.UUID) -> ListeningContent:
    """Bài của chính user, kèm segments. 404 cho cả "không có" lẫn "của người
    khác" — phân biệt hai case là lộ bài người khác tồn tại."""
    content = db.scalars(
        select(ListeningContent)
        .where(ListeningContent.id == content_id, ListeningContent.user_id == user_id)
        .options(selectinload(ListeningContent.segments))
    ).first()
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content


@router.post(
    "/listening/captions",
    response_model=ListeningCaptionsPublic,
    dependencies=[Depends(rate_limit("listening-captions", CAPTIONS_QUOTA, fail_open=True))],
)
def fetch_listening_captions(
    body: ListeningCaptionsRequest,
    current_user: User = Depends(get_current_user),
) -> ListeningCaptionsPublic:
    del current_user
    try:
        source = resolve_source(body.url)
    except SourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code}
        ) from exc
    if source.type != "youtube":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "UNSUPPORTED_SOURCE"},
        )
    try:
        captions = fetch_youtube_captions(source.external_id)
    except CaptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code}
        ) from exc
    kind: Literal["manual", "asr"] = "asr" if captions.kind == "asr" else "manual"
    # Dòng nhạc/nền ([Music], [♪♪♪]) không phải câu thoại — loại ở đây để con
    # số báo về form khớp đúng số câu tạo được ở endpoint dưới.
    kept = [seg for seg in captions.segments if is_speakable(seg.text)]
    if not kept:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": CAPTIONS_UNAVAILABLE},
        ) from None
    return ListeningCaptionsPublic(
        language=captions.language,
        kind=kind,
        raw=segments_to_vtt(kept),
        segment_count=len(kept),
        title=captions.title,
    )


@router.post("/listening/contents", response_model=ListeningContentCreated)
def create_listening_content(
    body: ListeningContentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListeningContentCreated:
    try:
        source = resolve_source(body.source.url)
    except SourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code}
        ) from exc
    if source.type != body.source.type:
        # Client nói tiktok nhưng URL là youtube (hoặc ngược lại) — tin URL đã
        # resolve, không tin nhãn client gửi: nhãn sai mà nhận là hỏng im lặng.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "SOURCE_TYPE_MISMATCH"},
        ) from None

    title = body.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "EMPTY_TITLE"}
        )

    parsed = parse_srt_vtt(body.transcript.raw)
    validation: TranscriptValidation = validate_transcript(parsed)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_TRANSCRIPT", "errors": validation.errors},
        )

    # Mỗi segment là một bài dictation — dòng không lời ([Music], [♪♪♪]) thành
    # bài là vô nghĩa nên loại từ đầu, đánh lại index liên tục. Hết sạch thì
    # không cho tạo: bài không câu thoại mà vẫn lưu là đúng issue đang sửa.
    speakable = [seg for seg in parsed if is_speakable(seg.text)]
    if not speakable:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_TRANSCRIPT", "errors": ["Transcript has no speakable lines"]},
        )
    dropped = len(parsed) - len(speakable)
    warnings = list(validation.warnings)
    if dropped:
        warnings.append(
            f"Skipped {dropped} non-dialogue line(s) (music/background noise)"
        )

    content = ListeningContent(
        user_id=current_user.id,
        source_type=source.type,
        source_url=source.url,
        external_id=source.external_id,
        title=title,
        transcript_status="ready",
        segments=[
            ListeningSegment(
                segment_index=index,
                start_seconds=seg.start,
                end_seconds=seg.end,
                text=seg.text,
                normalized_text=" ".join(dictation_grader.normalise(seg.text)),
            )
            for index, seg in enumerate(speakable)
        ],
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    return ListeningContentCreated(
        id=str(content.id),
        status=content.transcript_status,
        segment_count=len(speakable),
        warnings=warnings,
    )


@router.get("/listening/contents", response_model=list[ListeningContentSummary])
def list_listening_contents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ListeningContentSummary]:
    contents = db.scalars(
        select(ListeningContent)
        .where(ListeningContent.user_id == current_user.id)
        .order_by(ListeningContent.created_at.desc())
    ).all()
    if not contents:
        return []

    content_ids = [c.id for c in contents]
    counts: dict[uuid.UUID, int] = {}
    for content_id, total in db.execute(
        select(ListeningSegment.content_id, func.count())
        .where(ListeningSegment.content_id.in_(content_ids))
        .group_by(ListeningSegment.content_id)
    ).all():
        counts[content_id] = total
    completed: dict[uuid.UUID, int] = {}
    for content_id, total in db.execute(
        select(
            ListeningSegment.content_id,
            func.count(func.distinct(ListeningAttempt.segment_id)),
        )
        .join(ListeningAttempt, ListeningAttempt.segment_id == ListeningSegment.id)
        .where(
            ListeningSegment.content_id.in_(content_ids),
            ListeningAttempt.user_id == current_user.id,
            ListeningAttempt.is_complete.is_(True),
        )
        .group_by(ListeningSegment.content_id)
    ).all():
        completed[content_id] = total
    return [
        ListeningContentSummary(
            id=str(c.id),
            title=c.title,
            source_type=c.source_type,
            external_id=c.external_id,
            segment_count=counts.get(c.id, 0),
            completed_count=completed.get(c.id, 0),
            created_at=c.created_at,
        )
        for c in contents
    ]


@router.get("/listening/contents/{content_id}", response_model=ListeningContentPublic)
def get_listening_content(
    content_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListeningContentPublic:
    return _to_public(_get_owned_content(db, current_user.id, content_id))


@router.post("/listening/contents/{content_id}/attempts", response_model=ListeningAttemptResult)
def submit_listening_attempt(
    content_id: uuid.UUID,
    body: ListeningAttemptSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListeningAttemptResult:
    content = _get_owned_content(db, current_user.id, content_id)
    segment = next((s for s in content.segments if s.id == body.segment_id), None)
    if segment is None:
        # Segment không thuộc bài này (kể cả segment của bài KHÁC của cùng user)
        # — chấm chéo bài là hỏng im lặng tiến độ từng bài.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    # Chấm bằng đáp án segment, đúng bộ chấm dictation cũ — không copy, không fork.
    result = dictation_grader.grade(segment.text, body.answer)
    attempt = ListeningAttempt(
        user_id=current_user.id,
        segment_id=segment.id,
        answer=body.answer,
        accuracy=result.accuracy,
        is_complete=result.is_complete,
        word_diff=result.as_json(),
        time_spent_seconds=body.time_spent_seconds,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return ListeningAttemptResult(
        attempt_id=str(attempt.id),
        is_correct=result.is_complete,
        similarity=str(result.accuracy),
        expected_text=segment.text,
        diff=[WordDiff(op=item.op, word=item.word) for item in result.diff],
    )
