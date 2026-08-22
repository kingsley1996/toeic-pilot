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
    DictationSection,
    DictationStory,
    DictationTopic,
    Topic,
    User,
    VocabularyCollection,
    VocabularyCollectionItem,
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
    VocabularyTopic,
    VocabularyTopicSession,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.schemas.learning import (
    AudioClip,
    DictationDetail,
    DictationResult,
    DictationSectionDetail,
    DictationSectionPublic,
    DictationStoryDetail,
    DictationStorySummary,
    DictationSubmit,
    DictationSummary,
    DictationTopicDetail,
    DictationTopicPublic,
    RecallCheck,
    RecallCheckSubmit,
    RecallResult,
    RecallSubmit,
    ReviewCard,
    ReviewResult,
    ReviewSession,
    ReviewSubmit,
    StoryItem,
    StoryProgress,
    TopicPublic,
    TopicSession,
    TopicSessionSubmit,
    TopicSessionSummary,
    VocabularyCollectionDetail,
    VocabularyCollectionItemPublic,
    VocabularyCollectionPublic,
    VocabularyDetail,
    VocabularyItemDetail,
    VocabularyMastery,
    VocabularyProgress,
    VocabularySummary,
    WordDiff,
)
from app.services import dictation as dictation_grader
from app.services import progression
from app.services.profile import ensure_profile
from app.services.recall import VERDICT_UNKNOWN, grade_for, judge
from app.services.srs import (
    GRADES,
    MASTERY_LEARNING,
    MASTERY_LEVELS,
    MASTERY_MASTERED,
    MASTERY_NEW,
    MAX_SESSION_CARDS,
    NEW_CARDS_PER_DAY,
    ReviewOutcome,
    ReviewState,
    mastery,
    review,
)

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


def _published_entry_counts(db: Session) -> dict[uuid.UUID, int]:
    """topic_id -> số từ ĐÃ XUẤT BẢN trong topic đó.

    Dùng chung cho danh sách topic phẳng lẫn cây collection → item → topic:
    card của học viên hứa hẹn một con số, và con số đó chỉ được đếm trên thứ họ
    bấm vào mà thấy được. Đếm cả nháp sẽ treo lên card một lời hứa trang bên
    trong không giữ được.
    """
    return {
        topic_id: count
        for topic_id, count in db.execute(
            select(VocabularyTopic.topic_id, func.count(VocabularyTopic.entry_id))
            .join(VocabularyEntry, VocabularyEntry.id == VocabularyTopic.entry_id)
            .where(VocabularyEntry.status == PUBLISHED)
            .group_by(VocabularyTopic.topic_id)
        ).all()
    }


def _visible_topic_counts(db: Session) -> dict[uuid.UUID, int]:
    """item_id -> số topic published nằm trong cuốn sách đó (trục topic)."""
    return {
        item_id: count
        for item_id, count in db.execute(
            select(Topic.collection_item_id, func.count(Topic.id))
            .where(
                Topic.status == PUBLISHED,
                Topic.collection_item_id.is_not(None),
            )
            .group_by(Topic.collection_item_id)
        ).all()
    }


def _topic_public(topic: Topic, entry_count: int) -> TopicPublic:
    return TopicPublic(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        position=topic.position,
        entry_count=entry_count,
        collection_item_id=str(topic.collection_item_id) if topic.collection_item_id else None,
    )


@router.get("/topics", response_model=list[TopicPublic])
def list_topics(db: Session = Depends(get_db)) -> list[TopicPublic]:
    # Danh sách topic không lọc theo tầng collection/item: đây là trục phẳng
    # "toàn bộ" + nguồn cho phần "chủ đề chưa xếp" trên trang từ vựng.
    topics = db.scalars(
        select(Topic).where(Topic.status == PUBLISHED).order_by(Topic.position, Topic.name)
    ).all()
    counts = _published_entry_counts(db)
    return [_topic_public(topic, counts.get(topic.id, 0)) for topic in topics]


# --- vocabulary tree (collection -> collection_item -> topic) --------------
#
# Lọc `published` Ở TỪNG TẦNG — học viên không được thấy item draft dưới
# collection published, và ngược lại (cùng khuôn cây dictation:
# tests/test_dictation_tree.py ghim đủ bốn hướng).


@router.get("/vocabulary-collections", response_model=list[VocabularyCollectionPublic])
def list_vocabulary_collections(db: Session = Depends(get_db)) -> list[VocabularyCollectionPublic]:
    collections = db.scalars(
        select(VocabularyCollection)
        .where(VocabularyCollection.status == PUBLISHED)
        .order_by(VocabularyCollection.position, VocabularyCollection.name)
        .options(selectinload(VocabularyCollection.items))
    ).all()
    # Số chủ đề HỌC VIÊN ĐƯỢC THẤY: chỉ topic published nằm trong item published
    # của chính collection đó. Đếm mọi topic (kể cả dưới item draft) sẽ hứa một
    # trang mà nút mở ra không mở được.
    topics_per_item = _visible_topic_counts(db)
    out: list[VocabularyCollectionPublic] = []
    for collection in collections:
        item_ids = [item.id for item in collection.items if item.status == PUBLISHED]
        out.append(
            VocabularyCollectionPublic(
                id=str(collection.id),
                slug=collection.slug,
                name=collection.name,
                description=collection.description,
                position=collection.position,
                topic_count=sum(topics_per_item.get(item_id, 0) for item_id in item_ids),
            )
        )
    return out


def _published_collection(db: Session, ref: str) -> VocabularyCollection:
    """Học viên đi vào bằng slug ("toeic-vocabulary"); ID cũng mở được.

    Slug là URL ổn định và dễ đọc — đúng tiền lệ route topic của chính màn từ
    vựng — nên endpoint nhận cả hai thay vì bắt UUID và 422 trước slug.
    """
    collection: VocabularyCollection | None
    try:
        collection = db.get(VocabularyCollection, uuid.UUID(ref))
    except ValueError:
        collection = db.scalar(select(VocabularyCollection).where(VocabularyCollection.slug == ref))
    if collection is None or collection.status != PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return collection


@router.get("/vocabulary-collections/{collection_ref}", response_model=VocabularyCollectionDetail)
def get_vocabulary_collection(
    collection_ref: str, db: Session = Depends(get_db)
) -> VocabularyCollectionDetail:
    collection = _published_collection(db, collection_ref)
    items = db.scalars(
        select(VocabularyCollectionItem)
        .where(
            VocabularyCollectionItem.collection_id == collection.id,
            VocabularyCollectionItem.status == PUBLISHED,
        )
        .order_by(VocabularyCollectionItem.position, VocabularyCollectionItem.name)
    ).all()
    topics_per_item = _visible_topic_counts(db)
    return VocabularyCollectionDetail(
        id=str(collection.id),
        slug=collection.slug,
        name=collection.name,
        description=collection.description,
        position=collection.position,
        items=[
            VocabularyCollectionItemPublic(
                id=str(item.id),
                name=item.name,
                description=item.description,
                position=item.position,
                topic_count=topics_per_item.get(item.id, 0),
            )
            for item in items
        ],
    )


@router.get("/vocabulary-collection-items/{item_id}", response_model=VocabularyItemDetail)
def get_vocabulary_collection_item(
    item_id: uuid.UUID, db: Session = Depends(get_db)
) -> VocabularyItemDetail:
    item = db.get(VocabularyCollectionItem, item_id)
    # Item draft => 404 DÙ collection cha đã published — không lộ qua cửa sau.
    if item is None or item.status != PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found"
        )
    collection = db.get(VocabularyCollection, item.collection_id)
    if collection is None or collection.status != PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found"
        )
    topics = db.scalars(
        select(Topic)
        .where(Topic.collection_item_id == item_id, Topic.status == PUBLISHED)
        .order_by(Topic.position, Topic.name)
    ).all()
    counts = _published_entry_counts(db)
    return VocabularyItemDetail(
        id=str(item.id),
        name=item.name,
        description=item.description,
        position=item.position,
        topics=[_topic_public(topic, counts.get(topic.id, 0)) for topic in topics],
        collection_id=str(collection.id),
        collection_name=collection.name,
    )


# --- vocabulary -----------------------------------------------------------


@router.get("/vocabulary", response_model=Page[VocabularySummary])
def list_vocabulary(
    topic: str | None = Query(default=None, description="topic slug"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Page[VocabularySummary]:
    query = select(VocabularyEntry).where(VocabularyEntry.status == PUBLISHED)
    if topic is not None:
        query = query.join(VocabularyTopic, VocabularyTopic.entry_id == VocabularyEntry.id).join(
            Topic,
            (Topic.id == VocabularyTopic.topic_id) & (Topic.slug == topic),
        )
    # `id` làm khoá phụ, không phải trang trí: `headword` KHÔNG duy nhất — khoá
    # duy nhất là cặp (headword, part_of_speech), nên "invoice" danh từ và
    # "invoice" động từ có thứ tự tương đối *không xác định* giữa hai truy vấn.
    # Với LIMIT/OFFSET, điều đó nghĩa là một từ hiện ở cả trang 1 lẫn trang 2 còn
    # một từ khác không hiện ở đâu cả — và không có lỗi nào được ném ra.
    entries = db.scalars(
        query.order_by(VocabularyEntry.headword, VocabularyEntry.id).limit(limit).offset(offset)
    ).all()
    return page_of([_summary(entry) for entry in entries], count_rows(db, query), limit, offset)


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


# --- vocabulary progress --------------------------------------------------

# `/vocabulary-progress`, không phải `/vocabulary/progress`: route
# `/vocabulary/{entry_id}` khai `entry_id: uuid.UUID` nên sẽ bắt "progress"
# trước và trả 422. Cùng cái bẫy đã gặp ở `/dictation/topics`.


@router.get("/vocabulary-progress", response_model=VocabularyProgress)
def vocabulary_progress(
    topic: str | None = Query(default=None, description="topic slug"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VocabularyProgress:
    """Trạng thái thuộc/chưa thuộc của học viên trên tập từ đang xem.

    Lọc theo cùng tiêu chí `published` + topic như `GET /vocabulary`, nếu không
    mẫu số sẽ đếm cả những từ mà danh sách không hề hiện ra, và "đã thuộc 12/40"
    sẽ không bao giờ chạm tới 40.
    """
    query = select(VocabularyEntry.id).where(VocabularyEntry.status == PUBLISHED)
    if topic is not None:
        query = query.join(VocabularyTopic, VocabularyTopic.entry_id == VocabularyEntry.id).join(
            Topic,
            (Topic.id == VocabularyTopic.topic_id) & (Topic.slug == topic),
        )
    entry_ids = list(db.scalars(query).all())

    states: dict[uuid.UUID, VocabularyReviewState] = {}
    if entry_ids:
        states = {
            state.entry_id: state
            for state in db.scalars(
                select(VocabularyReviewState).where(
                    VocabularyReviewState.user_id == current_user.id,
                    VocabularyReviewState.entry_id.in_(entry_ids),
                )
            ).all()
        }

    # "Đến hạn chưa" phải so sánh TRONG SQL, không phải trong Python: cột khai
    # `DateTime(timezone=True)` nên Postgres trả về datetime có tz, còn SQLite
    # (bộ test) trả về naive, và so hai loại đó với nhau thì TypeError. Cùng
    # khuôn với `_completed_items` của dictation: một tập id lấy thẳng từ SQL.
    now = datetime.now(UTC)
    due_ids: set[uuid.UUID] = set()
    if entry_ids:
        due_ids = set(
            db.scalars(
                select(VocabularyReviewState.entry_id).where(
                    VocabularyReviewState.user_id == current_user.id,
                    VocabularyReviewState.entry_id.in_(entry_ids),
                    VocabularyReviewState.due_at <= now,
                )
            ).all()
        )

    counts = {level: 0 for level in MASTERY_LEVELS}
    entries: list[VocabularyMastery] = []

    for entry_id in entry_ids:
        state = states.get(entry_id)
        level = mastery(
            ReviewState(
                ease_factor=state.ease_factor,
                interval_days=state.interval_days,
                repetitions=state.repetitions,
                lapses=state.lapses,
            )
            if state is not None
            else None
        )
        counts[level] += 1
        # Một từ chưa từng ôn thì chưa "đến hạn" — nó chỉ đang chờ được học lần
        # đầu, và trộn hai thứ đó sẽ làm con số đến hạn nhảy vọt ngay ngày đầu
        # tiên của một chủ đề mới. `due_ids` chỉ chứa từ đã có state nên điều
        # kiện này tự đúng.
        entries.append(
            VocabularyMastery(entry_id=str(entry_id), mastery=level, is_due=entry_id in due_ids)
        )

    return VocabularyProgress(
        total=len(entry_ids),
        new=counts[MASTERY_NEW],
        learning=counts[MASTERY_LEARNING],
        mastered=counts[MASTERY_MASTERED],
        due=len(due_ids),
        entries=entries,
    )


# --- lưu chỗ học theo chủ đề -------------------------------------------------

# Đường dẫn gạch nối, không lồng vào `/vocabulary/...` — cùng cái bẫy UUID đã
# ghi ở `/vocabulary-progress`: `/vocabulary/{entry_id}` sẽ bắt "topic-sessions"
# trước và trả 422.


def _topic_session_public(session: VocabularyTopicSession) -> TopicSession:
    entry_ids = [uuid.UUID(raw) for raw in session.entry_ids]
    done = session.position >= len(entry_ids)
    return TopicSession(entry_ids=entry_ids, position=session.position, done=done)


@router.get("/vocabulary-topic-sessions", response_model=list[TopicSessionSummary])
def list_topic_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TopicSessionSummary]:
    """Các ván học của học viên này, mới động vào trước.

    Mảng trần chứ không phải `Page[T]`: số ván của MỘT học viên không thể vượt
    quá số chủ đề đã xuất bản (hiện là 7), vì khoá chính là `(user, topic)`.
    Đây là nhóm (A) của `schemas/common.py` — bị chặn trên bởi chính miền dữ
    liệu. Bọc envelope ở đây bắt frontend xử lý một trường hợp không xảy ra
    được. Xét lại nếu số chủ đề lên tới hàng trăm.

    Lọc `published` ở CẢ chủ đề: một chủ đề bị rút về nháp mà vẫn hiện trong
    "học tiếp" sẽ dẫn học viên tới một trang 404.
    """
    rows = db.execute(
        select(VocabularyTopicSession, Topic, VocabularyCollectionItem)
        .join(Topic, Topic.id == VocabularyTopicSession.topic_id)
        # OUTER: `topic.collection_item_id` nullable — chủ đề chưa xếp vào cuốn
        # sách nào vẫn có ván học hợp lệ, và inner join sẽ nuốt mất chúng.
        .outerjoin(
            VocabularyCollectionItem,
            VocabularyCollectionItem.id == Topic.collection_item_id,
        )
        .where(
            VocabularyTopicSession.user_id == current_user.id,
            Topic.status == PUBLISHED,
        )
        .order_by(VocabularyTopicSession.updated_at.desc(), VocabularyTopicSession.topic_id)
    ).all()

    return [
        TopicSessionSummary(
            topic_id=topic.id,
            topic_slug=topic.slug,
            topic_name=topic.name,
            collection_item_id=item.id if item else None,
            collection_item_name=item.name if item else None,
            total=len(session.entry_ids),
            position=session.position,
            done=session.position >= len(session.entry_ids),
        )
        for session, topic, item in rows
    ]


@router.get("/vocabulary-topic-sessions/{topic_id}", response_model=TopicSession)
def get_topic_session(
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TopicSession:
    """Bàn cờ đã lưu của học viên trong chủ đề này; 404 nếu chưa có.

    404 cho cả topic không tồn tại và "chưa từng lưu" — từ phía client hai thứ
    giống nhau: bắt đầu xáo một bàn mới. Lọc `published`: client không nhìn thấy
    nháp, thì phiên học gắn với nháp cũng không có lý do tồn tại.
    """
    topic = db.scalars(select(Topic).where(Topic.id == topic_id, Topic.status == PUBLISHED)).first()
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    session = db.get(VocabularyTopicSession, (current_user.id, topic_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved session")
    return _topic_session_public(session)


@router.put("/vocabulary-topic-sessions/{topic_id}", response_model=TopicSession)
def put_topic_session(
    topic_id: uuid.UUID,
    body: TopicSessionSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TopicSession:
    """Ghi lại bàn cờ sau mỗi lần chấm một từ — upsert theo (user, topic)."""
    topic = db.scalars(select(Topic).where(Topic.id == topic_id, Topic.status == PUBLISHED)).first()
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    session = db.get(VocabularyTopicSession, (current_user.id, topic_id))
    if session is None:
        session = VocabularyTopicSession(user_id=current_user.id, topic_id=topic_id)
        db.add(session)
    session.entry_ids = [str(entry_id) for entry_id in body.entry_ids]
    session.position = body.position
    db.commit()
    return _topic_session_public(session)


# --- ghi một lượt ôn tập ---------------------------------------------------

# Dùng chung cho hai lối vào: thẻ lật (`/review`, người học tự chấm) và gõ lại
# (`/recall`, máy chấm). Tách ra vì phần ghi state + log là thứ PHẢI giống hệt
# nhau ở cả hai — hai bản sao thì bản nào quên ghi log sẽ làm mất lịch sử, và
# không có gì báo cho biết ngoài việc sau này không hiệu chỉnh lại được thuật
# toán nữa.


def _published_entry(db: Session, entry_id: uuid.UUID) -> VocabularyEntry:
    entry = db.scalars(
        select(VocabularyEntry).where(
            VocabularyEntry.id == entry_id, VocabularyEntry.status == PUBLISHED
        )
    ).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


def _apply_review(
    db: Session, user_id: uuid.UUID, entry_id: uuid.UUID, grade: int, timezone: str
) -> ReviewOutcome:
    state = db.get(VocabularyReviewState, (user_id, entry_id))
    current = (
        ReviewState(state.ease_factor, state.interval_days, state.repetitions, state.lapses)
        if state
        else ReviewState()
    )
    now = datetime.now(UTC)
    outcome = review(current, grade, now)

    if state is None:
        state = VocabularyReviewState(user_id=user_id, entry_id=entry_id)
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
    log = VocabularyReviewLog(
        user_id=user_id,
        entry_id=entry_id,
        grade=grade,
        interval_days=outcome.interval_days,
        ease_factor=outcome.ease_factor,
    )
    db.add(log)

    # XP đi cùng giao dịch của lượt ôn, không phải sau nó. Trao XP cho một lượt
    # ôn bị rollback là sổ cái nói về việc chưa từng xảy ra; và ngược lại, một
    # lỗi ở nhánh XP không được phép làm mất lượt ôn — nên nó nằm trong `try`.
    #
    # `flush` để `log.id` tồn tại: nó là `source_id`, và chính nó làm
    # `uq_xp_event_source` chặn được việc trao hai lần cho cùng một lượt ôn.
    db.flush()
    try:
        progression.award(
            db,
            user_id=user_id,
            source_type="vocabulary_review",
            source_id=log.id,
            amount=progression.xp_for(db, "vocabulary_review"),
            timezone=timezone,
        )
    except Exception:  # pragma: no cover - lưới an toàn, xem chú thích trên
        pass

    db.commit()
    return outcome


def _review_result(entry_id: uuid.UUID, grade: int, outcome: ReviewOutcome) -> ReviewResult:
    return ReviewResult(
        entry_id=str(entry_id),
        grade=grade,
        interval_days=outcome.interval_days,
        repetitions=outcome.repetitions,
        lapses=outcome.lapses,
        ease_factor=str(outcome.ease_factor),
        due_at=outcome.due_at.isoformat(),
    )


# --- review session -------------------------------------------------------


@router.get("/vocabulary-review/session", response_model=ReviewSession)
def review_session(
    limit: int = Query(default=MAX_SESSION_CARDS, ge=1, le=MAX_SESSION_CARDS),
    include_new: bool = Query(
        default=True,
        description="False = chỉ những từ học viên đã gặp, không kèm từ mới",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewSession:
    """Cards due now, then new ones up to the daily cap.

    Due before new on purpose: reviewing what is about to be forgotten is worth
    more than meeting something for the first time, and if the session is cut
    short it should be the new words that wait.

    `include_new=False` phục vụ những chế độ đòi học viên TỰ VIẾT RA từ. Bắt gõ
    lại một từ chưa từng thấy thì không có câu trả lời nào đúng được: lối thoát
    duy nhất là đoán bừa rồi ăn điểm 0. Với người mới thì cả 20/20 thẻ đều rơi
    vào cảnh đó — tôi phát hiện khi tự đóng vai học viên mới, không phải khi
    đọc code.
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
    new_budget = (
        max(0, min(NEW_CARDS_PER_DAY - started_today, limit - len(due_ids))) if include_new else 0
    )

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

    entry = _published_entry(db, entry_id)
    outcome = _apply_review(
        db, current_user.id, entry.id, body.grade, ensure_profile(db, current_user).timezone
    )
    return _review_result(entry.id, body.grade, outcome)


@router.post("/vocabulary/{entry_id}/recall", response_model=RecallResult)
def submit_recall(
    entry_id: uuid.UUID,
    body: RecallSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecallResult:
    """Gõ lại từ: máy chấm, rồi điểm SM-2 được suy ra từ kết quả.

    Đây là điểm khác biệt duy nhất so với `/review`, và là lý do endpoint này
    tồn tại: thẻ lật hỏi "bạn có nhớ không" rồi ghi thẳng câu trả lời, nên
    người học có thể lật thẻ, nghĩ "à đúng rồi tôi biết mà", bấm Dễ và không
    học được gì. Ở đây phải viết ra được trước đã.
    """
    entry = _published_entry(db, entry_id)
    judgement = judge(body.typed, entry.headword)
    verdict = VERDICT_UNKNOWN if body.give_up else judgement.verdict
    grade = grade_for(verdict, easy=body.easy)
    outcome = _apply_review(
        db, current_user.id, entry.id, grade, ensure_profile(db, current_user).timezone
    )
    return RecallResult(
        **_review_result(entry.id, grade, outcome).model_dump(),
        verdict=verdict,
        expected=judgement.expected,
        typed=judgement.typed,
    )


@router.post("/vocabulary/{entry_id}/recall-check", response_model=RecallCheck)
def check_recall(
    entry_id: uuid.UUID,
    body: RecallCheckSubmit,
    db: Session = Depends(get_db),
) -> RecallCheck:
    """Gõ lại từ: máy chấm đúng/sai, nhưng KHÔNG ghi lượt ôn.

    Phục vụ luồng học theo chủ đề với năm nút chấm chuẩn: máy chỉ làm phần nó
    giỏi — kiểm tra gõ đúng không — rồi trả câu trả lời thật cho học viên nhìn.
    Mức độ nhớ sau đó do học viên tự chấm ở năm nút, ghi qua `/review`. Ghi
    điểm ở đây sẽ tính từ này hai lần trong cùng một lượt.

    Không đòi đăng nhập: endpoint này KHÔNG ghi gì và từ đã xuất bản vốn đã công
    khai ở `GET /vocabulary/{id}`. Ghi điểm mới là thứ cần tài khoản.
    """
    entry = _published_entry(db, entry_id)
    judgement = judge(body.typed, entry.headword)
    verdict = VERDICT_UNKNOWN if body.give_up else judgement.verdict
    return RecallCheck(
        verdict=verdict,
        expected=judgement.expected,
        typed=judgement.typed,
    )


# --- dictation ------------------------------------------------------------


@router.get("/dictation", response_model=Page[DictationSummary])
def list_dictation(
    topic: str | None = Query(default=None, description="topic slug"),
    standalone: bool = Query(
        default=False,
        description="only sentences that belong to no story",
    ),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Page[DictationSummary]:
    """Danh sách phẳng các câu đã xuất bản.

    `standalone=true` lọc lấy những câu chưa thuộc story nào. Có tham số này vì
    cây topic→section→story ra đời sau: nếu luồng duyệt chỉ đi theo cây, mọi câu
    có từ trước sẽ biến mất khỏi tầm mắt học viên mà không có gì báo. Mặc định
    giữ nguyên hành vi cũ để không phá những chỗ đang gọi.
    """
    query = select(DictationItem).where(DictationItem.status == PUBLISHED)
    if standalone:
        query = query.where(DictationItem.story_id.is_(None))
    if topic is not None:
        query = query.join(Topic, (Topic.id == DictationItem.topic_id) & (Topic.slug == topic))
    items = db.scalars(
        query.order_by(DictationItem.difficulty, DictationItem.id).limit(limit).offset(offset)
    ).all()
    return page_of(
        [
            DictationSummary(
                id=str(item.id),
                difficulty=item.difficulty,
                topic_id=str(item.topic_id) if item.topic_id else None,
                word_count=len(dictation_grader.normalise(item.transcript)),
            )
            for item in items
        ],
        count_rows(db, query),
        limit,
        offset,
    )


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
    # The transcript ships with the item so the client can grade without a round
    # trip. See DictationDetail.transcript for what that costs and why it is
    # acceptable here; the server still re-grades every submitted attempt, so the
    # stored score never depends on anything the browser claims.
    return DictationDetail(
        id=str(item.id),
        difficulty=item.difficulty,
        topic_id=str(item.topic_id) if item.topic_id else None,
        word_count=len(dictation_grader.normalise(item.transcript)),
        audio_url=public_audio_url(item.asset.storage_key),
        duration_ms=item.asset.duration_ms,
        transcript=item.transcript,
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
        is_complete=result.is_complete,
        word_diff=result.as_json(),
    )
    db.add(attempt)

    # Chỉ trao XP cho câu ĐÚNG TRỌN. `accuracy` không dùng được làm cổng ở đây:
    # gõ cả câu rồi gõ thêm vẫn cho 100%, và gõ hai lần cũng vậy — cùng lý do
    # tiến độ dictation đếm `is_complete` chứ không đếm điểm.
    db.flush()
    if result.is_complete:
        try:
            progression.award(
                db,
                user_id=current_user.id,
                source_type="dictation_complete",
                source_id=attempt.id,
                amount=progression.xp_for(db, "dictation_complete"),
                timezone=ensure_profile(db, current_user).timezone,
            )
        except Exception:  # pragma: no cover - XP không được làm hỏng bài nộp
            pass

    db.commit()
    db.refresh(attempt)

    return DictationResult(
        attempt_id=str(attempt.id),
        accuracy=str(result.accuracy),
        matched=result.matched,
        expected=result.expected,
        transcript=item.transcript,
        diff=[WordDiff(op=item_.op, word=item_.word) for item_ in result.diff],
        is_complete=result.is_complete,
    )


# --- cây dictation ---------------------------------------------------------
#
# Đường dẫn dùng dấu gạch nối (`/dictation-topics`) chứ không lồng vào
# (`/dictation/topics`), theo đúng tiền lệ `/vocabulary-review/session` đã có.
# Không phải để cho đẹp: `/dictation/{item_id}` khai `item_id: uuid.UUID`, nên
# `/dictation/topics` sẽ bị route đó bắt trước và trả 422 khi cố parse "topics"
# thành UUID. Đặt route tĩnh trước route động cũng chữa được, nhưng khi đó thứ
# tự khai báo trở thành một thứ ngầm mà người sắp xếp lại file sẽ phá.
#
# Bốn tầng, và MỖI tầng đều phải lọc `status = 'published'`. Quên một tầng là đủ
# để nội dung nháp lọt ra: một story nháp nằm dưới section đã publish vẫn hiện
# nếu chỉ lọc ở section. Kiểu lỗi này im lặng — không ai báo cáo được vì nội dung
# trông hoàn toàn bình thường (ADR-001 §A5.3).


def _completed_items(db: Session, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Những câu học viên đã gõ đúng ít nhất một lần.

    `DISTINCT` vì làm lại một câu nhiều lần vẫn là một câu. Xong rồi thì xong —
    làm lại sau đó không gỡ mất trạng thái đã hoàn thành, vì việc họ từng nghe ra
    được là chuyện đã xảy ra.
    """
    if not item_ids:
        return set()
    rows = db.scalars(
        select(DictationAttempt.item_id)
        .where(
            DictationAttempt.user_id == user_id,
            DictationAttempt.item_id.in_(item_ids),
            DictationAttempt.is_complete.is_(True),
        )
        .distinct()
    ).all()
    return set(rows)


@router.get("/dictation-topics", response_model=list[DictationTopicPublic])
def list_dictation_topics(db: Session = Depends(get_db)) -> list[DictationTopicPublic]:
    published_sections = (
        select(func.count(DictationSection.id))
        .where(
            DictationSection.topic_id == DictationTopic.id,
            DictationSection.status == PUBLISHED,
        )
        .scalar_subquery()
    )
    rows = db.execute(
        select(DictationTopic, published_sections.label("section_count"))
        .where(DictationTopic.status == PUBLISHED)
        .order_by(DictationTopic.position, DictationTopic.name)
    ).all()
    return [
        DictationTopicPublic(
            id=str(topic.id),
            slug=topic.slug,
            name=topic.name,
            description=topic.description,
            section_count=count,
        )
        for topic, count in rows
    ]


@router.get("/dictation-topics/{topic_id}", response_model=DictationTopicDetail)
def get_dictation_topic(topic_id: uuid.UUID, db: Session = Depends(get_db)) -> DictationTopicDetail:
    topic = db.scalars(
        select(DictationTopic).where(
            DictationTopic.id == topic_id, DictationTopic.status == PUBLISHED
        )
    ).first()
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    published_stories = (
        select(func.count(DictationStory.id))
        .where(
            DictationStory.section_id == DictationSection.id,
            DictationStory.status == PUBLISHED,
        )
        .scalar_subquery()
    )
    rows = db.execute(
        select(DictationSection, published_stories.label("story_count"))
        .where(
            DictationSection.topic_id == topic.id,
            DictationSection.status == PUBLISHED,
        )
        .order_by(DictationSection.position, DictationSection.name)
    ).all()

    return DictationTopicDetail(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        section_count=len(rows),
        sections=[
            DictationSectionPublic(
                id=str(section.id),
                name=section.name,
                description=section.description,
                story_count=count,
            )
            for section, count in rows
        ],
    )


@router.get("/dictation-sections/{section_id}", response_model=DictationSectionDetail)
def get_dictation_section(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DictationSectionDetail:
    section = db.scalars(
        select(DictationSection)
        .join(DictationTopic, DictationTopic.id == DictationSection.topic_id)
        .where(
            DictationSection.id == section_id,
            DictationSection.status == PUBLISHED,
            # Topic nháp thì cả nhánh dưới nó chưa được coi là đã xuất bản.
            DictationTopic.status == PUBLISHED,
        )
        .options(selectinload(DictationSection.topic))
    ).first()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    stories = db.scalars(
        select(DictationStory)
        .where(DictationStory.section_id == section.id, DictationStory.status == PUBLISHED)
        .order_by(DictationStory.position, DictationStory.title)
        .options(selectinload(DictationStory.items))
    ).all()

    summaries: list[DictationStorySummary] = []
    for story in stories:
        item_ids = [item.id for item in story.items if item.status == PUBLISHED]
        done = _completed_items(db, user.id, item_ids)
        summaries.append(
            DictationStorySummary(
                id=str(story.id),
                title=story.title,
                description=story.description,
                difficulty=story.difficulty,
                progress=StoryProgress(total_items=len(item_ids), completed_items=len(done)),
            )
        )

    return DictationSectionDetail(
        id=str(section.id),
        name=section.name,
        description=section.description,
        story_count=len(summaries),
        topic_id=str(section.topic_id),
        topic_name=section.topic.name,
        stories=summaries,
    )


@router.get("/dictation-stories/{story_id}", response_model=DictationStoryDetail)
def get_dictation_story(
    story_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DictationStoryDetail:
    story = db.scalars(
        select(DictationStory)
        .join(DictationSection, DictationSection.id == DictationStory.section_id)
        .join(DictationTopic, DictationTopic.id == DictationSection.topic_id)
        .where(
            DictationStory.id == story_id,
            DictationStory.status == PUBLISHED,
            DictationSection.status == PUBLISHED,
            DictationTopic.status == PUBLISHED,
        )
        .options(selectinload(DictationStory.section).selectinload(DictationSection.topic))
    ).first()
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    items = db.scalars(
        select(DictationItem)
        .where(
            DictationItem.story_id == story.id,
            DictationItem.status == PUBLISHED,
        )
        .order_by(DictationItem.position)
        .options(selectinload(DictationItem.asset))
    ).all()

    item_ids = [item.id for item in items]
    done = _completed_items(db, user.id, item_ids)

    return DictationStoryDetail(
        id=str(story.id),
        title=story.title,
        description=story.description,
        difficulty=story.difficulty,
        section_id=str(story.section_id),
        section_name=story.section.name,
        topic_id=str(story.section.topic_id),
        topic_name=story.section.topic.name,
        items=[
            StoryItem(
                id=str(item.id),
                # `position` là NOT NULL bất cứ khi nào story_id có giá trị —
                # CHECK ck_dictation_item_story_position bảo đảm điều đó.
                position=item.position or 0,
                word_count=len(dictation_grader.normalise(item.transcript)),
                audio_url=public_audio_url(item.asset.storage_key) if item.asset else "",
                duration_ms=item.asset.duration_ms if item.asset else 0,
                transcript=item.transcript,
                completed=item.id in done,
            )
            for item in items
        ],
        progress=StoryProgress(total_items=len(items), completed_items=len(done)),
    )
