"""Offline tests for the Part 1 image pipeline (ADR-004).

No network: the fetcher is a stand-in. What is under test is the skip/fetch
decision, the licence requirements, and the normalisation contract.
"""

import io
import json
from pathlib import Path

import pytest

from app.content.images import FetchError, generate, normalize, read_spec
from app.content.manifest import read_manifest, validate_image_record
from app.content.storage import LocalDirStore
from app.core.media import image_source_hash, image_storage_key_for

SPEC = {
    "url": "https://example.test/warehouse.jpg",
    "license": "CC BY 4.0",
    "attribution": "Someone, CC BY 4.0, via Example",
    "alt_text": "A forklift in a warehouse.",
}


def make_png(width: int = 40, height: int = 25, mode: str = "RGBA") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new(mode, (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def write_spec(tmp_path: Path, lines: list[dict[str, object]]) -> Path:
    path = tmp_path / "spec.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def fake_normalize(data: bytes) -> tuple[bytes, int, int]:
    return data, 1280, 853


# --- spec parsing ---------------------------------------------------------


def test_read_spec_accepts_a_complete_entry(tmp_path: Path) -> None:
    specs = list(read_spec(write_spec(tmp_path, [SPEC])))
    assert len(specs) == 1
    assert specs[0].license == "CC BY 4.0"


@pytest.mark.parametrize("missing", ["url", "license", "attribution"])
def test_read_spec_refuses_an_image_we_may_not_publish(tmp_path: Path, missing: str) -> None:
    # Most openly-licensed photographs are CC-BY: usable only *with* credit.
    # A spec without one is not a formatting problem, it is a licence violation.
    entry = {key: value for key, value in SPEC.items() if key != missing}
    with pytest.raises(ValueError, match="required and must be non-empty"):
        list(read_spec(write_spec(tmp_path, [entry])))


def test_read_spec_refuses_a_blank_attribution(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="required and must be non-empty"):
        list(read_spec(write_spec(tmp_path, [{**SPEC, "attribution": "   "}])))


# --- normalisation --------------------------------------------------------


def test_normalize_flattens_transparency_and_re_encodes_as_jpeg() -> None:
    from PIL import Image

    data, width, height = normalize(make_png(mode="RGBA"))
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG"
        # RGBA would raise on a JPEG save; CMYK would come out inverted.
        assert image.mode == "RGB"
    assert (width, height) == (40, 25)


def test_normalize_caps_the_long_edge() -> None:
    _, width, height = normalize(make_png(4000, 3000, mode="RGB"))
    assert max(width, height) == 1280
    # Aspect ratio preserved rather than squashed.
    assert abs(width / height - 4 / 3) < 0.01


def test_normalize_does_not_upscale_a_small_image() -> None:
    _, width, height = normalize(make_png(200, 150, mode="RGB"))
    assert (width, height) == (200, 150)


def test_normalize_strips_metadata() -> None:
    from PIL import Image

    data, _, _ = normalize(make_png(mode="RGB"))
    with Image.open(io.BytesIO(data)) as image:
        # EXIF routinely carries GPS coordinates belonging to the photographer.
        assert not image.info.get("exif")


def test_normalize_rejects_something_that_is_not_an_image() -> None:
    with pytest.raises(Exception):  # noqa: B017 — Pillow raises its own type
        normalize(b"this is not a picture")


# --- generate -------------------------------------------------------------


def test_generate_stores_the_image_and_its_licence(tmp_path: Path) -> None:
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"

    counts = generate(
        write_spec(tmp_path, [SPEC]),
        store=store,
        manifest_path=manifest_path,
        transform_version="1",
        fetcher=lambda url: b"bytes",
        normalizer=fake_normalize,
    )

    assert counts == {"total": 1, "skipped": 0, "fetched": 1, "failed": 0}
    record = next(iter(read_manifest(manifest_path).values()))
    validate_image_record(record)
    assert record["license"] == "CC BY 4.0"
    assert record["attribution"]
    assert store.exists(record["storage_key"])


def test_generate_is_idempotent(tmp_path: Path) -> None:
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    calls: list[str] = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return b"bytes"

    spec_path = write_spec(tmp_path, [SPEC])
    for _ in range(2):
        generate(
            spec_path,
            store=store,
            manifest_path=manifest_path,
            transform_version="1",
            fetcher=fetcher,
            normalizer=fake_normalize,
        )

    assert len(calls) == 1, "the second run fetched again"


def test_a_failed_image_does_not_discard_the_successful_ones(tmp_path: Path) -> None:
    # This is not hypothetical: Wikimedia returned 429 partway through the first
    # real three-image run. Losing the two that worked would make the documented
    # "re-running only does what is missing" untrue.
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    good = {**SPEC, "url": "https://example.test/good.jpg"}
    bad = {**SPEC, "url": "https://example.test/bad.jpg"}

    def fetcher(url: str) -> bytes:
        if "bad" in url:
            raise FetchError("429 Too many requests")
        return b"bytes"

    counts = generate(
        write_spec(tmp_path, [good, bad]),
        store=store,
        manifest_path=manifest_path,
        transform_version="1",
        fetcher=fetcher,
        normalizer=fake_normalize,
    )

    assert counts == {"total": 2, "skipped": 0, "fetched": 1, "failed": 1}
    assert len(read_manifest(manifest_path)) == 1


def test_a_later_run_picks_up_what_failed(tmp_path: Path) -> None:
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    good = {**SPEC, "url": "https://example.test/good.jpg"}
    flaky = {**SPEC, "url": "https://example.test/flaky.jpg"}
    attempts: list[str] = []

    def fetcher(url: str) -> bytes:
        attempts.append(url)
        if "flaky" in url and attempts.count(url) == 1:
            raise FetchError("429 Too many requests")
        return b"bytes"

    spec_path = write_spec(tmp_path, [good, flaky])
    kwargs = {
        "store": store,
        "manifest_path": manifest_path,
        "transform_version": "1",
        "fetcher": fetcher,
        "normalizer": fake_normalize,
    }
    generate(spec_path, **kwargs)  # type: ignore[arg-type]
    second = generate(spec_path, **kwargs)  # type: ignore[arg-type]

    assert second == {"total": 2, "skipped": 1, "fetched": 1, "failed": 0}
    assert len(read_manifest(manifest_path)) == 2


def test_dry_run_fetches_nothing(tmp_path: Path) -> None:
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"

    def fetcher(url: str) -> bytes:
        raise AssertionError("dry run must not fetch")

    counts = generate(
        write_spec(tmp_path, [SPEC]),
        store=store,
        manifest_path=manifest_path,
        transform_version="1",
        dry_run=True,
        fetcher=fetcher,
        normalizer=fake_normalize,
    )

    assert counts["fetched"] == 1
    assert not manifest_path.exists()


# --- hashing --------------------------------------------------------------


def test_transform_version_changes_the_hash() -> None:
    # The knob that forces a re-fetch of the whole library, and the reason the
    # hash covers the transform rather than the resulting bytes.
    assert image_source_hash(SPEC["url"], "1") != image_source_hash(SPEC["url"], "2")


def test_image_keys_live_under_their_own_prefix() -> None:
    digest = image_source_hash(SPEC["url"], "1")
    assert image_storage_key_for(digest).startswith("image/")
    assert image_storage_key_for(digest).endswith(".jpg")


# --- the manifest committed to this repo ---------------------------------


def test_committed_image_manifest_is_valid() -> None:
    from app.content.manifest import DEFAULT_IMAGE_MANIFEST_PATH

    records = read_manifest(DEFAULT_IMAGE_MANIFEST_PATH)
    assert records, "the committed image manifest is empty"
    for digest, record in records.items():
        validate_image_record(record, where=f"committed image manifest {digest[:12]}")
        assert record["attribution"].strip(), "an image without a credit may not be published"
