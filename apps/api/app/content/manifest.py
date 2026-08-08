"""Read and write the audio manifest.

The manifest is the hand-off between the two halves of the pipeline: `generate`
runs on a developer's laptop and writes it, `seed` runs wherever the database
lives and reads it. Committing it to the repo is what makes that hand-off
reviewable in a pull request and verifiable in CI without network access.

Pure stdlib on purpose — `seed` must be runnable inside the production image,
which is built without the `content` extra and therefore has no edge-tts.
"""

import json
from pathlib import Path
from typing import Any

from app.core.media import (
    AUDIO_ACCENTS,
    AUDIO_SOURCES,
    image_storage_key_for,
    storage_key_for,
)

# manifest.py -> content -> app -> apps/api
_API_DIR = Path(__file__).resolve().parents[2]

DEFAULT_MANIFEST_PATH = _API_DIR / "content" / "manifest" / "audio_assets.jsonl"
DEFAULT_IMAGE_MANIFEST_PATH = _API_DIR / "content" / "manifest" / "image_assets.jsonl"

# Exactly the writable columns of `audio_asset`; `id` and `created_at` belong to
# the database. Kept explicit so a stray key in a hand-edited manifest is caught
# rather than silently dropped on insert.
MANIFEST_FIELDS = (
    "storage_key",
    "source_hash",
    "mime_type",
    "size_bytes",
    "duration_ms",
    "source",
    "engine",
    "engine_version",
    "voice",
    "accent",
    "source_text",
)

# The writable columns of `image_asset`. Licence and attribution are in the
# required set on purpose: a manifest entry without them describes an image we
# are not allowed to publish (ADR-004 §2.2).
IMAGE_MANIFEST_FIELDS = (
    "storage_key",
    "source_hash",
    "mime_type",
    "size_bytes",
    "width",
    "height",
    "source",
    "source_url",
    "license",
    "attribution",
    "alt_text",
    "transform_version",
)

IMAGE_SOURCES = ("sourced", "generated", "uploaded")


def read_manifest(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load the manifest keyed by `source_hash`. A missing file is an empty manifest."""
    path = path or DEFAULT_MANIFEST_PATH
    if not path.is_file():
        return {}

    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON — {exc}") from exc
            digest = record.get("source_hash")
            if not digest:
                raise ValueError(f"{path}:{lineno}: record has no source_hash")
            records[digest] = record
    return records


def write_manifest(path: Path, records: dict[str, dict[str, Any]]) -> None:
    """Rewrite the manifest, sorted by hash.

    Sorted rather than appended so the committed artifact has a stable order:
    regenerating the same content on another machine then produces an empty diff
    instead of a reshuffled file nobody can review.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(records[key], ensure_ascii=False, sort_keys=True) + "\n"
        for key in sorted(records)
    )
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def validate_record(record: dict[str, Any], where: str = "record") -> None:
    """Reject a manifest entry that could not have come out of the pipeline.

    Runs offline with no network and no database, which is the point: a
    hand-edited manifest — a retyped hash, an invented accent, a storage_key that
    no longer matches its hash — would otherwise only surface as a 404 on a
    learner's audio player long after the pull request merged.
    """
    unexpected = set(record) - set(MANIFEST_FIELDS)
    missing = set(MANIFEST_FIELDS) - set(record)
    if unexpected:
        raise ValueError(f"{where}: unexpected field(s) {sorted(unexpected)}")
    if missing:
        raise ValueError(f"{where}: missing field(s) {sorted(missing)}")

    digest = record["source_hash"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(f"{where}: source_hash must be a 64-character sha256 hex digest")
    try:
        int(digest, 16)
    except ValueError:
        raise ValueError(f"{where}: source_hash is not hexadecimal") from None

    expected_key = storage_key_for(digest)
    if record["storage_key"] != expected_key:
        raise ValueError(
            f"{where}: storage_key {record['storage_key']!r} does not match its hash "
            f"(expected {expected_key!r})"
        )

    if record["accent"] not in AUDIO_ACCENTS:
        raise ValueError(f"{where}: accent {record['accent']!r} is not one of {AUDIO_ACCENTS}")
    if record["source"] not in AUDIO_SOURCES:
        raise ValueError(f"{where}: source {record['source']!r} is not one of {AUDIO_SOURCES}")

    for field in ("size_bytes", "duration_ms"):
        value = record[field]
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{where}: {field} must be a positive integer, got {value!r}")

    for field in ("mime_type", "engine", "engine_version", "voice"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f"{where}: {field} must be a non-empty string")


def validate_image_record(record: dict[str, Any], where: str = "record") -> None:
    """Reject an image manifest entry the pipeline could not have produced.

    Runs offline. The licence and attribution checks are the point: an image with
    a blank attribution is a CC-BY violation waiting to ship, and nothing else in
    the system will notice.
    """
    unexpected = set(record) - set(IMAGE_MANIFEST_FIELDS)
    missing = set(IMAGE_MANIFEST_FIELDS) - set(record)
    if unexpected:
        raise ValueError(f"{where}: unexpected field(s) {sorted(unexpected)}")
    if missing:
        raise ValueError(f"{where}: missing field(s) {sorted(missing)}")

    digest = record["source_hash"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(f"{where}: source_hash must be a 64-character sha256 hex digest")
    try:
        int(digest, 16)
    except ValueError:
        raise ValueError(f"{where}: source_hash is not hexadecimal") from None

    expected_key = image_storage_key_for(digest)
    if record["storage_key"] != expected_key:
        raise ValueError(
            f"{where}: storage_key {record['storage_key']!r} does not match its hash "
            f"(expected {expected_key!r})"
        )

    if record["source"] not in IMAGE_SOURCES:
        raise ValueError(f"{where}: source {record['source']!r} is not one of {IMAGE_SOURCES}")

    for field in ("size_bytes", "width", "height"):
        value = record[field]
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{where}: {field} must be a positive integer, got {value!r}")

    for field in ("mime_type", "source_url", "license", "attribution", "transform_version"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(
                f"{where}: {field} must be a non-empty string — an image without a "
                f"licence and a credit is one we may not publish"
            )
