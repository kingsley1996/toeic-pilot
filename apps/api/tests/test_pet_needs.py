"""Nhu cầu con thú: phép trừ dần và ba hành động (ADR-010 §4.1).

Số học thuần, nên kiểm không cần database — cùng khuôn `test_services.py` với
SM-2 và bộ chấm dictation.
"""

from decimal import Decimal

import pytest

from app.services.pet import (
    EFFECTS,
    FEED_REFUSED_ABOVE,
    MAX_PET_LEVEL,
    ONE,
    PET_LEVEL_XP,
    SLEEP_MAX_SECONDS,
    XP_PER_ACTION,
    Needs,
    apply,
    decay,
    grant,
    level_from_xp,
    level_progress,
    refusal,
    xp_for_action,
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


def test_sleeping_recovers_energy_four_times_faster() -> None:
    """Ngủ là một ĐÁNH ĐỔI, không phải một dòng chảy thứ hai.

    Sức vốn tự hồi mà không cần ai làm gì; nếu ngủ chỉ nhanh hơn một chút thì nó
    không phải cơ chế, chỉ là một cái nút làm cùng việc đồng hồ đang làm.
    """
    tired = fresh(energy="0.10")
    awake = decay(tired, DAY / 8)  # ba tiếng thức
    slept = decay(tired, DAY / 8, asleep_seconds=DAY / 8)  # ba tiếng ngủ
    assert float(awake.energy) == pytest.approx(0.35, abs=0.01)
    assert float(slept.energy) == pytest.approx(1.0, abs=0.01)


def test_one_full_sleep_is_exactly_long_enough_to_refill() -> None:
    """Độ dài giấc ngủ và tốc độ hồi sức là MỘT cặp, không phải hai con số rời.

    Giấc tự dứt sau `SLEEP_MAX_SECONDS`, và nó phải kết thúc đúng lúc sức vừa
    đầy: dài hơn thì thừa một quãng nằm không, ngắn hơn thì tỉnh dậy khi còn dở
    và người dùng phải quay lại bấm tiếp — đúng thứ "ngủ tự hết" sinh ra để
    tránh. Đổi một con số mà quên con kia sẽ không có gì báo.
    """
    flat = fresh(energy="0.0")
    slept = decay(flat, SLEEP_MAX_SECONDS, asleep_seconds=SLEEP_MAX_SECONDS)
    assert float(slept.energy) == pytest.approx(1.0, abs=0.001)

    just_short = decay(flat, SLEEP_MAX_SECONDS * 0.9, asleep_seconds=SLEEP_MAX_SECONDS * 0.9)
    assert float(just_short.energy) < 1.0, "ngắn hơn một chút thì CHƯA đầy — không dư thừa"


def test_a_nap_that_ended_mid_window_only_counts_while_it_lasted() -> None:
    """Chỗ dễ sai nhất: giấc ngủ gần như luôn kết thúc GIỮA hai lần đọc.

    Người dùng cho ngủ rồi đóng tab, và lần mở sau đã qua cả giấc lẫn một quãng
    thức. Nhân cả quãng với tốc độ ngủ thì con thú hồi sức trong lúc nó đã dậy từ
    lâu — con số vẫn hợp lệ, chỉ là sai, và không có gì báo.

    Một tiếng rưỡi tính từ số không: thức cả quãng được 0,125; ngủ nửa đầu rồi
    thức nửa sau được 0,5 + 0,0625.

    **Quãng phải đủ NGẮN để cả hai vế còn dưới 1,0.** Kịch trần thì hai vế bằng
    nhau và phép so sánh không nói lên điều gì — bài kiểm này đã đỏ đúng vì thế
    một lần rồi, và đỏ lần nữa khi tốc độ ngủ tăng từ gấp bốn lên gấp tám. Đổi
    tốc độ thì phải rút quãng theo, chứ không phải sửa con số kỳ vọng.
    """
    flat = fresh(energy="0.0")
    all_awake = decay(flat, DAY / 16)
    half_slept = decay(flat, DAY / 16, asleep_seconds=DAY / 32)
    assert float(all_awake.energy) == pytest.approx(0.125, abs=0.01)
    assert float(half_slept.energy) == pytest.approx(0.5625, abs=0.01)

    # Quãng ngủ dài hơn cả quãng thời gian thì bị kẹp lại, không cộng khống.
    over = decay(flat, DAY / 32, asleep_seconds=DAY)
    assert float(over.energy) == pytest.approx(0.5, abs=0.01)


def test_sleeping_pauses_mood_but_never_hunger() -> None:
    """Vui không tụt trong lúc ngủ; đói thì vẫn xuống như thường.

    Nếu đói cũng dừng thì cho ngủ là cách né cơn đói, và người chơi sẽ tìm ra mẹo
    ấy rồi dùng mãi — lúc đó "cho ăn" thành cái nút không ai cần bấm.
    """
    start = fresh(fullness="0.90", mood="0.90", energy="0.10")
    asleep = decay(start, DAY / 4, asleep_seconds=DAY / 4)
    awake = decay(start, DAY / 4)
    assert float(asleep.mood) == pytest.approx(float(start.mood), abs=0.001)
    assert awake.mood < asleep.mood
    assert float(asleep.fullness) == pytest.approx(float(awake.fullness), abs=0.001)


def test_sleep_is_refused_when_the_pet_is_not_tired() -> None:
    # Nút bấm có phản hồi mà chỉ số đứng yên đọc ra là hỏng — và ngủ tốn HÀNG
    # GIỜ, nên đánh đổi ấy phải được từ chối sớm hơn hẳn so với cho ăn.
    assert refusal("sleep", fresh(energy="0.95")) is not None
    assert refusal("sleep", fresh(energy="0.20")) is None


def test_sleeping_pays_no_xp() -> None:
    """Không tốn gì, không đòi hỏi gì, nên không trả điểm.

    Trả điểm cho nó là mở lại đúng cái cửa mà trần ngày đóng: bấm một nút không
    mất gì cho tới khi kịch trần. Thứ giấc ngủ trả về là ĐI DẠO ĐƯỢC.
    """
    assert XP_PER_ACTION["sleep"] == 0 and XP_PER_ACTION["wake"] == 0
    assert XP_PER_ACTION["walk"] > 0


def test_walking_is_the_only_action_that_costs_something() -> None:
    # Ba cái nút mà cái nào cũng chỉ toàn cho thì không có gì để cân nhắc.
    assert EFFECTS["walk"].energy < 0 and EFFECTS["walk"].fullness < 0
    assert EFFECTS["feed"].fullness > 0
    assert EFFECTS["poke"].mood > 0


# --- XP và level của con thú ------------------------------------------------


def test_poking_gains_less_the_happier_the_pet_already_is() -> None:
    """Đây là cách chặn spam mà §6 tài liệu Tamagotchi gọi là trần sức chứa.

    Cộng một khoản cố định thì chín cú bấm là vui kịch nóc, và cái nút rẻ nhất
    trong ba nút thành đường nhanh nhất tới một con thú hoàn hảo. Cộng theo phần
    còn thiếu thì mỗi cú vẫn có tác dụng — không có lúc nào nút trông như hỏng —
    nhưng nó tiến tới 1 chứ không nhảy tới.
    """
    # Hai mốc đều CÁCH XA 1.0: chọn 0,9 thì phép kẹp một mình cũng làm phần cộng
    # nhỏ đi, và bài kiểm sẽ xanh cả khi luật này bị gỡ ra.
    low = Needs(fullness=ONE, energy=ONE, mood=Decimal("0.10"))
    mid = Needs(fullness=ONE, energy=ONE, mood=Decimal("0.50"))
    gain_low = apply("poke", low).mood - low.mood
    gain_mid = apply("poke", mid).mood - mid.mood
    assert gain_low > gain_mid > 0, "vẫn cộng, chỉ nhỏ dần"

    # Và nó không bao giờ CHẠM 1.0 — thứ mà một khoản cộng cố định sẽ làm ngay ở
    # cú bấm kế tiếp, rồi dừng lại đó.
    nearly = Needs(fullness=ONE, energy=ONE, mood=Decimal("0.95"))
    assert apply("poke", nearly).mood < ONE


def test_poking_a_pet_that_is_already_cheerful_earns_nothing() -> None:
    """Chọc gần như không có giá (-0,03 sức), nên nó không được là đường kiếm XP.

    Trước đây một điểm mỗi lượt nghĩa là ba mươi cú bấm ăn hết suất đầy của
    ngày; sau khi trần cứng thành đường cong giảm dần thì nó còn ĐỐT mất phần
    đầy suất đáng ra dành cho việc học. Mốc bằng đúng `CHEERFUL_ABOVE` của giao
    diện, nên lúc điểm dừng thì màn hình đã sẵn chữ "Đang vui" giải thích.
    """
    sad = Needs(fullness=ONE, energy=ONE, mood=Decimal("0.10"))
    cheerful = Needs(fullness=ONE, energy=ONE, mood=Decimal("0.80"))
    assert xp_for_action("poke", sad) == XP_PER_ACTION["poke"]
    assert xp_for_action("poke", cheerful) == 0
    assert xp_for_action("feed", cheerful) == XP_PER_ACTION["feed"], "chỉ chọc bị chặn"


def test_the_curve_trims_the_award_that_crosses_the_mark() -> None:
    """Còn hai điểm đủ suất mà hành động đáng năm thì được hai, rồi phần dư ăn 1/5.

    Bỏ hẳn phần dư sẽ khiến một hành động hợp lệ trông như không xảy ra.
    """
    assert grant(raw_today=0, award=5) == 5
    assert grant(raw_today=28, award=5) == 2, "2 điểm đủ suất, 3 điểm dư chưa đủ một phần năm"
    assert grant(raw_today=30, award=5) == 1, "qua mốc vẫn có điểm — đây là thứ trần cứng không có"


def test_five_small_awards_past_the_mark_add_up_to_exactly_one() -> None:
    """Đây là lý do đường cong đo trên tổng THÔ chứ không trên từng lượt.

    Chia tỉ lệ từng lượt thì `1 // 5 = 0` với mọi lượt một điểm, tức trần cứng
    quay lại nguyên vẹn chỉ khác chỗ đặt — và nó sẽ hỏng im lặng, vì mọi con số
    vẫn hợp lệ.
    """
    raw, total = 30, 0
    for _ in range(5):
        total += grant(raw_today=raw, award=1)
        raw += 1
    assert total == 1


def test_the_curve_never_hands_back_negative_xp() -> None:
    # Trả về số âm sẽ TRỪ XP, tức lấy lại thứ đã cho.
    assert grant(raw_today=50, award=0) == 0
    assert grant(raw_today=50, award=-5) == 0


def test_level_is_derived_from_xp_not_stored() -> None:
    assert level_from_xp(0) == 1
    assert level_from_xp(24) == 1
    assert level_from_xp(25) == 2
    assert level_from_xp(PET_LEVEL_XP[4]) == 5


def test_level_stops_at_the_top_of_the_table() -> None:
    """Kịch bảng thì `0 / 0`, không phải một thanh đầy 100%.

    Thanh đầy đọc ra là "sắp lên level" trong khi không còn level nào để lên.
    """
    top = level_progress(PET_LEVEL_XP[-1] + 10_000)
    assert top.level == MAX_PET_LEVEL
    assert (top.into_level, top.for_next) == (0, 0)


def test_the_curve_only_ever_climbs() -> None:
    # Một bảng ngưỡng đi lùi làm phép tra dừng ở sai level, và vì `level_reached`
    # chỉ tăng nên một mốc sai ghi trong khoảng đó là vĩnh viễn.
    assert list(PET_LEVEL_XP) == sorted(PET_LEVEL_XP)
    assert len(set(PET_LEVEL_XP)) == len(PET_LEVEL_XP)


def test_walking_is_worth_the_most_because_it_costs_the_most() -> None:
    assert XP_PER_ACTION["walk"] > XP_PER_ACTION["feed"] > XP_PER_ACTION["poke"]
