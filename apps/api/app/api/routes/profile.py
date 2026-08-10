import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.media import (
    AVATAR_KEY_PREFIX,
    avatar_storage_key_for,
    upload_source_hash,
)
from app.core.rate_limit import Quota, rate_limit
from app.core.storage import StorageError, get_driver
from app.models.user import User
from app.schemas.media import UploadTicket, UploadTicketRequest
from app.schemas.profile import (
    AvatarConfirm,
    LearningStats,
    UserProfilePublic,
    UserProfileUpdate,
)
from app.services.profile import ensure_profile, profile_public
from app.services.profile_stats import gather_stats

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=UserProfilePublic)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Hồ sơ của CHÍNH người đang đăng nhập.

    Không có biến thể nhận id: hồ sơ ở đây là dữ liệu riêng — mục tiêu điểm, ngày
    thi, thời gian học mỗi ngày — chứ không phải trang cá nhân công khai. Một
    endpoint `/profile/{user_id}` sẽ phải trả lời câu hỏi "ai được xem của ai",
    và câu hỏi đó chưa có lý do tồn tại.
    """
    return profile_public(ensure_profile(db, current_user))


@router.patch("/profile", response_model=UserProfilePublic)
def update_profile(
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Cập nhật một phần hồ sơ.

    `exclude_unset=True` là điểm mấu chốt, không phải chi tiết: nó giữ được khác
    biệt giữa "không gửi trường này" và "gửi null để xoá trường này". Nếu gộp
    bằng `giá_trị or giá_trị_cũ` thì thao tác xoá ngày thi sẽ im lặng không làm
    gì cả, và người dùng chỉ phát hiện ra khi tải lại trang.
    """
    changes = body.model_dump(exclude_unset=True)
    profile = ensure_profile(db, current_user)

    for field, value in changes.items():
        # `timezone` và `locale` là NOT NULL. Gửi null cho chúng là yêu cầu vô
        # nghĩa chứ không phải yêu cầu xoá, nên bỏ qua thay vì để database ném
        # IntegrityError thành 500.
        if value is None and field in {"timezone", "locale"}:
            continue
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile_public(profile)


@router.get("/profile/stats", response_model=LearningStats)
def read_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearningStats:
    """Thống kê học tập, tính lại mỗi lần đọc.

    Tách khỏi `GET /profile` chứ không gộp vào: hồ sơ là vài cột đọc thẳng, còn
    phần này quét bảng lượt ôn và lượt dictation. Gộp lại thì mỗi lần sửa tên
    hiển thị cũng phải trả giá cho toàn bộ phép đếm, và `SessionProvider` — vốn
    gọi `/auth/me` ở mọi lần tải trang — sẽ kéo theo chúng ở khắp mọi nơi.
    """
    profile = ensure_profile(db, current_user)
    return gather_stats(db, current_user.id, profile.timezone)


# --- avatar -----------------------------------------------------------------

# Hạn mức riêng và chặt hơn của khu nội dung: một người chỉ có MỘT avatar, nên
# nhu cầu thật là vài lần mỗi phiên. Rộng hơn thế chỉ mở cửa cho việc dùng tài
# khoản Cloudinary của ta làm nơi chứa file.
AVATAR_QUOTA = Quota(limit=10, window_seconds=60 * 10)


@router.post(
    "/profile/avatar/ticket",
    response_model=UploadTicket,
    dependencies=[Depends(rate_limit("avatar-ticket", AVATAR_QUOTA))],
)
def avatar_ticket(
    body: UploadTicketRequest,
    current_user: User = Depends(get_current_user),
) -> UploadTicket:
    """Vé upload avatar — mọi học viên đều xin được.

    Khác với ảnh nội dung, đường này KHÔNG đòi vai trò editor: đây là media của
    chính người dùng. Đổi lại, khoá nằm dưới tiền tố `avatar/` riêng, nên một
    lệnh dọn nhắm vào ảnh nội dung không thể chạm nhầm vào đây (ADR-006 §2.1).
    """
    storage_key = avatar_storage_key_for(upload_source_hash(str(uuid.uuid4())), ext=body.ext)
    ticket = get_driver("image").ticket(storage_key)
    return UploadTicket(
        upload_url=ticket.upload_url,
        fields=ticket.fields,
        storage_key=ticket.storage_key,
        max_bytes=ticket.max_bytes,
        allowed_formats=list(ticket.allowed_formats),
        expires_at=ticket.expires_at,
    )


@router.post("/profile/avatar", response_model=UserProfilePublic)
def avatar_confirm(
    body: AvatarConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Gắn ảnh vừa tải lên vào hồ sơ.

    Vẫn hỏi lại nhà cung cấp (§2.3): không có bước đó thì đây là đường ghi một
    chuỗi tuỳ ý vào `avatar_storage_key`, và giao diện sẽ hiện ảnh vỡ cho tới
    khi có người để ý.

    Khoá phải nằm dưới `avatar/`. Thiếu kiểm tra này thì một người có thể trỏ
    avatar của mình vào một ảnh nội dung, và lệnh dọn ảnh mồ côi sau này sẽ xoá
    mất thứ đang được dùng.
    """
    if not body.storage_key.startswith(f"{AVATAR_KEY_PREFIX}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Khoá không thuộc vùng avatar"
        )
    try:
        get_driver("image").verify(body.storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None

    profile = ensure_profile(db, current_user)
    profile.avatar_storage_key = body.storage_key
    db.commit()
    db.refresh(profile)
    return profile_public(profile)


@router.delete("/profile/avatar", response_model=UserProfilePublic)
def avatar_remove(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Gỡ avatar, rơi về ảnh chữ cái đầu.

    KHÔNG xoá file khỏi kho ngay tại đây. Xoá đồng bộ nghĩa là một request của
    người dùng phải chờ một dịch vụ bên ngoài trả lời, và nếu nó lỗi thì hồ sơ
    vẫn giữ ảnh cũ trong khi người dùng đã thấy thông báo thành công. File mồ
    côi để lệnh đối chiếu dọn — đó là việc nó sinh ra để làm (§10.4).
    """
    profile = ensure_profile(db, current_user)
    profile.avatar_storage_key = None
    db.commit()
    db.refresh(profile)
    return profile_public(profile)
