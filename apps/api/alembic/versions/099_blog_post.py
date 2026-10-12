"""Blog editorial v1 (SPEC-BLOG): một bảng `blog_post`.

Revision ID: 099_blog_post
Revises: 098_dungeon_tower
Create Date: 2026-10-12 00:00:00.000000

`body_json` JSONB (tài liệu Tiptap) + `body_html` TEXT (render sẵn để SSR).
`tags` JSONB list — không TEXT[] + GIN: array Postgres làm SQLite của bộ test
vỡ, mà tag chỉ để filter hub (`@>` thay bằng contains ở Python/SQL JSON).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "099_blog_post"
down_revision: str | None = "098_dungeon_tower"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "blog_post",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("excerpt", sa.String(160), nullable=False),
        sa.Column("body_json", postgresql.JSONB(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("author_name", sa.String(64), nullable=False, server_default="ToeicPilot"),
        sa.Column("related_part", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="ck_blog_post_status"
        ),
        sa.CheckConstraint(
            "category IN ('meo-lam-bai', 'ngu-phap', 'tu-vung', 'kinh-nghiem', 'thong-bao')",
            name="ck_blog_post_category",
        ),
    )
    op.create_index("ix_blog_post_status_published", "blog_post", ["status", "published_at"])


def downgrade() -> None:
    op.drop_index("ix_blog_post_status_published", table_name="blog_post")
    op.drop_table("blog_post")
