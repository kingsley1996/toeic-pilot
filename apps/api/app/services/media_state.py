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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.core.media import (
    AUDIO_ACCENTS,
    DEFAULT_GAP_MS,
    conversation_source_hash,
    source_hash,
)
from app.models.audio import AudioAsset
from app.models.dictation import DictationItem
from app.models.vocabulary import VOCABULARY_AUDIO_KINDS, VocabularyEntry


class AudioState(StrEnum):
    MISSING = "missing"
    STALE = "stale"
    CURRENT = "current"
    # Clip do người tải lên, không do ta tổng hợp. `source_hash` của nó băm một
    # id ngẫu nhiên nên KHÔNG bao giờ khớp text — và đó không phải lỗi.
    #
    # Trạng thái riêng chứ không gộp vào STALE, vì hai bên gọi cần hai câu trả
    # lời khác nhau: màn quản trị muốn biết "có đáng ngờ không" (dùng
    # `audio_script_hash`), còn trình sinh audio muốn biết "có được phép ghi đè
    # không" — và câu trả lời cho bản thu giọng người luôn là KHÔNG. Gộp vào
    # STALE thì `backfill` sẽ lặng lẽ thay giọng người bằng giọng máy, và không
    # ai biết cho tới khi bật lên nghe.
    EXTERNAL = "external"


@dataclass(frozen=True)
class AudioSlot:
    """One clip a piece of content is expected to have."""

    kind: str
    accent: str
    state: AudioState


def clip_state(text: str, asset: AudioAsset | None) -> AudioState:
    if asset is None:
        return AudioState.MISSING
    if asset.source != "tts":
        return AudioState.EXTERNAL
    expected = source_hash(text, asset.voice, asset.engine, asset.engine_version)
    return AudioState.CURRENT if expected == asset.source_hash else AudioState.STALE


def script_state(
    script: Sequence[Mapping[str, str]], asset: AudioAsset | None, gap_ms: int = DEFAULT_GAP_MS
) -> AudioState:
    """Bản thu của một câu (Part 1, 2) hay một cụm (Part 3, 4) có còn khớp lời thoại không.

    Cùng nguyên tắc `clip_state`, khác đầu vào: ở đây thứ được băm là **cả danh
    sách lượt nói** cộng khoảng lặng, vì file phát ra là các lượt đã ghép.

    Đây là điều đường TTS làm được mà đường tải lên không: clip tự sinh có
    `source_hash` suy ra từ chính lời thoại, nên câu hỏi "còn khớp không" trả
    lời được **chắc chắn**, không phải phỏng đoán như `audio_script_hash`
    (ADR-007 §2.7b). Hai đường vì thế có hai mức bảo đảm, và `audio_asset.source`
    là chỗ phân biệt.

    Gọi với `script` rỗng là lỗi lập trình: không có lời thoại thì không có gì
    để đối chiếu, và bên gọi phải bỏ qua trước khi tới đây.
    """
    if not script:
        raise ValueError("script_state cần ít nhất một lượt nói")
    if asset is None:
        return AudioState.MISSING
    if asset.source != "tts":
        return AudioState.EXTERNAL
    expected = conversation_source_hash(
        [(turn["text"], turn["voice"]) for turn in script],
        gap_ms,
        asset.engine,
        asset.engine_version,
    )
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
