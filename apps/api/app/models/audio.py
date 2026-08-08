import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.media import AUDIO_ACCENTS, AUDIO_SOURCES

__all__ = ["AUDIO_ACCENTS", "AUDIO_SOURCES", "AudioAsset"]


class AudioAsset(Base):
    """One synthesised or sourced audio file, addressed by the hash of its input.

    Deliberately independent of the domain schema: the dependency runs
    domain -> asset, so `vocabulary`, `dictation_item` and the listening tables
    point here rather than the other way round.
    """

    __tablename__ = "audio_asset"
    __table_args__ = (
        CheckConstraint(
            "source IN ('tts', 'scraped', 'uploaded')",
            name="ck_audio_asset_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    # Hash of the synthesis INPUT (text | logical voice | engine | engine version),
    # never of the mp3 bytes — TTS output is not byte-stable, so hashing bytes
    # would break the "already generated, skip it" check and the seed upsert.
    source_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="audio/mpeg")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[str] = mapped_column(String(16), nullable=False, default="tts")
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # LOGICAL voice ("us_female_1"), not the provider's id ("en-US-JennyNeural").
    # Provider ids here would tie every stored hash to one vendor.
    voice: Mapped[str] = mapped_column(String(32), nullable=False)
    accent: Mapped[str] = mapped_column(String(8), nullable=False)

    # WARNING: this is the text that was fed to TTS, kept so an asset can be
    # re-derived and re-hashed. It is NOT the answer key for grading. Dictation
    # grades against `dictation_item.transcript`; treating this column as the
    # source of truth would leave two copies free to drift apart.
    source_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Text fed to TTS, for re-derivation only. NOT the grading answer key — "
            "dictation grades against dictation_item.transcript."
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AudioAsset {self.voice} {self.storage_key}>"
