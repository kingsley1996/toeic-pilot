"""Learner-facing endpoints for vocabulary and dictation.

Every read here filters `status == 'published'`. That filter is the only thing
standing between a half-written draft and a learner's screen, and forgetting it
fails silently — the content simply appears. Each endpoint has a test asserting
draft content stays invisible (ADR-001 A5.3).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.media import public_audio_url
from app.models import (
    DictationAttempt,
    DictationItem,
    Topic,
    User,
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
    VocabularyTopic,
)
from app.schemas.learning import (
    AudioClip,
    DictationDetail,
    DictationResult,
    DictationSubmit,
    DictationSummary,
    ReviewCard,
    ReviewResult,
    ReviewSession,
    ReviewSubmit,
    TopicPublic,
    VocabularyDetail,
    VocabularySummary,
    WordDiff,
)
from app.services import dictation as dictation_grader
from app.services.srs import GRADES, MAX_SESSION_CARDS, NEW_CARDS_PER_DAY, ReviewState, review

router = APIRouter(tags=["learning"])

PUBLISHED = "published"


def _clips(entry: VocabularyEntry, kind: str) -> list[AudioClip]:
    return [
        AudioClip(
            accent=row.accent,
            url=public_audio_url(row.asset.storage_key),
            duration_ms=row.asset.duration_ms,
        )
        for row in sorted(entry.audio, key=lambda r: r.accent)
        if row.kind == kind
    ]


def _summary(entry: VocabularyEntry) -> VocabularySummary:
    return VocabularySummary(
        id=str(entry.id),
        headword=entry.headword,
        part_of_speech=entry.part_of_speech,
        phonetic=entry.phonetic,
        meaning_vi=entry.meaning_vi,
    )


def _detail(entry: VocabularyEntry) -> VocabularyDetail:
    return VocabularyDetail(
        **_summary(entry).model_dump(),
        meaning_en=entry.meaning_en,
        example=entry.example,
        example_vi=entry.example_vi,
        cefr_level=entry.cefr_level,
        difficulty=entry.difficulty,
        headword_audio=_clips(entry, "headword"),
        example_audio=_clips(entry, "example"),
    )


def _entry_query() -> Select[tuple[VocabularyEntry]]:
    return (
        select(VocabularyEntry)
        .where(VocabularyEntry.status == PUBLISHED)
        .options(selectinload(VocabularyEntry.audio))
    )


# --- topics ---------------------------------------------------------------


@router.get("/topics", response_model=list[TopicPublic])
def list_topics(db: Session = Depends(get_db)) -> list[TopicPublic]:
    topics = db.scalars(
        select(Topic).where(Topic.status == PUBLISHED).order_by(Topic.position, Topic.name)
    ).all()
    return [
        TopicPublic(
            id=str(topic.id),
            slug=topic.slug,
            name=topic.name,
            description=topic.description,
            position=topic.position,
        )
        for topic in topics
    ]


# --- vocabulary -----------------------------------------------------------


@router.get("/vocabulary", response_model=list[VocabularySummary])
def list_vocabulary(
    topic: str | None = Query(default=None, description="topic slug"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[VocabularySummary]:
    query = select(VocabularyEntry).where(VocabularyEntry.status == PUBLISHED)
    if topic is not None:
        query = query.join(VocabularyTopic, VocabularyTopic.entry_id == VocabularyEntry.id).join(
            Topic,
            (Topic.id == VocabularyTopic.topic_id) & (Topic.slug == topic),
        )
    entries = db.scalars(query.order_by(VocabularyEntry.headword).limit(limit).offset(offset)).all()
    return [_summary(entry) for entry in entries]


@router.get("/vocabulary/{entry_id}", response_model=VocabularyDetail)
def get_vocabulary(entry_id: uuid.UUID, db: Session = Depends(get_db)) -> VocabularyDetail:
    entry = db.scalars(
        select(VocabularyEntry)
        .where(VocabularyEntry.id == entry_id, VocabularyEntry.status == PUBLISHED)
        .options(selectinload(VocabularyEntry.audio))
    ).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return _detail(entry)


# --- review session -------------------------------------------------------


@router.get("/vocabulary-review/session", response_model=ReviewSession)
def review_session(
    limit: int = Query(default=MAX_SESSION_CARDS, ge=1, le=MAX_SESSION_CARDS),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewSession:
    """Cards due now, then new ones up to the daily cap.

    Due before new on purpose: reviewing what is about to be forgotten is worth
    more than meeting something for the first time, and if the session is cut
    short it should be the new words that wait.
    """
    now = datetime.now(UTC)

    due_states = db.scalars(
        select(VocabularyReviewState)
        .join(VocabularyEntry, VocabularyEntry.id == VocabularyReviewState.entry_id)
        .where(
            VocabularyReviewState.user_id == current_user.id,
            VocabularyReviewState.due_at <= now,
            VocabularyEntry.status == PUBLISHED,
        )
        .order_by(VocabularyReviewState.due_at)
        .limit(limit)
    ).all()
    due_ids = [state.entry_id for state in due_states]

    # New cards introduced today, counted from when the state row was created.
    started_today = (
        db.scalar(
            select(func.count())
            .select_from(VocabularyReviewState)
            .where(
                VocabularyReviewState.user_id == current_user.id,
                VocabularyReviewState.created_at >= now - timedelta(days=1),
            )
        )
        or 0
    )
    new_budget = max(0, min(NEW_CARDS_PER_DAY - started_today, limit - len(due_ids)))

    new_entries: list[VocabularyEntry] = []
    if new_budget:
        seen = select(VocabularyReviewState.entry_id).where(
            VocabularyReviewState.user_id == current_user.id
        )
        new_entries = list(
            db.scalars(
                _entry_query()
                .where(VocabularyEntry.id.not_in(seen))
                .order_by(VocabularyEntry.difficulty, VocabularyEntry.headword)
                .limit(new_budget)
            ).all()
        )

    due_entries: list[VocabularyEntry] = []
    if due_ids:
        by_id = {
            entry.id: entry
            for entry in db.scalars(_entry_query().where(VocabularyEntry.id.in_(due_ids))).all()
        }
        due_entries = [by_id[entry_id] for entry_id in due_ids if entry_id in by_id]

    cards = [ReviewCard(**_detail(e).model_dump(), is_new=False) for e in due_entries]
    cards += [ReviewCard(**_detail(e).model_dump(), is_new=True) for e in new_entries]

    return ReviewSession(due_count=len(due_entries), new_count=len(new_entries), cards=cards)


@router.post("/vocabulary/{entry_id}/review", response_model=ReviewResult)
def submit_review(
    entry_id: uuid.UUID,
    body: ReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewResult:
    if body.grade not in GRADES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"grade must be one of {list(GRADES)}",
        )

    entry = db.scalars(
        select(VocabularyEntry).where(
            VocabularyEntry.id == entry_id, VocabularyEntry.status == PUBLISHED
        )
    ).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    state = db.get(VocabularyReviewState, (current_user.id, entry_id))
    current = (
        ReviewState(state.ease_factor, state.interval_days, state.repetitions, state.lapses)
        if state
        else ReviewState()
    )
    now = datetime.now(UTC)
    outcome = review(current, body.grade, now)

    if state is None:
        state = VocabularyReviewState(user_id=current_user.id, entry_id=entry_id)
        db.add(state)
    state.ease_factor = outcome.ease_factor
    state.interval_days = outcome.interval_days
    state.repetitions = outcome.repetitions
    state.lapses = outcome.lapses
    state.due_at = outcome.due_at
    state.last_reviewed_at = now

    # The log is written every time, even though the state already holds the same
    # numbers: the state is overwritten on the next review, and without the
    # history there is no way to retune the algorithm and re-evaluate it.
    db.add(
        VocabularyReviewLog(
            user_id=current_user.id,
            entry_id=entry_id,
            grade=body.grade,
            interval_days=outcome.interval_days,
            ease_factor=outcome.ease_factor,
        )
    )
    db.commit()

    return ReviewResult(
        entry_id=str(entry_id),
        grade=body.grade,
        interval_days=outcome.interval_days,
        repetitions=outcome.repetitions,
        lapses=outcome.lapses,
        ease_factor=str(outcome.ease_factor),
        due_at=outcome.due_at.isoformat(),
    )


# --- dictation ------------------------------------------------------------


@router.get("/dictation", response_model=list[DictationSummary])
def list_dictation(
    topic: str | None = Query(default=None, description="topic slug"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DictationSummary]:
    query = select(DictationItem).where(DictationItem.status == PUBLISHED)
    if topic is not None:
        query = query.join(Topic, (Topic.id == DictationItem.topic_id) & (Topic.slug == topic))
    items = db.scalars(
        query.order_by(DictationItem.difficulty, DictationItem.id).limit(limit).offset(offset)
    ).all()
    return [
        DictationSummary(
            id=str(item.id),
            difficulty=item.difficulty,
            topic_id=str(item.topic_id) if item.topic_id else None,
            word_count=len(dictation_grader.normalise(item.transcript)),
        )
        for item in items
    ]


@router.get("/dictation/{item_id}", response_model=DictationDetail)
def get_dictation(item_id: uuid.UUID, db: Session = Depends(get_db)) -> DictationDetail:
    item = db.scalars(
        select(DictationItem)
        .where(DictationItem.id == item_id, DictationItem.status == PUBLISHED)
        .options(selectinload(DictationItem.asset))
    ).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item.asset is None:
        # Unreachable while ck_dictation_item_published_has_audio holds — a
        # published item cannot lack audio. Treated as absent rather than crashing
        # so a constraint that somehow got dropped degrades to a 404, not a 500.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item has no audio")
    # The transcript is deliberately absent: it is the answer, and sending it to
    # the browser before the learner types would make the exercise pointless.
    return DictationDetail(
        id=str(item.id),
        difficulty=item.difficulty,
        topic_id=str(item.topic_id) if item.topic_id else None,
        word_count=len(dictation_grader.normalise(item.transcript)),
        audio_url=public_audio_url(item.asset.storage_key),
        duration_ms=item.asset.duration_ms,
    )


@router.post("/dictation/{item_id}/attempts", response_model=DictationResult)
def submit_dictation(
    item_id: uuid.UUID,
    body: DictationSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DictationResult:
    item = db.scalars(
        select(DictationItem).where(DictationItem.id == item_id, DictationItem.status == PUBLISHED)
    ).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Graded against `transcript`, never against `audio_asset.source_text`.
    result = dictation_grader.grade(item.transcript, body.submitted_text)

    attempt = DictationAttempt(
        user_id=current_user.id,
        item_id=item.id,
        # Stored exactly as typed: normalisation belongs to the grader, and the
        # grader will change. Keeping only the normalised form would make it
        # impossible to re-grade an old attempt under new rules.
        submitted_text=body.submitted_text,
        accuracy=result.accuracy,
        word_diff=result.as_json(),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return DictationResult(
        attempt_id=str(attempt.id),
        accuracy=str(result.accuracy),
        matched=result.matched,
        expected=result.expected,
        transcript=item.transcript,
        diff=[WordDiff(op=item_.op, word=item_.word) for item_ in result.diff],
    )
