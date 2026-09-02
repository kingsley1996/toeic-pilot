"""Endpoint DICTATION cho người học: cây bốn tầng, nghe chép, chấm và tiến độ.

Mọi lượt đọc ở đây lọc `status == 'published'`. Cái lọc ấy là thứ duy nhất đứng
giữa một bản nháp viết dở và màn hình người học, và quên nó thì hỏng im lặng —
nội dung cứ thế hiện ra. Mỗi endpoint có một test khẳng định nội dung nháp vẫn
vô hình (ADR-001 A5.3).

Ở đây luật ấy nặng hơn một bậc: cây có bốn tầng và **mỗi tầng lọc độc lập**,
nên một story nháp nằm dưới một section đã phát hành sẽ lọt nếu chỉ lọc ở
section — và không có gì kêu, nội dung trông hoàn toàn bình thường
(`tests/test_dictation_tree.py`).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_optional_user
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
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.schemas.learning import (
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
    StoryItem,
    StoryProgress,
    WordDiff,
)
from app.services import dictation as dictation_grader
from app.services import progression, ruby
from app.services.profile import ensure_profile

router = APIRouter(tags=["learning"])

PUBLISHED = "published"


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


def _dictation_detail(item: DictationItem) -> DictationDetail:
    """Hình dạng chung của một câu gửi cho trình duyệt.

    Hai đường vào — tra theo id và bốc ngẫu nhiên — phải trả về đúng một hình
    dạng. Hai bản dựng tay sẽ trôi khỏi nhau, và chỗ trôi đầu tiên là thứ tệ
    nhất để có hai phiên bản: `transcript`, tức đáp án mà bộ chấm phía trình
    duyệt so vào.
    """
    if item.asset is None:
        # Không tới được chừng nào ck_dictation_item_published_has_audio còn
        # sống — một câu đã xuất bản không thể thiếu audio. Coi như không tìm
        # thấy thay vì nổ, để một ràng buộc lỡ bị gỡ thành 404 chứ không thành
        # 500.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item has no audio")
    return DictationDetail(
        id=str(item.id),
        difficulty=item.difficulty,
        topic_id=str(item.topic_id) if item.topic_id else None,
        word_count=len(dictation_grader.normalise(item.transcript)),
        audio_url=public_audio_url(item.asset.storage_key),
        duration_ms=item.asset.duration_ms,
        transcript=item.transcript,
        transcript_vi=item.transcript_vi,
    )


@router.get("/dictation-random", response_model=DictationDetail)
def get_random_dictation(
    exclude: uuid.UUID | None = Query(
        default=None, description="id vừa nghe, để bấm lần nữa không ra đúng câu cũ"
    ),
    db: Session = Depends(get_db),
) -> DictationDetail:
    """Một câu bất kỳ trong toàn bộ nội dung đã xuất bản.

    **Đường dẫn gạch nối, không lồng dưới `/dictation/`.** `/dictation/{item_id}`
    khai `item_id: uuid.UUID`, nên `/dictation/random` bị chính nó bắt và trả 422
    vì không parse nổi chữ "random" thành UUID. Khai route tĩnh trước route động
    cũng chạy, nhưng khi đó THỨ TỰ KHAI BÁO trở thành thứ gánh trách nhiệm mà
    không nhìn thấy được — cùng lý do `/dictation-topics` đã nằm ngoài.

    Bốc ngẫu nhiên ở máy chủ chứ không ở trình duyệt. Cách làm phía client là
    hỏi `total` rồi bốc một `offset` — chạy được, nhưng nó lôi cơ chế phân trang
    vào một tính năng chẳng liên quan gì tới phân trang, tốn ba lượt gọi cho một
    lần bấm, và **không loại được câu vừa nghe**: với kho nội dung nhỏ, bấm "câu
    khác" mà ra đúng câu cũ đọc như nút hỏng.

    `exclude` bị BỎ QUA khi nó là câu duy nhất còn lại. Tôn trọng nó tuyệt đối
    nghĩa là kho có đúng một câu thì nút trả 404 — một lỗi cho một tình huống
    hoàn toàn hợp lệ.
    """
    query = select(DictationItem).where(DictationItem.status == PUBLISHED)
    item = db.scalars(
        query.where(DictationItem.id != exclude).order_by(func.random()).limit(1)
        if exclude is not None
        else query.order_by(func.random()).limit(1)
    ).first()
    if item is None and exclude is not None:
        # Chỉ còn đúng câu vừa nghe: trả lại chính nó chứ không báo hết nội dung.
        item = db.scalars(query.order_by(func.random()).limit(1)).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No published sentence")
    # `selectinload` không dùng được sau khi đã lấy hàng ra; nạp asset qua quan hệ
    # là một truy vấn nữa, và ở đây đúng một hàng nên nó rẻ.
    return _dictation_detail(item)


@router.get("/dictation/{item_id}", response_model=DictationDetail)
def get_dictation(item_id: uuid.UUID, db: Session = Depends(get_db)) -> DictationDetail:
    item = db.scalars(
        select(DictationItem)
        .where(DictationItem.id == item_id, DictationItem.status == PUBLISHED)
        .options(selectinload(DictationItem.asset))
    ).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    # The transcript ships with the item so the client can grade without a round
    # trip. See DictationDetail.transcript for what that costs and why it is
    # acceptable here; the server still re-grades every submitted attempt, so the
    # stored score never depends on anything the browser claims.
    return _dictation_detail(item)


def record_dictation_attempt(
    db: Session, user: User, item: DictationItem, submitted_text: str
) -> tuple[DictationAttempt, dictation_grader.GradeResult]:
    """Chấm một câu chép chính tả và ghi lại đủ mọi hệ quả của nó.

    **Đây là đường DUY NHẤT ghi một lượt chép chính tả**, và nó là hàm chứ không
    phải thân một route vì cuộc chạm mặt ở Petland (ADR-012 §2) cũng phải đi qua
    đúng chỗ này. Chép lại vài dòng "chấm rồi ghi" sang tính năng kia sẽ là bộ
    chấm thứ ba của cùng một miền — mà `lib/dictation.ts` đã mang sẵn một cảnh
    báo dài về chuyện hai bản trôi khỏi nhau.

    Không `commit`: người gọi quyết định ranh giới giao dịch.
    """
    # Graded against `transcript`, never against `audio_asset.source_text`.
    result = dictation_grader.grade(item.transcript, submitted_text)

    attempt = DictationAttempt(
        user_id=user.id,
        item_id=item.id,
        # Stored exactly as typed: normalisation belongs to the grader, and the
        # grader will change. Keeping only the normalised form would make it
        # impossible to re-grade an old attempt under new rules.
        submitted_text=submitted_text,
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
                user_id=user.id,
                source_type="dictation_complete",
                source_id=attempt.id,
                amount=progression.xp_for(db, "dictation_complete"),
                timezone=ensure_profile(db, user).timezone,
            )
        except Exception:  # pragma: no cover - XP không được làm hỏng bài nộp
            pass
        _pay_ruby_for_a_finished_story(db, user.id, item)
    return attempt, result


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

    attempt, result = record_dictation_attempt(db, current_user, item, body.submitted_text)
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


def _pay_ruby_for_a_finished_story(db: Session, user_id: uuid.UUID, item: DictationItem) -> None:
    """Ruby cho việc NGHE XONG CẢ BÀI, không cho từng câu (ADR-011 §1).

    XP đã trả cho từng câu rồi. Ruby trả cho việc kết thúc, và đó là toàn bộ lý
    do nó tồn tại như một đơn vị thứ hai: một nguồn ruby trả theo từng lượt nhỏ
    biến nó thành XP thứ hai.

    `source_id` là **story**, nên khoá duy nhất tự lo chuyện chống cày — gõ lại
    câu cuối lần thứ mười không trả thêm lần nào. Câu lẻ (`story_id` NULL) không
    có gì để "xong", nên không có ruby: nó là một câu, không phải một bài.

    Nằm trong `try` vì luật gamification không được với tới bài nộp, đúng luật
    `progression.award` đã đặt: bài nộp và tiến độ dictation phải giữ nguyên dù
    nhánh này hỏng bất cứ đâu.
    """
    if item.story_id is None:
        return
    try:
        siblings = list(
            db.scalars(
                select(DictationItem.id).where(
                    DictationItem.story_id == item.story_id,
                    DictationItem.status == PUBLISHED,
                )
            )
        )
        # Lượt vừa nộp đã `flush` nên nó nằm trong truy vấn này — cùng giao dịch,
        # chưa commit. Đọc sau commit thì câu cuối cùng của một bài không bao giờ
        # tính, và bài đó không bao giờ trả ruby.
        if siblings and _completed_items(db, user_id, siblings) >= set(siblings):
            ruby.earn(
                db,
                user_id=user_id,
                source_type="story_complete",
                source_id=item.story_id,
            )
    except Exception:  # pragma: no cover - lưới an toàn, xem chú thích trên
        pass


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
    # Khách vãng lai xem được cây; đăng nhập chỉ THÊM cột "đã xong mấy câu".
    # Nội dung không phải thứ tài khoản mở khoá — xem `ADR-015`.
    user: User | None = Depends(get_optional_user),
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
        done = _completed_items(db, user.id, item_ids) if user else set()
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
    user: User | None = Depends(get_optional_user),
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
    done = _completed_items(db, user.id, item_ids) if user else set()

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
                transcript_vi=item.transcript_vi,
                completed=item.id in done,
            )
            for item in items
        ],
        progress=StoryProgress(total_items=len(items), completed_items=len(done)),
    )
