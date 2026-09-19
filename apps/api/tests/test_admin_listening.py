"""Admin thư viện Listening Lab: editor xem, admin phát hành/xoá.

Ranh giới riêng tư là trọng tâm: admin KHÔNG bao giờ thấy bài riêng của user
ở đây (không list, không đọc, không public-hoá hộ) — mỗi ca dưới đều có một
khẳng định cho chuyện đó.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import ListeningContent, User

_SRT = """1
00:00:01,000 --> 00:00:03,000
Hello everyone.

2
00:00:03,000 --> 00:00:06,000
Welcome back.
"""

_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _headers_for(db_session: Session, email: str, role: str = "learner") -> dict[str, str]:
    user = User(email=email, hashed_password="x", role=role)
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _create_private(client: TestClient, headers: dict[str, str]) -> dict:
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Private lesson",
            "transcript": {"format": "srt", "raw": _SRT},
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _make_public(client: TestClient, db_session: Session) -> dict:
    import uuid as _uuid

    body = _create_private(client, _headers_for(db_session, "lib-owner@example.com"))
    row = db_session.get(ListeningContent, _uuid.UUID(body["id"]))
    assert row is not None
    row.is_public = True
    db_session.commit()
    return body


def test_list_requires_editor_and_hides_private(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    mine_headers = _headers_for(db_session, "some-learner@example.com")
    mine = _create_private(client, mine_headers)

    assert client.get("/api/v1/admin/listening/contents").status_code in (401, 403)
    learner_list = client.get("/api/v1/admin/listening/contents", headers=mine_headers)
    assert learner_list.status_code == 403

    editor_list = client.get(
        "/api/v1/admin/listening/contents",
        headers=_headers_for(db_session, "ed@example.com", "editor"),
    )
    assert editor_list.status_code == 200
    body = editor_list.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == public["id"]
    assert body["items"][0]["segment_count"] == 2
    assert body["items"][0]["attempt_count"] == 0
    assert mine["id"] not in [c["id"] for c in body["items"]]


def test_unpublish_removes_from_library(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    admin = _headers_for(db_session, "root@example.com", "admin")

    res = client.patch(
        f"/api/v1/admin/listening/contents/{public['id']}",
        headers=admin,
        json={"is_public": False},
    )
    assert res.status_code == 200
    assert res.json()["is_public"] is False
    assert client.get("/api/v1/listening/library", headers=admin).json() == []


def test_cannot_publish_private_content(client: TestClient, db_session: Session) -> None:
    owner_headers = _headers_for(db_session, "owner2@example.com")
    mine = _create_private(client, owner_headers)

    res = client.patch(
        f"/api/v1/admin/listening/contents/{mine['id']}",
        headers=_headers_for(db_session, "root2@example.com", "admin"),
        json={"is_public": True},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "CANNOT_PUBLISH_PRIVATE"


def test_admin_can_publish_own_private(client: TestClient, db_session: Session) -> None:
    admin_headers = _headers_for(db_session, "selfpub@example.com", "admin")
    mine = _create_private(client, admin_headers)
    res = client.patch(
        f"/api/v1/admin/listening/contents/{mine['id']}",
        headers=admin_headers,
        json={"is_public": True},
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_public"] is True


def test_editor_cannot_change_visibility(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    res = client.patch(
        f"/api/v1/admin/listening/contents/{public['id']}",
        headers=_headers_for(db_session, "ed2@example.com", "editor"),
        json={"is_public": False},
    )
    assert res.status_code == 403


def test_delete_clean_content(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    admin = _headers_for(db_session, "root3@example.com", "admin")
    assert (
        client.delete(f"/api/v1/admin/listening/contents/{public['id']}", headers=admin).status_code
        == 204
    )
    assert client.get("/api/v1/listening/library", headers=admin).json() == []


def test_delete_with_attempts_needs_force(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    learner = _headers_for(db_session, "studier@example.com")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=learner).json()
    client.post(
        f"/api/v1/listening/contents/{public['id']}/attempts",
        headers=learner,
        json={"segment_id": detail["segments"][0]["id"], "answer": "Hello everyone."},
    )
    admin = _headers_for(db_session, "root4@example.com", "admin")
    url = f"/api/v1/admin/listening/contents/{public['id']}"
    blocked = client.delete(url, headers=admin)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "HAS_ATTEMPTS"
    assert client.delete(f"{url}?force=true", headers=admin).status_code == 204


def _full_payload(detail: dict, first_text: str = "Hello friends.") -> list[dict]:
    """PUT admin là full-replace: gửi toàn bộ transcript, câu đầu sửa text."""
    out = []
    for i, seg in enumerate(detail["segments"]):
        row: dict = {"id": seg["id"], "start": seg["start"], "end": seg["end"], "text": seg["text"]}
        if i == 0:
            row["text"] = first_text
        out.append(row)
    return out


def test_admin_can_edit_title_and_segment(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    admin = _headers_for(db_session, "edit-root@example.com", "admin")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=admin).json()
    res = client.put(
        f"/api/v1/admin/listening/contents/{public['id']}",
        headers=admin,
        json={"title": "Fixed title", "segments": _full_payload(detail)},
    )
    assert res.status_code == 200, res.text
    assert res.json()["title"] == "Fixed title"
    assert res.json()["segment_count"] == 2
    after = client.get(f"/api/v1/listening/contents/{public['id']}", headers=admin).json()
    assert after["title"] == "Fixed title"
    assert after["segments"][0]["text"] == "Hello friends."
    assert after["segments"][1]["text"] == "Welcome back."


def test_editor_cannot_edit(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    editor = _headers_for(db_session, "edit-ed@example.com", "editor")
    assert (
        client.put(
            f"/api/v1/admin/listening/contents/{public['id']}",
            headers=editor,
            json={"title": "Nope"},
        ).status_code
        == 403
    )


def test_edit_private_is_404(client: TestClient, db_session: Session) -> None:
    mine = _create_private(client, _headers_for(db_session, "edit-owner@example.com"))
    admin = _headers_for(db_session, "edit-root2@example.com", "admin")
    assert (
        client.put(
            f"/api/v1/admin/listening/contents/{mine['id']}",
            headers=admin,
            json={"title": "Nope"},
        ).status_code
        == 404
    )


def test_edit_with_attempts_needs_force(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    learner = _headers_for(db_session, "edit-stud@example.com")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=learner).json()
    client.post(
        f"/api/v1/listening/contents/{public['id']}/attempts",
        headers=learner,
        json={"segment_id": detail["segments"][0]["id"], "answer": "Hello everyone."},
    )
    admin = _headers_for(db_session, "edit-root3@example.com", "admin")
    url = f"/api/v1/admin/listening/contents/{public['id']}"
    payload = {"segments": _full_payload(detail, first_text="Hello all.")}
    blocked = client.put(url, headers=admin, json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "HAS_ATTEMPTS"
    forced = client.put(f"{url}?force=true", headers=admin, json=payload)
    assert forced.status_code == 200, forced.text
    # Lịch sử giữ nguyên trên cùng segment id.
    assert forced.json()["attempt_count"] == 1


def test_edit_can_add_and_delete_segments(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    admin = _headers_for(db_session, "edit-root5@example.com", "admin")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=admin).json()
    kept = detail["segments"][0]
    res = client.put(
        f"/api/v1/admin/listening/contents/{public['id']}",
        headers=admin,
        json={
            "segments": [
                {
                    "id": kept["id"],
                    "start": kept["start"],
                    "end": kept["end"],
                    "text": kept["text"],
                },
                {"start": 6.0, "end": 8.0, "text": "See you soon."},
            ]
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["segment_count"] == 2
    after = client.get(f"/api/v1/listening/contents/{public['id']}", headers=admin).json()
    assert [s["text"] for s in after["segments"]] == ["Hello everyone.", "See you soon."]
    assert [s["index"] for s in after["segments"]] == [0, 1]


def test_delete_segment_drops_only_its_attempts(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    learner = _headers_for(db_session, "edit-stud2@example.com")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=learner).json()
    for seg in detail["segments"]:
        client.post(
            f"/api/v1/listening/contents/{public['id']}/attempts",
            headers=learner,
            json={"segment_id": seg["id"], "answer": seg["text"]},
        )
    admin = _headers_for(db_session, "edit-root6@example.com", "admin")
    url = f"/api/v1/admin/listening/contents/{public['id']}"
    kept = detail["segments"][0]
    payload = {
        "segments": [
            {"id": kept["id"], "start": kept["start"], "end": kept["end"], "text": kept["text"]}
        ]
    }
    assert client.put(url, headers=admin, json=payload).status_code == 409
    forced = client.put(f"{url}?force=true", headers=admin, json=payload)
    assert forced.status_code == 200, forced.text
    # Câu bị xoá mang lịch sử của nó đi, câu giữ lại còn nguyên.
    assert forced.json()["attempt_count"] == 1
    after = client.get(f"/api/v1/listening/contents/{public['id']}", headers=admin).json()
    assert len(after["segments"]) == 1


def test_edit_rejects_bad_timing(client: TestClient, db_session: Session) -> None:
    public = _make_public(client, db_session)
    admin = _headers_for(db_session, "edit-root4@example.com", "admin")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=admin).json()
    rows = _full_payload(detail)
    rows[0]["start"] = 5.0
    rows[0]["end"] = 2.0
    bad = client.put(
        f"/api/v1/admin/listening/contents/{public['id']}",
        headers=admin,
        json={"segments": rows},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_SEGMENT"
    ghost = client.put(
        f"/api/v1/admin/listening/contents/{public['id']}",
        headers=admin,
        json={"segments": [{"id": str(uuid.uuid4()), "text": "Ghost."}]},
    )
    assert ghost.status_code == 404
    empty = client.put(f"/api/v1/admin/listening/contents/{public['id']}", headers=admin, json={})
    assert empty.status_code == 422


def _set_media(db_session: Session, content_id: str, key: str) -> None:
    import uuid as _uuid

    from app.models import ListeningContent as _LC

    row = db_session.get(_LC, _uuid.UUID(content_id))
    assert row is not None
    row.media_storage_key = key
    db_session.commit()


def test_delete_removes_media_file(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.routes.admin_listening as _admin

    public = _make_public(client, db_session)
    _set_media(db_session, public["id"], "listening/gone.mp4")

    deleted: list[str] = []

    class _FakeDriver:
        def delete(self, key: str) -> None:
            deleted.append(key)

    monkeypatch.setattr(_admin, "get_driver", lambda kind: _FakeDriver())
    admin = _headers_for(db_session, "media-del@example.com", "admin")
    assert (
        client.delete(f"/api/v1/admin/listening/contents/{public['id']}", headers=admin).status_code
        == 204
    )
    assert deleted == ["listening/gone.mp4"]


def test_delete_without_media_touches_no_driver(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.routes.admin_listening as _admin

    public = _make_public(client, db_session)

    def _boom(kind: str) -> None:
        raise AssertionError("không có file thì không gọi driver")

    monkeypatch.setattr(_admin, "get_driver", _boom)
    admin = _headers_for(db_session, "media-del2@example.com", "admin")
    assert (
        client.delete(f"/api/v1/admin/listening/contents/{public['id']}", headers=admin).status_code
        == 204
    )


def test_delete_survives_storage_failure(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid as _uuid

    from app.core.storage import StorageError
    from app.models import ListeningContent as _LC

    public = _make_public(client, db_session)
    _set_media(db_session, public["id"], "listening/stuck.mp4")

    class _BrokenDriver:
        def delete(self, key: str) -> None:
            raise StorageError("kho hỏng")

    import app.api.routes.admin_listening as _admin

    monkeypatch.setattr(_admin, "get_driver", lambda kind: _BrokenDriver())
    admin = _headers_for(db_session, "media-del3@example.com", "admin")
    # Bài đã xoá xong thì vẫn 204 — kho hỏng chỉ log, không 500.
    assert (
        client.delete(f"/api/v1/admin/listening/contents/{public['id']}", headers=admin).status_code
        == 204
    )
    assert db_session.get(_LC, _uuid.UUID(public["id"])) is None


def _private_ids(client: TestClient, headers: dict[str, str]) -> list[str]:
    body = client.get("/api/v1/admin/listening/contents?is_public=false", headers=headers).json()
    return [c["id"] for c in body["items"]]


def test_private_list_shows_only_own(client: TestClient, db_session: Session) -> None:
    admin_a = _headers_for(db_session, "priva@example.com", "admin")
    mine = _create_private(client, admin_a)
    other = _create_private(client, _headers_for(db_session, "privb@example.com"))
    public = _make_public(client, db_session)

    assert _private_ids(client, admin_a) == [mine["id"]]
    assert other["id"] not in _private_ids(client, admin_a)
    assert public["id"] not in _private_ids(client, admin_a)
    # Bài nháp của editor cũng thấy được ở đây (riêng của chính mình).
    editor = _headers_for(db_session, "prive@example.com", "editor")
    draft = _create_private(client, editor)
    assert _private_ids(client, editor) == [draft["id"]]
    # Learner không vào được endpoint admin nào.
    assert (
        client.get(
            "/api/v1/admin/listening/contents?is_public=false",
            headers=_headers_for(db_session, "privc@example.com"),
        ).status_code
        == 403
    )


def test_unpublish_then_republish_roundtrip(client: TestClient, db_session: Session) -> None:
    admin_headers = _headers_for(db_session, "selfpub@example.com", "admin")
    mine = _create_private(client, admin_headers)
    url = f"/api/v1/admin/listening/contents/{mine['id']}"
    assert client.patch(url, headers=admin_headers, json={"is_public": True}).status_code == 200
    assert _private_ids(client, admin_headers) == []
    assert client.patch(url, headers=admin_headers, json={"is_public": False}).status_code == 200
    assert _private_ids(client, admin_headers) == [mine["id"]]
    repub = client.patch(url, headers=admin_headers, json={"is_public": True})
    assert repub.status_code == 200
    assert repub.json()["is_public"] is True
    assert _private_ids(client, admin_headers) == []


def test_editor_cannot_republish_own_draft(client: TestClient, db_session: Session) -> None:
    editor = _headers_for(db_session, "prived@example.com", "editor")
    draft = _create_private(client, editor)
    assert (
        client.patch(
            f"/api/v1/admin/listening/contents/{draft['id']}",
            headers=editor,
            json={"is_public": True},
        ).status_code
        == 403
    )


def test_admin_cannot_see_private_content(client: TestClient, db_session: Session) -> None:
    mine = _create_private(client, _headers_for(db_session, "owner3@example.com"))
    admin = _headers_for(db_session, "root5@example.com", "admin")
    assert (
        client.patch(
            f"/api/v1/admin/listening/contents/{mine['id']}",
            headers=admin,
            json={"is_public": False},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/admin/listening/contents/{mine['id']}", headers=admin).status_code
        == 404
    )
    assert uuid.UUID(mine["id"])  # sanity: id hợp lệ, 404 là do quyền chứ không phải route hỏng
