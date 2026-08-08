"""Fetch and normalise openly-licensed photographs for TOEIC Part 1.

    python -m app.content.images --input content/sources/images/<spec>.jsonl [--dry-run]

Deliberately not a search integration (ADR-004 §2.1). A Part 1 item only works
when the photograph and its four spoken statements fit each other, with three
plausibly wrong — no API can judge that, so any image a search returned would
still need a human to approve it. The spec file is that human's output: they pick
the picture and record where it came from and under what licence.

Mirrors `generate.py` throughout: same object store, same manifest shape, same
"already present" check, same idempotency.
"""

import argparse
import io
import json
import logging
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from app.content.manifest import DEFAULT_IMAGE_MANIFEST_PATH, read_manifest, write_manifest
from app.content.settings import ContentSettings, content_settings
from app.content.storage import LocalDirStore, ObjectStore
from app.core.media import image_source_hash, image_storage_key_for

logger = logging.getLogger(__name__)

MIME_TYPE = "image/jpeg"

# See ADR-004 §3 for why each of these is what it is.
MAX_EDGE_PX = 1280
JPEG_QUALITY = 82


@dataclass(frozen=True)
class ImageSpec:
    url: str
    license: str
    attribution: str
    alt_text: str | None = None


def read_spec(path: Path) -> Iterator[ImageSpec]:
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON — {exc}") from exc

            for field in ("url", "license", "attribution"):
                value = raw.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"{path}:{lineno}: {field!r} is required and must be non-empty. "
                        f"An image without a licence and a credit is one we may not publish."
                    )
            yield ImageSpec(
                url=raw["url"],
                license=raw["license"],
                attribution=raw["attribution"],
                alt_text=raw.get("alt_text"),
            )


class FetchError(RuntimeError):
    """A source refused or failed to serve the image."""


def fetch(url: str, timeout: float = 30.0, user_agent: str | None = None) -> bytes:
    import httpx

    # Wikimedia blocks anonymous library User-Agents outright, so this header is
    # required rather than polite. Wrapping httpx's error keeps the dependency
    # from leaking into callers, which is also why `main` could not catch it.
    headers = {"User-Agent": user_agent or content_settings.http_user_agent}
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FetchError(f"could not fetch {url}: {exc}") from exc
    return response.content


def normalize(data: bytes) -> tuple[bytes, int, int]:
    """Downscale, flatten to RGB, re-encode as JPEG, and drop the metadata.

    EXIF is stripped rather than carried along: it routinely contains GPS
    coordinates and device details belonging to whoever took the photograph, and
    nothing in this application needs them.
    """
    from PIL import Image

    with Image.open(io.BytesIO(data)) as source:
        source.load()
        # CMYK scans and PNGs with alpha both fail or go wrong on a JPEG save.
        image = source.convert("RGB")
        image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX), Image.Resampling.LANCZOS)
        width, height = image.size

        buffer = io.BytesIO()
        # A fresh image object carries no EXIF, so saving it drops the metadata.
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)

    return buffer.getvalue(), width, height


def generate(
    spec_path: Path,
    *,
    store: ObjectStore,
    manifest_path: Path,
    transform_version: str,
    dry_run: bool = False,
    delay_seconds: float = 0.0,
    fetcher: Callable[[str], bytes] = fetch,
    normalizer: Callable[[bytes], tuple[bytes, int, int]] = normalize,
) -> dict[str, int]:
    manifest = read_manifest(manifest_path)
    counts = {"total": 0, "skipped": 0, "fetched": 0, "failed": 0}

    for spec in read_spec(spec_path):
        counts["total"] += 1
        digest = image_source_hash(spec.url, transform_version)
        key = image_storage_key_for(digest)

        # Same two-part check as audio: the manifest is committed, the bytes are
        # not, so a fresh clone has entries whose files are missing.
        if digest in manifest and store.exists(key):
            counts["skipped"] += 1
            continue

        if dry_run:
            counts["fetched"] += 1
            print(f"would fetch {spec.url}")
            continue

        if counts["fetched"] or counts["failed"]:
            time.sleep(delay_seconds)
        try:
            data, width, height = normalizer(fetcher(spec.url))
        except (FetchError, OSError, ValueError) as exc:
            # Keep going and keep what already worked. A run that discards three
            # good images because the fourth 404s is not the resumable pipeline
            # the docs promise.
            counts["failed"] += 1
            print(f"FAILED  {spec.url}\n        {exc}", file=sys.stderr)
            continue

        store.put(key, data, MIME_TYPE)
        manifest[digest] = {
            "storage_key": key,
            "source_hash": digest,
            "mime_type": MIME_TYPE,
            "size_bytes": len(data),
            "width": width,
            "height": height,
            "source": "sourced",
            "source_url": spec.url,
            "license": spec.license,
            "attribution": spec.attribution,
            "alt_text": spec.alt_text,
            "transform_version": transform_version,
        }
        counts["fetched"] += 1
        print(f"fetched {width}x{height} {len(data)} bytes  {key}")

    if not dry_run:
        write_manifest(manifest_path, manifest)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and normalise Part 1 photographs.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    settings: ContentSettings = content_settings
    manifest_path = args.manifest or DEFAULT_IMAGE_MANIFEST_PATH
    store = LocalDirStore(root=args.output_dir or settings.object_store_dir)

    try:
        counts = generate(
            args.input,
            store=store,
            manifest_path=manifest_path,
            transform_version=settings.image_transform_version,
            dry_run=args.dry_run,
            delay_seconds=settings.image_fetch_delay_seconds,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    verb = "would fetch" if args.dry_run else "fetched"
    print(
        f"\n{counts['total']} requested · {counts['skipped']} already present · "
        f"{counts['fetched']} {verb} · {counts['failed']} failed"
    )
    # Non-zero on any failure, but only after the manifest has been written: the
    # successful images stay, and re-running picks up just the missing ones.
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
