"""Manifest validation and seeding.

The manifest is a committed artifact, so it can be reviewed — and quietly
mis-edited. These tests are the CI-side guard: they run with no network and no
PostgreSQL, and they check the file that is actually in the repo.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.content.manifest import (
    DEFAULT_MANIFEST_PATH,
    MANIFEST_FIELDS,
    read_manifest,
    validate_record,
    write_manifest,
)
from app.content.seed import seed_assets
from app.content.tts import accent_for
from app.core.media import AUDIO_ACCENTS, source_hash, storage_key_for
from app.models import AudioAsset


def make_record(text: str = "invoice", voice: str = "us_female_1") -> dict[str, Any]:
    digest = source_hash(text, voice, "edge-tts", "1")
    return {
        "storage_key": storage_key_for(digest),
        "source_hash": digest,
        "mime_type": "audio/mpeg",
        "size_bytes": 10656,
        "duration_ms": 1776,
        "source": "tts",
        "engine": "edge-tts",
        "engine_version": "1",
        "voice": voice,
        "accent": accent_for(voice),
        "source_text": text,
    }


# --- the manifest committed to this repo ---------------------------------


def test_committed_manifest_is_valid() -> None:
    records = read_manifest(DEFAULT_MANIFEST_PATH)
    assert records, "the committed manifest is empty"
    for digest, record in records.items():
        validate_record(record, where=f"committed manifest {digest[:12]}")


def test_committed_manifest_covers_all_four_accents() -> None:
    records = read_manifest(DEFAULT_MANIFEST_PATH)
    assert {record["accent"] for record in records.values()} == set(AUDIO_ACCENTS)


def test_committed_manifest_is_sorted_by_hash() -> None:
    # A sorted file is what keeps regenerating on another machine from producing
    # a diff that is pure reshuffling.
    lines = DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    hashes = [json.loads(line)["source_hash"] for line in lines if line.strip()]
    assert hashes == sorted(hashes)
    assert len(hashes) == len(set(hashes)), "duplicate source_hash in the manifest"


# --- validation ----------------------------------------------------------


def test_validate_accepts_a_well_formed_record() -> None:
    validate_record(make_record())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.update(storage_key="audio/zz/wrong.mp3"), "does not match its hash"),
        (lambda r: r.update(accent="American"), "is not one of"),
        (lambda r: r.update(source="handwritten"), "is not one of"),
        (lambda r: r.update(source_hash="not-a-hash"), "64-character sha256"),
        (lambda r: r.update(source_hash="z" * 64), "not hexadecimal"),
        (lambda r: r.update(duration_ms=0), "positive integer"),
        (lambda r: r.update(size_bytes=-1), "positive integer"),
        (lambda r: r.update(engine="  "), "non-empty string"),
        (lambda r: r.update(extra="surprise"), "unexpected field"),
        (lambda r: r.pop("voice"), "missing field"),
    ],
)
def test_validate_rejects_a_tampered_record(mutate: Any, message: str) -> None:
    record = make_record()
    mutate(record)
    with pytest.raises(ValueError, match=message):
        validate_record(record)


def test_manifest_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    records = {r["source_hash"]: r for r in (make_record(), make_record(voice="uk_male_1"))}
    write_manifest(path, records)
    assert read_manifest(path) == records


def test_missing_manifest_reads_as_empty(tmp_path: Path) -> None:
    assert read_manifest(tmp_path / "absent.jsonl") == {}


def test_manifest_fields_match_the_model_columns() -> None:
    # Drift here is what turns a manifest into rows the seed cannot insert.
    columns = {c.name for c in AudioAsset.__table__.columns} - {"id", "created_at"}
    assert set(MANIFEST_FIELDS) == columns


# --- seeding -------------------------------------------------------------


def test_seed_inserts_every_record(db_session: Session) -> None:
    records = {r["source_hash"]: r for r in (make_record(), make_record(voice="uk_male_1"))}

    counts = seed_assets(db_session, records)

    assert counts == {"total": 2, "inserted": 2, "updated": 0, "unchanged": 0}
    assert db_session.query(AudioAsset).count() == 2


def test_seeding_twice_leaves_the_same_rows(db_session: Session) -> None:
    # The test this whole design exists for: `source_hash` fingerprints the
    # synthesis input, so replaying a manifest must never duplicate a row.
    records = {r["source_hash"]: r for r in (make_record(),)}

    seed_assets(db_session, records)
    second = seed_assets(db_session, records)

    assert second == {"total": 1, "inserted": 0, "updated": 0, "unchanged": 1}
    assert db_session.query(AudioAsset).count() == 1


def test_seed_updates_a_changed_record(db_session: Session) -> None:
    record = make_record()
    seed_assets(db_session, {record["source_hash"]: record})

    # Same synthesis input, re-rendered: the hash is unchanged by design while the
    # bytes are not, so the row must be updated in place rather than duplicated.
    record["size_bytes"] = 12000
    counts = seed_assets(db_session, {record["source_hash"]: record})

    assert counts == {"total": 1, "inserted": 0, "updated": 1, "unchanged": 0}
    assert db_session.query(AudioAsset).one().size_bytes == 12000


def test_seed_refuses_an_invalid_record(db_session: Session) -> None:
    record = make_record()
    record["accent"] = "American"
    with pytest.raises(ValueError, match="is not one of"):
        seed_assets(db_session, {record["source_hash"]: record})
    assert db_session.query(AudioAsset).count() == 0
