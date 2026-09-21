"""Hình dạng bảng xếp hạng Sảnh danh vọng (SPEC-HALL-OF-FAME)."""

from pydantic import BaseModel


class HallUserEntry(BaseModel):
    rank: int
    display_name: str
    avatar_url: str | None
    level: int
    xp_total: int
    is_me: bool


class HallPetEntry(BaseModel):
    rank: int
    display_name: str
    level: int
    xp: int
    species: str
    nickname: str | None
    tier: str
    tile: int
    sheet: str
    is_me: bool


class HallUserBoard(BaseModel):
    entries: list[HallUserEntry]
    my_rank: int | None
    total: int


class HallPetBoard(BaseModel):
    entries: list[HallPetEntry]
    my_rank: int | None
    total: int
