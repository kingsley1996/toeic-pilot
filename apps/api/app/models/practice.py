"""TOEIC Practice: questions, tests, and what a learner did with them.

The shape here follows the exam rather than any tidier abstraction, because the
exam is what has to be rendered. Two facts drive almost every decision in this
module (ADR-001 A2):

  * Parts 3, 4, 6 and 7 hang several questions off one shared stimulus — an
    audio conversation, a talk, a passage. Parts 1, 2 and 5 do not.
  * Part 2 has three options and prints neither the prompt nor the options; the
    learner only hears them. Every other part has four printed options.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import PublishableMixin, difficulty_check, status_check

# Parts whose questions hang off a shared stimulus. Listed here rather than
# inlined so the CHECK constraint and any future validator cannot disagree.
GROUPED_PARTS = (3, 4, 6, 7)

LISTENING_PARTS = (1, 2, 3, 4)
READING_PARTS = (5, 6, 7)

QUESTION_SOURCES = ("original", "generated", "licensed")
TEST_KINDS = ("full", "mini")
ATTEMPT_MODES = ("full_test", "part_practice")

# Parts whose options exist only in the audio. ETS prints neither the four
# statements of part 1 nor the three responses of part 2; part 1's test book
# shows the photograph alone. So `prompt_text` and `question_option.content` are
# NULL for both — the correct value, not missing data.
UNPRINTED_PARTS = (1, 2)

# Part 2 is the one part with three options rather than four.
PART_2_OPTION_COUNT = 3
DEFAULT_OPTION_COUNT = 4


class QuestionSet(Base, PublishableMixin):
    """A stimulus shared by several questions (parts 3, 4, 6, 7)."""

    __tablename__ = "question_set"
    __table_args__ = (
        CheckConstraint("part BETWEEN 1 AND 7", name="ck_question_set_part"),
        status_check("question_set"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    # Parts 3 and 4: one recording, several questions. Parts 1 and 2 put their
    # audio on the question instead, because there it really is one per question.
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=True
    )
    # Parts 6 and 7. Three separate columns rather than an array because part 7
    # tops out at three passages and their order carries meaning — an email, its
    # reply, then a schedule. An array loses that; a child table adds a join for
    # a limit that is hard-coded at three anyway.
    passage: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="question_set", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QuestionSet part={self.part} {self.title or self.id}>"


class Question(Base, PublishableMixin):
    __tablename__ = "question"
    __table_args__ = (
        CheckConstraint("part BETWEEN 1 AND 7", name="ck_question_part"),
        # Parts 3, 4, 6 and 7 are meaningless without their stimulus. Enforcing it
        # here catches malformed content when it is seeded, rather than when a
        # learner opens a conversation question with no conversation attached.
        CheckConstraint(
            "part NOT IN (3, 4, 6, 7) OR set_id IS NOT NULL",
            name="ck_question_set_required",
        ),
        CheckConstraint(
            "source IN ('original', 'generated', 'licensed')",
            name="ck_question_source",
        ),
        difficulty_check("question"),
        status_check("question"),
        Index("ix_question_part_status", "part", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_set.id", ondelete="CASCADE"), nullable=True, index=True
    )
    position: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # NULL for part 2, where nothing is printed. That is the correct value, not
    # missing data.
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Parts 1 and 2 only; parts 3 and 4 carry their audio on the set.
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=True
    )
    # Part 1 photographs (ADR-004). An FK rather than a URL string: a bare URL
    # has nowhere to record the licence and attribution that CC-BY requires, and
    # it invites hotlinking someone else's server.
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_asset.id", ondelete="RESTRICT"), nullable=True
    )
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    # What the question tests ("inference", "verb-tense"). This is the raw
    # material for telling a learner *what* they are weak at rather than only
    # which part they score badly on.
    skill_tag: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # NOT NULL on purpose. Real TOEIC material is ETS copyright, and that is a
    # legal exposure rather than a technical one. Requiring provenance forces the
    # question to be answered while someone still knows the answer; backfilling
    # it later means auditing thousands of rows nobody remembers adding.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    question_set: Mapped["QuestionSet | None"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    @property
    def is_listening(self) -> bool:
        return self.part in LISTENING_PARTS

    def __repr__(self) -> str:
        return f"<Question part={self.part} {self.id}>"


class QuestionOption(Base):
    __tablename__ = "question_option"
    __table_args__ = (
        UniqueConstraint("question_id", "label", name="uq_question_option_label"),
        CheckConstraint("label IN ('A', 'B', 'C', 'D')", name="ck_question_option_label"),
        # At most one correct answer. "At least one" cannot be expressed as a
        # declarative constraint on this table — see ADR-001 B4; it is checked
        # when content is seeded and has its own test.
        Index(
            "uq_question_option_single_correct",
            "question_id",
            unique=True,
            postgresql_where=text("is_correct"),
            sqlite_where=text("is_correct"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(1), nullable=False)
    # NULL for part 2: the options exist only in the audio.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")

    def __repr__(self) -> str:
        return f"<QuestionOption {self.label}{'*' if self.is_correct else ''}>"


class PracticeTest(Base, PublishableMixin):
    __tablename__ = "practice_test"
    __table_args__ = (
        CheckConstraint("kind IN ('full', 'mini')", name="ck_practice_test_kind"),
        status_check("practice_test"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="full")
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Which raw-to-scaled curve this form uses. Real TOEIC forms differ, so the
    # scale belongs to the test rather than to the application.
    score_scale_slug: Mapped[str] = mapped_column(
        ForeignKey("score_scale.slug", ondelete="RESTRICT"),
        nullable=False,
        server_default="default",
    )

    def __repr__(self) -> str:
        return f"<PracticeTest {self.slug}>"


class PracticeTestQuestion(Base):
    """Ordering of questions within a test.

    A join table rather than an FK on `question`, for two reasons: a good
    question should be reusable across tests, and "Practice by Part" draws
    questions that belong to no test at all.
    """

    __tablename__ = "practice_test_question"
    __table_args__ = (
        UniqueConstraint("test_id", "position", name="uq_practice_test_question_position"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_test.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Attempt(Base):
    """One sitting: a full mock test, or an ad-hoc run of questions from one part."""

    __tablename__ = "attempt"
    __table_args__ = (
        CheckConstraint("mode IN ('full_test', 'part_practice')", name="ck_attempt_mode"),
        # The two modes carry different fields, and neither should borrow the
        # other's. Practice by part is not a test and must not invent a row in
        # `practice_test` just to have something to point at.
        CheckConstraint(
            "(mode = 'full_test' AND test_id IS NOT NULL AND part IS NULL)"
            " OR (mode = 'part_practice' AND part IS NOT NULL AND test_id IS NULL)",
            name="ck_attempt_mode_fields",
        ),
        CheckConstraint("part IS NULL OR part BETWEEN 1 AND 7", name="ck_attempt_part"),
        Index("ix_attempt_user_started", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    test_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_test.id", ondelete="RESTRICT"), nullable=True
    )
    part: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    listening_raw: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reading_raw: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Stored, never recomputed on read. TOEIC conversion tables differ per form
    # and will be corrected over time; deriving the scaled score at display time
    # would silently rewrite a learner's past results every time we touch the
    # table, and their progress chart would move on its own.
    listening_scaled: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reading_scaled: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    total_scaled: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    items: Mapped[list["AttemptItem"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )
    test: Mapped["PracticeTest | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Attempt {self.mode} user={self.user_id}>"


class AttemptItem(Base):
    """A question as served to a learner, plus what they did with it.

    One table for both, because an unanswered question is data. Fifteen blanks at
    the end of part 7 means the learner ran out of time — one of the strongest
    signals the study planner has. Splitting "served" from "answered" would turn
    that signal into the absence of a row.
    """

    __tablename__ = "attempt_item"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_item_question"),
        UniqueConstraint("attempt_id", "position", name="uq_attempt_item_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # NULL means left blank — see the class docstring.
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_option.id", ondelete="RESTRICT"), nullable=True
    )
    # Derivable from the selected option, but stored anyway: content can be
    # corrected after a learner has sat the test, and a past result must keep the
    # verdict it had at the time. Same reasoning as the scaled scores above.
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt: Mapped["Attempt"] = relationship(back_populates="items")
