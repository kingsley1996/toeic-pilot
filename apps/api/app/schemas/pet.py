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
    nickname: str | None
    level: int
    xp: int
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
