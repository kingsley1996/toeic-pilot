"""Đọc danh sách loài, gieo mặc định nếu bảng còn trống.

Tách khỏi `services/pet.py` vì hai tệp trả lời hai câu khác nhau: kia là số học
thuần không cần database, còn đây thì cần. Trộn lại sẽ kéo một `Session` vào
tệp mà cả giá trị của nó là chạy được ngoài database.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pet import DEFAULT_PET_SPECIES, PetSpecies


def all_species(db: Session, *, include_disabled: bool = False) -> list[PetSpecies]:
    """Mọi loài, theo thứ tự hiển thị. Gieo mặc định ở lần đọc đầu.

    **Bảng rỗng nghĩa là "chưa từng cấu hình", không phải "cố ý để trống"** —
    cùng tính chất với `frame_tier`, và cùng hệ quả: xoá hết mọi loài thì lần
    đọc sau gieo lại đủ mười hai. Muốn bỏ một loài thì TẮT nó.
    """
    rows = list(db.scalars(select(PetSpecies).order_by(PetSpecies.position, PetSpecies.code)))
    if not rows:
        for spec in DEFAULT_PET_SPECIES:
            db.add(PetSpecies(**spec))
        db.commit()
        rows = list(db.scalars(select(PetSpecies).order_by(PetSpecies.position, PetSpecies.code)))
    return rows if include_disabled else [row for row in rows if row.enabled]


def tile_for(db: Session, code: str) -> int:
    """Ô của một mã loài, kể cả loài đã tắt.

    Đọc cả hàng đã tắt có chủ ý: tắt một loài phải làm nó biến khỏi gacha, không
    được làm con thú của người đang nuôi nó biến thành ô trống.
    """
    row = db.get(PetSpecies, code)
    if row is not None:
        return row.tile
    # Mã mồ côi — loài đã bị xoá hẳn. Rơi về con đầu danh sách thay vì vẽ một ô
    # trống: một con thú lạ vẫn giải thích được, một khoảng trống thì không.
    fallback = all_species(db)
    return fallback[0].tile if fallback else 0
