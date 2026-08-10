"""The content admin surface.

Two things are checked on every endpoint, because both fail silently:
a learner must get 403, and an import must never land as `published`.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.media import source_hash
from app.core.security import create_access_token
from app.models import DictationItem, User, VocabularyAudio, VocabularyEntry
from app.models.image import ImageAsset
from tests.test_domain_model import make_audio

PASTE = (
    "invoice | noun | /ˈɪnvɔɪs/ | a bill | hóa đơn | Pay the invoice. | Thanh toán hóa đơn.\n"
    "deadline | noun | /ˈdedlaɪn/ | the latest time | hạn chót\n"
)


@pytest.fixture()
def auth(db_session: Session) -> Callable[[str], dict[str, str]]:
    """Header factory: `auth("admin")` gives headers for an admin.

    Cached per role, so calling it twice in one test reuses the same account
    rather than colliding on the unique email.
    """
    cache: dict[str, dict[str, str]] = {}

    def make(role: str) -> dict[str, str]:
        if role not in cache:
            user = User(email=f"{role}@example.com", hashed_password="x", role=role)
            db_session.add(user)
            db_session.commit()
            cache[role] = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
        return cache[role]

    return make


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
    ("POST", "/api/v1/admin/vocabulary/parse", {"raw_text": "a"}),
    ("POST", "/api/v1/admin/vocabulary", {"rows": []}),
    ("GET", "/api/v1/admin/vocabulary", None),
    ("POST", "/api/v1/admin/dictation/parse", {"raw_text": "a"}),
    ("POST", "/api/v1/admin/dictation", {"rows": []}),
    ("GET", "/api/v1/admin/dictation", None),
    ("GET", "/api/v1/admin/test-collections", None),
    ("POST", "/api/v1/admin/test-collections", {"slug": "x", "title": "X"}),
    ("POST", "/api/v1/admin/test-collections/x/publish", None),
    ("GET", "/api/v1/admin/tests", None),
    ("PATCH", "/api/v1/admin/tests/x", {"title": "X"}),
    ("GET", "/api/v1/admin/tests/x/sets", None),
    (
        "PATCH",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000",
        {"explanation": "x"},
    ),
    (
        "POST",
        "/api/v1/admin/question-sets/00000000-0000-0000-0000-000000000000/passage-image",
        {"slot": 1},
    ),
    ("POST", "/api/v1/admin/tests", {"slug": "x", "title": "X"}),
    ("GET", "/api/v1/admin/tests/x", None),
    ("GET", "/api/v1/admin/tests/x/questions", None),
    ("POST", "/api/v1/admin/tests/x/parts/7/parse", {"raw_text": "a"}),
    ("POST", "/api/v1/admin/tests/x/parts", {"part": 7, "groups": []}),
    ("POST", "/api/v1/admin/tests/x/publish", None),
    (
        "POST",
        "/api/v1/admin/questions/00000000-0000-0000-0000-000000000000/publish",
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
