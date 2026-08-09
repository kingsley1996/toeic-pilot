"""Offline audio generation.

    uv run python -m app.content.generate --input content/sources/sample.jsonl [--dry-run]

Reads a spec file, synthesises whatever is missing, writes the audio into the
object store, and records each asset in the manifest. It never touches the
database: the manifest is the hand-off, because the machine that runs this is a
laptop and the database that needs the rows is somewhere else entirely.

Re-running is safe and cheap — anything already in the manifest *and* present in
the store is skipped, which also makes an interrupted bulk run resumable.
"""

import argparse
import io
import json
import logging
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from app.content.manifest import read_manifest, write_manifest
from app.content.settings import ContentSettings, content_settings
from app.content.storage import LocalDirStore, ObjectStore
from app.content.tts import LOGICAL_VOICES, EdgeTTSEngine, TTSEngine, accent_for
from app.core.media import source_hash, storage_key_for

logger = logging.getLogger(__name__)

MIME_TYPE = "audio/mpeg"


@dataclass(frozen=True)
class SpecItem:
    text: str
    voice: str


def read_spec(path: Path) -> Iterator[SpecItem]:
    """Parse a spec file: one JSON object per line, `text` plus `voice` or `voices`."""
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON — {exc}") from exc

            text = raw.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{path}:{lineno}: missing a non-empty 'text'")

            voices = raw.get("voices") or ([raw["voice"]] if "voice" in raw else [])
            if not voices:
                raise ValueError(f"{path}:{lineno}: needs 'voice' or 'voices'")

            for voice in voices:
                if voice not in LOGICAL_VOICES:
                    raise ValueError(
                        f"{path}:{lineno}: unknown logical voice {voice!r}; "
                        f"known voices: {sorted(LOGICAL_VOICES)}"
                    )
                yield SpecItem(text=text, voice=voice)


def probe_duration_ms(data: bytes) -> int:
    """Read playback length out of the mp3 headers.

    Stored so the UI can size a progress bar without downloading the file first.
    """
    from mutagen.mp3 import MP3

    info = MP3(io.BytesIO(data)).info
    if info is None:
        raise ValueError("synthesised audio has no readable mp3 header")
    return int(round(info.length * 1000))


def generate(
    spec_path: Path,
    *,
    engine: TTSEngine,
    store: ObjectStore,
    manifest_path: Path,
    dry_run: bool = False,
    duration_probe: Callable[[bytes], int] = probe_duration_ms,
) -> dict[str, int]:
    """Render everything in `spec_path` that is not already present.

    `duration_probe` is a seam alongside `engine` and `store`: it lets the tests
    drive the skip/generate logic with stand-ins instead of real mp3 bytes.
    """
    manifest = read_manifest(manifest_path)
    counts = {"total": 0, "skipped": 0, "generated": 0}

    for item in read_spec(spec_path):
        counts["total"] += 1
        digest = source_hash(item.text, item.voice, engine.name, engine.version)
        key = storage_key_for(digest)

        # Both halves matter: the manifest is committed to git, the audio is not,
        # so on a fresh clone the entry exists while the bytes do not.
        if digest in manifest and store.exists(key):
            counts["skipped"] += 1
            continue

        if dry_run:
            counts["generated"] += 1
            print(f"would generate {item.voice:<14} {key}  {item.text[:60]!r}")
            continue

        data = engine.synthesize(item.text, item.voice)
        store.put(key, data, MIME_TYPE)
        manifest[digest] = {
            "storage_key": key,
            "source_hash": digest,
            "mime_type": MIME_TYPE,
            "size_bytes": len(data),
            "duration_ms": duration_probe(data),
            "source": "tts",
            "engine": engine.name,
            "engine_version": engine.version,
            "voice": item.voice,
            "accent": accent_for(item.voice),
            "source_text": item.text,
        }
        counts["generated"] += 1
        print(f"generated {item.voice:<14} {key}  ({len(data)} bytes)")

    if not dry_run:
        write_manifest(manifest_path, manifest)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate audio assets from a spec file.")
    parser.add_argument("--input", required=True, type=Path, help="spec .jsonl to render")
    parser.add_argument("--manifest", type=Path, default=None, help="manifest to update")
    parser.add_argument("--output-dir", type=Path, default=None, help="object store root")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be generated without calling TTS or writing anything",
    )
    args = parser.parse_args(argv)

    settings: ContentSettings = content_settings
    manifest_path = args.manifest or settings.manifest_path
    store = LocalDirStore(root=args.output_dir or settings.object_store_dir)

    try:
        counts = generate(
            args.input,
            engine=EdgeTTSEngine(settings),
            store=store,
            manifest_path=manifest_path,
            dry_run=args.dry_run,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    verb = "would generate" if args.dry_run else "generated"
    print(
        f"\n{counts['total']} requested · {counts['skipped']} already present · "
        f"{counts['generated']} {verb}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
