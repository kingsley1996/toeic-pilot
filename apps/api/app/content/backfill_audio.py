"""Generate the audio that content in the database is still missing.

    uv run python -m app.content.backfill_audio [--dry-run] [--limit N]

The missing link between "an editor created a word" and "an admin can publish
it". It runs **out of band**, not inside a request, for two reasons that are not
negotiable:

  * the API cannot import this module at all — the production image is built
    without the `content` extra and has no edge-tts (PHASE2-AUDIO A4.1);
  * synthesising eight clips takes tens of seconds, which inside a request would
    drag in a job queue, pending/failed states and polling — exactly what A2.5
    chose to avoid.

The work queue is a query, not a table: "content whose audio is missing or no
longer matches its text". Nothing to enqueue, nothing to retry, no state to get
out of sync — re-running simply finds less to do.
"""

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.content.generate import probe_duration_ms
from app.content.manifest import DEFAULT_MANIFEST_PATH, read_manifest, write_manifest
from app.content.settings import ContentSettings, content_settings
from app.content.storage import LocalDirStore, ObjectStore
from app.content.tts import LOGICAL_VOICES, EdgeTTSEngine, TTSEngine
from app.core.database import SessionLocal
from app.core.media import AUDIO_ACCENTS, source_hash, storage_key_for
from app.models import AudioAsset, DictationItem, VocabularyAudio, VocabularyEntry
from app.services.media_state import AudioState, dictation_audio_state, vocabulary_audio_slots

MIME_TYPE = "audio/mpeg"

# One voice per accent, fixed. Vocabulary is about hearing the same word in four
# accents, so varying the speaker as well would confuse the comparison.
VOICE_FOR_ACCENT = {
    "en-US": "us_female_1",
    "en-GB": "uk_male_1",
    "en-AU": "au_female_1",
    "en-CA": "ca_male_1",
}

# Dictation gets variety instead, chosen from the item's own id so the same
# sentence always comes back in the same voice.
DICTATION_VOICES = ("us_female_1", "uk_male_1", "au_female_1", "ca_male_1")


@dataclass
class Counts:
    synthesised: int = 0
    reused: int = 0
    linked: int = 0
    failed: int = 0

    def as_line(self) -> str:
        return (
            f"{self.synthesised} synthesised · {self.reused} reused · "
            f"{self.linked} linked · {self.failed} failed"
        )


def voice_for_dictation(item: DictationItem) -> str:
    return DICTATION_VOICES[item.id.int % len(DICTATION_VOICES)]


class AudioFactory:
    """Finds or creates the asset for one (text, voice) pair.

    Content-addressed, so two entries sharing a headword share the clip — the
    dedup is free and needs no lookup table.
    """

    def __init__(
        self,
        session: Session,
        engine: TTSEngine,
        store: ObjectStore,
        manifest: dict[str, dict[str, object]],
        *,
        dry_run: bool = False,
    ) -> None:
        self.session = session
        self.engine = engine
        self.store = store
        self.manifest = manifest
        self.dry_run = dry_run
        self.counts = Counts()

    def get_or_create(self, text: str, voice: str) -> AudioAsset | None:
        digest = source_hash(text, voice, self.engine.name, self.engine.version)

        existing = self.session.scalar(select(AudioAsset).where(AudioAsset.source_hash == digest))
        if existing is not None:
            self.counts.reused += 1
            return existing

        # Not in the database, but the clip may still exist: the manifest and the
        # store outlive any single database, so a fresh environment seeded from
        # the repository already has the bytes. Re-synthesising them would burn a
        # TTS call to produce audio we are holding.
        recorded = self.manifest.get(digest)
        if recorded is not None and self.store.exists(str(recorded["storage_key"])):
            asset = AudioAsset(**recorded)
            self.session.add(asset)
            self.session.flush()
            self.counts.reused += 1
            return asset

        if self.dry_run:
            print(f"  would synthesise {voice:<14} {text[:60]!r}")
            self.counts.synthesised += 1
            return None

        key = storage_key_for(digest)
        try:
            data = self.engine.synthesize(text, voice)
            duration = probe_duration_ms(data)
        except Exception as exc:  # edge-tts surfaces a wide range of failures
            # Keep going: one bad clip must not discard a long run's progress.
            print(f"  FAILED {voice} {text[:50]!r}: {exc}", file=sys.stderr)
            self.counts.failed += 1
            return None

        self.store.put(key, data, MIME_TYPE)
        record = {
            "storage_key": key,
            "source_hash": digest,
            "mime_type": MIME_TYPE,
            "size_bytes": len(data),
            "duration_ms": duration,
            "source": "tts",
            "engine": self.engine.name,
            "engine_version": self.engine.version,
            "voice": voice,
            "accent": LOGICAL_VOICES[voice].accent,
            "source_text": text,
        }
        self.manifest[digest] = record

        asset = AudioAsset(**record)
        self.session.add(asset)
        self.session.flush()
        self.counts.synthesised += 1
        print(f"  synthesised {voice:<14} {text[:60]!r}")
        return asset


def backfill_vocabulary(factory: AudioFactory, limit: int | None) -> None:
    entries = factory.session.scalars(
        select(VocabularyEntry).options(selectinload(VocabularyEntry.audio))
    ).all()

    done = 0
    for entry in entries:
        slots = [
            slot for slot in vocabulary_audio_slots(entry) if slot.state is not AudioState.CURRENT
        ]
        if not slots:
            continue
        print(f"{entry.headword} ({entry.part_of_speech}): {len(slots)} clip(s) needed")

        for slot in slots:
            text = entry.headword if slot.kind == "headword" else entry.example
            if not text:
                continue
            asset = factory.get_or_create(text, VOICE_FOR_ACCENT[slot.accent])
            if asset is None:
                continue

            link = factory.session.get(VocabularyAudio, (entry.id, slot.kind, slot.accent))
            if link is None:
                factory.session.add(
                    VocabularyAudio(
                        entry_id=entry.id,
                        kind=slot.kind,
                        accent=slot.accent,
                        audio_asset_id=asset.id,
                    )
                )
            else:
                # Re-pointing rather than deleting: the old asset may still be in
                # use by another entry that shares the headword.
                link.audio_asset_id = asset.id
            factory.counts.linked += 1

        done += 1
        if limit is not None and done >= limit:
            break


def backfill_dictation(factory: AudioFactory, limit: int | None) -> None:
    items = factory.session.scalars(
        select(DictationItem).options(selectinload(DictationItem.asset))
    ).all()

    done = 0
    for item in items:
        if dictation_audio_state(item) is AudioState.CURRENT:
            continue
        print(f"dictation: {item.transcript[:60]!r}")
        asset = factory.get_or_create(item.transcript, voice_for_dictation(item))
        if asset is None:
            continue
        item.audio_asset_id = asset.id
        factory.counts.linked += 1

        done += 1
        if limit is not None and done >= limit:
            break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesise audio the database is missing.")
    parser.add_argument("--dry-run", action="store_true", help="report without calling TTS")
    parser.add_argument("--limit", type=int, default=None, help="stop after N items per kind")
    parser.add_argument(
        "--only",
        choices=("vocabulary", "dictation"),
        default=None,
        help="restrict to one kind of content",
    )
    args = parser.parse_args(argv)

    settings: ContentSettings = content_settings
    manifest = read_manifest(DEFAULT_MANIFEST_PATH)

    with SessionLocal() as session:
        factory = AudioFactory(
            session,
            EdgeTTSEngine(settings),
            LocalDirStore(root=settings.object_store_dir),
            manifest,
            dry_run=args.dry_run,
        )
        if args.only != "dictation":
            backfill_vocabulary(factory, args.limit)
        if args.only != "vocabulary":
            backfill_dictation(factory, args.limit)

        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    if not args.dry_run:
        # The manifest stays in step so the corpus is still reproducible from the
        # repository, even though the database is the source of truth for the text.
        write_manifest(DEFAULT_MANIFEST_PATH, manifest)

    print(f"\n{factory.counts.as_line()}")
    if unknown := set(AUDIO_ACCENTS) - set(VOICE_FOR_ACCENT):
        print(f"warning: no voice configured for {sorted(unknown)}", file=sys.stderr)
    return 1 if factory.counts.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
