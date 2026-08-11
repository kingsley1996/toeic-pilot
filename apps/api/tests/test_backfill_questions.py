"""Sinh audio cho lời thoại đã soạn trong database (ADR-007 §2.7b).

Không có mạng, không có ffmpeg: engine, bộ đo độ dài và bước ghép đều là hàng
thay thế. Thứ đang kiểm là **quyết định sinh hay bỏ qua** và những gì được ghi
lại sau khi sinh — không phải endpoint của Microsoft hay bộ nối của ffmpeg.
"""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.content.backfill_audio import AudioFactory, backfill_questions
from app.content.storage import LocalDirStore
from app.core.media import script_fingerprint, upload_source_hash
from app.models import AudioAsset, QuestionSet
from app.services.media_state import AudioState, script_state

SCRIPT = [
    {"text": "Attention passengers, the gate has changed.", "voice": "us_male_1"},
    {"text": "Which gate should we go to?", "voice": "us_female_1"},
]


class FakeEngine:
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


def make_factory(session: Session, tmp_path: Path) -> AudioFactory:
    return AudioFactory(
        session,
        FakeEngine(),
        LocalDirStore(root=tmp_path),
        {},
        duration_probe=lambda data: len(data) * 10,
        joiner=lambda parts, gap: b"|".join(parts),
    )


def make_set(session: Session, script: list[dict[str, str]] | None = None) -> QuestionSet:
    stimulus = QuestionSet(part=3, title="Sân bay", audio_script=script or SCRIPT, status="draft")
    session.add(stimulus)
    session.commit()
    return stimulus


def test_a_set_with_a_script_gets_one_joined_clip(db_session: Session, tmp_path: Path) -> None:
    stimulus = make_set(db_session)
    factory = make_factory(db_session, tmp_path)

    backfill_questions(factory, None)
    db_session.commit()

    assert factory.counts.synthesised == 1
    assert factory.counts.linked == 1
    # Một clip cho cả cụm, không phải một clip mỗi lượt: Part 3 là một bài nói
    # dùng chung (ADR-001 §A4.3).
    asset = db_session.get(AudioAsset, stimulus.audio_asset_id)
    assert asset is not None
    assert asset.source == "tts"


def test_generated_audio_does_not_immediately_read_as_stale(
    db_session: Session, tmp_path: Path
) -> None:
    """Clip vừa sinh cho đúng lời thoại đó phải im lặng.

    `audio_script_hash` được ghi lúc gắn. Quên dòng đó thì mọi clip tự sinh bật
    cảnh báo "lời thoại đã đổi" ngay khi vừa ra đời, và một cảnh báo luôn bật là
    một cảnh báo người ta học cách bỏ qua.
    """
    stimulus = make_set(db_session)
    backfill_questions(make_factory(db_session, tmp_path), None)
    db_session.commit()

    turns = [(t["text"], t["voice"]) for t in SCRIPT]
    assert stimulus.audio_script_hash == script_fingerprint(turns)
    assert stimulus.audio_attached_at is not None


def test_editing_the_script_makes_the_next_run_regenerate(
    db_session: Session, tmp_path: Path
) -> None:
    """Hàng đợi là một truy vấn: sửa chữ xong chạy lại là thấy việc."""
    stimulus = make_set(db_session)
    backfill_questions(make_factory(db_session, tmp_path), None)
    db_session.commit()
    first = stimulus.audio_asset_id

    stimulus.audio_script = [dict(SCRIPT[0]), {**SCRIPT[1], "text": "Which terminal?"}]
    db_session.commit()

    second_factory = make_factory(db_session, tmp_path)
    backfill_questions(second_factory, None)
    db_session.commit()

    assert second_factory.counts.synthesised == 1
    assert stimulus.audio_asset_id != first


def test_an_uploaded_recording_is_never_replaced_by_tts(
    db_session: Session, tmp_path: Path
) -> None:
    """Giọng người đã tải lên là thứ trình sinh audio KHÔNG được đụng vào.

    `source_hash` của file tải lên băm một id ngẫu nhiên, nên nó không đời nào
    khớp lời thoại — với phép kiểm cũ (`is not CURRENT`) nó rơi thẳng vào nhánh
    sinh lại, và bản thu giọng người bị thay bằng giọng máy mà không ai biết cho
    tới khi bật lên nghe.
    """
    stimulus = make_set(db_session)
    human = AudioAsset(
        storage_key="audio/aa/human.mp3",
        source_hash=upload_source_hash(str(uuid.uuid4())),
        voice="uploaded",
        accent="en-US",
        engine="uploaded",
        engine_version="-",
        duration_ms=9000,
        size_bytes=100,
        source="uploaded",
    )
    db_session.add(human)
    db_session.commit()
    stimulus.audio_asset_id = human.id
    db_session.commit()

    assert script_state(SCRIPT, human) is AudioState.EXTERNAL

    factory = make_factory(db_session, tmp_path)
    backfill_questions(factory, None)
    db_session.commit()

    assert factory.counts.synthesised == 0
    assert stimulus.audio_asset_id == human.id
