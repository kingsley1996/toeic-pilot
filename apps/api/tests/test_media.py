"""Unit tests for content-addressed audio naming.

No fixtures, no database, no network — `app.core.media` is pure stdlib.
"""

import pytest

from app.core.media import public_audio_url, source_hash, storage_key_for

TEXT = "The shipment will arrive on Tuesday morning."
ENGINE = "edge-tts"
VERSION = "7.0.0"


def test_source_hash_is_deterministic() -> None:
    first = source_hash(TEXT, "us_female_1", ENGINE, VERSION)
    second = source_hash(TEXT, "us_female_1", ENGINE, VERSION)
    assert first == second
    assert len(first) == 64


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("text", ("Different sentence entirely.", "us_female_1", ENGINE, VERSION)),
        ("voice", (TEXT, "uk_male_1", ENGINE, VERSION)),
        ("engine", (TEXT, "us_female_1", "piper", VERSION)),
        ("engine_version", (TEXT, "us_female_1", ENGINE, "8.0.0")),
    ],
)
def test_every_input_field_changes_the_hash(field: str, changed: tuple[str, str, str, str]) -> None:
    baseline = source_hash(TEXT, "us_female_1", ENGINE, VERSION)
    assert source_hash(*changed) != baseline, f"{field} does not participate in the hash"


def test_field_separator_prevents_collisions() -> None:
    # With a printable delimiter, ("a|b", "c") and ("a", "b|c") would hash alike.
    assert source_hash("a|b", "c", ENGINE, VERSION) != source_hash("a", "b|c", ENGINE, VERSION)


def test_storage_key_shards_on_the_hash_prefix() -> None:
    digest = source_hash(TEXT, "us_female_1", ENGINE, VERSION)
    assert storage_key_for(digest) == f"audio/{digest[:2]}/{digest}.mp3"


def test_storage_key_honours_the_extension() -> None:
    digest = source_hash(TEXT, "us_female_1", ENGINE, VERSION)
    assert storage_key_for(digest, ext="wav").endswith(".wav")


def test_storage_key_rejects_an_unshardable_hash() -> None:
    with pytest.raises(ValueError):
        storage_key_for("a")


@pytest.mark.parametrize(
    "base",
    [
        "http://localhost:8000/media",
        "http://localhost:8000/media/",
        "http://localhost:8000/media///",
    ],
)
def test_public_url_survives_a_trailing_slash(base: str) -> None:
    assert (
        public_audio_url("audio/ab/abcd.mp3", base_url=base)
        == "http://localhost:8000/media/audio/ab/abcd.mp3"
    )


def test_public_url_survives_a_leading_slash_on_the_key() -> None:
    assert (
        public_audio_url("/audio/ab/abcd.mp3", base_url="https://cdn.example.com")
        == "https://cdn.example.com/audio/ab/abcd.mp3"
    )


def test_public_url_falls_back_to_settings() -> None:
    from app.core.config import settings

    url = public_audio_url("audio/ab/abcd.mp3")
    assert url == f"{settings.audio_public_base_url.rstrip('/')}/audio/ab/abcd.mp3"
