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
    tile: int
    """Ô của loài, tra từ `pet_species` ngay ở đây.

    Gửi kèm thay vì để trình duyệt tra: bảng loài là dữ liệu admin sửa, nên một
    bảng tra thứ hai phía frontend sẽ trôi khỏi nó vào đúng ngày ai đó thêm loài
    — và hậu quả là một con thú vẽ nhầm hình, không phải một lỗi.
    """
    tier: Literal["common", "uncommon", "rare", "epic", "legendary"]
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
    needs: PetNeeds
    hatched_at: datetime


class PetActionRequest(BaseModel):
    action: Literal["feed", "poke", "walk"]


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
    tier: Literal["common", "uncommon", "rare", "epic", "legendary"]
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
    tier: Literal["common", "uncommon", "rare", "epic", "legendary"] | None = None
    drop_weight: int | None = Field(default=None, ge=0, le=1000)
    position: int | None = None
    enabled: bool | None = None


class PetSpeciesCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=64)
    tile: int = Field(ge=0, lt=180)
    tier: Literal["common", "uncommon", "rare", "epic", "legendary"] = "common"
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
