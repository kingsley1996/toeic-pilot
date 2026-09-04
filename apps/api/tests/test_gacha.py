"""Mở trứng: quay ở máy chủ, tỉ lệ khớp bảng, pity, trùng thì hoàn ruby (ADR-010 lát 8).

Phép quay nhận `rng` làm tham số, cùng lý do `srs.review` nhận `now`: một phép
quay không lặp lại được thì không bài kiểm nào nói được điều gì về tỉ lệ.
"""

import random
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EggSetting, PetOwned, PetSpecies, User
from app.models.pet import DEFAULT_PET_SPECIES, RARE_TIERS
from app.services import gacha, ruby
from app.services.pet_state import ensure_state


def _learner(db: Session, email: str = "gacha@example.com", ruby_amount: int = 0) -> User:
    user = User(email=email, hashed_password="x", role="learner")
    db.add(user)
    db.commit()
    if ruby_amount:
        ruby.earn(
            db,
            user_id=user.id,
            source_type="topic_mastered",
            source_id=uuid.uuid4(),
            amount=ruby_amount,
        )
        db.commit()
    return user


def _only(db: Session, *codes: str) -> None:
    """Thu bảng loài xuống đúng mấy mã này, để phép quay đoán trước được."""
    gacha.chances(db)  # gieo bộ mặc định
    for row in db.query(PetSpecies).all():
        row.enabled = row.code in codes
    db.commit()


def test_the_printed_odds_come_from_the_same_table_the_roll_uses(db_session: Session) -> None:
    """Tỉ lệ in ra màn hình phải khớp bảng cấu hình (ADR-010 §6.4).

    Hai phép tính là hai cơ hội để màn hình nói một đằng và máy làm một nẻo. Ghim
    ở đây: tổng luôn là 100, và tắt một loài chia lại phần của nó chứ không để
    bảng cộng ra 87.
    """
    _only(db_session, "duck", "tiger")  # 40 và 4
    rows = {row.code: row.percent for row in gacha.chances(db_session)}
    assert rows == pytest.approx({"duck": 40 / 44 * 100, "tiger": 4 / 44 * 100})
    assert sum(rows.values()) == pytest.approx(100)


def test_a_zero_weight_species_never_drops(db_session: Session) -> None:
    """Trọng số 0 khác `enabled = false`: loài vẫn hiện ở tủ, chỉ không rơi ra."""
    _only(db_session, "duck", "tiger")
    tiger = db_session.get(PetSpecies, "tiger")
    assert tiger is not None
    tiger.drop_weight = 0
    db_session.commit()
    assert [row.code for row in gacha.chances(db_session)] == ["duck"]


def already_has_a_pet(db: Session, user: User) -> None:
    """Cho tài khoản này một con thú sẵn, để lượt mở tới TÍNH TIỀN như bình thường.

    Quả trứng đầu tiên của mỗi tài khoản miễn phí, nên bài kiểm nào nói về GIÁ
    phải bước qua nó trước — nếu không nó đo con số 0 và tưởng đang đo giá.
    """
    db.add(PetOwned(user_id=user.id, species="starter"))
    db.commit()


def test_opening_an_egg_spends_ruby_and_writes_the_collection(db_session: Session) -> None:
    user = _learner(db_session, ruby_amount=30)
    _only(db_session, "duck")
    already_has_a_pet(db_session, user)
    state = ensure_state(db_session, user.id)

    result = gacha.open_egg(db_session, user_id=user.id, state=state, rng=random.Random(1))
    db_session.commit()

    assert result.species.code == "duck" and result.duplicate is False
    assert result.balance == 5 and ruby.balance(db_session, user.id) == 5
    owned = db_session.get(PetOwned, (user.id, "duck"))
    assert owned is not None and owned.copies == 1


def test_a_duplicate_refunds_ruby_instead_of_handing_out_nothing(db_session: Session) -> None:
    """Trùng thì hoàn một phần bằng chính ruby.

    Mở quả thứ mười và nhận đúng con đã có, không được gì cả, là trải nghiệm dạy
    người ta ngừng mở. Hoàn NHỎ HƠN giá trứng, nếu không thì mở trùng liên tục là
    một cỗ máy in ruby — ràng buộc đó nằm ở cả database lẫn màn quản trị.
    """
    user = _learner(db_session, ruby_amount=60)
    _only(db_session, "duck")
    already_has_a_pet(db_session, user)
    state = ensure_state(db_session, user.id)

    gacha.open_egg(db_session, user_id=user.id, state=state, rng=random.Random(1))
    second = gacha.open_egg(db_session, user_id=user.id, state=state, rng=random.Random(2))
    db_session.commit()

    assert second.duplicate is True and second.refund == 10
    # 60 − 25 − 25 + 10
    assert ruby.balance(db_session, user.id) == 20
    owned = db_session.get(PetOwned, (user.id, "duck"))
    assert owned is not None and owned.copies == 2


def test_the_pity_counter_forces_a_rare_and_then_resets(db_session: Session) -> None:
    """Ngẫu nhiên thuần cho ra những chuỗi xui mà người chơi đọc là "hỏng".

    Bộ đếm chỉ về 0 khi THẬT SỰ ra hạng hiếm, kể cả khi chính nó ép ra.
    """
    user = _learner(db_session, ruby_amount=25 * 12)
    _only(db_session, "duck", "tiger")
    duck = db_session.get(PetSpecies, "duck")
    assert duck is not None
    duck.drop_weight = 1000  # gần như chắc chắn ra vịt nếu không có pity
    db_session.commit()

    already_has_a_pet(db_session, user)

    state = ensure_state(db_session, user.id)
    config = gacha.settings_row(db_session)
    seen = []
    for _ in range(config.pity_rolls + 1):
        result = gacha.open_egg(db_session, user_id=user.id, state=state, rng=random.Random(7))
        seen.append(result)
    db_session.commit()

    assert all(r.species.tier not in RARE_TIERS for r in seen[:-1])
    last = seen[-1]
    assert last.species.tier in RARE_TIERS and last.forced_rare is True
    assert last.rolls_since_rare == 0


def test_opening_without_enough_ruby_is_refused_and_costs_nothing(db_session: Session) -> None:
    user = _learner(db_session, ruby_amount=5)
    _only(db_session, "duck")
    already_has_a_pet(db_session, user)
    state = ensure_state(db_session, user.id)

    with pytest.raises(ruby.NotEnoughRuby):
        gacha.open_egg(db_session, user_id=user.id, state=state, rng=random.Random(1))
    assert ruby.balance(db_session, user.id) == 5
    assert db_session.get(PetOwned, (user.id, "duck")) is None


def test_ten_eggs_are_one_transaction_in_the_ledger(db_session: Session) -> None:
    """Mở mười quả để lại MỘT dòng trừ và một dòng hoàn, không phải hai mươi dòng.

    Trừ tiền từng quả thì một lỗi ở quả thứ bảy để lại người dùng mất tiền của
    sáu quả đã mở mà không có gì nói vì sao — và đường tiêu này là đường có khoá,
    nên nửa chừng còn nghĩa là giữ khoá lâu gấp mười lần cần thiết.
    """
    user = _learner(db_session, ruby_amount=400)
    _only(db_session, "duck")  # chắc chắn trùng từ quả thứ hai
    already_has_a_pet(db_session, user)
    state = ensure_state(db_session, user.id)

    batch = gacha.open_eggs(
        db_session, user_id=user.id, state=state, count=10, rng=random.Random(3)
    )
    db_session.commit()

    assert len(batch.hatched) == 10
    assert batch.spent == 250
    # Chín quả trùng (quả đầu là con mới), hoàn 10 mỗi quả.
    assert sum(1 for one in batch.hatched if not one.duplicate) == 1
    assert batch.refund == 90
    assert ruby.balance(db_session, user.id) == 400 - 250 + 90

    rows = [(e.source_type, e.amount) for e in ruby.history(db_session, user.id)]
    assert rows.count(("egg", -250)) == 1
    assert rows.count(("egg_refund", 90)) == 1
    assert not any(amount == -25 for _, amount in rows), "không có dòng lẻ nào cho từng quả"

    owned = db_session.get(PetOwned, (user.id, "duck"))
    assert owned is not None and owned.copies == 10


def test_the_pity_counter_runs_through_a_batch(db_session: Session) -> None:
    """Bộ đếm an ủi chạy qua từng quả TRONG lượt, đúng như khi mở lẻ.

    Không có luật "mở 10 chắc chắn có hàng hiếm" riêng: đó sẽ là luật thứ hai làm
    đúng việc mà bộ đếm đang làm, với một con số khác — mà bộ đếm thì admin sửa
    được, nên hai con số sẽ lệch nhau vào ngày ai đó chỉnh một trong hai.
    """
    user = _learner(db_session, ruby_amount=25 * 12)
    _only(db_session, "duck", "tiger")
    duck = db_session.get(PetSpecies, "duck")
    assert duck is not None
    duck.drop_weight = 1000
    db_session.commit()

    already_has_a_pet(db_session, user)

    state = ensure_state(db_session, user.id)
    config = gacha.settings_row(db_session)
    state.rolls_since_rare = config.pity_rolls - 1  # quả thứ hai trong lượt sẽ bị ép
    db_session.commit()

    batch = gacha.open_eggs(
        db_session, user_id=user.id, state=state, count=10, rng=random.Random(5)
    )
    db_session.commit()

    forced = [i for i, one in enumerate(batch.hatched) if one.forced_rare]
    assert forced == [1], f"đúng quả thứ hai bị ép, nhận: {forced}"
    assert batch.hatched[1].species.tier in RARE_TIERS


def test_ten_eggs_are_refused_all_or_nothing(db_session: Session) -> None:
    """Thiếu tiền cho cả lượt thì KHÔNG mở quả nào, chứ không mở được mấy quả."""
    user = _learner(db_session, ruby_amount=100)  # đủ 4 quả, không đủ 10
    _only(db_session, "duck")
    already_has_a_pet(db_session, user)
    state = ensure_state(db_session, user.id)

    with pytest.raises(ruby.NotEnoughRuby):
        gacha.open_eggs(db_session, user_id=user.id, state=state, count=10)
    assert ruby.balance(db_session, user.id) == 100
    assert db_session.get(PetOwned, (user.id, "duck")) is None


def test_the_ten_endpoint_names_the_price_of_the_batch(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Lời từ chối nói con số của CẢ LƯỢT: người bấm "Mở 10" cần biết thiếu bao nhiêu."""
    headers = auth("learner")
    # Bước qua quả trứng miễn phí trước: bài này nói về LỜI TỪ CHỐI vì thiếu
    # tiền, mà quả đầu thì không đòi tiền.
    assert client.post("/api/v1/pet/eggs/open", headers=headers).status_code == 200
    refused = client.post("/api/v1/pet/eggs/open-ten", headers=headers)
    assert refused.status_code == 409
    assert "250" in refused.json()["detail"]


def test_the_endpoint_refuses_with_409_and_names_the_number(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Yêu cầu hợp lệ, trạng thái không cho phép — 409 chứ không 400.

    Lời từ chối nói ra CON SỐ để giao diện lặp lại được thay vì tự đoán, đúng
    khuôn lời từ chối của `POST /pet/actions`.
    """
    headers = auth("learner")
    # Bước qua quả trứng miễn phí trước: bài này nói về LỜI TỪ CHỐI vì thiếu
    # tiền, mà quả đầu thì không đòi tiền.
    assert client.post("/api/v1/pet/eggs/open", headers=headers).status_code == 200
    refused = client.post("/api/v1/pet/eggs/open", headers=headers)
    assert refused.status_code == 409
    assert "25" in refused.json()["detail"]


def test_the_egg_screen_reads_everything_in_one_call(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    headers = auth("learner")
    # Tài khoản mới CHƯA có con nào, nên quả đầu miễn phí — và màn hình phải nói
    # ra giá thật, không nói giá niêm yết.
    free = client.get("/api/v1/pet/eggs", headers=headers).json()
    assert free["ruby_cost"] == 0 and free["can_open"] is True, (
        "mở được dù ví rỗng: đó là cả điểm của việc tặng trứng thay vì tặng tiền"
    )
    assert client.post("/api/v1/pet/eggs/open", headers=headers).status_code == 200

    body = client.get("/api/v1/pet/eggs", headers=headers).json()
    assert body["ruby_cost"] == 25 and body["can_open"] is False
    # Đếm theo bảng loài chứ không theo một con số chép tay: bộ mặc định là thứ
    # còn dài ra nữa, và một bài kiểm ghim "12" sẽ đỏ vì nội dung chứ không vì
    # lỗi — đúng loại đỏ khiến người ta thôi tin bộ kiểm.
    assert len(body["chances"]) == len(DEFAULT_PET_SPECIES)
    assert sum(row["percent"] for row in body["chances"]) == pytest.approx(100, abs=0.5)
    # Trong tủ đúng một con: con vừa nở ra từ quả trứng miễn phí.
    assert len(body["owned"]) == 1


def test_only_an_admin_can_price_an_egg(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    assert client.get("/api/v1/admin/pet/eggs", headers=auth("editor")).status_code == 403
    assert client.get("/api/v1/admin/pet/eggs", headers=auth("admin")).status_code == 200


def test_a_refund_at_or_above_the_price_is_refused(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Hoàn ≥ giá trứng là một cỗ máy in ruby, và hai trường đổi được cùng lúc —
    nên phép so phải chạy trên giá trị SAU khi áp cả hai."""
    headers = auth("admin")
    bad = client.patch("/api/v1/admin/pet/eggs", json={"duplicate_refund": 25}, headers=headers)
    assert bad.status_code == 422 and "print" in bad.json()["detail"]

    good = client.patch(
        "/api/v1/admin/pet/eggs", json={"ruby_cost": 40, "duplicate_refund": 30}, headers=headers
    )
    assert good.status_code == 200 and good.json() == {
        "ruby_cost": 40,
        "pity_rolls": 10,
        "duplicate_refund": 30,
    }
    row = db_session.get(EggSetting, 1)
    assert row is not None and row.ruby_cost == 40
