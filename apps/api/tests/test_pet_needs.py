"""Nhu cầu con thú: phép trừ dần và ba hành động (ADR-010 §4.1).

Số học thuần, nên kiểm không cần database — cùng khuôn `test_services.py` với
SM-2 và bộ chấm dictation.
"""

from decimal import Decimal

import pytest

from app.services.pet import (
    EFFECTS,
    FEED_REFUSED_ABOVE,
    Needs,
    apply,
    decay,
    refusal,
)

DAY = 86_400.0


def fresh(fullness: str = "0.62", energy: str = "0.78", mood: str = "0.70") -> Needs:
    return Needs(fullness=Decimal(fullness), energy=Decimal(energy), mood=Decimal(mood))


def test_a_full_pet_takes_about_a_day_to_get_hungry() -> None:
    """Nhịp đo bằng NGÀY, không bằng phút.

    Bản cũ trừ theo `dt` của vòng animation, nên nhịp của nó (cạn trong ~10 phút
    MỞ BẢNG) hợp lý dưới giả định đó. Với đồng hồ thật, cùng con số ấy nghĩa là
    mở lại sau giờ nghỉ trưa đã thấy con thú kiệt sức — và một góc trang trí biến
    thành việc phải làm.
    """
    after = decay(fresh(fullness="1.0"), DAY)
    assert after.fullness == 0
    assert decay(fresh(fullness="1.0"), DAY / 2).fullness == pytest.approx(0.5, abs=0.01)


def test_a_hungry_pet_also_gets_sad() -> None:
    # Dưới ngưỡng đói thì vui tụt nhanh gấp đôi. Kiểm bằng cách SO SÁNH hai con
    # cùng mức vui, khác mức no — chứ không ghim một con số, vì con số ấy là thứ
    # sẽ được chỉnh.
    hungry = decay(fresh(fullness="0.10", mood="0.80"), DAY / 2)
    fed = decay(fresh(fullness="1.00", mood="0.80"), DAY / 2)
    assert hungry.mood < fed.mood


def test_energy_comes_back_on_its_own() -> None:
    assert decay(fresh(energy="0.10"), DAY).energy > Decimal("0.10")


def test_a_clock_that_runs_backwards_is_not_a_free_meal() -> None:
    """Đồng hồ máy chủ lùi là chuyện có thật — NTP chỉnh, đổi múi giờ.

    Cho phép quãng thời gian âm nghĩa là nhu cầu HỒI lại, tức một cách cho ăn
    miễn phí mà không ai nhìn thấy: chỉ số lên, không có bản ghi nào, không có
    lỗi nào.
    """
    before = fresh()
    assert decay(before, -DAY) == before


def test_nothing_ever_leaves_zero_to_one() -> None:
    starved = decay(fresh(fullness="0.01", mood="0.01"), DAY * 10)
    assert starved.fullness == 0 and starved.mood == 0
    stuffed = apply("feed", fresh(fullness="0.99"))
    assert stuffed.fullness == 1


def test_feeding_a_full_pet_is_refused_rather_than_doing_nothing() -> None:
    """Nút bấm có phản hồi mà chỉ số đứng yên thì đọc ra là hỏng.

    Nên hành động không có nghĩa lúc đó bị TỪ CHỐI kèm lý do, chứ không "thành
    công" một cách rỗng.
    """
    assert refusal("feed", fresh(fullness=str(FEED_REFUSED_ABOVE))) is not None
    assert refusal("feed", fresh(fullness="0.5")) is None


def test_walking_needs_energy() -> None:
    assert refusal("walk", fresh(energy="0.05")) is not None
    assert refusal("walk", fresh(energy="0.90")) is None


def test_walking_is_the_only_action_that_costs_something() -> None:
    # Ba cái nút mà cái nào cũng chỉ toàn cho thì không có gì để cân nhắc.
    assert EFFECTS["walk"].energy < 0 and EFFECTS["walk"].fullness < 0
    assert EFFECTS["feed"].fullness > 0
    assert EFFECTS["poke"].mood > 0
