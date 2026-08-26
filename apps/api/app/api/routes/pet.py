"""Góc thú cưng: trạng thái con thú đang nuôi (ADR-010).

Router riêng chứ không nhét vào `profile`: phần này sẽ mọc thêm hành động (cho
ăn, chọc, đi dạo), bộ sưu tập và gacha, còn `profile` trả lời một câu khác hẳn —
người này là ai và họ đặt gì.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import PetState, User
from app.schemas.pet import PetMove, PetNeeds, PetPublic

router = APIRouter(prefix="/pet", tags=["pet"])

# Loài mặc định khi một người mở góc thú cưng lần đầu. Là một MÃ, không phải chỉ
# số ô: bảng `pet_species` (lát 7) sẽ dịch mã sang ô, và ngày đổi bộ sprite thì
# chỉ bảng đó đổi.
DEFAULT_SPECIES = "cat"


def ensure_pet(db: Session, user_id: uuid.UUID) -> PetState:
    """Lấy con thú của người này, dựng một con nếu chưa có.

    Dựng NGAY LÚC ĐỌC chứ không lúc đăng ký, khác `user_profile`. Hồ sơ được
    `get_current_user` đọc trên mọi request nên nó phải luôn tồn tại; con thú thì
    chỉ có nghĩa với người đã mở góc này, và tạo sẵn cho 821 tài khoản để chờ vài
    người bấm vào là trả tiền cho một thứ chưa ai xin.
    """
    pet = db.get(PetState, user_id)
    if pet is None:
        pet = PetState(user_id=user_id, species=DEFAULT_SPECIES)
        db.add(pet)
        db.commit()
        db.refresh(pet)
    return pet


@router.get("", response_model=PetPublic)
def read_pet(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> PetPublic:
    """Trạng thái con thú, kèm MỐC THỜI GIAN của nhu cầu.

    Chưa trừ dần ở đây: phép trừ theo thời gian là lát 5. Nhưng `needs.at` đã có
    mặt từ bây giờ, vì thêm nó sau là một thay đổi hợp đồng ở đúng chỗ client đã
    kịp tin rằng ba con số kia là "bây giờ".
    """
    pet = ensure_pet(db, current_user.id)
    return PetPublic(
        species=pet.species,
        nickname=pet.nickname,
        # Chưa có bảng ngưỡng (lát 6), nên level tạm là mốc cao nhất đã đạt.
        level=pet.level_reached,
        xp=pet.xp,
        tile_x=pet.tile_x,
        tile_y=pet.tile_y,
        facing=pet.facing,
        needs=PetNeeds(
            fullness=float(pet.fullness),
            energy=float(pet.energy),
            mood=float(pet.mood),
            at=pet.needs_at,
        ),
        hatched_at=pet.hatched_at,
    )


@router.put("/position", response_model=PetPublic)
def move_pet(
    body: PetMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetPublic:
    """Ghi lại chỗ con thú vừa dừng.

    **Không kiểm ô đó có đi được không**, và đó là chủ ý. Bản đồ sống ở
    `public/pet/map.json` — một tệp tĩnh mà máy chủ không đọc và không nên đọc:
    bắt nó biết bố cục nghĩa là mỗi lần đổi bản đồ trong trình vẽ lại phải deploy
    lại API. Cái giá của việc không kiểm là một người dùng nghịch devtools có thể
    đặt con thú của CHÍNH HỌ vào giữa cái ao. Không ai khác thấy, không gì khác
    hỏng, và `nearestWalkable` ở client kéo nó ra ở lần mở sau.

    Đây là lý do khoảng hợp lệ chỉ chặn ở 0..255: đủ để không ai nhét được số âm
    hay số khổng lồ vào cột `SmallInteger`, không hơn.
    """
    pet = ensure_pet(db, current_user.id)
    pet.tile_x = body.tile_x
    pet.tile_y = body.tile_y
    pet.facing = body.facing
    db.commit()
    db.refresh(pet)
    return read_pet(db, current_user)
