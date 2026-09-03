"""Endpoint TỪ VỰNG cho người học: chủ đề, cuốn, ôn tập SM-2, gõ lại.

Mọi lượt đọc ở đây lọc `status == 'published'`. Cái lọc ấy là thứ duy nhất đứng
giữa một bản nháp viết dở và màn hình người học, và quên nó thì hỏng im lặng —
nội dung cứ thế hiện ra. Mỗi endpoint có một test khẳng định nội dung nháp vẫn
vô hình (ADR-001 A5.3).

Tách khỏi dictation vì hai miền đổi vì lý do khác nhau, không phải vì tệp cũ
dài: `REFACTOR-LONG-FILES.md` §0.
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
    RecallCheck,
    RecallCheckSubmit,
    RecallResult,
    RecallSubmit,
    ReviewCard,
    ReviewDueCount,
    ReviewResult,
    ReviewSession,
    ReviewSubmit,
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
)
from app.services import progression, ruby
from app.services.pet_state import reward_study
from app.services.profile import ensure_profile
from app.services.recall import VERDICT_UNKNOWN, grade_for, judge
from app.services.srs import (
    GRADES,
    MASTERED_INTERVAL_DAYS,
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

    _pay_ruby_for_a_mastered_topic(db, user_id, entry_id, outcome)

    db.commit()
    return outcome


def _pay_ruby_for_a_mastered_topic(
    db: Session, user_id: uuid.UUID, entry_id: uuid.UUID, outcome: ReviewOutcome
) -> None:
    """Ruby cho việc THUỘC TRỌN một chủ đề, không cho từng lượt ôn (ADR-011 §1).

    Cổng đầu tiên là chính lượt vừa rồi: nếu từ này vẫn chưa "thuộc" thì chủ đề
    chứa nó chắc chắn chưa xong, và cả nhánh này khỏi chạy. Đó là thứ giữ cho ba
    trăm lượt ôn mỗi ngày không kéo theo ba trăm truy vấn đếm.

    "Thuộc" ở đây là ĐÚNG định nghĩa `srs.mastery` dùng — `interval_days` đã tới
    ngưỡng — chứ không phải "vừa bấm nút grade 6". Hai định nghĩa sẽ lệch nhau
    ngay lần đầu ai đó chỉnh `MASTERED_INTERVAL_DAYS`, và cái lệch sẽ im lặng.

    Một từ thuộc nhiều chủ đề (`vocabulary_topic` là many-to-many), nên một lượt
    ôn có thể đóng nhiều chủ đề cùng lúc; `source_id` là chủ đề nên mỗi cái trả
    đúng một lần, vĩnh viễn.
    """
    if outcome.interval_days < MASTERED_INTERVAL_DAYS:
        return
    try:
        # `flush` để state vừa ghi nằm trong truy vấn đếm bên dưới: session chạy
        # `autoflush=False`, nên không có nó thì từ CUỐI CÙNG của một chủ đề
        # không bao giờ được tính, và chủ đề đó không bao giờ trả ruby.
        db.flush()
        topic_ids = list(
            db.scalars(select(VocabularyTopic.topic_id).where(VocabularyTopic.entry_id == entry_id))
        )
        for topic_id in topic_ids:
            member_ids = list(
                db.scalars(
                    select(VocabularyTopic.entry_id)
                    .join(VocabularyEntry, VocabularyEntry.id == VocabularyTopic.entry_id)
                    .where(
                        VocabularyTopic.topic_id == topic_id,
                        VocabularyEntry.status == PUBLISHED,
                    )
                )
            )
            if not member_ids:
                continue
            mastered = db.scalar(
                select(func.count(VocabularyReviewState.entry_id)).where(
                    VocabularyReviewState.user_id == user_id,
                    VocabularyReviewState.entry_id.in_(member_ids),
                    VocabularyReviewState.interval_days >= MASTERED_INTERVAL_DAYS,
                )
            )
            if int(mastered or 0) >= len(member_ids):
                ruby.earn(
                    db,
                    user_id=user_id,
                    source_type="topic_mastered",
                    source_id=topic_id,
                )
    except Exception:  # pragma: no cover - lưới an toàn, xem chú thích trên
        pass


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


@router.get("/vocabulary-review/due-count", response_model=ReviewDueCount)
def review_due_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewDueCount:
    """Bao nhiêu từ đang đến hạn, và không gì khác.

    Huy hiệu trên thanh điều hướng gọi endpoint này ở mọi lần đổi trang, nên nó
    phải là MỘT lượt `COUNT` chứ không phải một lượt dựng danh sách rồi đếm.

    Đếm KHÔNG có `limit`, khác `review_session`: ở đó `limit` là kích thước một
    buổi học, còn ở đây con số là toàn bộ hàng đợi. Mượn `due_count` của session
    sẽ chặn ở 100 và người có 150 từ đến hạn thấy 100 — sai mà vẫn hợp lý, nên
    không ai phát hiện.
    """
    due = db.scalar(
        select(func.count())
        .select_from(VocabularyReviewState)
        .join(VocabularyEntry, VocabularyEntry.id == VocabularyReviewState.entry_id)
        .where(
            VocabularyReviewState.user_id == current_user.id,
            VocabularyReviewState.due_at <= datetime.now(UTC),
            VocabularyEntry.status == PUBLISHED,
        )
    )
    return ReviewDueCount(due=due or 0)


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

    # Con thú vui lên vì người học vừa ôn một từ. Ở ĐÂY chứ không trong
    # `_apply_review`: hàm ấy còn được các cuộc chạm mặt gọi tới, và ở đó phần
    # thưởng đã là `XP_PER_ENCOUNTER` — móc vào hàm chung thì một lượt trả lời
    # NPC được trả hai lần. `test_encounters` bắt được đúng chỗ đó.
    reward_study(db, current_user.id, "vocabulary_review")
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

    # Con thú vui lên vì người học vừa ôn một từ. Ở ĐÂY chứ không trong
    # `_apply_review`: hàm ấy còn được các cuộc chạm mặt gọi tới, và ở đó phần
    # thưởng đã là `XP_PER_ENCOUNTER` — móc vào hàm chung thì một lượt trả lời
    # NPC được trả hai lần. `test_encounters` bắt được đúng chỗ đó.
    reward_study(db, current_user.id, "vocabulary_review")
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
