import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.media import AUDIO_ACCENTS
from app.models.mixins import PublishableMixin, TimestampMixin, difficulty_check, status_check

PARTS_OF_SPEECH = ("noun", "verb", "adjective", "adverb", "preposition", "phrase")
CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# Which piece of the entry an audio clip renders. Without this the example
# sentence would either collide with the headword on the unique key or need a
# second, near-identical join table (ADR-001 A4.4).
VOCABULARY_AUDIO_KINDS = ("headword", "example")

_ACCENT_LIST = ", ".join(f"'{accent}'" for accent in AUDIO_ACCENTS)


class VocabularyEntry(Base, PublishableMixin):
    __tablename__ = "vocabulary_entry"
    __table_args__ = (
        # "book" the noun and "book" the verb are different entries; a unique
        # constraint on headword alone would let only one of them exist.
        UniqueConstraint("headword", "part_of_speech", name="uq_vocabulary_entry_headword_pos"),
        CheckConstraint(
            "part_of_speech IN ('noun', 'verb', 'adjective', 'adverb', 'preposition', 'phrase')",
            name="ck_vocabulary_entry_part_of_speech",
        ),
        CheckConstraint(
            "cefr_level IS NULL OR cefr_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')",
            name="ck_vocabulary_entry_cefr_level",
        ),
        difficulty_check("vocabulary_entry"),
        status_check("vocabulary_entry"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    headword: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    part_of_speech: Mapped[str] = mapped_column(String(16), nullable=False)
    phonetic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meaning_en: Mapped[str] = mapped_column(Text, nullable=False)
    meaning_vi: Mapped[str] = mapped_column(Text, nullable=False)
    example: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    cefr_level: Mapped[str | None] = mapped_column(String(4), nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    audio: Mapped[list["VocabularyAudio"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    topics: Mapped[list["VocabularyTopic"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<VocabularyEntry {self.headword} ({self.part_of_speech})>"


class VocabularyTopic(Base):
    """Many-to-many: "contract" belongs to both *business* and *legal*."""

    __tablename__ = "vocabulary_topic"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocabulary_entry.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"), primary_key=True
    )

    entry: Mapped["VocabularyEntry"] = relationship(back_populates="topics")


class VocabularyAudio(Base):
    """Pronunciations of one entry, one row per (kind, accent).

    TOEIC uses four accents, so a single FK column on the entry cannot express
    this (PHASE2-AUDIO A6). A fully recorded entry has eight rows: four accents
    for the headword and four for the example sentence.
    """

    __tablename__ = "vocabulary_audio"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('headword', 'example')",
            name="ck_vocabulary_audio_kind",
        ),
        CheckConstraint(f"accent IN ({_ACCENT_LIST})", name="ck_vocabulary_audio_accent"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocabulary_entry.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    accent: Mapped[str] = mapped_column(String(8), primary_key=True)
    # RESTRICT, not CASCADE: dropping an audio asset that content still points at
    # should be a deliberate act, not a side effect of tidying up the store.
    audio_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=False
    )

    entry: Mapped["VocabularyEntry"] = relationship(back_populates="audio")


class VocabularyReviewState(Base, TimestampMixin):
    """Current SM-2 state for one (learner, entry) pair."""

    __tablename__ = "vocabulary_review_state"
    __table_args__ = (
        # 1.30 is SM-2's floor; below it the interval stops growing at all.
        CheckConstraint("ease_factor >= 1.30", name="ck_vocabulary_review_state_ease_factor"),
        CheckConstraint("interval_days >= 0", name="ck_vocabulary_review_state_interval"),
        # The hot path of the whole Learning Hub: every review session opens with
        # "which entries are due for this learner".
        Index("ix_vocabulary_review_state_due", "user_id", "due_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocabulary_entry.id", ondelete="CASCADE"), primary_key=True
    )
    ease_factor: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="2.50"
    )
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Counts forgetting, which is the signal AI Coach needs to name a weakness.
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class VocabularyReviewLog(Base):
    """One row per review, kept because `VocabularyReviewState` is overwritten.

    Without the history there is no way to retune the algorithm and re-evaluate
    it, and no trend for AI Coach to read.
    """

    __tablename__ = "vocabulary_review_log"
    __table_args__ = (
        CheckConstraint("grade BETWEEN 0 AND 5", name="ck_vocabulary_review_log_grade"),
        Index("ix_vocabulary_review_log_user_entry", "user_id", "entry_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocabulary_entry.id", ondelete="CASCADE"), nullable=False
    )
    grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # The interval and ease the algorithm chose *at this review*. Reading them
    # back off the state row would only ever show the latest values.
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    ease_factor: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
