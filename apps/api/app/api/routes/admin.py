"""Content admin: paste, review, commit, publish.

Two rules run through everything here, both from ADR-005:

  * **Parse never writes.** A parser gets things wrong; putting 300 half-right
    rows in the database is harder to clean up than retyping them. Parsing is a
    separate endpoint that returns rows and their problems, and the client sends
    back what the editor approved.
  * **Commit always writes `draft`.** There is no path from import straight to
    published. Publishing is its own action, admin-only, and recorded.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_role
from app.core.database import get_db
from app.models import (
    DictationAttempt,
    DictationItem,
    DictationSection,
    DictationStory,
    DictationTopic,
    Topic,
    User,
    VocabularyEntry,
    VocabularyTopic,
)
from app.schemas.admin import (
    AudioSlotState,
    CommitResult,
    DictationAdmin,
    DictationCommit,
    DictationParseResponse,
    DictationRow,
    DictationSectionAdmin,
    DictationSectionCreate,
    DictationSectionUpdate,
    DictationStoryAdmin,
    DictationStoryCreate,
    DictationStoryUpdate,
    DictationTopicAdmin,
    DictationTopicCreate,
    DictationTopicUpdate,
    DictationUpdate,
    ParseRequest,
    StoryReorder,
    TopicAdmin,
    TopicCreate,
    VocabularyAdmin,
    VocabularyCommit,
    VocabularyParseResponse,
    VocabularyRow,
    VocabularyUpdate,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.services.content_import import parse_dictation, parse_vocabulary
from app.services.media_state import (
    dictation_audio_state,
    dictation_is_publishable,
    vocabulary_audio_slots,
    vocabulary_is_publishable,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# An editor writes, an admin releases. Nobody reviews their own work.
can_edit = require_role("editor", "admin")
can_publish = require_role("admin")


def _topic_admin(topic: Topic) -> TopicAdmin:
    return TopicAdmin(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        position=topic.position,
        status=topic.status,
    )


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


def _dictation_admin(item: DictationItem) -> DictationAdmin:
    return DictationAdmin(
        id=str(item.id),
        transcript=item.transcript,
        difficulty=item.difficulty,
        status=item.status,
        audio_state=dictation_audio_state(item).value,
        publishable=dictation_is_publishable(item),
        story_id=str(item.story_id) if item.story_id else None,
        position=item.position,
    )


# --- topics ---------------------------------------------------------------


@router.get("/topics", response_model=list[TopicAdmin])
def list_topics(db: Session = Depends(get_db), _: User = Depends(can_edit)) -> list[TopicAdmin]:
    topics = db.scalars(select(Topic).order_by(Topic.position, Topic.name)).all()
    return [_topic_admin(topic) for topic in topics]


@router.post("/topics", response_model=TopicAdmin, status_code=status.HTTP_201_CREATED)
def create_topic(
    body: TopicCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> TopicAdmin:
    topic = Topic(
        slug=body.slug,
        name=body.name,
        description=body.description,
        position=body.position,
        # Topics are the one thing a learner sees before any content exists, and
        # an empty topic is harmless, so they go live immediately.
        status="published",
        created_by=user.id,
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
    return _topic_admin(topic)


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
        db.add(entry)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
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
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[VocabularyAdmin]:
    query = select(VocabularyEntry)
    entries = db.scalars(
        query.options(selectinload(VocabularyEntry.audio))
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
        .options(selectinload(VocabularyEntry.audio))
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


# --- dictation ------------------------------------------------------------


@router.post("/dictation/parse", response_model=DictationParseResponse)
def parse_dictation_paste(
    body: ParseRequest, _: User = Depends(can_edit)
) -> DictationParseResponse:
    rows = [
        DictationRow(line=row.line, transcript=row.transcript, problems=row.problems)
        for row in parse_dictation(body.raw_text)
    ]
    ok = sum(1 for row in rows if not row.problems)
    return DictationParseResponse(ok_count=ok, error_count=len(rows) - ok, rows=rows)


@router.post("/dictation", response_model=CommitResult, status_code=status.HTTP_201_CREATED)
def commit_dictation(
    body: DictationCommit, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> CommitResult:
    topic_id = uuid.UUID(body.topic_id) if body.topic_id else None
    if topic_id is not None and db.get(Topic, topic_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    story_id = uuid.UUID(body.story_id) if body.story_id else None
    next_position: int | None = None
    if story_id is not None:
        if db.get(DictationStory, story_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
        # Nối tiếp sau những câu đã có, không chèn vào giữa: dán thêm vào một
        # story đang soạn dở là thao tác thường gặp, và đánh số lại từ đầu sẽ
        # xáo trộn thứ tự của phần đã nhập.
        highest = db.scalar(
            select(func.max(DictationItem.position)).where(DictationItem.story_id == story_id)
        )
        next_position = (highest or 0) + 1

    created = 0
    skipped = 0
    problems: list[str] = []

    for row in body.rows:
        if row.problems:
            skipped += 1
            problems.append(f"line {row.line}: skipped, still has problems")
            continue
        # audio_asset_id is NOT NULL, so a dictation item cannot exist before its
        # audio does. The row is created by the backfill worker, which owns TTS;
        # the API cannot import it (PHASE2-AUDIO A4.1).
        db.add(
            DictationItem(
                audio_asset_id=None,
                transcript=row.transcript,
                topic_id=topic_id,
                story_id=story_id,
                position=next_position,
                difficulty=body.difficulty,
                status="draft",
                created_by=user.id,
            )
        )
        if next_position is not None:
            next_position += 1
        created += 1

    db.commit()
    return CommitResult(created=created, skipped=skipped, problems=problems)


@router.get("/dictation", response_model=Page[DictationAdmin])
def list_dictation_admin(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[DictationAdmin]:
    query = select(DictationItem)
    items = db.scalars(
        query.options(selectinload(DictationItem.asset))
        # Đây là chỗ thiếu khoá phụ đau nhất: `difficulty` là số nguyên 1-5, nên
        # gần như mọi hàng đều trùng khoá sắp xếp và thứ tự giữa hai truy vấn
        # gần như chắc chắn khác nhau.
        .order_by(DictationItem.status, DictationItem.difficulty, DictationItem.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return page_of([_dictation_admin(item) for item in items], count_rows(db, query), limit, offset)


@router.patch("/dictation/{item_id}", response_model=DictationAdmin)
def update_dictation(
    item_id: uuid.UUID,
    body: DictationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> DictationAdmin:
    item = db.get(DictationItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    payload = body.model_dump(exclude_unset=True)
    if "topic_id" in payload:
        payload["topic_id"] = uuid.UUID(payload["topic_id"]) if payload["topic_id"] else None

    # `story_id` kéo theo `position`: CHECK ck_dictation_item_story_position đòi
    # hai cột luôn cùng có hoặc cùng không. Đặt một cột mà quên cột kia thì
    # database từ chối, và người dùng nhận một lỗi 500 khó hiểu thay vì thao tác
    # họ vừa yêu cầu.
    if "story_id" in payload:
        raw = payload.pop("story_id")
        if raw:
            story_id = uuid.UUID(raw)
            if db.get(DictationStory, story_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
            highest = db.scalar(
                select(func.max(DictationItem.position)).where(
                    DictationItem.story_id == story_id, DictationItem.id != item.id
                )
            )
            item.story_id = story_id
            item.position = (highest or 0) + 1
        else:
            item.story_id = None
            item.position = None

    for field_name, value in payload.items():
        setattr(item, field_name, value)

    db.commit()
    db.refresh(item)
    return _dictation_admin(item)


@router.post("/dictation/{item_id}/publish", response_model=DictationAdmin)
def publish_dictation(
    item_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> DictationAdmin:
    item = db.get(DictationItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    state = dictation_audio_state(item)
    if state.value != "current":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot publish: audio is {state.value}. The transcript is the answer key, so "
                f"a stale clip would grade learners on a sentence they were never played. "
                f"Run in apps/api: uv run python -m app.content.backfill_audio"
            ),
        )

    item.status = "published"
    item.published_by = user.id
    item.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return _dictation_admin(item)


# --- cây dictation: topic -> section -> story ------------------------------


@router.get("/dictation/topics", response_model=list[DictationTopicAdmin])
def list_dictation_topics_admin(
    db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> list[DictationTopicAdmin]:
    counts = (
        select(func.count(DictationSection.id))
        .where(DictationSection.topic_id == DictationTopic.id)
        .scalar_subquery()
    )
    rows = db.execute(
        select(DictationTopic, counts.label("n")).order_by(
            DictationTopic.position, DictationTopic.name
        )
    ).all()
    return [
        DictationTopicAdmin(
            id=str(t.id),
            slug=t.slug,
            name=t.name,
            description=t.description,
            position=t.position,
            status=t.status,
            section_count=n,
        )
        for t, n in rows
    ]


@router.post(
    "/dictation/topics", response_model=DictationTopicAdmin, status_code=status.HTTP_201_CREATED
)
def create_dictation_topic(
    body: DictationTopicCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> DictationTopicAdmin:
    topic = DictationTopic(
        slug=body.slug,
        name=body.name,
        description=body.description,
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
            status_code=status.HTTP_409_CONFLICT, detail="Slug already exists"
        ) from None
    db.refresh(topic)
    return DictationTopicAdmin(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        position=topic.position,
        status=topic.status,
        section_count=0,
    )


@router.get("/dictation/sections", response_model=Page[DictationSectionAdmin])
def list_dictation_sections_admin(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[DictationSectionAdmin]:
    """Phần của cây dictation.

    Nhóm B chứ không phải nhóm "có trần", dù nó trông giống một bảng phân loại:
    số phần là chủ đề NHÂN số phần mỗi chủ đề, nên nó phình theo nội dung chứ
    không dừng ở một con số do miền nghiệp vụ đặt ra.

    `position` và `name` đều không duy nhất, nên thiếu `id` thì lật trang sẽ lặp
    một phần và nuốt một phần khác.
    """
    counts = (
        select(func.count(DictationStory.id))
        .where(DictationStory.section_id == DictationSection.id)
        .scalar_subquery()
    )
    query = select(DictationSection)
    rows = db.execute(
        select(DictationSection, counts.label("n"))
        .options(selectinload(DictationSection.topic))
        .order_by(DictationSection.position, DictationSection.name, DictationSection.id)
        .limit(limit)
        .offset(offset)
    ).all()
    sections = [
        DictationSectionAdmin(
            id=str(s.id),
            topic_id=str(s.topic_id),
            topic_name=s.topic.name,
            name=s.name,
            description=s.description,
            position=s.position,
            status=s.status,
            story_count=n,
        )
        for s, n in rows
    ]
    return page_of(sections, count_rows(db, query), limit, offset)


@router.post(
    "/dictation/sections",
    response_model=DictationSectionAdmin,
    status_code=status.HTTP_201_CREATED,
)
def create_dictation_section(
    body: DictationSectionCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> DictationSectionAdmin:
    topic = db.get(DictationTopic, uuid.UUID(body.topic_id))
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    section = DictationSection(
        topic_id=topic.id,
        name=body.name,
        description=body.description,
        position=body.position,
        status="draft",
        created_by=user.id,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return DictationSectionAdmin(
        id=str(section.id),
        topic_id=str(topic.id),
        topic_name=topic.name,
        name=section.name,
        description=section.description,
        position=section.position,
        status=section.status,
        story_count=0,
    )


def _story_admin(db: Session, story: DictationStory) -> DictationStoryAdmin:
    total = db.scalar(
        select(func.count(DictationItem.id)).where(DictationItem.story_id == story.id)
    )
    published = db.scalar(
        select(func.count(DictationItem.id)).where(
            DictationItem.story_id == story.id, DictationItem.status == "published"
        )
    )
    return DictationStoryAdmin(
        id=str(story.id),
        section_id=str(story.section_id),
        section_name=story.section.name,
        topic_name=story.section.topic.name,
        title=story.title,
        description=story.description,
        position=story.position,
        difficulty=story.difficulty,
        status=story.status,
        item_count=total or 0,
        published_item_count=published or 0,
        publishable=(published or 0) > 0,
    )


@router.get("/dictation/stories", response_model=Page[DictationStoryAdmin])
def list_dictation_stories_admin(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[DictationStoryAdmin]:
    query = select(DictationStory)
    stories = db.scalars(
        query.options(selectinload(DictationStory.section).selectinload(DictationSection.topic))
        .order_by(DictationStory.position, DictationStory.title, DictationStory.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return page_of(
        [_story_admin(db, story) for story in stories], count_rows(db, query), limit, offset
    )


@router.post(
    "/dictation/stories", response_model=DictationStoryAdmin, status_code=status.HTTP_201_CREATED
)
def create_dictation_story(
    body: DictationStoryCreate, db: Session = Depends(get_db), user: User = Depends(can_edit)
) -> DictationStoryAdmin:
    section = db.scalars(
        select(DictationSection)
        .where(DictationSection.id == uuid.UUID(body.section_id))
        .options(selectinload(DictationSection.topic))
    ).first()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    story = DictationStory(
        section_id=section.id,
        title=body.title,
        description=body.description,
        position=body.position,
        difficulty=body.difficulty,
        status="draft",
        created_by=user.id,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return _story_admin(db, story)


def _publish_node(
    db: Session, node: DictationTopic | DictationSection | DictationStory, user: User
) -> None:
    node.status = "published"
    node.published_by = user.id
    node.published_at = datetime.now(UTC)
    db.commit()


@router.post("/dictation/topics/{topic_id}/publish", response_model=DictationTopicAdmin)
def publish_dictation_topic(
    topic_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> DictationTopicAdmin:
    topic = db.get(DictationTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    _publish_node(db, topic, user)
    count = db.scalar(
        select(func.count(DictationSection.id)).where(DictationSection.topic_id == topic.id)
    )
    return DictationTopicAdmin(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        position=topic.position,
        status=topic.status,
        section_count=count or 0,
    )


@router.post("/dictation/sections/{section_id}/publish", response_model=DictationSectionAdmin)
def publish_dictation_section(
    section_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> DictationSectionAdmin:
    section = db.scalars(
        select(DictationSection)
        .where(DictationSection.id == section_id)
        .options(selectinload(DictationSection.topic))
    ).first()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    _publish_node(db, section, user)
    count = db.scalar(
        select(func.count(DictationStory.id)).where(DictationStory.section_id == section.id)
    )
    return DictationSectionAdmin(
        id=str(section.id),
        topic_id=str(section.topic_id),
        topic_name=section.topic.name,
        name=section.name,
        description=section.description,
        position=section.position,
        status=section.status,
        story_count=count or 0,
    )


@router.post("/dictation/stories/{story_id}/publish", response_model=DictationStoryAdmin)
def publish_dictation_story(
    story_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(can_publish)
) -> DictationStoryAdmin:
    story = db.scalars(
        select(DictationStory)
        .where(DictationStory.id == story_id)
        .options(selectinload(DictationStory.section).selectinload(DictationSection.topic))
    ).first()
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    # Cùng một tinh thần với cổng publish của audio: từ chối thay vì cho ra một
    # trang trống. Story không có câu nào đã publish sẽ hiện với học viên như
    # một bài hỏng, chứ không như một bài chưa soạn xong.
    published = db.scalar(
        select(func.count(DictationItem.id)).where(
            DictationItem.story_id == story.id, DictationItem.status == "published"
        )
    )
    if not published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot publish: the story has no published sentences. Publish its "
                "sentences first — a story with none is an empty page to a learner."
            ),
        )
    _publish_node(db, story, user)
    return _story_admin(db, story)


# --- sửa và xoá cây --------------------------------------------------------
#
# Xoá ở đây là xoá **cấu trúc**, không phải xoá bài làm của học viên. Khoá ngoại
# đã dựng sẵn cho việc đó: `dictation_section.topic_id` và `dictation_story.
# section_id` là CASCADE (xoá nhánh thì xoá cả cành), còn `dictation_item.
# story_id` là SET NULL — xoá một bài thì các câu trong nó trở lại thành câu lẻ
# chứ không biến mất. Mất một bài học đã soạn vì bấm nhầm là thứ không nên xảy
# ra được.


def _detach_items(db: Session, story_ids: list[uuid.UUID]) -> None:
    """Gỡ các câu ra khỏi những story sắp bị xoá, xoá cả `story_id` lẫn `position`.

    Bắt buộc, và lý do không hiển nhiên: khoá ngoại khai `ON DELETE SET NULL`,
    nhưng database chỉ xoá `story_id` và để nguyên `position` — thế là vi phạm
    CHECK `ck_dictation_item_story_position`, vốn đòi hai cột luôn cùng có hoặc
    cùng không. Hai thứ đó chống nhau, nên nếu không gỡ trước thì **không xoá
    được story nào cả**: database từ chối, và người dùng nhận một lỗi 500.

    Gỡ ở đây thì `ON DELETE SET NULL` không còn gì để chạm vào. Nó vẫn là lưới
    an toàn cho ai xoá thẳng bằng SQL — khi đó DB sẽ từ chối, ồn ào nhưng an
    toàn, thay vì để lại câu mang số thứ tự trỏ vào một bài không còn tồn tại.
    """
    if not story_ids:
        return
    db.execute(
        update(DictationItem)
        .where(DictationItem.story_id.in_(story_ids))
        .values(story_id=None, position=None)
    )


def _apply(node: object, body: object, fields: tuple[str, ...]) -> None:
    """Gán những trường được gửi lên, bỏ qua những trường không gửi.

    `exclude_unset` là mấu chốt: PATCH phải phân biệt "đặt về rỗng" với "không
    đụng tới". Không có nó, mọi PATCH sẽ xoá sạch những trường client không quan
    tâm.
    """
    data = body.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
    for field in fields:
        if field in data:
            setattr(node, field, data[field])


@router.patch("/dictation/topics/{topic_id}", response_model=DictationTopicAdmin)
def update_dictation_topic(
    topic_id: uuid.UUID,
    body: DictationTopicUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> DictationTopicAdmin:
    topic = db.get(DictationTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    _apply(topic, body, ("name", "slug", "description", "position", "status"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already exists"
        ) from None
    db.refresh(topic)
    count = db.scalar(
        select(func.count(DictationSection.id)).where(DictationSection.topic_id == topic.id)
    )
    return DictationTopicAdmin(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        description=topic.description,
        position=topic.position,
        status=topic.status,
        section_count=count or 0,
    )


@router.delete("/dictation/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dictation_topic(
    topic_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    topic = db.get(DictationTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    # Section và story đi theo (CASCADE), nhưng các CÂU thì không: chúng trở lại
    # thành câu lẻ và vẫn nằm trong màn quản lý.
    story_ids = list(
        db.scalars(
            select(DictationStory.id)
            .join(DictationSection, DictationSection.id == DictationStory.section_id)
            .where(DictationSection.topic_id == topic.id)
        )
    )
    _detach_items(db, story_ids)
    db.delete(topic)
    db.commit()


@router.patch("/dictation/sections/{section_id}", response_model=DictationSectionAdmin)
def update_dictation_section(
    section_id: uuid.UUID,
    body: DictationSectionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> DictationSectionAdmin:
    section = db.scalars(
        select(DictationSection)
        .where(DictationSection.id == section_id)
        .options(selectinload(DictationSection.topic))
    ).first()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    if body.topic_id is not None and db.get(DictationTopic, uuid.UUID(body.topic_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if body.topic_id is not None:
        section.topic_id = uuid.UUID(body.topic_id)
    _apply(section, body, ("name", "description", "position", "status"))
    db.commit()
    db.refresh(section)
    count = db.scalar(
        select(func.count(DictationStory.id)).where(DictationStory.section_id == section.id)
    )
    return DictationSectionAdmin(
        id=str(section.id),
        topic_id=str(section.topic_id),
        topic_name=section.topic.name,
        name=section.name,
        description=section.description,
        position=section.position,
        status=section.status,
        story_count=count or 0,
    )


@router.delete("/dictation/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dictation_section(
    section_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    section = db.get(DictationSection, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    story_ids = list(
        db.scalars(select(DictationStory.id).where(DictationStory.section_id == section.id))
    )
    _detach_items(db, story_ids)
    db.delete(section)
    db.commit()


@router.patch("/dictation/stories/{story_id}", response_model=DictationStoryAdmin)
def update_dictation_story(
    story_id: uuid.UUID,
    body: DictationStoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> DictationStoryAdmin:
    story = db.scalars(
        select(DictationStory)
        .where(DictationStory.id == story_id)
        .options(selectinload(DictationStory.section).selectinload(DictationSection.topic))
    ).first()
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    if body.section_id is not None:
        if db.get(DictationSection, uuid.UUID(body.section_id)) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        story.section_id = uuid.UUID(body.section_id)
    _apply(story, body, ("title", "description", "position", "difficulty", "status"))
    db.commit()
    db.refresh(story)
    return _story_admin(db, story)


@router.delete("/dictation/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dictation_story(
    story_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    story = db.get(DictationStory, story_id)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    # Xoá vỏ không được kéo theo phần ruột đã mất công soạn: các câu trở lại
    # thành câu lẻ và vẫn nằm trong màn "Câu nghe".
    _detach_items(db, [story.id])
    db.delete(story)
    db.commit()


@router.post("/dictation/stories/{story_id}/reorder", response_model=list[DictationAdmin])
def reorder_story_items(
    story_id: uuid.UUID,
    body: StoryReorder,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> list[DictationAdmin]:
    story = db.get(DictationStory, story_id)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    items = db.scalars(
        select(DictationItem)
        .where(DictationItem.story_id == story.id)
        .options(selectinload(DictationItem.asset))
    ).all()
    by_id = {item.id: item for item in items}
    wanted = [uuid.UUID(value) for value in body.item_ids]

    # Đòi đúng và đủ tập câu của story. Nhận một phần sẽ để lại những câu không
    # được nhắc tới mang số cũ, và chúng sẽ đụng số với những câu vừa đánh lại.
    if set(wanted) != set(by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_ids must list exactly the sentences of this story, once each",
        )

    for index, item_id in enumerate(wanted, start=1):
        by_id[item_id].position = index
    db.commit()

    return [_dictation_admin(by_id[item_id]) for item_id in wanted]


@router.delete("/dictation/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dictation_item(
    item_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(can_publish)
) -> None:
    item = db.get(DictationItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # `dictation_attempt.item_id` là RESTRICT, nên xoá một câu đã có người làm sẽ
    # nổ IntegrityError. Chặn trước và chỉ đường sang `archived` — trạng thái đã
    # được thiết kế đúng cho việc này (mixins.CONTENT_STATUSES): gỡ khỏi tầm mắt
    # học viên mà không làm mồ côi lịch sử làm bài của họ.
    attempts = db.scalar(
        select(func.count(DictationAttempt.id)).where(DictationAttempt.item_id == item.id)
    )
    if attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete: {attempts} learner attempt(s) reference this sentence. "
                "Set its status to 'archived' instead — that hides it from learners "
                "without orphaning their history."
            ),
        )
    db.delete(item)
    db.commit()
