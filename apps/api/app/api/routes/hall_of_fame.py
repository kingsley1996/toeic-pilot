"""Sảnh danh vọng: BXH level học viên + level thú cưng (SPEC-HALL-OF-FAME).

Đọc CÔNG KHAI (kể cả khách): đây là số liệu tổng hợp, không phải hồ sơ riêng —
cùng tinh thần ADR-015 của thư viện listening. Đăng nhập thì kèm highlight
dòng của mình và hạng của mình.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user
from app.core.database import get_db
from app.models import User
from app.schemas.hall_of_fame import (
    HallPetBoard,
    HallPetEntry,
    HallUserBoard,
    HallUserEntry,
)
from app.services import hall_of_fame

router = APIRouter(tags=["hall"])


@router.get("/hall-of-fame/users", response_model=HallUserBoard)
def read_user_board(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> HallUserBoard:
    """Top N học viên theo tổng XP. Khách đọc được, `my_rank` null."""
    viewer_id: uuid.UUID | None = user.id if user else None
    entries, my_rank, total = hall_of_fame.user_board(db, viewer_id=viewer_id, limit=limit)
    return HallUserBoard(
        entries=[
            HallUserEntry(
                rank=rank,
                display_name=name,
                avatar_url=avatar,
                level=level,
                xp_total=xp,
                is_me=is_me,
            )
            for rank, name, avatar, level, xp, is_me in entries
        ],
        my_rank=my_rank,
        total=total,
    )


@router.get("/hall-of-fame/pets", response_model=HallPetBoard)
def read_pet_board(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> HallPetBoard:
    """Top N thú ĐANG NUÔI theo (level, xp). Chưa mở trứng thì `my_rank` null."""
    viewer_id: uuid.UUID | None = user.id if user else None
    entries, my_rank, total = hall_of_fame.pet_board(db, viewer_id=viewer_id, limit=limit)
    return HallPetBoard(
        entries=[
            HallPetEntry(
                rank=rank,
                display_name=name,
                level=level,
                xp=xp,
                species=species,
                nickname=nickname,
                tier=tier,
                tile=tile,
                sheet=sheet,
                is_me=is_me,
            )
            for rank, name, level, xp, species, nickname, tier, tile, sheet, is_me in entries
        ],
        my_rank=my_rank,
        total=total,
    )
