"""Luật sinh của những cuộc chạm mặt ở Petland (ADR-012 §1).

**Đây là chỗ duy nhất phá được ràng buộc "không bỏ lỡ được thứ chưa từng có",
và hỏng ở đây thì giao diện không thấy gì cả**: một NPC không xuất hiện trông
hệt như một NPC chưa tới giờ. Nên `sync` nhận `now` và `rng` làm tham số, cùng
lý do `srs.review` nhận `now` và `gacha.roll` nhận `rng` — một luật phụ thuộc
đồng hồ và may rủi mà không tiêm được thì không bài kiểm nào nói được gì về nó.
"""

import json
import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.pet import _answer_mode as answer_mode
from app.api.routes.pet import _choice_key as choice_key
from app.models import DictationItem, Encounter, PetOwned, PetState, User
from app.models.audio import AudioAsset
from app.models.vocabulary import VocabularyEntry
from app.services import encounters
from app.services.pet import XP_PER_ENCOUNTER

T0 = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)


def _learner(db: Session, email: str = "meet@example.com") -> User:
    user = User(email=email, hashed_password="x", role="learner")
    db.add(user)
    db.commit()
    return user


def _pet(db: Session, user: User) -> PetState:
    state = PetState(user_id=user.id, species="duck")
    db.add(state)
    db.commit()
    return state


def _npc_only(db: Session) -> None:
    """Đẩy nhịp kẻ xâm nhập ra xa để chỉ còn một làn chạy.

    Hai làn cùng chạy dưới một `rng` thật thì bài kiểm về làn NPC thỉnh thoảng
    bắt được một kẻ xâm nhập và đỏ vì lý do chẳng liên quan — mà một bài kiểm
    thỉnh thoảng đỏ thì người ta chạy lại chứ không đọc, và nó thôi bảo vệ được
    gì. Nhịp là HÀNG dữ liệu chính là để chỗ này chỉnh được.
    """
    encounters.settings_row(db).intruder_gap_seconds = 86_400
    db.commit()


def _words(db: Session, count: int = 5) -> list[VocabularyEntry]:
    rows = [
        VocabularyEntry(
            headword=f"word{index}",
            part_of_speech="noun",
            meaning_en=f"meaning {index}",
            meaning_vi=f"nghĩa {index}",
            status="published",
        )
        for index in range(count)
    ]
    db.add_all(rows)
    db.commit()
    return rows


def _sentence(db: Session, text: str = "The meeting is at noon.") -> DictationItem:
    asset = AudioAsset(
        storage_key=f"audio/{uuid.uuid4().hex}.mp3",
        source_hash=uuid.uuid4().hex,
        source_text=text,
        voice="us_female_1",
        accent="en-US",
        engine="edge-tts",
        engine_version="7",
        duration_ms=2000,
        size_bytes=1024,
    )
    db.add(asset)
    db.flush()
    item = DictationItem(transcript=text, status="published", audio_asset_id=asset.id)
    db.add(item)
    db.commit()
    return item


def test_the_first_read_only_sets_a_date_and_never_spawns(db_session: Session) -> None:
    """Không ai bị một NPC nhảy vào mặt ở giây đầu tiên.

    Cái giá của việc bỏ dòng này là một tài khoản vừa mở bảng thú cưng lần đầu
    đã bị giao việc trước khi kịp hiểu bảng ấy là gì — và không có gì báo lỗi,
    vì hàng dữ liệu hoàn toàn hợp lệ.
    """
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _npc_only(db_session)
    _words(db_session)

    assert encounters.sync(db_session, user_id=user.id, pet=pet, now=T0) == []
    assert pet.next_npc_at is not None
    assert pet.next_npc_at.replace(tzinfo=UTC) > T0


def test_nothing_spawns_before_the_appointment_and_one_does_after(db_session: Session) -> None:
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _npc_only(db_session)
    _words(db_session)
    encounters.sync(db_session, user_id=user.id, pet=pet, now=T0)

    early = encounters.sync(db_session, user_id=user.id, pet=pet, now=T0 + timedelta(minutes=5))
    assert early == []

    # Nhịp mặc định là 20 phút, dao động tối đa 1,4 lần — nên 30 phút chắc chắn
    # đã qua giờ hẹn, dù `rng` bốc ra con số nào.
    late = encounters.sync(db_session, user_id=user.id, pet=pet, now=T0 + timedelta(minutes=30))
    assert len(late) == 1 and late[0].state == "waiting"


class _PickDictation(random.Random):
    """`rng` luôn bốc ra dạng chép chính tả, để luật "chỉ giao từ vựng" đo được thật.

    Với `SystemRandom` thì bài này xanh phần lớn số lần dù luật có bị gỡ ra hay
    không — và một bài kiểm xanh vì may thì không nói được điều gì.
    """

    def random(self) -> float:
        return 0.0


def test_a_sick_pet_gets_a_one_step_rescue_task_in_a_lane_of_its_own(
    db_session: Session,
) -> None:
    """Nửa "thú xin được chú ý" của §12, và nó KHÔNG mượn làn NPC.

    Mượn thì kéo theo cả những thứ không thuộc về nó: nhịp hai mươi phút, trần
    hai cuộc mỗi loại, số bước, và mức thưởng ruby — nên cứu con thú lại thành
    một nguồn thu, và một lần cứu tiêu mất suất NPC của người học.

    Làn riêng nên không có giờ hẹn: sinh theo TRẠNG THÁI, không theo đồng hồ. Và
    nó tự dọn khi con thú khoẻ lại — để lại thì đó là một câu hỏi lơ lửng mà
    không ai biết vì sao có.
    """
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _npc_only(db_session)
    _words(db_session)
    # Kho chép chính tả CÓ hàng, và `rng` bốc luôn ra nó — nếu không, "hồi phục
    # chỉ giao từ vựng" sẽ xanh vì may chứ không vì luật.
    _sentence(db_session)
    rng = _PickDictation()
    at5 = T0 + timedelta(minutes=5)
    encounters.sync(db_session, user_id=user.id, pet=pet, now=T0, rng=rng)

    # Chưa tới giờ hẹn của NPC: khoẻ thì trống, ốm thì có nhiệm vụ hồi phục.
    assert encounters.sync(db_session, user_id=user.id, pet=pet, now=at5, rng=rng) == []
    rows = encounters.sync(db_session, user_id=user.id, pet=pet, sick=True, now=at5, rng=rng)
    assert len(rows) == 1
    task = rows[0]
    assert task.kind == "rescue"
    assert task.steps_total == 1, "một câu duy nhất — đây là lối ra, không phải một trận"
    assert task.reward_ruby == 0, "phần thưởng là con thú đứng dậy, không phải tiền"
    assert task.task_kind == "vocabulary", (
        "chỉ giao từ vựng: gõ lại trọn một câu nghe được là một bức tường nữa "
        "trước cái cửa, mà đây là LỐI RA chứ không phải bài để thử sức"
    )

    again = encounters.sync(
        db_session, user_id=user.id, pet=pet, sick=True, now=T0 + timedelta(minutes=6), rng=rng
    )
    assert len(again) == 1, "đã có nhiệm vụ thì không sinh thêm"

    # Không tiêu suất của NPC: giờ hẹn của làn kia không bị đụng tới.
    healthy = encounters.sync(
        db_session, user_id=user.id, pet=pet, now=T0 + timedelta(minutes=7), rng=rng
    )
    assert healthy == [], "khoẻ lại thì nhiệm vụ hồi phục được dọn đi"


def test_reading_ten_times_in_a_row_does_not_make_ten_encounters(db_session: Session) -> None:
    """`GET /pet/encounters` ghi, nên gọi lại phải là chuyện an toàn.

    Cùng hình dạng với `GET /daily-tasks`. Trần mỗi loại giữ cho nó an toàn, chứ
    không phải "mỗi lúc một cuộc" — mà kể cả có trần thì đọc dồn dập vẫn không
    được phép lấp đầy trần trong một giây: giờ hẹn mới là thứ định nhịp.
    """
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _npc_only(db_session)
    _words(db_session)
    encounters.sync(db_session, user_id=user.id, pet=pet, now=T0)

    at = T0 + timedelta(minutes=30)
    first = encounters.sync(db_session, user_id=user.id, pet=pet, now=at)
    assert len(first) == 1
    for _ in range(10):
        again = encounters.sync(db_session, user_id=user.id, pet=pet, now=at)
        assert [row.id for row in again] == [first[0].id]

    db_session.commit()
    waiting = db_session.query(Encounter).filter(Encounter.state == "waiting").count()
    assert waiting == 1


def test_a_new_encounter_never_replaces_one_already_waiting(db_session: Session) -> None:
    """Cuộc mới đứng CẠNH cuộc cũ, không đè lên nó.

    Đây là chỗ bản một-cuộc-một-lúc sai nặng nhất: một người đang gõ dở câu trả
    lời sẽ thấy đề bài đổi dưới tay mình, và công sức của họ biến mất vì một cái
    đồng hồ ở đâu đó vừa điểm. Trần là **hai mỗi loại**, và trần ấy đếm riêng
    từng loại — một trần chung sẽ để NPC lấp kín bản đồ và kẻ xâm nhập không bao
    giờ có chỗ mà xuất hiện.
    """
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _words(db_session, count=12)

    at = T0
    encounters.sync(db_session, user_id=user.id, pet=pet, now=at)
    ids: list[uuid.UUID] = []
    # Nhảy từng giờ: đủ lâu để cả hai làn tới hẹn nhiều lần.
    for hour in range(1, 12):
        alive = encounters.sync(
            db_session, user_id=user.id, pet=pet, now=T0 + timedelta(hours=hour)
        )
        for row in alive:
            if row.id not in ids:
                ids.append(row.id)
        assert sum(1 for row in alive if row.kind == "npc") <= encounters.MAX_PER_KIND
        assert sum(1 for row in alive if row.kind == "intruder") <= encounters.MAX_PER_KIND

    # Có sinh thật, và không cuộc nào bị xoá để lấy chỗ: mọi cuộc từng xuất hiện
    # đều còn hàng, ở trạng thái `waiting` hoặc `expired`.
    assert len(ids) >= 2
    rows = db_session.query(Encounter).all()
    assert {row.id for row in rows} >= set(ids)
    assert all(row.state in ("waiting", "expired") for row in rows)


def test_letting_one_expire_does_not_summon_the_next_one_instantly(db_session: Session) -> None:
    """Bỏ lỡ một cuộc không được phép làm cuộc sau tới NGAY.

    Nếu không, để hết hạn rồi tải lại chính là cách gọi cuộc mới tới nhanh hơn,
    và cái nhịp xuất hiện — thứ duy nhất giới hạn ruby từ nhiệm vụ (ADR-012 §6)
    — không còn giới hạn gì cả.

    Khác bản trước ở chỗ nhịp ấy giờ do phép SINH giữ, không do phép hết hạn:
    mỗi lần sinh đã hẹn lần sau, nên hết hạn không cần hẹn lại nữa — và hẹn lại
    thêm ở đó chỉ còn là phạt người ta vì đã lờ một lời mời (§4 từ chối).
    """
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _npc_only(db_session)
    _words(db_session)
    encounters.sync(db_session, user_id=user.id, pet=pet, now=T0)

    born = encounters.sync(db_session, user_id=user.id, pet=pet, now=T0 + timedelta(minutes=30))
    assert len(born) == 1

    # Quá hạn (mặc định sống 10 phút) — dọn xong thì KHÔNG có cuộc mới ngay.
    dead_at = T0 + timedelta(minutes=41)
    assert encounters.sync(db_session, user_id=user.id, pet=pet, now=dead_at) == []
    assert born[0].state == "expired"
    assert pet.next_npc_at is not None
    assert pet.next_npc_at.replace(tzinfo=UTC) > dead_at


def test_an_empty_library_spawns_nothing_instead_of_a_broken_task(db_session: Session) -> None:
    """Kho rỗng thì không sinh ai, và giờ hẹn chỉ lùi một nhịp ngắn.

    Sinh ra một nhiệm vụ trỏ vào hư không sẽ tạo một thẻ không làm được nhưng
    vẫn chiếm chỗ trong mười phút — hỏng im lặng, đúng loại tệ nhất.
    """
    user = _learner(db_session)
    pet = _pet(db_session, user)
    _npc_only(db_session)
    encounters.sync(db_session, user_id=user.id, pet=pet, now=T0)

    assert encounters.sync(db_session, user_id=user.id, pet=pet, now=T0 + timedelta(hours=3)) == []
    assert db_session.query(Encounter).count() == 0


def test_a_dictation_quest_never_reaches_for_an_unpublished_sentence(
    db_session: Session,
) -> None:
    """Câu chưa xuất bản không được giao cho ai.

    Đây là đúng chỗ rò rỉ mà cây chép chính tả đã phải lọc `published` ở cả bốn
    tầng: một câu nháp lọt ra ngoài trông hoàn toàn bình thường, và không ai báo.
    Ràng buộc `ck_dictation_item_published_has_audio` đã lo phần "phải có bản
    thu" — nên bài kiểm này ghim phần database KHÔNG lo hộ.
    """
    user = _learner(db_session)
    draft = _sentence(db_session, "Still a draft.")
    draft.status = "draft"
    db_session.commit()

    rng = random.Random(1)
    assert encounters.pick_target(db_session, user.id, "dictation", rng) is None

    heard = _sentence(db_session)
    assert encounters.pick_target(db_session, user.id, "dictation", rng) == heard.id


def _solve(db: Session, row: Encounter, entry_id: uuid.UUID) -> dict[str, str]:
    """Câu trả lời ĐÚNG cho một nhiệm vụ từ vựng, theo cách nó đang hỏi."""
    entry = db.get(VocabularyEntry, entry_id)
    assert entry is not None
    if answer_mode(row) == "choice":
        return {"choice": choice_key(row.id, entry.id)}
    return {"text": entry.headword}


def test_the_task_never_carries_its_own_answer(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Đề bài không được chứa đáp án, và hai dạng hỏng theo hai kiểu khác nhau.

    Dạng gõ lại hỏi "từ này là gì" nên `headword` không được gửi — bản đầu gửi cả
    từ lẫn nghĩa vì màn thẻ lật cần cả hai, và bê nguyên sang đây là in đáp án
    lên đề. Dạng chọn nghĩa thì không được gửi `entry_id`: đáp án đúng khi ấy là
    ô có id trùng với nó, và cả câu hỏi trả lời được từ devtools.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    words = _words(db_session, count=8)
    _pet(db_session, user)

    row = Encounter(
        user_id=user.id,
        kind="npc",
        task_kind="vocabulary",
        target_id=words[0].id,
        steps_total=1,
        reward_ruby=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(row)
    db_session.commit()

    listed = client.get("/api/v1/pet/encounters", headers=headers).json()
    task = next(item for item in listed if item["id"] == str(row.id))["task"]
    serialised = json.dumps(task, ensure_ascii=False)
    if task["mode"] == "choice":
        # Hỏi ngược: in ra TỪ, và bốn nghĩa để chọn. Đáp án nằm trong bốn ô ấy —
        # đó là thể loại câu hỏi — nên thứ phải giấu là *ô nào*: không `entry_id`,
        # và không id thật ở bất cứ đâu trong phần trả lời.
        assert task["entry_id"] is None
        assert str(words[0].id) not in serialised
        assert len(task["choices"]) > 1
    else:
        assert task["prompt"] == words[0].meaning_vi
        assert words[0].headword not in serialised
        assert task["choices"] is None


def test_answering_an_intruder_step_moves_on_to_a_different_word(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Ba bước phải là ba câu hỏi khác nhau.

    Cùng một từ ba lần thì bước hai và ba chỉ là gõ lại đáp án vừa nhìn thấy, và
    cả đợt xâm nhập rút gọn thành một cái nút bấm ba lần — nó vẫn trả thưởng, vẫn
    chạy trơn, chỉ là không còn là bài học nào.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    _words(db_session, count=8)
    _pet(db_session, user)

    first_target = encounters.pick_target(db_session, user.id, "vocabulary", random.Random(2))
    assert first_target is not None
    row = Encounter(
        user_id=user.id,
        kind="intruder",
        task_kind="vocabulary",
        target_id=first_target,
        steps_total=3,
        reward_ruby=20,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(row)
    db_session.commit()

    response = client.post(
        f"/api/v1/pet/encounters/{row.id}/answer",
        headers=headers,
        json=_solve(db_session, row, first_target),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True and body["steps_done"] == 1 and body["done"] is False
    db_session.refresh(row)
    assert row.target_id != first_target


def test_a_wrong_vocabulary_answer_still_records_the_review(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Sai thì bước không tính, **nhưng lượt ôn vẫn được ghi**.

    Nó là một lượt học thật đã xảy ra: người học đã gặp từ, đã cố nhớ, và đã sai.
    Không ghi thì lịch ôn không biết chuyện đó và từ ấy quay lại đúng như cũ.
    """
    from app.models.vocabulary import VocabularyReviewState

    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    words = _words(db_session, count=8)
    _pet(db_session, user)

    row = Encounter(
        user_id=user.id,
        kind="npc",
        task_kind="vocabulary",
        target_id=words[0].id,
        steps_total=1,
        reward_ruby=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(row)
    db_session.commit()

    body = client.post(
        f"/api/v1/pet/encounters/{row.id}/answer",
        headers=headers,
        json={"text": "hoan-toan-sai", "choice": "sai"},
    ).json()
    assert body["correct"] is False and body["reward_ruby"] == 0
    state = db_session.query(VocabularyReviewState).filter_by(user_id=user.id).one()
    assert state.entry_id == words[0].id


def test_a_dictation_answer_is_graded_by_the_real_grader_and_recorded(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Câu gõ ở thẻ nhiệm vụ đi qua đúng bộ chấm của màn chép chính tả.

    Và `is_complete` là cổng, không phải `accuracy`: gõ đủ câu rồi gõ thêm vẫn
    ra 100%, nên lấy điểm làm cổng là trả ruby cho một bài sai rõ ràng.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    item = _sentence(db_session, "The meeting is at noon.")
    _pet(db_session, user)

    row = Encounter(
        user_id=user.id,
        kind="npc",
        task_kind="dictation",
        target_id=item.id,
        steps_total=1,
        reward_ruby=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(row)
    db_session.commit()

    wrong = client.post(
        f"/api/v1/pet/encounters/{row.id}/answer",
        headers=headers,
        json={"text": "The meeting is at noon and then some"},
    )
    assert wrong.status_code == 200
    assert wrong.json()["correct"] is False, "gõ thừa vẫn cho accuracy 100%"

    right = client.post(
        f"/api/v1/pet/encounters/{row.id}/answer",
        headers=headers,
        json={"text": "the meeting is at noon"},
    )
    body = right.json()
    assert body["correct"] is True and body["done"] is True and body["reward_ruby"] == 5

    # Lượt làm được GHI như mọi lượt chép chính tả khác — nếu không, người học
    # vừa làm bài xong mà lịch sử của họ không đổi.
    from app.models.dictation import DictationAttempt

    assert (
        db_session.query(DictationAttempt).filter(DictationAttempt.user_id == user.id).count() == 2
    )


def test_finishing_an_encounter_also_levels_the_pet(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Xong nhiệm vụ thì CON THÚ cũng được XP, không chỉ cái ví.

    Và nó đi qua đúng `_award` của mấy nút chăm sóc, nên trần ngày, mốc level và
    múi giờ người học là một bộ. Một đường trao XP thứ hai là chỗ trần ngày đếm
    thiếu mà không ai thấy — con thú lên level bằng một phép cộng mà cái trần
    không biết.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    words = _words(db_session, count=8)
    pet = _pet(db_session, user)
    owned = db_session.query(PetOwned).filter(PetOwned.user_id == user.id).one_or_none()
    if owned is None:
        client.get("/api/v1/pet", headers=headers)
        owned = db_session.query(PetOwned).filter(PetOwned.user_id == user.id).one()
    before = owned.xp
    del pet

    row = Encounter(
        user_id=user.id,
        kind="npc",
        task_kind="vocabulary",
        target_id=words[0].id,
        steps_total=1,
        reward_ruby=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(row)
    db_session.commit()

    body = client.post(
        f"/api/v1/pet/encounters/{row.id}/answer",
        headers=headers,
        json=_solve(db_session, row, words[0].id),
    ).json()
    assert body["done"] is True

    db_session.refresh(owned)
    assert owned.xp == before + XP_PER_ENCOUNTER["npc"]


def test_the_admin_spawn_button_respects_the_cap(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Nút gọi khách của admin **vẫn tôn trọng trần**.

    Nếu không thì nó thôi là công cụ thử và thành một cửa hậu: bấm mười lần là
    bốn mươi cuộc chạm mặt, tức là bốn mươi lần phần thưởng ruby mà cái nhịp —
    thứ duy nhất giới hạn nguồn ruby ấy (ADR-012 §6) — không hề biết tới.
    """
    headers = auth("admin")
    _words(db_session, count=12)

    first = client.post("/api/v1/admin/pet/encounters/spawn", headers=headers)
    assert first.status_code == 201
    assert first.json() == {"npc": encounters.MAX_PER_KIND, "intruder": encounters.MAX_PER_KIND}

    for _ in range(9):
        client.post("/api/v1/admin/pet/encounters/spawn", headers=headers)
    waiting = db_session.query(Encounter).filter(Encounter.state == "waiting").count()
    assert waiting == encounters.MAX_PER_KIND * 2


def test_only_an_admin_can_summon_encounters(client: TestClient, auth: dict) -> None:
    """Học viên bị 403. Cùng luật với cả tệp `admin_pet`, và cùng lý do: gọi
    khách ra là quyền vận hành, không phải quyền biên tập."""
    assert (
        client.post("/api/v1/admin/pet/encounters/spawn", headers=auth("learner")).status_code
        == 403
    )
    assert (
        client.post("/api/v1/admin/pet/encounters/spawn", headers=auth("editor")).status_code == 403
    )


def test_a_hint_opens_a_quarter_then_a_half_and_stops(db_session: Session) -> None:
    """Luật gợi ý, đo thẳng trên hàm thuần.

    Một phần tư rồi một nửa, chứ không phải một chữ mỗi lần: với một từ mười chữ
    thì mở từng chữ nghĩa là hai lần gợi ý chỉ ra hai chữ — không gỡ được gì, và
    cái nút thành trang trí. Không quá một nửa, vì phần còn phải nhớ chính là thứ
    phân biệt một bài kiểm với một ô điền sẵn.
    """
    assert encounters.hint_for("negotiation", 0) == "neg········"
    assert encounters.hint_for("negotiation", 1) == "negoti·····"
    # Từ ngắn vẫn phải hở ít nhất một chữ, và không bao giờ hở hết.
    assert encounters.hint_for("go", 0) == "g·"
    assert encounters.hint_for("go", 1) == "g·"
    assert all("·" in encounters.hint_for(word, 1) for word in ("go", "invoice", "a" * 20))


def test_the_hint_button_runs_out_and_the_cap_lives_on_the_server(
    client: TestClient, db_session: Session, auth: dict
) -> None:
    """Hai lần rồi thôi, và cái trần ấy đếm ở máy chủ.

    Đếm ở trình duyệt thì devtools đặt lại được trong hai giây, và xin đủ nhiều
    lần thì gợi ý in ra cả từ — lúc ấy phần thưởng ruby chỉ còn là một cái nút
    bấm nhiều lần.
    """
    headers = auth("learner")
    user = db_session.query(User).filter(User.role == "learner").one()
    words = _words(db_session, count=8)
    _pet(db_session, user)

    # Chốt id sao cho nó rơi vào dạng GÕ LẠI TỪ — dạng chọn nghĩa không có gợi ý.
    while True:
        rid = uuid.uuid4()
        if rid.int % 2 == 0:
            break
    row = Encounter(
        id=rid,
        user_id=user.id,
        kind="npc",
        task_kind="vocabulary",
        target_id=words[0].id,
        steps_total=1,
        reward_ruby=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(row)
    db_session.commit()

    first = client.post(f"/api/v1/pet/encounters/{row.id}/hint", headers=headers).json()
    assert first["hints_left"] == 1
    second = client.post(f"/api/v1/pet/encounters/{row.id}/hint", headers=headers).json()
    assert second["hints_left"] == 0
    assert len(second["hint"].replace("·", "")) > len(first["hint"].replace("·", ""))

    third = client.post(f"/api/v1/pet/encounters/{row.id}/hint", headers=headers)
    assert third.status_code == 409

    # Và giao diện biết trước là hết lượt, không mời bấm một nút chắc chắn lỗi.
    listed = client.get("/api/v1/pet/encounters", headers=headers).json()
    task = next(item for item in listed if item["id"] == str(row.id))["task"]
    assert task["hints_left"] == 0
