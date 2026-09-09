"""Video bài giảng cho lesson ngữ pháp (SPEC-GRAMMAR-VIDEO §7).

Tám tính chất, phần lớn hỏng IM LẶNG nếu mất: khoá ngoài vùng `grammar-video/`
trỏ được vào media người khác, confirm không hỏi lại nhà cung cấp là đường ghi
chuỗi tuỳ ý, practice gắn video là nuôi một cột không bao giờ đọc, và role thấp
hơn editor phải bị chặn ở CẢ hai đường.
"""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.storage import StorageError


@pytest.fixture
def stub_video(monkeypatch):
    """Driver video thật nhưng `verify` gật đầu với mọi khoá.

    `get_driver` đọc settings mỗi lần gọi, nên phải ép LỰA CHỌN driver về local
    rồi patch trên đúng class của nó (`type(driver)`, khuôn `test_feedback`) —
    `.env` của dev trỏ audio driver sang S3, patch nhầm class là bài test chạy
    xanh với driver mà production không dùng.
    """
    from app.core import storage
    from app.core.config import settings

    monkeypatch.setattr(settings, "audio_storage_driver", "local")
    driver = storage.get_driver("video")
    monkeypatch.setattr(type(driver), "verify", lambda self, key: None)
    return driver


def make_theory_lesson(
    client: TestClient, auth: Callable[[str], dict[str, str]], **over: object
) -> dict:
    topic = client.post(
        "/api/v1/admin/grammar/topics",
        json={"code": "GRAMMAR_TENSE", "slug": "thi-video", "title": "Thì"},
        headers=auth("editor"),
    ).json()
    body = {"topic_id": topic["id"], "slug": "l-video", "title": "Bài có video", "body": "x"} | over
    return client.post("/api/v1/admin/grammar/lessons", json=body, headers=auth("editor")).json()


def test_ticket_returns_presigned_url_under_the_video_prefix(client, auth) -> None:
    lesson = make_theory_lesson(client, auth)
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video/ticket",
        json={"ext": "mp4"},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["storage_key"].startswith("grammar-video/")
    assert body["storage_key"].endswith(".mp4")


def test_ticket_refuses_an_unknown_extension(client, auth) -> None:
    lesson = make_theory_lesson(client, auth)
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video/ticket",
        json={"ext": "avi"},
        headers=auth("editor"),
    )
    assert response.status_code == 422


def test_confirm_refuses_a_key_outside_the_video_prefix(client, auth) -> None:
    """Bẫy prefix, đúng bài `avatar_confirm`: một khoá sai có thể trỏ vào vùng
    media của người khác, và lệnh dọn mồ côi sau này xoá mất thứ đang được dùng."""
    lesson = make_theory_lesson(client, auth)
    response = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video",
        json={"storage_key": "audio/ab/abcdef.mp4"},
        headers=auth("editor"),
    )
    assert response.status_code == 400


def test_confirm_verifies_with_the_driver(client, auth, stub_video) -> None:
    """Thiếu `verify()` là đường ghi một chuỗi tuỳ ý — người học sẽ thấy player vỡ."""
    lesson = make_theory_lesson(client, auth)

    def refuse(self, storage_key: str) -> None:
        raise StorageError(f"No object at {storage_key}")

    import pytest

    from app.core import storage

    pytest.MonkeyPatch().setattr(storage.LocalDiskDriver, "verify", refuse)
    response = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video",
        json={"storage_key": "grammar-video/ab/abcdef.mp4"},
        headers=auth("editor"),
    )
    assert response.status_code == 400
    assert "Chưa thấy file" in response.json()["detail"]


def test_confirm_stores_the_key_when_the_driver_accepts(client, auth, stub_video) -> None:
    lesson = make_theory_lesson(client, auth)
    ok = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video",
        json={"storage_key": "grammar-video/ab/abcdef.mp4", "duration_s": 754},
        headers=auth("editor"),
    )
    assert ok.status_code == 200
    assert ok.json()["video_duration_s"] == 754
    assert ok.json()["video_url"] is not None
    assert ok.json()["video_url"].endswith("grammar-video/ab/abcdef.mp4")


def test_confirm_on_a_practice_lesson_is_refused(client, auth, stub_video) -> None:
    """`practice` không có chỗ hiển thị video — chặn ở biên thay vì nuôi một
    cột không bao giờ đọc."""
    lesson = make_theory_lesson(client, auth, kind="practice", body="")
    response = client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video",
        json={"storage_key": "grammar-video/ab/abcdef.mp4"},
        headers=auth("editor"),
    )
    assert response.status_code == 400


def test_video_routes_require_editor_or_admin(client, auth) -> None:
    lesson = make_theory_lesson(client, auth)
    base = f"/api/v1/admin/grammar/lessons/{lesson['id']}/video"
    assert (
        client.post(f"{base}/ticket", json={"ext": "mp4"}, headers=auth("learner")).status_code
        == 403
    )
    assert client.put(base, json={}, headers=auth("learner")).status_code == 403
    assert client.delete(base, headers=auth("learner")).status_code == 403


def test_remove_clears_the_video_and_is_idempotent(client, auth, stub_video) -> None:
    lesson = make_theory_lesson(client, auth)
    key = "grammar-video/ab/abcdef.mp4"
    client.put(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video",
        json={"storage_key": key},
        headers=auth("editor"),
    )
    first = client.delete(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video", headers=auth("editor")
    )
    assert first.status_code == 200
    assert first.json()["video_url"] is None
    # Lần hai vẫn 200 — gỡ một bài không có video không phải lỗi.
    second = client.delete(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/video", headers=auth("editor")
    )
    assert second.status_code == 200


def test_public_lesson_carries_video_url_only_when_present(
    client, auth, db_session: Session, stub_video
) -> None:
    from app.models import GrammarLesson

    lesson = make_theory_lesson(client, auth)
    # Learning route kiểm CẢ HAI tầng published — lesson và topic của nó.
    client.post(f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin"))
    client.post(f"/api/v1/admin/grammar/topics/{lesson['topic_id']}/publish", headers=auth("admin"))

    empty = client.get(f"/api/v1/grammar-lessons/{lesson['id']}")
    assert empty.status_code == 200
    assert empty.json()["video_url"] is None

    stored = db_session.get(GrammarLesson, uuid.UUID(lesson["id"]))
    assert stored is not None
    stored.video_storage_key = "grammar-video/ab/abcdef.mp4"
    stored.video_duration_s = 61
    db_session.commit()

    with_video = client.get(f"/api/v1/grammar-lessons/{lesson['id']}")
    assert with_video.json()["video_url"] is not None
    assert with_video.json()["video_url"].endswith("grammar-video/ab/abcdef.mp4")


def test_publish_gate_ignores_the_video(client, auth) -> None:
    """§5: video là phụ kiện — lesson theory không video vẫn publish, và confirm
    đã `verify()` nên không có trạng thái "khoá ghi mà file mất" cần cổng chặn."""
    lesson = make_theory_lesson(client, auth)
    response = client.post(
        f"/api/v1/admin/grammar/lessons/{lesson['id']}/publish", headers=auth("admin")
    )
    assert response.status_code == 200
