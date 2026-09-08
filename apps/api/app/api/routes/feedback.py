"""Góp ý của người học — gửi và xem lại của chính mình."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.media import FEEDBACK_KEY_PREFIX, feedback_storage_key_for, upload_source_hash
from app.core.rate_limit import Quota, rate_limit
from app.core.storage import StorageError, get_driver
from app.models.feedback import PENDING_CAP, Feedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackPublic, FeedbackReward
from app.schemas.media import UploadTicket, UploadTicketRequest
from app.services.ruby import rules

router = APIRouter(tags=["feedback"])

# Chặt hơn hạn mức của khu nội dung, cùng lý do với avatar: một góp ý cần nhiều
# nhất một ảnh, nên nhu cầu thật là vài vé mỗi phiên. Rộng hơn thế chỉ mở cửa
# cho việc mượn tài khoản Cloudinary của ta làm nơi chứa file.
SCREENSHOT_QUOTA = Quota(limit=10, window_seconds=60 * 10)
CREATE_QUOTA = Quota(limit=20, window_seconds=60 * 10)


def public(feedback: Feedback) -> FeedbackPublic:
    """Bản gửi ra ngoài, kèm URL ảnh nếu có.

    URL sinh ở đây chứ không để frontend ghép: nhà cung cấp là một biến cấu
    hình, và Cloudinary còn chèn thêm một tiền tố thư mục vào `public_url` —
    ghép tay ở phía kia là dựng một chỗ thứ hai phải nhớ điều đó, và nó sẽ 404
    im lặng khi ai đó đổi nhà cung cấp.
    """
    out = FeedbackPublic.model_validate(feedback)
    driver = get_driver("image")
    out.image_urls = [driver.public_url(key) for key in feedback.screenshot_keys or []]
    return out


@router.post(
    "/feedback/screenshot/ticket",
    response_model=UploadTicket,
    dependencies=[Depends(rate_limit("feedback-ticket", SCREENSHOT_QUOTA))],
)
def screenshot_ticket(
    body: UploadTicketRequest,
    current_user: User = Depends(get_current_user),
) -> UploadTicket:
    """Vé để trình duyệt tự tải ảnh lên, không đi qua API (ADR-006 §2.3)."""
    storage_key = feedback_storage_key_for(upload_source_hash(str(uuid.uuid4())), ext=body.ext)
    ticket = get_driver("image").ticket(storage_key)
    return UploadTicket.of(ticket)


@router.post(
    "/feedback",
    response_model=FeedbackPublic,
    dependencies=[Depends(rate_limit("feedback-create", CREATE_QUOTA))],
)
def create_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackPublic:
    """Gửi góp ý. Tạo LÀ bước xác nhận ảnh — không có bước thứ ba.

    Avatar tách `ticket` và `confirm` vì hồ sơ đã tồn tại sẵn và ảnh chỉ gắn
    vào. Ở đây hàng góp ý chưa có gì để gắn vào cho tới lúc gửi, nên gộp lại là
    đúng: một lần ghi, và ảnh không bao giờ trỏ tới một hàng chưa tồn tại.
    """
    if not body.description.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mô tả không được để trống"
        )

    # Kiểm TỪNG khoá, và hai phép kiểm cho mỗi khoá — bỏ phép nào cũng hỏng im
    # lặng. Thiếu kiểm tiền tố thì đây là đường ghi một chuỗi tuỳ ý: trỏ được
    # vào ảnh nội dung, và lệnh dọn ảnh mồ côi sau này sẽ xoá mất thứ đang dùng.
    # Thiếu `verify` thì admin mở góp ý ra thấy ảnh vỡ.
    #
    # Trùng khoá bị gộp lại: gửi cùng một ảnh ba lần không được tính là ba.
    keys = list(dict.fromkeys(body.screenshot_keys))
    driver = get_driver("image")
    for key in keys:
        if not key.startswith(f"{FEEDBACK_KEY_PREFIX}/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Khoá không thuộc vùng góp ý"
            )
        try:
            driver.verify(key)
        except StorageError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chưa thấy file trên kho lưu trữ: {error}",
            ) from None

    # Trần đếm theo `pending`, không theo tổng: người góp ý đều đặn và được xử
    # lý đều đặn không bao giờ chạm trần, còn người rải hàng loạt dừng ngay —
    # và trần tự mở ra khi admin làm việc, không cần ai gỡ tay.
    pending = db.execute(
        select(func.count())
        .select_from(Feedback)
        .where(Feedback.user_id == current_user.id, Feedback.status == "pending")
    ).scalar_one()
    if pending >= PENDING_CAP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bạn đang có {pending} góp ý chờ xử lý. Đợi được duyệt rồi gửi tiếp nhé.",
        )

    feedback = Feedback(
        user_id=current_user.id,
        type=body.type,
        description=body.description.strip(),
        screenshot_keys=keys or None,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return public(feedback)


@router.get("/feedback/mine", response_model=list[FeedbackPublic])
def my_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FeedbackPublic]:
    """Góp ý của chính mình, mới nhất trước.

    Mảng trần chứ không `Page[T]`: số góp ý một người gửi có trần cứng ở
    `PENDING_CAP` cho phần chờ, và phần đã xử lý cũng không phải thứ tăng theo
    thời gian dùng app — đây là nhóm (A) của `schemas/common.py`.
    """
    rows = db.execute(
        select(Feedback)
        .where(Feedback.user_id == current_user.id)
        .order_by(Feedback.created_at.desc())
        .limit(50)
    ).scalars()
    return [public(row) for row in rows]


@router.get("/feedback/reward", response_model=FeedbackReward)
def reward(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FeedbackReward:
    """Mức ruby cho một góp ý được duyệt, đọc từ `ruby_rule`.

    Phục vụ đúng một việc: để giao diện KHÔNG viết cứng con số. Mức thưởng là
    một hàng admin sửa được ở `/admin/ruby` mà không cần deploy, nên một số viết
    thẳng vào modal sẽ lệch ngay lần chỉnh đầu tiên — và lệch theo hướng tệ
    nhất, là hứa nhiều hơn thứ thật sự trao.

    `rules()` chỉ trả hàng ĐANG BẬT, nên tắt hàng ấy đi thì `amount` về 0 và
    giao diện bỏ luôn câu hứa. Một lời hứa thưởng khi phần thưởng đã tắt còn tệ
    hơn không hứa gì.
    """
    row = next((r for r in rules(db) if r.source_type == "feedback_reward"), None)
    return FeedbackReward(amount=row.amount if row else 0)
