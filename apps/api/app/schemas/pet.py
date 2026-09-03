"""Hình dạng trạng thái con thú gửi cho trình duyệt (ADR-010 §4)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PetNeeds(BaseModel):
    """Ba nhu cầu, 0..1.

    Gửi kèm `at` — mốc thời gian của ba số này — chứ không gửi số trần. Trình
    duyệt nội suy tiếp từ mốc đó để thanh chỉ số nhích mượt, nhưng con số của
    máy chủ vẫn là con số thật. Thiếu mốc thì client không có cách nào biết ba
    số kia cũ bao lâu, và nó sẽ vẽ một con thú no nê ngay sau một tuần vắng mặt.
    """

    fullness: float = Field(ge=0, le=1)
    energy: float = Field(ge=0, le=1)
    mood: float = Field(ge=0, le=1)
    at: datetime


class PetPublic(BaseModel):
    species: str
    label: str
    """Tên loài để hiển thị, tra từ `pet_species` ngay ở đây.

    Cùng lý do với `tile` và `tier` ngay dưới: bảng loài là dữ liệu admin sửa
    được, nên một bảng tra mã→tên phía frontend sẽ trôi khỏi nó vào đúng ngày ai
    đó thêm hoặc đổi tên một loài — và hậu quả là một con thú mang tên con khác,
    không phải một lỗi.
    """
    tile: int
    """Ô của loài, tra từ `pet_species` ngay ở đây.

    Gửi kèm thay vì để trình duyệt tra: bảng loài là dữ liệu admin sửa, nên một
    bảng tra thứ hai phía frontend sẽ trôi khỏi nó vào đúng ngày ai đó thêm loài
    — và hậu quả là một con thú vẽ nhầm hình, không phải một lỗi.
    """
    tier: Literal["common", "uncommon", "rare", "epic", "legendary", "god"]
    """Hạng hiếm của loài đang nuôi.

    Gửi kèm vì giao diện vẽ một vòng sáng dưới chân con thú theo hạng, và bảng
    loài là dữ liệu admin sửa được: một bảng tra mã→hạng phía frontend sẽ trôi
    khỏi nó vào đúng ngày ai đó đổi hạng của một loài, và hậu quả là một con cực
    hiếm mang vòng sáng của loài thường — không lỗi nào, chỉ sai. Cùng lý do
    `tile` được gửi kèm chứ không để client tra.
    """
    nickname: str | None
    level: int
    """Level ĐANG hiển thị: đã áp mốc cao nhất từng đạt, nên nó không bao giờ tụt."""
    xp: int
    xp_into_level: int
    xp_for_next: int
    """`0 / 0` khi đã kịch bảng — một thanh đầy 100% ở đó đọc ra là "sắp lên level"."""
    xp_today: int
    daily_cap: int
    tile_x: int
    tile_y: int
    facing: str
    sleep_until: datetime | None
    """Đang ngủ tới lúc nào, hoặc `null` nếu đang thức.

    Gửi MỐC chứ không gửi cờ `asleep`: trình duyệt cần biết còn bao lâu để đếm
    ngược, và một cờ thì tới lúc hết giấc vẫn nói "đang ngủ" cho tới lần đọc kế
    tiếp — con thú nằm im trên màn hình trong khi máy chủ đã coi nó dậy từ lâu.
    """

    needs: PetNeeds
    hatched_at: datetime


class PetActionRequest(BaseModel):
    action: Literal["feed", "poke", "walk", "sleep", "wake"]


class PetMove(BaseModel):
    """Chỗ con thú dừng lại sau một lần đi.

    Chỉ có toạ độ Ô và hướng nhìn — không có nhu cầu, không có XP. Client không
    được phép nói với máy chủ rằng con thú của nó no bao nhiêu: đó là thứ máy chủ
    suy ra từ `needs_at`, và nhận nó từ trình duyệt là mở một đường sửa chỉ số
    bằng devtools.
    """

    tile_x: int = Field(ge=0, le=255)
    tile_y: int = Field(ge=0, le=255)
    facing: Literal["left", "right"]


class PetSwitch(BaseModel):
    """Đổi con đang nuôi. Chỉ MÃ LOÀI, không gì khác.

    Không nhận vị trí, nhu cầu hay XP, cùng lý do `PetMove` không nhận: đổi con
    là một câu ngắn, và mọi trường thừa ở đây là một đường để client tự đặt chỉ
    số cho mình.
    """

    species: str = Field(min_length=1, max_length=32)


class PetSpeciesPublic(BaseModel):
    """Một loài, như học viên và màn quản trị nhìn thấy.

    `tile` đi thẳng ra trình duyệt thay vì một mã mà frontend phải tra: tấm ghép
    ô LÀ nguồn ảnh, nên mọi chỉ số hợp lệ đều vẽ ra được và không có gì để một
    bảng tra phía frontend bảo vệ. Đây là chỗ khác `BadgePublic.icon`, vốn phải
    là tập đóng vì frontend gọi một component có tên.
    """

    code: str
    label: str
    tile: int = Field(ge=0, lt=180)
    tier: Literal["common", "uncommon", "rare", "epic", "legendary", "god"]
    drop_weight: int = Field(ge=0, le=1000)
    """Trọng số rơi khi mở trứng, KHÔNG phải phần trăm.

    Phần trăm phải cộng lại đúng 100, nên tắt hay thêm một loài biến cả bảng
    thành sai. Trọng số tự chuẩn hoá; tỉ lệ hiển thị tính từ tổng của các loài
    đang bật (`EggChance.percent`). 0 nghĩa là không bao giờ rơi ra — khác với
    `enabled = false`, vốn còn giấu nó khỏi mọi chỗ khác nữa.
    """

    position: int
    enabled: bool


class PetSpeciesEdit(BaseModel):
    """Sửa một loài. Khoá vắng mặt = đừng đụng tới (`exclude_unset` ở nơi gọi).

    `code` KHÔNG có ở đây: nó là khoá chính và là thứ `pet_state.species` trỏ
    tới. Đổi mã nghĩa là mọi con thú đang mang mã cũ trở thành mồ côi cùng lúc —
    cùng lý do `slug` của bộ đề không sửa được từ ô đổi tên.
    """

    label: str | None = Field(default=None, min_length=1, max_length=64)
    tile: int | None = Field(default=None, ge=0, lt=180)
    tier: Literal["common", "uncommon", "rare", "epic", "legendary", "god"] | None = None
    drop_weight: int | None = Field(default=None, ge=0, le=1000)
    position: int | None = None
    enabled: bool | None = None


class PetSpeciesCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=64)
    tile: int = Field(ge=0, lt=180)
    tier: Literal["common", "uncommon", "rare", "epic", "legendary", "god"] = "common"
    drop_weight: int = Field(default=10, ge=0, le=1000)
    position: int = 0


# --- gacha (ADR-010 lát 8) --------------------------------------------------


class EggChance(BaseModel):
    """Một dòng của bảng tỉ lệ, đúng như nó hiện trên màn hình mở trứng.

    Tỉ lệ **phải** được in ra (ADR-010 §6.4). Nhiều nơi đã luật hoá việc này, và
    kể cả không có luật thì đây là sản phẩm học cho học sinh — che tỉ lệ là thứ
    không nên làm với đối tượng đó. `percent` tính ở máy chủ từ chính bảng trọng
    số mà phép quay dùng, nên màn hình không thể nói khác máy.
    """

    code: str
    label: str
    tile: int
    tier: str
    percent: float


class EggPublic(BaseModel):
    """Mọi thứ màn mở trứng cần, trong một lần đọc."""

    ruby_cost: int
    balance: int
    can_open: bool
    """`balance >= ruby_cost` **và** còn loài đang bật. Tính ở máy chủ vì cả hai
    vế đều là dữ liệu máy chủ; tính lại ở client là hai định nghĩa cho một nút."""
    pity_rolls: int
    rolls_since_rare: int
    duplicate_refund: int
    owned: list[str]
    """Mã những loài đã có. Màn hình cần nó để đánh dấu ô đã sưu tầm."""
    chances: list[EggChance]


class EggResult(BaseModel):
    """Kết quả một lần mở trứng. Con thú đã nằm trong bộ sưu tập rồi."""

    species: EggChance
    duplicate: bool
    refund: int
    """Ruby hoàn lại vì trùng. 0 khi là con mới, hoặc khi admin đặt mức hoàn về 0."""
    balance: int
    rolls_since_rare: int
    forced_rare: bool
    """Ra hạng hiếm vì bộ đếm an ủi đã đầy, không phải vì may."""


class EggBatchResult(BaseModel):
    """Kết quả mở nhiều quả một lượt.

    Trả về CẢ DANH SÁCH chứ không phải một bản tóm tắt: người chơi muốn xem từng
    quả ra con gì, và một dòng "được 3 con mới" thì không ai nhớ nổi mình vừa mở
    ra cái gì. `spent` và `refund` là con số của CẢ LƯỢT — sổ ruby cũng ghi đúng
    một dòng trừ và một dòng hoàn, nên hai bên kể cùng một câu chuyện.
    """

    opened: list[EggResult]
    spent: int
    refund: int
    balance: int
    rolls_since_rare: int
    new_species: int
    """Số con CHƯA TỪNG có trong lượt này. Đây là con số người chơi thật sự đo
    một lượt mở bằng, nên máy chủ đếm hộ thay vì bắt giao diện lọc lại."""


class PetOwnedPublic(BaseModel):
    code: str
    label: str
    tile: int
    tier: str
    copies: int
    obtained_at: datetime


class EggSettingPublic(BaseModel):
    ruby_cost: int
    pity_rolls: int
    duplicate_refund: int


class EggSettingEdit(BaseModel):
    """Sửa ba con số của gacha.

    `duplicate_refund` phải NHỎ HƠN `ruby_cost`, và điều đó được kiểm ở cả tầng
    này lẫn database: hoàn bằng hoặc hơn giá trứng là một cỗ máy in ruby, và một
    ràng buộc chỉ nằm ở một tầng là ràng buộc mà tầng kia không biết.
    """

    ruby_cost: int | None = Field(default=None, ge=1, le=1000)
    pity_rolls: int | None = Field(default=None, ge=1, le=100)
    duplicate_refund: int | None = Field(default=None, ge=0, le=999)


# --- chạm mặt (ADR-012) -----------------------------------------------------


class EncounterChoice(BaseModel):
    """Một lựa chọn của câu hỏi chọn nghĩa.

    `key` là mã băm theo (cuộc chạm mặt, mục từ) chứ không phải id mục từ, nên
    nó vô nghĩa ở mọi nơi khác và không nói được đáp án nào đúng. Máy chủ tính
    lại đúng mã ấy cho mục tiêu của cuộc chạm mặt để đối chiếu — không lưu gì
    thêm, không có bảng phiên nào phải dọn.
    """

    key: str
    text: str


class EncounterTask(BaseModel):
    """Nội dung của nhiệm vụ, đủ để hiện lên và không hơn.

    Dạng từ vựng gửi kèm nghĩa và ví dụ vì người học TỰ CHẤM — đây là thẻ lật,
    và thẻ lật thì phải lật ra được. Dạng trắc nghiệm (chưa mở) sẽ dùng đúng
    `QuestionPublic`, thứ cố ý không mang `is_correct`: một schema "gọn hơn" kèm
    đáp án cho tiện chấm ở client là chỗ đáp án rời máy chủ trước khi trả lời.
    """

    kind: Literal["vocabulary", "dictation", "quiz"]
    mode: Literal["typing", "choice", "dictation"] = "typing"
    """Cách người học trả lời, và nó KHÔNG phải `kind`.

    `kind` nói nhiệm vụ mượn bộ chấm nào; `mode` nói màn hình vẽ ra cái gì. Một
    nhiệm vụ từ vựng có hai cách hỏi — gõ lại từ, hoặc chọn nghĩa — và cả hai
    đều đi vào SM-2 qua đúng một đường.

    Không có "lật thẻ": lật thẻ là **tự chấm**, và tự chấm không dùng được ở đây.
    Phần thưởng là ruby, nên một cái nút "tôi nhớ rồi" là một cái nút in tiền —
    và nó cũng không đo được gì, vì người bấm là người được thưởng.
    """

    entry_id: str | None = None
    prompt: str | None = None
    """Đề bài: nghĩa tiếng Việt cho dạng gõ lại, từ tiếng Anh cho dạng chọn nghĩa."""
    part_of_speech: str | None = None
    choices: list[EncounterChoice] | None = None
    """Bốn lựa chọn cho dạng chọn nghĩa, `null` cho dạng khác.

    **Không gửi `entry_id` ở dạng này** và mỗi lựa chọn mang một `key` băm theo
    cuộc chạm mặt, chứ không mang id thật: gửi id thật thì đáp án đúng là cái id
    trùng với `entry_id`, và cả câu hỏi trả lời được bằng devtools mà không cần
    đọc chữ nào.
    """

    hints_left: int = 0
    """Còn xin gợi ý được mấy lần. Chỉ dạng gõ lại từ mới khác 0.

    Gửi kèm để cái nút biết tự khoá sau khi tải lại trang: bộ đếm sống ở máy chủ
    (`encounter.hints_used`), nên nếu không gửi thì giao diện dựng lại sẽ mời
    người dùng bấm một cái nút chắc chắn trả về lỗi.
    """

    audio_url: str | None = None
    """Bản thu của câu chép chính tả. Dạng khác để trống."""
    word_count: int | None = None
    """Số từ của câu, để giao diện nói trước câu này dài bao nhiêu.

    Gửi ĐỘ DÀI chứ không gửi `transcript`, và đây là chỗ khác hẳn
    `GET /dictation/{id}`: màn chép chính tả chấm ở trình duyệt nên phải nhận
    đáp án, còn thẻ nhiệm vụ thì không — nó gửi câu gõ lên máy chủ và nhận lại
    kết quả. Gửi kèm đáp án ở đây là cho không một phần thưởng.
    """


class EncounterPublic(BaseModel):
    """Một cuộc chạm mặt đang chờ.

    **Không có ô sprite và không có toạ độ**: trình duyệt tự chọn con vật và chỗ
    đứng từ `id`. Máy chủ không đọc `map.json` (cùng lý do `PUT /pet/position`
    không kiểm ô đi được), và bảng phân vai sinh vật sống ở frontend.
    """

    id: str
    kind: Literal["npc", "intruder"]
    steps_total: int
    steps_done: int
    reward_ruby: int
    expires_at: datetime
    """Gửi MỐC chứ không gửi số giây còn lại: số giây đứng yên giữa hai lần đọc,
    còn mốc thì trình duyệt đếm ngược được — cùng lý do `sleep_until` là mốc."""
    task: EncounterTask


class EncounterAnswer(BaseModel):
    """Trả lời một bước.

    **Máy chủ nhận CÂU TRẢ LỜI, không nhận điểm.** Bản đầu nhận thẳng điểm SM-2
    do người học tự chấm ở màn thẻ lật; điểm ấy là thứ quyết định có trả ruby
    hay không, nên nó là một trường "hãy trả tôi hai mươi ruby" gửi từ trình
    duyệt. Giờ máy chủ tự chấm rồi mới quy ra điểm, qua đúng `recall.judge` và
    `recall.grade_for` mà màn gõ lại từ đang dùng — vẫn không có bộ chấm thứ hai
    nào (ADR-012 §2).

    Hai trường, không phải hai endpoint: cách hỏi là thuộc tính của cuộc chạm
    mặt chứ không phải của lời gọi, nên tách đường sẽ để client tự khai nó đang
    trả lời dạng gì — và khai sai thì bước vẫn tính.
    """

    text: str = Field(default="", max_length=2000)
    """Câu đã gõ: cả câu cho chép chính tả, một từ cho dạng gõ lại."""
    choice: str = Field(default="", max_length=64)
    """`key` của lựa chọn đã chọn, cho dạng chọn nghĩa."""


class DiffWord(BaseModel):
    """Một từ trong bảng so sánh của bài chép chính tả.

    Khai thành model chứ không để `dict[str, str]`: OpenAPI dịch dict thành một
    bản đồ khoá tự do, nên phía TypeScript nhận `{[k: string]: string}` và mất
    đúng hai cái tên mà giao diện đọc.
    """

    op: Literal["match", "missing", "extra"]
    word: str


class EncounterResult(BaseModel):
    correct: bool
    """Bước vừa rồi có được tính là làm được không.

    Với từ vựng, "được" nghĩa là gõ đúng từ hoặc chọn đúng nghĩa — máy chấm, và
    một lỗi gõ nhẹ vẫn tính là chưa được (nó vào SM-2 ở mức KHÓ). Với chép chính tả,
    "được" là `is_complete` — đúng trọn câu, cùng thước đo mà tiến độ chép chính
    tả đang đếm, chứ không phải `accuracy` (gõ thừa vẫn cho 100%).
    """
    steps_done: int
    steps_total: int
    done: bool
    reward_ruby: int
    """Ruby thực sự vào ví ở lần gọi này. 0 khi chưa xong hoặc đã trả rồi."""
    balance: int
    encounter: EncounterPublic | None
    """Cuộc chạm mặt sau khi trả lời, hoặc `null` khi nó đã xong.

    Với kẻ xâm nhập, `task` trong này là **nhiệm vụ MỚI của bước sau**: mục tiêu
    được bốc lại sau mỗi bước đúng, nếu không thì ba bước cùng một từ và cả cuộc
    chạm mặt chỉ là một cái nút bấm ba lần.
    """

    word_diff: list[DiffWord] | None = None
    """Kết quả so từng từ của một lượt chép chính tả, để thẻ tô đúng/sai.

    `null` cho dạng khác. Chỉ có ở đây, KHÔNG có ở `EncounterTask`: nó là thứ
    máy chủ trả lại SAU khi chấm, nên nó không tiết lộ gì trước lúc trả lời.
    """


# --- cấu hình chạm mặt (ADR-012 lát 7) --------------------------------------


class EncounterSettingPublic(BaseModel):
    """Bảy con số của cơ chế chạm mặt.

    Nhịp sinh **phải** sửa được từ đây, và đó là điều kiện để lập luận "phần
    thưởng không cày được" của ADR-012 §6 đứng vững: thứ giới hạn ruby từ nhiệm
    vụ là nhịp xuất hiện, và một trần nằm rải rác trong mã thì không ai chỉnh
    được vào ngày phát hiện nó sai.
    """

    npc_gap_seconds: int
    npc_life_seconds: int
    npc_reward: int
    intruder_gap_seconds: int
    intruder_life_seconds: int
    intruder_reward: int
    intruder_steps: int


class EncounterSettingEdit(BaseModel):
    """Sửa cấu hình chạm mặt. Khoá vắng mặt = đừng đụng tới.

    Cận trên không phải để làm khó: `life` dài hơn `gap` nghĩa là cuộc trước
    chưa hết hạn thì cuộc sau đã tới giờ, và vì mỗi lúc chỉ một cuộc được tồn
    tại, giờ hẹn cứ trôi qua mà không sinh được gì — tính năng im lặng chứ không
    báo lỗi. Chỗ kiểm chuyện đó là endpoint, vì nó so hai trường với nhau.
    """

    npc_gap_seconds: int | None = Field(default=None, ge=60, le=86_400)
    npc_life_seconds: int | None = Field(default=None, ge=30, le=86_400)
    npc_reward: int | None = Field(default=None, ge=0, le=500)
    intruder_gap_seconds: int | None = Field(default=None, ge=60, le=86_400)
    intruder_life_seconds: int | None = Field(default=None, ge=30, le=86_400)
    intruder_reward: int | None = Field(default=None, ge=0, le=500)
    intruder_steps: int | None = Field(default=None, ge=1, le=10)


class EncounterHint(BaseModel):
    """Một lần gợi ý cho nhiệm vụ gõ lại từ.

    Trả về từ ĐÃ CHE, không trả về số chữ đã mở: giao diện chỉ việc in ra, nên
    không có phép ghép chuỗi nào ở phía trình duyệt để mà làm sai — và cũng không
    có đường nào để một client tự "mở thêm" bằng cách gọi lại với số lớn hơn.
    """

    hint: str
    hints_left: int
