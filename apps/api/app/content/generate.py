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

from app.content.audio_join import join_turns, require_ffmpeg
from app.content.manifest import read_manifest, write_manifest
from app.content.settings import ContentSettings, content_settings
from app.content.storage import LocalDirStore, ObjectStore
from app.content.tts import LOGICAL_VOICES, EdgeTTSEngine, TTSEngine, accent_for
from app.core.media import (
    AUDIO_ACCENTS,
    DEFAULT_GAP_MS,
    MULTI_VOICE,
    conversation_source_hash,
    source_hash,
    storage_key_for,
)

logger = logging.getLogger(__name__)

MIME_TYPE = "audio/mpeg"

# `DEFAULT_GAP_MS` ở `app/core/media.py` — `media_state` cũng cần nó.


@dataclass(frozen=True)
class SpecItem:
    text: str
    voice: str


@dataclass(frozen=True)
class Turn:
    """Một lượt nói trong đoạn hội thoại."""

    text: str
    voice: str


@dataclass(frozen=True)
class ConversationItem:
    """Nhiều lượt, nhiều giọng, một file — thứ Part 2 và Part 3 cần.

    Part 2 là một câu hỏi ở giọng này và ba câu đáp ở giọng khác; Part 3 là hội
    thoại hai đến ba người. Cả hai đều bất khả thi với `SpecItem`, vốn là *một*
    text và *một* giọng (`MEDIA-PIPELINE` §10.2).
    """

    turns: tuple[Turn, ...]
    gap_ms: int
    # Accent ghi vào `audio_asset.accent`. Bắt buộc khai khi các lượt KHÔNG cùng
    # accent — xem `_read_conversation`.
    accent: str

    @property
    def hashable_turns(self) -> list[tuple[str, str]]:
        return [(turn.text, turn.voice) for turn in self.turns]

    @property
    def labelled_text(self) -> str:
        """Bản ghi lời có nhãn giọng, để lưu vào `audio_asset.source_text`.

        Cột đó tồn tại để *dựng lại được* asset, và với một clip nhiều giọng thì
        chỉ nối text lại là mất mất thông tin cần nhất: lượt nào ai nói. Vẫn đọc
        được bằng mắt, nên nó cũng là thứ người biên tập soi khi nghi bản thu
        không khớp.
        """
        return "\n".join(f"[{turn.voice}] {turn.text}" for turn in self.turns)


def read_spec(path: Path) -> Iterator[SpecItem | ConversationItem]:
    """Parse a spec file: one JSON object per line, in one of two shapes.

        {"text": "...", "voice": "us_female_1"}          -> một clip
        {"text": "...", "voices": ["us_female_1", ...]}  -> cùng text, nhiều accent
        {"turns": [{"text": "...", "voice": "..."}, ...], "gap_ms": 700}

    Dạng `turns` là dạng mới; hai dạng cũ không đổi gì, nên mọi spec đã có vẫn
    chạy nguyên như trước.
    """
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON — {exc}") from exc

            where = f"{path}:{lineno}"
            if "turns" in raw:
                yield _read_conversation(raw, where)
                continue

            text = raw.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{where}: missing a non-empty 'text'")

            voices = raw.get("voices") or ([raw["voice"]] if "voice" in raw else [])
            if not voices:
                raise ValueError(f"{where}: needs 'voice', 'voices' or 'turns'")

            for voice in voices:
                _require_known_voice(voice, where)
                yield SpecItem(text=text, voice=voice)


def _require_known_voice(voice: object, where: str) -> str:
    if not isinstance(voice, str) or voice not in LOGICAL_VOICES:
        raise ValueError(
            f"{where}: unknown logical voice {voice!r}; known voices: {sorted(LOGICAL_VOICES)}"
        )
    return voice


def _read_conversation(raw: dict[str, object], where: str) -> ConversationItem:
    raw_turns = raw.get("turns")
    if not isinstance(raw_turns, list) or not raw_turns:
        raise ValueError(f"{where}: 'turns' must be a non-empty list")

    turns: list[Turn] = []
    for index, entry in enumerate(raw_turns, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: turn {index} is not an object")
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{where}: turn {index} has no non-empty 'text'")
        turns.append(Turn(text=text, voice=_require_known_voice(entry.get("voice"), where)))

    # Trộn accent trong một clip là chuyện CÓ THẬT và đúng format: Part 2 của
    # TOEIC cố ý đặt câu hỏi ở một accent và ba câu đáp ở accent khác. Nên
    # không cấm.
    #
    # Nhưng `audio_asset.accent` giữ được đúng một giá trị, nên khi các lượt
    # khác accent thì phải có NGƯỜI quyết định ghi giá trị nào — spec khai
    # `"accent"`. Chọn hộ (lấy lượt đầu) sẽ là một giá trị trông như dữ liệu
    # thật nhưng không ai từng cân nhắc, và không có gì trong file nói ra rằng
    # nó được đoán.
    accents = {accent_for(turn.voice) for turn in turns}
    declared = raw.get("accent")
    if declared is not None:
        if declared not in AUDIO_ACCENTS:
            raise ValueError(f"{where}: accent {declared!r} không thuộc {AUDIO_ACCENTS}")
        accent = str(declared)
    elif len(accents) == 1:
        accent = accents.pop()
    else:
        raise ValueError(
            f'{where}: các lượt dùng {sorted(accents)}; hãy khai rõ "accent" cho clip này. '
            f"`audio_asset.accent` chỉ giữ được MỘT giá trị, nên khi các lượt khác accent "
            f"thì phải có người quyết định ghi giá trị nào — không để mặc định chọn hộ."
        )

    gap = raw.get("gap_ms", DEFAULT_GAP_MS)
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 0:
        raise ValueError(f"{where}: 'gap_ms' phải là số nguyên không âm, đang là {gap!r}")

    return ConversationItem(turns=tuple(turns), gap_ms=gap, accent=accent)


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
    joiner: Callable[[list[bytes], int], bytes] = join_turns,
) -> dict[str, int]:
    """Render everything in `spec_path` that is not already present.

    `duration_probe` and `joiner` are seams alongside `engine` and `store`: they
    let the tests drive the skip/generate logic with stand-ins instead of real
    mp3 bytes — ffmpeg cần mp3 thật, còn thứ đang kiểm ở đây là quyết định sinh
    hay bỏ qua và hàng manifest đi kèm.
    """
    manifest = read_manifest(manifest_path)
    counts = {"total": 0, "skipped": 0, "generated": 0}

    # Đọc hết spec TRƯỚC khi gọi lên TTS, để kiểm ffmpeg một lần ở đầu. Nếu để
    # nó bật ra ở đoạn hội thoại thứ tư mươi thì manifest chưa được ghi và toàn
    # bộ phần đã tổng hợp trước đó mất trắng — `write_manifest` chỉ chạy ở cuối.
    items = list(read_spec(spec_path))
    if not dry_run and any(isinstance(item, ConversationItem) for item in items):
        require_ffmpeg()

    for item in items:
        counts["total"] += 1
        if isinstance(item, ConversationItem):
            digest = conversation_source_hash(
                item.hashable_turns, item.gap_ms, engine.name, engine.version
            )
        else:
            digest = source_hash(item.text, item.voice, engine.name, engine.version)
        key = storage_key_for(digest)

        # Both halves matter: the manifest is committed to git, the audio is not,
        # so on a fresh clone the entry exists while the bytes do not.
        if digest in manifest and store.exists(key):
            counts["skipped"] += 1
            continue

        if dry_run:
            counts["generated"] += 1
            print(f"would generate {_label(item):<14} {key}  {_preview(item)!r}")
            continue

        if isinstance(item, ConversationItem):
            data = joiner(
                [engine.synthesize(turn.text, turn.voice) for turn in item.turns],
                item.gap_ms,
            )
            voice, accent, text = MULTI_VOICE, item.accent, item.labelled_text
        else:
            data = engine.synthesize(item.text, item.voice)
            voice, accent, text = item.voice, accent_for(item.voice), item.text

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
            "voice": voice,
            "accent": accent,
            "source_text": text,
        }
        counts["generated"] += 1
        print(f"generated {_label(item):<14} {key}  ({len(data)} bytes)")

    if not dry_run:
        write_manifest(manifest_path, manifest)
    return counts


def _label(item: SpecItem | ConversationItem) -> str:
    if isinstance(item, ConversationItem):
        return f"{MULTI_VOICE}×{len(item.turns)}"
    return item.voice


def _preview(item: SpecItem | ConversationItem) -> str:
    text = item.turns[0].text if isinstance(item, ConversationItem) else item.text
    return text[:60]


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
