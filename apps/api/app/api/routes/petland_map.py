"""Đọc và ghi nội dung góc thú cưng: bản đồ (migration 048) và phân vai ô sinh
vật (migration 071).
Trình vẽ trước đây tải tệp về rồi người sửa commit tay. Lý do cũ vẫn đúng — bản
đồ là nội dung và nội dung thuộc về git — nhưng nó có trước khi có production,
nơi sửa một ô cỏ phải đi qua một lần deploy.

Cách dung hoà: **không có hàng nghĩa là tệp đã commit đang chạy.** Bảng chỉ là
lớp ghi đè, và giao diện nói rõ đang chạy bản nào, nên chuyện "hai nơi hai bản
đồ" không còn là chuyện thầm lặng — đó chính là điều thiết kế cũ sợ.

`GET` không cần đăng nhập: bản đồ và bảng phân vai không phải bí mật, và trang
Petland tải chúng trước khi làm bất cứ việc gì khác.
"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models import Creature, PetlandMap, PetSpecies, User
from app.schemas.pet import (
    CreatureEdit,
    CreaturePromote,
    CreaturePublic,
    CreatureRoleLiteral,
    CreatureRoleMap,
)
from app.schemas.petland_map import PetlandMapBody, PetlandMapPublic
from app.services import creature as creature_service

router = APIRouter(tags=["petland"])

can_edit_map = require_role("admin")


@router.get(
    "/petland/map",
    response_model=PetlandMapPublic,
    responses={204: {"description": "Chưa ai sửa trên web; dùng bản đã commit."}},
)
def read_map(response: Response, db: Session = Depends(get_db)) -> PetlandMapPublic | Response:
    row = db.execute(select(PetlandMap).where(PetlandMap.id == 1)).scalar_one_or_none()
    if row is None:
        # 204 chứ không 404: "chưa cấu hình" là trạng thái BÌNH THƯỜNG ở đây, và
        # 404 sẽ hiện lên như một lỗi trong console của mọi lần tải trang.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return PetlandMapPublic(
        w=row.w,
        h=row.h,
        ground=row.ground,  # type: ignore[arg-type]
        objects=row.objects,  # type: ignore[arg-type]
        solid=row.solid,  # type: ignore[arg-type]
        updated_at=row.updated_at,
    )


@router.put("/admin/petland/map", response_model=PetlandMapPublic)
def save_map(
    body: PetlandMapBody,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit_map),
) -> PetlandMapPublic:
    payload = body.model_dump(mode="json")
    row = db.execute(select(PetlandMap).where(PetlandMap.id == 1)).scalar_one_or_none()
    if row is None:
        row = PetlandMap(id=1)
        db.add(row)
    row.w, row.h = body.w, body.h
    row.ground = payload["ground"]
    row.objects = payload["objects"]
    row.solid = payload["solid"]
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return PetlandMapPublic(
        w=row.w,
        h=row.h,
        ground=row.ground,  # type: ignore[arg-type]
        objects=row.objects,  # type: ignore[arg-type]
        solid=row.solid,  # type: ignore[arg-type]
        updated_at=row.updated_at,
    )


# --- phân vai ô sinh vật (migration 071) ------------------------------------


def _species_codes_by_tile(db: Session) -> dict[int, str]:
    """{tile: code} của loài thú nuôi, theo vị trí hiển thị khi hai loài dùng
    chung một ô. Màn quản trị chỉ cần biết "ô này đã có chủ"."""
    rows = db.execute(
        select(PetSpecies.tile, PetSpecies.code).order_by(PetSpecies.position, PetSpecies.code)
    ).all()
    return {int(tile): code for tile, code in rows}


def _pet_tiles(db: Session) -> list[int]:
    return [int(tile) for (tile,) in db.execute(select(PetSpecies.tile)).all()]


@router.get("/petland/creatures", response_model=CreatureRoleMap)
def read_creature_roles(db: Session = Depends(get_db)) -> CreatureRoleMap:
    """{tile: role} + danh sách ô thú nuôi, cho runtime phía frontend.

    Vai "pet" không nằm trong `roles` — nó là join với `pet_species` (xem
    `CREATURE_ROLES`), nên client nhận kèm danh sách ô của loài để loại chúng
    khỏi đám NPC/quái. Gieo lười chạy ở đây: người học mở Petland trước cả khi
    admin mở màn quản trị, và bảng rỗng vẫn phải trả lời được.
    """
    return CreatureRoleMap(
        roles={
            str(tile): cast(CreatureRoleLiteral, role)
            for tile, role in creature_service.role_map(db).items()
        },
        pets=_pet_tiles(db),
    )


@router.get("/admin/petland/creatures", response_model=list[CreaturePublic])
def list_creatures(
    db: Session = Depends(get_db),
    _user: User = Depends(can_edit_map),
) -> list[CreaturePublic]:
    species_by_tile = _species_codes_by_tile(db)
    return [
        CreaturePublic(
            tile=row.tile,
            role=cast(CreatureRoleLiteral, row.role),
            label=row.label,
            species_code=species_by_tile.get(row.tile),
        )
        for row in creature_service.seed_if_empty(db)
    ]


@router.patch("/admin/petland/creatures/{tile}", response_model=CreaturePublic)
def edit_creature(
    tile: int,
    body: CreatureEdit,
    db: Session = Depends(get_db),
    _user: User = Depends(can_edit_map),
) -> CreaturePublic:
    row = db.get(Creature, tile)
    if row is None:
        # Mọi ô 0..179 được gieo, nên ô hợp lệ mà thiếu hàng là lỗi trạng thái,
        # không phải "chưa có" — gieo lại rồi đọc tiếp.
        creature_service.seed_if_empty(db)
        row = db.get(Creature, tile)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có ô này")
    # `model_fields_set` chứ không `is not None`: null là LỆNH XOÁ tên, và so
    # `is not None` là gộp "không gửi" với "gửi null" — ô không bao giờ được
    # trả lại đúng danh nghĩa.
    if body.role is not None or "label" in body.model_fields_set:
        if db.scalar(select(PetSpecies).where(PetSpecies.tile == tile)) is not None:
            # Từ chối NGAY CẢ khi chỉ đổi tên: vai của ô này không nằm ở bảng
            # creature, và cho sửa nửa cái là tạo cảm giác bảng đang cai trị ô.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ô này là loài thú nuôi — đổi vai và tên ở màn quản trị loài (/admin/pet)",
            )
        if body.role is not None:
            row.role = body.role
        if "label" in body.model_fields_set:
            row.label = body.label or None
        db.commit()
    species_by_tile = _species_codes_by_tile(db)
    return CreaturePublic(
        tile=row.tile,
        role=cast(CreatureRoleLiteral, row.role),
        label=row.label,
        species_code=species_by_tile.get(row.tile),
    )


@router.post(
    "/admin/petland/creatures/{tile}/promote",
    response_model=CreaturePublic,
    status_code=status.HTTP_201_CREATED,
)
def promote_creature(
    tile: int,
    body: CreaturePromote,
    db: Session = Depends(get_db),
    _user: User = Depends(can_edit_map),
) -> CreaturePublic:
    """Chuyển một ô thành thú nuôi: tạo hàng loài tại đúng ô đó.

    Thú nuôi là hàng trong `pet_species`, nên "chuyển vai" ở đây KHÔNG đụng tới
    bảng creature — nó tạo loài. Trước khi tạo phải đảm bảo ô chưa có chủ: hai
    loài dùng chung một ô nghĩa là gacha trả về con này mà màn hình vẽ con kia,
    và không có gì báo.

    Vai cũ được GIỮ NGUYÊN trong hàng creature — nó là vai phụ, dùng khi loài
    bị xoá bỏ hay chuyển đi nơi khác, không phải vai đang chạy.
    """
    if tile < 0 or tile >= 180:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có ô này")
    if db.scalar(select(PetSpecies).where(PetSpecies.tile == tile)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ô này đã là thú nuôi — sửa loài ở /admin/pet",
        )
    if db.scalar(select(PetSpecies).where(PetSpecies.code == body.code)) is not None:
        # Kiểm TRƯỚC khi add: IntegrityError từ khoá chính là 500, và một mã
        # trùng là lỗi người dùng (400-họ), không phải lỗi máy chủ.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã loài đã tồn tại — chọn mã khác, hoặc sửa loài cũ ở /admin/pet",
        )
    creature_service.seed_if_empty(db)
    row = db.get(Creature, tile)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có ô này")
    label = body.label or row.label or f"Ô {tile}"
    db.add(
        PetSpecies(
            code=body.code,
            label=label,
            tile=tile,
            tier=body.tier,
            drop_weight=(
                body.drop_weight
                if body.drop_weight is not None
                else CreaturePromote.TIER_WEIGHTS[body.tier]
            ),
            position=body.position,
        )
    )
    db.commit()
    return CreaturePublic(
        tile=tile,
        role=cast(CreatureRoleLiteral, row.role),
        label=label,
        species_code=body.code,
    )
