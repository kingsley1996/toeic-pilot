"""Blog public (SPEC-BLOG §4): chỉ bài published, khách đọc được.

Cùng tinh thần ADR-015 như hall-of-fame: nội dung công khai thì Google và
người chưa đăng nhập đọc full text SSR. Draft → 404 (không 403 — không để lộ
sự tồn tại của bài chưa duyệt).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import BlogPost
from app.schemas.blog import BlogPostCard, BlogPostDetail, TocEntry
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, page_of
from app.services.blog_html import doc_text, reading_minutes, toc_from_doc

router = APIRouter(tags=["blog"])


def _card(post: BlogPost) -> BlogPostCard:
    text = doc_text(post.body_json)
    return BlogPostCard(
        slug=post.slug,
        title=post.title,
        excerpt=post.excerpt,
        cover_image_url=post.cover_image_url,
        category=post.category,
        tags=list(post.tags or []),
        author_name=post.author_name,
        published_at=post.published_at,
        reading_minutes=reading_minutes(text),
    )


def _detail(post: BlogPost, db: Session) -> BlogPostDetail:
    card = _card(post)
    related_rows = (
        db.execute(
            select(BlogPost)
            .where(
                BlogPost.status == "published",
                BlogPost.category == post.category,
                BlogPost.id != post.id,
            )
            .order_by(BlogPost.published_at.desc())
            .limit(3)
        )
        .scalars()
        .all()
    )
    return BlogPostDetail(
        **card.model_dump(),
        body_html=post.body_html,
        toc=[
            TocEntry(level=int(entry["level"]), text=str(entry["text"]), id=str(entry["id"]))
            for entry in toc_from_doc(post.body_json)
        ],
        related_part=post.related_part,
        related=[_card(row) for row in related_rows],
    )


@router.get("/blog/posts", response_model=Page[BlogPostCard])
def list_posts(
    category: str | None = Query(default=None, max_length=32),
    tag: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Page[BlogPostCard]:
    """Hub blog: bài published mới nhất trước. Mỗi category có URL riêng để crawl."""
    query = select(BlogPost).where(BlogPost.status == "published")
    if category:
        query = query.where(BlogPost.category == category)
    if q:
        like = f"%{q}%"
        query = query.where(or_(BlogPost.title.ilike(like), BlogPost.excerpt.ilike(like)))
    rows = db.execute(query.order_by(BlogPost.published_at.desc())).scalars().all()
    # ponytail: lọc tag + cắt trang ở Python — blog biên tập đếm bằng chục bài,
    # viết SQL JSONcontains hai dialect (Postgres/SQLite test) tốn hơn được.
    # Vượt vài trăm bài published thì chuyển tag thành bảng nối.
    if tag:
        rows = [row for row in rows if tag in (row.tags or [])]
    total = len(rows)
    return page_of([_card(row) for row in rows[offset : offset + limit]], total, limit, offset)


@router.get("/blog/posts/{slug}", response_model=BlogPostDetail)
def read_post(slug: str, db: Session = Depends(get_db)) -> BlogPostDetail:
    post = db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.status == "published")
    ).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết.")
    return _detail(post, db)
