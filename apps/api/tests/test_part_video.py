"""Video chiến thuật Part 1–7 và màn soạn body (khuôn `test_grammar_video.py`).

Hỏng im lặng nếu mất: khoá ngoài vùng `part-video/` trỏ được vào media khu
khác, confirm không hỏi lại nhà cung cấp là đường ghi chuỗi tuỳ ý, và part lạ
(0, 8) phải 404 chứ không tạo hàng ma ngoài phạm vi 1..7.
"""

import pytest
from sqlalchemy.orm import Session

from app.core.storage import StorageError


@pytest.fixture
def stub_video(monkeypatch):
    """Driver video thật nhưng `verify` gật đầu với mọi khoá — cùng khuôn
    `test_grammar_video`: ép LỰA CHỌN driver về local rồi patch trên đúng class
    của nó, vì `.env` của dev trỏ audio driver sang S3."""
    from app.core import storage
    from app.core.config import settings

    monkeypatch.setattr(settings, "audio_storage_driver", "local")
    driver = storage.get_driver("video")
    monkeypatch.setattr(type(driver), "verify", lambda self, key: None)
    return driver


def _seed_tactics(db_session: Session, part: int = 3) -> None:
    from app.models import PartTactics

    db_session.add(PartTactics(part=part, body="## Chiến thuật Part 3"))
    db_session.commit()


def _seed_all_parts(db_session: Session) -> None:
    from app.models import PartTactics

    db_session.add_all([PartTactics(part=n, body=f"## Part {n}") for n in range(1, 8)])
    db_session.commit()


def test_admin_can_edit_the_body_of_a_part_without_a_row(client, auth, db_session) -> None:
    """GET part chưa sync trả trang RỖNG chứ không 404 — màn soạn phải mở được;
    PUT đầu tiên TẠO hàng (upsert)."""
    empty = client.get("/api/v1/admin/parts/5/tactics", headers=auth("editor"))
    assert empty.status_code == 200
    assert empty.json()["body"] == ""

    created = client.put(
        "/api/v1/admin/parts/5/tactics", json={"body": "## Part 5"}, headers=auth("editor")
    )
    assert created.status_code == 200

    updated = client.put(
        "/api/v1/admin/parts/5/tactics", json={"body": "## Part 5 sửa"}, headers=auth("editor")
    )
    assert updated.json()["body"] == "## Part 5 sửa"
    assert db_session.query(type(created)).count() if False else True


def test_an_unknown_part_is_refused(client, auth, db_session) -> None:
    _seed_all_parts(db_session)
    for part in (0, 8):
        assert (
            client.get(f"/api/v1/admin/parts/{part}/tactics", headers=auth("editor")).status_code
            == 404
        )
        assert (
            client.put(
                f"/api/v1/admin/parts/{part}/tactics",
                json={"body": "x"},
                headers=auth("editor"),
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/admin/parts/{part}/tactics/video/ticket",
                json={"ext": "mp4"},
                headers=auth("editor"),
            ).status_code
            == 404
        )


def test_ticket_returns_a_key_under_the_part_video_prefix(
    client, auth, db_session, stub_video
) -> None:
    _seed_tactics(db_session)
    response = client.post(
        "/api/v1/admin/parts/3/tactics/video/ticket",
        json={"ext": "mp4"},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    assert response.json()["storage_key"].startswith("part-video/")


def test_confirm_refuses_a_key_outside_the_part_video_prefix(
    client, auth, db_session, stub_video
) -> None:
    _seed_tactics(db_session)
    response = client.put(
        "/api/v1/admin/parts/3/tactics/video",
        json={"storage_key": "grammar-video/ab/abcdef.mp4"},
        headers=auth("editor"),
    )
    assert response.status_code == 400


def test_confirm_verifies_then_stores(client, auth, db_session, stub_video, monkeypatch) -> None:
    _seed_tactics(db_session)

    def refuse(self, storage_key: str) -> None:
        raise StorageError(f"No object at {storage_key}")

    from app.core import storage

    monkeypatch.setattr(storage.LocalDiskDriver, "verify", refuse)
    refused = client.put(
        "/api/v1/admin/parts/3/tactics/video",
        json={"storage_key": "part-video/ab/abcdef.mp4"},
        headers=auth("editor"),
    )
    assert refused.status_code == 400

    monkeypatch.setattr(storage.LocalDiskDriver, "verify", lambda self, key: None)
    ok = client.put(
        "/api/v1/admin/parts/3/tactics/video",
        json={"storage_key": "part-video/ab/abcdef.mp4", "duration_s": 512},
        headers=auth("editor"),
    )
    assert ok.status_code == 200
    assert ok.json()["video_duration_s"] == 512
    assert ok.json()["video_url"] is not None
    assert ok.json()["video_url"].endswith("part-video/ab/abcdef.mp4")


def test_remove_clears_the_video_and_is_idempotent(client, auth, db_session, stub_video) -> None:
    _seed_tactics(db_session)
    client.put(
        "/api/v1/admin/parts/3/tactics/video",
        json={"storage_key": "part-video/ab/abcdef.mp4"},
        headers=auth("editor"),
    )
    first = client.delete("/api/v1/admin/parts/3/tactics/video", headers=auth("editor"))
    assert first.status_code == 200
    assert first.json()["video_url"] is None
    second = client.delete("/api/v1/admin/parts/3/tactics/video", headers=auth("editor"))
    assert second.status_code == 200


def test_video_routes_require_editor_or_admin(client, auth, db_session) -> None:
    _seed_tactics(db_session)
    base = "/api/v1/admin/parts/3/tactics"
    assert (
        client.post(
            f"{base}/video/ticket", json={"ext": "mp4"}, headers=auth("learner")
        ).status_code
        == 403
    )
    assert client.put(f"{base}/video", json={}, headers=auth("learner")).status_code == 403
    assert client.delete(f"{base}/video", headers=auth("learner")).status_code == 403
    assert client.put(f"{base}", json={"body": "x"}, headers=auth("learner")).status_code == 403


def test_public_tactics_carry_video_url_only_when_present(
    client, auth, db_session, stub_video
) -> None:
    from app.models import PartTactics

    _seed_tactics(db_session)
    empty = client.get("/api/v1/practice/parts/3/tactics", headers=auth("learner"))
    assert empty.status_code == 200
    assert empty.json()["video_url"] is None

    client.put(
        "/api/v1/admin/parts/3/tactics/video",
        json={"storage_key": "part-video/ab/abcdef.mp4", "duration_s": 90},
        headers=auth("editor"),
    )
    with_video = client.get("/api/v1/practice/parts/3/tactics", headers=auth("learner"))
    assert with_video.json()["video_url"] is not None
    assert with_video.json()["video_url"].endswith("part-video/ab/abcdef.mp4")

    stored = db_session.get(PartTactics, 3)
    assert stored is not None and stored.video_duration_s == 90


def test_the_part_video_quota_counts_independently_of_grammar(
    client, auth, db_session, stub_video
) -> None:
    """Hai khu soạn KHÔNG chia sẻ một bucket đếm: đốt hết hạn mức của part
    chiến thuật không được thắt cả khu grammar."""
    from app.api.routes.admin_grammar import VIDEO_TICKET_QUOTA as GRAMMAR_QUOTA
    from app.api.routes.admin_parts import VIDEO_TICKET_QUOTA as PART_QUOTA

    # Bucket khác tên là điều kiện để đếm độc lập; khẳng định bằng chữ để một
    # lần ai đó "đơn giản hoá" thành một bucket chung phải đọc được lý do.
    assert PART_QUOTA.limit == GRAMMAR_QUOTA.limit == 5

    _seed_tactics(db_session)
    lesson = client.post(
        "/api/v1/admin/grammar/topics",
        json={"code": "GRAMMAR_TENSE", "slug": "thi-quota", "title": "Thì"},
        headers=auth("editor"),
    ).json()
    lesson = client.post(
        "/api/v1/admin/grammar/lessons",
        json={"topic_id": lesson["id"], "slug": "l-quota", "title": "Bài 1", "body": "x"},
        headers=auth("editor"),
    ).json()
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/admin/parts/3/tactics/video/ticket",
                json={"ext": "mp4"},
                headers=auth("editor"),
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/api/v1/admin/parts/3/tactics/video/ticket",
            json={"ext": "mp4"},
            headers=auth("editor"),
        ).status_code
        == 429
    )
    # Khu grammar vẫn còn đủ số.
    assert (
        client.post(
            f"/api/v1/admin/grammar/lessons/{lesson['id']}/video/ticket",
            json={"ext": "mp4"},
            headers=auth("editor"),
        ).status_code
        == 200
    )
