"""Sinh ra, hết hạn, và trả thưởng cho một cuộc chạm mặt (ADR-012).

**Sinh ra lúc ĐỌC, và đó là điều kiện tồn tại của cả tính năng.** Không có đồng
hồ nào chạy khi người dùng vắng mặt: mở bảng thú cưng ra thì máy chủ mới quyết
định có ai xuất hiện không. Hệ quả là **không thể bỏ lỡ một thứ chưa từng có** —
không NPC nào sinh ra lúc ba giờ sáng rồi hết hạn trước khi người ta thức dậy.

Bỏ ràng buộc ấy đi là biến một lời mời thành một cuộc hẹn, và một cuộc hẹn bị lỡ
là mất mát — đúng thứ mà ADR-010 §11 và ADR-011 §9 đều từ chối.

Ba việc, theo đúng thứ tự này, và thứ tự có lý do:

1. **Hết hạn trước.** Nếu sinh trước thì một cuộc vừa hết hạn vẫn chiếm chỗ và
   lần đọc này không sinh được gì.
2. **Đầy chỗ thì thôi.** Mỗi loại tối đa `MAX_PER_KIND` cuộc cùng lúc, đếm
   RIÊNG từng loại — xem ghi chú ở hằng số ấy.
3. **Chưa tới giờ hẹn thì thôi.** Giờ hẹn chốt từ lần trước, không bốc lại ở mỗi
   lần đọc.

**Một cuộc mới không bao giờ đẩy một cuộc đang diễn ra đi.** Cái đang chờ chỉ
biến mất khi hết hạn hoặc khi làm xong; hàm này không xoá gì để lấy chỗ. Nếu
không thì một người đang gõ dở câu trả lời sẽ thấy đề bài đổi dưới tay mình, và
công sức của họ biến mất vì một cái đồng hồ ở đâu đó vừa điểm.
"""

from __future__ import annotations

import math
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dictation import DictationItem
from app.models.encounter import ENCOUNTER_DEFAULTS, MAX_HINTS, Encounter, EncounterSetting
from app.models.pet import PetState
from app.models.vocabulary import VocabularyEntry, VocabularyReviewState
from app.services import ruby

# Khoảng ngẫu nhiên quanh nhịp đã cấu hình: giờ hẹn rơi vào 0,7–1,4 lần khoảng
# cách. Người dùng hỏi "xuất hiện ở các thời gian ngẫu nhiên", và đây là chỗ
# ngẫu nhiên ấy sống — chốt MỘT LẦN cho lần sau, chứ không bốc lại mỗi lần đọc.
JITTER_LOW = 0.7
JITTER_HIGH = 1.4

"""Tỉ lệ nhiệm vụ rơi vào dạng chép chính tả.

Một phần tư, không phải một nửa: kho từ vựng dày gấp gần mười lần kho câu chép
chính tả (303 so với 35), nên chia đều sẽ làm người học gặp lại cùng một câu
nghe nhiều lần trong tuần — và lúc đó nhiệm vụ dạy thuộc lòng câu đó chứ không
dạy nghe.
"""
DICTATION_SHARE = 0.25

"""Bao nhiêu cuộc mỗi loại được cùng tồn tại.

Đếm **riêng từng loại**, không phải một trần chung: một trần chung 4 sẽ để bốn
NPC lấp kín bản đồ và kẻ xâm nhập — thứ hiếm hơn hẳn và là chỗ hoạt cảnh chiến
đấu sống — không bao giờ có chỗ mà xuất hiện.

Hai chứ không phải một, vì bản trước chỉ cho một cuộc mỗi lúc và điều đó khiến
một cuộc bị bỏ dở chặn đứng cả làn: người học mở thẻ, thấy câu khó, để đó, và
mười phút sau vẫn đúng câu ấy. Hai chứ không phải năm, vì mỗi vị khách là một
lời mời, và năm lời mời cùng lúc thì người ta làm cái dễ nhất rồi bỏ hết phần
còn lại — cả năm cùng mất giá.
"""
MAX_PER_KIND = 2

"""Nhiệm vụ hồi phục sống cả ngày, khác hẳn mười phút của một vị khách.

Đồng hồ ngắn của NPC là thứ biến một lời mời thành một khoảnh khắc (ADR-012 §1).
Nhưng đây không phải lời mời — nó là lối DUY NHẤT ra khỏi trạng thái ốm bằng một
bước, và một lối ra hết hạn giữa chừng thì con thú kẹt lại tới lần đọc sau. Cho
nó cả ngày, và nó tự biến mất khi con thú đã khoẻ.
"""
RESCUE_LIFE_SECONDS = 24 * 60 * 60

__all__ = [
    "MAX_HINTS",
    "MAX_PER_KIND",
    "fill_now",
    "hint_for",
    "pick_target",
    "reward",
    "settings_row",
    "sync",
]


def hint_for(word: str, used: int) -> str:
    """Từ cần gõ, che một phần — càng xin thì hở ra càng nhiều.

    Lần thứ nhất mở **một phần tư** số chữ, lần thứ hai mở **một nửa**. Không mở
    một chữ mỗi lần: với một từ mười chữ thì hai lần gợi ý chỉ ra hai chữ, tức là
    không gỡ được gì và cái nút thành trang trí. Và không mở quá một nửa, vì phần
    còn phải nhớ chính là thứ phân biệt một bài kiểm với một ô điền sẵn.

    Chỗ chưa mở in thành dấu chấm giữa dòng, nên **độ dài của từ cũng lộ ra** —
    đó là chủ ý: biết từ cần gõ dài mấy chữ là nửa phần giá trị của một gợi ý.

    `used` là số lần ĐÃ xin TRƯỚC lần này, nên lần xin đầu tiên truyền vào 0.
    Hàm thuần, không kẹp `used` theo trần: trần là việc của đường ghi, còn ở đây
    kẹp im lặng sẽ giấu mất một lỗi gọi sai.
    """
    letters = len(word)
    share = 0.25 if used <= 0 else 0.5
    shown = max(1, min(letters, math.ceil(letters * share)))
    return word[:shown] + "·" * (letters - shown)


def settings_row(db: Session) -> EncounterSetting:
    """Hàng cấu hình duy nhất, gieo từ bộ mặc định nếu chưa có.

    Gieo trong SAVEPOINT và nuốt va chạm, đúng bài học mà `tests/test_ruby_race.py`
    đã dạy: hai request đầu tiên sau một lần triển khai cùng đọc bảng rỗng và cùng
    gieo, và người thua vỡ khoá chính — một lượt học hỏng vì một cuộc đua trên
    bảng cấu hình.
    """
    row = db.get(EncounterSetting, 1)
    if row is not None:
        return row
    try:
        with db.begin_nested():
            db.add(EncounterSetting(id=1, **ENCOUNTER_DEFAULTS))
    except IntegrityError:
        pass
    else:
        db.commit()
    found = db.get(EncounterSetting, 1)
    assert found is not None
    return found


def _schedule(rng: random.Random, now: datetime, gap_seconds: int) -> datetime:
    return now + timedelta(seconds=gap_seconds * rng.uniform(JITTER_LOW, JITTER_HIGH))


def _pick_vocabulary(db: Session, user_id: uuid.UUID, rng: random.Random) -> uuid.UUID | None:
    """Một từ ĐANG ĐẾN HẠN của chính người này, hoặc một từ chưa gặp bao giờ.

    Ưu tiên từ đến hạn vì nhiệm vụ phải là *việc học thật*, không phải một câu đố
    lấy lệ: làm nó xong thì lịch ôn nhích đúng như khi ôn ở màn từ vựng. Hết từ
    đến hạn thì lấy từ chưa gặp — người mới không có gì "đến hạn" nhưng vẫn có
    hàng trăm từ để học, cùng lập luận `_reviewable` của daily task đã dùng.

    Trả `None` khi kho rỗng; người gọi hiểu là "lần này không sinh ai cả".
    """
    now = datetime.now(UTC)
    published = select(VocabularyEntry.id).where(VocabularyEntry.status == "published")

    due = list(
        db.scalars(
            select(VocabularyReviewState.entry_id)
            .where(
                VocabularyReviewState.user_id == user_id,
                VocabularyReviewState.due_at <= now,
                VocabularyReviewState.entry_id.in_(published),
            )
            .limit(50)
        )
    )
    if due:
        return rng.choice(due)

    seen = select(VocabularyReviewState.entry_id).where(VocabularyReviewState.user_id == user_id)
    fresh = list(db.scalars(published.where(VocabularyEntry.id.notin_(seen)).limit(50)))
    return rng.choice(fresh) if fresh else None


def _pick_dictation(db: Session, rng: random.Random) -> uuid.UUID | None:
    """Một câu chép chính tả đã xuất bản và CÓ BẢN THU.

    Không có bản thu thì không nghe được, và một nhiệm vụ nghe-chép mà không có
    gì để nghe là một nhiệm vụ không làm được — hàng dữ liệu vẫn hợp lệ, chỉ
    người mở thẻ ra mới biết.
    """
    rows = list(
        db.scalars(
            select(DictationItem.id)
            .where(
                DictationItem.status == "published",
                DictationItem.audio_asset_id.is_not(None),
            )
            .limit(80)
        )
    )
    return rng.choice(rows) if rows else None


def pick_target(
    db: Session, user_id: uuid.UUID, task_kind: str, rng: random.Random
) -> uuid.UUID | None:
    """Mục tiêu cho một bước, theo dạng bài.

    Tách ra vì kẻ xâm nhập cần bước SAU một mục tiêu KHÁC: ba bước cùng một từ
    thì bước hai và ba chỉ là gõ lại câu trả lời vừa nhớ, và cả cuộc chạm mặt
    biến thành một cái nút bấm ba lần.
    """
    if task_kind == "dictation":
        return _pick_dictation(db, rng)
    return _pick_vocabulary(db, user_id, rng)


def sync(
    db: Session,
    *,
    user_id: uuid.UUID,
    pet: PetState,
    sick: bool = False,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[Encounter]:
    """Dọn cuộc đã hết hạn, sinh thêm nếu tới giờ và còn chỗ. Trả MỌI cuộc đang chờ.

    Không `commit`: đường gọi quyết định ranh giới giao dịch, cùng luật với
    `progression.award` và `gacha.open_eggs`.

    `now` và `rng` là tham số chứ không đọc thẳng đồng hồ với module `random`,
    cùng lý do `srs.review` nhận `now`: một luật sinh phụ thuộc đồng hồ và may
    rủi thì không bài kiểm nào nói được gì về nó — mà đây lại đúng là chỗ duy
    nhất có thể phá ràng buộc "không bỏ lỡ được thứ chưa từng có".
    """
    at = now or datetime.now(UTC)
    picker = rng or random.SystemRandom()
    config = settings_row(db)

    # 1. Hết hạn trước khi sinh.
    #
    #    KHÔNG hẹn lại giờ ở đây, khác bản một-cuộc-một-lúc. Lúc ấy phải hẹn lại
    #    để "bỏ lỡ" không thành có lợi; giờ thì mỗi lần SINH đã tự hẹn lần sau,
    #    nên nhịp được giữ bởi chính phép sinh. Hẹn lại thêm ở đây chỉ còn là
    #    phạt người ta vì đã lờ một lời mời — đúng thứ ADR-012 §4 từ chối.
    # Thứ tự CHỐT, không để database tự chọn. Giao diện chỉ vẽ một dấu hiệu cho
    # mỗi loại và người mang nó là người tới trước; không có `ORDER BY` thì thứ
    # tự đổi giữa hai lần đọc và cái dấu ấy nhảy qua nhảy lại giữa hai vị khách.
    # `id` là chốt chặn cuối vì hai cuộc có thể sinh trong cùng một mili giây.
    waiting = list(
        db.scalars(
            select(Encounter)
            .where(Encounter.user_id == user_id, Encounter.state == "waiting")
            .order_by(Encounter.created_at, Encounter.id)
        )
    )
    alive: list[Encounter] = []
    for row in waiting:
        expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
        if expires <= at:
            row.state = "expired"
        else:
            alive.append(row)

    # 2. Lần đọc đầu tiên chỉ ĐẶT MỐC, không sinh ngay: một tài khoản mới không
    #    nên bị NPC nhảy vào mặt ở giây thứ nhất, trước cả khi họ hiểu cái bảng
    #    này là gì.
    if pet.next_npc_at is None:
        pet.next_npc_at = _schedule(picker, at, config.npc_gap_seconds)
    if pet.next_intruder_at is None:
        pet.next_intruder_at = _schedule(picker, at, config.intruder_gap_seconds)
    if pet.next_npc_at is None or pet.next_intruder_at is None:
        return alive

    # 2b. Con thú ỐM thì có một nhiệm vụ HỒI PHỤC, làn riêng.
    #
    #     Đây là nửa "thú xin được chú ý" của §12 tài liệu cơ chế. Bản đầu mượn
    #     làn NPC bằng cách hạ giờ hẹn xuống, và mượn thì kéo theo cả những thứ
    #     không thuộc về nó: nhịp hai mươi phút, trần hai cuộc, số bước, và mức
    #     thưởng ruby — nên cứu con thú lại thành một nguồn thu, và một lần cứu
    #     tiêu mất suất NPC của người học.
    #
    #     Làn riêng nên KHÔNG có giờ hẹn: nó sinh theo trạng thái, không theo
    #     đồng hồ. ADR-012 §1 vẫn nguyên — vẫn sinh lúc đọc, vẫn không có gì
    #     chạy lúc vắng mặt, và một con thú ốm lúc người ta vắng mặt thì đơn giản
    #     là chưa có nhiệm vụ nào cho tới khi họ mở bảng ra.
    if sick and not any(row.kind == "rescue" for row in alive):
        made = _spawn(db, user_id=user_id, kind="rescue", at=at, config=config, rng=picker)
        if made is not None:
            alive.append(made)
    elif not sick:
        # Khoẻ lại rồi thì dọn nhiệm vụ hồi phục đang treo: nó thuộc về một trạng
        # thái không còn nữa, và để lại thì nó là một câu hỏi lơ lửng không ai
        # biết vì sao có.
        for row in alive:
            if row.kind == "rescue":
                row.state = "expired"
        alive = [row for row in alive if row.kind != "rescue"]

    # 3. Mỗi loại một làn riêng, xét kẻ xâm nhập trước: nó hiếm hơn nhiều, nên
    #    một lần lỡ nhịp của nó tốn hàng giờ, còn của NPC thì tốn vài phút.
    for kind in ("intruder", "npc"):
        due_at = _remembered(pet, kind)
        if due_at is None or due_at > at:
            continue
        if sum(1 for row in alive if row.kind == kind) >= MAX_PER_KIND:
            # Đầy chỗ. Lùi một nhịp NGẮN chứ không lùi cả một nhịp đầy: chỗ sẽ
            # trống ngay khi một cuộc hết hạn, và bắt người ta đợi thêm hai mươi
            # phút nữa sau đó là phạt cho việc bản đồ vừa đông.
            #
            # Nhưng cũng không sinh ngay lúc có chỗ: như thế thì hết hạn một
            # cuộc lại là cách gọi cuộc mới tới nhanh hơn.
            _remember(pet, kind, at + timedelta(seconds=max(60, _gap_for(config, kind) // 4)))
            continue
        made = _spawn(db, user_id=user_id, kind=kind, at=at, config=config, rng=picker)
        if made is None:
            # Không có nội dung để giao. Lùi một nhịp ngắn rồi thử lại, chứ không
            # thử lại ở mọi lần đọc: kho rỗng thì mỗi lần mở bảng sẽ là một lượt
            # quét vô ích.
            _remember(pet, kind, at + timedelta(seconds=max(60, _gap_for(config, kind) // 4)))
            continue
        _remember(pet, kind, _schedule(picker, at, _gap_for(config, kind)))
        alive.append(made)
    return alive


def fill_now(
    db: Session,
    *,
    user_id: uuid.UUID,
    pet: PetState,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[Encounter]:
    """Sinh cho đủ trần MỖI LOẠI ngay lập tức. Chỉ dùng để thử tính năng.

    Đi qua đúng `_spawn` mà đường thật dùng, nên thứ hiện ra là thứ thật: cùng
    bộ chọn nội dung, cùng số bước, cùng mức thưởng chốt lúc sinh. Một đường sinh
    riêng cho việc thử sẽ dựng ra những cuộc chạm mặt mà đường thật không bao giờ
    tạo được, và lúc đó thử xong cũng không biết mình vừa thử cái gì.

    **Vẫn tôn trọng trần**, và đó là chỗ nó khác một nút "sinh thêm một cuộc":
    gọi mười lần cũng chỉ ra bốn người, nên nó không dùng được để lách nhịp.

    Giờ hẹn của làn cũng được dời như một lần sinh bình thường: bỏ qua thì ngay
    sau khi thử xong, làn ấy sẽ nhả thêm một cuộc nữa vào giây kế tiếp.
    """
    at = now or datetime.now(UTC)
    picker = rng or random.SystemRandom()
    config = settings_row(db)
    alive = list(
        db.scalars(
            select(Encounter).where(Encounter.user_id == user_id, Encounter.state == "waiting")
        )
    )
    for kind in ("npc", "intruder"):
        while sum(1 for row in alive if row.kind == kind) < MAX_PER_KIND:
            made = _spawn(db, user_id=user_id, kind=kind, at=at, config=config, rng=picker)
            if made is None:
                break  # kho rỗng cho loại này
            alive.append(made)
            _remember(pet, kind, _schedule(picker, at, _gap_for(config, kind)))
    return alive


def _gap_for(config: EncounterSetting, kind: str) -> int:
    return config.intruder_gap_seconds if kind == "intruder" else config.npc_gap_seconds


def _remembered(pet: PetState, kind: str) -> datetime | None:
    stamp = pet.next_intruder_at if kind == "intruder" else pet.next_npc_at
    if stamp is None:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def _remember(pet: PetState, kind: str, when: datetime) -> None:
    if kind == "intruder":
        pet.next_intruder_at = when
    else:
        pet.next_npc_at = when


def _spawn(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: str,
    at: datetime,
    config: EncounterSetting,
    rng: random.Random,
) -> Encounter | None:
    """Dựng một cuộc chạm mặt, hoặc `None` nếu không có nội dung để giao.

    Hai dạng: TỪ VỰNG và CHÉP CHÍNH TẢ. Trắc nghiệm chưa mở — kho chỉ có 55 câu,
    nên một người học chăm gặp lại câu cũ trong vài ngày và nhiệm vụ sẽ dạy thuộc
    lòng đáp án chứ không dạy tiếng Anh (ADR-012 §8.3). Dạng bài mở theo độ dày
    của kho, không theo thứ tự dễ code.

    Từ vựng chiếm phần lớn có chủ ý: kho từ dày gấp gần mười lần kho câu chép
    chính tả, nên rải đều hai dạng sẽ làm người học gặp lại cùng một câu nghe
    nhiều lần trong tuần.
    """
    # Hồi phục chỉ giao TỪ VỰNG. Chép chính tả là gõ lại trọn một câu nghe được
    # — nặng hơn hẳn một câu chọn nghĩa, và đây là lối ra khỏi một trạng thái
    # chứ không phải một bài để thử sức. Bắt gõ cả câu lúc con thú đang nằm bẹp
    # là dựng thêm một bức tường trước cái cửa.
    if kind == "rescue":
        task_kind = "vocabulary"
    else:
        task_kind = "dictation" if rng.random() < DICTATION_SHARE else "vocabulary"
    target = pick_target(db, user_id, task_kind, rng)
    if target is None and kind != "rescue":
        # Kho của dạng vừa bốc đang rỗng — thử dạng kia trước khi bỏ cuộc. Hồi
        # phục thì KHÔNG đổi sang chép chính tả: thà không có nhiệm vụ (bảng tự
        # nói ra đường cho ăn) còn hơn đưa ra đúng dạng vừa loại đi.
        task_kind = "vocabulary" if task_kind == "dictation" else "dictation"
        target = pick_target(db, user_id, task_kind, rng)
    if target is None:
        return None

    intruder = kind == "intruder"
    rescue = kind == "rescue"
    row = Encounter(
        user_id=user_id,
        kind=kind,
        task_kind=task_kind,
        target_id=target,
        # Hồi phục đúng MỘT câu. Nó không phải một cuộc chạm mặt để chơi, nó là
        # lối ra khỏi một trạng thái — bắt làm ba bước lúc con thú đang nằm bẹp
        # là dựng một cái cổng, không phải một lối ra.
        steps_total=config.intruder_steps if intruder else 1,
        steps_done=0,
        # Chốt mức thưởng NGAY LÚC SINH: hạ mức giữa lúc một NPC đang đứng chờ
        # không được đổi lời hứa đã hiện trên màn hình.
        #
        # Hồi phục KHÔNG trả ruby: phần thưởng của nó là con thú đứng dậy được.
        # Trả thêm tiền thì bỏ bê hoá ra là một nguồn thu, và lúc ấy cái trạng
        # thái này thôi là chuyện đáng tránh.
        reward_ruby=0 if rescue else (config.intruder_reward if intruder else config.npc_reward),
        state="waiting",
        # Không hết hạn theo đồng hồ ngắn: một lời mời bỏ lỡ thì thôi, còn một
        # lối ra bỏ lỡ thì con thú kẹt lại. Cho nó cả ngày.
        expires_at=at
        + timedelta(
            seconds=RESCUE_LIFE_SECONDS
            if rescue
            else (config.intruder_life_seconds if intruder else config.npc_life_seconds)
        ),
    )
    db.add(row)
    db.flush()
    return row


def reward(db: Session, encounter: Encounter) -> int:
    """Trả thưởng cho một cuộc vừa xong. Trả về số ruby thực sự vào ví.

    `source_id` là chính `encounter.id`, nên khoá duy nhất
    `(user, source_type, source_id)` tự lo chuyện trả hai lần — không có đoạn
    `if` nào phải nhớ viết, và một request lặp không sinh thêm đồng nào.
    """
    return ruby.earn(
        db,
        user_id=encounter.user_id,
        source_type="encounter",
        source_id=encounter.id,
        amount=encounter.reward_ruby,
    )
