"""Schema blog (SPEC-BLOG): public đọc published, admin CRUD + cổng publish."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

BlogCategory = Literal["meo-lam-bai", "ngu-phap", "tu-vung", "kinh-nghiem", "thong-bao"]

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


def _must_be_doc(value: dict[str, Any]) -> dict[str, Any]:
    from app.services.blog_html import is_tiptap_doc

    if not is_tiptap_doc(value):
        raise ValueError("body_json phải là tài liệu Tiptap (type=doc)")
    return value


def _tag_len(value: list[str]) -> list[str]:
    for tag in value:
        if not 1 <= len(tag) <= 32:
            raise ValueError("mỗi tag 1–32 ký tự")
    return value


class TocEntry(BaseModel):
    level: int
    text: str
    id: str


class BlogPostCard(BaseModel):
    slug: str
    title: str
    excerpt: str
    cover_image_url: str | None
    category: str
    tags: list[str]
    author_name: str
    published_at: datetime | None
    reading_minutes: int


class BlogPostDetail(BlogPostCard):
    body_html: str
    toc: list[TocEntry]
    related_part: int | None
    related: list[BlogPostCard]


class BlogPostAdmin(BlogPostDetail):
    id: UUID
    status: str
    # Gốc Tiptap để mở lại editor soạn tiếp (public không bao giờ thấy field này).
    body_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BlogPostCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64, pattern=SLUG_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    excerpt: str = Field(min_length=10, max_length=160)
    body_json: dict[str, Any]
    body_html: str = Field(min_length=1)
    cover_image_url: str | None = None
    category: BlogCategory
    tags: list[str] = Field(default_factory=list, max_length=10)
    author_name: str = Field(default="ToeicPilot", min_length=1, max_length=64)
    related_part: int | None = Field(default=None, ge=1, le=7)

    @field_validator("body_json")
    @classmethod
    def _check_doc(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _must_be_doc(value)

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str]) -> list[str]:
        return _tag_len(value)


class BlogPostUpdate(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=64, pattern=SLUG_PATTERN)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    excerpt: str | None = Field(default=None, min_length=10, max_length=160)
    body_json: dict[str, Any] | None = None
    body_html: str | None = Field(default=None, min_length=1)
    cover_image_url: str | None = None
    category: BlogCategory | None = None
    tags: list[str] | None = Field(default=None, max_length=10)
    author_name: str | None = Field(default=None, min_length=1, max_length=64)
    related_part: int | None = Field(default=None, ge=1, le=7)

    @field_validator("body_json")
    @classmethod
    def _check_doc(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _must_be_doc(value) if value is not None else None

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str] | None) -> list[str] | None:
        return _tag_len(value) if value is not None else None
