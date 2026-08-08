"""Constraints on `audio_asset`.

These run against the SQLite fixture, which does enforce UNIQUE and CHECK — the
two things this table relies on to stay idempotent.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.media import source_hash, storage_key_for
from app.models import AudioAsset


def make_asset(text: str = "Please hold the line.", voice: str = "us_female_1") -> AudioAsset:
    digest = source_hash(text, voice, "edge-tts", "7.0.0")
    return AudioAsset(
        storage_key=storage_key_for(digest),
        source_hash=digest,
        mime_type="audio/mpeg",
        size_bytes=8192,
        duration_ms=1500,
        source="tts",
        engine="edge-tts",
        engine_version="7.0.0",
        voice=voice,
        accent="en-US",
        source_text=text,
    )


def test_asset_round_trips(db_session: Session) -> None:
    asset = make_asset()
    db_session.add(asset)
    db_session.commit()

    stored = db_session.query(AudioAsset).one()
    assert stored.id is not None
    assert stored.storage_key.startswith("audio/")
    assert stored.created_at is not None


def test_source_hash_is_unique(db_session: Session) -> None:
    db_session.add(make_asset())
    db_session.commit()

    # Same input, different key: the hash alone must block the second insert,
    # because that is what makes re-running the seed a no-op.
    duplicate = make_asset()
    duplicate.storage_key = "audio/zz/somewhere-else.mp3"
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_storage_key_is_unique(db_session: Session) -> None:
    first = make_asset()
    db_session.add(first)
    db_session.commit()

    collision = make_asset(text="A completely different sentence.")
    collision.storage_key = first.storage_key
    db_session.add(collision)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_source_is_constrained_to_known_values(db_session: Session) -> None:
    asset = make_asset()
    asset.source = "handwritten"
    db_session.add(asset)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_different_voices_coexist(db_session: Session) -> None:
    # The four-accent requirement means one sentence yields four rows, not one.
    for voice, accent in [
        ("us_female_1", "en-US"),
        ("uk_male_1", "en-GB"),
        ("au_female_1", "en-AU"),
        ("ca_male_1", "en-CA"),
    ]:
        asset = make_asset(voice=voice)
        asset.accent = accent
        db_session.add(asset)
    db_session.commit()

    assert db_session.query(AudioAsset).count() == 4
