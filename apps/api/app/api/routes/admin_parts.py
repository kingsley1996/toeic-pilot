"""Quản trị CHIẾN THUẬT Part 1–7: body markdown và video chiến thuật.

Nguồn soạn SƠ CẤP của body từng là markdown trong `apps/web/content/parts/`
qua `scripts/sync-parts.sh` — một chiều, và đòi deploy để đổi một chữ. Trang
này cho biên tập viên sửa THẲNG trong DB, cùng lý do grammar lesson nằm trong
DB: "sửa một trang chiến thuật không đáng một lần deploy". Markdown gốc còn
nguyên vai trò hạt giống lần đầu; chạy sync sau khi sửa tay là GHI ĐÈ nội dung
trên admin — script in cảnh báo này.

Video đi đúng luồng bốn bước của ADR-006 (khuôn `SPEC-GRAMMAR-VIDEO`), vùng
khoá riêng `part-video/`: byte PUT thẳng object store, `verify()` hỏi lại nhà
cung cấp trước khi ghi khoá.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core import rate_limit
from app.core.database import get_db
from app.core.media import (
    PART_VIDEO_KEY_PREFIX,
    part_video_storage_key_for,
    public_video_url,
    upload_source_hash,
)
from app.core.storage import StorageError, get_driver
from app.models import PartTactics, User
from app.schemas.admin import PartTacticsAdmin, PartTacticsBody
from app.schemas.media import UploadTicket, VideoConfirm, VideoTicketRequest

router = APIRouter(prefix="/admin", tags=["admin"])

can_edit = require_role("editor", "admin")

# Hạn mức RIÊNG và chặt hơn mọi khu khác: một part chỉ một video, nhu cầu thật
# là vài lần mỗi đợt soạn. Rộng hơn thế chỉ mời dùng bucket làm ổ đĩa.
VIDEO_TICKET_QUOTA = rate_limit.Quota(limit=5, window_seconds=600)


def _check_part(part: int) -> None:
    if not 1 <= part <= 7:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")


def _tactics(db: Session, part: int) -> PartTactics:
    row = db.get(PartTactics, part)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tactics not found")
    return row


def _tactics_admin(row: PartTactics) -> PartTacticsAdmin:
    return PartTacticsAdmin(
        part=row.part,
        body=row.body,
        video_url=public_video_url(row.video_storage_key) if row.video_storage_key else None,
        video_duration_s=row.video_duration_s,
    )


@router.get("/parts/{part}/tactics", response_model=PartTacticsAdmin)
def get_tactics(
    part: int, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> PartTacticsAdmin:
    """Một trang chiến thuật cho màn soạn. Part chưa từng sync là trang RỖNG
    chứ không 404 — màn soạn phải mở được rồi `PUT` tạo hàng."""
    _check_part(part)
    row = db.get(PartTactics, part)
    if row is None:
        return PartTacticsAdmin(part=part, body="")
    return _tactics_admin(row)


@router.put("/parts/{part}/tactics", response_model=PartTacticsAdmin)
def update_tactics(
    part: int, body: PartTacticsBody, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> PartTacticsAdmin:
    """Upsert body — lần đầu soạn part chưa từng sync là TẠO hàng, không 404."""
    _check_part(part)
    row = db.get(PartTactics, part)
    if row is None:
        row = PartTactics(part=part, body=body.body)
        db.add(row)
    else:
        row.body = body.body
    db.commit()
    db.refresh(row)
    return _tactics_admin(row)


@router.post(
    "/parts/{part}/tactics/video/ticket",
    response_model=UploadTicket,
    dependencies=[
        Depends(can_edit),
        Depends(rate_limit.rate_limit("part-video-ticket", VIDEO_TICKET_QUOTA)),
    ],
)
def part_video_ticket(
    part: int, body: VideoTicketRequest, db: Session = Depends(get_db)
) -> UploadTicket:
    """Vé upload video chiến thuật — trình duyệt PUT thẳng object store."""
    _check_part(part)
    storage_key = part_video_storage_key_for(upload_source_hash(str(uuid.uuid4())), ext=body.ext)
    return UploadTicket.of(get_driver("video").ticket(storage_key))


@router.put("/parts/{part}/tactics/video", response_model=PartTacticsAdmin)
def part_video_confirm(
    part: int,
    body: VideoConfirm,
    db: Session = Depends(get_db),
    _: User = Depends(can_edit),
) -> PartTacticsAdmin:
    """Gắn video vừa tải lên. Hai kiểm, cùng khuôn `avatar_confirm`: khoá phải
    nằm dưới `part-video/` (không thì có thể trỏ vào vùng media khác và lệnh dọn
    mồ côi sau này xoá mất thứ đang dùng), và `verify()` hỏi lại nhà cung cấp —
    thiếu bước này là đường ghi một chuỗi tuỳ ý, người học sẽ thấy player vỡ."""
    _check_part(part)
    if not body.storage_key.startswith(f"{PART_VIDEO_KEY_PREFIX}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Khoá không thuộc vùng video chiến thuật",
        )
    try:
        get_driver("video").verify(body.storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None
    row = _tactics(db, part)
    row.video_storage_key = body.storage_key
    row.video_duration_s = body.duration_s
    db.commit()
    db.refresh(row)
    return _tactics_admin(row)


@router.delete("/parts/{part}/tactics/video", response_model=PartTacticsAdmin)
def part_video_remove(
    part: int, db: Session = Depends(get_db), _: User = Depends(can_edit)
) -> PartTacticsAdmin:
    """Gỡ video khỏi part. Idempotent. File để MỒ CÔI cho đường dọn dẹp media —
    xoá đồng nghĩa với một request chờ dịch vụ ngoài."""
    _check_part(part)
    row = _tactics(db, part)
    row.video_storage_key = None
    row.video_duration_s = None
    db.commit()
    db.refresh(row)
    return _tactics_admin(row)
