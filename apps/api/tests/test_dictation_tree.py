"""Cây dictation: topic -> section -> story -> item.

Trọng tâm là chuyện dễ hỏng im lặng: **mỗi tầng phải tự lọc `published`**. Một
story nháp nằm dưới section đã publish vẫn lọt ra nếu chỉ lọc ở tầng section, và
không ai báo cáo được vì nội dung trông hoàn toàn bình thường.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AudioAsset,
    DictationAttempt,
    DictationItem,
    DictationSection,
    DictationStory,
    DictationTopic,
    User,
)


def make_asset(db: Session, marker: str) -> AudioAsset:
    asset = AudioAsset(
        storage_key=f"audio/{marker}/{marker}.mp3",
        source_hash=marker * 8,
        mime_type="audio/mpeg",
        size_bytes=1000,
        duration_ms=2000,
        source="tts",
        engine="edge-tts",
        engine_version="1",
        voice="us_female_1",
        accent="en-US",
        source_text="x",
    )
    db.add(asset)
    db.flush()
    return asset


def build_tree(
    db: Session,
    *,
    topic_status: str = "published",
    section_status: str = "published",
    story_status: str = "published",
    item_status: str = "published",
    marker: str = "t",
) -> DictationStory:
    topic = DictationTopic(
        slug=f"slug-{marker}", name=f"Topic {marker}", status=topic_status, position=0
    )
    db.add(topic)
    db.flush()
    section = DictationSection(
        topic_id=topic.id, name=f"Section {marker}", status=section_status, position=0
    )
    db.add(section)
    db.flush()
    story = DictationStory(
        section_id=section.id, title=f"Story {marker}", status=story_status, position=0
    )
    db.add(story)
    db.flush()
    for index, text in enumerate(["First sentence here.", "Second sentence here."], start=1):
        db.add(
            DictationItem(
                audio_asset_id=make_asset(db, f"{marker}{index}").id,
                transcript=text,
                story_id=story.id,
                position=index,
                status=item_status,
                difficulty=3,
            )
        )
    db.commit()
    return story


def auth(client: TestClient, db: Session, email: str = "learner@example.com") -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "supersecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- draft không lọt ra, ở TỪNG tầng --------------------------------------


def test_draft_topic_hides_itself(client: TestClient, db_session: Session) -> None:
    build_tree(db_session, topic_status="draft", marker="a")
    assert client.get("/api/v1/dictation-topics").json() == []


def test_draft_section_hides_itself_under_a_published_topic(
    client: TestClient, db_session: Session
) -> None:
    story = build_tree(db_session, section_status="draft", marker="b")
    section = db_session.get(DictationSection, story.section_id)
    assert section is not None
    body = client.get(f"/api/v1/dictation-topics/{section.topic_id}").json()
    assert body["sections"] == []
    assert body["section_count"] == 0


def test_draft_story_hides_itself_under_a_published_section(
    client: TestClient, db_session: Session
) -> None:
    story = build_tree(db_session, story_status="draft", marker="c")
    headers = auth(client, db_session, "c@example.com")
    body = client.get(f"/api/v1/dictation-sections/{story.section_id}", headers=headers).json()
    assert body["stories"] == []


def test_a_published_story_under_a_draft_topic_is_still_hidden(
    client: TestClient, db_session: Session
) -> None:
    """Tầng trên nháp thì cả nhánh dưới chưa được coi là đã xuất bản.

    Đây là ca mà việc chỉ lọc ở tầng đang truy vấn sẽ bỏ lọt: bản thân story
    published, chỉ có topic là nháp.
    """
    story = build_tree(db_session, topic_status="draft", marker="d")
    headers = auth(client, db_session, "d@example.com")
    assert client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).status_code == 404
    assert (
        client.get(f"/api/v1/dictation-sections/{story.section_id}", headers=headers).status_code
        == 404
    )


def test_draft_items_do_not_appear_in_a_published_story(
    client: TestClient, db_session: Session
) -> None:
    story = build_tree(db_session, item_status="draft", marker="e")
    headers = auth(client, db_session, "e@example.com")
    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert body["items"] == []
    assert body["progress"]["total_items"] == 0


# --- thứ tự và nội dung ----------------------------------------------------


def test_items_come_back_in_story_order(client: TestClient, db_session: Session) -> None:
    story = build_tree(db_session, marker="f")
    headers = auth(client, db_session, "f@example.com")
    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert [item["position"] for item in body["items"]] == [1, 2]
    assert body["items"][0]["transcript"] == "First sentence here."
    # Đường dẫn quay lui phải có sẵn, nếu không màn story là ngõ cụt.
    assert body["section_name"] == "Section f"
    assert body["topic_name"] == "Topic f"


# --- tiến độ ---------------------------------------------------------------


def test_progress_starts_at_zero(client: TestClient, db_session: Session) -> None:
    story = build_tree(db_session, marker="g")
    headers = auth(client, db_session, "g@example.com")
    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert body["progress"] == {"total_items": 2, "completed_items": 0}
    assert all(item["completed"] is False for item in body["items"])


def test_only_a_perfect_answer_counts_as_done(client: TestClient, db_session: Session) -> None:
    """Tiến độ đếm câu ĐÚNG, không đếm câu đã thử.

    Gõ gần đúng vẫn là chưa nghe ra, nên nó không được đánh dấu xong — đó là toàn
    bộ ý nghĩa của thanh tiến độ.
    """
    story = build_tree(db_session, marker="h")
    headers = auth(client, db_session, "h@example.com")
    detail = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    first = detail["items"][0]["id"]

    near = client.post(
        f"/api/v1/dictation/{first}/attempts",
        json={"submitted_text": "First sentence there."},
        headers=headers,
    ).json()
    assert near["is_complete"] is False
    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert body["progress"]["completed_items"] == 0

    exact = client.post(
        f"/api/v1/dictation/{first}/attempts",
        json={"submitted_text": "first sentence here"},
        headers=headers,
    ).json()
    # Hoa thường và dấu câu không tính — nghe thì không biết dấu chấm ở đâu.
    assert exact["is_complete"] is True
    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert body["progress"]["completed_items"] == 1
    assert body["items"][0]["completed"] is True


def test_typing_extra_words_is_not_done_even_at_full_accuracy(
    client: TestClient, db_session: Session
) -> None:
    """`accuracy` là matched/expected, nên gõ đủ RỒI GÕ THÊM vẫn ra 100%.

    Đây là lý do tiến độ đếm `is_complete` chứ không đếm `accuracy == 100`.
    """
    story = build_tree(db_session, marker="u")
    headers = auth(client, db_session, "u@example.com")
    detail = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    first = detail["items"][0]["id"]

    result = client.post(
        f"/api/v1/dictation/{first}/attempts",
        json={"submitted_text": "First sentence here and then some more words"},
        headers=headers,
    ).json()
    assert result["accuracy"] == "100.00", "accuracy đủ 100 vì mọi từ cần có đều khớp"
    assert result["is_complete"] is False, "nhưng bài rõ ràng chưa đúng"

    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert body["progress"]["completed_items"] == 0


def test_done_stays_done_after_a_worse_attempt(client: TestClient, db_session: Session) -> None:
    """Đã nghe ra được là chuyện đã xảy ra; làm lại sai không gỡ mất điều đó."""
    story = build_tree(db_session, marker="v")
    headers = auth(client, db_session, "v@example.com")
    detail = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    first = detail["items"][0]["id"]

    for text in ("First sentence here.", "totally wrong"):
        client.post(
            f"/api/v1/dictation/{first}/attempts",
            json={"submitted_text": text},
            headers=headers,
        )

    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert body["progress"]["completed_items"] == 1


def test_progress_is_per_user(client: TestClient, db_session: Session) -> None:
    story = build_tree(db_session, marker="i")
    mine = auth(client, db_session, "mine@example.com")
    theirs = auth(client, db_session, "theirs@example.com")
    detail = client.get(f"/api/v1/dictation-stories/{story.id}", headers=mine).json()
    client.post(
        f"/api/v1/dictation/{detail['items'][0]['id']}/attempts",
        json={"submitted_text": "First sentence here."},
        headers=mine,
    )
    other = client.get(f"/api/v1/dictation-stories/{story.id}", headers=theirs).json()
    assert other["progress"]["completed_items"] == 0


# --- cổng publish của story ------------------------------------------------


def test_an_empty_story_cannot_be_published(client: TestClient, db_session: Session) -> None:
    """Story rỗng lên sóng là một trang trống — trông như lỗi, không như bài chưa xong."""
    admin_headers = auth(client, db_session, "admin@example.com")
    user = db_session.query(User).filter(User.email == "admin@example.com").one()
    user.role = "admin"
    db_session.commit()

    topic = DictationTopic(slug="empty", name="Empty", status="draft")
    db_session.add(topic)
    db_session.flush()
    section = DictationSection(topic_id=topic.id, name="S", status="draft")
    db_session.add(section)
    db_session.flush()
    story = DictationStory(section_id=section.id, title="No sentences", status="draft")
    db_session.add(story)
    db_session.commit()

    response = client.post(
        f"/api/v1/admin/dictation/stories/{story.id}/publish", headers=admin_headers
    )
    assert response.status_code == 409
    assert "no published sentences" in response.json()["detail"]


def test_learner_cannot_reach_the_admin_tree(client: TestClient, db_session: Session) -> None:
    headers = auth(client, db_session, "nosy@example.com")
    for path in ("topics", "sections", "stories"):
        assert client.get(f"/api/v1/admin/dictation/{path}", headers=headers).status_code == 403


def test_pasting_into_a_story_numbers_the_lines_in_order(
    client: TestClient, db_session: Session
) -> None:
    admin_headers = auth(client, db_session, "editor@example.com")
    user = db_session.query(User).filter(User.email == "editor@example.com").one()
    user.role = "admin"
    db_session.commit()

    topic = DictationTopic(slug="paste", name="Paste", status="draft")
    db_session.add(topic)
    db_session.flush()
    section = DictationSection(topic_id=topic.id, name="S", status="draft")
    db_session.add(section)
    db_session.flush()
    story = DictationStory(section_id=section.id, title="Ordered", status="draft")
    db_session.add(story)
    db_session.commit()

    raw = "One line here.\nTwo line here.\nThree line here."
    parsed = client.post(
        "/api/v1/admin/dictation/parse", json={"raw_text": raw}, headers=admin_headers
    ).json()
    client.post(
        "/api/v1/admin/dictation",
        json={"rows": parsed["rows"], "story_id": str(story.id)},
        headers=admin_headers,
    )

    items = (
        db_session.query(DictationItem)
        .filter(DictationItem.story_id == story.id)
        .order_by(DictationItem.position)
        .all()
    )
    assert [item.position for item in items] == [1, 2, 3]
    assert items[0].transcript == "One line here."

    # Dán thêm phải NỐI TIẾP, không đánh số lại từ đầu — thêm vào một story đang
    # soạn dở là thao tác thường gặp.
    parsed2 = client.post(
        "/api/v1/admin/dictation/parse", json={"raw_text": "Four line here."}, headers=admin_headers
    ).json()
    client.post(
        "/api/v1/admin/dictation",
        json={"rows": parsed2["rows"], "story_id": str(story.id)},
        headers=admin_headers,
    )
    positions = [
        item.position
        for item in db_session.query(DictationItem)
        .filter(DictationItem.story_id == story.id)
        .order_by(DictationItem.position)
        .all()
    ]
    assert positions == [1, 2, 3, 4]


def test_an_item_in_a_story_must_have_a_position(client: TestClient, db_session: Session) -> None:
    """CHECK ck_dictation_item_story_position.

    Không có nó, một câu có thể nằm trong story mà không biết đứng thứ mấy —
    thứ tự phát cho học viên thành ngẫu nhiên theo cách database trả hàng.
    """
    import pytest
    from sqlalchemy.exc import IntegrityError

    story = build_tree(db_session, marker="j")
    db_session.add(
        DictationItem(
            audio_asset_id=None,
            transcript="No position.",
            story_id=story.id,
            position=None,
            status="draft",
            difficulty=3,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert uuid.UUID(str(story.id))


# --- sửa và xoá ------------------------------------------------------------


def admin_headers(client: TestClient, db: Session, email: str) -> dict[str, str]:
    headers = auth(client, db, email)
    user = db.query(User).filter(User.email == email).one()
    user.role = "admin"
    db.commit()
    return headers


def test_deleting_a_story_keeps_its_sentences(client: TestClient, db_session: Session) -> None:
    """Xoá cái vỏ không được kéo theo phần ruột đã mất công soạn.

    `dictation_item.story_id` là SET NULL, nên các câu trở lại thành câu lẻ và
    vẫn nằm trong màn quản lý — chứ không biến mất cùng story.
    """
    story = build_tree(db_session, marker="k")
    headers = admin_headers(client, db_session, "del-story@example.com")
    item_ids = [
        item.id
        for item in db_session.query(DictationItem).filter(DictationItem.story_id == story.id)
    ]
    assert len(item_ids) == 2

    deleted = client.delete(f"/api/v1/admin/dictation/stories/{story.id}", headers=headers)
    assert deleted.status_code == 204

    db_session.expire_all()
    survivors = db_session.query(DictationItem).filter(DictationItem.id.in_(item_ids)).all()
    assert len(survivors) == 2, "các câu phải sống sót"
    assert all(item.story_id is None and item.position is None for item in survivors)


def test_deleting_a_topic_takes_the_branch_but_not_the_sentences(
    client: TestClient, db_session: Session
) -> None:
    story = build_tree(db_session, marker="l")
    section_id = story.section_id
    topic_id = db_session.get(DictationSection, section_id).topic_id  # type: ignore[union-attr]
    headers = admin_headers(client, db_session, "del-topic@example.com")

    deleted = client.delete(f"/api/v1/admin/dictation/topics/{topic_id}", headers=headers)
    assert deleted.status_code == 204

    db_session.expire_all()
    assert db_session.get(DictationSection, section_id) is None, "section đi theo (CASCADE)"
    assert db_session.get(DictationStory, story.id) is None, "story đi theo (CASCADE)"
    assert db_session.query(DictationItem).filter(DictationItem.story_id.is_(None)).count() >= 2


def test_a_sentence_with_attempts_refuses_deletion_and_points_at_archive(
    client: TestClient, db_session: Session
) -> None:
    """Xoá một câu đã có người làm sẽ làm mồ côi lịch sử của họ.

    Khoá ngoại là RESTRICT nên database sẽ chặn; endpoint chặn trước để trả 409
    có giải thích thay vì 500, và chỉ sang `archived` — trạng thái vốn được
    thiết kế đúng cho việc này.
    """
    story = build_tree(db_session, marker="m")
    headers = admin_headers(client, db_session, "attempted@example.com")
    detail = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    item_id = detail["items"][0]["id"]

    client.post(
        f"/api/v1/dictation/{item_id}/attempts",
        json={"submitted_text": "First sentence here."},
        headers=headers,
    )

    response = client.delete(f"/api/v1/admin/dictation/{item_id}", headers=headers)
    assert response.status_code == 409
    assert "archived" in response.json()["detail"]

    # Đường lui phải thật sự dùng được, không chỉ được nhắc tới.
    patched = client.patch(
        f"/api/v1/admin/dictation/{item_id}", json={"status": "archived"}, headers=headers
    )
    assert patched.status_code == 200
    body = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert item_id not in [item["id"] for item in body["items"]], "câu archived biến mất khỏi bài"


def test_moving_a_sentence_into_a_story_gives_it_a_position(
    client: TestClient, db_session: Session
) -> None:
    story = build_tree(db_session, marker="n")
    headers = admin_headers(client, db_session, "move@example.com")
    loose = DictationItem(
        audio_asset_id=make_asset(db_session, "loose1").id,
        transcript="A loose sentence.",
        status="draft",
        difficulty=3,
    )
    db_session.add(loose)
    db_session.commit()

    client.patch(
        f"/api/v1/admin/dictation/{loose.id}",
        json={"story_id": str(story.id)},
        headers=headers,
    )
    db_session.expire_all()
    moved = db_session.get(DictationItem, loose.id)
    assert moved is not None
    assert moved.story_id == story.id
    assert moved.position == 3, "xếp cuối bài, không đụng số của câu đang có"

    # Chuỗi rỗng đưa nó trở lại thành câu lẻ, và position phải rỗng theo — CHECK
    # ck_dictation_item_story_position đòi hai cột cùng có hoặc cùng không.
    client.patch(f"/api/v1/admin/dictation/{loose.id}", json={"story_id": ""}, headers=headers)
    db_session.expire_all()
    moved = db_session.get(DictationItem, loose.id)
    assert moved is not None and moved.story_id is None and moved.position is None


def test_reorder_renumbers_the_whole_story(client: TestClient, db_session: Session) -> None:
    story = build_tree(db_session, marker="o")
    headers = admin_headers(client, db_session, "reorder@example.com")
    items = (
        db_session.query(DictationItem)
        .filter(DictationItem.story_id == story.id)
        .order_by(DictationItem.position)
        .all()
    )
    reversed_ids = [str(item.id) for item in reversed(items)]

    response = client.post(
        f"/api/v1/admin/dictation/stories/{story.id}/reorder",
        json={"item_ids": reversed_ids},
        headers=headers,
    )
    assert response.status_code == 200
    db_session.expire_all()
    now = (
        db_session.query(DictationItem)
        .filter(DictationItem.story_id == story.id)
        .order_by(DictationItem.position)
        .all()
    )
    assert [str(item.id) for item in now] == reversed_ids
    assert [item.position for item in now] == [1, 2]


def test_reorder_refuses_a_partial_list(client: TestClient, db_session: Session) -> None:
    """Nhận một phần sẽ để lại những câu không được nhắc tới mang số cũ, và
    chúng sẽ đụng số với những câu vừa đánh lại."""
    story = build_tree(db_session, marker="p")
    headers = admin_headers(client, db_session, "partial@example.com")
    one = db_session.query(DictationItem).filter(DictationItem.story_id == story.id).first()
    assert one is not None

    response = client.post(
        f"/api/v1/admin/dictation/stories/{story.id}/reorder",
        json={"item_ids": [str(one.id)]},
        headers=headers,
    )
    assert response.status_code == 400


def test_renaming_a_topic_does_not_wipe_its_other_fields(
    client: TestClient, db_session: Session
) -> None:
    """PATCH phải phân biệt "đặt về rỗng" với "không đụng tới"."""
    story = build_tree(db_session, marker="q")
    section = db_session.get(DictationSection, story.section_id)
    assert section is not None
    topic = db_session.get(DictationTopic, section.topic_id)
    assert topic is not None
    topic.description = "Mô tả gốc"
    db_session.commit()

    headers = admin_headers(client, db_session, "rename@example.com")
    body = client.patch(
        f"/api/v1/admin/dictation/topics/{topic.id}", json={"name": "Tên mới"}, headers=headers
    ).json()
    assert body["name"] == "Tên mới"
    assert body["description"] == "Mô tả gốc", "trường không gửi lên phải giữ nguyên"


def test_only_admins_can_delete(client: TestClient, db_session: Session) -> None:
    story = build_tree(db_session, marker="r")
    headers = auth(client, db_session, "editor-only@example.com")
    user = db_session.query(User).filter(User.email == "editor-only@example.com").one()
    user.role = "editor"
    db_session.commit()

    # Editor sửa được nhưng không xoá được: xoá là thao tác không lùi lại được.
    assert (
        client.patch(
            f"/api/v1/admin/dictation/stories/{story.id}",
            json={"title": "Đổi tên"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/admin/dictation/stories/{story.id}", headers=headers).status_code
        == 403
    )


def test_archiving_is_a_real_way_out_not_just_advice(
    client: TestClient, db_session: Session
) -> None:
    """Thông báo 409 chỉ sang `archived`, nên `archived` phải thật sự làm được việc.

    Ba điều phải cùng đúng, nếu không lời khuyên đó dẫn vào ngõ cụt:
    câu biến mất khỏi phần học, lịch sử làm bài còn nguyên, và đưa lại được
    về nháp.
    """
    story = build_tree(db_session, marker="s")
    headers = admin_headers(client, db_session, "archive-flow@example.com")
    detail = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    item_id = detail["items"][0]["id"]

    client.post(
        f"/api/v1/dictation/{item_id}/attempts",
        json={"submitted_text": "First sentence here."},
        headers=headers,
    )
    assert client.delete(f"/api/v1/admin/dictation/{item_id}", headers=headers).status_code == 409

    client.patch(f"/api/v1/admin/dictation/{item_id}", json={"status": "archived"}, headers=headers)
    after = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()
    assert item_id not in [item["id"] for item in after["items"]]

    # Lịch sử phải sống sót — đó là toàn bộ lý do tồn tại của `archived`.
    attempts = db_session.execute(
        select(func.count())
        .select_from(DictationAttempt)
        .where(DictationAttempt.item_id == uuid.UUID(item_id))
    ).scalar()
    assert attempts == 1

    # Và phải quay lại được: lưu trữ là gỡ xuống, không phải xoá bằng đường vòng.
    restored = client.patch(
        f"/api/v1/admin/dictation/{item_id}", json={"status": "draft"}, headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"


def test_archiving_the_last_sentence_blocks_republishing_the_story(
    client: TestClient, db_session: Session
) -> None:
    """Lưu trữ hết câu thì bài trở thành trang trống — cổng publish phải chặn lại."""
    story = build_tree(db_session, marker="t", story_status="draft")
    headers = admin_headers(client, db_session, "archive-all@example.com")
    for item in db_session.query(DictationItem).filter(DictationItem.story_id == story.id).all():
        client.patch(
            f"/api/v1/admin/dictation/{item.id}", json={"status": "archived"}, headers=headers
        )

    response = client.post(f"/api/v1/admin/dictation/stories/{story.id}/publish", headers=headers)
    assert response.status_code == 409
    assert "no published sentences" in response.json()["detail"]
