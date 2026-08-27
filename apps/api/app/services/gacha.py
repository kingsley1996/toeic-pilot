"""Mở trứng: quay ở MÁY CHỦ, trả bằng ruby (ADR-010 §6, ADR-011).

Quay ở client là để người dùng tự quyết định mình nhận được gì — chỉ cần mở
devtools, và kết quả thì đi thẳng vào một bộ sưu tập vĩnh viễn. Nên toàn bộ phép
quay nằm ở đây; trình duyệt chỉ *diễn hoạt* thứ đã xảy ra.

Ba thứ trong tệp này hỏng im lặng nếu làm khác:

- **Tiêu phải đi qua `ruby.spend`**, vì đó là chỗ duy nhất có khoá tư vấn. Một
  đường tiêu viết thẳng bằng một hàng âm sẽ chạy đúng trong mọi lần thử tay và
  hỏng đúng vào ngày có hai người bấm cùng lúc (ADR-011 §5).
- **Tỉ lệ in ra màn hình phải tính từ CÙNG bảng trọng số mà phép quay dùng.** Hai
  phép tính là hai cơ hội để màn hình nói một đằng và máy làm một nẻo — và với
  một sản phẩm học cho học sinh, đó là chuyện không được phép xảy ra.
- **Bộ đếm an ủi chỉ về 0 khi thật sự ra hạng hiếm**, kể cả khi chính nó ép ra.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pet import (
    EGG_DEFAULTS,
    RARE_TIERS,
    EggSetting,
    PetOwned,
    PetSpecies,
    PetState,
)
from app.services import ruby
from app.services.pet_species import all_species


def settings_row(db: Session) -> EggSetting:
    """Hàng cấu hình duy nhất, gieo từ bộ mặc định nếu chưa có.

    Cùng khuôn `progression_config.settings_row`, kể cả hệ quả: xoá hàng đi không
    phải cách tắt gacha — lần đọc sau gieo lại. Muốn đóng gacha thì tắt hết loài.
    """
    row = db.get(EggSetting, 1)
    if row is None:
        row = EggSetting(id=1, **EGG_DEFAULTS)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Hai request đầu tiên sau một lần triển khai cùng đọc bảng rỗng và
            # cùng gieo; người thua chỉ cần đọc lại. Cùng cuộc đua đã bắt được ở
            # `ruby.rules`.
            db.rollback()
            row = db.get(EggSetting, 1)
            assert row is not None
        else:
            db.refresh(row)
    return row


@dataclass(frozen=True)
class Chance:
    """Một dòng của bảng tỉ lệ, đúng như nó sẽ hiện trên màn hình."""

    code: str
    label: str
    tile: int
    tier: str
    weight: int
    percent: float


def chances(db: Session) -> list[Chance]:
    """Tỉ lệ từng loài, chuẩn hoá từ trọng số của các loài ĐANG BẬT.

    Chuẩn hoá thay vì lưu phần trăm: phần trăm phải cộng lại đúng 100, nên tắt
    một loài biến cả bảng thành sai và người sửa phải chỉnh tay từng hàng. Ở đây
    tắt một loài chỉ làm phần của nó chia lại cho những loài còn lại, và con số
    trên màn hình vẫn là con số máy dùng.
    """
    rows = [row for row in all_species(db) if row.drop_weight > 0]
    total = sum(row.drop_weight for row in rows)
    return [
        Chance(
            code=row.code,
            label=row.label,
            tile=row.tile,
            tier=row.tier,
            weight=row.drop_weight,
            percent=(row.drop_weight / total * 100) if total else 0.0,
        )
        for row in rows
    ]


@dataclass(frozen=True)
class Hatched:
    """Kết quả một lần mở trứng."""

    species: PetSpecies
    duplicate: bool
    refund: int
    balance: int
    rolls_since_rare: int
    forced_rare: bool
    """Quả này ra hạng hiếm vì bộ đếm an ủi đã đầy, chứ không vì may.

    Nói ra trên màn hình: một phần thưởng đến từ luật thì người chơi hiểu luật,
    còn giấu đi thì bộ đếm chỉ là một con số không giải thích được điều gì.
    """


class NoSpeciesAvailable(Exception):
    """Không loài nào đang bật. Admin tắt hết là một cấu hình hợp lệ, không phải lỗi."""


def _pick(pool: list[PetSpecies], rng: random.Random) -> PetSpecies:
    """Rút một loài theo trọng số. `random.choices` chứ không tự cộng dồn tay."""
    return rng.choices(pool, weights=[row.drop_weight for row in pool], k=1)[0]


def open_egg(
    db: Session,
    *,
    user_id: uuid.UUID,
    state: PetState,
    rng: random.Random | None = None,
) -> Hatched:
    """Trừ ruby, quay, ghi vào bộ sưu tập. Ném `ruby.NotEnoughRuby` nếu thiếu tiền.

    Nhận `state` (góc thú cưng) chứ không nhận con đang nuôi: quả trứng không
    liên quan gì tới con nào đang được nuôi, và bộ đếm an ủi là của NGƯỜI CHƠI.

    `rng` là tham số chứ không đọc thẳng module `random`, cùng lý do `srs.review`
    nhận `now`: một phép quay không lặp lại được thì không có bài kiểm nào nói
    được điều gì về tỉ lệ hay về bộ đếm an ủi.

    Không `commit`: đường gọi (route) mới là chỗ quyết định ranh giới giao dịch,
    và khoá tư vấn trong `ruby.spend` chỉ nhả lúc đó. Trứng và khoản ruby phải
    sống chết cùng nhau — trừ tiền rồi rollback phần quay là mất tiền không nhận
    được gì.
    """
    picker = rng or random.SystemRandom()
    pool = [row for row in all_species(db) if row.drop_weight > 0]
    if not pool:
        raise NoSpeciesAvailable

    config = settings_row(db)
    balance = ruby.spend(
        db,
        user_id=user_id,
        source_type="egg",
        source_id=uuid.uuid4(),
        amount=config.ruby_cost,
    )
    # `source_id` là một uuid MỚI mỗi lần, không phải một khoá tất định: mở trứng
    # lần thứ hai là một sự kiện khác, không phải cùng một sự kiện được ghi lại.
    # Đây là chỗ khác hẳn các nguồn KIẾM, nơi khoá duy nhất chính là thứ chống
    # cày.

    forced = state.rolls_since_rare >= config.pity_rolls
    if forced:
        rare_pool = [row for row in pool if row.tier in RARE_TIERS]
        # Không có loài hiếm nào đang bật thì bộ đếm không ép được gì; quay bình
        # thường còn hơn ném lỗi vào mặt người vừa trả tiền.
        species = _pick(rare_pool, picker) if rare_pool else _pick(pool, picker)
        forced = species.tier in RARE_TIERS
    else:
        species = _pick(pool, picker)

    if species.tier in RARE_TIERS:
        state.rolls_since_rare = 0
    else:
        state.rolls_since_rare += 1

    owned = db.get(PetOwned, (user_id, species.code))
    duplicate = owned is not None
    if owned is None:
        db.add(PetOwned(user_id=user_id, species=species.code))
    else:
        owned.copies += 1

    refund = 0
    if duplicate and config.duplicate_refund > 0:
        # Trùng thì hoàn một phần bằng chính ruby, không phải bằng một loại
        # "mảnh" riêng. Mảnh chỉ có nghĩa khi có chỗ tiêu, và một tài nguyên
        # không tiêu được là một con số người chơi không làm gì được với nó.
        # Hoàn NHỎ HƠN giá trứng (ràng buộc ở tầng database), nếu không thì mở
        # trùng liên tục là một cỗ máy in ruby.
        refund = ruby.earn(
            db,
            user_id=user_id,
            source_type="egg_refund",
            source_id=uuid.uuid4(),
            amount=config.duplicate_refund,
        )
        balance += refund

    return Hatched(
        species=species,
        duplicate=duplicate,
        refund=refund,
        balance=balance,
        rolls_since_rare=state.rolls_since_rare,
        forced_rare=forced,
    )


def collection(db: Session, user_id: uuid.UUID) -> list[PetOwned]:
    """Những loài đã có, mới nhất trước."""
    return list(
        db.scalars(
            select(PetOwned)
            .where(PetOwned.user_id == user_id)
            .order_by(PetOwned.obtained_at.desc(), PetOwned.species)
        )
    )
