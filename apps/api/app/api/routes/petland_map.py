"""Đọc và ghi bản đồ góc thú cưng (migration 048).

Trình vẽ trước đây tải tệp về rồi người sửa commit tay. Lý do cũ vẫn đúng — bản
đồ là nội dung và nội dung thuộc về git — nhưng nó có trước khi có production,
nơi sửa một ô cỏ phải đi qua một lần deploy.

Cách dung hoà: **không có hàng nghĩa là tệp đã commit đang chạy.** Bảng chỉ là
lớp ghi đè, và giao diện nói rõ đang chạy bản nào, nên chuyện "hai nơi hai bản
đồ" không còn là chuyện thầm lặng — đó chính là điều thiết kế cũ sợ.

`GET` không cần đăng nhập: bản đồ không phải bí mật, và trang Petland tải nó
trước khi làm bất cứ việc gì khác.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models import PetlandMap, User
from app.schemas.petland_map import PetlandMapBody, PetlandMapPublic

router = APIRouter(tags=["petland"])

can_edit_map = require_role("admin")


@router.get(
    "/petland/map",
    response_model=PetlandMapPublic,
    responses={204: {"description": "Chưa ai sửa trên web; dùng bản đã commit."}},
)
def read_map(response: Response, db: Session = Depends(get_db)) -> PetlandMapPublic | Response:
    row = db.execute(select(PetlandMap).where(PetlandMap.id == 1)).scalar_one_or_none()
    if row is None:
        # 204 chứ không 404: "chưa cấu hình" là trạng thái BÌNH THƯỜNG ở đây, và
        # 404 sẽ hiện lên như một lỗi trong console của mọi lần tải trang.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return PetlandMapPublic(
        w=row.w,
        h=row.h,
        ground=row.ground,  # type: ignore[arg-type]
        objects=row.objects,  # type: ignore[arg-type]
        solid=row.solid,  # type: ignore[arg-type]
        updated_at=row.updated_at,
    )


@router.put("/admin/petland/map", response_model=PetlandMapPublic)
def save_map(
    body: PetlandMapBody,
    db: Session = Depends(get_db),
    user: User = Depends(can_edit_map),
) -> PetlandMapPublic:
    payload = body.model_dump(mode="json")
    row = db.execute(select(PetlandMap).where(PetlandMap.id == 1)).scalar_one_or_none()
    if row is None:
        row = PetlandMap(id=1)
        db.add(row)
    row.w, row.h = body.w, body.h
    row.ground = payload["ground"]
    row.objects = payload["objects"]
    row.solid = payload["solid"]
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return PetlandMapPublic(
        w=row.w,
        h=row.h,
        ground=row.ground,  # type: ignore[arg-type]
        objects=row.objects,  # type: ignore[arg-type]
        solid=row.solid,  # type: ignore[arg-type]
        updated_at=row.updated_at,
    )
