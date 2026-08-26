"""Nhu cầu con thú: trừ dần theo thời gian, và ba hành động tác động lên nó.

**Số học thuần, không session, không HTTP** — cùng khuôn `srs.py` và
`dictation.py`, và vì cùng một lý do: đây là chỗ dễ sai nhất và cũng là chỗ rẻ
nhất để kiểm, miễn là nó không cần database để chạy.

`Decimal` chứ không `float`, theo đúng `ease_factor` của SM-2: ba con số này
được lưu `Numeric(4,3)` và đọc ra là `Decimal`, nên tính bằng float sẽ phải đổi
kiểu ở mọi biên và mỗi lần đổi là một chỗ làm tròn.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

PetAction = Literal["feed", "poke", "walk"]

ONE = Decimal(1)
ZERO = Decimal(0)


@dataclass(frozen=True)
class Needs:
    fullness: Decimal
    energy: Decimal
    mood: Decimal


"""Độ chính xác THẬT của ba con số này, lấy từ chính cột `Numeric(4, 3)`.

Không làm tròn thì `1 / 86400` kéo theo 28 chữ số qua mọi phép tính, và sau đúng
một ngày con thú còn `4E-28` phần no thay vì 0 — một con số vừa vô nghĩa vừa
khiến "đã cạn" không bao giờ so bằng được. Tệ hơn, giá trị trong bộ nhớ khác giá
trị vừa ghi xuống database, nên cùng một con thú cho hai đáp số tuỳ theo nó vừa
đi qua đường nào.
"""
PRECISION = Decimal("0.001")


def _clamp(value: Decimal) -> Decimal:
    return max(ZERO, min(ONE, value)).quantize(PRECISION)


"""Tốc độ đổi, tính theo ĐƠN VỊ MỖI GIÂY, đo bằng đồng hồ THẬT.

Bản Petland cũ trừ theo `dt` của vòng `requestAnimationFrame`, nên đồng hồ chỉ
chạy khi bảng đang mở — và nhịp của nó (đói hết trong ~10 phút mở bảng) hợp lý
dưới giả định đó. Chuyển sang đồng hồ thật thì cùng con số ấy nghĩa là mở lại
sau giờ nghỉ trưa đã thấy con thú kiệt sức.

Nhịp mới đo bằng NGÀY, và cố ý chậm: đây là góc thú cưng của một ứng dụng học,
không phải một game nuôi thú. Một chỉ số cạn sau vài giờ biến nó thành việc phải
làm, và việc phải làm thứ hai bên cạnh việc học là thứ khiến người ta đóng hẳn
bảng này lại.
"""
_PER_DAY = Decimal(86_400)
FULLNESS_DECAY = ONE / _PER_DAY  # đầy → cạn: 1 ngày
MOOD_DECAY = ONE / (_PER_DAY * Decimal("1.5"))  # 1,5 ngày
ENERGY_RECOVER = ONE / (_PER_DAY / Decimal(2))  # cạn → đầy: 12 giờ

"""Đói thì vui cũng tụt: một con thú đói không thể "rất vui".

Ngưỡng là một BẬC chứ không phải một dải liên tục — dưới ngưỡng thì có phạt, trên
thì không. Một hàm trơn nghe hợp lý hơn nhưng không ai đọc ra được nó từ hai cái
thanh chỉ số, còn một bậc thì giải thích được bằng một câu.
"""
HUNGRY_BELOW = Decimal("0.25")
HUNGRY_MOOD_PENALTY = ONE / _PER_DAY


def decay(needs: Needs, seconds: float) -> Needs:
    """Nhu cầu sau `seconds` giây không ai đụng tới.

    Thời gian âm trả về nguyên trạng: đồng hồ máy chủ lùi (NTP chỉnh, đổi múi
    giờ) là chuyện có thật, và cho phép nó chạy ngược sẽ HỒI nhu cầu — tức một
    cách cho ăn miễn phí mà không ai nhìn thấy.
    """
    if seconds <= 0:
        return needs
    elapsed = Decimal(str(seconds))
    fullness = _clamp(needs.fullness - FULLNESS_DECAY * elapsed)
    mood = needs.mood - MOOD_DECAY * elapsed
    if fullness < HUNGRY_BELOW:
        mood -= HUNGRY_MOOD_PENALTY * elapsed
    return Needs(
        fullness=fullness,
        energy=_clamp(needs.energy + ENERGY_RECOVER * elapsed),
        mood=_clamp(mood),
    )


"""Tác động của từng hành động. Số dương là cho, số âm là lấy đi.

`walk` tốn sức và tốn cả no — nó là hành động duy nhất có giá thật, và đó là chủ
ý: ba cái nút mà cái nào cũng chỉ toàn cho thì không có gì để cân nhắc.
"""
EFFECTS: dict[PetAction, Needs] = {
    "feed": Needs(fullness=Decimal("0.35"), energy=ZERO, mood=Decimal("0.05")),
    "poke": Needs(fullness=ZERO, energy=Decimal("-0.03"), mood=Decimal("0.12")),
    "walk": Needs(fullness=Decimal("-0.05"), energy=Decimal("-0.20"), mood=Decimal("0.15")),
}

"""Ngưỡng từ chối, cho những hành động không có nghĩa lúc đó.

Cho ăn một con đã no căng thì không nên vừa "thành công" vừa không đổi gì: nút
bấm có phản hồi mà chỉ số đứng yên đọc ra là hỏng. Đi dạo lúc kiệt sức cũng vậy.
"""
FEED_REFUSED_ABOVE = Decimal("0.95")
WALK_REFUSED_BELOW = Decimal("0.15")


def refusal(action: PetAction, needs: Needs) -> str | None:
    """Lý do KHÔNG làm được, bằng tiếng Việt, hoặc `None` nếu làm được."""
    if action == "feed" and needs.fullness >= FEED_REFUSED_ABOVE:
        return "Nó đang no, chưa ăn thêm được."
    if action == "walk" and needs.energy < WALK_REFUSED_BELOW:
        return "Nó đang mệt, để nó nghỉ đã."
    return None


def apply(action: PetAction, needs: Needs) -> Needs:
    """Nhu cầu sau khi làm `action`. Gọi SAU `decay`, không phải trước.

    Ngược thứ tự thì phần thưởng bị trừ dần theo quãng thời gian trước khi hành
    động xảy ra — cho ăn sau một tuần vắng mặt sẽ gần như không có tác dụng, và
    con số vẫn hợp lệ nên không có gì báo.
    """
    effect = EFFECTS[action]
    return Needs(
        fullness=_clamp(needs.fullness + effect.fullness),
        energy=_clamp(needs.energy + effect.energy),
        mood=_clamp(needs.mood + effect.mood),
    )
