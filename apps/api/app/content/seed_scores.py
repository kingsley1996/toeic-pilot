"""Seed the default raw-to-scaled score conversion.

    python -m app.content.seed_scores

ETS does not publish official conversion tables, and each real form has its own.
What is seeded here is an **approximation**, built by linear interpolation
between widely-published anchor points and rounded to the multiples of 5 that
TOEIC scores always land on.

The anchors are the reviewable artifact, which is why they live here rather than
202 interpolated rows living in a data file: a reviewer can argue with twelve
numbers, not with two hundred. The expanded table lands in the database, where a
single wrong value can be corrected without a release.

Stdlib and SQLAlchemy only, like `seed.py` — this has to run inside the
production image, which has no `content` extra.
"""

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.scoring import MAX_SECTION_SCORE, MIN_SECTION_SCORE, ScoreConversion, ScoreScale

DEFAULT_SLUG = "default"

SOURCE_NOTE = (
    "Approximation, NOT an official ETS conversion table. Linear interpolation "
    "between commonly published anchor points, rounded to multiples of 5. Real "
    "TOEIC forms differ from each other and from this. Replace with a per-form "
    "scale before any score is presented as an official estimate."
)

# (raw correct, scaled score) anchors per section.
ANCHORS: dict[str, tuple[tuple[int, int], ...]] = {
    "listening": (
        (0, 5),
        (10, 60),
        (20, 110),
        (30, 155),
        (40, 205),
        (50, 255),
        (60, 305),
        (70, 355),
        (80, 405),
        (90, 450),
        (96, 495),
        (100, 495),
    ),
    "reading": (
        (0, 5),
        (10, 30),
        (20, 70),
        (30, 120),
        (40, 170),
        (50, 220),
        (60, 275),
        (70, 325),
        (80, 375),
        (90, 425),
        (96, 470),
        (100, 495),
    ),
}


def _round_to_5(value: float) -> int:
    return int(round(value / 5.0) * 5)


def expand(anchors: tuple[tuple[int, int], ...]) -> dict[int, int]:
    """Interpolate every raw count from 0 to 100 between the anchor points."""
    table: dict[int, int] = {}
    for (low_raw, low_score), (high_raw, high_score) in zip(anchors, anchors[1:], strict=False):
        span = high_raw - low_raw
        for step in range(span):
            raw = low_raw + step
            ratio = step / span
            table[raw] = _round_to_5(low_score + (high_score - low_score) * ratio)
    last_raw, last_score = anchors[-1]
    table[last_raw] = last_score

    out_of_range = {
        raw: score
        for raw, score in table.items()
        if not MIN_SECTION_SCORE <= score <= MAX_SECTION_SCORE
    }
    if out_of_range:
        raise ValueError(f"anchors produce out-of-range scores: {out_of_range}")
    return table


def seed_scales(session: Session, slug: str = DEFAULT_SLUG) -> dict[str, int]:
    """Upsert the scale and its conversion rows. Re-running changes nothing."""
    scale = session.get(ScoreScale, slug)
    if scale is None:
        scale = ScoreScale(slug=slug, name="Default approximation", source_note=SOURCE_NOTE)
        session.add(scale)
        session.flush()
    else:
        scale.source_note = SOURCE_NOTE

    existing = {
        (row.section, row.raw_correct): row
        for row in session.scalars(
            select(ScoreConversion).where(ScoreConversion.scale_slug == slug)
        )
    }

    counts = {"total": 0, "inserted": 0, "updated": 0, "unchanged": 0}
    for section, anchors in ANCHORS.items():
        for raw, scaled in expand(anchors).items():
            counts["total"] += 1
            row = existing.get((section, raw))
            if row is None:
                session.add(
                    ScoreConversion(
                        scale_slug=slug, section=section, raw_correct=raw, scaled_score=scaled
                    )
                )
                counts["inserted"] += 1
            elif row.scaled_score != scaled:
                row.scaled_score = scaled
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    session.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the default TOEIC score conversion.")
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        try:
            counts = seed_scales(session, args.slug)
        except ValueError as exc:
            session.rollback()
            print(f"error: {exc}", file=sys.stderr)
            return 1

    print(
        f"{counts['total']} rows · {counts['inserted']} inserted · "
        f"{counts['updated']} updated · {counts['unchanged']} unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
