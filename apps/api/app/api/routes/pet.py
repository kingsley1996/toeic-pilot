"""Góc thú cưng: trạng thái con thú đang nuôi (ADR-010).

Router riêng chứ không nhét vào `profile`: phần này sẽ mọc thêm hành động (cho
ăn, chọc, đi dạo), bộ sưu tập và gacha, còn `profile` trả lời một câu khác hẳn —
người này là ai và họ đặt gì.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import PetState, User
from app.schemas.pet import PetActionRequest, PetMove, PetNeeds, PetPublic
from app.services import pet as needs_service
from app.services.profile import ensure_profile
from app.services.progression import local_today

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


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(stamp: datetime) -> datetime:
    """Gắn UTC cho mốc thời gian nếu nó chưa có múi giờ.

    `DateTime(timezone=True)` không hứa điều gì giống nhau ở hai database:
    Postgres trả về mốc CÓ múi giờ, SQLite trả về mốc TRẦN. Trừ hai kiểu đó cho
    nhau ném `TypeError`, nên cùng một dòng code chạy ở production và nổ trong
    test — hoặc ngược lại, tuỳ chỗ nào được viết trước.

    Coi mốc trần là UTC là đúng chứ không phải nhân nhượng: mọi thứ ghi vào cột
    này đều đi qua `datetime.now(UTC)` hoặc `func.now()`.
    """
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


def _current_needs(pet: PetState, at: datetime) -> needs_service.Needs:
    """Nhu cầu **suy ra ở thời điểm `at`**, không phải con số đang nằm trong cột.

    Cột lưu ảnh chụp tại `needs_at`; giá trị bây giờ là ảnh chụp đó trừ dần theo
    quãng thời gian đã trôi. Đây là cùng một luật với chuỗi ngày ở
    `profile_stats.py` và tiến độ ở `StoryProgress`: suy ra ở mỗi lần đọc, không
    nuôi một bộ đếm chạy song song với lịch sử.
    """
    stored = needs_service.Needs(fullness=pet.fullness, energy=pet.energy, mood=pet.mood)
    return needs_service.decay(stored, (at - _aware(pet.needs_at)).total_seconds())


def _as_public(pet: PetState, now: needs_service.Needs, at: datetime) -> PetPublic:
    progress = needs_service.level_progress(pet.xp)
    return PetPublic(
        species=pet.species,
        nickname=pet.nickname,
        # Mốc cao nhất, không phải level vừa tính: chỉnh đường cong XP về sau
        # không được lấy mất level của con thú đã đạt tới nó.
        level=max(progress.level, pet.level_reached),
        xp=pet.xp,
        xp_into_level=progress.into_level,
        xp_for_next=progress.for_next,
        xp_today=pet.xp_today,
        daily_cap=needs_service.DAILY_XP_CAP,
        tile_x=pet.tile_x,
        tile_y=pet.tile_y,
        facing=pet.facing,
        needs=PetNeeds(
            fullness=float(now.fullness),
            energy=float(now.energy),
            mood=float(now.mood),
            at=at,
        ),
        hatched_at=pet.hatched_at,
    )


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
    at = _now()
    # Đọc KHÔNG ghi. Trừ dần rồi lưu lại ở mỗi lần đọc sẽ biến một GET thành một
    # lệnh ghi trên đường nóng, và không được gì: mốc cộng ảnh chụp đã đủ để suy
    # ra giá trị bây giờ ở bất cứ lúc nào. Chỉ hành động mới ghi.
    return _as_public(pet, _current_needs(pet, at), at)


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
    at = _now()
    return _as_public(pet, _current_needs(pet, at), at)


@router.post("/actions", response_model=PetPublic)
def act(
    body: PetActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetPublic:
    """Cho ăn, chọc, hoặc dắt đi dạo.

    **Trừ dần TRƯỚC rồi mới cộng tác động**, không ngược lại. Ngược thứ tự thì
    phần thưởng bị trừ theo quãng thời gian trước khi hành động xảy ra — cho ăn
    sau một tuần vắng mặt gần như không có tác dụng, mà con số vẫn hợp lệ nên
    không có gì báo.

    Ghi lại cả `needs_at`: từ giây này ảnh chụp mới là mốc, nếu không lần đọc kế
    tiếp sẽ trừ lại đúng quãng thời gian vừa rồi một lần nữa.

    Từ chối trả **409**, không phải 400: yêu cầu hợp lệ, chỉ là trạng thái hiện
    tại không cho phép — cùng hình dạng với việc từ chối xoá một câu dictation đã
    có người làm. Và lời từ chối nói ra ĐIỀU KIỆN, để giao diện lặp lại được
    nguyên văn thay vì tự đoán.
    """
    at = _now()
    pet = ensure_pet(db, current_user.id)
    now = _current_needs(pet, at)

    reason = needs_service.refusal(body.action, now)
    if reason is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

    after = needs_service.apply(body.action, now)
    pet.fullness = after.fullness
    pet.energy = after.energy
    pet.mood = after.mood
    pet.needs_at = at

    # Trao XP sau khi nhu cầu đã ghi — xem .
    _award(db, pet, current_user, body.action, at)

    db.commit()
    return _as_public(pet, after, at)


def _award(
    db: Session, pet: PetState, user: User, action: needs_service.PetAction, at: datetime
) -> None:
    """Trao XP cho hành động, sau khi áp trần ngày.

    **Ngày theo múi giờ NGƯỜI HỌC**, cùng định nghĩa mà chuỗi ngày và nhiệm vụ
    ngày dùng. Một định nghĩa thứ hai là chỗ trần XP và nhiệm vụ ngày nói hai
    điều khác nhau về cùng một hôm, và không có gì báo.

    **Chạm trần không đụng tới nhu cầu.** Hàm này chạy SAU khi nhu cầu đã được
    ghi, và nó không đọc lại chúng: con thú vẫn no lên dù XP đã kịch trần. Luật
    gamification không được phép đổi thứ đã thật sự xảy ra.
    """
    profile = ensure_profile(db, user)
    today = local_today(at, profile.timezone)
    if pet.xp_day != today:
        # Đặt lại lúc GHI, không phải lúc đọc: kẹp ở đường đọc sẽ biến trần thành
        # một công thức, và đổi trần sau này sẽ viết lại quá khứ.
        pet.xp_day = today
        pet.xp_today = 0

    awarded = needs_service.grant(pet.xp_today, needs_service.XP_PER_ACTION[action])
    if awarded == 0:
        return
    pet.xp_today += awarded
    pet.xp += awarded
    level = needs_service.level_from_xp(pet.xp)
    if level > pet.level_reached:
        pet.level_reached = level
