"""Flow Listening Lab đầu-cuối: tạo bài → đọc → chấm → tiến độ.

Chạy trên SQLite in-memory (conftest) — CHECK/Numeric hành xử đủ giống Postgres
cho những gì ở đây cần kiểm.
"""

from decimal import Decimal

import pytest
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


def test_create_youtube_content_with_segments(client: TestClient, db_session: Session) -> None:
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


def test_invalid_transcript_creates_nothing(client: TestClient, db_session: Session) -> None:
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


def test_tiktok_url_with_pasted_transcript_creates_content(
    client: TestClient, db_session: Session
) -> None:
    # Phase 1 TikTok: resolve mở cổng, transcript dán tay — player + captions
    # tự động tới ở phase sau, nhưng dữ liệu đã đi trọn vòng.
    video_id = "7345678901234567890"
    headers = _headers_for(db_session, "tiktok-creator@example.com")
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "tiktok", "url": f"https://www.tiktok.com/@u/video/{video_id}"},
            "title": "TikTok",
            "transcript": {"format": "srt", "raw": _SRT},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["segment_count"] == 2

    detail = client.get(
        f"/api/v1/listening/contents/{body['id']}",
        headers=headers,
    ).json()
    assert detail["source_type"] == "tiktok"
    assert detail["external_id"] == video_id


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


def test_submit_correct_and_wrong_answers(client: TestClient, db_session: Session) -> None:
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


def test_cross_user_and_cross_content_are_404(client: TestClient, db_session: Session) -> None:
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

    foreign_segment = client.get(
        f"/api/v1/listening/contents/{other['id']}", headers=other_headers
    ).json()["segments"][0]["id"]
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
    # Host lạ (không phải YouTube/TikTok) — chặn ở cổng captions.
    res = client.post(
        "/api/v1/listening/captions",
        headers=headers,
        json={"url": "https://vimeo.com/123456789"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "UNSUPPORTED_SOURCE"


def test_captions_endpoint_supports_tiktok(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.listening_tiktok_captions import TiktokCaptions
    from app.services.listening_transcript import parse_srt_vtt

    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello TikTok.\n"
    segments = parse_srt_vtt(vtt)

    def fake(url: str) -> TiktokCaptions:
        assert url == "https://www.tiktok.com/@u/video/7345678901234567890"
        return TiktokCaptions(
            language="eng-US", kind="asr", raw_vtt=vtt, segments=segments, title="TT"
        )

    monkeypatch.setattr("app.api.routes.listening.fetch_tiktok_captions", fake)
    headers = _headers_for(db_session, "captions-tt@example.com")
    res = client.post(
        "/api/v1/listening/captions",
        headers=headers,
        json={"url": "https://www.tiktok.com/@u/video/7345678901234567890"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "asr"
    assert body["segment_count"] == 1
    assert body["title"] == "TT"


_MUSIC_SRT = """1
00:00:01,000 --> 00:00:03,000
[♪♪♪]

2
00:00:03,000 --> 00:00:05,000
[Music]
"""

_MIXED_SRT = """1
00:00:01,000 --> 00:00:03,000
[♪♪♪]

2
00:00:03,000 --> 00:00:06,000
Hello everyone.

3
00:00:06,000 --> 00:00:08,000
[Applause]
"""


def test_create_all_music_transcript_is_rejected(client: TestClient, db_session: Session) -> None:
    headers = _headers_for(db_session, "nomusic@example.com")
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Music only",
            "transcript": {"format": "srt", "raw": _MUSIC_SRT},
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["errors"] == ["Transcript has no speakable lines"]
    assert db_session.query(ListeningContent).count() == 0


def test_create_drops_nonspeakable_segments_and_warns(
    client: TestClient, db_session: Session
) -> None:
    headers = _headers_for(db_session, "mixed@example.com")
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Mixed",
            "transcript": {"format": "srt", "raw": _MIXED_SRT},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["segment_count"] == 1
    assert any("Skipped 2" in line for line in body["warnings"])

    detail = client.get(f"/api/v1/listening/contents/{body['id']}", headers=headers).json()
    assert [s["text"] for s in detail["segments"]] == ["Hello everyone."]
    assert [s["index"] for s in detail["segments"]] == [0]


def test_captions_all_music_is_unavailable(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    from decimal import Decimal

    from app.services.listening_transcript import ParsedSegment
    from app.services.listening_youtube_captions import YoutubeCaptions

    def fake(video_id: str, transport: object | None = None) -> YoutubeCaptions:
        del video_id, transport
        return YoutubeCaptions(
            language="en",
            kind="manual",
            raw_vtt="WEBVTT",
            segments=[
                ParsedSegment(start=Decimal("0"), end=Decimal("1"), text="[Music]"),
            ],
            title=None,
        )

    monkeypatch.setattr("app.api.routes.listening.fetch_youtube_captions", fake)
    res = client.post(
        "/api/v1/listening/captions",
        headers=_headers_for(db_session, "capmusic@example.com"),
        json={"url": _URL},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "CAPTIONS_UNAVAILABLE"


def test_captions_filters_nonspeakable_segments(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    from decimal import Decimal

    from app.services.listening_transcript import ParsedSegment
    from app.services.listening_youtube_captions import YoutubeCaptions

    def fake(video_id: str, transport: object | None = None) -> YoutubeCaptions:
        del video_id, transport
        return YoutubeCaptions(
            language="en",
            kind="manual",
            raw_vtt="WEBVTT",
            segments=[
                ParsedSegment(start=Decimal("0"), end=Decimal("1"), text="[♪♪♪]"),
                ParsedSegment(start=Decimal("1"), end=Decimal("2"), text="Hi."),
            ],
            title=None,
        )

    monkeypatch.setattr("app.api.routes.listening.fetch_youtube_captions", fake)
    res = client.post(
        "/api/v1/listening/captions",
        headers=_headers_for(db_session, "capmixed@example.com"),
        json={"url": _URL},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["segment_count"] == 1
    assert "Hi." in body["raw"]
    assert "♪" not in body["raw"]


def test_detail_reports_completed_segment_ids(client: TestClient, db_session: Session) -> None:
    headers = _headers_for(db_session, "progress@example.com")
    body = _create(client, headers)
    detail = client.get(f"/api/v1/listening/contents/{body['id']}", headers=headers).json()
    assert detail["completed_segment_ids"] == []

    first = detail["segments"][0]["id"]
    client.post(
        f"/api/v1/listening/contents/{body['id']}/attempts",
        headers=headers,
        json={"segment_id": first, "answer": "Hello everyone."},
    )
    # Trả lời sai không đánh dấu — chỉ is_complete mới vào danh sách.
    second = detail["segments"][1]["id"]
    client.post(
        f"/api/v1/listening/contents/{body['id']}/attempts",
        headers=headers,
        json={"segment_id": second, "answer": "nonsense words here"},
    )

    again = client.get(f"/api/v1/listening/contents/{body['id']}", headers=headers).json()
    assert again["completed_segment_ids"] == [first]


def _make_public(
    client: TestClient, db_session: Session, email: str = "librarian@example.com"
) -> dict:
    """Bài public của thư viện: tạo thường rồi bật cờ (chỉ seed script làm)."""
    import uuid as _uuid

    from app.models import ListeningContent as _LC

    headers = _headers_for(db_session, email)
    body = _create(client, headers)
    row = db_session.get(_LC, _uuid.UUID(body["id"]))
    assert row is not None
    row.is_public = True
    db_session.commit()
    return body


def test_library_lists_public_for_guest_and_hides_private(
    client: TestClient, db_session: Session
) -> None:
    public = _make_public(client, db_session)
    mine_headers = _headers_for(db_session, "private-owner@example.com")
    mine = _create(client, mine_headers)

    guest_list = client.get("/api/v1/listening/library").json()
    assert [c["id"] for c in guest_list] == [public["id"]]
    assert guest_list[0]["completed_count"] == 0

    # Bài riêng không lọt ra thư viện, khách cũng không đọc được.
    assert client.get(f"/api/v1/listening/contents/{mine['id']}").status_code == 404
    assert (
        client.get(f"/api/v1/listening/contents/{mine['id']}", headers=mine_headers).status_code
        == 200
    )


def test_detail_exposes_media_url_when_ingested(client: TestClient, db_session: Session) -> None:
    import uuid as _uuid

    from app.models import ListeningContent as _LC

    public = _make_public(client, db_session, email="media-lib@example.com")
    row = db_session.get(_LC, _uuid.UUID(public["id"]))
    assert row is not None
    row.media_storage_key = "listening/demo.mp4"
    db_session.commit()

    learner = _headers_for(db_session, "media-learner@example.com")
    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=learner).json()
    assert detail["media_url"].endswith("/listening/demo.mp4")

    plain = _make_public(client, db_session, email="media-lib2@example.com")
    detail2 = client.get(f"/api/v1/listening/contents/{plain['id']}", headers=learner).json()
    assert detail2["media_url"] is None


def test_public_detail_readable_and_attemptable_by_other_user(
    client: TestClient, db_session: Session
) -> None:
    public = _make_public(client, db_session)
    learner = _headers_for(db_session, "library-learner@example.com")

    detail = client.get(f"/api/v1/listening/contents/{public['id']}", headers=learner).json()
    assert detail["completed_segment_ids"] == []
    assert len(detail["segments"]) == 2

    first = detail["segments"][0]
    attempt = client.post(
        f"/api/v1/listening/contents/{public['id']}/attempts",
        headers=learner,
        json={"segment_id": first["id"], "answer": first["text"]},
    )
    assert attempt.status_code == 200, attempt.text
    assert attempt.json()["is_correct"] is True

    library = client.get("/api/v1/listening/library", headers=learner).json()
    assert library[0]["completed_count"] == 1


_FRAGMENT_SRT = """1
00:00:01,000 --> 00:00:02,000
Today we're going

2
00:00:02,000 --> 00:00:04,000
to discuss the new schedule.

3
00:00:05,000 --> 00:00:09,000
Hello everyone.
"""


def test_create_merges_short_fragments(client: TestClient, db_session: Session) -> None:
    headers = _headers_for(db_session, "fragments@example.com")
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Fragments",
            "transcript": {"format": "srt", "raw": _FRAGMENT_SRT},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["segment_count"] == 2
    assert any("Merged 1" in line for line in body["warnings"])

    detail = client.get(f"/api/v1/listening/contents/{body['id']}", headers=headers).json()
    assert [s["text"] for s in detail["segments"]] == [
        "Today we're going to discuss the new schedule.",
        "Hello everyone.",
    ]
    assert [s["index"] for s in detail["segments"]] == [0, 1]


def test_create_warns_when_transcript_spans_over_five_minutes(
    client: TestClient, db_session: Session
) -> None:
    headers = _headers_for(db_session, "longvideo@example.com")
    raw = (
        "1\n00:00:01,000 --> 00:00:02,000\nHello there.\n\n"
        "2\n00:06:01,000 --> 00:06:03,000\nGeneral Kenobi.\n"
    )
    res = client.post(
        "/api/v1/listening/contents",
        headers=headers,
        json={
            "source": {"type": "youtube", "url": _URL},
            "title": "Long",
            "transcript": {"format": "srt", "raw": raw},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["segment_count"] == 2
    assert any("over 5 minutes" in line for line in body["warnings"])
