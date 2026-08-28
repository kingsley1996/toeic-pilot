"""Góc thú cưng: trạng thái con thú đang nuôi (ADR-010).

Router riêng chứ không nhét vào `profile`: phần này sẽ mọc thêm hành động (cho
ăn, chọc, đi dạo), bộ sưu tập và gacha, còn `profile` trả lời một câu khác hẳn —
người này là ai và họ đặt gì.
"""

import hashlib
import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.learning import _apply_review as apply_review
from app.api.routes.learning import record_dictation_attempt
from app.core.database import get_db
from app.core.media import public_audio_url
from app.models import Encounter, PetOwned, PetState, User
from app.models.dictation import DictationItem
from app.models.encounter import MAX_HINTS
from app.models.vocabulary import VocabularyEntry
from app.schemas.pet import (
    DiffWord,
    EggBatchResult,
    EggChance,
    EggPublic,
    EggResult,
    EncounterAnswer,
    EncounterChoice,
    EncounterHint,
    EncounterPublic,
    EncounterResult,
    EncounterTask,
    PetActionRequest,
    PetMove,
    PetNeeds,
    PetOwnedPublic,
    PetPublic,
    PetSwitch,
)
from app.services import encounters, gacha, ruby
from app.services import pet as needs_service
from app.services.dictation import normalise as dictation_words
from app.services.pet_species import all_species, row_for
from app.services.profile import ensure_profile
from app.services.progression import local_today
from app.services.recall import VERDICT_CORRECT, grade_for, judge
from app.services.srs import GRADE_FORGOT, GRADE_GOOD

router = APIRouter(prefix="/pet", tags=["pet"])

# Loài mặc định khi một người mở góc thú cưng lần đầu. Là một MÃ, không phải chỉ
# số ô: bảng `pet_species` (lát 7) sẽ dịch mã sang ô, và ngày đổi bộ sprite thì
# chỉ bảng đó đổi.
DEFAULT_SPECIES = "cat"


def db_get_state(db: Session, user_id: uuid.UUID) -> PetState | None:
    """Đọc hàng góc thú cưng. Tách ra CHỈ để bài kiểm đua chèn được hàng rào vào
    đúng khe giữa "chưa có" và "dựng" — cùng kỹ thuật mà bài mua trứng dùng với
    `ruby.balance`. Không có seam này thì cuộc đua không tái tạo được, và một bài
    kiểm không tái tạo được là một bức tường xanh không khẳng định gì."""
    return db.get(PetState, user_id)


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
    state = db_get_state(db, user_id)
    if state is None:
        state = PetState(user_id=user_id, species=DEFAULT_SPECIES)
        db.add(state)
        try:
            db.commit()
        except IntegrityError:
            # LẦN MỞ BẢNG ĐẦU TIÊN bắn hai request gần như cùng lúc — `GET /pet`
            # và `GET /pet/encounters` — và cả hai đều đi qua đây. Trên một tài
            # khoản chưa có hàng nào thì cả hai cùng thấy `None` và cùng dựng;
            # người thua vỡ khoá chính và nhận 500 ngay ở lần mở góc thú cưng
            # đầu tiên của đời tài khoản đó.
            #
            # Bắt được nhờ một lượt chạy e2e đỏ ở chỗ chẳng liên quan, không
            # phải nhờ đọc mã: cuộc đua này chỉ trúng khi hai request rơi vào
            # đúng vài mili giây của nhau.
            db.rollback()
            state = db.get(PetState, user_id)
            assert state is not None
        else:
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
        try:
            db.commit()
        except IntegrityError:
            # Cùng cuộc đua với `ensure_pet`, và cùng cách chữa: hai request đầu
            # tiên cùng dựng con thú đầu tiên.
            db.rollback()
            owned = db.get(PetOwned, (user_id, species))
            assert owned is not None
        else:
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


def _asleep_seconds(pet: PetOwned, since: datetime, at: datetime) -> float:
    """Bao nhiêu giây trong khoảng `[since, at]` con này nằm ngủ.

    Giấc ngủ gần như luôn kết thúc GIỮA hai lần đọc — người dùng cho ngủ rồi đóng
    tab, và lần mở sau đã qua cả giấc lẫn một quãng thức. Nên phép tính phải cắt
    đúng chỗ mốc `sleep_until` rơi vào, chứ không hỏi "bây giờ có đang ngủ không"
    rồi áp cho cả quãng: hỏi thế thì con thú hồi sức trong lúc nó đã dậy từ lâu,
    hoặc không hồi gì trong cả giấc vừa ngủ xong.
    """
    if pet.sleep_until is None:
        return 0.0
    end = min(at, _aware(pet.sleep_until))
    return max(0.0, (end - since).total_seconds())


def is_asleep(pet: PetOwned, at: datetime) -> bool:
    return pet.sleep_until is not None and at < _aware(pet.sleep_until)


def _current_needs(pet: PetOwned, at: datetime) -> needs_service.Needs:
    """Nhu cầu **suy ra ở thời điểm `at`**, không phải con số đang nằm trong cột.

    Cột lưu ảnh chụp tại `needs_at`; giá trị bây giờ là ảnh chụp đó trừ dần theo
    quãng thời gian đã trôi. Đây là cùng một luật với chuỗi ngày ở
    `profile_stats.py` và tiến độ ở `StoryProgress`: suy ra ở mỗi lần đọc, không
    nuôi một bộ đếm chạy song song với lịch sử.
    """
    since = _aware(pet.needs_at)
    stored = needs_service.Needs(fullness=pet.fullness, energy=pet.energy, mood=pet.mood)
    return needs_service.decay(
        stored,
        (at - since).total_seconds(),
        _asleep_seconds(pet, since, at),
    )


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
        sleep_until=pet.sleep_until,
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

    # Đang ngủ thì ba hành động kia bị từ chối, KHÔNG phải tự đánh thức. Một cú
    # bấm nhầm mà xoá mất hai tiếng hồi sức là thứ người dùng không thể lường
    # trước và cũng không hoàn lại được; nút "Đánh thức" thì họ chủ động bấm.
    if body.action != "wake" and is_asleep(pet, at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Nó đang ngủ, để nó ngủ đã."
        )
    if body.action == "wake" and not is_asleep(pet, at):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nó đang thức mà.")

    reason = needs_service.refusal(body.action, now)
    if reason is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

    if body.action == "sleep":
        pet.sleep_until = at + timedelta(seconds=needs_service.SLEEP_MAX_SECONDS)
    elif body.action == "wake":
        # Chốt sổ TRƯỚC khi xoá mốc: `_current_needs` ở trên đã cộng phần sức
        # ngủ được tới `at`, và `after` bên dưới ghi nó xuống. Xoá mốc trước thì
        # cả giấc vừa rồi biến mất khỏi phép tính.
        pet.sleep_until = None

    after = needs_service.apply(body.action, now)
    pet.fullness = after.fullness
    pet.energy = after.energy
    pet.mood = after.mood
    pet.needs_at = at

    # Trao XP sau khi nhu cầu đã ghi — xem docstring của `_award`.
    _award(db, pet, current_user, needs_service.XP_PER_ACTION[body.action], at)

    db.commit()
    return _as_public(db, pet, after, at)


def _award(
    db: Session,
    pet: PetOwned,
    user: User,
    amount: int,
    at: datetime,
) -> None:
    """Trao XP cho con thú, sau khi áp trần ngày.

    Nhận SỐ ĐIỂM chứ không nhận tên hành động, vì XP giờ đến từ hai chỗ: mấy cái
    nút chăm sóc, và những cuộc chạm mặt làm xong. Tra bảng ở trong hàm thì cái
    thứ hai phải bịa ra một "hành động" không có nút nào bấm được.

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

    awarded = needs_service.grant(pet.xp_today, amount)
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


"""Số quả mở trong một lượt "mở nhiều".

Mười là con số của cả thể loại, và nó không phải hằng số cấu hình: đổi nó là đổi
cả cái nút trên màn hình lẫn câu chữ quanh nó, nên nó thuộc về sản phẩm chứ
không thuộc về bảng cấu hình. Giá thì vẫn là hàng — `egg_setting.ruby_cost` nhân
lên.
"""
EGGS_PER_BATCH = 10


@router.post("/eggs/open-ten", response_model=EggBatchResult)
def open_ten_eggs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EggBatchResult:
    """Mở mười quả trong MỘT giao dịch.

    Đường dẫn riêng chứ không phải một tham số `count` trên `/eggs/open`: hai
    lượt mở trả về hai hình dạng khác nhau (một quả và một danh sách), và một
    endpoint trả về hình dạng thay đổi theo tham số là thứ frontend phải đoán.

    Thiếu ruby trả **409** kèm CON SỐ của cả lượt, không phải giá một quả: người
    bấm "Mở 10" cần biết mình thiếu bao nhiêu cho lượt đó.
    """
    state, _pet = ensure_pet(db, current_user.id)
    ruby.top_up_admin(db, user_id=current_user.id, role=current_user.role)
    try:
        batch = gacha.open_eggs(db, user_id=current_user.id, state=state, count=EGGS_PER_BATCH)
    except gacha.NoSpeciesAvailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chưa có loài nào để nở. Thử lại sau nhé.",
        ) from None
    except ruby.NotEnoughRuby as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cần {exc.needed} ruby cho mười quả, hiện có {exc.available}.",
        ) from None

    db.commit()
    chances = {row.code: round(row.percent, 1) for row in gacha.chances(db)}
    return EggBatchResult(
        opened=[
            EggResult(
                species=EggChance(
                    code=one.species.code,
                    label=one.species.label,
                    tile=one.species.tile,
                    tier=one.species.tier,
                    percent=chances.get(one.species.code, 0.0),
                ),
                duplicate=one.duplicate,
                refund=one.refund,
                balance=one.balance,
                rolls_since_rare=one.rolls_since_rare,
                forced_rare=one.forced_rare,
            )
            for one in batch.hatched
        ],
        spent=batch.spent,
        refund=batch.refund,
        balance=batch.balance,
        rolls_since_rare=batch.rolls_since_rare,
        new_species=sum(1 for one in batch.hatched if not one.duplicate),
    )


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


# --- chạm mặt (ADR-012) -----------------------------------------------------


def _choice_key(encounter_id: uuid.UUID, entry_id: uuid.UUID) -> str:
    """Mã của một lựa chọn: băm theo (cuộc chạm mặt, mục từ).

    Băm theo cả hai chứ không chỉ mục từ, nên cùng một từ ở hai cuộc khác nhau
    mang hai mã khác nhau — không ai học thuộc được mã của đáp án đúng. Và không
    lưu gì: máy chủ tính lại đúng mã ấy cho `target_id` để đối chiếu, nên không
    có bảng phiên nào phải dọn và không có gì hết hạn sai lúc.
    """
    return hashlib.sha256(f"{encounter_id}:{entry_id}".encode()).hexdigest()[:16]


def _answer_mode(row: Encounter) -> str:
    """Gõ lại từ hay chọn nghĩa, chốt theo id nên KHÔNG đổi giữa hai lần đọc.

    Bốc lại mỗi lần đọc thì câu hỏi tự đổi dạng dưới tay người đang gõ dở — và
    nó đổi đúng vào lúc trang tự hỏi lại sau mỗi phút.
    """
    return "choice" if row.id.int % 2 else "typing"


def _vocabulary_task(db: Session, row: Encounter, entry: VocabularyEntry) -> EncounterTask:
    mode = _answer_mode(row)
    if mode == "typing":
        # Đề là NGHĨA, đáp án là từ — nên `headword` không được gửi đi. Bản đầu
        # gửi cả hai vì màn thẻ lật cần cả hai; ở đây gửi cả hai là in đáp án ra
        # ngay trên đề bài.
        return EncounterTask(
            kind="vocabulary",
            mode="typing",
            entry_id=str(entry.id),
            prompt=entry.meaning_vi,
            part_of_speech=entry.part_of_speech,
            hints_left=max(0, MAX_HINTS - row.hints_used),
        )

    # Mồi nhử lọc theo NGHĨA chứ không chỉ theo id: hai mục từ khác nhau dịch ra
    # cùng một tiếng Việt là chuyện có thật trong kho hiện tại, và khi đó màn
    # hình in hai lựa chọn giống hệt nhau mà chỉ một cái được tính đúng.
    seen = {entry.meaning_vi.strip().lower()}
    options = [EncounterChoice(key=_choice_key(row.id, entry.id), text=entry.meaning_vi)]
    pool = db.scalars(
        select(VocabularyEntry)
        .where(VocabularyEntry.status == "published", VocabularyEntry.id != entry.id)
        .order_by(func.random())
        .limit(40)
    )
    for other in pool:
        text = other.meaning_vi.strip().lower()
        if text in seen:
            continue
        seen.add(text)
        options.append(EncounterChoice(key=_choice_key(row.id, other.id), text=other.meaning_vi))
        if len(options) == 4:
            break
    # Xáo theo id cuộc chạm mặt, nên đáp án đúng không phải lúc nào cũng nằm ở
    # ô đầu — mà thứ tự vẫn y hệt sau khi tải lại trang.
    random.Random(row.id.int).shuffle(options)
    return EncounterTask(
        kind="vocabulary",
        mode="choice",
        prompt=entry.headword,
        part_of_speech=entry.part_of_speech,
        choices=options,
    )


def _task_public(db: Session, row: Encounter) -> EncounterTask:
    if row.task_kind == "vocabulary" and row.target_id is not None:
        entry = db.get(VocabularyEntry, row.target_id)
        if entry is not None:
            return _vocabulary_task(db, row, entry)
    if row.task_kind == "dictation" and row.target_id is not None:
        item = db.get(DictationItem, row.target_id)
        if item is not None and item.asset is not None:
            return EncounterTask(
                kind="dictation",
                mode="dictation",
                entry_id=str(item.id),
                audio_url=public_audio_url(item.asset.storage_key),
                word_count=len(dictation_words(item.transcript)),
            )
    # Nội dung đã bị xoá sau khi cuộc chạm mặt sinh ra. `target_id` cố ý không
    # phải khoá ngoại, nên chuyện này xảy ra được — và câu trả lời đúng là để
    # cuộc ấy hết hạn, không phải để nó nổ.
    return EncounterTask(kind=row.task_kind)  # type: ignore[arg-type]


def _encounter_public(db: Session, row: Encounter) -> EncounterPublic:
    return EncounterPublic(
        id=str(row.id),
        kind=row.kind,  # type: ignore[arg-type]
        steps_total=row.steps_total,
        steps_done=row.steps_done,
        reward_ruby=row.reward_ruby,
        expires_at=row.expires_at,
        task=_task_public(db, row),
    )


@router.get("/encounters", response_model=list[EncounterPublic])
def read_encounters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EncounterPublic]:
    """Cuộc chạm mặt đang chờ, hoặc `null`.

    **Lần đọc này CÓ GHI**, và đó là ngoại lệ có chủ ý — cùng hình dạng với
    `GET /daily-tasks`, và cùng lý do: sinh ra lúc đọc là thứ bảo đảm không ai
    bỏ lỡ được một cuộc chạm mặt sinh ra trong lúc họ đang ngủ (ADR-012 §1).
    Không có đường nào khác để giữ tính chất ấy mà không dựng một job nền, mà
    một job nền thì lại sinh ra đúng cái nó phải tránh.

    An toàn vì nhịp sinh được **hẹn trước**: gọi lại mười lần trong một giây
    không tạo ra mười cuộc, vì giờ hẹn chỉ dời khi có một cuộc thật sự sinh ra.
    """
    _state, pet = ensure_pet(db, current_user.id)
    state = db.get(PetState, current_user.id)
    assert state is not None
    rows = encounters.sync(db, user_id=current_user.id, pet=state)
    db.commit()
    # Mảng trần, không bọc `Page[T]`: số cuộc bị chặn cứng bởi miền
    # (`MAX_PER_KIND` mỗi loại, hai loại), nên đây là nhóm (A) của
    # `app/schemas/common.py` — bọc lại là bắt frontend xử lý một trường hợp
    # không thể xảy ra.
    out: list[EncounterPublic] = []
    for row in rows:
        db.refresh(row)
        out.append(_encounter_public(db, row))
    return out


@router.post("/encounters/{encounter_id}/answer", response_model=EncounterResult)
def answer_encounter(
    encounter_id: uuid.UUID,
    body: EncounterAnswer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EncounterResult:
    """Trả lời một bước, và **câu trả lời đi thẳng vào bộ chấm thật**.

    Với từ vựng, nó gọi đúng `_apply_review` mà `POST /vocabulary/{id}/review`
    gọi — nên lượt ôn này ghi vào SM-2, vào `vocabulary_review_log`, và chảy tiếp
    vào chuỗi ngày y như mọi lượt ôn khác. Nếu không, người học vừa làm bài xong
    mà lịch ôn không đổi: họ đã học, và hệ thống giả vờ như chưa.

    Đây cũng là lý do endpoint này nhận `grade` chứ không nhận "đúng/sai" —
    thang điểm là của SM-2, và một thang thứ hai ở đây là bộ chấm thứ hai.
    """
    row = db.get(Encounter, encounter_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có cuộc này")

    at = _now()
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if row.state != "waiting" or expires <= at:
        # Hết hạn ngay lúc trả lời là chuyện có thật với một đồng hồ mười phút.
        # 409 chứ không 404: cuộc ấy CÓ tồn tại, chỉ là đã qua.
        if row.state == "waiting":
            row.state = "expired"
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cuộc chạm mặt này đã kết thúc."
        )

    _state, pet_row = ensure_pet(db, current_user.id)
    profile = ensure_profile(db, current_user)
    correct = False
    diff: list[DiffWord] | None = None
    if row.task_kind == "vocabulary" and row.target_id is not None:
        entry = db.get(VocabularyEntry, row.target_id)
        if entry is not None:
            if _answer_mode(row) == "choice":
                # Chọn đúng ô nào thì so bằng mã băm, không so bằng id: id đúng
                # là thứ trình duyệt đọc được từ chính đề bài.
                correct = body.choice == _choice_key(row.id, entry.id)
                grade = GRADE_GOOD if correct else GRADE_FORGOT
            else:
                # Đi qua đúng bộ chấm của màn gõ lại từ, kể cả cái ngưỡng lỗi
                # gõ: sai một chữ cái trên một từ dài là "gõ nhầm", vào SM-2 ở
                # mức KHÓ chứ không phải mức QUÊN. Một bộ so chuỗi thứ hai ở đây
                # sẽ là chỗ hai màn hình chấm cùng một từ ra hai kết quả.
                verdict = judge(body.text, entry.headword).verdict
                correct = verdict == VERDICT_CORRECT
                grade = grade_for(verdict, easy=False)
            # Lượt ôn được GHI dù đúng hay sai, vì nó là một lượt học thật đã
            # xảy ra — chỉ có BƯỚC nhiệm vụ mới đòi trả lời đúng.
            apply_review(db, current_user.id, row.target_id, grade, profile.timezone)
    elif row.task_kind == "dictation" and row.target_id is not None:
        item = db.get(DictationItem, row.target_id)
        if item is not None:
            attempt, graded = record_dictation_attempt(db, current_user, item, body.text)
            # `is_complete`, không phải `accuracy`: gõ đủ câu rồi gõ thêm vẫn ra
            # 100%, nên lấy điểm làm cổng là trả thưởng cho một bài sai rõ ràng.
            correct = graded.is_complete
            diff = [DiffWord(op=word.op, word=word.word) for word in graded.diff]  # type: ignore[arg-type]
            del attempt

    granted = 0
    if correct:
        row.steps_done += 1
        if row.steps_done >= row.steps_total:
            row.state = "done"
            granted = encounters.reward(db, row)
            # Con thú cũng lên XP: nó vừa được người nuôi dắt đi làm một việc,
            # và với kẻ xâm nhập thì nó đứng ra đánh nhau. Đi qua đúng `_award`
            # nên trần ngày, mốc level và múi giờ người học đều là một bộ với
            # mấy cái nút chăm sóc — một đường trao XP thứ hai là chỗ trần ngày
            # đếm thiếu mà không ai thấy.
            _award(db, pet_row, current_user, needs_service.XP_PER_ENCOUNTER[row.kind], at)
        else:
            # Bước sau phải là một câu KHÁC. Ba bước cùng một từ thì bước hai và
            # ba chỉ là gõ lại đáp án vừa nhìn thấy, và cả đợt xâm nhập rút gọn
            # thành một cái nút bấm ba lần.
            nxt = encounters.pick_target(db, current_user.id, row.task_kind, random.SystemRandom())
            if nxt is not None:
                row.target_id = nxt
                # Bước sau là một từ khác, nên nó xứng đáng có phần gợi ý riêng.
                # Không đặt lại thì bước hai và ba của một đợt xâm nhập thừa
                # hưởng cái trần đã dùng hết ở bước một.
                row.hints_used = 0
    db.commit()
    db.refresh(row)

    return EncounterResult(
        correct=correct,
        steps_done=row.steps_done,
        steps_total=row.steps_total,
        done=row.state == "done",
        reward_ruby=granted,
        balance=ruby.balance(db, current_user.id),
        encounter=None if row.state != "waiting" else _encounter_public(db, row),
        word_diff=diff,
    )


@router.post("/encounters/{encounter_id}/hint", response_model=EncounterHint)
def take_hint(
    encounter_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EncounterHint:
    """Mở một phần từ cần gõ. Tối đa `MAX_HINTS` lần cho mỗi bước.

    **Trần đếm ở máy chủ**, và đó là điều kiện để cái nút này không phá chính bài
    kiểm nó đang giúp: xin đủ nhiều lần thì gợi ý in ra cả từ, và lúc đó phần
    thưởng ruby chỉ còn là một cái nút bấm nhiều lần. Một bộ đếm trong `useState`
    thì devtools đặt lại được trong hai giây.

    Chỉ dạng **gõ lại từ**. Dạng chọn nghĩa đã có sẵn bốn ô để loại trừ, và dạng
    chép chính tả thì "mở vài ký tự" của cả một câu là mở luôn đáp án.
    """
    row = db.get(Encounter, encounter_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có cuộc này")

    at = _now()
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if row.state != "waiting" or expires <= at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cuộc chạm mặt này đã kết thúc."
        )
    if row.task_kind != "vocabulary" or _answer_mode(row) != "typing" or row.target_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Nhiệm vụ này không có gợi ý."
        )
    if row.hints_used >= MAX_HINTS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hết lượt gợi ý rồi.")

    entry = db.get(VocabularyEntry, row.target_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nội dung không còn nữa.")

    hint = encounters.hint_for(entry.headword, row.hints_used)
    row.hints_used += 1
    db.commit()
    return EncounterHint(hint=hint, hints_left=max(0, MAX_HINTS - row.hints_used))
