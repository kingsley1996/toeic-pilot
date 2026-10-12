"""Quản trị blog (SPEC-BLOG §3): CRUD + cổng publish.

Soạn (editor) – duyệt (admin) tách như grammar: tạo/sửa editor làm được,
publish/unpublish chỉ admin. Slug khóa sau publish để không gãy URL đã crawl.
`body_json` và `body_html` luôn đi cùng nhau — nhận lẻ một trong hai là 422,
hai cột không bao giờ lệch.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.routes._admin_content import _apply
from app.api.routes.blog import _detail
from app.core.database import get_db
from app.models import BlogPost, User
from app.schemas.blog import BlogPostAdmin, BlogPostCreate, BlogPostUpdate
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, page_of
from app.services.blog_html import doc_text, sanitize_body_html

router = APIRouter(prefix="/admin", tags=["admin-blog"])

can_edit = require_role("editor", "admin")
can_publish = require_role("admin")

# Cổng publish: liệt kê từng lỗi (giống cổng publish đề thi — không "lỗi chung
# chung"). DB đã chặn title/excerpt/category/slug, nên thực tế chỉ còn độ dài
# body là thứ người viết có thể thiếu lúc bấm Publish.
MIN_BODY_CHARS = 300


def _publish_errors(post: BlogPost) -> list[str]:
    errors: list[str] = []
    if len(doc_text(post.body_json)) < MIN_BODY_CHARS:
        errors.append(f"thân bài cần ≥{MIN_BODY_CHARS} ký tự (hiện tại thiếu)")
    return errors


def _to_admin(post: BlogPost, db: Session) -> BlogPostAdmin:
    detail = _detail(post, db)
    return BlogPostAdmin(
        **detail.model_dump(),
        body_json=post.body_json,
        id=post.id,
        status=post.status,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.get("/blog/posts", response_model=Page[BlogPostAdmin])
def list_all(
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> Page[BlogPostAdmin]:
    query = select(BlogPost)
    if status:
        query = query.where(BlogPost.status == status)
    query = query.order_by(BlogPost.updated_at.desc()).offset(offset).limit(limit)
    rows = db.execute(query).scalars().all()
    count_query = select(func.count()).select_from(BlogPost)
    if status:
        count_query = count_query.where(BlogPost.status == status)
    total = db.execute(count_query).scalar_one()
    return page_of([_to_admin(row, db) for row in rows], total, limit, offset)


@router.get("/blog/posts/{post_id}", response_model=BlogPostAdmin)
def read_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> BlogPostAdmin:
    """Một bài (cả draft) để mở editor soạn tiếp."""
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    return _to_admin(post, db)


@router.delete("/blog/posts/{post_id}", status_code=204)
def delete_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> None:
    """Xóa hẳn (không có gì tham chiếu tới bài — khác lesson gắn câu)."""
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    db.delete(post)
    db.commit()


@router.post("/blog/posts", response_model=BlogPostAdmin, status_code=201)
def create_post(
    body: BlogPostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit),
) -> BlogPostAdmin:
    post = BlogPost(
        slug=body.slug,
        title=body.title,
        excerpt=body.excerpt,
        body_json=body.body_json,
        body_html=sanitize_body_html(body.body_html),
        cover_image_url=body.cover_image_url,
        category=body.category,
        tags=body.tags,
        author_name=body.author_name,
        related_part=body.related_part,
        status="draft",
        created_by=user.id,
    )
    db.add(post)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug đã tồn tại.") from None
    db.refresh(post)
    return _to_admin(post, db)


@router.patch("/blog/posts/{post_id}", response_model=BlogPostAdmin)
def update_post(
    post_id: uuid.UUID,
    body: BlogPostUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> BlogPostAdmin:
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    data = body.model_dump(exclude_unset=True)
    if data.get("slug") is not None and data["slug"] != post.slug and post.status == "published":
        raise HTTPException(status_code=422, detail="Slug bất biến sau publish (giữ URL đã crawl).")
    if ("body_json" in data) != ("body_html" in data):
        raise HTTPException(status_code=422, detail="body_json và body_html phải gửi cùng nhau.")
    _apply(
        post,
        body,
        (
            "slug",
            "title",
            "excerpt",
            "body_json",
            "cover_image_url",
            "category",
            "tags",
            "author_name",
            "related_part",
        ),
    )
    if "body_html" in data:
        post.body_html = sanitize_body_html(data["body_html"])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug đã tồn tại.") from None
    db.refresh(post)
    return _to_admin(post, db)


@router.post("/blog/posts/{post_id}/publish", response_model=BlogPostAdmin)
def publish_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(can_publish),
) -> BlogPostAdmin:
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    errors = _publish_errors(post)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    post.status = "published"
    post.published_by = user.id
    if post.published_at is None:
        post.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(post)
    return _to_admin(post, db)


@router.post("/blog/posts/{post_id}/unpublish", response_model=BlogPostAdmin)
def unpublish_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(can_publish),
) -> BlogPostAdmin:
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    post.status = "draft"
    db.commit()
    db.refresh(post)
    return _to_admin(post, db)
