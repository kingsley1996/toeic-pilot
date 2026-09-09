"""Quản trị nội dung TỪ VỰNG: dán, duyệt, ghi, phát hành.

Hai luật xuyên suốt, cả hai từ ADR-005 và cùng áp cho `admin_dictation.py`:

  * **Parse không bao giờ ghi.** Trình phân tích có lúc sai; ba trăm hàng
    đúng-một-nửa nằm trong database khó dọn hơn là gõ lại. Phân tích là một
    endpoint riêng trả về hàng kèm lỗi của chúng, và client gửi lại đúng thứ
    người soạn đã duyệt.
  * **Commit luôn ghi `draft`.** Không có đường đi thẳng từ nhập vào thành đã
    phát hành. Phát hành là hành động riêng, chỉ admin, và được ghi lại.

Tách khỏi dictation vì hai miền đổi vì lý do khác nhau, không phải vì tệp cũ
dài: `REFACTOR-LONG-FILES.md` §0.
"""

import re
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_role
from app.api.routes._admin_content import _apply
from app.core.database import get_db
from app.models import (
    CollocationDetail,
    DictationItem,
    Topic,
    User,
    VocabularyAudio,
    VocabularyCollection,
    VocabularyCollectionItem,
    VocabularyEntry,
    VocabularyTopic,
)
from app.models.vocabulary import COLLOCATION_PATTERNS, MAX_COLLOCATION_DISTRACTORS
from app.schemas.admin import (
    AudioSlotState,
    CollocationCommit,
    CollocationParseResponse,
    CollocationRow,
    CollocationUpdate,
    CommitResult,
    ParseRequest,
    TopicAdmin,
    TopicCreate,
    TopicUpdate,
    VocabularyAdmin,
    VocabularyCollectionAdmin,
    VocabularyCollectionCreate,
    VocabularyCollectionItemAdmin,
    VocabularyCollectionItemCreate,
    VocabularyCollectionItemUpdate,
    VocabularyCollectionUpdate,
    VocabularyCommit,
    VocabularyParseResponse,
    VocabularyRow,
    VocabularyUpdate,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.services.content_import import parse_collocation, parse_vocabulary
from app.services.media_state import (
    vocabulary_audio_slots,
    vocabulary_is_publishable,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# An editor writes, an admin releases. Nobody reviews their own work.
can_edit = require_role("editor", "admin")
can_publish = require_role("admin")


def _topic_admin(topic: Topic, entry_count: int) -> TopicAdmin:
    return TopicAdmin(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        position=topic.position,
        status=topic.status,
        entry_count=entry_count,
        collection_item_id=str(topic.collection_item_id) if topic.collection_item_id else None,
        collection_item_name=topic.collection_item.name if topic.collection_item else None,
    )


def _entry_counts(db: Session) -> dict[uuid.UUID, int]:
    """topic_id → số từ gắn vào (mọi trạng thái).

    Một truy vấn cho cả danh sách thay vì N truy vấn: chủ đề là bảng nhỏ nhưng
    trang admin liệt kê tất cả cùng lúc.
    """
    rows = db.execute(
        select(VocabularyTopic.topic_id, func.count(VocabularyTopic.entry_id)).group_by(
            VocabularyTopic.topic_id
        )
    ).all()
    return {topic_id: count for topic_id, count in rows}


def _vocabulary_admin(entry: VocabularyEntry) -> VocabularyAdmin:
    return VocabularyAdmin(
        id=str(entry.id),
        headword=entry.headword,
        part_of_speech=entry.part_of_speech,
        meaning_vi=entry.meaning_vi,
        status=entry.status,
        audio=[
            AudioSlotState(kind=slot.kind, accent=slot.accent, state=slot.state.value)
            for slot in vocabulary_audio_slots(entry)
        ],
        publishable=vocabulary_is_publishable(entry),
    )


# --- topics ---------------------------------------------------------------


@router.get("/topics", response_model=list[TopicAdmin])
def list_topics(db: Session = Depends(get_db), _: User = Depends(can_edit)) -> list[TopicAdmin]:
    topics = db.scalars(
        select(Topic)
        .options(selectinload(Topic.collection_item))
        .order_by(Topic.position, Topic.name)
    ).all()
    counts = _entry_counts(db)
    return [_topic_admin(topic, counts.get(topic.id, 0)) for topic in topics]


def _get_collection_item(db: Session, item_id: str, detail: str) -> VocabularyCollectionItem:
    try:
        item_pk = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from None
    item = db.get(VocabularyCollectionItem, item_pk)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return item


def _get_collection(db: Session, collection_id: str, detail: str) -> VocabularyCollection:
    try:
        pk = uuid.UUID(collection_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from None
    collection = db.get(VocabularyCollection, pk)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return collection


@router.post("/topics", response_model=TopicAdmin, status_code=status.HTTP_201_CREATED)
def create_topic(
    body: TopicCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> TopicAdmin:
    # Topic gắn vào cuốn nào phải tồn tại thực — FK không có gì bảo vệ lúc insert
    # trên SQLite nên kiểm tra ở đây trước khi commit.
    collection_item_id: uuid.UUID | None = None
    if body.collection_item_id:
        collection_item_id = _get_collection_item(
            db, body.collection_item_id, "Collection item not found"
        ).id
    topic = Topic(
        slug=body.slug,
        name=body.name,
        description=body.description,
        position=body.position,
        # Topics are the one thing a learner sees before any content exists, and
        # an empty topic is harmless, so they go live immediately.
        status="published",
        created_by=user.id,
        collection_item_id=collection_item_id,
    )
    db.add(topic)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Topic {body.slug!r} already exists"
        ) from None
    db.refresh(topic)
    return _topic_admin(topic, 0)


@router.patch("/topics/{topic_id}", response_model=TopicAdmin)
def update_topic(
    topic_id: uuid.UUID,
    body: TopicUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> TopicAdmin:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    _apply(topic, body, ("name", "slug", "description", "position", "status"))
    # Quy ước gửi lên: "" = gỡ khỏi cuốn; UUID = xếp vào cuốn; không gửi = để
    # nguyên. `None` không dùng để gỡ vì exclude_unset không phân biệt được
    # "không gửi" với gửi null.
    data = body.model_dump(exclude_unset=True)
    if "collection_item_id" in data:
        raw = data["collection_item_id"]
        if raw == "":
            topic.collection_item_id = None
        elif raw:
            topic.collection_item_id = _get_collection_item(db, raw, "Collection item not found").id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already exists"
        ) from None
    db.refresh(topic)
    return _topic_admin(topic, _entry_counts(db).get(topic.id, 0))


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(
    topic_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    """Xoá chủ đề, KHÔNG xoá từ.

    `vocabulary_topic` và `dictation_item.topic_id` đều gắn `ondelete=CASCADE` /
    `SET NULL` sẵn, nên xoá chủ đề chỉ gỡ liên kết — các từ vẫn còn trong màn
    quản lý (không topic), không có dữ liệu học tập nào bị đụng. Cùng nguyên tắc
    với việc xoá bài dictation không xoá câu. Đăng nhập mức admin, không phải
    editor, vì đây là xoá thứ người học đang nhìn thấy.
    """
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    # Gỡ liên kết BẰNG TAY thay vì dựa vào ON DELETE trong schema. Postgres sẽ
    # CASCADE/SET NULL giúp, nhưng SQLite (bộ test) không thực thi khoá ngoại mặc
    # định, và làm thẳng thì hai database cư xử giống hệt nhau — không có cái bẫy
    # "test xanh, prod khác" nằm chờ.
    db.execute(delete(VocabularyTopic).where(VocabularyTopic.topic_id == topic.id))
    db.execute(
        update(DictationItem).where(DictationItem.topic_id == topic.id).values(topic_id=None)
    )
    db.delete(topic)
    db.commit()


# --- vocabulary tree (collection -> collection_item) -----------------------


def _collection_admin(
    collection: VocabularyCollection, item_count: int
) -> VocabularyCollectionAdmin:
    return VocabularyCollectionAdmin(
        id=str(collection.id),
        slug=collection.slug,
        name=collection.name,
        description=collection.description,
        position=collection.position,
        status=collection.status,
        item_count=item_count,
    )


def _collection_item_admin(
    item: VocabularyCollectionItem, topic_count: int
) -> VocabularyCollectionItemAdmin:
    return VocabularyCollectionItemAdmin(
        id=str(item.id),
        collection_id=str(item.collection_id),
        collection_name=item.collection.name,
        name=item.name,
        description=item.description,
        position=item.position,
        status=item.status,
        topic_count=topic_count,
    )


def _item_counts(db: Session) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    """(collection_id -> số item, item_id -> số topic) trong hai truy vấn."""
    items_per_collection = {
        collection_id: count
        for collection_id, count in db.execute(
            select(
                VocabularyCollectionItem.collection_id,
                func.count(VocabularyCollectionItem.id),
            ).group_by(VocabularyCollectionItem.collection_id)
        ).all()
    }
    topics_per_item = {
        item_id: count
        for item_id, count in db.execute(
            select(Topic.collection_item_id, func.count(Topic.id))
            .where(Topic.collection_item_id.is_not(None))
            .group_by(Topic.collection_item_id)
        ).all()
    }
    return items_per_collection, topics_per_item


@router.get("/vocabulary-collections", response_model=list[VocabularyCollectionAdmin])
def list_vocabulary_collections(
    db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[VocabularyCollectionAdmin]:
    collections = db.scalars(
        select(VocabularyCollection).order_by(
            VocabularyCollection.position, VocabularyCollection.name
        )
    ).all()
    items_per_collection, _topics_per_item = _item_counts(db)
    return [
        _collection_admin(collection, items_per_collection.get(collection.id, 0))
        for collection in collections
    ]


@router.post(
    "/vocabulary-collections",
    response_model=VocabularyCollectionAdmin,
    status_code=status.HTTP_201_CREATED,
)
def create_vocabulary_collection(
    body: VocabularyCollectionCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> VocabularyCollectionAdmin:
    # Cùng luật với dictation section/store: tầng trung gian sinh ra ở trạng thái
    # draft — người học không thấy gì cho tới khi admin publish (không như topic
    # tự publish vì "topic trống vô hại" là ngoại lệ duy nhất).
    collection = VocabularyCollection(
        slug=body.slug,
        name=body.name,
        description=body.description,
        position=body.position,
        status="draft",
        created_by=user.id,
    )
    db.add(collection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vocabulary collection {body.slug!r} already exists",
        ) from None
    db.refresh(collection)
    return _collection_admin(collection, 0)


@router.post(
    "/vocabulary-collections/{collection_id}/publish", response_model=VocabularyCollectionAdmin
)
def publish_vocabulary_collection(
    collection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> VocabularyCollectionAdmin:
    collection = db.get(VocabularyCollection, collection_id)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary collection not found"
        )
    collection.status = "published"
    collection.published_by = user.id
    collection.published_at = datetime.now(UTC)
    db.commit()
    items_per_collection, _topics_per_item = _item_counts(db)
    return _collection_admin(collection, items_per_collection.get(collection.id, 0))


@router.patch("/vocabulary-collections/{collection_id}", response_model=VocabularyCollectionAdmin)
def update_vocabulary_collection(
    collection_id: uuid.UUID,
    body: VocabularyCollectionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> VocabularyCollectionAdmin:
    collection = db.get(VocabularyCollection, collection_id)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary collection not found"
        )
    _apply(collection, body, ("name", "slug", "description", "position", "status"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already exists"
        ) from None
    db.refresh(collection)
    items_per_collection, _topics_per_item = _item_counts(db)
    return _collection_admin(collection, items_per_collection.get(collection.id, 0))


@router.delete("/vocabulary-collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocabulary_collection(
    collection_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    """Xoá tuyển tập: item con CASCADE đi theo (schema), topic được gỡ về NULL
    bằng tay để SQLite/Postgres cư xử giống nhau trong test — xoá tuyển tập
    không bao giờ xoá chủ đề."""
    collection = db.get(VocabularyCollection, collection_id)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary collection not found"
        )
    item_ids = [item.id for item in collection.items]
    if item_ids:
        db.execute(
            update(Topic)
            .where(Topic.collection_item_id.in_(item_ids))
            .values(collection_item_id=None)
        )
    db.delete(collection)
    db.commit()


@router.get("/vocabulary-collection-items", response_model=list[VocabularyCollectionItemAdmin])
def list_vocabulary_collection_items(
    db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[VocabularyCollectionItemAdmin]:
    items = db.scalars(
        select(VocabularyCollectionItem)
        .options(selectinload(VocabularyCollectionItem.collection))
        .order_by(VocabularyCollectionItem.collection_id, VocabularyCollectionItem.position)
    ).all()
    _items_per_collection, topics_per_item = _item_counts(db)
    return [_collection_item_admin(item, topics_per_item.get(item.id, 0)) for item in items]


@router.post(
    "/vocabulary-collection-items",
    response_model=VocabularyCollectionItemAdmin,
    status_code=status.HTTP_201_CREATED,
)
def create_vocabulary_collection_item(
    body: VocabularyCollectionItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit),
) -> VocabularyCollectionItemAdmin:
    collection = _get_collection(db, body.collection_id, "Vocabulary collection not found")
    item = VocabularyCollectionItem(
        collection_id=collection.id,
        name=body.name,
        description=body.description,
        position=body.position,
        status="draft",
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _collection_item_admin(item, 0)


@router.post(
    "/vocabulary-collection-items/{item_id}/publish",
    response_model=VocabularyCollectionItemAdmin,
)
def publish_vocabulary_collection_item(
    item_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> VocabularyCollectionItemAdmin:
    item = db.get(VocabularyCollectionItem, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary collection item not found"
        )
    item.status = "published"
    item.published_by = user.id
    item.published_at = datetime.now(UTC)
    db.commit()
    _items_per_collection, topics_per_item = _item_counts(db)
    return _collection_item_admin(item, topics_per_item.get(item.id, 0))


@router.patch(
    "/vocabulary-collection-items/{item_id}", response_model=VocabularyCollectionItemAdmin
)
def update_vocabulary_collection_item(
    item_id: uuid.UUID,
    body: VocabularyCollectionItemUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> VocabularyCollectionItemAdmin:
    item = db.get(VocabularyCollectionItem, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary collection item not found"
        )
    _apply(item, body, ("name", "description", "position", "status"))
    db.commit()
    db.refresh(item)
    _items_per_collection, topics_per_item = _item_counts(db)
    return _collection_item_admin(item, topics_per_item.get(item.id, 0))


@router.delete("/vocabulary-collection-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocabulary_collection_item(
    item_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    """Xoá cuốn sách: topic bên trong quay về "chưa xếp" (SET NULL, làm tay cho
    đồng nhất SQLite/Postgres), từ vựng không bị đụng vì chúng gắn với topic."""
    item = db.get(VocabularyCollectionItem, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary collection item not found"
        )
    db.execute(
        update(Topic).where(Topic.collection_item_id == item.id).values(collection_item_id=None)
    )
    db.delete(item)
    db.commit()


# --- vocabulary -----------------------------------------------------------


@router.post("/vocabulary/parse", response_model=VocabularyParseResponse)
def parse_vocabulary_paste(
    body: ParseRequest, _: User = Depends(can_edit)
) -> VocabularyParseResponse:
    """Parse a paste and report every problem. Writes nothing."""
    rows = [
        VocabularyRow(
            line=row.line,
            headword=row.headword,
            part_of_speech=row.part_of_speech,
            phonetic=row.phonetic,
            meaning_en=row.meaning_en,
            meaning_vi=row.meaning_vi,
            example=row.example,
            example_vi=row.example_vi,
            problems=row.problems,
        )
        for row in parse_vocabulary(body.raw_text)
    ]
    ok = sum(1 for row in rows if not row.problems)
    return VocabularyParseResponse(ok_count=ok, error_count=len(rows) - ok, rows=rows)


@router.post("/vocabulary", response_model=CommitResult, status_code=status.HTTP_201_CREATED)
def commit_vocabulary(
    body: VocabularyCommit, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> CommitResult:
    topic_id = uuid.UUID(body.topic_id) if body.topic_id else None
    if topic_id is not None and db.get(Topic, topic_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    created = 0
    skipped = 0
    problems: list[str] = []

    for row in body.rows:
        if row.problems:
            skipped += 1
            problems.append(f"line {row.line}: skipped, still has problems")
            continue

        entry = VocabularyEntry(
            headword=row.headword,
            part_of_speech=row.part_of_speech,
            phonetic=row.phonetic,
            meaning_en=row.meaning_en,
            meaning_vi=row.meaning_vi,
            example=row.example,
            example_vi=row.example_vi,
            difficulty=body.difficulty,
            # Never `published` straight from an import, however clean the parse.
            status="draft",
            created_by=user.id,
        )
        try:
            # A savepoint per row, and the `add` INSIDE it. Two failure shapes
            # that the older `flush` then `rollback` got wrong: rolling the whole
            # transaction back discarded every row already flushed in this
            # request while the counter still claimed them — a paste with one
            # duplicate mid-list saved nothing and reported full success — and a
            # pending add left outside the failed savepoint deactivates the
            # session, so the next row could not even be tried.
            with db.begin_nested():
                db.add(entry)
                db.flush()
        except IntegrityError:
            # Rolling back the savepoint discards just this row; the rest of the
            # batch survives.
            skipped += 1
            problems.append(
                f"line {row.line}: {row.headword!r} ({row.part_of_speech}) already exists"
            )
            continue

        if topic_id is not None:
            db.add(VocabularyTopic(entry_id=entry.id, topic_id=topic_id))
        created += 1

    db.commit()
    return CommitResult(created=created, skipped=skipped, problems=problems)


@router.get("/vocabulary", response_model=Page[VocabularyAdmin])
def list_vocabulary_admin(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    collocation: int = Query(default=0, description="1 = chỉ entry có collocation_detail"),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[VocabularyAdmin]:
    # Định nghĩa collocation là SỰ TỒN TẠI của detail (spec §2.1) chứ không phải
    # part_of_speech='phrase' — 59 hàng phrase cũ không phải collocation.
    query = select(VocabularyEntry)
    if collocation == 1:
        query = query.join(
            CollocationDetail, CollocationDetail.entry_id == VocabularyEntry.id
        )
    entries = db.scalars(
        query.options(
            selectinload(VocabularyEntry.audio).selectinload(VocabularyAudio.asset),
        )
        # `id` khép thứ tự lại thành toàn phần: `headword` KHÔNG duy nhất (khoá
        # duy nhất là cặp headword + part_of_speech), nên thiếu nó thì lật trang
        # sẽ lặp một từ và nuốt mất một từ khác, không lỗi nào được ném ra.
        .order_by(VocabularyEntry.status, VocabularyEntry.headword, VocabularyEntry.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return page_of(
        [_vocabulary_admin(entry) for entry in entries],
        count_rows(db, query),
        limit,
        offset,
    )


@router.patch("/vocabulary/{entry_id}", response_model=VocabularyAdmin)
def update_vocabulary(
    entry_id: uuid.UUID,
    body: VocabularyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> VocabularyAdmin:
    entry = db.get(VocabularyEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field_name, value)

    # Editing the headword or the example silently invalidates the recordings —
    # the clip still says the old word. Nothing here repairs that; the publish
    # gate below refuses to release it, and the backfill worker regenerates it.
    db.commit()
    db.refresh(entry)
    return _vocabulary_admin(entry)


@router.post("/vocabulary/{entry_id}/publish", response_model=VocabularyAdmin)
def publish_vocabulary(
    entry_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> VocabularyAdmin:
    entry = db.scalars(
        select(VocabularyEntry)
        .where(VocabularyEntry.id == entry_id)
        .options(
            selectinload(VocabularyEntry.audio).selectinload(VocabularyAudio.asset),
        )
    ).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    slots = vocabulary_audio_slots(entry)
    unusable = [slot for slot in slots if slot.state.value != "current"]
    if unusable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot publish: audio is "
                + ", ".join(f"{slot.kind}/{slot.accent} {slot.state.value}" for slot in unusable)
                + ". Run in apps/api: uv run python -m app.content.backfill_audio"
            ),
        )

    entry.status = "published"
    entry.published_by = user.id
    entry.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(entry)
    return _vocabulary_admin(entry)


# --- collocation (SPEC-COLLOCATION §10–§12) --------------------------------


def _validate_collocation_detail(
    *,
    headword: str,
    base_word: str,
    gap_word: str | None,
    pattern: str,
    distractors: list[str],
) -> list[str]:
    """Bộ luật §11 dùng chung cho commit và PATCH — hai bản sao sẽ trôi."""
    problems: list[str] = []
    if not headword.strip():
        problems.append("headword is required")
    if not base_word.strip():
        problems.append("base_word is required")
    if pattern not in COLLOCATION_PATTERNS:
        problems.append(f"pattern {pattern!r} is not one of {list(COLLOCATION_PATTERNS)}")
    if gap_word:
        if re.search(r"\s", gap_word):
            problems.append("gap_word must be a single token without whitespace")
        elif gap_word == headword.lower():
            problems.append("gap_word must not be the entire headword")
        elif gap_word not in headword.lower().split():
            problems.append(f"gap_word {gap_word!r} does not appear in headword")
    if len(distractors) > MAX_COLLOCATION_DISTRACTORS:
        problems.append(f"at most {MAX_COLLOCATION_DISTRACTORS} distractors")
    if len(set(distractors)) != len(distractors):
        problems.append("duplicate distractors")
    if any(not word.strip() for word in distractors):
        problems.append("empty distractor")
    if gap_word and gap_word in distractors:
        problems.append("distractor must not equal gap_word")
    return problems


def _collocation_row(entry: VocabularyEntry) -> CollocationRow:
    detail = entry.collocation
    assert detail is not None  # callers filter on the relationship
    return CollocationRow(
        line=0,
        headword=entry.headword,
        base_word=detail.base_word,
        gap_word=detail.gap_word,
        pattern=detail.pattern,
        meaning_vi=entry.meaning_vi,
        example=entry.example,
        example_vi=entry.example_vi,
        distractors=list(detail.distractors or []),
    )


@router.post("/collocations/parse", response_model=CollocationParseResponse)
def parse_collocation_paste(
    body: ParseRequest, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> CollocationParseResponse:
    """Parse a collocation paste and report every problem. Writes nothing."""
    existing = set(
        db.scalars(
            select(VocabularyEntry.headword).join(
                CollocationDetail, CollocationDetail.entry_id == VocabularyEntry.id
            )
        )
    )
    existing = {word.lower() for word in existing}
    rows = [
        CollocationRow(**asdict(row))
        for row in parse_collocation(body.raw_text, existing_headwords=existing)
    ]
    ok = sum(1 for row in rows if not row.problems)
    return CollocationParseResponse(ok_count=ok, error_count=len(rows) - ok, rows=rows)


@router.post("/collocations", response_model=CommitResult, status_code=status.HTTP_201_CREATED)
def commit_collocations(
    body: CollocationCommit, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> CommitResult:
    topic_id = uuid.UUID(body.topic_id) if body.topic_id else None
    if topic_id is not None and db.get(Topic, topic_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    created = 0
    skipped = 0
    problems: list[str] = []

    for row in body.rows:
        if row.problems:
            skipped += 1
            problems.append(f"line {row.line}: skipped, still has problems")
            continue
        if remaining := _validate_collocation_detail(
            headword=row.headword,
            base_word=row.base_word,
            gap_word=row.gap_word,
            pattern=row.pattern,
            distractors=row.distractors,
        ):
            skipped += 1
            problems.append(f"line {row.line}: {'; '.join(remaining)}")
            continue

        entry = VocabularyEntry(
            headword=row.headword,
            part_of_speech="phrase",
            meaning_en=row.headword,
            meaning_vi=row.meaning_vi,
            example=row.example,
            example_vi=row.example_vi,
            difficulty=body.difficulty,
            status="draft",
            created_by=user.id,
            collocation=CollocationDetail(
                base_word=row.base_word,
                gap_word=row.gap_word,
                pattern=row.pattern,
                distractors=row.distractors or None,
            ),
        )
        try:
            with db.begin_nested():
                db.add(entry)
                db.flush()
        except IntegrityError:
            skipped += 1
            problems.append(f"line {row.line}: {row.headword!r} (phrase) already exists")
            continue

        if topic_id is not None:
            db.add(VocabularyTopic(entry_id=entry.id, topic_id=topic_id))
        created += 1

    db.commit()
    return CommitResult(created=created, skipped=skipped, problems=problems)


@router.get("/vocabulary/{entry_id}/collocation", response_model=CollocationRow)
def get_collocation(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> CollocationRow:
    """Detail của một entry, cho form sửa sau commit (§12)."""
    entry = db.scalars(
        select(VocabularyEntry)
        .where(VocabularyEntry.id == entry_id)
        .options(selectinload(VocabularyEntry.collocation))
    ).first()
    if entry is None or entry.part_of_speech != "phrase" or entry.collocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return _collocation_row(entry)


@router.patch("/vocabulary/{entry_id}/collocation", response_model=CollocationRow)
def update_collocation(
    entry_id: uuid.UUID,
    body: CollocationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> CollocationRow:
    entry = db.get(VocabularyEntry, entry_id)
    if entry is None or entry.part_of_speech != "phrase":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    detail = entry.collocation
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry has no collocation detail"
        )

    updates = body.model_dump(exclude_unset=True)
    if "base_word" in updates and updates["base_word"]:
        updates["base_word"] = updates["base_word"].lower()
    if "gap_word" in updates:
        # Chuỗi rỗng là ý "gỡ gap" (client không có cách gửi null riêng với
        # absent); empty qua CHECK thì vỡ, nên map sang None.
        updates["gap_word"] = updates["gap_word"].lower() or None
    if "pattern" in updates and updates["pattern"]:
        updates["pattern"] = updates["pattern"].upper()

    merged = {
        "headword": entry.headword,
        "base_word": updates.get("base_word", detail.base_word),
        "gap_word": updates.get("gap_word", detail.gap_word),
        "pattern": updates.get("pattern", detail.pattern),
        "distractors": updates.get("distractors", list(detail.distractors or [])),
    }
    if remaining := _validate_collocation_detail(**merged):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=remaining)

    for field_name, value in updates.items():
        setattr(detail, field_name, value)
    db.commit()
    db.refresh(detail)
    return _collocation_row(entry)
