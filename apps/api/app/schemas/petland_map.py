"""Bản đồ Petland đi qua HTTP (migration 048).

Kiểm ở máy chủ chứ không tin trình vẽ. Một bản đồ sai độ dài hay chặn hết lối đi
vẫn là JSON hợp lệ, vẫn lưu được, và chỉ lộ ra khi có người mở góc thú cưng lên
thấy con thú kẹt trong tường.
"""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

# Ô sinh mặc định của `pet_state` (migration 046). Bản đồ nào chặn ô này thì mọi
# tài khoản mới có một con thú không đi được — đúng lỗi mà 046 đã phải đi sửa.
SPAWN_X, SPAWN_Y = 3, 5

MIN_SIDE, MAX_SIDE = 4, 64


class MapCell(BaseModel):
    sheet: str = Field(min_length=1, max_length=32)
    index: int = Field(ge=0, le=4095)


class PetlandMapBody(BaseModel):
    w: int = Field(ge=MIN_SIDE, le=MAX_SIDE)
    h: int = Field(ge=MIN_SIDE, le=MAX_SIDE)
    ground: list[MapCell | None]
    objects: list[MapCell | None]
    solid: list[bool]

    @model_validator(mode="after")
    def _check(self) -> "PetlandMapBody":
        size = self.w * self.h
        for name, layer in (
            ("ground", self.ground),
            ("objects", self.objects),
            ("solid", self.solid),
        ):
            if len(layer) != size:
                raise ValueError(
                    f"{name} has {len(layer)} cells, expected {size} for {self.w}×{self.h}"
                )
        if all(self.solid):
            raise ValueError("every tile is blocking — the pet would have nowhere to stand")
        if self.w <= SPAWN_X or self.h <= SPAWN_Y:
            raise ValueError(f"the map must contain the spawn tile ({SPAWN_X}, {SPAWN_Y})")
        if self.solid[SPAWN_Y * self.w + SPAWN_X]:
            raise ValueError(
                f"the spawn tile ({SPAWN_X}, {SPAWN_Y}) is blocking, "
                "so every new pet would start stuck"
            )
        return self


class PetlandMapPublic(PetlandMapBody):
    updated_at: datetime | None = None
