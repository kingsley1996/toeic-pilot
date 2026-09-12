"""Góp ý của người học: gửi, xem, duyệt, từ chối.

Bảy tính chất, và bốn trong số đó hỏng IM LẶNG nếu mất: khoá ảnh ngoài vùng
`feedback/`, trần góp ý chờ xử lý, tính idempotent của lần duyệt thứ hai, và
hàng `ruby_rule` mà `create_all` không dựng được.
"""

import uuid

import pytest

from app.models.feedback import MAX_SCREENSHOTS, PENDING_CAP, Feedback
from app.models.ruby import DEFAULT_RUBY_RULES, RubyRule


@pytest.fixture
def stub_storage(monkeypatch):
    """`verify` gật đầu với mọi khoá — bài test không có nhà cung cấp thật."""
    from app.core import storage

    driver = storage.get_driver("image")
    monkeypatch.setattr(type(driver), "verify", lambda self, key: None, raising=False)
    return driver


@pytest.fixture
def reward_rule(db_session):
    """Hàng `feedback_reward`, thứ `create_all` KHÔNG dựng được.

    `services/ruby.py::rules()` chỉ gieo khi bảng rỗng, và trong bài test bảng
    được gieo ở lần đọc đầu tiên — nên hàng này có mặt. Nhưng trên một cài đặt
    THẬT bảng đã có bảy hàng từ trước, và hàng thứ tám chỉ tới bằng migration
    074. Bài `test_reward_rule_exists` giữ hai đường ấy nói cùng một con số.
    """
    row = db_session.get(RubyRule, "feedback_reward")
    if row is None:
        spec = next(r for r in DEFAULT_RUBY_RULES if r["source_type"] == "feedback_reward")
        row = RubyRule(**spec)
        db_session.add(row)
        db_session.commit()
    return row


def _send(client, headers, **over):
    body = {"type": "bug", "description": "Nút nộp bài không phản hồi ở Part 5."}
    body.update(over)
    return client.post("/api/v1/feedback", headers=headers, json=body)


def test_a_learner_can_send_feedback_with_screenshots(client, auth, stub_storage):
    keys = ["feedback/ab/cd/mot.png", "feedback/ab/cd/hai.png"]
    response = _send(client, auth("learner"), screenshot_keys=keys)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["type"] == "bug"
    # URL sinh ở máy chủ, không phải khoá thô: nhà cung cấp là một biến cấu hình
    # và Cloudinary còn chèn thêm tiền tố thư mục vào `public_url`.
    assert len(body["image_urls"]) == 2
    assert all(url.endswith(key) for url, key in zip(body["image_urls"], keys, strict=True))


def test_more_than_three_screenshots_is_refused(client, auth, stub_storage):
    """Trần ở HỢP ĐỒNG, không chỉ ở giao diện — một request viết tay đi vòng
    qua React được, và bốn ảnh thì màn duyệt thành thư viện ảnh."""
    keys = [f"feedback/ab/cd/{n}.png" for n in range(MAX_SCREENSHOTS + 1)]
    assert _send(client, auth("learner"), screenshot_keys=keys).status_code == 422


def test_the_same_image_sent_three_times_counts_once(client, auth, stub_storage):
    key = "feedback/ab/cd/mot.png"
    body = _send(client, auth("learner"), screenshot_keys=[key, key, key]).json()
    assert len(body["image_urls"]) == 1


def test_a_key_outside_the_feedback_prefix_is_refused(client, auth, stub_storage):
    """Thiếu phép kiểm này thì đây là đường ghi một chuỗi tuỳ ý.

    Người gửi trỏ được ảnh góp ý vào một ảnh NỘI DUNG, và lệnh dọn ảnh mồ côi
    sau này sẽ xoá mất thứ đang được một câu hỏi dùng — hỏng ở một chỗ hoàn
    toàn khác, nhiều tuần sau.
    """
    response = _send(client, auth("learner"), screenshot_keys=["image/ab/cd/de.png"])
    assert response.status_code == 400

    # Một khoá hợp lệ đứng cạnh một khoá sai vẫn phải bị chặn CẢ CỤM: kiểm
    # từng khoá rồi bỏ qua cái sai sẽ ghi vào database một góp ý thiếu ảnh mà
    # người gửi tưởng đã đính kèm.
    mixed = _send(
        client,
        auth("learner"),
        screenshot_keys=["feedback/ab/cd/ok.png", "avatar/ab/cd/xau.png"],
    )
    assert mixed.status_code == 400


def test_an_empty_description_or_unknown_type_is_refused(client, auth):
    assert _send(client, auth("learner"), description="   ").status_code == 422
    assert _send(client, auth("learner"), description="").status_code == 422
    assert _send(client, auth("learner"), type="complaint").status_code == 422


def test_the_pending_cap_stops_a_flood(client, auth):
    """Trần đếm theo `pending`, nên nó TỰ MỞ RA khi admin xử lý.

    Đếm theo tổng thì người góp ý đều đặn sẽ bị khoá vĩnh viễn sau vài tháng —
    một cái trần chống spam không được phép phạt người dùng đúng cách.
    """
    headers = auth("learner")
    for _ in range(PENDING_CAP):
        assert _send(client, headers).status_code == 200

    blocked = _send(client, headers)
    assert blocked.status_code == 409


def test_mine_shows_only_my_own(client, auth, db_session):
    mine = _send(client, auth("learner"))
    assert mine.status_code == 200

    other = Feedback(user_id=uuid.uuid4(), type="other", description="của người khác")
    db_session.add(other)
    db_session.commit()

    rows = client.get("/api/v1/feedback/mine", headers=auth("learner")).json()
    assert [row["id"] for row in rows] == [mine.json()["id"]]


def test_approving_pays_once_however_many_times_it_is_clicked(
    client, auth, db_session, reward_rule
):
    """Duyệt lần hai phải 409, và sổ ruby KHÔNG được tăng.

    `uq_ruby_event_source` đã chặn hàng thứ hai, nên tiền không nhân đôi kể cả
    khi cổng này biến mất — nhưng một 200 im lặng khiến người bấm tưởng lần thứ
    hai vừa làm được việc gì đó.
    """
    from app.services.ruby import balance

    created = _send(client, auth("learner")).json()
    admin = auth("admin")

    approved = client.post(f"/api/v1/admin/feedback/{created['id']}/approve", headers=admin)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    owner = uuid.UUID(created["user_id"])
    after_first = balance(db_session, owner)
    assert after_first == reward_rule.amount

    again = client.post(f"/api/v1/admin/feedback/{created['id']}/approve", headers=admin)
    assert again.status_code == 409
    assert balance(db_session, owner) == after_first


def test_rejecting_pays_nothing_and_keeps_the_note(client, auth, db_session, reward_rule):
    from app.services.ruby import balance

    created = _send(client, auth("learner")).json()
    rejected = client.post(
        f"/api/v1/admin/feedback/{created['id']}/reject",
        headers=auth("admin"),
        json={"admin_note": "Trùng với góp ý trước"},
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["admin_note"] == "Trùng với góp ý trước"
    assert balance(db_session, uuid.UUID(created["user_id"])) == 0


def test_the_reward_rule_is_a_row_not_a_constant():
    """Mức thưởng nằm trong `ruby_rule`, và migration 074 là đường nó đi vào.

    `DEFAULT_RUBY_RULES` một mình KHÔNG đủ: `rules()` chỉ gieo khi bảng rỗng,
    mà mọi cài đặt đang chạy đã có bảy hàng. Bài này giữ hai đường — hằng số và
    migration — nói cùng một `source_type`.
    """
    from app.models.ruby import RUBY_SOURCES

    assert "feedback_reward" in RUBY_SOURCES
    spec = next(r for r in DEFAULT_RUBY_RULES if r["source_type"] == "feedback_reward")
    assert spec["amount"] == 200

    migration = (
        __import__("pathlib").Path("alembic/versions/074_feedback.py").read_text(encoding="utf-8")
    )
    assert "INSERT INTO ruby_rule" in migration
    assert "ON CONFLICT (source_type) DO NOTHING" in migration


def test_the_reward_endpoint_reads_the_row_and_goes_quiet_when_disabled(
    client, auth, db_session, reward_rule
):
    """Giao diện đọc con số từ đây, nên nó phải theo hàng chứ không theo hằng số.

    Và tắt hàng thì trả 0: giao diện bỏ luôn câu hứa. Hứa thưởng khi phần
    thưởng đã tắt còn tệ hơn không hứa gì.
    """
    headers = auth("learner")
    assert client.get("/api/v1/feedback/reward", headers=headers).json()["amount"] == 200

    reward_rule.amount = 50
    db_session.commit()
    db_session.info.clear()  # memo cau hinh song theo request, test dung chung Session
    assert client.get("/api/v1/feedback/reward", headers=headers).json()["amount"] == 50

    reward_rule.enabled = False
    db_session.commit()
    db_session.info.clear()  # nhu tren
    assert client.get("/api/v1/feedback/reward", headers=headers).json()["amount"] == 0
