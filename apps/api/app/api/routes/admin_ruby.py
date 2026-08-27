"""Quản trị mức thưởng ruby (ADR-011 §6).

`require_role("admin")` chứ không `editor`: đặt giá cho cả nền kinh tế là quyền
VẬN HÀNH, không phải quyền biên tập nội dung. Cùng ranh giới mà
`/admin/progression` và `/admin/pet` đã vẽ.

Sửa mức thưởng không lấy lại thứ đã trao — mỗi hàng `ruby_event` giữ số ruby tại
thời điểm đó. Đó chính là tính chất khiến việc giao bảng này cho admin là an
toàn, và nó là một tính chất của SỔ CÁI: bỏ sổ cái đi thì màn hình này trở thành
một cách viết lại quá khứ.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models import RubyRule, User
from app.schemas.ruby import RubyRuleEdit, RubyRulePublic
from app.services.ruby import rules

router = APIRouter(prefix="/admin/ruby", tags=["admin"])

can_configure = require_role("admin")


def _public(row: RubyRule) -> RubyRulePublic:
    return RubyRulePublic(
        source_type=row.source_type,
        label=row.label,
        amount=row.amount,
        position=row.position,
        enabled=row.enabled,
    )


@router.get("/rules", response_model=list[RubyRulePublic])
def list_rules(
    db: Session = Depends(get_db), _: User = Depends(can_configure)
) -> list[RubyRulePublic]:
    """Cả hàng đã tắt — màn quản trị là nơi DUY NHẤT nhìn thấy chúng.

    Mảng trần chứ không `Page[T]`: bảng này bị chặn trên bởi số nguồn ruby có
    trong mã, tức là bucket (A) của `app/schemas/common.py`. Bọc phong bì cho nó
    là bắt frontend xử lý một trường hợp không thể xảy ra.
    """
    return [_public(row) for row in rules(db, include_disabled=True)]


@router.patch("/rules/{source_type}", response_model=RubyRulePublic)
def update_rule(
    source_type: str,
    body: RubyRuleEdit,
    db: Session = Depends(get_db),
    _: User = Depends(can_configure),
) -> RubyRulePublic:
    # Đọc trước khi ghi để bảng rỗng được gieo mặc định; không có bước này thì
    # lần sửa đầu tiên sau một lần triển khai sạch sẽ trả 404 cho một nguồn có
    # thật.
    rules(db, include_disabled=True)
    row = db.get(RubyRule, source_type)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ruby rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    return _public(row)
