"""Quản trị thư viện Listening Lab: liệt kê, sửa, xuất bản/gỡ, xoá bài public.

Nguyên tắc riêng tư: list CHỈ thấy bài public — bài riêng của user khác không
bao giờ lọt vào đây. Ngoại lệ duy nhất là admin publish bài của chính mình:
UI admin tạo từ learner endpoint (private) rồi PATCH ở đây thành public.
Thêm bài mới không cần endpoint riêng nên khỏi đẻ đường ghi thứ hai.

Vai trò theo `admin_dictation.py`: xem/sửa nháp là editor+, riêng phát hành và
xoá là admin — không ai tự duyệt bài của mình.
"""

import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_role
from app.core.database import get_db
from app.core.storage import StorageError, get_driver
from app.models import (
    ListeningAttempt,
    ListeningContent,
    ListeningSegment,
    User,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.schemas.listening import (
    ListeningContentAdmin,
    ListeningContentUpdate,
    ListeningVisibilityUpdate,
)
from app.services import dictation as dictation_grader
from app.services.listening_transcript import is_speakable

router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger(__name__)

can_edit = require_role("editor", "admin")
can_publish = require_role("admin")


def _admin_row(
    content: ListeningContent,
    segment_count: int,
    attempt_count: int,
    owner_email: str,
) -> ListeningContentAdmin:
    return ListeningContentAdmin(
        id=str(content.id),
        title=content.title,
        source_type=content.source_type,
        source_url=content.source_url,
        external_id=content.external_id,
        segment_count=segment_count,
        attempt_count=attempt_count,
        owner_email=owner_email,
        is_public=content.is_public,
        created_at=content.created_at,
    )


def _get_public_content(db: Session, content_id: uuid.UUID) -> ListeningContent:
    """Bài public theo id. Bài riêng (kể cả tồn tại) thì 404 như không có —
    admin không có đường nào chạm vào bài của user qua module này."""
    content = db.scalars(
        select(ListeningContent)
        .where(ListeningContent.id == content_id, ListeningContent.is_public.is_(True))
        .options(selectinload(ListeningContent.segments))
    ).first()
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content


@router.get("/listening/contents", response_model=Page[ListeningContentAdmin])
def list_listening_admin(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    # Mặc định thư viện public; `is_public=false` trả bài RIÊNG của chính mình
    # (bài đã gỡ + nháp) để xuất bản lại — bài riêng của người khác không bao
    # giờ lọt vào dù ở chế độ nào.
    is_public: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(can_edit),
) -> Page[ListeningContentAdmin]:
    if is_public:
        base = select(ListeningContent).where(ListeningContent.is_public.is_(True))
    else:
        base = select(ListeningContent).where(
            ListeningContent.user_id == user.id, ListeningContent.is_public.is_(False)
        )
    page_items = list(
        db.scalars(
            base.options(selectinload(ListeningContent.segments))
            .order_by(ListeningContent.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    ids = [c.id for c in page_items]
    seg_counts: dict[uuid.UUID, int] = {}
    for content_id, total in (
        db.execute(
            select(ListeningSegment.content_id, func.count())
            .where(ListeningSegment.content_id.in_(ids))
            .group_by(ListeningSegment.content_id)
        ).all()
        if ids
        else []
    ):
        seg_counts[content_id] = total
    att_counts: dict[uuid.UUID, int] = {}
    for content_id, total in (
        db.execute(
            select(ListeningSegment.content_id, func.count(ListeningAttempt.id))
            .join(ListeningAttempt, ListeningAttempt.segment_id == ListeningSegment.id)
            .where(ListeningSegment.content_id.in_(ids))
            .group_by(ListeningSegment.content_id)
        ).all()
        if ids
        else []
    ):
        att_counts[content_id] = total
    owners = {
        user.id: user.email
        for user in db.scalars(
            select(User).where(User.id.in_([c.user_id for c in page_items]))
        ).all()
    }
    return page_of(
        [
            _admin_row(
                content,
                seg_counts.get(content.id, 0),
                att_counts.get(content.id, 0),
                owners.get(content.user_id, "?"),
            )
            for content in page_items
        ],
        count_rows(db, base),
        limit,
        offset,
    )


@router.patch("/listening/contents/{content_id}", response_model=ListeningContentAdmin)
def set_listening_visibility(
    content_id: uuid.UUID,
    body: ListeningVisibilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(can_publish),
) -> ListeningContentAdmin:
    content = db.get(ListeningContent, content_id)
    # Bài riêng của user khác không tồn tại đối với admin — chỉ bài public hoặc
    # bài của chính admin mới vào được endpoint này. Public-hoá bài người khác
    # thì 422 có mã riêng chứ không 404: admin CẦN biết mình vừa bấm nhầm cái
    # gì. Ngoại lệ cho chính chủ để admin tạo từ learner endpoint rồi publish.
    if content is None or (not content.is_public and not body.is_public):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if body.is_public and not content.is_public and content.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "CANNOT_PUBLISH_PRIVATE"},
        )
    content.is_public = body.is_public
    db.commit()
    db.refresh(content)
    owner = db.get(User, content.user_id)
    seg_count = len(content.segments)
    att_count = (
        db.query(ListeningAttempt)
        .join(ListeningSegment, ListeningSegment.id == ListeningAttempt.segment_id)
        .where(ListeningSegment.content_id == content.id)
        .count()
    )
    return _admin_row(content, seg_count, att_count, owner.email if owner else "?")


@router.put("/listening/contents/{content_id}", response_model=ListeningContentAdmin)
def update_listening_content(
    content_id: uuid.UUID,
    body: ListeningContentUpdate,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> ListeningContentAdmin:
    """Sửa thủ công bài public: tên + toàn bộ transcript khi lệch video. Chỉ
    admin (sửa nội dung live ảnh hưởng người học, như xoá). `segments` là
    full-replace theo thứ tự list (xem `ListeningSegmentUpdate`). Đã có người
    học thì 409 + ?force=: câu giữ lại thì giữ lịch sử, câu bị xoá thì lịch sử
    của nó đi theo — cùng luật "không mất dữ liệu trong im lặng" với endpoint
    xoá bên dưới."""
    content = _get_public_content(db, content_id)
    if body.title is None and body.segments is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "EMPTY_UPDATE"},
        )
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "EMPTY_TITLE"},
            )
        content.title = title
    if body.segments is not None:
        if not body.segments:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_SEGMENT", "errors": ["Transcript is empty"]},
            )
        by_id = {seg.id: seg for seg in content.segments}
        for upd in body.segments:
            if upd.id is not None and upd.id not in by_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
                )
        if not force:
            has_attempts = (
                db.query(ListeningAttempt)
                .join(ListeningSegment, ListeningSegment.id == ListeningAttempt.segment_id)
                .where(ListeningSegment.content_id == content.id)
                .first()
                is not None
            )
            if has_attempts:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "HAS_ATTEMPTS"},
                )
        # Validate trên giá trị cuối theo cùng luật `validate_transcript`: text
        # rỗng/không lời, start âm, end<=start, thứ tự. Overlap chỉ warning ở
        # creation nên ở đây cho qua.
        preview: list[tuple[float, float, str]] = []
        for position, upd in enumerate(body.segments, start=1):
            if upd.id is None:
                if upd.text is None or upd.start is None or upd.end is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "INVALID_SEGMENT",
                            "errors": [f"Segment {position} needs text/start/end"],
                        },
                    )
                preview.append((float(upd.start), float(upd.end), upd.text.strip()))
            else:
                seg = by_id[upd.id]
                text = upd.text.strip() if upd.text is not None else seg.text
                start = float(upd.start) if upd.start is not None else float(seg.start_seconds)
                end = float(upd.end) if upd.end is not None else float(seg.end_seconds)
                preview.append((start, end, text))
        errors = []
        for i, (start, end, text) in enumerate(preview, start=1):
            if not text.strip():
                errors.append(f"Segment {i} has empty text")
            elif not is_speakable(text):
                errors.append(f"Segment {i} has no speakable lines")
            if start < 0:
                errors.append(f"Segment {i} has negative start")
            if end <= start:
                errors.append(f"Segment {i} has end <= start")
        for i in range(2, len(preview) + 1):
            if preview[i - 1][0] < preview[i - 2][0]:
                errors.append(f"Segment {i} starts before segment {i - 1}")
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_SEGMENT", "errors": errors},
            )
        keep_ids = {upd.id for upd in body.segments if upd.id is not None}
        for seg in content.segments:
            if seg.id not in keep_ids:
                for attempt in db.scalars(
                    select(ListeningAttempt).where(ListeningAttempt.segment_id == seg.id)
                ).all():
                    db.delete(attempt)
                db.delete(seg)
        for index, upd in enumerate(body.segments):
            if upd.id is None:
                assert upd.text is not None and upd.start is not None and upd.end is not None
                text = upd.text.strip()
                db.add(
                    ListeningSegment(
                        content_id=content.id,
                        segment_index=index,
                        start_seconds=Decimal(str(upd.start)),
                        end_seconds=Decimal(str(upd.end)),
                        text=text,
                        text_vi=upd.text_vi.strip() or None if upd.text_vi is not None else None,
                        normalized_text=" ".join(dictation_grader.normalise(text)),
                    )
                )
            else:
                seg = by_id[upd.id]
                seg.segment_index = index
                if upd.text is not None:
                    seg.text = upd.text.strip()
                    seg.normalized_text = " ".join(dictation_grader.normalise(seg.text))
                # Vắng là giữ bản dịch cũ; rỗng là xoá — cùng quy ước dictation.
                if upd.text_vi is not None:
                    seg.text_vi = upd.text_vi.strip() or None
                if upd.start is not None:
                    seg.start_seconds = Decimal(str(upd.start))
                if upd.end is not None:
                    seg.end_seconds = Decimal(str(upd.end))
    db.commit()
    db.refresh(content)
    owner = db.get(User, content.user_id)
    att_count = (
        db.query(ListeningAttempt)
        .join(ListeningSegment, ListeningSegment.id == ListeningAttempt.segment_id)
        .where(ListeningSegment.content_id == content.id)
        .count()
    )
    return _admin_row(content, len(content.segments), att_count, owner.email if owner else "?")


@router.delete("/listening/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listening_content(
    content_id: uuid.UUID,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> None:
    content = _get_public_content(db, content_id)
    if not force:
        has_attempts = (
            db.query(ListeningAttempt)
            .join(ListeningSegment, ListeningSegment.id == ListeningAttempt.segment_id)
            .where(ListeningSegment.content_id == content.id)
            .first()
            is not None
        )
        # Xoá lịch sử học của người ta trong im lặng là mất dữ liệu — chặn như
        # endpoint xoá dictation (409 + ?force=). Muốn dọn mà giữ lịch sử thì
        # gỡ public (PATCH false) thay vì xoá.
        if has_attempts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "HAS_ATTEMPTS"},
            )
    media_key = content.media_storage_key
    db.delete(content)
    db.commit()
    # File tự host đi theo bài, không để lại mồ côi tính tiền kho. Xoá DB trước
    # rồi dọn file sau: kho hỏng thì log chứ không 500 một bài đã xoá xong.
    if media_key:
        try:
            get_driver("video").delete(media_key)
        except StorageError:
            logger.warning("không xoá được file %s của bài %s", media_key, content_id)
