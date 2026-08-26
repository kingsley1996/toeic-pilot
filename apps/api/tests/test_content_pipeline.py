"""Offline tests for the audio generation pipeline.

No network: the TTS engine is a stand-in. What is under test is the skip/generate
decision and the spec parsing, not Microsoft's endpoint.
"""

import json
from pathlib import Path

import pytest

from app.content.backfill_audio import Policy
from app.content.generate import generate, read_spec
from app.content.manifest import read_manifest
from app.content.storage import LocalDirStore
from app.content.tts import LOGICAL_VOICES, accent_for
from app.core.media import (
    AUDIO_ACCENTS,
    MULTI_VOICE,
    conversation_source_hash,
    source_hash,
    storage_key_for,
)
from app.services.media_state import AudioState


class FakeEngine:
    """Records what it was asked to synthesise so tests can assert on the calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return "fake-tts"

    @property
    def version(self) -> str:
        return "1"

    def synthesize(self, text: str, voice: str) -> bytes:
        self.calls.append((text, voice))
        return f"audio::{voice}::{text}".encode()


def fake_duration(data: bytes) -> int:
    return len(data) * 10


def write_spec(tmp_path: Path, lines: list[dict[str, object]]) -> Path:
    path = tmp_path / "spec.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


# --- logical voices -------------------------------------------------------


def test_all_four_toeic_accents_have_a_voice() -> None:
    covered = {voice.accent for voice in LOGICAL_VOICES.values()}
    assert covered == set(AUDIO_ACCENTS)


def test_logical_names_never_leak_a_provider_id() -> None:
    # The whole point of the logical layer: a provider id in the key would end up
    # in the source hash, and changing engines would invalidate every asset.
    for name in LOGICAL_VOICES:
        assert "Neural" not in name
        assert name.islower()


def test_accent_for_rejects_an_unknown_voice() -> None:
    with pytest.raises(ValueError, match="unknown logical voice"):
        accent_for("martian_female_1")


# --- ép thu lại ------------------------------------------------------------


def test_force_never_overwrites_a_human_recording() -> None:
    """`--force` phải dừng lại đúng ở `EXTERNAL`, và đây là chỗ tốn kém nếu quên.

    Clip do người tải lên băm một id ngẫu nhiên nên không đời nào khớp text —
    dưới phép thử cũ `is not CURRENT` nó rơi thẳng vào nhánh sinh lại và giọng
    người bị TTS ghi đè, chuyện chỉ phát hiện được bằng cách bấm play. Một cái cờ
    tên là "ép" là đúng thứ dễ mở lại cánh cửa đó nhất.
    """
    policy = Policy(force=True)
    assert policy.wants(AudioState.EXTERNAL, "a full sentence here") is False
    assert policy.wants(AudioState.CURRENT, "a full sentence here") is True


def test_force_is_what_separates_a_pace_change_from_a_text_change() -> None:
    # Không ép thì `CURRENT` là dừng: `media_state` cố ý không nhìn thấy việc đổi
    # tốc độ đọc, vì clip đọc nhanh vẫn đọc đúng chữ.
    assert Policy().wants(AudioState.CURRENT, "a full sentence here") is False
    assert Policy().wants(AudioState.MISSING, "a full sentence here") is True


def test_min_words_leaves_single_words_alone() -> None:
    # Đổi tốc độ chỉ có nghĩa với thứ CÓ nhịp; thu lại hơn một nghìn clip từ đơn
    # là trả tiền cho một thay đổi không nghe thấy. Từ khoá hai chữ thì có nhịp
    # thật, nên nó vẫn lọt qua.
    policy = Policy(force=True, min_words=2)
    assert policy.wants(AudioState.CURRENT, "invoice") is False
    assert policy.wants(AudioState.CURRENT, "take off") is True


# --- spec parsing ---------------------------------------------------------


def test_read_spec_expands_voices_into_one_item_each(tmp_path: Path) -> None:
    path = write_spec(tmp_path, [{"text": "invoice", "voices": ["us_female_1", "uk_male_1"]}])
    items = list(read_spec(path))
    assert [item.voice for item in items] == ["us_female_1", "uk_male_1"]
    assert {item.text for item in items} == {"invoice"}


def test_read_spec_accepts_a_single_voice(tmp_path: Path) -> None:
    path = write_spec(tmp_path, [{"text": "invoice", "voice": "us_female_1"}])
    assert len(list(read_spec(path))) == 1


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ({"voice": "us_female_1"}, "non-empty 'text'"),
        ({"text": "  ", "voice": "us_female_1"}, "non-empty 'text'"),
        ({"text": "invoice"}, "needs 'voice', 'voices' or 'turns'"),
        ({"text": "invoice", "voice": "martian_female_1"}, "unknown logical voice"),
    ],
)
def test_read_spec_rejects_a_bad_line(
    tmp_path: Path, line: dict[str, object], message: str
) -> None:
    path = write_spec(tmp_path, [line])
    with pytest.raises(ValueError, match=message):
        list(read_spec(path))


def test_read_spec_reports_the_offending_line_number(tmp_path: Path) -> None:
    path = tmp_path / "spec.jsonl"
    path.write_text('{"text": "ok", "voice": "us_female_1"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"spec\.jsonl:2"):
        list(read_spec(path))


# --- generate -------------------------------------------------------------


def test_generate_writes_audio_and_manifest(tmp_path: Path) -> None:
    spec = write_spec(tmp_path, [{"text": "invoice", "voices": ["us_female_1", "uk_male_1"]}])
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    engine = FakeEngine()

    counts = generate(
        spec,
        engine=engine,
        store=store,
        manifest_path=manifest_path,
        duration_probe=fake_duration,
    )

    assert counts == {"total": 2, "skipped": 0, "generated": 2}
    records = read_manifest(manifest_path)
    assert len(records) == 2
    for record in records.values():
        assert store.exists(record["storage_key"])
        assert record["accent"] == LOGICAL_VOICES[record["voice"]].accent
        assert record["engine"] == "fake-tts"


def test_generate_is_idempotent(tmp_path: Path) -> None:
    spec = write_spec(tmp_path, [{"text": "invoice", "voice": "us_female_1"}])
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    engine = FakeEngine()

    def run() -> dict[str, int]:
        return generate(
            spec,
            engine=engine,
            store=store,
            manifest_path=manifest_path,
            duration_probe=fake_duration,
        )

    run()
    second = run()

    assert second == {"total": 1, "skipped": 1, "generated": 0}
    assert len(engine.calls) == 1, "the second run called TTS again"


def test_generate_regenerates_when_the_manifest_entry_has_no_file(tmp_path: Path) -> None:
    # The fresh-clone case: the manifest is committed to git, the audio is not.
    # Skipping on the manifest alone would leave the entry permanently silent.
    spec = write_spec(tmp_path, [{"text": "invoice", "voice": "us_female_1"}])
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    engine = FakeEngine()

    def run() -> dict[str, int]:
        return generate(
            spec,
            engine=engine,
            store=store,
            manifest_path=manifest_path,
            duration_probe=fake_duration,
        )

    run()
    digest = source_hash("invoice", "us_female_1", engine.name, engine.version)
    (store.root / storage_key_for(digest)).unlink()

    second = run()

    assert second == {"total": 1, "skipped": 0, "generated": 1}
    assert store.exists(storage_key_for(digest))


def test_dry_run_touches_nothing(tmp_path: Path) -> None:
    spec = write_spec(tmp_path, [{"text": "invoice", "voice": "us_female_1"}])
    store = LocalDirStore(root=tmp_path / "media")
    manifest_path = tmp_path / "manifest.jsonl"
    engine = FakeEngine()

    counts = generate(
        spec,
        engine=engine,
        store=store,
        manifest_path=manifest_path,
        dry_run=True,
        duration_probe=fake_duration,
    )

    assert counts == {"total": 1, "skipped": 0, "generated": 1}
    assert engine.calls == []
    assert not manifest_path.exists()
    assert not (tmp_path / "media").exists()


# --- local store ----------------------------------------------------------


def test_store_round_trips_and_leaves_no_partial_file(tmp_path: Path) -> None:
    store = LocalDirStore(root=tmp_path / "media")
    store.put("audio/ab/abcd.mp3", b"bytes", "audio/mpeg")

    assert store.exists("audio/ab/abcd.mp3")
    assert (store.root / "audio/ab/abcd.mp3").read_bytes() == b"bytes"
    assert list((tmp_path / "media").rglob("*.part")) == []


def test_store_rejects_a_key_that_escapes_the_root(tmp_path: Path) -> None:
    store = LocalDirStore(root=tmp_path / "media")
    with pytest.raises(ValueError, match="escapes the store root"):
        store.put("../../etc/passwd", b"nope", "audio/mpeg")


# --- hội thoại nhiều giọng (MEDIA-PIPELINE §10.2) -------------------------


def fake_join(parts: list[bytes], gap_ms: int) -> bytes:
    return f"::gap{gap_ms}::".encode().join(parts)


def test_conversation_hash_follows_order_and_gap() -> None:
    """Hai thứ mà bỏ sót khỏi hash sẽ hỏng theo cùng một kiểu im lặng.

    Đảo hai lượt hoặc đổi khoảng lặng đều cho ra một file khác hẳn. Nếu hash
    không đổi theo, lần sinh sau sẽ "bỏ qua vì đã có" và bản thu cũ ở lại vĩnh
    viễn — không lỗi, không cảnh báo, chỉ là nội dung sai.
    """
    a = [("Where is the meeting?", "us_female_1"), ("Third floor.", "us_male_1")]
    digest = conversation_source_hash(a, 700, "fake-tts", "1")

    assert conversation_source_hash(list(reversed(a)), 700, "fake-tts", "1") != digest
    assert conversation_source_hash(a, 500, "fake-tts", "1") != digest
    # Và một hội thoại một lượt không được trùng với một clip đơn cùng text:
    # hai đường tạo khác nhau dùng chung storage_key thì cái tới sau thắng.
    single = [("Third floor.", "us_male_1")]
    assert conversation_source_hash(single, 0, "fake-tts", "1") != source_hash(
        "Third floor.", "us_male_1", "fake-tts", "1"
    )


def test_mixed_accents_must_be_declared_not_guessed(tmp_path: Path) -> None:
    """Part 2 cố ý trộn accent, nên không cấm — nhưng cũng không đoán hộ.

    `audio_asset.accent` giữ đúng một giá trị. Lấy đại accent của lượt đầu sẽ
    tạo ra một con số trông như dữ liệu thật mà không ai từng cân nhắc.
    """
    turns = [
        {"text": "Where is the meeting?", "voice": "us_female_1"},
        {"text": "Third floor.", "voice": "uk_male_1"},
    ]
    with pytest.raises(ValueError, match='khai rõ "accent"'):
        list(read_spec(write_spec(tmp_path, [{"turns": turns}])))

    (item,) = list(read_spec(write_spec(tmp_path, [{"turns": turns, "accent": "en-GB"}])))
    assert item.accent == "en-GB"


def test_generate_renders_a_conversation_as_one_asset(tmp_path: Path) -> None:
    spec = write_spec(
        tmp_path,
        [
            {
                "gap_ms": 500,
                "turns": [
                    {"text": "Where is the meeting?", "voice": "us_female_1"},
                    {"text": "Third floor.", "voice": "us_male_1"},
                ],
            }
        ],
    )
    engine = FakeEngine()
    manifest_path = tmp_path / "manifest.jsonl"

    counts = generate(
        spec,
        engine=engine,
        store=LocalDirStore(root=tmp_path / "media"),
        manifest_path=manifest_path,
        duration_probe=fake_duration,
        joiner=fake_join,
    )

    assert counts == {"total": 1, "skipped": 0, "generated": 1}
    assert len(engine.calls) == 2, "mỗi lượt phải là một lần gọi TTS riêng"

    (record,) = read_manifest(manifest_path).values()
    assert record["voice"] == MULTI_VOICE
    assert record["accent"] == "en-US"
    # Bản ghi lời mang nhãn giọng: nối trơn sẽ mất đúng thông tin cần nhất.
    assert record["source_text"] == (
        "[us_female_1] Where is the meeting?\n[us_male_1] Third floor."
    )
