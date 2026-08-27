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
    tier: Literal["common", "uncommon", "rare", "epic"]
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
    tier: Literal["common", "uncommon", "rare", "epic"] | None = None
    position: int | None = None
    enabled: bool | None = None


class PetSpeciesCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=64)
    tile: int = Field(ge=0, lt=180)
    tier: Literal["common", "uncommon", "rare", "epic"] = "common"
    position: int = 0
