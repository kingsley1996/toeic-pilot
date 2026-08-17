"""Nền lưới động: một đường đọc công khai, một đường ghi cho quản trị."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.models import BackdropSetting, User
from app.models.appearance import BACKDROP_COLORS, BACKDROP_DEFAULTS
from app.schemas.appearance import BackdropPublic, BackdropUpdate

router = APIRouter(tags=["appearance"])


def _row(db: Session) -> BackdropSetting:
    """Hàng cấu hình duy nhất, tạo nếu chưa có.

    Migration `027` đã chèn sẵn hàng id=1, nên nhánh tạo mới ở đây chỉ chạy
    trên database dựng bằng `create_all` — tức là bộ test và môi trường dev.
    Giữ lại vì thiếu nó thì mọi test chạm tới endpoint này phải tự seed.
    """
    row = db.get(BackdropSetting, 1)
    if row is None:
        row = BackdropSetting(id=1, **BACKDROP_DEFAULTS)
        db.add(row)
        db.commit()
    return row


def _public(row: BackdropSetting) -> BackdropPublic:
    return BackdropPublic(
        spark_count=row.spark_count,
        twinkle_count=row.twinkle_count,
        color=row.color,
        speed_percent=row.speed_percent,
        enabled=row.enabled,
    )


@router.get("/backdrop", response_model=BackdropPublic)
def read_backdrop(db: Session = Depends(get_db)) -> BackdropPublic:
    """KHÔNG đòi đăng nhập: nền này hiện cả trên trang giới thiệu.

    Bắt xác thực ở đây sẽ làm khách chưa đăng nhập rơi về nền mặc định, nên cấu
    hình quản trị viên vừa đặt lại không áp dụng cho đúng nhóm người nhìn thấy
    trang nhiều nhất. Cấu hình này không phải bí mật — nó mô tả thứ ai cũng
    nhìn thấy.
    """
    return _public(_row(db))


@router.put(
    "/admin/backdrop",
    response_model=BackdropPublic,
    dependencies=[Depends(require_role("editor", "admin"))],
)
def update_backdrop(
    body: BackdropUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BackdropPublic:
    """`require_role` là DEPENDENCY, không phải một lệnh kiểm trong thân hàm.

    Kiểm trong thân hàm là thứ người ta quên chép sang route kế tiếp, và kiểu
    hỏng của nó là một endpoint quản trị mở cho mọi học viên.
    """
    if body.color not in BACKDROP_COLORS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"color must be one of {list(BACKDROP_COLORS)}",
        )

    row = _row(db)
    row.spark_count = body.spark_count
    row.twinkle_count = body.twinkle_count
    row.color = body.color
    row.speed_percent = body.speed_percent
    row.enabled = body.enabled
    row.updated_by = current_user.id
    db.commit()
    return _public(row)
