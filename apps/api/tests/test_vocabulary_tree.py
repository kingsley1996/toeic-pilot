"""Cây từ vựng: collection -> collection_item -> topic.

Cùng khuôn với `tests/test_dictation_tree.py`: mỗi tầng phải TỰ lọc `published`,
và chuyện admin xoá một nút chỉ gỡ liên kết chứ không xoá nội dung bên trong.
"""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Topic, User, VocabularyCollection, VocabularyCollectionItem

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture()
def auth(db_session: Session) -> Callable[[str], dict[str, str]]:
    cache: dict[str, dict[str, str]] = {}

    def make(role: str) -> dict[str, str]:
        if role not in cache:
            user = User(email=f"{role}@example.com", hashed_password="x", role=role)
            db_session.add(user)
            db_session.commit()
            cache[role] = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
        return cache[role]

    return make


def build_tree(
    db: Session,
    *,
    collection_status: str = "published",
    item_status: str = "published",
    topic_status: str = "published",
    marker: str = "t",
) -> tuple[VocabularyCollection, VocabularyCollectionItem, Topic]:
    collection = VocabularyCollection(
        slug=f"col-{marker}", name=f"Collection {marker}", status=collection_status, position=0
    )
    db.add(collection)
    db.flush()
    item = VocabularyCollectionItem(
        collection_id=collection.id, name=f"Book {marker}", status=item_status, position=0
    )
    db.add(item)
    db.flush()
    topic = Topic(
        slug=f"topic-{marker}",
        name=f"Topic {marker}",
        status=topic_status,
        position=0,
        collection_item_id=item.id,
    )
    db.add(topic)
    db.flush()
    return collection, item, topic


def test_a_draft_collection_is_invisible(client: TestClient, db_session: Session) -> None:
    build_tree(db_session)
    build_tree(db_session, collection_status="draft", marker="d")
    db_session.commit()

    body = client.get("/api/v1/vocabulary-collections").json()
    assert [row["slug"] for row in body] == ["col-t"]


def test_a_draft_item_stays_invisible_under_a_published_collection(
    client: TestClient, db_session: Session
) -> None:
    # Nút nháp phải gắn DƯỚI CHÍNH cây đang publish mới là trường hợp đáng thử —
    # một tuyển tập draft nằm riêng lẻ thì endpoint nào cũng lọc được.
    collection, item, _ = build_tree(db_session)
    draft_item = VocabularyCollectionItem(
        collection_id=collection.id, name="Draft book", status="draft", position=1
    )
    db_session.add(draft_item)
    db_session.commit()

    body = client.get(f"/api/v1/vocabulary-collections/{collection.id}").json()
    assert [row["id"] for row in body["items"]] == [str(item.id)]


def test_a_draft_topic_stays_invisible_under_a_published_item(
    client: TestClient, db_session: Session
) -> None:
    _, item, topic = build_tree(db_session)
    draft_topic = Topic(slug="topic-draft", name="Topic draft", status="draft", position=1)
    draft_topic.collection_item_id = item.id
    db_session.add(draft_topic)
    db_session.commit()

    body = client.get(f"/api/v1/vocabulary-collection-items/{item.id}").json()
    assert [row["id"] for row in body["topics"]] == [str(topic.id)]


def test_an_item_404s_through_a_draft_collection(client: TestClient, db_session: Session) -> None:
    # Không được lộ item qua cửa "detail" khi tuyển tập cha chưa publish.
    _, item, _ = build_tree(db_session, collection_status="draft")
    db_session.commit()

    assert client.get(f"/api/v1/vocabulary-collection-items/{item.id}").status_code == 404


def test_topic_count_only_counts_what_a_learner_can_actually_see(
    client: TestClient, db_session: Session
) -> None:
    # topic_count trên card tuyển tập đếm topic nhìn thấy được — KHÔNG đếm topic
    # nháp hay topic dưới item nháp, nếu không card sẽ hứa một trang bấm vào 404.
    collection, _, _ = build_tree(db_session)
    build_tree(db_session, item_status="draft", marker="d")
    build_tree(db_session, topic_status="draft", marker="e")
    db_session.commit()

    by_slug = {row["slug"]: row for row in client.get("/api/v1/vocabulary-collections").json()}
    assert by_slug["col-t"]["topic_count"] == 1
    # Item nháp và topic nháp không được đếm vào số của card.
    assert by_slug["col-d"]["topic_count"] == 0
    assert by_slug["col-e"]["topic_count"] == 0

    detail = client.get(f"/api/v1/vocabulary-collections/{collection.id}").json()
    assert [row["topic_count"] for row in detail["items"]] == [1]


def test_deleting_a_collection_detaches_topics_but_keeps_them(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    collection, item, topic = build_tree(db_session)
    db_session.commit()

    response = client.delete(
        f"/api/v1/admin/vocabulary-collections/{collection.id}", headers=auth("admin")
    )
    assert response.status_code == 204
    # Topic còn nguyên, chỉ bị gỡ khỏi cuốn — cuốn không phải thứ sở hữu từ vựng.
    refreshed = db_session.get(Topic, topic.id)
    assert refreshed is not None
    assert refreshed.collection_item_id is None
    # Item con CASCADE đi theo collection (không như topic: item thuộc về tuyển tập).
    assert db_session.get(VocabularyCollectionItem, item.id) is None


def test_deleting_an_item_detaches_topics(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _, item, topic = build_tree(db_session)
    db_session.commit()

    response = client.delete(
        f"/api/v1/admin/vocabulary-collection-items/{item.id}", headers=auth("admin")
    )
    assert response.status_code == 204
    refreshed = db_session.get(Topic, topic.id)
    assert refreshed is not None
    assert refreshed.collection_item_id is None


def test_a_topic_can_be_moved_between_item_and_unfiled(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    # Quy ước gửi lên: UUID = xếp vào cuốn; "" = gỡ về "chưa xếp"; không gửi key =
    # để nguyên. Ba trường hợp đó là ba hành vi khác nhau, phải có test ghim cả ba.
    _, item, topic = build_tree(db_session)
    orphan = Topic(slug="orphan", name="Orphan", status="published")
    db_session.add(orphan)
    another_item = VocabularyCollectionItem(
        collection_id=item.collection_id, name="Other book", status="draft", position=1
    )
    db_session.add(another_item)
    db_session.commit()

    # Xếp orphan vào cuốn.
    response = client.patch(
        f"/api/v1/admin/topics/{orphan.id}",
        json={"collection_item_id": str(item.id)},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    assert response.json()["collection_item_id"] == str(item.id)
    assert response.json()["collection_item_name"] == item.name

    # Gỡ topic khỏi cuốn.
    response = client.patch(
        f"/api/v1/admin/topics/{topic.id}",
        json={"collection_item_id": ""},
        headers=auth("editor"),
    )
    assert response.status_code == 200
    assert response.json()["collection_item_id"] is None

    # PATCH không gửi key thì cuốn vẫn ở nguyên chỗ cũ.
    response = client.patch(
        f"/api/v1/admin/topics/{orphan.id}",
        json={"name": "Orphan renamed"},
        headers=auth("editor"),
    )
    assert response.json()["collection_item_id"] == str(item.id)

    # Xếp vào item khác.
    response = client.patch(
        f"/api/v1/admin/topics/{orphan.id}",
        json={"collection_item_id": str(another_item.id)},
        headers=auth("editor"),
    )
    assert response.json()["collection_item_id"] == str(another_item.id)

    # Item không tồn tại -> 404 chứ không phải lỗi khoá ngoại âm thầm.
    response = client.patch(
        f"/api/v1/admin/topics/{orphan.id}",
        json={"collection_item_id": ZERO},
        headers=auth("editor"),
    )
    assert response.status_code == 404


def test_admin_create_publish_delete_collection_flow(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    editor = auth("editor")
    admin = auth("admin")

    created = client.post(
        "/api/v1/admin/vocabulary-collections",
        json={"slug": "toeic", "name": "TOEIC words"},
        headers=editor,
    )
    assert created.status_code == 201
    # Cùng luật với dictation section: sinh ra ở draft, học viên không thấy.
    assert created.json()["status"] == "draft"
    collection_id = created.json()["id"]

    item_created = client.post(
        "/api/v1/admin/vocabulary-collection-items",
        json={"collection_id": collection_id, "name": "600 essential words"},
        headers=editor,
    )
    assert item_created.status_code == 201
    assert item_created.json()["status"] == "draft"
    item_id = item_created.json()["id"]

    # Publish là việc của admin — editor không publish được.
    assert (
        client.post(
            f"/api/v1/admin/vocabulary-collections/{collection_id}/publish", headers=editor
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/admin/vocabulary-collection-items/{item_id}/publish", headers=admin
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/v1/admin/vocabulary-collections/{collection_id}/publish", headers=admin
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["item_count"] == 1

    # Học viên giờ thấy được.
    visible = client.get("/api/v1/vocabulary-collections").json()
    assert any(row["id"] == collection_id for row in visible)

    # Editor không xoá được — xoá là quyết định của admin (cùng luật với topic).
    assert (
        client.delete(
            f"/api/v1/admin/vocabulary-collections/{collection_id}", headers=editor
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/v1/admin/vocabulary-collections/{collection_id}", headers=admin
        ).status_code
        == 204
    )


def test_creating_a_collection_with_a_duplicate_slug_is_a_conflict(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    client.post(
        "/api/v1/admin/vocabulary-collections",
        json={"slug": "toeic", "name": "TOEIC"},
        headers=auth("editor"),
    )
    response = client.post(
        "/api/v1/admin/vocabulary-collections",
        json={"slug": "toeic", "name": "TOEIC again"},
        headers=auth("editor"),
    )
    assert response.status_code == 409


def test_collection_detail_opens_by_slug_or_id(
    client: TestClient, db_session: Session
) -> None:
    # Slug là URL thật của trang tuyển tập; endpoint 422 trước slug là lỗi chính
    # người dùng gặp khi bấm vào card.
    collection, _, _ = build_tree(db_session)
    db_session.commit()

    by_slug = client.get(f"/api/v1/vocabulary-collections/{collection.slug}")
    by_id = client.get(f"/api/v1/vocabulary-collections/{collection.id}")
    assert by_slug.status_code == 200
    assert by_slug.json() == by_id.json()

    # Slug của collection chưa publish cũng phải 404, không phải 404 lộ qua đường khác.
    draft, _, _ = build_tree(db_session, collection_status="draft", marker="d")
    db_session.commit()
    assert client.get(f"/api/v1/vocabulary-collections/{draft.slug}").status_code == 404


def test_missing_nodes_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/vocabulary-collections/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/vocabulary-collections/khong-ton-tai").status_code == 404
    assert client.get(f"/api/v1/vocabulary-collection-items/{uuid.uuid4()}").status_code == 404
