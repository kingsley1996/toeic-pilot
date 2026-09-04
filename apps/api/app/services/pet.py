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

PetAction = Literal["feed", "poke", "walk", "sleep", "wake"]

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

"""Ngủ: hồi sức NHANH GẤP TÁM, và đây là cả cơ chế.

Sức vốn đã tự hồi (1 điểm mỗi 12 giờ) mà không cần ai làm gì. Nếu ngủ chỉ là một
dòng chảy thứ hai chạy song song thì nó không phải cơ chế, chỉ là một cái nút
làm cùng việc mà đồng hồ đang làm. Thứ nó thêm vào là một QUYẾT ĐỊNH: đánh đổi
vài giờ không chơi được với con thú để lấy lại sức đi dạo.

**Ngủ tự hết, không cần ai đánh thức.** Đây là ràng buộc quan trọng nhất, và nó
đến thẳng từ luật của cả góc thú cưng: một chỉ số cạn sau vài giờ biến nó thành
việc phải làm, và một con thú nằm chờ được đánh thức thì cũng đúng như thế. Giấc
ngủ dài tối đa `SLEEP_MAX_SECONDS` rồi tự dứt, và độ dài ấy đặt **bằng đúng thời
gian đầy sức từ số không** — nên giấc ngủ kết thúc đúng lúc nó xong việc, và
không có trạng thái nào đòi người dùng quay lại. Đổi một trong hai con số mà quên
con kia thì hoặc thừa một quãng nằm không, hoặc tỉnh dậy khi còn dở.

Trước đây là gấp bốn, tức một giấc ba tiếng. Với một ứng dụng người ta mở hai
mươi tới bốn mươi phút rồi đóng, ba tiếng nghĩa là con thú ngủ qua cả buổi học và
tỉnh lại vào lúc không ai còn ngồi đó. Gấp tám rút xuống chín mươi phút: vẫn là
một đánh đổi thật — vẫn phải bỏ vài chục phút không chơi được — nhưng nằm trong
tầm một buổi.

Trong lúc ngủ **vui không tụt**: nghỉ ngơi là chuyện dễ chịu. Nhưng **đói vẫn
xuống bình thường** — một con vật đang ngủ vẫn đói đi, và cho nó ngủ để né cơn
đói sẽ là một mẹo mà người chơi tìm ra rồi dùng mãi.
"""
SLEEP_ENERGY_RECOVER = ENERGY_RECOVER * Decimal(8)
SLEEP_MAX_SECONDS = 90 * 60

"""Đã gần đầy sức thì không ngủ được, cùng lý do đã no thì không ăn thêm.

Nút bấm có phản hồi mà chỉ số đứng yên đọc ra là hỏng. Ngưỡng cao hơn ngưỡng no
(0,95) một chút: ngủ tốn HÀNG GIỜ, nên đánh thức người dùng dậy chỉ để nhích 3%
là một đánh đổi tệ mà lời từ chối nên nói hộ họ.
"""
SLEEP_REFUSED_ABOVE = Decimal("0.9")

"""Đói thì vui cũng tụt: một con thú đói không thể "rất vui".

Ngưỡng là một BẬC chứ không phải một dải liên tục — dưới ngưỡng thì có phạt, trên
thì không. Một hàm trơn nghe hợp lý hơn nhưng không ai đọc ra được nó từ hai cái
thanh chỉ số, còn một bậc thì giải thích được bằng một câu.
"""
HUNGRY_BELOW = Decimal("0.25")
HUNGRY_MOOD_PENALTY = ONE / _PER_DAY

"""Chọc lúc đói thì vui lên ít hơn — xem `apply`."""
HUNGRY_POKE_FACTOR = Decimal("0.35")

"""Đói thì sức TỤT, đúng bằng tốc độ nó vốn hồi lúc thức — xem `_energy_after`."""
HUNGRY_ENERGY_DRAIN = ENERGY_RECOVER

"""Dưới mức này thì con thú buồn, và nghỉ chỉ lại nửa sức.

Đối xứng với `CHEERFUL_ABOVE` (0,75) của giao diện và bằng đúng `HUNGRY_BELOW`,
nên ba cái bậc của hệ này nằm ở hai con số chứ không phải ba. Giao diện gọi mức
này là "Đang buồn" — một hình phạt không có nhãn thì người dùng chỉ thấy sức đứng
yên mà không biết vì sao.
"""
SAD_BELOW = Decimal("0.25")
SAD_ENERGY_FACTOR = Decimal("0.5")


def decay(needs: Needs, seconds: float, asleep_seconds: float = 0) -> Needs:
    """Nhu cầu sau `seconds` giây không ai đụng tới, trong đó `asleep_seconds` là ngủ.

    Thời gian âm trả về nguyên trạng: đồng hồ máy chủ lùi (NTP chỉnh, đổi múi
    giờ) là chuyện có thật, và cho phép nó chạy ngược sẽ HỒI nhu cầu — tức một
    cách cho ăn miễn phí mà không ai nhìn thấy.

    **Khoảng thời gian chia làm hai đoạn, không phải một hệ số nhân.** Giấc ngủ
    gần như luôn kết thúc GIỮA hai lần đọc: người dùng cho ngủ rồi đóng tab, và
    lần mở sau đã qua cả giấc lẫn một quãng thức. Nhân cả quãng với tốc độ ngủ
    thì con thú hồi sức trong lúc nó đã dậy từ lâu — con số vẫn hợp lệ, chỉ là
    sai, và không có gì báo.

    Đoạn ngủ: sức hồi gấp bốn, **vui không tụt**, đói vẫn xuống như thường.
    """
    if seconds <= 0:
        return needs
    asleep = Decimal(str(max(0.0, min(asleep_seconds, seconds))))
    awake = Decimal(str(seconds)) - asleep
    elapsed = asleep + awake

    fullness = _clamp(needs.fullness - FULLNESS_DECAY * elapsed)
    # Vui chỉ tụt trong lúc THỨC. Đói thì phạt cả hai đoạn: bụng rỗng làm con thú
    # ngủ không ngon, và nó tỉnh dậy đúng như thế.
    mood = needs.mood - MOOD_DECAY * awake
    if fullness < HUNGRY_BELOW:
        mood -= HUNGRY_MOOD_PENALTY * elapsed
    mood = _clamp(mood)

    energy = _clamp(_energy_after(needs.energy, fullness, mood, awake, asleep))
    return Needs(fullness=fullness, mood=mood, energy=energy)


def _energy_after(
    energy: Decimal, fullness: Decimal, mood: Decimal, awake: Decimal, asleep: Decimal
) -> Decimal:
    """Sức sau một quãng, và đây là chỗ ba chỉ số ăn vào nhau.

    Trước đó sức chỉ đi LÊN và đi lên bất kể no với vui đang ở đâu, nên trạng
    thái "đói 0%, vui 0%, sức 100%" là chuyện thường gặp chứ không phải hiếm: bỏ
    con thú một tuần thì no và vui rơi về 0 còn sức leo lên kịch trần và nằm đó.
    Ba cái thanh khi ấy không mô tả một sinh vật nào cả.

    **Đói thì sức TỤT, không phải chỉ ngừng hồi.** Ngừng hồi không sửa được đúng
    cái cảnh trên — một con thú đã đầy sức trước khi bị bỏ quên vẫn đứng nguyên ở
    100%. Tốc độ tụt đặt bằng đúng tốc độ nó vốn hồi lúc thức, nên một câu là đủ
    tả: bụng rỗng thì cái đồng hồ chạy ngược.

    **Buồn thì nghỉ chỉ lại nửa sức.** Nhẹ hơn đói vì đói là gốc — nó kéo cả vui
    xuống theo (`HUNGRY_MOOD_PENALTY`) — còn buồn là ngọn. Phạt hai lần bằng nhau
    thì một con thú bị bỏ quên rơi thẳng xuống đáy cả ba chỉ số cùng lúc, và lúc
    đó ba cái thanh lại thôi nói ba điều khác nhau.

    Cả hai là BẬC chứ không phải dải liên tục, cùng lý do đã ghi ở `HUNGRY_BELOW`:
    một hàm trơn nghe hợp lý hơn nhưng không ai đọc ra được nó từ mấy cái thanh,
    còn một bậc thì giải thích được bằng một câu — và cả hai bậc đều có nhãn trên
    màn hình ("Đang đói", "Đang buồn") nên người dùng thấy được vì sao sức không
    lên.

    Luôn có lối ra: cho ăn không bao giờ bị từ chối vì đói, nên một con thú kiệt
    quệ vẫn cứu được bằng đúng hành động rẻ nhất.
    """
    if fullness < HUNGRY_BELOW:
        return energy - HUNGRY_ENERGY_DRAIN * (awake + asleep)
    gain = ENERGY_RECOVER * awake + SLEEP_ENERGY_RECOVER * asleep
    return energy + (gain * SAD_ENERGY_FACTOR if mood < SAD_BELOW else gain)


"""Tác động của từng hành động. Số dương là cho, số âm là lấy đi.

`walk` tốn sức và tốn cả no — nó là hành động duy nhất có giá thật, và đó là chủ
ý: ba cái nút mà cái nào cũng chỉ toàn cho thì không có gì để cân nhắc.
"""
EFFECTS: dict[PetAction, Needs] = {
    "feed": Needs(fullness=Decimal("0.35"), energy=ZERO, mood=Decimal("0.05")),
    "poke": Needs(fullness=ZERO, energy=Decimal("-0.03"), mood=Decimal("0.12")),
    "walk": Needs(fullness=Decimal("-0.05"), energy=Decimal("-0.20"), mood=Decimal("0.15")),
    # Ngủ và dậy KHÔNG đổi chỉ số ngay lúc bấm: cái chúng đổi là TỐC ĐỘ của
    # quãng thời gian sau đó. Một cú cộng tức thì ở đây sẽ là phần thưởng cho
    # việc bấm nút, và lúc đó bấm ngủ-dậy-ngủ-dậy liên tục là đường hồi sức
    # nhanh nhất — đúng thứ mà cả cơ chế này dựng ra để không có.
    "sleep": Needs(fullness=ZERO, energy=ZERO, mood=ZERO),
    "wake": Needs(fullness=ZERO, energy=ZERO, mood=ZERO),
}

"""Ngưỡng từ chối, cho những hành động không có nghĩa lúc đó.

Cho ăn một con đã no căng thì không nên vừa "thành công" vừa không đổi gì: nút
bấm có phản hồi mà chỉ số đứng yên đọc ra là hỏng. Đi dạo lúc kiệt sức cũng vậy.

`WALK_HUNGRY_BELOW` là thứ biến ba cái nút thành một CƠ CHẾ.

Trước đó ba hành động độc lập hoàn toàn với nhau: mỗi cái cộng vào một chỉ số
riêng, không cái nào cần cái nào, nên thứ tự bấm không bao giờ quan trọng — và
một hệ mà thứ tự không quan trọng thì không có gì để cân nhắc, chỉ có ba cái nút
để bấm cho hết. Ràng buộc này dựng một thứ tự có thật và giải thích được bằng
một câu: **cho ăn trước, rồi mới dắt đi**. Nó cũng đúng với đời sống, nên không
ai phải học luật.

Ngưỡng đói (0,2) đặt CAO HƠN ngưỡng kiệt sức (0,15) có chủ ý: đói tới trước mệt
trong đa số trường hợp, nên lời nhắc mà người dùng gặp thường xuyên hơn là lời
nhắc dẫn tới hành động rẻ nhất và vui nhất — cho ăn.
"""
FEED_REFUSED_ABOVE = Decimal("0.95")
WALK_REFUSED_BELOW = Decimal("0.15")
WALK_HUNGRY_BELOW = Decimal("0.2")


def refusal(action: PetAction, needs: Needs) -> str | None:
    """Lý do KHÔNG làm được, bằng tiếng Việt, hoặc `None` nếu làm được."""
    if action == "feed" and needs.fullness >= FEED_REFUSED_ABOVE:
        return "Nó đang no, chưa ăn thêm được."
    if action in ("walk", "poke") and needs.energy < WALK_REFUSED_BELOW:
        # Chọc cũng TỐN sức (-0,03), chỉ ít hơn đi dạo. Cho cái này qua mà chặn
        # cái kia là võ đoán từ phía người chơi, và tệ hơn thế: lúc kiệt sức thì
        # chọc là cái nút duy nhất còn sáng, mà nó lại kéo dài đúng tình trạng
        # ấy — từ 0,14 thì năm cú bấm về 0, và hồi lại tới ngưỡng mất gần hai
        # tiếng thức.
        #
        # Chặn chứ không giảm thưởng như `HUNGRY_POKE_FACTOR`: ở kia vấn đề là
        # phần thưởng quá hời, ở đây là CÁI GIÁ — con thú không có sức để mất.
        # Luật này khép kín thứ tự mà `WALK_HUNGRY_BELOW` mở ra: cho ăn trước rồi
        # mới dắt đi, và kiệt sức thì cho ngủ.
        return "Nó đang mệt, để nó nghỉ đã."
    if action == "walk" and needs.fullness < WALK_HUNGRY_BELOW:
        return "Nó đang đói, cho ăn trước đã."
    if action == "sleep" and needs.energy >= SLEEP_REFUSED_ABOVE:
        return "Nó chưa buồn ngủ."
    return None


"""Cả ba chỉ số cùng dưới ngưỡng: con thú ỐM.

Không đặt ngưỡng mới. Ốm là "cả ba cái ngưỡng đã có cùng bị phá", nên nó không
thêm một con số nào để chỉnh lệch khỏi ba con số kia — và nó tự đúng khi ai đó
chỉnh một trong ba.

**Không phải một cái chết, và cũng không khoá gì cả.** §12 của tài liệu cơ chế
gốc từ chối kiểu "ba ngày không học thì thú chết" và thay bằng vòng: bỏ bê → thú
buồn → chỉ số tụt → **thú xin được chú ý** → hồi phục. Nên ốm không chặn cho ăn,
không chặn ngủ; nó chỉ gọi một vị khách tới ngay thay vì đợi hết đồng hồ hai mươi
phút, và làm xong việc của khách thì con thú được vực dậy.

Vực dậy chứ không chữa lành: `REVIVE_TO` nhấc cả ba lên vừa qua ngưỡng, đủ để
đường chăm sóc bình thường chạy lại được, chứ không phải một con thú đầy ắp từ
một câu trả lời. Nó cũng không thể farm: chỉ nhận được khi đang ốm, mà muốn ốm
thì phải bỏ bê cả ngày, và thứ nhận được là nhu cầu chứ không phải tiền.
"""
REVIVE_TO = Decimal("0.35")


def is_sick(needs: Needs) -> bool:
    return (
        needs.fullness < HUNGRY_BELOW
        and needs.mood < SAD_BELOW
        and needs.energy < WALK_REFUSED_BELOW
    )


def revive(needs: Needs) -> Needs:
    """Nhấc mọi chỉ số đang dưới `REVIVE_TO` lên đúng mức ấy, không đụng cái nào đã cao hơn."""
    return Needs(
        fullness=max(needs.fullness, REVIVE_TO),
        energy=max(needs.energy, REVIVE_TO),
        mood=max(needs.mood, REVIVE_TO),
    )


def apply(action: PetAction, needs: Needs) -> Needs:
    """Nhu cầu sau khi làm `action`. Gọi SAU `decay`, không phải trước.

    Ngược thứ tự thì phần thưởng bị trừ dần theo quãng thời gian trước khi hành
    động xảy ra — cho ăn sau một tuần vắng mặt sẽ gần như không có tác dụng, và
    con số vẫn hợp lệ nên không có gì báo.
    """
    effect = EFFECTS[action]
    if action == "poke":
        # Chọc cộng theo PHẦN CÒN THIẾU, không cộng một khoản cố định.
        #
        # Cố định thì chín cú bấm là vui kịch nóc, và cái nút rẻ nhất trong ba
        # nút lại là đường nhanh nhất tới một con thú hoàn hảo — §6 của
        # `toeic_pilot_tamagotchi_mechanics.md` gọi đúng đó là spam action. Tài
        # liệu đưa hai cách chặn: đồng hồ hồi chiêu, hoặc trần sức chứa làm phần
        # dư bỏ phí. Đây là cách thứ hai, ở dạng liên tục — mỗi cú bấm vẫn có tác
        # dụng, chỉ nhỏ dần, nên không có lúc nào nút "hỏng" mà cũng không có
        # đường tắt.
        #
        # Đồng hồ hồi chiêu bị loại có lý do: nó sẽ phá chính thứ tự "cho ăn
        # trước, rồi mới dắt đi" mà `WALK_HUNGRY_BELOW` dựng lên, và bảo một
        # người mỗi ngày mở ứng dụng một lần rằng hãy quay lại sau ba mươi phút
        # là phạt đúng nhịp dùng bình thường (ADR-010 §11).
        effect = Needs(
            fullness=effect.fullness,
            energy=effect.energy,
            mood=effect.mood * (ONE - needs.mood),
        )
    if action == "poke" and needs.fullness < HUNGRY_BELOW:
        # Chọc một con đang đói thì nó không vui lên mấy — cùng một bậc mà
        # `decay` đã dùng để trừ vui khi đói, nên hai chỗ nói cùng một điều về
        # cùng một ngưỡng thay vì mỗi chỗ một con số.
        #
        # Giảm phần thưởng chứ KHÔNG từ chối và KHÔNG trừ vui: góc thú cưng
        # không phạt người dùng (ADR-010 §11). Ở đây nó chỉ nói rằng có một việc
        # đáng làm hơn đang chờ.
        effect = Needs(
            fullness=effect.fullness,
            energy=effect.energy,
            mood=effect.mood * HUNGRY_POKE_FACTOR,
        )
    return Needs(
        fullness=_clamp(needs.fullness + effect.fullness),
        energy=_clamp(needs.energy + effect.energy),
        mood=_clamp(needs.mood + effect.mood),
    )


# --- XP và level của CON THÚ, tách hẳn khỏi level người học ------------------

"""XP mỗi hành động.

`walk` được nhiều nhất vì nó là hành động duy nhất có giá — nó tốn sức và tốn
no. Ba cái nút mà cái nào cũng cùng một phần thưởng thì không có gì để chọn.
"""
XP_PER_ACTION: dict[PetAction, int] = {"feed": 3, "poke": 1, "walk": 5, "sleep": 0, "wake": 0}

"""Trên mức này thì chọc thôi sinh điểm.

Bằng đúng `CHEERFUL_ABOVE` của `petland-pet.ts`, và cố ý: đó là mốc mà giao diện
đã gọi con thú là "Đang vui", nên lúc điểm dừng lại thì trên màn hình đã có sẵn
một câu giải thích vì sao. Đổi một trong hai mà quên chỗ kia thì không có gì báo
— hai con số vẫn hợp lệ, chỉ là không còn nói cùng một điều.

Vì sao cần: chọc là hành động duy nhất gần như không có giá (`-0,03` sức), nên
một điểm mỗi lượt biến nó thành đường kiếm XP rẻ nhất — bấm ba mươi lần là hết
suất đầy của ngày mà không học một chữ nào. Sau khi trần cứng thành đường cong
giảm dần, chuyện đó còn tệ hơn: nó ĐỐT mất phần đầy suất đáng ra dành cho việc
học. Chặn ở đây, chứ không chặn bằng đồng hồ, vì nó nói một điều có nghĩa — một
con thú đang vui sẵn thì chọc thêm không dạy nó được gì.

Không phạt: cú bấm vẫn cộng vui (nhỏ dần), chỉ là thôi cộng điểm.
"""
POKE_XP_MOOD_CEILING = Decimal("0.75")


def xp_for_action(action: PetAction, before: Needs) -> int:
    """XP của một lượt chăm, đọc trên nhu cầu TRƯỚC khi hành động chạy."""
    if action == "poke" and before.mood >= POKE_XP_MOOD_CEILING:
        return 0
    return XP_PER_ACTION[action]


"""Ngủ và dậy KHÔNG cho XP, có chủ ý.

Chúng không tốn gì và không đòi hỏi gì, nên trả điểm cho chúng là mở lại đúng
cái cửa mà trần ngày đóng lại: bấm một nút không mất gì cho tới khi kịch trần.
Thứ giấc ngủ trả về là ĐI DẠO ĐƯỢC — mà đi dạo mới là hành động đáng 5 điểm.
"""

"""XP con thú nhận được khi một cuộc chạm mặt kết thúc thắng lợi.

Cùng tỉ lệ với ruby (5 và 20), vì hai phần thưởng đo cùng một việc: đẩy lui một
kẻ xâm nhập là ba câu đúng liên tiếp, còn giúp một NPC là một câu.

Cao hơn hẳn `walk` (5 điểm) có chủ ý — đây là XP duy nhất phải HỌC mới có. Mấy
cái nút chăm sóc trả điểm cho sự chăm chỉ; cái này trả cho việc trả lời đúng.
Để nó ngang một cú bấm là nói rằng hai thứ ấy đáng như nhau.
"""
XP_PER_ENCOUNTER: dict[str, int] = {"npc": 6, "intruder": 15, "rescue": 0}
"""Hồi phục trao 0 XP, cùng lý do nó trao 0 ruby: phần thưởng của nó là con thú
đứng dậy được. Có mặt trong bảng chứ không để `KeyError` lo — thiếu khoá ở đây
là một 500 trên đúng đường mà người dùng đang cố cứu con thú."""


"""Việc HỌC cũng nuôi con thú — đây là chỗ vòng lặp khép lại.

Trước đây con thú chỉ lớn lên nhờ bấm nút chăm sóc và đánh chạm mặt, nên nó là
một trò chơi nhỏ nằm CẠNH app học chứ không phải một lớp nằm TRÊN nó: học xong
một buổi từ vựng không làm con thú vui hơn chút nào. Ba con số dưới đây là sợi
dây nối, và chúng cố ý nhỏ.

**Chỉ nâng TINH THẦN, không nâng no.** Cho ăn là cho ăn; nếu học cũng làm no thì
cái nút "Cho ăn" thành thừa và ba cái thanh thôi nói được điều gì khác nhau. Một
người học đều sẽ có con thú luôn vui — đó chính là điều mong muốn, không phải
tác dụng phụ.

**XP đi qua đúng trần ngày** của `DAILY_XP_CAP`. Nhờ vậy một buổi cày trăm từ
không thổi con thú lên mấy level trong mười phút.
"""
XP_PER_STUDY: dict[str, int] = {"vocabulary_review": 1, "dictation_item": 1, "attempt": 8}
MOOD_PER_STUDY: dict[str, Decimal] = {
    "vocabulary_review": Decimal("0.04"),
    "dictation_item": Decimal("0.04"),
    "attempt": Decimal("0.20"),
}


def cheer(needs: Needs, amount: Decimal) -> Needs:
    """Nâng tinh thần, giữ nguyên no và sức."""
    return Needs(fullness=needs.fullness, energy=needs.energy, mood=_clamp(needs.mood + amount))


"""XP mỗi ngày GIẢM DẦN, không chặn cứng.

Bản trước chặn cứng ở 30: qua mốc đó thì chăm tiếp không sinh thêm điểm nào. Nó
giữ cho level pet còn nghĩa, nhưng nói sai một điều — người học lấy con thú làm
động lực sẽ dừng đúng lúc chạm trần, tức một luật trò chơi đang bảo người ta thôi
học (`Evaluate_Pet_TOEIC_Pilot.md` §2.2.1).

Nên giờ 30 điểm đầu ăn đủ suất, phần sau ăn một phần năm. Chăm thêm luôn còn
đáng, chỉ là không còn là đường nhanh nhất — đúng thứ trần cứng định làm mà không
kèm câu "thôi đi".

**Tính trên tổng THÔ của ngày, không phải trên từng lượt.** Chia tỉ lệ từng lượt
thì một lượt đáng 1 điểm sau mốc sẽ thành `1 // 5 = 0`, tức lại là trần cứng, chỉ
khác chỗ đặt. Đo trên tổng dồn thì năm lượt một điểm cộng lại đúng một điểm, và
hàm vẫn đơn điệu — mỗi lượt trao đúng phần chênh mà nó tạo ra.
"""
DAILY_XP_FULL = 30
REDUCED_DIVISOR = 5


def granted_from_raw(raw_today: int) -> int:
    """Tổng XP thật sự được trao, từ tổng THÔ đã kiếm trong ngày."""
    return min(raw_today, DAILY_XP_FULL) + max(0, raw_today - DAILY_XP_FULL) // REDUCED_DIVISOR


def grant(raw_today: int, award: int) -> int:
    """Phần XP trao cho lượt này. Không bao giờ âm."""
    if award <= 0:
        return 0
    return granted_from_raw(raw_today + award) - granted_from_raw(raw_today)


"""Ngưỡng XP CỘNG DỒN của từng level, chỉ số 0 là level 1.

Dãy tam giác: level n cần `25 * (n-1) * n / 2`. Nó dốc dần lên, nên vài level
đầu tới nhanh — đúng lúc người dùng còn đang thử xem cái góc này có gì — rồi
chậm lại.

Bảng cứng trong mã, KHÔNG phải bảng trong database. Level người học có
`level_tier` cho admin sửa vì nó gắn với khung avatar, huy hiệu và nhiệm vụ
ngày; level pet hiện chỉ nuôi đúng một con số hiển thị. Ngày nó mua được thứ gì
thật thì đánh đổi này hết hạn và bảng phải chuyển xuống database — ghi ở đây để
lúc đó không ai phải đoán lại lý do.
"""
PET_LEVEL_XP: tuple[int, ...] = tuple(25 * (n - 1) * n // 2 for n in range(1, 21))

MAX_PET_LEVEL = len(PET_LEVEL_XP)


def level_from_xp(xp: int) -> int:
    """Level ứng với tổng XP. Kịch bảng thì dừng ở level cuối.

    Suy ra chứ không lưu: một cột `level` bên cạnh `xp` là hai nguồn sự thật cho
    một con số, và cái sai sẽ là cái không ai đọc.
    """
    level = 1
    for index, needed in enumerate(PET_LEVEL_XP, start=1):
        if xp >= needed:
            level = index
    return level


@dataclass(frozen=True)
class LevelProgress:
    level: int
    """XP đã có TRONG level hiện tại, và XP cần để sang level sau.

    `0 / 0` khi đã kịch bảng: một thanh đầy 100% ở đó đọc ra là "sắp lên level"
    trong khi không còn level nào để lên. Cùng cách `ProgressionPublic` xử lý.
    """
    into_level: int
    for_next: int


def level_progress(xp: int) -> LevelProgress:
    level = level_from_xp(xp)
    if level >= MAX_PET_LEVEL:
        return LevelProgress(level=level, into_level=0, for_next=0)
    base = PET_LEVEL_XP[level - 1]
    nxt = PET_LEVEL_XP[level]
    return LevelProgress(level=level, into_level=xp - base, for_next=nxt - base)
