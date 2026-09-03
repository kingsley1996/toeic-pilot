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
from app.models import EncounterSetting, PetSpecies, User
from app.schemas.pet import (
    EggSettingEdit,
    EggSettingPublic,
    EncounterSettingEdit,
    EncounterSettingPublic,
    PetSpeciesCreate,
    PetSpeciesEdit,
    PetSpeciesPublic,
)
from app.services import encounters
from app.services.gacha import settings_row
from app.services.pet_species import all_species
from app.services.pet_state import ensure_pet

router = APIRouter(prefix="/admin/pet", tags=["admin"])

can_configure = require_role("admin")


def _public(row: PetSpecies) -> PetSpeciesPublic:
    return PetSpeciesPublic(
        code=row.code,
        label=row.label,
        tile=row.tile,
        tier=row.tier,  # type: ignore[arg-type]
        drop_weight=row.drop_weight,
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


@router.get("/eggs", response_model=EggSettingPublic)
def read_egg_setting(
    db: Session = Depends(get_db), _: User = Depends(can_configure)
) -> EggSettingPublic:
    row = settings_row(db)
    return EggSettingPublic(
        ruby_cost=row.ruby_cost,
        pity_rolls=row.pity_rolls,
        duplicate_refund=row.duplicate_refund,
    )


@router.patch("/eggs", response_model=EggSettingPublic)
def update_egg_setting(
    body: EggSettingEdit,
    db: Session = Depends(get_db),
    _: User = Depends(can_configure),
) -> EggSettingPublic:
    """Giá trứng, bộ đếm an ủi, mức hoàn khi trùng.

    Kiểm "hoàn < giá" ở ĐÂY nữa, không chỉ ở database: hai trường có thể đổi
    trong cùng một lần gửi, nên phải so giá trị SAU khi áp cả hai. Ràng buộc
    database là lưới cuối và nó ném ra một lỗi không dịch được cho người dùng;
    chỗ này mới là chỗ nói được vì sao.
    """
    row = settings_row(db)
    changes = body.model_dump(exclude_unset=True)
    cost = int(changes.get("ruby_cost", row.ruby_cost))
    refund = int(changes.get("duplicate_refund", row.duplicate_refund))
    if refund >= cost:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Duplicate refund ({refund}) must stay below the egg price ({cost}) — "
                "otherwise opening duplicates prints ruby out of nothing."
            ),
        )
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    return EggSettingPublic(
        ruby_cost=row.ruby_cost,
        pity_rolls=row.pity_rolls,
        duplicate_refund=row.duplicate_refund,
    )


def _encounter_public(row: EncounterSetting) -> EncounterSettingPublic:
    return EncounterSettingPublic(
        npc_gap_seconds=row.npc_gap_seconds,
        npc_life_seconds=row.npc_life_seconds,
        npc_reward=row.npc_reward,
        intruder_gap_seconds=row.intruder_gap_seconds,
        intruder_life_seconds=row.intruder_life_seconds,
        intruder_reward=row.intruder_reward,
        intruder_steps=row.intruder_steps,
    )


@router.get("/encounters", response_model=EncounterSettingPublic)
def read_encounter_setting(
    db: Session = Depends(get_db), _: User = Depends(can_configure)
) -> EncounterSettingPublic:
    return _encounter_public(encounters.settings_row(db))


@router.patch("/encounters", response_model=EncounterSettingPublic)
def update_encounter_setting(
    body: EncounterSettingEdit,
    db: Session = Depends(get_db),
    _: User = Depends(can_configure),
) -> EncounterSettingPublic:
    """Nhịp sinh, tuổi thọ, mức thưởng, số bước.

    Từ chối `life >= gap`, và lý do là một cách hỏng IM LẶNG: chỉ một cuộc chạm
    mặt được tồn tại cùng lúc, nên một cuộc sống lâu hơn khoảng cách giữa hai
    lần sinh sẽ chiếm chỗ suốt — giờ hẹn tới rồi trôi qua mà không ai xuất hiện,
    và không có lỗi nào để mà đọc. So SAU khi áp cả hai thay đổi, cùng lý do
    "hoàn < giá" ở trên: hai trường có thể đổi trong cùng một lần gửi.
    """
    row = encounters.settings_row(db)
    changes = body.model_dump(exclude_unset=True)
    for kind in ("npc", "intruder"):
        gap = int(changes.get(f"{kind}_gap_seconds", getattr(row, f"{kind}_gap_seconds")))
        life = int(changes.get(f"{kind}_life_seconds", getattr(row, f"{kind}_life_seconds")))
        if life >= gap:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"{kind}: lifetime ({life}s) must stay below the gap ({gap}s) — "
                    "one encounter exists at a time, so a longer-lived one would "
                    "occupy the slot and later spawns would silently never happen."
                ),
            )
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    return _encounter_public(row)


@router.post("/encounters/spawn", status_code=status.HTTP_201_CREATED)
def spawn_encounters(
    db: Session = Depends(get_db),
    admin: User = Depends(can_configure),
) -> dict[str, int]:
    """Gọi ngay đủ trần NPC và kẻ xâm nhập, **cho chính tài khoản đang gọi**.

    Đây là công cụ thử, và nó chỉ tồn tại vì đường thật cố ý CHẬM: nhịp mặc định
    là hai mươi phút cho NPC và một giờ cho kẻ xâm nhập, mà một tài khoản mới thì
    lần đọc đầu chỉ đặt mốc chứ không sinh ai. Không có nút này thì mỗi lần sửa
    một dòng trong hoạt cảnh chiến đấu là hai mươi phút chờ.

    Ba tính chất giữ cho nó không thành một cửa hậu:

    * **Chỉ cho chính mình.** Không nhận `user_id`, nên không ai gọi kẻ xâm nhập
      vào bản đồ của người khác.
    * **Vẫn tôn trọng trần.** Gọi mười lần cũng chỉ ra bốn người.
    * **Đi qua đúng `_spawn` của đường thật**, nên thứ hiện ra là thứ thật —
      cùng bộ chọn nội dung, cùng số bước, cùng mức thưởng.

    `require_role("admin")` chứ không `editor`: đây là quyền vận hành, cùng ranh
    giới mà cả tệp này đã vẽ.
    """
    # `ensure_pet` chứ không tự dựng hàng: `pet_state.species` là NOT NULL và
    # loài mặc định là dữ liệu, không phải hằng số ở đây.
    pet, _owned = ensure_pet(db, admin.id)
    rows = encounters.fill_now(db, user_id=admin.id, pet=pet)
    db.commit()
    return {
        "npc": sum(1 for row in rows if row.kind == "npc"),
        "intruder": sum(1 for row in rows if row.kind == "intruder"),
    }
