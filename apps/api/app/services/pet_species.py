"""Đọc danh sách loài, gieo mặc định nếu bảng còn trống.

Tách khỏi `services/pet.py` vì hai tệp trả lời hai câu khác nhau: kia là số học
thuần không cần database, còn đây thì cần. Trộn lại sẽ kéo một `Session` vào
tệp mà cả giá trị của nó là chạy được ngoài database.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pet import DEFAULT_PET_SPECIES, PetSpecies


def all_species(db: Session, *, include_disabled: bool = False) -> list[PetSpecies]:
    """Mọi loài, theo thứ tự hiển thị. Gieo mặc định ở lần đọc đầu.

    **Bảng rỗng nghĩa là "chưa từng cấu hình", không phải "cố ý để trống"** —
    cùng tính chất với `frame_tier`, và cùng hệ quả: xoá hết mọi loài thì lần
    đọc sau gieo lại cả bảng. Muốn bỏ một loài thì TẮT nó.
    """
    order = (PetSpecies.position, PetSpecies.code)
    rows = list(db.scalars(select(PetSpecies).order_by(*order)))
    if not rows:
        for spec in DEFAULT_PET_SPECIES:
            db.add(PetSpecies(**spec))
        try:
            db.commit()
        except IntegrityError:
            # Hai request đầu tiên sau một lần triển khai cùng đọc bảng rỗng và
            # cùng gieo; người thua vỡ khoá chính và mất nguyên một lượt học vì
            # một cuộc đua trên bảng cấu hình. Chỉ cần đọc lại — cùng cuộc đua đã
            # bắt được ở `ruby.rules`, và cùng cách chữa mà `gacha.settings_row`,
            # `progression` và `encounters` đều đang dùng.
            #
            # `pet_species` là bảng CUỐI CÙNG trong nhóm gieo lười còn thiếu chốt
            # này, và nó lại nằm trên đường đọc nóng nhất của cả góc thú cưng:
            # `ensure_pet` gọi nó ở mỗi lần mở bảng.
            db.rollback()
        rows = list(db.scalars(select(PetSpecies).order_by(*order)))
    return rows if include_disabled else [row for row in rows if row.enabled]


def row_for(db: Session, code: str) -> PetSpecies | None:
    """Hàng của một mã loài, kể cả loài đã tắt, hoặc rơi về con đầu danh sách.

    Đọc cả hàng đã tắt có chủ ý: tắt một loài phải làm nó biến khỏi gacha, không
    được làm con thú của người đang nuôi nó biến thành ô trống.

    Trả về CẢ HÀNG chứ không riêng ô, vì bây giờ có hai thứ cần tra cùng lúc —
    ô để vẽ và hạng hiếm để tô vòng sáng dưới chân. Hai lần tra cho hai cột của
    cùng một hàng là hai lần đi database cho một câu hỏi.
    """
    row = db.get(PetSpecies, code)
    if row is not None:
        return row
    # Mã mồ côi — loài đã bị xoá hẳn. Rơi về con đầu danh sách thay vì vẽ một ô
    # trống: một con thú lạ vẫn giải thích được, một khoảng trống thì không.
    fallback = all_species(db)
    return fallback[0] if fallback else None


def tile_for(db: Session, code: str) -> int:
    """Ô của một mã loài. Bọc `row_for` cho những chỗ chỉ cần vẽ."""
    row = row_for(db, code)
    return row.tile if row is not None else 0
