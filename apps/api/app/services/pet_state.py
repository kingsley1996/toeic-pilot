"""Trạng thái con thú: đọc, dựng, suy ra nhu cầu, và trao XP.

**Ở service chứ không ở route, vì cả hai chiều đều cần nó.** `routes/pet.py` đã
nhập `record_dictation_attempt` từ luồng dictation — góc thú cưng giao bài chính
tả cho các cuộc chạm mặt — và từ khi việc học nuôi ngược lại con thú, luồng học
cũng cần gọi sang. Để hai hàm này nằm trong route thì hai chiều ấy khép thành
một vòng import, và `ruff` lẫn `mypy` đều không thấy: cả hai đọc mã chứ không
chạy import, nên lỗi chỉ nổ lúc khởi động.

Khác `services/pet.py` ở đúng một chỗ và đó là ranh giới: tệp kia là số học
thuần, không session, không model. Tệp này là nơi những phép tính ấy gặp
database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PetOwned, PetState, User
from app.services import pet as needs_service
from app.services.profile import ensure_profile
from app.services.progression import local_today

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
    return state, own_pet(db, user_id, state.species)


def own_pet(db: Session, user_id: uuid.UUID, species: str) -> PetOwned:
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


def now() -> datetime:
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


def current_needs(pet: PetOwned, at: datetime) -> needs_service.Needs:
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


def award_xp(
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


@dataclass(frozen=True)
class StudyReward:
    """Thứ con thú vừa NHẬN ĐƯỢC THẬT, để giao diện khỏi phải đoán.

    Trần XP ngày và trần 1.0 của tinh thần đều có thể cắt bớt phần thưởng, nên
    con số hiện trên màn phải là con số đã ghi xuống — không phải con số trong
    bảng. Một cái toast báo "+8 XP" trong ngày đã kịch trần là một lời nói dối
    nhỏ mà không ai kiểm được.
    """

    xp: int
    mood: Decimal


def reward_study(db: Session, user_id: uuid.UUID, source: str) -> StudyReward | None:
    """Một lượt học vừa xong: con thú vui lên và nhận XP.

    **Đây là sợi dây nối việc học với con thú**, và trước đó nó không tồn tại:
    XP của thú chỉ đến từ mấy cái nút chăm sóc và các cuộc chạm mặt, còn ruby thì
    đến từ việc học — nên học chăm chỉ làm đầy bộ sưu tập mà không đụng gì tới
    con thú đang đứng đó. Cả `planning/docs/toeic_pilot_tamagotchi_mechanics.md`
    §24 lẫn ba nguyên tắc đầu của nó nói cùng một câu: hành động học tập PHẢI là
    hành động nuôi thú, nếu không góc thú cưng là một trò chơi riêng nằm cạnh.

    **Không bao giờ ném.** Nó chạy trên đường nộp bài của người học, và một lỗi ở
    lớp gamification không được phép làm hỏng thứ họ vừa làm — cùng luật mà mấy
    lượt cấp XP quanh đây đang theo bằng `try/except`.

    **Không idempotent, và không cần.** Ruby dùng khoá uuid5 vì nó là tiền; ở đây
    trần XP ngày và mức trần 1.0 của tinh thần đã chặn mọi lượt cộng thừa.
    """
    amount = needs_service.XP_PER_STUDY.get(source)
    lift = needs_service.MOOD_PER_STUDY.get(source)
    if amount is None or lift is None:
        return None
    try:
        # Nhận `user_id` chứ không nhận `User`: chỗ gọi ở luồng ôn từ vựng chỉ có
        # id trong tay, và bắt nó nạp `User` lên chỉ để truyền xuống đây là bắt
        # đường nóng nhất của việc học trả giá cho một lớp gamification.
        user = db.get(User, user_id)
        if user is None:
            return None
        at = now()
        _state, pet = ensure_pet(db, user_id)
        before_needs = current_needs(pet, at)
        after = needs_service.cheer(before_needs, lift)
        pet.fullness = after.fullness
        pet.energy = after.energy
        pet.mood = after.mood
        pet.needs_at = at
        before_xp = pet.xp
        award_xp(db, pet, user, amount, at)
        # Chênh lệch THẬT, không phải `amount` và `lift`: trần XP ngày và mức
        # trần 1.0 của tinh thần đều có thể đã cắt bớt. Một cái toast báo "+8 XP"
        # trong ngày đã kịch trần là lời nói dối nhỏ mà không ai kiểm được.
        return StudyReward(xp=pet.xp - before_xp, mood=after.mood - before_needs.mood)
    except Exception:  # noqa: BLE001 — xem docstring: không làm hỏng bài nộp
        return None
