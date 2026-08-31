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
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.content.audio_join import join_turns, require_ffmpeg
from app.content.generate import probe_duration_ms
from app.content.manifest import DEFAULT_MANIFEST_PATH, read_manifest, write_manifest
from app.content.settings import ContentSettings, content_settings
from app.content.storage import LocalDirStore, ObjectStore
from app.content.tts import LOGICAL_VOICES, EdgeTTSEngine, TTSEngine
from app.core.database import SessionLocal
from app.core.media import (
    AUDIO_ACCENTS,
    DEFAULT_GAP_MS,
    MULTI_VOICE,
    TOEIC_NARRATORS,
    conversation_source_hash,
    script_fingerprint,
    source_hash,
    storage_key_for,
)
from app.models import (
    AudioAsset,
    DictationItem,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionSet,
    VocabularyAudio,
    VocabularyEntry,
)
from app.services.media_state import (
    AudioState,
    dictation_audio_state,
    script_state,
    vocabulary_audio_slots,
)

MIME_TYPE = "audio/mpeg"

# One voice per accent, fixed. Vocabulary is about hearing the same word in four
# accents, so varying the speaker as well would confuse the comparison.
#
# Đó là dàn narrator của đề thật (`TOEIC_NARRATORS`), không phải một lựa chọn
# riêng của phần từ vựng: người học gặp đúng bốn giọng ấy trong bài thi, nên
# gặp một dàn khác khi luyện từ là luyện một thứ sẽ không gặp. Bảng cũ lệch hai
# trên bốn — Anh nam và Úc nữ, hai cặp quốc tịch–giới tính không tồn tại trong
# đề.
VOICE_FOR_ACCENT = dict(TOEIC_NARRATORS)

# Dictation gets variety instead — but the unit of variety is the **story**, not
# the sentence. A story is one continuous passage, and rotating the speaker
# between its sentences makes it sound like four people reading alternate lines
# of the same paragraph.
#
# Standalone sentences keep per-sentence variety: there the point is to meet all
# four accents, and each sentence stands alone anyway.
DICTATION_VOICES = tuple(TOEIC_NARRATORS[accent] for accent in AUDIO_ACCENTS)


# Hai trạng thái này, và CHỈ hai. `CURRENT` thì không có việc gì để làm; còn
# `EXTERNAL` là bản thu người tải lên — ghi đè nó là lặng lẽ thay giọng người
# bằng giọng máy, và không ai biết cho tới khi bật lên nghe.
#
# Trước khi có `EXTERNAL`, phép kiểm là `is not CURRENT`, nên một clip tải lên
# (hash băm id ngẫu nhiên, không đời nào khớp text) rơi thẳng vào nhánh sinh lại.
_REGENERATE = (AudioState.MISSING, AudioState.STALE)


@dataclass(frozen=True)
class Policy:
    """Cái gì được thu lại, ngoài "thiếu" và "lệch text".

    `force` tồn tại vì có một loại thay đổi mà `media_state` **cố ý** không nhìn
    thấy: đổi giọng hay đổi tốc độ đọc. Câu hỏi nó trả lời là "clip này có đọc
    đúng câu này không", và một clip đọc quá nhanh vẫn đọc đúng chữ — nên nó trả
    về `CURRENT`, đúng theo thiết kế. Muốn thu lại thì phải nói ra bằng miệng,
    và đó là cờ này.

    `min_words` là cách diễn đạt phạm vi theo TÍNH CHẤT của nội dung thay vì
    theo danh sách bảng: đổi tốc độ chỉ có nghĩa với thứ CÓ nhịp. Một từ đơn
    ("invoice") đọc nhanh hay chậm gần như không khác gì, nên thu lại 1 212 clip
    từ đơn là trả tiền cho một thay đổi không nghe thấy. `--min-words 2` gói gọn
    ý đó, và nó tự đúng cả với những từ khoá gồm hai chữ như "take off", vốn thì
    có nhịp thật.
    """

    force: bool = False
    min_words: int = 1

    def wants(self, state: AudioState, text: str) -> bool:
        # Bản thu giọng người KHÔNG bao giờ bị ghi đè, kể cả khi ép. Đây là cả lý
        # do `EXTERNAL` tách khỏi `STALE` ngay từ đầu.
        if state is AudioState.EXTERNAL:
            return False
        if len(text.split()) < self.min_words:
            return False
        return state in _REGENERATE or self.force


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
    """One voice per story; per sentence only when the sentence stands alone.

    Derived from an id rather than stored, so it needs no column and never
    drifts: the same story always comes back in the same voice, and re-running
    the backfill after an edit does not silently re-cast the narrator.
    """
    key = item.story_id if item.story_id is not None else item.id
    return DICTATION_VOICES[key.int % len(DICTATION_VOICES)]


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
        duration_probe: Callable[[bytes], int] = probe_duration_ms,
        joiner: Callable[[list[bytes], int], bytes] = join_turns,
    ) -> None:
        self.session = session
        self.engine = engine
        self.store = store
        self.manifest = manifest
        self.dry_run = dry_run
        # Hai seam giống hệt `generate()`, và vì cùng lý do: mutagen cần mp3
        # thật, ffmpeg cần mp3 thật, còn thứ đáng kiểm ở đây là quyết định sinh
        # hay bỏ qua và hàng manifest đi kèm. Không có chúng thì không nhánh nào
        # của lớp này chạy được ngoài một máy đã cài đủ đồ.
        self.duration_probe = duration_probe
        self.joiner = joiner
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
            duration = self.duration_probe(data)
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

    def get_or_create_conversation(
        self, turns: list[tuple[str, str]], gap_ms: int = DEFAULT_GAP_MS
    ) -> AudioAsset | None:
        """Bản thu của một lời thoại nhiều lượt, mỗi lượt một giọng.

        Song song với `get_or_create`, khác đúng ở chỗ băm và ở bước ghép. Vẫn
        content-addressed, nên hai cụm có lời thoại giống hệt dùng chung một
        clip — và sinh lại sau khi sửa một chữ chỉ tốn đúng lời thoại đó.
        """
        digest = conversation_source_hash(turns, gap_ms, self.engine.name, self.engine.version)

        existing = self.session.scalar(select(AudioAsset).where(AudioAsset.source_hash == digest))
        if existing is not None:
            self.counts.reused += 1
            return existing

        recorded = self.manifest.get(digest)
        if recorded is not None and self.store.exists(str(recorded["storage_key"])):
            asset = AudioAsset(**recorded)
            self.session.add(asset)
            self.session.flush()
            self.counts.reused += 1
            return asset

        if self.dry_run:
            print(f"  would synthesise {len(turns)} lượt nói, {_accent_of(turns)}")
            self.counts.synthesised += 1
            return None

        key = storage_key_for(digest)
        try:
            rendered = [self.engine.synthesize(text, voice) for text, voice in turns]
            # Một lượt thì không có ranh giới nào để chèn khoảng lặng, nên bỏ qua
            # ffmpeg luôn: kết quả y hệt, và máy soạn nội dung chưa cài ffmpeg
            # vẫn làm được phần đơn giọng.
            data = rendered[0] if len(rendered) == 1 else self.joiner(rendered, gap_ms)
            duration = self.duration_probe(data)
        except Exception as exc:  # edge-tts và ffmpeg đều hỏng theo nhiều kiểu
            print(f"  FAILED hội thoại {len(turns)} lượt: {exc}", file=sys.stderr)
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
            # Cột `voice` chỉ chứa một giá trị, mà clip này có nhiều giọng.
            "voice": MULTI_VOICE,
            "accent": _accent_of(turns),
            "source_text": "\n".join(f"[{voice}] {text}" for text, voice in turns),
        }
        self.manifest[digest] = record

        asset = AudioAsset(**record)
        self.session.add(asset)
        self.session.flush()
        self.counts.synthesised += 1
        print(f"  synthesised {len(turns)} lượt nói -> {key}")
        return asset


def _accent_of(turns: list[tuple[str, str]]) -> str:
    """Accent ghi lên clip nhiều giọng.

    Cột `accent` chỉ chứa một giá trị. Đồng giọng thì hiển nhiên; lệch giọng —
    đúng hình dạng Part 2, câu hỏi một accent và ba câu đáp accent khác — thì
    lấy accent của **lượt đầu**.

    Ở đường spec file, `MEDIA-PIPELINE` §10.2 bắt khai `accent` thay vì chọn hộ.
    Ở đây nới ra được vì người dùng khác nhau: từ vựng lọc THEO accent (bốn
    accent cho mỗi từ, và chọn sai là hỏng đúng thứ người học đang so sánh), còn
    audio của câu hỏi thì không ai lọc — nó chỉ đi kèm đúng câu đó. Chỗ này
    accent là mô tả, không phải khoá tra cứu.
    """
    accents = [LOGICAL_VOICES[voice].accent for _, voice in turns]
    return accents[0]


def backfill_vocabulary(
    factory: AudioFactory, limit: int | None, policy: Policy = Policy()
) -> None:
    entries = factory.session.scalars(
        select(VocabularyEntry).options(selectinload(VocabularyEntry.audio))
    ).all()

    done = 0
    for entry in entries:
        slots = [
            slot
            for slot in vocabulary_audio_slots(entry)
            if policy.wants(
                slot.state, entry.headword if slot.kind == "headword" else (entry.example or "")
            )
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


def backfill_dictation(factory: AudioFactory, limit: int | None, policy: Policy = Policy()) -> None:
    items = factory.session.scalars(
        select(DictationItem).options(selectinload(DictationItem.asset))
    ).all()

    done = 0
    for item in items:
        if not policy.wants(dictation_audio_state(item), item.transcript):
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


def backfill_questions(
    factory: AudioFactory,
    limit: int | None,
    policy: Policy = Policy(),
    test_slug: str | None = None,
) -> None:
    """Audio cho lời thoại đã soạn: Part 1, 2 trên CÂU và Part 3, 4 trên CỤM.

    Hai nguồn chứ không một, vì bản thu treo ở hai tầng khác nhau (ADR-001 §A4.3):
    Part 1 và 2 mỗi câu một clip, Part 3 và 4 một bài nói dùng chung cho cả cụm.

    Chỉ đụng vào thứ có `audio_script`. Câu chưa ai gõ lời thoại không phải là
    thiếu dữ liệu — nó chỉ chưa được soạn tới.
    """
    owners = _script_owners(factory.session, test_slug)
    assets = _assets_by_id(factory.session, owners)

    # Kiểm ffmpeg MỘT LẦN ở đầu, không để nó nổ ở cụm thứ bốn mươi: lúc đó
    # manifest chưa được ghi và toàn bộ phần đã tổng hợp trước đó mất trắng.
    # Chỉ đòi khi thật sự có clip nhiều lượt — lời thoại một lượt không đi qua
    # ffmpeg (xem `get_or_create_conversation`).
    # Cùng lý do như `generate`: chỉ đòi ffmpeg khi bộ ghép THẬT sẽ chạy. Test
    # tiêm `joiner` riêng chính là để không cần ffmpeg.
    needs_ffmpeg = any(len(owner.audio_script or []) > 1 for owner, _ in owners)
    if not factory.dry_run and factory.joiner is join_turns and needs_ffmpeg:
        require_ffmpeg()

    done = 0
    for owner, label in owners:
        script = owner.audio_script or []
        if not script:
            continue
        asset = assets.get(owner.audio_asset_id) if owner.audio_asset_id else None
        # Qua `policy`, không so thẳng với `_REGENERATE`: so thẳng thì `--force`
        # bị bỏ qua ở đúng chỗ nó cần nhất. Đổi tốc độ đọc hay đổi ánh xạ giọng
        # để `script_state` trả `CURRENT` — nó hỏi "clip này có đọc đúng lời
        # thoại này không", và clip cũ vẫn đọc đúng chữ — nên không có `--force`
        # thì audio của đề KHÔNG BAO GIỜ được thu lại.
        if not policy.wants(script_state(script, asset), " ".join(t["text"] for t in script)):
            continue

        print(f"{label}: {len(script)} lượt nói")
        turns = [(turn["text"], turn["voice"]) for turn in script]
        made = factory.get_or_create_conversation(turns)
        if made is None:
            continue

        owner.audio_asset_id = made.id
        # Chốt luôn "bản thu này gắn cho lời thoại nào", đúng như đường tải lên
        # làm. Không có nó, cảnh báo lệch ở màn quản trị sẽ kêu ngay với chính
        # clip vừa sinh đúng cho lời thoại đó.
        owner.audio_attached_at = datetime.now(UTC)
        owner.audio_script_hash = script_fingerprint(turns)
        factory.counts.linked += 1

        done += 1
        if limit is not None and done >= limit:
            return


_ScriptOwner = Question | QuestionSet


def _script_owners(
    session: Session, test_slug: str | None = None
) -> list[tuple[_ScriptOwner, str]]:
    """Mọi thứ mang lời thoại, kèm nhãn đọc được để in ra tiến độ.

    `test_slug` thu phạm vi về một đề, và nó tồn tại vì `--force`: ép thu lại
    tốn hàng giờ và không hoàn tác được, nên phải thử được trên một đề trước khi
    áp cho cả kho.
    """
    scope: set[uuid.UUID] | None = None
    if test_slug is not None:
        test = session.scalar(select(PracticeTest).where(PracticeTest.slug == test_slug))
        if test is None:
            raise SystemExit(f"không có đề nào tên {test_slug!r}")
        scope = set(
            session.scalars(
                select(PracticeTestQuestion.question_id).where(
                    PracticeTestQuestion.test_id == test.id
                )
            ).all()
        )

    question_where = [Question.audio_script.is_not(None), Question.part.in_((1, 2))]
    set_where = [QuestionSet.audio_script.is_not(None), QuestionSet.part.in_((3, 4))]
    if scope is not None:
        question_where.append(Question.id.in_(scope))
        # Cụm không trỏ tới đề; đường đi là qua câu thuộc cụm đó.
        set_where.append(
            QuestionSet.id.in_(
                select(Question.set_id).where(Question.id.in_(scope), Question.set_id.is_not(None))
            )
        )

    questions = session.scalars(
        select(Question).where(*question_where).order_by(Question.created_at)
    ).all()
    sets = session.scalars(
        select(QuestionSet).where(*set_where).order_by(QuestionSet.created_at)
    ).all()

    owners: list[tuple[_ScriptOwner, str]] = [(q, f"câu Part {q.part}") for q in questions]
    owners += [(st, f"cụm Part {st.part} · {st.title or 'không tên'}") for st in sets]
    return owners


def _assets_by_id(
    session: Session, owners: list[tuple[_ScriptOwner, str]]
) -> dict[uuid.UUID, AudioAsset]:
    """Nạp bản thu đang gắn, một lượt.

    `Question` và `QuestionSet` chỉ có cột `audio_asset_id`, không có quan hệ ORM
    tới `audio_asset` — bảng asset cố ý độc lập với schema nghiệp vụ, phụ thuộc
    chạy một chiều nghiệp vụ → asset (PHASE2-AUDIO §A4). Nên tra tay, và tra một
    lượt thay vì mỗi cụm một lần đi lại database.
    """
    ids = {owner.audio_asset_id for owner, _ in owners if owner.audio_asset_id}
    if not ids:
        return {}
    return {a.id: a for a in session.scalars(select(AudioAsset).where(AudioAsset.id.in_(ids)))}


def run_backfill(
    *,
    only: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    policy: Policy | None = None,
    settings: ContentSettings | None = None,
    test_slug: str | None = None,
) -> Counts:
    """Một lượt quét đầy đủ. Dùng chung cho CLI và cho worker chạy dài.

    Tách khỏi `main` để worker gọi được cùng một đường: hai bản sao của "quét
    những gì" sẽ trôi khỏi nhau, và cái trôi là cái không ai chạy bằng tay nên
    không ai phát hiện.
    """
    settings = settings or content_settings
    policy = policy or Policy()
    manifest = read_manifest(DEFAULT_MANIFEST_PATH)

    with SessionLocal() as session:
        factory = AudioFactory(
            session,
            EdgeTTSEngine(settings),
            LocalDirStore(root=settings.object_store_dir),
            manifest,
            dry_run=dry_run,
        )
        if only in (None, "vocabulary"):
            backfill_vocabulary(factory, limit, policy)
        if only in (None, "dictation"):
            backfill_dictation(factory, limit, policy)
        if only in (None, "questions"):
            backfill_questions(factory, limit, policy, test_slug)

        if dry_run:
            session.rollback()
        else:
            session.commit()

    if not dry_run:
        # Manifest giữ nhịp với database để kho nội dung vẫn dựng lại được từ
        # repository, dù database mới là nguồn sự thật cho phần chữ.
        write_manifest(DEFAULT_MANIFEST_PATH, manifest)

    return factory.counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesise audio the database is missing.")
    parser.add_argument("--dry-run", action="store_true", help="report without calling TTS")
    parser.add_argument("--limit", type=int, default=None, help="stop after N items per kind")
    parser.add_argument(
        "--only",
        choices=("vocabulary", "dictation", "questions"),
        default=None,
        help="restrict to one kind of content",
    )
    parser.add_argument(
        "--test",
        help="chỉ một đề, theo slug (ví dụ tp-form-07); chỉ có nghĩa với --only questions",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="thu lại cả clip đang khớp text (dùng khi đổi giọng hoặc tốc độ đọc)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=1,
        help="bỏ qua văn bản ngắn hơn N từ; 2 = chỉ thứ có nhịp, không gồm từ đơn",
    )
    args = parser.parse_args(argv)

    counts = run_backfill(
        only=args.only,
        limit=args.limit,
        dry_run=args.dry_run,
        policy=Policy(force=args.force, min_words=args.min_words),
        test_slug=args.test,
    )

    print(f"\n{counts.as_line()}")
    if unknown := set(AUDIO_ACCENTS) - set(VOICE_FOR_ACCENT):
        print(f"warning: no voice configured for {sorted(unknown)}", file=sys.stderr)
    return 1 if counts.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
