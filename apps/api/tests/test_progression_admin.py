"""Cấu hình hệ level trên đường quản trị.

Bốn thứ được kiểm ở đây, và cả bốn đều là loại lỗi không ai báo:

  · học viên mở được màn hình chỉnh XP của chính mình;
  · sửa mục tiêu một khe rồi XP của những ngày đã thưởng được trao lại;
  · ghi một bảng level không tăng đều, khiến người học rơi xuống một level thấp
    hơn XP của họ — và `level_reached` ghi lại mốc sai đó vĩnh viễn;
  · hạ mức XP làm tụt điểm đã trao trong quá khứ.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.progression import DailyTaskSlot
from app.models.user import User
from app.services import progression_config
from app.services.daily_tasks import grant_rewards, tasks_for
from app.services.progression import total_xp


def _headers(client, db_session, role: str) -> dict[str, str]:
    """Một tài khoản mới ở vai đã cho, và header Bearer của nó.

    Vai đặt qua `db_session` chứ không qua một session riêng: bộ test chạy SQLite
    trong bộ nhớ và chỉ có ĐÚNG một kết nối, nên `SessionLocal()` mở ra một
    database khác — trống rỗng — và tài khoản vừa đăng ký không có ở đó.
    """
    email = f"prog-{role}-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "x" * 12})
    if role != "learner":
        user = db_session.scalars(select(User).where(User.email == email)).one()
        user.role = role
        db_session.commit()
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "x" * 12}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def test_a_learner_cannot_reach_the_configuration(client, db_session):
    """Và một editor cũng không.

    Biên tập viên soạn nội dung; các con số này quyết định level của mọi tài
    khoản và đổ vào một sổ cái không sửa lại được. Đó là quyền vận hành.
    """
    for role in ("learner", "editor"):
        headers = _headers(client, db_session, role)
        assert client.get("/api/v1/admin/progression", headers=headers).status_code == 403


def test_admin_reads_a_seeded_config_on_the_first_open(client, db_session):
    """Lần đọc đầu tiên tự seed, nên màn hình không bao giờ mở ra trống rỗng."""
    headers = _headers(client, db_session, "admin")
    body = client.get("/api/v1/admin/progression", headers=headers).json()

    assert body["setting"]["daily_xp_cap"] == 120
    assert len(body["slots"]) == 3
    assert len(body["badges"]) == 15
    assert len(body["frames"]) == 4
    assert body["levels"][0] == {"level": 1, "xp_required": 0}
    assert len(body["levels"]) == body["setting"]["max_level"]


def test_a_level_table_that_does_not_climb_is_refused(client, db_session):
    """Bảng ngưỡng kiểm như một KHỐI, không phải từng hàng.

    Một bảng không tăng đều làm phép tra cứu dừng sai chỗ, và vì `level_reached`
    chỉ đi lên, một mốc sai ghi xuống trong lúc đó thì ở lại mãi.
    """
    headers = _headers(client, db_session, "admin")

    flat = client.put(
        "/api/v1/admin/progression/levels",
        headers=headers,
        json={"tiers": [{"level": 1, "xp_required": 0}, {"level": 2, "xp_required": 0}]},
    )
    assert flat.status_code == 422

    gap = client.put(
        "/api/v1/admin/progression/levels",
        headers=headers,
        json={"tiers": [{"level": 1, "xp_required": 0}, {"level": 3, "xp_required": 50}]},
    )
    assert gap.status_code == 422

    good = client.put(
        "/api/v1/admin/progression/levels",
        headers=headers,
        json={"tiers": [{"level": 1, "xp_required": 0}, {"level": 2, "xp_required": 40}]},
    )
    assert good.status_code == 200
    assert len(good.json()["levels"]) == 2


def test_raising_the_curve_never_takes_a_level_away(client, db_session):
    """Mốc nước cao: nâng chuẩn không lấy lại level của ai.

    Đây là điều đã hứa khi mở cấu hình cho admin sửa. Không có nó thì một lần gõ
    nhầm hệ số là hàng loạt người mất level, và không có gì hoàn lại được.
    """
    from app.services.progression import award

    headers = _headers(client, db_session, "admin")
    learner = _headers(client, db_session, "learner")
    learner_id = db_session.scalars(
        select(User.id).where(User.email.like("prog-learner-%"))
    ).first()
    assert learner_id is not None

    client.put(
        "/api/v1/admin/progression/levels",
        headers=headers,
        json={"tiers": [{"level": 1, "xp_required": 0}, {"level": 2, "xp_required": 10}]},
    )
    award(
        db_session,
        user_id=learner_id,
        source_type="vocabulary_review",
        source_id=uuid.uuid4(),
        amount=10,
        timezone="UTC",
    )
    db_session.commit()
    assert client.get("/api/v1/profile/progression", headers=learner).json()["level"] == 2

    # Nâng chuẩn: level 2 giờ đòi 5000 XP mà người học chỉ có 10.
    client.put(
        "/api/v1/admin/progression/levels",
        headers=headers,
        json={"tiers": [{"level": 1, "xp_required": 0}, {"level": 2, "xp_required": 5000}]},
    )
    body = client.get("/api/v1/profile/progression", headers=learner).json()
    assert body["level"] == 2, "level đã đạt thì không lấy lại"
    assert body["xp_total"] == 10, "và XP thì không đổi — sổ cái không bị đụng tới"


def test_editing_a_slot_does_not_re_award_a_day_already_paid(client, db_session):
    """`id` của khe là thứ chống trao lại, nên đổi mục tiêu và nhãn là an toàn.

    Đây là lý do khe phải là một HÀNG chứ không phải một mã chuỗi: mã đổi theo
    tên, và đổi tên một khe sẽ trao thưởng lần nữa cho mọi ngày đã trao.
    """
    headers = _headers(client, db_session, "admin")
    user = User(
        email=f"slot-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("x" * 12),
    )
    db_session.add(user)
    db_session.flush()

    slot = progression_config.slots(db_session)[0]
    day = datetime.now(tz=UTC).date()
    _, tasks = tasks_for(db_session, user.id, "UTC")
    done = [t for t in tasks if t.slot_id == slot.id]
    done[0] = type(done[0])(**{**done[0].__dict__, "done": True, "progress": done[0].target})

    assert grant_rewards(db_session, user.id, "UTC", day, done) == done[0].xp
    before = total_xp(db_session, user.id)

    client.patch(
        f"/api/v1/admin/progression/slots/{slot.id}",
        headers=headers,
        json={"label": "Ôn từ vựng (đã đổi tên)", "target": 25},
    )
    db_session.expire_all()
    assert grant_rewards(db_session, user.id, "UTC", day, done) == 0
    assert total_xp(db_session, user.id) == before


def test_lowering_an_xp_rate_leaves_the_ledger_alone(client, db_session):
    """Sổ cái ghi số điểm ĐÃ TRAO, nên hạ mức hôm nay không rút của quá khứ.

    Chính tính chất này là thứ khiến các mức điểm an toàn để mở cho admin sửa.
    """
    from app.services.progression import award, xp_for

    headers = _headers(client, db_session, "admin")
    user = User(
        email=f"rate-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("x" * 12),
    )
    db_session.add(user)
    db_session.flush()

    award(
        db_session,
        user_id=user.id,
        source_type="vocabulary_review",
        source_id=uuid.uuid4(),
        amount=xp_for(db_session, "vocabulary_review"),
        timezone="UTC",
    )
    db_session.flush()
    before = total_xp(db_session, user.id)
    assert before == 2

    client.patch(
        "/api/v1/admin/progression/setting",
        headers=headers,
        json={"xp_vocabulary_review": 1},
    )
    db_session.expire_all()
    assert total_xp(db_session, user.id) == before, "hàng cũ giữ nguyên số điểm đã trao"
    assert xp_for(db_session, "vocabulary_review") == 1, "lần trao kế tiếp dùng mức mới"


def test_a_new_slot_shows_up_for_learners(client, db_session):
    """Thêm một khe là thêm một hàng — không cần triển khai lại gì cả."""
    headers = _headers(client, db_session, "admin")
    created = client.post(
        "/api/v1/admin/progression/slots",
        headers=headers,
        json={
            "kind": "dictation_complete",
            "label": "Chép thêm 5 câu",
            "target": 5,
            "xp": 15,
            "position": 9,
        },
    )
    assert created.status_code == 201

    user = User(
        email=f"newslot-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("x" * 12),
    )
    db_session.add(user)
    db_session.flush()
    _, tasks = tasks_for(db_session, user.id, "UTC")
    assert [t.label for t in tasks][-1] == "Chép thêm 5 câu"
    assert len(tasks) == 4

    # Và tắt nó thì học viên không thấy nữa, nhưng hàng vẫn còn để chống trao lại.
    row = db_session.scalars(
        select(DailyTaskSlot).where(DailyTaskSlot.label == "Chép thêm 5 câu")
    ).one()
    client.patch(
        f"/api/v1/admin/progression/slots/{row.id}", headers=headers, json={"enabled": False}
    )
    db_session.expire_all()
    _, after = tasks_for(db_session, user.id, "UTC")
    assert len(after) == 3
    assert db_session.get(DailyTaskSlot, row.id) is not None


def test_regenerating_levels_overwrites_hand_edits(client, db_session):
    """Nút sinh lại GHI ĐÈ, và bài này ghim điều đó để giao diện phải nói trước."""
    headers = _headers(client, db_session, "admin")
    client.put(
        "/api/v1/admin/progression/levels",
        headers=headers,
        json={"tiers": [{"level": 1, "xp_required": 0}, {"level": 2, "xp_required": 7}]},
    )
    body = client.post("/api/v1/admin/progression/levels/generate", headers=headers).json()
    assert len(body["levels"]) == body["setting"]["max_level"]
    assert body["levels"][1]["xp_required"] == 151


def test_art_key_must_belong_to_the_progression_area(client, db_session):
    """Khoá tranh phải nằm dưới `progression/`, và file phải có thật.

    Thiếu lớp thứ nhất thì đây là một đường ghi chuỗi tuỳ ý: trỏ khung vào một
    ảnh nội dung, rồi lệnh dọn ảnh mồ côi xoá mất thứ đang được dùng. Thiếu lớp
    thứ hai thì giao diện hiện ảnh vỡ cho tới khi có người để ý — và không ai để
    ý một cái khung.
    """
    headers = _headers(client, db_session, "admin")

    wrong_area = client.patch(
        "/api/v1/admin/progression/frames/bronze",
        headers=headers,
        json={"image_storage_key": "images/ab/cd/ef.png"},
    )
    assert wrong_area.status_code == 400
    assert "vùng tranh" in wrong_area.json()["detail"]

    missing_file = client.patch(
        "/api/v1/admin/progression/badges/first_steps",
        headers=headers,
        json={"image_storage_key": "progression/ab/cd/khong-co-that.png"},
    )
    assert missing_file.status_code == 400


def test_art_can_be_attached_and_removed(client, db_session, monkeypatch):
    """Gắn tranh rồi gỡ ra, và `null` phải khác với "không gửi khoá này".

    Một phép gộp `value or existing` không phân biệt được hai trường hợp đó, và
    cái hỏng thì im lặng: gỡ ảnh trả về 200 và không đổi gì cả.
    """
    from app.core import storage

    driver = storage.get_driver("image")
    monkeypatch.setattr(type(driver), "verify", lambda self, key: None, raising=False)

    headers = _headers(client, db_session, "admin")
    key = "progression/ab/cd/khung-vang.png"

    attached = client.patch(
        "/api/v1/admin/progression/frames/gold", headers=headers, json={"image_storage_key": key}
    ).json()
    gold = next(f for f in attached["frames"] if f["code"] == "gold")
    assert gold["image_storage_key"] == key
    assert gold["image_url"] and gold["image_url"].endswith(key)

    # Sửa một trường khác mà KHÔNG gửi khoá: ảnh phải ở nguyên đó.
    kept = client.patch(
        "/api/v1/admin/progression/frames/gold", headers=headers, json={"label": "Vàng ròng"}
    ).json()
    assert next(f for f in kept["frames"] if f["code"] == "gold")["image_storage_key"] == key

    removed = client.patch(
        "/api/v1/admin/progression/frames/gold",
        headers=headers,
        json={"image_storage_key": None},
    ).json()
    assert next(f for f in removed["frames"] if f["code"] == "gold")["image_storage_key"] is None


def test_an_admin_wears_the_top_frame_without_gaining_a_level(client, db_session):
    """Khung cao nhất mở sẵn cho quản trị viên — và DỪNG ở đó.

    Nếu ưu đãi này chạm tới level thì con số trên hồ sơ họ thành một lời nói dối,
    và nó lây sang các huy hiệu `level_*` vốn đo bằng đúng con số đó. Bài này ghim
    cả hai vế: khung có, level không.
    """
    admin = _headers(client, db_session, "admin")
    learner = _headers(client, db_session, "learner")

    top = max(progression_config.frame_tiers(db_session), key=lambda tier: tier.min_level).code

    body = client.get("/api/v1/profile/progression", headers=admin).json()
    assert body["frame"]["code"] == top
    assert body["level"] == 1, "khung là trang trí, không phải một cách lên level"
    assert body["xp_total"] == 0

    # Học viên cùng level thì vẫn chưa có khung nào.
    assert client.get("/api/v1/profile/progression", headers=learner).json()["frame"] is None
