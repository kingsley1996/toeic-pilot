"""Flow Listening Lab đầu-cuối: tạo bài → đọc → chấm → tiến độ.

Chạy trên SQLite in-memory (conftest) — CHECK/Numeric hành xử đủ giống Postgres
cho những gì ở đây cần kiểm.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import ListeningContent, User

_SRT = """1
00:00:12,420 --> 00:00:15,180
Hello everyone.

2
00:00:15,180 --> 00:00:20,910
Today we're going to discuss the new schedule.
"""

_BAD_SRT = "1\n00:00:05,000 --> 00:00:02,000\nBackwards.\n"

_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _headers_for(db_session: Session, email: str) -> dict[str, str]:
    """User learner riêng (fixture `auth` cache theo role nên không cho hai
    learner khác nhau — mà test 404-chéo cần đúng thứ đó)."""
    user = User(email=email, hashed_password="x", role="learner")
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _create(client: TestClient, headers: dict[str, str], raw: str = _SRT) -> dict:
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Business Meeting",
            "transcript": {"format": "srt", "raw": raw},
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_create_youtube_content_with_segments(
    client: TestClient, db_session: Session
) -> None:
    headers = _headers_for(db_session, "creator@example.com")
    body = _create(client, headers)
    assert body["status"] == "ready"
    assert body["segment_count"] == 2

    detail = client.get(f"/api/v1/listening/contents/{body['id']}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["external_id"] == "dQw4w9WgXcQ"
    assert data["source_url"] == _URL
    assert [s["text"] for s in data["segments"]] == [
        "Hello everyone.",
        "Today we're going to discuss the new schedule.",
    ]
    assert [s["index"] for s in data["segments"]] == [0, 1]
    assert data["segments"][0]["start"] == 12.42


def test_invalid_transcript_creates_nothing(
    client: TestClient, db_session: Session
) -> None:
    res = client.post(
        "/api/v1/listening/contents",
        headers=_headers_for(db_session, "creator@example.com"),
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Bad",
            "transcript": {"format": "srt", "raw": _BAD_SRT},
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "INVALID_TRANSCRIPT"
    assert db_session.query(ListeningContent).count() == 0


def test_tiktok_url_rejected_with_unsupported(
    client: TestClient, db_session: Session
) -> None:
    res = client.post(
        "/api/v1/listening/contents",
        headers=_headers_for(db_session, "creator@example.com"),
        json={
            "source": {"type": "tiktok", "url": "https://www.tiktok.com/@u/video/1"},
            "title": "TikTok",
            "transcript": {"format": "srt", "raw": _SRT},
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "UNSUPPORTED_SOURCE"


def test_source_label_must_match_url(client: TestClient, db_session: Session) -> None:
    res = client.post(
        "/api/v1/listening/contents",
        headers=_headers_for(db_session, "creator@example.com"),
        json={
            "source": {"type": "tiktok", "url": _URL},
            "title": "Mismatch",
            "transcript": {"format": "srt", "raw": _SRT},
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "SOURCE_TYPE_MISMATCH"


def test_submit_correct_and_wrong_answers(
    client: TestClient, db_session: Session
) -> None:
    headers = _headers_for(db_session, "learner@example.com")
    body = _create(client, headers)
    detail = client.get(f"/api/v1/listening/contents/{body['id']}", headers=headers).json()
    first, second = detail["segments"]

    good = client.post(
        f"/api/v1/listening/contents/{body['id']}/attempts",
        headers=headers,
        json={"segment_id": first["id"], "answer": "Hello everyone", "time_spent_seconds": 9},
    )
    assert good.status_code == 200
    assert good.json()["is_correct"] is True
    assert good.json()["expected_text"] == "Hello everyone."

    bad = client.post(
        f"/api/v1/listening/contents/{body['id']}/attempts",
        headers=headers,
        json={"segment_id": second["id"], "answer": "Today we're late"},
    )
    assert bad.status_code == 200
    assert bad.json()["is_correct"] is False
    assert bad.json()["similarity"] != "100.00"

    listing = client.get("/api/v1/listening/contents", headers=headers).json()
    assert listing[0]["segment_count"] == 2
    assert listing[0]["completed_count"] == 1


def test_cross_user_and_cross_content_are_404(
    client: TestClient, db_session: Session
) -> None:
    mine_headers = _headers_for(db_session, "mine@example.com")
    other_headers = _headers_for(db_session, "other@example.com")
    stranger_headers = _headers_for(db_session, "stranger@example.com")
    mine = _create(client, mine_headers)
    other = _create(client, other_headers)

    assert (
        client.get(f"/api/v1/listening/contents/{mine['id']}", headers=other_headers).status_code
        == 404
    )
    assert client.get("/api/v1/listening/contents", headers=stranger_headers).json() == []

    foreign_segment = (
        client.get(f"/api/v1/listening/contents/{other['id']}", headers=other_headers)
        .json()["segments"][0]["id"]
    )
    res = client.post(
        f"/api/v1/listening/contents/{mine['id']}/attempts",
        headers=mine_headers,
        json={"segment_id": foreign_segment, "answer": "Hello everyone."},
    )
    assert res.status_code == 404


def test_captions_endpoint_uses_resolved_id(client: TestClient, db_session: Session, monkeypatch):
    from app.services.listening_transcript import ParsedSegment
    from app.services.listening_youtube_captions import YoutubeCaptions

    captured: list[str] = []

    def fake(video_id: str, transport: object | None = None) -> YoutubeCaptions:
        del transport
        captured.append(video_id)
        return YoutubeCaptions(
            language="en",
            kind="manual",
            raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHi.\n",
            segments=[ParsedSegment(start=Decimal("0"), end=Decimal("1"), text="Hi.")],
            title="From captions",
        )

    monkeypatch.setattr("app.api.routes.listening.fetch_youtube_captions", fake)
    headers = _headers_for(db_session, "captions@example.com")
    res = client.post(
        "/api/v1/listening/captions",
        headers=headers,
        json={"url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert captured == ["dQw4w9WgXcQ"]
    assert body["kind"] == "manual"
    assert body["segment_count"] == 1
    assert body["title"] == "From captions"
    assert body["raw"].startswith("WEBVTT")


def test_captions_endpoint_maps_source_errors(client: TestClient, db_session: Session):
    headers = _headers_for(db_session, "captions-bad@example.com")
    res = client.post(
        "/api/v1/listening/captions",
        headers=headers,
        json={"url": "https://www.tiktok.com/@u/video/1"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "UNSUPPORTED_SOURCE"
