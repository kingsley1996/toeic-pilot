"""Leo tháp dungeon: run, battle theo lượt, chết và đánh lại (migration 098).

Chỉ kiểm dòng chảy mà hỏng thì người chơi kẹt: mở battle, đúng hết bước thì
sang tầng, sai thì mất máu, hết máu thì chết và đánh lại từ checkpoint. Mọi
bước kiểm dùng đúng đường HTTP mà client đi, không gọi service trực tiếp —
trừ bảng công thức, thứ không có đường HTTP nào.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.pet import _answer_mode as answer_mode
from app.api.routes.pet import _choice_key as choice_key
from app.models import DungeonRun, Encounter, PetState, User
from app.models.vocabulary import VocabularyEntry
from app.services import dungeon


def _learner(db: Session, email: str = "climber@example.com") -> User:
    user = User(email=email, hashed_password="x", role="learner")
    db.add(user)
    db.commit()
    return user


def _pet(db: Session, user: User) -> PetState:
    state = PetState(user_id=user.id, species="duck")
    db.add(state)
    db.commit()
    return state


def _words(db: Session, count: int = 10) -> list[VocabularyEntry]:
    rows = [
        VocabularyEntry(
            headword=f"dword{index}",
            part_of_speech="noun",
            meaning_en=f"meaning {index}",
            meaning_vi=f"ngữ {index}",
            status="published",
        )
        for index in range(count)
    ]
    db.add_all(rows)
    db.commit()
    return rows


def _solve(db: Session, row: Encounter) -> dict[str, str]:
    entry = db.get(VocabularyEntry, row.target_id)
    assert entry is not None
    if answer_mode(row) == "choice":
        return {"choice": choice_key(row.id, entry.id)}
    return {"text": entry.headword}


def _wrong(row: Encounter) -> dict[str, str]:
    if answer_mode(row) == "choice":
        return {"choice": "0" * 16}
    return {"text": "sai hoàn toàn"}


def _state(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get("/api/v1/dungeon/state", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_formulas_match_the_spec() -> None:
    assert (dungeon.monster_hp(1), dungeon.monster_hp(100)) == (3, 13)
    assert (dungeon.monster_dmg(1), dungeon.monster_dmg(100)) == (2, 8)
    assert dungeon.pet_max_hp(1) == 22
    assert dungeon.battle_reward(1) == 10
    assert dungeon.MAX_FLOOR == 100 and dungeon.CHECKPOINT_EVERY == 10


def test_state_without_a_pet_is_a_409_not_a_run(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    response = client.get("/api/v1/dungeon/state", headers=headers)
    assert response.status_code == 409
    assert db_session.get(DungeonRun, user.id) is None


def test_first_visit_opens_floor_one_with_full_hp(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    _words(db_session)
    _pet(db_session, user)

    body = _state(client, headers)
    assert body["floor"] == 1 and body["status"] == "fighting"
    assert body["pet_hp"] == body["pet_max_hp"] == 22
    battle = body["battle"]
    assert battle["kind"] == "dungeon" and battle["steps_total"] == 3
    assert battle["task"]["prompt"] is not None


def test_clearing_every_step_advances_one_floor(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    _words(db_session)
    _pet(db_session, user)

    battle_id = _state(client, headers)["battle"]["id"]
    view = None
    for step in range(3):
        row = db_session.get(Encounter, uuid.UUID(battle_id))
        assert row is not None and row.state == "waiting"
        body = client.post(
            f"/api/v1/pet/encounters/{battle_id}/answer",
            headers=headers,
            json=_solve(db_session, row),
        ).json()
        assert body["correct"] is True
        view = body["dungeon"]
        if step < 2:
            assert body["done"] is False and view["monster_hp"] == 2 - step
    assert body["done"] is True and body["reward_ruby"] > 0
    assert view["floor"] == 2 and view["status"] == "fighting"
    assert view["monster_hp"] == 0

    again = _state(client, headers)
    assert again["floor"] == 2 and again["battle"]["steps_total"] == 3


def test_wrong_answers_cost_hp_and_kill_at_zero(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    _words(db_session)
    _pet(db_session, user)

    battle_id = _state(client, headers)["battle"]["id"]
    row = db_session.get(Encounter, uuid.UUID(battle_id))
    body = client.post(
        f"/api/v1/pet/encounters/{battle_id}/answer",
        headers=headers,
        json=_wrong(row),
    ).json()
    assert body["correct"] is False and body["done"] is False
    assert body["dungeon"]["pet_hp"] == 22 - 2  # dmg tầng 1

    # Đánh tới chết: mỗi lượt sai mất 2 máu trên 22 máu.
    for _ in range(20):
        row = db_session.get(Encounter, uuid.UUID(battle_id))
        if row.state != "waiting":
            break
        body = client.post(
            f"/api/v1/pet/encounters/{battle_id}/answer",
            headers=headers,
            json=_wrong(row),
        ).json()
    assert body["dungeon"]["status"] == "dead" and body["dungeon"]["pet_hp"] == 0

    # Battle của run thua không trả lời được nữa.
    gone = client.post(
        f"/api/v1/pet/encounters/{battle_id}/answer",
        headers=headers,
        json=_wrong(row),
    )
    assert gone.status_code == 409

    # Đánh lại: về checkpoint (tầng 1), máu đầy, battle mới ở lượt đọc sau.
    retry = client.post("/api/v1/dungeon/retry", headers=headers).json()
    assert retry["status"] == "fighting" and retry["floor"] == 1
    assert retry["pet_hp"] == retry["pet_max_hp"] and retry["battle"] is None
    assert _state(client, headers)["battle"] is not None


def test_retry_while_alive_is_a_free_heal_and_is_refused(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    _words(db_session)
    _pet(db_session, user)
    _state(client, headers)

    response = client.post("/api/v1/dungeon/retry", headers=headers)
    assert response.status_code == 409


def test_orphan_battle_cannot_be_answered(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Battle không thuộc run đang đánh (run chết, battle cũ) thì 409.

    Không có cổng này thì client cũ giữ id battle sau khi thua vẫn chấm điểm
    và nhận ruby trên một trận không còn ai chứng kiến.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    words = _words(db_session)
    _pet(db_session, user)

    row = Encounter(
        user_id=user.id,
        kind="dungeon",
        task_kind="vocabulary",
        target_id=words[0].id,
        steps_total=3,
        reward_ruby=10,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(row)
    db_session.commit()

    response = client.post(
        f"/api/v1/pet/encounters/{row.id}/answer",
        headers=headers,
        json={"text": words[0].headword},
    )
    assert response.status_code == 409


def test_dungeon_battles_stay_out_of_the_main_board(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Battle trong tháp không hiện ở `GET /encounters` (map chính).

    Lọt ra đó là một vị khách đứng trên bản đồ mà không ai mời, và `sync()`
    còn có thể hết hạn nó giữa trận.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    _words(db_session)
    _pet(db_session, user)
    battle_id = _state(client, headers)["battle"]["id"]

    listed = client.get("/api/v1/pet/encounters", headers=headers).json()
    assert all(item["id"] != battle_id for item in listed)
    assert all(item["kind"] != "dungeon" for item in listed)


def test_checkpoint_every_ten_floors(db_session: Session) -> None:
    user = _learner(db_session, email="checkpoint@example.com")

    run = dungeon.ensure_run(db_session, user.id, 1)
    run.floor = 10
    run.pet_hp = dungeon.pet_max_hp(1)
    db_session.commit()
    dungeon.register_clear(db_session, run, pet_max_hp=dungeon.pet_max_hp(1))
    assert (run.floor, run.checkpoint) == (11, 10)
    run.floor = 11
    dungeon.register_clear(db_session, run, pet_max_hp=dungeon.pet_max_hp(1))
    assert (run.floor, run.checkpoint) == (12, 10)

    run.status = "dead"
    dungeon.retry(db_session, run, pet_max_hp=dungeon.pet_max_hp(1))
    assert (run.floor, run.status) == (10, "fighting")
