"""The content admin surface.

Two things are checked on every endpoint, because both fail silently:
a learner must get 403, and an import must never land as `published`.
"""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.media import source_hash
from app.models import (
    Attempt,
    AudioAsset,
    DictationItem,
    PracticeTest,
    Question,
    QuestionSet,
    Topic,
    User,
    VocabularyAudio,
    VocabularyEntry,
    VocabularyTopic,
)
from app.models.image import ImageAsset
from tests.test_domain_model import make_audio

PASTE = (
    "invoice | noun | /ˈɪnvɔɪs/ | a bill | hóa đơn | Pay the invoice. | Thanh toán hóa đơn.\n"
    "deadline | noun | /ˈdedlaɪn/ | the latest time | hạn chót\n"
)


def give_audio(session: Session, entry: VocabularyEntry, marker: str = "a") -> None:
    for index, accent in enumerate(("en-US", "en-GB", "en-AU", "en-CA")):
        voice = f"v{index}"
        digest = source_hash(entry.headword, voice, "edge-tts", "1")
        asset = make_audio(session, marker=f"{marker}{index}")
        asset.source_hash = digest
        asset.storage_key = f"audio/{digest[:2]}/{digest}.mp3"
        asset.voice = voice
        asset.accent = accent
        session.flush()
        session.add(
            VocabularyAudio(
                entry_id=entry.id, kind="headword", accent=accent, audio_asset_id=asset.id
            )
        )
    session.commit()


# --- authorisation --------------------------------------------------------


ADMIN_CALLS = [
    ("GET", "/api/v1/admin/topics", None),
    ("POST", "/api/v1/admin/topics", {"slug": "x", "name": "X"}),
    (
        "PATCH",
        "/api/v1/admin/topics/00000000-0000-0000-0000-000000000000",
        {"name": "X"},
    ),
    ("DELETE", "/api/v1/admin/topics/00000000-0000-0000-0000-000000000000", None),
    ("POST", "/api/v1/admin/vocabulary/parse", {"raw_text": "a"}),
    ("POST", "/api/v1/admin/vocabulary", {"rows": []}),
    ("GET", "/api/v1/admin/vocabulary", None),
    ("POST", "/api/v1/admin/dictation/parse", {"raw_text": "a"}),
    ("POST", "/api/v1/admin/dictation", {"rows": []}),
    ("GET", "/api/v1/admin/dictation", None),
    ("GET", "/api/v1/admin/voices", None),
    ("GET", "/api/v1/admin/test-collections", None),
    ("POST", "/api/v1/admin/test-collections", {"slug": "x", "title": "X"}),
    ("POST", "/api/v1/admin/test-collections/x/publish", None),
    ("GET", "/api/v1/admin/tests", None),
    ("POST", "/api/v1/admin/test-collections/x/archive", {"archived": True}),
    ("DELETE", "/api/v1/admin/test-collections/x", None),
    ("POST", "/api/v1/admin/tests/x/archive", {"archived": True}),
    ("DELETE", "/api/v1/admin/tests/x", None),
    (
        "POST",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000/archive",
        {"archived": True},
    ),
    ("DELETE", "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000", None),
    ("PATCH", "/api/v1/admin/tests/x", {"title": "X"}),
    ("GET", "/api/v1/admin/tests/x/sets", None),
    (
        "PATCH",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000",
        {"explanation": "x"},
    ),
    (
        "PATCH",
        "/api/v1/admin/question-sets/00000000-0000-0000-0000-000000000000",
        {"title": "X"},
    ),
    (
        "POST",
        "/api/v1/admin/question-sets/00000000-0000-0000-0000-000000000000/passage-image",
        {"slot": 1},
    ),
    ("POST", "/api/v1/admin/media/audio/requests", None),
    ("POST", "/api/v1/admin/media/audio/ticket", {"ext": "mp3"}),
    (
        "POST",
        "/api/v1/admin/media/audio/confirm",
        {"storage_key": "audio/aa/x.mp3", "duration_ms": 1, "accent": "en-US"},
    ),
    (
        "POST",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000/audio",
        {"asset_id": None},
    ),
    (
        "POST",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000/image",
        {"asset_id": None},
    ),
    (
        "POST",
        "/api/v1/admin/question-sets/00000000-0000-0000-0000-000000000000/audio",
        {"asset_id": None},
    ),
    ("POST", "/api/v1/admin/tests", {"slug": "x", "title": "X"}),
    ("GET", "/api/v1/admin/tests/x", None),
    ("GET", "/api/v1/admin/tests/x/questions", None),
    ("POST", "/api/v1/admin/tests/x/parts/7/parse", {"raw_text": "a"}),
    ("POST", "/api/v1/admin/tests/x/parts", {"part": 7, "groups": []}),
    ("POST", "/api/v1/admin/tests/x/publish", None),
    ("POST", "/api/v1/admin/tests/x/questions/publish", None),
    (
        "POST",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000/publish",
        None,
    ),
    # Tầng AI. Nút gắn nhãn CHẠY ĐƯỢC VIỆC TỐN TIỀN, nên nó phải chịu đúng cổng
    # phân quyền như mọi thứ khác — và cổng đó là một dependency, không phải một
    # phép kiểm trong thân hàm, vì phép kiểm trong thân hàm là thứ người ta quên
    # chép sang route tiếp theo.
    ("POST", "/api/v1/admin/ai/skill-tags/requests", None),
    ("GET", "/api/v1/admin/ai/stats", None),
    ("GET", "/api/v1/admin/ai/features", None),
    ("GET", "/api/v1/admin/ai/models", None),
    (
        "PUT",
        "/api/v1/admin/ai/features/coach_explain",
        {"provider": "ollama", "model": "gemma3:latest", "enabled": True},
    ),
    ("GET", "/api/v1/admin/ai/labels", None),
    ("GET", "/api/v1/admin/ai/labels/catalog", None),
    (
        "PATCH",
        "/api/v1/admin/ai/labels/00000000-0000-0000-0000-000000000000",
        {"facet": "question_type", "code": "PART_5_GRAMMAR"},
    ),
    (
        "PATCH",
        "/api/v1/admin/ai/set-labels/00000000-0000-0000-0000-000000000000",
        {"facet": "topic", "code": "PART_3_HOUSING"},
    ),
    # Cây từ vựng (collection -> collection_item -> topic). Mọi nút chịu cùng cổng
    # phân quyền như phần còn lại: editor viết, admin quyết định thứ được học viên
    # thấy (publish/delete).
    ("GET", "/api/v1/admin/vocabulary-collections", None),
    ("POST", "/api/v1/admin/vocabulary-collections", {"slug": "x", "name": "X"}),
    (
        "PATCH",
        "/api/v1/admin/vocabulary-collections/00000000-0000-0000-0000-000000000000",
        {"name": "X"},
    ),
    (
        "DELETE",
        "/api/v1/admin/vocabulary-collections/00000000-0000-0000-0000-000000000000",
        None,
    ),
    (
        "POST",
        "/api/v1/admin/vocabulary-collections/00000000-0000-0000-0000-000000000000/publish",
        None,
    ),
    ("GET", "/api/v1/admin/vocabulary-collection-items", None),
    (
        "POST",
        "/api/v1/admin/vocabulary-collection-items",
        {
            "collection_id": "00000000-0000-0000-0000-000000000000",
            "name": "X",
        },
    ),
    (
        "PATCH",
        "/api/v1/admin/vocabulary-collection-items/00000000-0000-0000-0000-000000000000",
        {"name": "X"},
    ),
    (
        "DELETE",
        "/api/v1/admin/vocabulary-collection-items/00000000-0000-0000-0000-000000000000",
        None,
    ),
    (
        "POST",
        "/api/v1/admin/vocabulary-collection-items/00000000-0000-0000-0000-000000000000/publish",
        None,
    ),
]


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_CALLS)
def test_a_learner_is_refused_everywhere(
    client: TestClient,
    auth: Callable[[str], dict[str, str]],
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    response = client.request(method, path, json=body, headers=auth("learner"))
    assert response.status_code == 403, path


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_CALLS)
def test_anonymous_is_refused_everywhere(
    client: TestClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    assert client.request(method, path, json=body).status_code == 401, path


def test_an_editor_cannot_publish(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    # The one role boundary that matters: whoever writes the content does not get
    # to decide it is ready.
    entry = VocabularyEntry(
        headword="invoice", part_of_speech="noun", meaning_en="a bill", meaning_vi="hóa đơn"
    )
    db_session.add(entry)
    db_session.commit()
    give_audio(db_session, entry)

    response = client.post(f"/api/v1/admin/vocabulary/{entry.id}/publish", headers=auth("editor"))
    assert response.status_code == 403


# --- topic CRUD ---------------------------------------------------------


def _make_topic(db: Session, slug: str, name: str) -> Topic:
    topic = Topic(slug=slug, name=name, status="published")
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def test_editing_a_topic_keeps_its_words(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = _make_topic(db_session, "biz", "Business")
    entry = VocabularyEntry(
        headword="invoice", part_of_speech="noun", meaning_en="a bill", meaning_vi="hóa đơn"
    )
    db_session.add(entry)
    db_session.commit()
    db_session.add(VocabularyTopic(entry_id=entry.id, topic_id=topic.id))
    db_session.commit()

    response = client.patch(
        f"/api/v1/admin/topics/{topic.id}",
        json={"name": "Kinh doanh", "position": 3},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kinh doanh"
    assert body["position"] == 3
    assert body["entry_count"] == 1

    refreshed = db_session.get(Topic, topic.id)
    assert refreshed is not None and refreshed.name == "Kinh doanh"
    assert db_session.get(VocabularyEntry, entry.id) is not None


def test_duplicate_topic_slug_is_a_conflict(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _make_topic(db_session, "biz", "Business")
    topic = _make_topic(db_session, "travel", "Travel")
    response = client.patch(
        f"/api/v1/admin/topics/{topic.id}", json={"slug": "biz"}, headers=auth("editor")
    )
    assert response.status_code == 409


def test_deleting_a_topic_unties_words_but_keeps_them(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    topic = _make_topic(db_session, "biz", "Business")
    entry = VocabularyEntry(
        headword="invoice", part_of_speech="noun", meaning_en="a bill", meaning_vi="hóa đơn"
    )
    db_session.add(entry)
    db_session.commit()
    db_session.add(VocabularyTopic(entry_id=entry.id, topic_id=topic.id))
    dict_item = DictationItem(transcript="The meeting is at noon.", topic_id=topic.id)
    db_session.add(dict_item)
    db_session.commit()

    response = client.delete(f"/api/v1/admin/topics/{topic.id}", headers=auth("admin"))
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.get(Topic, topic.id) is None
    # Từ và câu nghe sống sót, chỉ mất liên kết chủ đề.
    assert db_session.get(VocabularyEntry, entry.id) is not None
    assert db_session.query(VocabularyTopic).count() == 0
    assert db_session.get(DictationItem, dict_item.id).topic_id is None


def test_an_editor_cannot_delete_a_topic(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    # Xoá thứ người học đang thấy là quyền của admin, như publish.
    topic = _make_topic(db_session, "biz", "Business")
    response = client.delete(f"/api/v1/admin/topics/{topic.id}", headers=auth("editor"))
    assert response.status_code == 403
    assert db_session.get(Topic, topic.id) is not None


# --- parse ----------------------------------------------------------------


def test_parse_reports_rows_and_writes_nothing(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    response = client.post(
        "/api/v1/admin/vocabulary/parse", json={"raw_text": PASTE}, headers=auth("editor")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok_count"] == 2
    assert body["error_count"] == 0
    # The whole point of splitting parse from commit.
    assert db_session.query(VocabularyEntry).count() == 0


def test_parse_reports_every_problem_not_just_the_first(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    raw = "no-pipes-here\n| noun | | en | vi\ninvoice | verbo | | en | vi\n"
    body = client.post(
        "/api/v1/admin/vocabulary/parse", json={"raw_text": raw}, headers=auth("editor")
    ).json()
    assert body["error_count"] == 3


def test_parse_catches_a_duplicate_inside_the_paste(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    raw = "invoice | noun | | a bill | hóa đơn\ninvoice | noun | | a bill | hóa đơn\n"
    rows = client.post(
        "/api/v1/admin/vocabulary/parse", json={"raw_text": raw}, headers=auth("editor")
    ).json()["rows"]
    assert any("duplicate of line 1" in problem for problem in rows[1]["problems"])


# --- commit ---------------------------------------------------------------


def test_commit_creates_drafts_only(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    rows = client.post(
        "/api/v1/admin/vocabulary/parse", json={"raw_text": PASTE}, headers=auth("editor")
    ).json()["rows"]

    response = client.post("/api/v1/admin/vocabulary", json={"rows": rows}, headers=auth("editor"))
    assert response.status_code == 201
    assert response.json()["created"] == 2
    statuses = {entry.status for entry in db_session.query(VocabularyEntry).all()}
    assert statuses == {"draft"}


def test_commit_saves_good_rows_even_when_a_later_one_duplicates(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Reproduces the real failure: one duplicate mid-batch used to roll back
    every row already flushed in the request while `created` still counted
    them — the response said success and half the paste never landed."""
    headers = auth("editor")
    seed = client.post(
        "/api/v1/admin/vocabulary",
        json={
            "rows": [
                {
                    "line": 1,
                    "headword": "invoice",
                    "part_of_speech": "noun",
                    "meaning_en": "a bill",
                    "meaning_vi": "hóa đơn",
                    "problems": [],
                }
            ]
        },
        headers=headers,
    )
    assert seed.json()["created"] == 1

    rows = client.post(
        "/api/v1/admin/vocabulary/parse",
        json={
            "raw_text": "deadline | noun | | the latest time | hạn chót\n"
            "invoice | noun | | a bill | hóa đơn\n"
            "warehouse | noun | | a storage building | nhà kho\n"
        },
        headers=headers,
    ).json()["rows"]

    body = client.post("/api/v1/admin/vocabulary", json={"rows": rows}, headers=headers).json()
    assert body["created"] == 2
    assert body["skipped"] == 1
    assert body["problems"] == ["line 2: 'invoice' (noun) already exists"]
    headwords = {entry.headword for entry in db_session.query(VocabularyEntry).all()}
    assert headwords == {"invoice", "deadline", "warehouse"}


def test_commit_skips_rows_that_still_have_problems(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    rows = [
        {
            "line": 1,
            "headword": "invoice",
            "part_of_speech": "noun",
            "meaning_en": "a bill",
            "meaning_vi": "hóa đơn",
            "problems": ["still broken"],
        }
    ]
    body = client.post(
        "/api/v1/admin/vocabulary", json={"rows": rows}, headers=auth("editor")
    ).json()
    assert body == {
        "created": 0,
        "skipped": 1,
        "problems": ["line 1: skipped, still has problems"],
    }
    assert db_session.query(VocabularyEntry).count() == 0


def test_commit_records_the_author(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    headers = auth("editor")
    rows = client.post(
        "/api/v1/admin/vocabulary/parse", json={"raw_text": PASTE}, headers=headers
    ).json()["rows"]
    client.post("/api/v1/admin/vocabulary", json={"rows": rows}, headers=headers)
    assert all(entry.created_by is not None for entry in db_session.query(VocabularyEntry).all())


def test_dictation_commit_creates_items_without_audio(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    # A draft exists before its audio does; the worker fills it in later.
    raw = "The quarterly report is due Friday.\nPlease submit your expense claims.\n"
    headers = auth("editor")
    rows = client.post(
        "/api/v1/admin/dictation/parse", json={"raw_text": raw}, headers=headers
    ).json()["rows"]
    assert (
        client.post("/api/v1/admin/dictation", json={"rows": rows}, headers=headers).json()[
            "created"
        ]
        == 2
    )
    items = db_session.query(DictationItem).all()
    assert all(item.audio_asset_id is None and item.status == "draft" for item in items)


# --- publishing -----------------------------------------------------------


def test_publishing_is_blocked_without_audio(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    entry = VocabularyEntry(
        headword="invoice", part_of_speech="noun", meaning_en="a bill", meaning_vi="hóa đơn"
    )
    db_session.add(entry)
    db_session.commit()

    response = client.post(f"/api/v1/admin/vocabulary/{entry.id}/publish", headers=auth("admin"))
    assert response.status_code == 409
    assert "missing" in response.json()["detail"]


def test_publishing_succeeds_once_audio_is_current(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    entry = VocabularyEntry(
        headword="invoice", part_of_speech="noun", meaning_en="a bill", meaning_vi="hóa đơn"
    )
    db_session.add(entry)
    db_session.commit()
    give_audio(db_session, entry)

    response = client.post(f"/api/v1/admin/vocabulary/{entry.id}/publish", headers=auth("admin"))
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    db_session.refresh(entry)
    assert entry.published_by is not None
    assert entry.published_at is not None


def test_editing_the_headword_blocks_publishing_again(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    # The defect this gate exists for: the clips still say the old word, and
    # without the check nothing would notice.
    entry = VocabularyEntry(
        headword="recieve", part_of_speech="verb", meaning_en="to get", meaning_vi="nhận"
    )
    db_session.add(entry)
    db_session.commit()
    give_audio(db_session, entry)
    headers = auth("admin")
    published = client.post(f"/api/v1/admin/vocabulary/{entry.id}/publish", headers=headers)
    assert published.status_code == 200

    patched = client.patch(
        f"/api/v1/admin/vocabulary/{entry.id}",
        json={"headword": "receive"},
        headers=headers,
    )
    assert patched.json()["publishable"] is False
    assert {slot["state"] for slot in patched.json()["audio"]} == {"stale"}

    response = client.post(f"/api/v1/admin/vocabulary/{entry.id}/publish", headers=headers)
    assert response.status_code == 409
    assert "stale" in response.json()["detail"]


def test_dictation_publishing_is_blocked_without_audio(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    item = DictationItem(transcript="The report is due Friday.", difficulty=3)
    db_session.add(item)
    db_session.commit()

    response = client.post(f"/api/v1/admin/dictation/{item.id}/publish", headers=auth("admin"))
    assert response.status_code == 409
    # The message has to explain why this matters more here than for vocabulary.
    assert "answer key" in response.json()["detail"]


def test_the_database_also_refuses_a_published_item_without_audio(db_session: Session) -> None:
    # Belt and braces: the endpoint checks, and so does the schema.
    from sqlalchemy.exc import IntegrityError

    item = DictationItem(transcript="The report is due Friday.", difficulty=3, status="published")
    db_session.add(item)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- soạn đề: cổng chặn hai tầng (ADR-007 §2.8) -----------------------------


def _reading_paste() -> str:
    return """[PASSAGE] Thông báo
The lobby entrance will be closed from Wednesday.

[QUESTION]
What is the notice mainly about?
(A) A change of address
(B) Building maintenance
(C) A new tenant
(D) A rent increase
answer: B
source: original
explanation: Đoạn văn nói về việc đóng cửa sảnh để bảo trì.
"""


def test_a_test_refuses_to_publish_while_a_question_is_still_draft(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Chặn ở tầng đề, không chỉ tầng câu.

    Cùng lý do cây dictation lọc `published` ở cả bốn tầng: một câu nháp nằm
    trong đề đã publish sẽ lọt ra tới người học, và nội dung đó trông hoàn toàn
    bình thường — không có gì để phát hiện.
    """
    headers = auth("admin")
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "gate-test", "title": "Gate", "kind": "mini"},
        headers=headers,
    )
    parsed = client.post(
        "/api/v1/admin/tests/gate-test/parts/7/parse",
        json={"raw_text": _reading_paste()},
        headers=headers,
    ).json()
    committed = client.post(
        "/api/v1/admin/tests/gate-test/parts",
        json={"part": 7, "groups": parsed["groups"]},
        headers=headers,
    )
    assert committed.status_code == 201

    refused = client.post("/api/v1/admin/tests/gate-test/publish", headers=headers)
    assert refused.status_code == 409
    # Lời từ chối phải nêu ĐÚNG câu nào, không chỉ "còn câu chưa xuất bản":
    # người soạn cần biết đi sửa ở đâu, và số câu là cách họ định vị.
    assert "147" in refused.json()["detail"]


def test_commit_refuses_a_paste_that_still_has_problems(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    headers = auth("admin")
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "gate-test-2", "title": "Gate 2", "kind": "mini"},
        headers=headers,
    )
    # `source:` bị bỏ đi — không có giá trị mặc định ở bất kỳ tầng nào (§2.5).
    parsed = client.post(
        "/api/v1/admin/tests/gate-test-2/parts/7/parse",
        json={"raw_text": _reading_paste().replace("source: original\n", "")},
        headers=headers,
    ).json()
    assert parsed["error_count"] == 1

    refused = client.post(
        "/api/v1/admin/tests/gate-test-2/parts",
        json={"part": 7, "groups": parsed["groups"]},
        headers=headers,
    )
    assert refused.status_code == 400


def test_moving_a_test_between_collections_and_out_of_one(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Khoá vắng mặt và khoá bằng null là hai chuyện khác nhau.

    `collection_slug: null` là cách gỡ đề khỏi bộ. Một phép gộp `giá trị or cũ`
    không phân biệt được nó với "không gửi khoá này", và lỗi thì im lặng: lệnh
    gỡ trả về 200 mà không đổi gì.
    """
    headers = auth("admin")
    for slug in ("bo-a", "bo-b"):
        assert (
            client.post(
                "/api/v1/admin/test-collections",
                json={"slug": slug, "title": slug.upper()},
                headers=headers,
            ).status_code
            == 201
        )
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "di-chuyen", "title": "Di chuyển", "collection_slug": "bo-a"},
        headers=headers,
    )

    moved = client.patch(
        "/api/v1/admin/tests/di-chuyen", json={"collection_slug": "bo-b"}, headers=headers
    )
    assert moved.json()["collection_slug"] == "bo-b"

    # Sửa tên mà KHÔNG gửi collection_slug: bộ đề phải giữ nguyên.
    renamed = client.patch(
        "/api/v1/admin/tests/di-chuyen", json={"title": "Tên mới"}, headers=headers
    )
    assert renamed.json() == {**moved.json(), "title": "Tên mới"}

    removed = client.patch(
        "/api/v1/admin/tests/di-chuyen", json={"collection_slug": None}, headers=headers
    )
    assert removed.json()["collection_slug"] is None


def test_renaming_a_collection_leaves_its_slug_alone(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Đổi tên là đổi NHÃN, không phải đổi danh tính.

    `slug` nằm trong mọi URL của khu quản trị và là thứ các script nội dung tra
    cứu. Cho sửa nó từ màn đổi tên nghĩa là một cú sửa lỗi chính tả làm hỏng mọi
    liên kết đã lưu cùng lúc, mà không có gì chuyển hướng chúng. `CollectionUpdate`
    không khai `slug`, nên gửi lên cũng bị bỏ qua — và đây là chỗ pin điều đó.
    """
    headers = auth("editor")
    client.post(
        "/api/v1/admin/test-collections",
        json={"slug": "bo-goc", "title": "Tên gõ sai", "year": 2024},
        headers=headers,
    )

    renamed = client.patch(
        "/api/v1/admin/test-collections/bo-goc",
        json={"title": "Tên đã sửa", "slug": "bo-moi"},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Tên đã sửa"
    assert renamed.json()["slug"] == "bo-goc"
    # Trường không gửi thì không bị đụng tới; gửi null thì mới xoá.
    assert renamed.json()["year"] == 2024
    assert (
        client.patch(
            "/api/v1/admin/test-collections/bo-goc", json={"year": None}, headers=headers
        ).json()["year"]
        is None
    )
    # Và kiểm ở nguồn chứ không chỉ ở response vừa trả: slug cũ vẫn là slug duy nhất.
    slugs = {
        row["slug"] for row in client.get("/api/v1/admin/test-collections", headers=headers).json()
    }
    assert "bo-goc" in slugs
    assert "bo-moi" not in slugs


def test_a_published_collection_can_still_be_renamed(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Lỗi chính tả trong một cái tên chỉ lộ ra sau khi có người nhìn thấy nó.

    Mà lúc đó chính là lúc bộ đề đã ra ngoài. Bắt gỡ xuất bản để sửa một chữ sẽ
    làm bộ đề biến mất khỏi mắt học viên vì một dấu phẩy.
    """
    headers = auth("admin")
    client.post(
        "/api/v1/admin/test-collections",
        json={"slug": "da-phat-hanh", "title": "Bộ đề"},
        headers=headers,
    )
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "de-1", "title": "Đề 1", "collection_slug": "da-phat-hanh"},
        headers=headers,
    )
    client.post("/api/v1/admin/tests/de-1/archive", headers=headers)

    renamed = client.patch(
        "/api/v1/admin/test-collections/da-phat-hanh",
        json={"title": "Bộ đề 2024"},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Bộ đề 2024"


def test_a_learner_cannot_rename_a_collection(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    admin = auth("admin")
    client.post(
        "/api/v1/admin/test-collections",
        json={"slug": "khoa", "title": "Bộ đề"},
        headers=admin,
    )
    assert (
        client.patch(
            "/api/v1/admin/test-collections/khoa",
            json={"title": "Bị đổi"},
            headers=auth("learner"),
        ).status_code
        == 403
    )


def test_a_collection_refuses_to_publish_with_no_published_test(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Tầng thứ ba của cùng một cổng chặn.

    Bộ đề mở ra rỗng không là thứ người học không giải thích được, và không có
    gì trong giao diện nói cho họ biết vì sao.
    """
    headers = auth("admin")
    client.post(
        "/api/v1/admin/test-collections", json={"slug": "rong", "title": "Rỗng"}, headers=headers
    )
    refused = client.post("/api/v1/admin/test-collections/rong/publish", headers=headers)
    assert refused.status_code == 409
    assert "chưa có đề nào" in refused.json()["detail"]


def test_a_passage_image_without_alt_text_is_refused(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Ảnh làm ngữ liệu bắt buộc có chữ thay ảnh — khác hẳn ảnh Part 1.

    Ở Part 1 mô tả quá kỹ là lộ đáp án. Ở Part 6/7 thì ảnh *là* ngữ liệu, nên
    thiếu chữ thay ảnh là một câu hỏi người dùng máy đọc màn hình không trả lời
    được. Đó không phải bất tiện, đó là không làm được bài.
    """
    headers = auth("admin")
    client.post("/api/v1/admin/tests", json={"slug": "alt-test", "title": "Alt"}, headers=headers)
    parsed = client.post(
        "/api/v1/admin/tests/alt-test/parts/7/parse",
        json={"raw_text": _reading_paste()},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/admin/tests/alt-test/parts",
        json={"part": 7, "groups": parsed["groups"]},
        headers=headers,
    )
    (stimulus,) = client.get("/api/v1/admin/tests/alt-test/sets", headers=headers).json()
    # Ô rỗng vẫn trả về, để người soạn có chỗ bấm vào mà gắn ảnh.
    assert [passage["slot"] for passage in stimulus["passages"]] == [1, 2, 3]

    blank = ImageAsset(
        storage_key="image/aa/blank.jpg",
        source_hash="a" * 64,
        mime_type="image/jpeg",
        size_bytes=10,
        width=10,
        height=10,
        source="uploaded",
        source_url="https://example.com",
        license="CC0",
        attribution="Ai đó",
        alt_text=None,
    )
    db_session.add(blank)
    db_session.commit()

    refused = client.post(
        f"/api/v1/admin/question-sets/{stimulus['id']}/passage-image",
        json={"slot": 2, "image_id": str(blank.id)},
        headers=headers,
    )
    assert refused.status_code == 409
    assert "chữ thay ảnh" in refused.json()["detail"]


def _part3_paste() -> str:
    return """[SCRIPT] Gọi hỏi đơn hàng
voice: us_female_1
Hi, I'm calling about the chairs we ordered last Monday.
voice: us_male_1
Let me check. They shipped yesterday and arrive on Friday.

[QUESTION]
What is the woman calling about?
(A) A late delivery
(B) A billing error
(C) A product return
(D) A price change
answer: A
source: original
explanation: Người phụ nữ hỏi về đơn ghế đã đặt.
"""


def _commit_part3(client: TestClient, headers: dict[str, str], slug: str) -> dict[str, object]:
    client.post(
        "/api/v1/admin/tests",
        json={"slug": slug, "title": "Nghe", "kind": "mini"},
        headers=headers,
    )
    parsed = client.post(
        f"/api/v1/admin/tests/{slug}/parts/3/parse",
        json={"raw_text": _part3_paste()},
        headers=headers,
    ).json()
    assert (
        client.post(
            f"/api/v1/admin/tests/{slug}/parts",
            json={"part": 3, "groups": parsed["groups"]},
            headers=headers,
        ).status_code
        == 201
    )
    (stimulus,) = client.get(f"/api/v1/admin/tests/{slug}/sets", headers=headers).json()
    assert isinstance(stimulus, dict)
    return stimulus


def test_editing_a_set_script_makes_its_audio_look_stale(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Sửa lời thoại của cụm phải bật cảnh báo lệch cho Part 3/4.

    Trước khi có `PATCH /question-sets/{id}` thì cảnh báo này đúng mà vô dụng:
    bản thu ứng với LỜI THOẠI, lời thoại lại không sửa được, nên `updated_at`
    của cụm không bao giờ vượt `audio_attached_at`. Sửa một câu trong cụm cũng
    không bật được — nó không đụng tới cụm, và đúng ra là không nên.
    """
    headers = auth("admin")
    stimulus = _commit_part3(client, headers, "stale-test")

    clip = AudioAsset(
        storage_key="audio/aa/talk.mp3",
        source_hash="c" * 64,
        voice="us_female_1",
        accent="en-US",
        engine="uploaded",
        engine_version="-",
        duration_ms=9000,
        size_bytes=100,
    )
    db_session.add(clip)
    db_session.commit()

    attached = client.post(
        f"/api/v1/admin/question-sets/{stimulus['id']}/audio",
        json={"asset_id": str(clip.id)},
        headers=headers,
    ).json()
    assert attached["audio_may_be_stale"] is False

    edited = client.patch(
        f"/api/v1/admin/question-sets/{stimulus['id']}",
        json={
            "audio_script": [
                {
                    "text": "Hi, I'm calling about the desks we ordered last Monday.",
                    "voice": "us_female_1",
                },
                {
                    "text": "Let me check. They shipped yesterday and arrive on Friday.",
                    "voice": "us_male_1",
                },
            ]
        },
        headers=headers,
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["audio_script"][0]["text"].endswith("desks we ordered last Monday.")
    assert body["audio_may_be_stale"] is True


def test_editing_a_set_script_sends_its_published_questions_back_to_draft(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Cổng xuất bản soát từng CÂU, nên hạ mỗi cụm là chưa đủ.

    Cụm về nháp mà các câu vẫn `published` thì đề vẫn phát hành bình thường và
    người học vẫn nghe bản thu ứng với lời thoại cũ — không có gì báo.
    """
    headers = auth("admin")
    stimulus = _commit_part3(client, headers, "demote-test")
    (question,) = client.get("/api/v1/admin/tests/demote-test/questions", headers=headers).json()

    # Xuất bản thẳng trong database: cổng chặn đòi audio, mà ở đây đang xét
    # chuyện khác.
    published = client.patch(
        f"/api/v1/admin/questions/{question['id']}",
        json={"explanation": "x"},
        headers=headers,
    )
    assert published.status_code == 200

    client.patch(
        f"/api/v1/admin/question-sets/{stimulus['id']}",
        json={"title": "Tên khác"},
        headers=headers,
    )
    (after,) = client.get("/api/v1/admin/tests/demote-test/questions", headers=headers).json()
    assert after["status"] == "draft"


def test_a_question_refuses_a_script_that_belongs_to_its_set(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Part 3/4: lời thoại ở cụm, và câu phải NÓI RA chỗ sửa đúng.

    Ghi im lặng vào `question.audio_script` sẽ tạo ra một lời thoại thứ hai mà
    không bản thu nào ứng với — và người soát bản thu sẽ đối chiếu nhầm nó.
    """
    headers = auth("admin")
    stimulus = _commit_part3(client, headers, "script-owner-test")
    (question,) = client.get(
        "/api/v1/admin/tests/script-owner-test/questions", headers=headers
    ).json()

    refused = client.patch(
        f"/api/v1/admin/questions/{question['id']}",
        json={"audio_script": [{"text": "Hello.", "voice": "us_female_1"}]},
        headers=headers,
    )
    assert refused.status_code == 400
    assert stimulus["id"] in refused.json()["detail"]


def test_an_unknown_voice_is_refused_at_the_form_not_at_synthesis(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Tên giọng sai chỉ nổ ở bước sinh audio, cách chỗ gõ vào hàng ngày."""
    headers = auth("admin")
    stimulus = _commit_part3(client, headers, "voice-test")

    refused = client.patch(
        f"/api/v1/admin/question-sets/{stimulus['id']}",
        json={"audio_script": [{"text": "Hello.", "voice": "us_female_9"}]},
        headers=headers,
    )
    assert refused.status_code == 400
    assert "us_female_1" in refused.json()["detail"]


def test_a_listening_set_takes_one_graphic_and_only_slot_one(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Vài cụm cuối Part 3/4 có một hình dùng chung ("Look at the graphic").

    Ảnh về CỤM chứ không về câu: đề in nó một lần cạnh cả ba câu, đúng như đoạn
    văn Part 7. Nhưng chỉ MỘT hình — mở ba ô ở đây là mời người soạn điền vào
    hai ô không tồn tại trong đề thật.
    """
    headers = auth("admin")
    stimulus = _commit_part3(client, headers, "graphic-test")

    chart = ImageAsset(
        storage_key="image/aa/chart.png",
        source_hash="d" * 64,
        mime_type="image/png",
        size_bytes=10,
        width=10,
        height=10,
        source="uploaded",
        source_url="https://example.com",
        license="CC0",
        attribution="Ai đó",
        # Bắt buộc, và ở đây KHÔNG lộ đáp án: người học vẫn phải nghe mới trả lời
        # được. Khác Part 1, nơi bức ảnh chính là toàn bộ câu hỏi.
        alt_text="Lịch trình phòng họp",
    )
    db_session.add(chart)
    db_session.commit()

    attached = client.post(
        f"/api/v1/admin/question-sets/{stimulus['id']}/passage-image",
        json={"slot": 1, "image_id": str(chart.id)},
        headers=headers,
    )
    assert attached.status_code == 200
    assert attached.json()["passages"][0]["image_url"] is not None

    refused = client.post(
        f"/api/v1/admin/question-sets/{stimulus['id']}/passage-image",
        json={"slot": 2, "image_id": str(chart.id)},
        headers=headers,
    )
    assert refused.status_code == 400
    assert "một hình" in refused.json()["detail"]


def _make_test_with_one_question(
    client: TestClient, headers: dict[str, str], slug: str
) -> dict[str, object]:
    client.post(
        "/api/v1/admin/tests",
        json={"slug": slug, "title": slug, "kind": "mini"},
        headers=headers,
    )
    parsed = client.post(
        f"/api/v1/admin/tests/{slug}/parts/7/parse",
        json={"raw_text": _reading_paste()},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/admin/tests/{slug}/parts",
        json={"part": 7, "groups": parsed["groups"]},
        headers=headers,
    )
    (question,) = client.get(f"/api/v1/admin/tests/{slug}/questions", headers=headers).json()
    assert isinstance(question, dict)
    return question


def test_deleting_a_test_takes_its_questions_and_sets_with_it(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Không được để lại câu mồ côi.

    `practice_test_question.test_id` là CASCADE nên hàng liên kết tự biến mất,
    nhưng `question` thì sống sót — và một câu không thuộc đề nào KHÔNG hiện ở
    màn quản trị nào (`_link_or_409` giả định nó phải thuộc một đề). Nó nằm lại
    trong database vĩnh viễn và không ai với tới để dọn.
    """
    headers = auth("admin")
    question = _make_test_with_one_question(client, headers, "gone-test")
    question_id = uuid.UUID(str(question["id"]))
    set_id = uuid.UUID(str(question["set_id"]))

    assert client.delete("/api/v1/admin/tests/gone-test", headers=headers).status_code == 204

    assert db_session.get(Question, question_id) is None
    # Cụm rỗng cũng phải đi theo: nó không hiện ở đâu và không ai với tới được.
    assert db_session.get(QuestionSet, set_id) is None


def test_a_test_with_attempts_refuses_deletion_and_names_the_way_out(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """`attempt.test_id` là RESTRICT: xoá thẳng sẽ là IntegrityError → 500.

    Và lời từ chối phải nêu lối thoát, vì nó có thật: `archived` giấu đề khỏi
    người học mà không làm mồ côi lịch sử làm bài của họ.
    """
    headers = auth("admin")
    _make_test_with_one_question(client, headers, "sat-test")

    test = db_session.scalars(select(PracticeTest).where(PracticeTest.slug == "sat-test")).one()
    auth("learner")  # fixture tạo user theo vai trò khi được gọi
    learner = db_session.scalars(select(User).where(User.role == "learner")).one()
    db_session.add(Attempt(user_id=learner.id, test_id=test.id))
    db_session.commit()

    refused = client.delete("/api/v1/admin/tests/sat-test", headers=headers)
    assert refused.status_code == 409
    assert "Lưu trữ" in refused.json()["detail"]

    # Và lối thoát đó phải dùng được ngay.
    archived = client.post(
        "/api/v1/admin/tests/sat-test/archive", json={"archived": True}, headers=headers
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


def test_a_collection_with_tests_refuses_deletion(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Cấp duy nhất mà database KHÔNG chặn, nên phải chặn ở đây.

    `practice_test.collection_id` là SET NULL: xoá bộ đề không lỗi, không mất
    dữ liệu, và lặng lẽ cắt đường của người học tới từng đề bên trong — vì đề
    không thuộc bộ nào thì không xuất hiện ở đâu cả.
    """
    headers = auth("admin")
    client.post(
        "/api/v1/admin/test-collections",
        json={"slug": "box", "title": "Bộ đề"},
        headers=headers,
    )
    _make_test_with_one_question(client, headers, "in-box")
    client.patch("/api/v1/admin/tests/in-box", json={"collection_slug": "box"}, headers=headers)

    refused = client.delete("/api/v1/admin/test-collections/box", headers=headers)
    assert refused.status_code == 409
    assert "còn 1 đề" in refused.json()["detail"]


def test_deleting_a_question_frees_its_number_for_the_next_paste(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Số câu để lại CHỖ TRỐNG, không dồn lại.

    `commit_part` chọn "số chưa dùng trong khoảng của part", nên ô vừa xoá được
    lấy lại ở lần dán sau. Dồn số là suy ra số câu thay vì lưu nó (ADR-007 §2.6)
    và sẽ đổi tên những câu không ai đụng vào.
    """
    headers = auth("admin")
    question = _make_test_with_one_question(client, headers, "gap-test")
    assert question["number"] == 147

    assert (
        client.delete(f"/api/v1/admin/questions/{question['id']}", headers=headers).status_code
        == 204
    )

    parsed = client.post(
        "/api/v1/admin/tests/gap-test/parts/7/parse",
        json={"raw_text": _reading_paste()},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/admin/tests/gap-test/parts",
        json={"part": 7, "groups": parsed["groups"]},
        headers=headers,
    )
    (again,) = client.get("/api/v1/admin/tests/gap-test/questions", headers=headers).json()
    assert again["number"] == 147


# --- xoá cưỡng chế (force): dev xoá được nội dung đã có người làm -------------


def _publish(client: TestClient, headers: dict[str, str], slug: str) -> None:
    for question in client.get(f"/api/v1/admin/tests/{slug}/questions", headers=headers).json():
        assert (
            client.post(
                f"/api/v1/admin/questions/{question['id']}/publish", headers=headers
            ).status_code
            == 200
        )
    assert client.post(f"/api/v1/admin/tests/{slug}/publish", headers=headers).status_code == 200


def _attempt_with_answer(
    client: TestClient, headers: dict[str, str], learner: dict[str, str], slug: str
) -> str:
    """Một lượt làm thật, đã trả lời một câu — tức là có `attempt_item`."""
    state = client.post(
        "/api/v1/attempts",
        json={"test_slug": slug, "parts": [], "review_mode": "exam"},
        headers=learner,
    )
    assert state.status_code == 201, state.json()
    body = state.json()
    (question,) = body["questions"]
    answered = client.patch(
        f"/api/v1/attempts/{body['id']}/questions/{question['id']}",
        json={"selected_option_id": question["options"][0]["id"]},
        headers=learner,
    )
    assert answered.status_code == 200, answered.json()
    return str(body["id"])


def test_force_deleting_a_test_removes_its_attempts_questions_and_sets(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """`?force=true` là lối thoát cho giai đoạn dev: xoá cả lịch sử làm bài.

    Không force thì 409 như trước — và có force thì KHÔNG được để lại gì: lượt
    làm, câu trả lời, câu hỏi, cụm và chính đề đó.
    """
    from app.models import AttemptItem, QuestionOption

    headers = auth("admin")
    question = _make_test_with_one_question(client, headers, "wipe-test")
    question_id = uuid.UUID(str(question["id"]))
    set_id = uuid.UUID(str(question["set_id"]))
    _publish(client, headers, "wipe-test")
    attempt_id = _attempt_with_answer(client, headers, auth("learner"), "wipe-test")

    still_refused = client.delete("/api/v1/admin/tests/wipe-test", headers=headers)
    assert still_refused.status_code == 409

    wiped = client.delete("/api/v1/admin/tests/wipe-test?force=true", headers=headers)
    assert wiped.status_code == 204

    assert db_session.get(Attempt, uuid.UUID(attempt_id)) is None
    assert db_session.scalars(select(AttemptItem)).all() == []
    assert db_session.scalars(select(QuestionOption)).all() == []
    assert db_session.get(Question, question_id) is None
    assert db_session.get(QuestionSet, set_id) is None


def test_force_deleting_a_question_removes_its_answers(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Xoá câu đã có người trả lời: câu trả lời phải đi trước (RESTRICT)."""
    from app.models import AttemptItem

    headers = auth("admin")
    question = _make_test_with_one_question(client, headers, "wipe-q")
    question_id = uuid.UUID(str(question["id"]))
    _publish(client, headers, "wipe-q")
    _attempt_with_answer(client, headers, auth("learner"), "wipe-q")

    refused = client.delete(f"/api/v1/admin/questions/{question['id']}", headers=headers)
    assert refused.status_code == 409

    wiped = client.delete(f"/api/v1/admin/questions/{question['id']}?force=true", headers=headers)
    assert wiped.status_code == 204

    assert db_session.get(Question, question_id) is None
    assert db_session.scalars(select(AttemptItem)).all() == []
    # Đề chỉ có đúng câu đó: lượt làm rỗng cũng không được để lại.
    assert db_session.scalars(select(Attempt)).all() == []


def test_force_deleting_a_collection_takes_its_tests_and_attempts(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Cây ba tầng đi cả cây: bộ đề -> đề -> câu, kèm lượt làm ở dưới."""
    headers = auth("admin")
    client.post(
        "/api/v1/admin/test-collections",
        json={"slug": "wipe-box", "title": "Bộ đề"},
        headers=headers,
    )
    _make_test_with_one_question(client, headers, "wipe-in-box")
    client.patch(
        "/api/v1/admin/tests/wipe-in-box",
        json={"collection_slug": "wipe-box"},
        headers=headers,
    )
    _publish(client, headers, "wipe-in-box")
    _attempt_with_answer(client, headers, auth("learner"), "wipe-in-box")

    still_refused = client.delete("/api/v1/admin/test-collections/wipe-box", headers=headers)
    assert still_refused.status_code == 409

    wiped = client.delete("/api/v1/admin/test-collections/wipe-box?force=true", headers=headers)
    assert wiped.status_code == 204

    assert db_session.scalars(select(PracticeTest)).all() == []
    assert db_session.scalars(select(Question)).all() == []
    assert db_session.scalars(select(Attempt)).all() == []


def test_force_delete_is_refused_in_production(
    client: TestClient,
    auth: Callable[[str], dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lịch sử học viên là bất khả xâm phạm: force chỉ tồn tại ngoài production."""
    from app.core.config import Settings

    monkeypatch.setattr(Settings, "is_production", property(lambda self: True))

    headers = auth("admin")
    _make_test_with_one_question(client, headers, "prod-test")
    _publish(client, headers, "prod-test")
    _attempt_with_answer(client, headers, auth("learner"), "prod-test")

    refused = client.delete("/api/v1/admin/tests/prod-test?force=true", headers=headers)
    assert refused.status_code == 403
    assert "production" in refused.json()["detail"]

    # Và production vẫn chặn cả đường thường.
    assert client.delete("/api/v1/admin/tests/prod-test", headers=headers).status_code == 409


def test_attached_media_actually_reaches_the_question_list(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Gắn xong rồi thì danh sách câu phải THẤY nó.

    `_question_admin` dựng URL từ một bản đồ asset truyền vào. Bản đầu để tham
    số đó tuỳ chọn (`= None`) và không call site nào truyền — nên `lookup` luôn
    rỗng và mọi câu trả về `audio_url=None`. Media gắn xong vẫn hiện "chưa có
    bản thu", và không có gì báo vì phản hồi vẫn hợp lệ, chỉ sai.
    """
    headers = auth("admin")
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "media-list", "title": "Media", "kind": "mini"},
        headers=headers,
    )
    parsed = client.post(
        "/api/v1/admin/tests/media-list/parts/1/parse",
        json={
            "raw_text": (
                "[QUESTION]\nvoice: us_female_1\n"
                "Look at the picture marked number one in your test book.\n"
                "(A) A man is painting a wall.\n(B) A man is climbing a ladder.\n"
                "(C) A man is washing a car.\n(D) A man is planting a tree.\n"
                "answer: B\nsource: original\n"
            )
        },
        headers=headers,
    ).json()
    client.post(
        "/api/v1/admin/tests/media-list/parts",
        json={"part": 1, "groups": parsed["groups"]},
        headers=headers,
    )
    (question,) = client.get("/api/v1/admin/tests/media-list/questions", headers=headers).json()

    clip = AudioAsset(
        storage_key="audio/bb/one.mp3",
        source_hash="e" * 64,
        voice="uploaded",
        accent="en-US",
        engine="uploaded",
        engine_version="-",
        duration_ms=4000,
        size_bytes=90,
        source="uploaded",
    )
    photo = ImageAsset(
        storage_key="image/bb/one.jpg",
        source_hash="f" * 64,
        mime_type="image/jpeg",
        size_bytes=90,
        width=640,
        height=480,
        source="uploaded",
        source_url="https://example.com",
        license="CC0",
        attribution="Ai đó",
    )
    db_session.add_all([clip, photo])
    db_session.commit()

    for path, body in (
        (f"/api/v1/admin/questions/{question['id']}/audio", {"asset_id": str(clip.id)}),
        (f"/api/v1/admin/questions/{question['id']}/image", {"asset_id": str(photo.id)}),
    ):
        assert client.post(path, json=body, headers=headers).status_code == 200

    (after,) = client.get("/api/v1/admin/tests/media-list/questions", headers=headers).json()
    assert after["audio_url"] is not None
    assert after["image_url"] is not None
    # Và cổng chặn không còn kêu thiếu media nữa.
    assert after["problems"] == []
