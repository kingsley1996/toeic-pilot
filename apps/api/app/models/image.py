import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# How the image reached us. `sourced` covers the openly-licensed photographs the
# content pipeline downloads; the other two are placeholders for routes that do
# not exist yet and must not be used without revisiting ADR-004 §2.1.
IMAGE_SOURCES = ("sourced", "generated", "uploaded")


class ImageAsset(Base):
    """A photograph used by a question, stored under a content-addressed key.

    A separate table from `audio_asset` rather than a shared `media_asset`: the
    two only look alike. Audio has duration, voice, accent and engine; images
    have dimensions, a licence and an attribution. Merged, more than half the
    columns would always be NULL and every CHECK would have to begin with "if the
    media type is…". See ADR-004 §2.3.
    """

    __tablename__ = "image_asset"
    __table_args__ = (
        CheckConstraint(
            "source IN ('sourced', 'generated', 'uploaded')",
            name="ck_image_asset_source",
        ),
        CheckConstraint("width > 0 AND height > 0", name="ck_image_asset_dimensions"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    # Hash of (source URL | transform version), not of the stored bytes: the
    # pipeline re-encodes before storing and Pillow output is not stable across
    # versions. Same principle as audio — hash the input.
    source_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/jpeg")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[str] = mapped_column(String(16), nullable=False, default="sourced")
    # NOT NULL, all three. Most openly-licensed photographs are CC-BY: free to
    # use *provided* the creator is credited. Missing attribution is a licence
    # violation, not a cosmetic gap — and it can only be recorded honestly at the
    # moment someone adds the image, while the source page is still open.
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    license: Mapped[str] = mapped_column(String(64), nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    # Storing the attribution is not enough on its own: any endpoint that serves
    # this image must return it, and the UI must render it (ADR-004 §4.2).

    # Describes the photograph for screen readers. Deliberately not the answer to
    # the question — a caption that gave away which statement is true would make
    # the item unanswerable for sighted and unsighted learners alike.
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transform_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ImageAsset {self.width}x{self.height} {self.storage_key}>"
