"""Sảnh danh vọng: BXH level học viên + level thú cưng (SPEC-HALL-OF-FAME).

Chỉ đọc, không mùa giải ở v1. Mỗi bảng đúng 2 truy vấn (top N + hạng của tôi);
hạng tính ở Python trên N hàng đã lấy, không tính trong SQL.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.storage import get_driver
from app.models import PetOwned, User
from app.models.profile import UserProfile
from app.models.progression import XpEvent
from app.services.pet_species import row_for


def mask_email(email: str) -> str:
    """Email che cho người chưa đặt tên hiển thị: giữ 2 ký tự đầu + `***`.

    Một hàm duy nhất để mọi chỗ che giống nhau — và test ghim đúng định dạng
    này, vì lộ nguyên email người khác là lỗi riêng tư chứ không phải lỗi hiển
    thị.
    """
    local = email.split("@", 1)[0]
    return f"{local[:2]}***" if len(local) >= 2 else "***"


def shown_name(display_name: str | None, email: str) -> str:
    return display_name or mask_email(email)


def _ranked(pairs: list[tuple[Any, Any]]) -> list[tuple[int, Any]]:
    """Gắn hạng kiểu thi đấu từ cặp (mốc xếp hạng, bản ghi): đồng điểm thì cùng
    hạng, hạng kế nhảy (`1,2,2,4`).

    Thuần để test được mà không dựng bảng — phần khó ở đây là số học hạng.
    """
    out: list[tuple[int, Any]] = []
    rank = 0
    seen = 0
    last: Any = object()
    for value, entry in pairs:
        seen += 1
        if value != last:
            rank = seen
            last = value
        out.append((rank, entry))
    return out


def user_board(
    db: Session, *, viewer_id: uuid.UUID | None, limit: int
) -> tuple[list[tuple[int, str, str | None, int, int, bool]], int | None, int]:
    """Top N học viên theo tổng XP + hạng của người xem + tổng số người.

    Mỗi hàng `(rank, tên, avatar, level, xp, is_me)`. Level là `level_reached`
    đã lưu — bảng ngưỡng admin sửa được nên tính lại lúc đọc sẽ làm cả bảng
    tụt hạng cùng lúc sau một lần nâng chuẩn. Avatar dựng URL ở đây theo đúng
    cách `profile_public` làm.
    """
    per = (
        select(XpEvent.user_id.label("uid"), func.sum(XpEvent.amount).label("t"))
        .group_by(XpEvent.user_id)
        .subquery()
    )
    total_col = func.coalesce(per.c.t, 0)
    rows = list(
        db.execute(
            select(
                User.id,
                User.email,
                UserProfile.display_name,
                UserProfile.avatar_storage_key,
                UserProfile.level_reached,
                total_col.label("total"),
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .outerjoin(per, per.c.uid == User.id)
            .order_by(total_col.desc(), User.created_at.asc())
            .limit(limit)
        ).all()
    )
    my_rank: int | None = None
    if viewer_id is not None:
        my_total = int(
            db.scalar(
                select(func.coalesce(func.sum(XpEvent.amount), 0)).where(
                    XpEvent.user_id == viewer_id
                )
            )
            or 0
        )
        higher = db.scalar(
            select(func.count())
            .select_from(User)
            .outerjoin(per, per.c.uid == User.id)
            .where(func.coalesce(per.c.t, 0) > my_total)
        )
        my_rank = int(higher or 0) + 1
    total = int(db.scalar(select(func.count()).select_from(User)) or 0)

    out = []
    for rank, row in _ranked([(row.total, row) for row in rows]):
        out.append(
            (
                rank,
                shown_name(row.display_name, row.email),
                (
                    get_driver("image").public_url(row.avatar_storage_key)
                    if row.avatar_storage_key
                    else None
                ),
                row.level_reached or 1,
                int(row.total),
                row.id == viewer_id,
            )
        )
    return out, my_rank, total


def pet_board(
    db: Session, *, viewer_id: uuid.UUID | None, limit: int
) -> tuple[list[tuple[int, str, int, int, str, str | None, str, int, str, bool]], int | None, int]:
    """Top N thú theo (level, xp) + hạng của người xem + tổng số.

    Mỗi hàng `(rank, tên chủ, level, xp, species, nickname, tier, tile, sheet,
    is_me)`. MỌI con trong tủ đều lên bảng, không riêng con đang nuôi — một
    hàng là một con, và một người có thể chiếm nhiều hàng. `my_rank` là hạng
    của con TỐT NHẤT của người xem.
    """
    rows = list(
        db.execute(
            select(
                User.id,
                User.email,
                UserProfile.display_name,
                PetOwned.species,
                PetOwned.nickname,
                PetOwned.xp,
                PetOwned.level_reached,
            )
            .join(PetOwned, PetOwned.user_id == User.id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .order_by(PetOwned.level_reached.desc(), PetOwned.xp.desc(), PetOwned.obtained_at.asc())
            .limit(limit)
        ).all()
    )

    my_rank: int | None = None
    if viewer_id is not None:
        best = db.execute(
            select(PetOwned.level_reached, PetOwned.xp)
            .where(PetOwned.user_id == viewer_id)
            .order_by(PetOwned.level_reached.desc(), PetOwned.xp.desc())
            .limit(1)
        ).first()
        if best is not None:
            higher = db.scalar(
                select(func.count())
                .select_from(PetOwned)
                .where(
                    (PetOwned.level_reached > best.level_reached)
                    | ((PetOwned.level_reached == best.level_reached) & (PetOwned.xp > best.xp))
                )
            )
            my_rank = int(higher or 0) + 1
    total = int(db.scalar(select(func.count()).select_from(PetOwned)) or 0)

    out = []
    for rank, row in _ranked([((row.level_reached, row.xp), row) for row in rows]):
        species_row = row_for(db, row.species)
        out.append(
            (
                rank,
                shown_name(row.display_name, row.email),
                row.level_reached,
                row.xp,
                row.species,
                row.nickname,
                species_row.tier if species_row is not None else "common",
                species_row.tile if species_row is not None else 0,
                species_row.sheet if species_row is not None else "creatures",
                row.id == viewer_id,
            )
        )
    return out, my_rank, total
