"""Shared column vocabulary for the domain tables.

Thirteen tables carrying hand-written `created_at`/`updated_at` pairs and
hand-written status CHECK constraints is thirteen chances to spell one of them
differently. These helpers exist so the schema says the same thing every time.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

# Publication state, not soft delete. The real need is "not visible to learners
# yet" (AI-generated content awaiting review) and "withdrawn without breaking
# history" — a hard delete would orphan the attempt_item rows that reference it.
CONTENT_STATUSES = ("draft", "published", "archived")

# Difficulty is a 1-5 band everywhere it appears.
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


def status_check(table: str) -> CheckConstraint:
    return CheckConstraint(
        "status IN ('draft', 'published', 'archived')",
        name=f"ck_{table}_status",
    )


def difficulty_check(table: str) -> CheckConstraint:
    return CheckConstraint(
        f"difficulty BETWEEN {MIN_DIFFICULTY} AND {MAX_DIFFICULTY}",
        name=f"ck_{table}_difficulty",
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PublishableMixin(TimestampMixin):
    """Content a learner may or may not be allowed to see.

    Every learner-facing query must filter `status = 'published'`. Forgetting is
    silent — draft questions simply appear in a test — so each read endpoint
    needs a test asserting draft content stays invisible (ADR-001 A5.3).
    """

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)

    # Who wrote it and who let it out. This is a product with more than one
    # editor, so when a wrong answer reaches a learner the first question is "who
    # approved this" — and a column added later leaves every existing row
    # permanently untraceable.
    #
    # SET NULL rather than CASCADE: deleting a staff account must not delete the
    # content they wrote. Losing the attribution is bad; losing the lesson is worse.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
