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
from app.models import PetOwned, PetState, User
from app.schemas.pet import (
    EggChance,
    EggPublic,
    EggResult,
    PetActionRequest,
    PetMove,
    PetNeeds,
    PetOwnedPublic,
    PetPublic,
    PetSwitch,
)
from app.services import gacha, ruby
from app.services import pet as needs_service
from app.services.pet_species import all_species, row_for
from app.services.profile import ensure_profile
from app.services.progression import local_today

router = APIRouter(prefix="/pet", tags=["pet"])

# Loài mặc định khi một người mở góc thú cưng lần đầu. Là một MÃ, không phải chỉ
# số ô: bảng `pet_species` (lát 7) sẽ dịch mã sang ô, và ngày đổi bộ sprite thì
# chỉ bảng đó đổi.
DEFAULT_SPECIES = "cat"


def ensure_pet(db: Session, user_id: uuid.UUID) -> tuple[PetState, PetOwned]:
    """Góc thú cưng của người này, cùng CON ĐANG NUÔI. Dựng nếu chưa có.

    Trả về cả hai vì mọi đường ghi đều cần cả hai: chỉ số nằm trên con
    (`PetOwned`), còn trần XP ngày và bộ đếm gacha nằm trên góc (`PetState`).
    Trả về một cái rồi để người gọi tự tra cái kia là chỗ ai đó sẽ quên tra.

    Dựng NGAY LÚC ĐỌC chứ không lúc đăng ký, khác `user_profile`. Hồ sơ được
    `get_current_user` đọc trên mọi request nên nó phải luôn tồn tại; con thú thì
    chỉ có nghĩa với người đã mở góc này, và tạo sẵn cho 821 tài khoản để chờ vài
    người bấm vào là trả tiền cho một thứ chưa ai xin.
    """
    state = db.get(PetState, user_id)
    if state is None:
        state = PetState(user_id=user_id, species=DEFAULT_SPECIES)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state, _own(db, user_id, state.species)


def _own(db: Session, user_id: uuid.UUID, species: str) -> PetOwned:
    """Hàng của con này trong tủ, dựng nếu chưa có.

    Con đầu tiên không đến từ một quả trứng, nên không có gì ghi nó vào
    `pet_owned` — và hậu quả là một cái tủ rỗng trong khi trên bản đồ đang có một
    con mèo, rồi đổi sang con khác là mất luôn con mèo vì "không sở hữu".

    Ghi ở đường ĐỌC chứ không chỉ lúc tạo, vì những tài khoản có từ trước lát 8
    đã có `pet_state` mà chưa có hàng nào ở `pet_owned`. Một lần `get` theo khoá
    chính mỗi lần đọc con thú là cái giá rẻ hơn hẳn một migration đi vá dữ liệu
    cũ, và nó tự đúng với cả tài khoản mới lẫn cũ.
    """
    owned = db.get(PetOwned, (user_id, species))
    if owned is None:
        owned = PetOwned(user_id=user_id, species=species)
        db.add(owned)
        db.commit()
        db.refresh(owned)
    return owned


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


def _current_needs(pet: PetOwned, at: datetime) -> needs_service.Needs:
    """Nhu cầu **suy ra ở thời điểm `at`**, không phải con số đang nằm trong cột.

    Cột lưu ảnh chụp tại `needs_at`; giá trị bây giờ là ảnh chụp đó trừ dần theo
    quãng thời gian đã trôi. Đây là cùng một luật với chuỗi ngày ở
    `profile_stats.py` và tiến độ ở `StoryProgress`: suy ra ở mỗi lần đọc, không
    nuôi một bộ đếm chạy song song với lịch sử.
    """
    stored = needs_service.Needs(fullness=pet.fullness, energy=pet.energy, mood=pet.mood)
    return needs_service.decay(stored, (at - _aware(pet.needs_at)).total_seconds())


def _as_public(
    db: Session,
    pet: PetOwned,
    now: needs_service.Needs,
    at: datetime,
) -> PetPublic:
    """Hình dạng gửi ra ngoài KHÔNG đổi khi chỉ số dời sang từng con.

    Nó vẫn là "con thú đang nuôi, ngay bây giờ" — chỉ khác ở chỗ mọi con số lấy
    từ hàng của chính con đó, kể cả `xp_today`. Nhờ vậy frontend không phải sửa
    gì.
    """
    progress = needs_service.level_progress(pet.xp)
    row = row_for(db, pet.species)
    return PetPublic(
        species=pet.species,
        tile=row.tile if row is not None else 0,
        tier=row.tier if row is not None else "common",  # type: ignore[arg-type]
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
        hatched_at=pet.obtained_at,
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
    _state, pet = ensure_pet(db, current_user.id)
    at = _now()
    # Đọc KHÔNG ghi. Trừ dần rồi lưu lại ở mỗi lần đọc sẽ biến một GET thành một
    # lệnh ghi trên đường nóng, và không được gì: mốc cộng ảnh chụp đã đủ để suy
    # ra giá trị bây giờ ở bất cứ lúc nào. Chỉ hành động mới ghi.
    return _as_public(db, pet, _current_needs(pet, at), at)


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
    _state, pet = ensure_pet(db, current_user.id)
    # Ghi lên CON, không lên góc: mỗi con nhớ chỗ của riêng nó, nên đổi qua con
    # khác rồi quay lại thì nó vẫn đứng chỗ cũ.
    pet.tile_x = body.tile_x
    pet.tile_y = body.tile_y
    pet.facing = body.facing
    db.commit()
    at = _now()
    return _as_public(db, pet, _current_needs(pet, at), at)


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
    _state, pet = ensure_pet(db, current_user.id)
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
    return _as_public(db, pet, after, at)


def _award(
    db: Session,
    pet: PetOwned,
    user: User,
    action: needs_service.PetAction,
    at: datetime,
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
    # Trần VÀ xp đều trên con. Để trần ở góc thì con vừa nở không nhận nổi một
    # điểm nào cho tới hôm sau, vì con trước đó đã dùng hết trần của ngày.
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


# --- gacha trứng (ADR-010 lát 8) --------------------------------------------


def _chance_public(chance: gacha.Chance) -> EggChance:
    return EggChance(
        code=chance.code,
        label=chance.label,
        tile=chance.tile,
        tier=chance.tier,
        # Một chữ số thập phân: "3.4%" đọc được, "3.389830508474576%" thì không,
        # và làm tròn ở máy chủ giữ cho hai màn hình khác nhau không in ra hai
        # con số khác nhau cho cùng một tỉ lệ.
        percent=round(chance.percent, 1),
    )


@router.get("/eggs", response_model=EggPublic)
def read_egg(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EggPublic:
    """Giá trứng, số dư, bộ đếm an ủi và BẢNG TỈ LỆ.

    Tỉ lệ đi kèm chứ không nằm ở một endpoint riêng: nó phải hiện trên chính màn
    hình có cái nút, và một lần đọc thứ hai là một cơ hội để hai con số lệch nhau
    (ADR-010 §6.4).
    """
    state, _pet = ensure_pet(db, current_user.id)
    config = gacha.settings_row(db)
    rows = gacha.chances(db)
    # Cùng lý do như ở ví ruby: bù TRƯỚC khi đọc, nếu không màn trứng in ra số
    # dư cũ và cái nút "Mở trứng" mờ đi trong khi tiền đã có.
    if ruby.top_up_admin(db, user_id=current_user.id, role=current_user.role):
        db.commit()
    balance = ruby.balance(db, current_user.id)
    return EggPublic(
        ruby_cost=config.ruby_cost,
        balance=balance,
        can_open=bool(rows) and balance >= config.ruby_cost,
        pity_rolls=config.pity_rolls,
        rolls_since_rare=state.rolls_since_rare,
        duplicate_refund=config.duplicate_refund,
        owned=[row.species for row in gacha.collection(db, current_user.id)],
        chances=[_chance_public(row) for row in rows],
    )


@router.post("/eggs/open", response_model=EggResult)
def open_egg(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EggResult:
    """Mở một quả trứng. Quay ở MÁY CHỦ (ADR-010 §6.1).

    Thiếu ruby trả **409**, không phải 400: yêu cầu hoàn toàn hợp lệ, chỉ là
    trạng thái hiện tại không cho phép — cùng hình dạng với việc từ chối cho con
    thú ăn khi nó đang no. Và lời từ chối nói ra CON SỐ, để giao diện lặp lại
    được thay vì tự đoán.

    Không có tham số nào cả. Một hạng trứng duy nhất nên không có gì để chọn, và
    một endpoint nhận `tier` từ client là một endpoint nhận giá từ client.
    """
    state, _pet = ensure_pet(db, current_user.id)
    # Bù cả ở đường TIÊU, không chỉ ở đường đọc: một admin mở liên tiếp sẽ cạn
    # giữa chừng, và lời từ chối "cần 25 ruby" giữa một phiên thử là đúng chỗ
    # người ta kết luận nhầm rằng tính năng hỏng.
    ruby.top_up_admin(db, user_id=current_user.id, role=current_user.role)
    try:
        result = gacha.open_egg(db, user_id=current_user.id, state=state)
    except gacha.NoSpeciesAvailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chưa có loài nào để nở. Thử lại sau nhé.",
        ) from None
    except ruby.NotEnoughRuby as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cần {exc.needed} ruby, hiện có {exc.available}.",
        ) from None

    db.commit()
    return EggResult(
        species=EggChance(
            code=result.species.code,
            label=result.species.label,
            tile=result.species.tile,
            tier=result.species.tier,
            # Tỉ lệ của chính con vừa ra, để màn hình nói được "3.4% đấy".
            percent=next(
                (
                    round(row.percent, 1)
                    for row in gacha.chances(db)
                    if row.code == result.species.code
                ),
                0.0,
            ),
        ),
        duplicate=result.duplicate,
        refund=result.refund,
        balance=result.balance,
        rolls_since_rare=result.rolls_since_rare,
        forced_rare=result.forced_rare,
    )


@router.patch("", response_model=PetPublic)
def switch_pet(
    body: PetSwitch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PetPublic:
    """Đổi con đang nuôi sang một con ĐÃ CÓ trong bộ sưu tập.

    **Mỗi con giữ chỉ số của riêng nó** — đói, sức, vui, XP, level và cả chỗ
    đứng. Đổi qua đổi lại không mất gì và cũng không mượn được gì: con vừa chọn
    ra đúng như lúc nó được cất đi, còn con vừa cất giữ nguyên trạng thái của nó
    và tiếp tục đói theo đồng hồ thật.

    Bản đầu làm ngược lại — một bộ chỉ số dùng chung cho cả góc, đổi con thì con
    mới thừa hưởng độ no của con cũ. Nghe như "không mất tiến độ", nhưng nó nói
    rằng mọi con là cùng một con mang hình khác nhau, và cả bộ sưu tập mất nghĩa.

    Loài chưa sở hữu trả **404, không phải 403**: nói "bạn không có quyền" với
    một con vật là sai nghĩa, và 404 cũng không tiết lộ loài nào tồn tại trong
    bảng cho một người chưa mở được nó.

    Loài đã bị TẮT vẫn đổi được nếu đã sở hữu — tắt một loài là gỡ nó khỏi
    gacha, không phải tịch thu của người đã có (cùng luật `tile_for` đang giữ).
    """
    state, _pet = ensure_pet(db, current_user.id)
    if db.get(PetOwned, (current_user.id, body.species)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có con này trong bộ sưu tập.",
        )
    state.species = body.species
    db.commit()
    at = _now()
    # Con vừa chọn mang chỉ số CỦA CHÍNH NÓ ra — kể cả chỗ nó đang đứng và mốc
    # đói của nó, nên một con bị bỏ quên ba ngày sẽ đói đúng ba ngày.
    pet = _own(db, current_user.id, body.species)
    return _as_public(db, pet, _current_needs(pet, at), at)


@router.get("/collection", response_model=list[PetOwnedPublic])
def read_collection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PetOwnedPublic]:
    """Bộ sưu tập. Mảng trần: nó bị chặn trên bởi số loài có trong `pet_species`.

    Đọc cả loài đã TẮT, cùng lý do `tile_for` đọc chúng: tắt một loài phải làm nó
    biến khỏi gacha, không được làm con thú người ta đã có biến mất khỏi tủ.
    """
    species = {row.code: row for row in all_species(db, include_disabled=True)}
    out: list[PetOwnedPublic] = []
    for owned in gacha.collection(db, current_user.id):
        row = species.get(owned.species)
        if row is None:
            # Mã mồ côi — loài bị xoá hẳn. Bỏ qua chứ không dựng một ô trống:
            # một khoảng trống trong tủ đọc như dữ liệu hỏng.
            continue
        out.append(
            PetOwnedPublic(
                code=row.code,
                label=row.label,
                tile=row.tile,
                tier=row.tier,
                copies=owned.copies,
                obtained_at=owned.obtained_at,
            )
        )
    return out
