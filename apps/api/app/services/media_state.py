"""Whether a piece of content's audio still matches its text.

Nothing in the schema links an audio clip to the *version* of the text it was
made from, so editing a headword or a transcript leaves the old recording in
place with no complaint. A learner then hears one thing and reads another; for
dictation it is worse, because the transcript is the answer key, so they are
graded against a sentence they were never played.

The check needs no extra column. `audio_asset.source_hash` is the hash of the
synthesis *input*, so recomputing it from the current text answers the question
directly:

    sha256(text_now | voice | engine | engine_version) == asset.source_hash ?

Note the engine and version come from **the asset's own row**, not from settings.
That is deliberate: the question here is "was this clip made from this text",
which is about correctness. "Was this clip made by the current engine" is a
different question, about regeneration, and it must not block publishing —
bumping the engine version does not make existing audio say the wrong words.

Imported by the API, so it may only depend on `app.core` and `app.models`;
`app.content` is off limits (PHASE2-AUDIO A4.1).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.media import AUDIO_ACCENTS, source_hash
from app.models.audio import AudioAsset
from app.models.dictation import DictationItem
from app.models.vocabulary import VOCABULARY_AUDIO_KINDS, VocabularyEntry


class AudioState(StrEnum):
    MISSING = "missing"
    STALE = "stale"
    CURRENT = "current"


@dataclass(frozen=True)
class AudioSlot:
    """One clip a piece of content is expected to have."""

    kind: str
    accent: str
    state: AudioState


def clip_state(text: str, asset: AudioAsset | None) -> AudioState:
    if asset is None:
        return AudioState.MISSING
    expected = source_hash(text, asset.voice, asset.engine, asset.engine_version)
    return AudioState.CURRENT if expected == asset.source_hash else AudioState.STALE


def vocabulary_audio_slots(entry: VocabularyEntry) -> list[AudioSlot]:
    """Every clip the entry should have, and the state of each.

    The headword needs all four TOEIC accents. The example sentence needs them
    too, but only when there is an example — an entry without one is complete
    with four clips, not incomplete with eight.
    """
    by_key = {(row.kind, row.accent): row for row in entry.audio}
    texts = {"headword": entry.headword, "example": entry.example}

    slots: list[AudioSlot] = []
    for kind in VOCABULARY_AUDIO_KINDS:
        text = texts[kind]
        if not text:
            continue
        for accent in AUDIO_ACCENTS:
            row = by_key.get((kind, accent))
            slots.append(AudioSlot(kind, accent, clip_state(text, row.asset if row else None)))
    return slots


def dictation_audio_state(item: DictationItem) -> AudioState:
    # Graded against `transcript`, so that is the text the audio must match —
    # never `audio_asset.source_text`, which only records what was fed to TTS.
    return clip_state(item.transcript, item.asset)


def vocabulary_is_publishable(entry: VocabularyEntry) -> bool:
    return all(slot.state is AudioState.CURRENT for slot in vocabulary_audio_slots(entry))


def dictation_is_publishable(item: DictationItem) -> bool:
    return dictation_audio_state(item) is AudioState.CURRENT
