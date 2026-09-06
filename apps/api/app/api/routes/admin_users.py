"""Quản trị THÀNH VIÊN — `admin_users.py`.

Sức khoẻ người dùng của ứng dụng: ai đăng ký mới, tài khoản nào đang hoạt
động, tăng trưởng theo ngày, và vòng đời của một tài khoản (tạo, đổi quyền,
cấp ruby, xoá). `require_role("admin")` cho MỌI endpoint ở đây — đọc danh
sách email của người dùng không phải quyền biên tập nội dung, và đổi quyền
hay xoá tài khoản càng không.

Cấp ruby đi qua `services/ruby.earn` chứ không `UPDATE` số dư: số dư không
phải một cột để sửa, nó là `SUM` của sổ cái, và một khoản không có hàng sổ
cái là khoản không trả lời được "ở đâu ra".
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import Subquery

from app.api.deps import require_role
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models import (
    Attempt,
    DictationAttempt,
    GrammarAttempt,
    GrammarLessonCompletion,
    PartSession,
    PracticeTest,
    RubyEvent,
    User,
)
from app.schemas.admin_users import (
    AdminUserCreate,
    AdminUserEdit,
    AdminUserPublic,
    AdminUserStats,
    GrowthDay,
    RubyGrant,
    UserActivity,
)
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.services.ruby import earn

router = APIRouter(prefix="/admin/users", tags=["admin"])

can_manage = require_role("admin")


def _activity_union(user_ids: list[uuid.UUID] | None = None) -> Subquery:
    """Một cột (user_id, at) gộp mọi đường hoạt động — nguồn duy nhất cho
    `last_activity`, cho "đang hoạt động", và cho feed của một người."""

    def branch(model: Any, column: Any) -> Any:
        query = select(model.user_id, column.label("at")).select_from(model)
        if user_ids is not None:
            query = query.where(model.user_id.in_(user_ids))
        return query

    return union_all(
        branch(Attempt, Attempt.started_at),
        branch(DictationAttempt, DictationAttempt.created_at),
        branch(GrammarAttempt, GrammarAttempt.created_at),
        branch(GrammarLessonCompletion, GrammarLessonCompletion.created_at),
        branch(PartSession, PartSession.created_at),
        branch(RubyEvent, RubyEvent.created_at),
    ).subquery("activity")


def _public(db: Session, user: User) -> AdminUserPublic:
    """Một hàng đầy đủ cho MỘT người — đường trả lời của create/patch/grant.

    Không trả số 0 giả: frontend hiển thị đúng những gì nó nhận, và một
    `ruby_balance: 0` sau khi vừa cấp 2000 là cái nói dối có lịch sử.
    """
    activity = _activity_union([user.id])
    return AdminUserPublic(
        id=str(user.id),
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        ruby_balance=int(
            db.scalar(
                select(func.coalesce(func.sum(RubyEvent.amount), 0)).where(
                    RubyEvent.user_id == user.id
                )
            )
            or 0
        ),
        last_activity=db.scalar(select(func.max(activity.c.at))),
        attempt_count=int(
            db.scalar(select(func.count()).select_from(Attempt).where(Attempt.user_id == user.id))
            or 0
        ),
    )


@router.get("", response_model=Page[AdminUserPublic])
def list_users(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_manage),
) -> Page[AdminUserPublic]:
    """Danh sách kèm số dư ruby và nhịp hoạt động — đủ để quyết định mở ai."""
    query = select(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(User.email.ilike(like), User.role == q.strip()))
    total = count_rows(db, query)
    users = list(db.scalars(query.order_by(User.created_at.desc()).limit(limit).offset(offset)))
    ids = [u.id for u in users]

    balances: dict[uuid.UUID, int] = {
        uid: int(n)
        for uid, n in db.execute(
            select(RubyEvent.user_id, func.coalesce(func.sum(RubyEvent.amount), 0))
            .where(RubyEvent.user_id.in_(ids))
            .group_by(RubyEvent.user_id)
        )
    }
    activity = _activity_union()
    last: dict[uuid.UUID, datetime] = {
        uid: at
        for uid, at in db.execute(
            select(activity.c.user_id, func.max(activity.c.at))
            .where(activity.c.user_id.in_(ids))
            .group_by(activity.c.user_id)
        )
    }
    attempts: dict[uuid.UUID, int] = {
        uid: int(n)
        for uid, n in db.execute(
            select(Attempt.user_id, func.count())
            .where(Attempt.user_id.in_(ids))
            .group_by(Attempt.user_id)
        )
    }
    items = [
        AdminUserPublic(
            id=str(u.id),
            email=u.email,
            role=u.role,
            created_at=u.created_at,
            ruby_balance=int(balances.get(u.id, 0)),
            last_activity=last.get(u.id),
            attempt_count=int(attempts.get(u.id, 0)),
        )
        for u in users
    ]
    return page_of(items, total, limit, offset)


@router.get("/stats", response_model=AdminUserStats)
def stats(db: Session = Depends(get_db), _: User = Depends(can_manage)) -> AdminUserStats:
    """Tăng trưởng 30 ngày + số đang hoạt động — các con số đầu trang.

    # ponytail: `active_7d` quét union 6 bảng mỗi lần mở trang — Postgres đẩy
    # điều kiện ngày xuống được nên hiện tại rẻ; nếu prod chậm thì chuyển sang
    # bảng tóm tắt hoặc giới hạn theo `user_ids` của trang đang xem.
    """
    now = datetime.now(UTC)
    since = now - timedelta(days=30)
    # Gom theo Python, không `date_trunc`: hàng là số NGƯỜI (vài nghìn), và
    # `date_trunc` không tồn tại trên SQLite của bộ test — một cột ngày không
    # đáng một nhánh đặc cách theo hiệu thuốc.
    growth_rows: dict[str, int] = {}
    for created in db.scalars(select(User.created_at).where(User.created_at >= since)):
        # SQLite trả naive (giá trị là UTC); Postgres trả aware.
        day_key = (
            (created.replace(tzinfo=UTC) if created.tzinfo is None else created).date().isoformat()
        )
        growth_rows[day_key] = growth_rows.get(day_key, 0) + 1
    growth = [
        GrowthDay(
            day=(since + timedelta(days=i)).date().isoformat(),
            count=growth_rows.get((since + timedelta(days=i)).date().isoformat(), 0),
        )
        for i in range(31)
    ]
    activity = _activity_union()
    active = db.scalar(
        select(func.count(func.distinct(activity.c.user_id))).where(
            activity.c.at >= now - timedelta(days=7)
        )
    )
    return AdminUserStats(
        total=int(db.scalar(select(func.count(User.id))) or 0),
        new_7d=int(
            db.scalar(select(func.count(User.id)).where(User.created_at >= now - timedelta(days=7)))
            or 0
        ),
        new_30d=int(db.scalar(select(func.count(User.id)).where(User.created_at >= since)) or 0),
        active_7d=int(active or 0),
        growth=growth,
    )


@router.post("", response_model=AdminUserPublic, status_code=status.HTTP_201_CREATED)
def create_user(
    body: AdminUserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(can_manage),
) -> AdminUserPublic:
    """Tạo tài khoản hộ người chưa tự đăng ký được (đặt mật khẩu giúp lần đầu).

    Email trùng → 409, cùng thông báo như chính người dùng gặp khi đăng ký.
    """
    if db.scalar(select(User.id).where(User.email == body.email.lower())) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email này đã có tài khoản"
        )
    user = User(
        email=body.email.lower(),
        hashed_password=get_password_hash(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _public(db, user)


def _own_guard(user: User, target: User) -> None:
    """Không tự hạ quyền/xoá chính mình — cửa thoát duy nhất của một admin là
    tài khoản của người khác, và admin đơn độc thì không có ai đó."""
    if user.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Không thể thao tác trên chính mình"
        )


@router.patch("/{user_id}", response_model=AdminUserPublic)
def update_role(
    user_id: uuid.UUID,
    body: AdminUserEdit,
    db: Session = Depends(get_db),
    caller: User = Depends(can_manage),
) -> AdminUserPublic:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _own_guard(caller, target)
    target.role = body.role
    db.commit()
    db.refresh(target)
    return _public(db, target)


@router.post("/{user_id}/ruby", response_model=AdminUserPublic)
def grant_ruby(
    user_id: uuid.UUID,
    body: RubyGrant,
    db: Session = Depends(get_db),
    _: User = Depends(can_manage),
) -> AdminUserPublic:
    """Cấp ruby — một hàng `admin_grant` trong sổ cái, không phải sửa số dư."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    earn(
        db, user_id=target.id, source_type="admin_grant", source_id=uuid.uuid4(), amount=body.amount
    )
    # `earn` cố ý KHÔNG commit (khoản ruby phải sống chết cùng giao dịch của
    # người gọi) — ở đây GIAO DỊCH CHÍNH LÀ LẦN CẤP NÀY, nên commit là việc của
    # route. Quên một dòng: trả 200, sổ cái rolled back, ruby không tới tay ai.
    db.commit()
    return _public(db, target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    caller: User = Depends(can_manage),
) -> None:
    """Xoá tài khoản. Mọi bảng của người đó CASCADE; `question`/nội dung dùng
    chung có FK RESTRICT tới `users` (created_by) — nếu còn thứ gì trỏ về,
    database sẽ từ chối và lỗi nổi lên thay vì để lại nội dung mồ côi."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _own_guard(caller, target)
    db.delete(target)
    try:
        db.commit()
    except IntegrityError:
        # FK RESTRICT (`question.created_by`...): người này còn nội dung gắn
        # với họ. Database từ chối là đúng; việc của route là nói ra lý do
        # thay vì để một IntegrityError thoát ra thành 500 không lời.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Người này còn nội dung do họ tạo — xử lý nội dung trước khi xoá tài khoản.",
        )


@router.get("/{user_id}/activity", response_model=list[UserActivity])
def activity(
    user_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(can_manage),
) -> list[UserActivity]:
    """Feed thao tác gần nhất của một người, mới trước — 'hôm qua bạn ấy làm gì'."""
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    events: list[UserActivity] = []

    def latest(rows: list[tuple[datetime, str, str]]) -> None:
        events.extend(UserActivity(kind=k, label=lab, at=at) for at, k, lab in rows)

    latest(
        [
            (started_at, "attempt", f"Làm đề · {title}")
            for started_at, title in db.execute(
                select(Attempt.started_at, PracticeTest.title)
                .join(PracticeTest, PracticeTest.id == Attempt.test_id)
                .where(Attempt.user_id == user_id)
                .order_by(Attempt.started_at.desc())
                .limit(10)
            ).all()
        ]
    )
    latest(
        [
            (at, "dictation", "Chép chính tả")
            for (at,) in db.execute(
                select(DictationAttempt.created_at)
                .where(DictationAttempt.user_id == user_id)
                .order_by(DictationAttempt.created_at.desc())
                .limit(10)
            ).all()
        ]
    )
    latest(
        [
            (at, "grammar", "Ôn ngữ pháp")
            for (at,) in db.execute(
                select(GrammarAttempt.created_at)
                .where(GrammarAttempt.user_id == user_id)
                .order_by(GrammarAttempt.created_at.desc())
                .limit(10)
            ).all()
        ]
    )
    latest(
        [
            (at, "part", "Luyện theo part")
            for (at,) in db.execute(
                select(PartSession.created_at)
                .where(PartSession.user_id == user_id)
                .order_by(PartSession.created_at.desc())
                .limit(10)
            ).all()
        ]
    )
    latest(
        [
            (at, "ruby", f"{'+' if amount > 0 else ''}{amount} ruby · {source}")
            for amount, source, at in db.execute(
                select(RubyEvent.amount, RubyEvent.source_type, RubyEvent.created_at)
                .where(RubyEvent.user_id == user_id)
                .order_by(RubyEvent.created_at.desc())
                .limit(10)
            ).all()
        ]
    )
    events.sort(key=lambda e: e.at, reverse=True)
    return events[:limit]
