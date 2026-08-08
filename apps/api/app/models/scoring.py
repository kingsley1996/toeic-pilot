from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

SECTIONS = ("listening", "reading")

# A TOEIC section score runs 5-495 and always lands on a multiple of 5.
MIN_SECTION_SCORE = 5
MAX_SECTION_SCORE = 495


class ScoreScale(Base, TimestampMixin):
    """A named raw-to-scaled conversion table.

    A table rather than a constant in code, for two reasons. TOEIC conversions
    differ from form to form, so a single hard-coded curve is wrong by
    construction. And a scoring error should be correctable by editing a row, not
    by shipping a release.
    """

    __tablename__ = "score_scale"

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # NOT NULL, and it earns it. ETS does not publish official conversion tables,
    # so every scale here is an approximation from some source. When a learner
    # disputes a score, this column is the answer to "where did this number come
    # from" — and without it there is no answer.
    source_note: Mapped[str] = mapped_column(Text, nullable=False)

    conversions: Mapped[list["ScoreConversion"]] = relationship(
        back_populates="scale", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ScoreScale {self.slug}>"


class ScoreConversion(Base):
    """One row per (scale, section, raw correct count)."""

    __tablename__ = "score_conversion"
    __table_args__ = (
        CheckConstraint("section IN ('listening', 'reading')", name="ck_score_conversion_section"),
        CheckConstraint("raw_correct BETWEEN 0 AND 100", name="ck_score_conversion_raw"),
        CheckConstraint("scaled_score BETWEEN 5 AND 495", name="ck_score_conversion_scaled"),
    )

    scale_slug: Mapped[str] = mapped_column(
        ForeignKey("score_scale.slug", ondelete="CASCADE"), primary_key=True
    )
    section: Mapped[str] = mapped_column(String(16), primary_key=True)
    raw_correct: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    scaled_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    scale: Mapped["ScoreScale"] = relationship(back_populates="conversions")
