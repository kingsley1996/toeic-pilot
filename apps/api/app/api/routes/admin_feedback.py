"""Xử lý góp ý — xem, duyệt (trao ruby), từ chối.

`require_role("admin")` chứ không `editor`: duyệt một góp ý là trao ruby, tức
là chạm vào nền kinh tế, cùng lý do với `/admin/ruby`. Biên tập viên sửa nội
dung; phát thưởng là quyền vận hành.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.routes.feedback import public
from app.core.database import get_db
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.common import Page, page_of
from app.schemas.feedback import (
    FeedbackNoteBody,
    FeedbackPublic,
    FeedbackRejectBody,
    FeedbackStatus,
)
from app.services.ruby import earn

router = APIRouter(prefix="/admin/feedback", tags=["admin"])

can_review = require_role("admin")


def _load(db: Session, feedback_id: uuid.UUID) -> Feedback:
    feedback = db.get(Feedback, feedback_id)
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không thấy góp ý")
    return feedback


@router.get("", response_model=Page[FeedbackPublic])
def list_feedback(
    status_filter: FeedbackStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_review),
) -> Page[FeedbackPublic]:
    """Danh sách góp ý. `Page[T]` vì nó lớn theo lượng người dùng — nhóm (C)."""
    where = [Feedback.status == status_filter] if status_filter else []
    total = db.execute(select(func.count()).select_from(Feedback).where(*where)).scalar_one()
    rows = db.execute(
        select(Feedback)
        .where(*where)
        # `id` làm khoá phụ: `created_at` không phải thứ tự TOÀN PHẦN — hai góp
        # ý gửi trong cùng một tick sẽ đổi chỗ giữa hai truy vấn, và với
        # LIMIT/OFFSET thì một hàng hiện ở hai trang còn một hàng biến mất.
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars()
    return page_of([public(row) for row in rows], total, limit, offset)


@router.post("/{feedback_id}/approve", response_model=FeedbackPublic)
def approve(
    feedback_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(can_review),
) -> FeedbackPublic:
    """Duyệt và trao ruby, trong CÙNG một transaction.

    409 khi đã duyệt, chứ không lặng lẽ trả về như cũ: `earn()` đã idempotent
    nhờ `uq_ruby_event_source`, nên bấm hai lần không trao hai lần — nhưng một
    200 im lặng khiến người bấm tưởng lần thứ hai vừa làm được việc gì đó.
    """
    feedback = _load(db, feedback_id)
    if feedback.status == "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Góp ý đã được duyệt")

    feedback.status = "approved"
    feedback.reviewed_by = current_user.id
    feedback.reviewed_at = datetime.now(UTC)
    # Mức thưởng đọc từ `ruby_rule`, không truyền `amount`: admin sửa được ở
    # `/admin/ruby` mà không cần deploy, và tắt hàng đó là tắt luôn phần thưởng.
    earn(db, user_id=feedback.user_id, source_type="feedback_reward", source_id=feedback.id)
    db.commit()
    db.refresh(feedback)
    return public(feedback)


@router.post("/{feedback_id}/reject", response_model=FeedbackPublic)
def reject(
    feedback_id: uuid.UUID,
    body: FeedbackRejectBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(can_review),
) -> FeedbackPublic:
    """Từ chối. KHÔNG rút ruby nếu trước đó đã duyệt — sổ cái bất biến.

    Đó là tính chất của `ruby_event` chứ không phải sơ suất ở đây: một hàng đã
    ghi thì không bị xoá, cùng lý do `xp_event` không bao giờ bị trừ ngược.
    """
    feedback = _load(db, feedback_id)
    if feedback.status == "rejected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Góp ý đã bị từ chối")

    feedback.status = "rejected"
    feedback.admin_note = body.admin_note
    feedback.reviewed_by = current_user.id
    feedback.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(feedback)
    return public(feedback)


@router.patch("/{feedback_id}", response_model=FeedbackPublic)
def edit_note(
    feedback_id: uuid.UUID,
    body: FeedbackNoteBody,
    db: Session = Depends(get_db),
    _: User = Depends(can_review),
) -> FeedbackPublic:
    """Sửa ghi chú. Vắng khoá `admin_note` là GIỮ NGUYÊN, `null` là XOÁ.

    Cùng luật với `PATCH /profile`: một phép gộp `body.admin_note or existing`
    không phân biệt được hai chuyện đó, và hệ quả là xoá ghi chú trả về 200 mà
    không xoá gì.
    """
    feedback = _load(db, feedback_id)
    if "admin_note" in body.model_dump(exclude_unset=True):
        feedback.admin_note = body.admin_note
    db.commit()
    db.refresh(feedback)
    return public(feedback)
