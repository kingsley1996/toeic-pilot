"""Hình dạng leo tháp dungeon đi qua HTTP (migration 098).

Mọi con số nằm ở `services/dungeon.py`; schemas chỉ mang số đã tính.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.pet import DungeonView, EncounterPublic

DungeonStatus = str
"""`fighting` | `dead` | `done`. Giữ `str` thay vì `Literal` để OpenAPI regen
không phình — client chỉ đọc ba giá trị này, và server giữ CHECK ở DB."""


class DungeonState(BaseModel):
    """`GET /dungeon/state`: run + battle đang đánh (nếu có)."""

    floor: int = Field(ge=1, le=100)
    checkpoint: int = Field(ge=1)
    pet_hp: int = Field(ge=0)
    pet_max_hp: int = Field(ge=1)
    status: DungeonStatus
    updated_at: datetime | None = None
    battle: EncounterPublic | None = None
    """Battle kind=`dungeon` đang chờ, hoặc `null` khi chết/xong tháp."""

    def with_view(self, monster_hp: int, monster_max_hp: int) -> DungeonView:
        """Gói gọn thành `DungeonView` để gắn vào `EncounterResult`."""
        return DungeonView(
            floor=self.floor,
            checkpoint=self.checkpoint,
            pet_hp=self.pet_hp,
            pet_max_hp=self.pet_max_hp,
            status=self.status,
            monster_hp=monster_hp,
            monster_max_hp=monster_max_hp,
        )
