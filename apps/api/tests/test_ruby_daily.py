"""Ba nguồn ruby theo ngày (ADR-011 lát 3): cả ba việc, quà, và mốc chuỗi ngày."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DailyTaskSlot, User, VocabularyReviewLog
from app.services import ruby, ruby_daily
from app.services.daily_tasks import KIND_DICTATION
from tests.test_dictation_tree import auth as learner_auth
from tests.test_dictation_tree import build_tree


def _user(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def _disable_every_slot_but(
    db: Session, client: TestClient, headers: dict[str, str], kind: str
) -> None:
    """Giữ đúng một khe, để "xong cả ba việc" đạt được trong một bài kiểm.

    Đọc `/daily-tasks` một lần trước để bảng khe được gieo — bảng rỗng nghĩa là
    "chưa từng cấu hình", nên tắt trước khi gieo thì lần đọc sau gieo lại đủ ba.
    """
    client.get("/api/v1/daily-tasks", headers=headers)
    for slot in db.query(DailyTaskSlot).all():
        if slot.kind != kind:
            slot.enabled = False
        else:
            slot.target = 1
    db.commit()


def test_the_gift_unlocks_only_after_the_day_counts_as_studied(
    client: TestClient, db_session: Session
) -> None:
    """Nút quà sáng lên SAU bài đầu tiên, không sáng sẵn lúc mở app (ADR-011 §2).

    Thưởng cho việc mở app mà không học là dạy đúng cái hành vi không muốn; quà
    vẫn là "vào nhận mỗi ngày", chỉ khác ở chỗ nó có một câu để nói.
    """
    story = build_tree(db_session, marker="gift")
    headers = learner_auth(client, db_session, "gift@example.com")
    user = _user(db_session, "gift@example.com")

    wallet = client.get("/api/v1/ruby", headers=headers).json()
    assert wallet["gift"] == {"amount": 3, "unlocked": False, "claimed": False}
    assert client.post("/api/v1/ruby/gift", headers=headers).json()["granted"] == 0
    assert ruby.balance(db_session, user.id) == 0

    items = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()["items"]
    client.post(
        f"/api/v1/dictation/{items[0]['id']}/attempts",
        json={"submitted_text": "first sentence here"},
        headers=headers,
    )

    claimed = client.post("/api/v1/ruby/gift", headers=headers).json()
    assert claimed["granted"] == 3 and claimed["balance"] == 3
    assert claimed["gift"]["claimed"] is True


def test_claiming_the_gift_twice_pays_once(client: TestClient, db_session: Session) -> None:
    """Bấm đúp không phải sự cố: `source_id` tất định, lần hai bị khoá từ chối,
    và câu trả lời là 200 với `granted = 0` chứ không phải một hộp thoại lỗi."""
    story = build_tree(db_session, marker="twice")
    headers = learner_auth(client, db_session, "twice@example.com")
    items = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()["items"]
    client.post(
        f"/api/v1/dictation/{items[0]['id']}/attempts",
        json={"submitted_text": "first sentence here"},
        headers=headers,
    )

    first = client.post("/api/v1/ruby/gift", headers=headers).json()
    second = client.post("/api/v1/ruby/gift", headers=headers)
    assert first["granted"] == 3
    assert second.status_code == 200 and second.json()["granted"] == 0
    assert second.json()["balance"] == 3


def test_finishing_every_task_pays_once_a_day(client: TestClient, db_session: Session) -> None:
    """`daily_all` trả cho việc đóng TRỌN một ngày, không cho từng khe.

    XP đã trả cho từng khe rồi; hai phần thưởng cùng hình dạng trên cùng một hành
    động là chỗ người dùng thôi phân biệt được hai đơn vị.
    """
    story = build_tree(db_session, marker="all")
    headers = learner_auth(client, db_session, "all@example.com")
    user = _user(db_session, "all@example.com")
    _disable_every_slot_but(db_session, client, headers, KIND_DICTATION)

    body = client.get("/api/v1/daily-tasks", headers=headers).json()
    assert body["ruby_awarded"] == 0

    items = client.get(f"/api/v1/dictation-stories/{story.id}", headers=headers).json()["items"]
    client.post(
        f"/api/v1/dictation/{items[0]['id']}/attempts",
        json={"submitted_text": "first sentence here"},
        headers=headers,
    )

    done = client.get("/api/v1/daily-tasks", headers=headers).json()
    assert all(task["done"] for task in done["tasks"])
    assert done["ruby_awarded"] == 10
    assert client.get("/api/v1/daily-tasks", headers=headers).json()["ruby_awarded"] == 0
    assert ruby.balance(db_session, user.id) == 10


def test_an_empty_task_list_is_not_a_finished_day(client: TestClient, db_session: Session) -> None:
    """`all([])` là `True`, nên một tài khoản không còn khe nào bật sẽ được trả
    mỗi ngày mà chẳng làm gì — chỗ hỏng im lặng nhất của cả lát này."""
    learner_auth(client, db_session, "empty@example.com")
    user = _user(db_session, "empty@example.com")
    assert ruby_daily.grant_all_tasks_done(db_session, user.id, datetime.now(UTC).date(), []) == 0


def test_a_streak_milestone_pays_once_ever(client: TestClient, db_session: Session) -> None:
    """Mốc 7 trả một lần trong đời tài khoản; mốc 14 trả tiếp.

    `source_id` sinh từ SỐ MỐC chứ không từ ngày, nên đứt chuỗi rồi gây lại tới 7
    không trả lần nữa — nếu không thì người cứ bảy ngày nghỉ một lần có một nguồn
    thu đều đặn.
    """
    headers = learner_auth(client, db_session, "streak@example.com")
    user = _user(db_session, "streak@example.com")
    assert headers

    assert ruby_daily.grant_streak_milestone(db_session, user.id, 6) == 0
    assert ruby_daily.grant_streak_milestone(db_session, user.id, 7) == 20
    assert ruby_daily.grant_streak_milestone(db_session, user.id, 7) == 0
    assert ruby_daily.grant_streak_milestone(db_session, user.id, 13) == 0
    assert ruby_daily.grant_streak_milestone(db_session, user.id, 14) == 20
    db_session.commit()
    assert ruby.balance(db_session, user.id) == 40


def test_the_endpoint_pays_the_streak_milestone_from_real_history(
    client: TestClient, db_session: Session
) -> None:
    """Chuỗi ngày đọc từ `gather_stats`, tức là CÙNG con số hiển thị trên hồ sơ.

    Một phép đếm thứ hai ở đây sẽ trả thưởng vào một ngày khác với ngày thanh
    chuỗi ngày sáng lên, và không có gì báo.
    """
    headers = learner_auth(client, db_session, "seven@example.com")
    user = _user(db_session, "seven@example.com")
    now = datetime.now(UTC)
    for back in range(7):
        db_session.add(
            VocabularyReviewLog(
                user_id=user.id,
                entry_id=uuid.uuid4(),
                grade=4,
                interval_days=1,
                ease_factor=2.5,
                reviewed_at=now - timedelta(days=back, hours=1),
            )
        )
    db_session.commit()

    body = client.get("/api/v1/daily-tasks", headers=headers).json()
    assert body["ruby_awarded"] == 20
    assert client.get("/api/v1/profile/stats", headers=headers).json()["current_streak"] == 7
