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

from app.content.manifest import MANIFEST_FIELDS, read_manifest, validate_record
from app.core.database import SessionLocal
from app.models.audio import AudioAsset

# Everything except the identity of the row itself. `source_hash` is what an
# existing row was found by, so rewriting it would be either a no-op or a bug.
_UPDATABLE_FIELDS = tuple(f for f in MANIFEST_FIELDS if f != "source_hash")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed audio assets from the manifest.")
    parser.add_argument("--manifest", type=Path, default=None, help="manifest to load")
    args = parser.parse_args(argv)

    try:
        records = read_manifest(args.manifest)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not records:
        print("manifest is empty — nothing to seed")
        return 0

    with SessionLocal() as session:
        try:
            counts = seed_assets(session, records)
        except ValueError as exc:
            session.rollback()
            print(f"error: {exc}", file=sys.stderr)
            return 1

    print(
        f"{counts['total']} in manifest · {counts['inserted']} inserted · "
        f"{counts['updated']} updated · {counts['unchanged']} unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
