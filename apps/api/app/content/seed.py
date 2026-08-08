"""Load the audio manifest into the database.

    python -m app.content.seed [--manifest <path>]

Split from `generate` on purpose. Generation runs on a developer's machine and
needs edge-tts; seeding runs wherever the database happens to live — including
inside the production image, which is built without the `content` extra. So this
module stays on stdlib and SQLAlchemy, and takes its input from the committed
manifest rather than from the synthesis run that produced it.

Re-running is a no-op: rows are matched on `source_hash`, which fingerprints the
synthesis input, so the same manifest always maps onto the same rows.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.manifest import (
    DEFAULT_IMAGE_MANIFEST_PATH,
    IMAGE_MANIFEST_FIELDS,
    MANIFEST_FIELDS,
    read_manifest,
    validate_image_record,
    validate_record,
)
from app.core.database import SessionLocal
from app.models.audio import AudioAsset
from app.models.image import ImageAsset

# Everything except the identity of the row itself. `source_hash` is what an
# existing row was found by, so rewriting it would be either a no-op or a bug.
_UPDATABLE_FIELDS = tuple(f for f in MANIFEST_FIELDS if f != "source_hash")
_UPDATABLE_IMAGE_FIELDS = tuple(f for f in IMAGE_MANIFEST_FIELDS if f != "source_hash")


def seed_assets(session: Session, records: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Upsert manifest records into `audio_asset`, keyed by `source_hash`."""
    for digest, record in records.items():
        validate_record(record, where=f"manifest entry {digest[:12]}")

    existing = {
        asset.source_hash: asset
        for asset in session.scalars(
            select(AudioAsset).where(AudioAsset.source_hash.in_(records.keys()))
        )
    }

    counts = {"total": len(records), "inserted": 0, "updated": 0, "unchanged": 0}
    for digest, record in records.items():
        asset = existing.get(digest)
        if asset is None:
            session.add(AudioAsset(**record))
            counts["inserted"] += 1
            continue

        changed = [f for f in _UPDATABLE_FIELDS if getattr(asset, f) != record[f]]
        if not changed:
            counts["unchanged"] += 1
            continue
        for field in changed:
            setattr(asset, field, record[field])
        counts["updated"] += 1

    session.commit()
    return counts


def seed_images(session: Session, records: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Upsert image manifest records into `image_asset`, keyed by `source_hash`."""
    for digest, record in records.items():
        validate_image_record(record, where=f"image manifest entry {digest[:12]}")

    existing = {
        asset.source_hash: asset
        for asset in session.scalars(
            select(ImageAsset).where(ImageAsset.source_hash.in_(records.keys()))
        )
    }

    counts = {"total": len(records), "inserted": 0, "updated": 0, "unchanged": 0}
    for digest, record in records.items():
        asset = existing.get(digest)
        if asset is None:
            session.add(ImageAsset(**record))
            counts["inserted"] += 1
            continue

        changed = [f for f in _UPDATABLE_IMAGE_FIELDS if getattr(asset, f) != record[f]]
        if not changed:
            counts["unchanged"] += 1
            continue
        for field in changed:
            setattr(asset, field, record[field])
        counts["updated"] += 1

    session.commit()
    return counts


def _report(label: str, counts: dict[str, int]) -> None:
    print(
        f"{label}: {counts['total']} in manifest · {counts['inserted']} inserted · "
        f"{counts['updated']} updated · {counts['unchanged']} unchanged"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed media assets from the manifests.")
    parser.add_argument("--manifest", type=Path, default=None, help="audio manifest to load")
    parser.add_argument("--image-manifest", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        audio_records = read_manifest(args.manifest)
        image_records = read_manifest(args.image_manifest or DEFAULT_IMAGE_MANIFEST_PATH)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not audio_records and not image_records:
        print("manifests are empty — nothing to seed")
        return 0

    with SessionLocal() as session:
        try:
            if audio_records:
                _report("audio", seed_assets(session, audio_records))
            if image_records:
                _report("image", seed_images(session, image_records))
        except ValueError as exc:
            session.rollback()
            print(f"error: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
