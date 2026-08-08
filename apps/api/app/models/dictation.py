import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.mixins import PublishableMixin, difficulty_check, status_check

# JSONB on PostgreSQL, plain JSON on the SQLite used by the test fixture.
_JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class DictationItem(Base, PublishableMixin):
    __tablename__ = "dictation_item"
    __table_args__ = (
        difficulty_check("dictation_item"),
        status_check("dictation_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audio_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=False
    )
    # THE ANSWER KEY. `audio_asset.source_text` is the string that was fed to TTS
    # and exists only so an asset can be re-derived; the two are usually
    # identical, which is exactly the trap. Editing one does not touch the other,
    # and grading against the wrong one marks a learner down over a comma in a
    # copy nobody meant to grade against.
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topic.id", ondelete="SET NULL"), nullable=True
    )
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    def __repr__(self) -> str:
        return f"<DictationItem {self.transcript[:40]!r}>"


class DictationAttempt(Base):
    __tablename__ = "dictation_attempt"
    __table_args__ = (
        CheckConstraint("accuracy BETWEEN 0 AND 100", name="ck_dictation_attempt_accuracy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dictation_item.id", ondelete="RESTRICT"), nullable=False
    )
    # Stored exactly as typed. Normalisation belongs to the grader, and the
    # grader will change; keeping only the normalised form would make it
    # impossible to ever re-grade an old attempt under new rules.
    submitted_text: Mapped[str] = mapped_column(Text, nullable=False)
    accuracy: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    # Word-level comparison, so the UI can re-render the highlighting without
    # re-running the grader.
    word_diff: Mapped[Any | None] = mapped_column(_JSON_TYPE, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
