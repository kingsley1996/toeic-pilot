"""Quản trị loài thú (ADR-010 §6.3).

`require_role("admin")` chứ không `editor`: đặt bảng loài và hạng hiếm là quyết
định VẬN HÀNH — nó định giá cho cả hệ gacha — chứ không phải việc biên tập nội
dung. Cùng ranh giới mà `/admin/progression` đã vẽ.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models import PetSpecies, User
from app.schemas.pet import PetSpeciesCreate, PetSpeciesEdit, PetSpeciesPublic
from app.services.pet_species import all_species

router = APIRouter(prefix="/admin/pet", tags=["admin"])

can_configure = require_role("admin")


def _public(row: PetSpecies) -> PetSpeciesPublic:
    return PetSpeciesPublic(
        code=row.code,
        label=row.label,
        tile=row.tile,
        tier=row.tier,  # type: ignore[arg-type]
        position=row.position,
        enabled=row.enabled,
    )


@router.get("/species", response_model=list[PetSpeciesPublic])
def list_species(
    db: Session = Depends(get_db), _: User = Depends(can_configure)
) -> list[PetSpeciesPublic]:
    """Cả loài đã tắt.

    Màn quản trị là nơi DUY NHẤT nhìn thấy hàng đã tắt; giấu chúng ở đây thì cách
    duy nhất bật lại là sửa database.
    """
    return [_public(row) for row in all_species(db, include_disabled=True)]


@router.post("/species", response_model=PetSpeciesPublic, status_code=status.HTTP_201_CREATED)
def create_species(
    body: PetSpeciesCreate, db: Session = Depends(get_db), _: User = Depends(can_configure)
) -> PetSpeciesPublic:
    # Đọc trước khi ghi để bảng rỗng được gieo mặc định — nếu không, loài đầu
    # tiên admin tạo sẽ khiến bảng hết rỗng và mười hai loài mặc định không bao
    # giờ xuất hiện.
    all_species(db, include_disabled=True)
    row = PetSpecies(**body.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Species {body.code!r} already exists"
        ) from None
    return _public(row)


@router.patch("/species/{code}", response_model=PetSpeciesPublic)
def update_species(
    code: str,
    body: PetSpeciesEdit,
    db: Session = Depends(get_db),
    _: User = Depends(can_configure),
) -> PetSpeciesPublic:
    row = db.get(PetSpecies, code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Species not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    return _public(row)
