from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.profile import LearningStats, UserProfilePublic, UserProfileUpdate
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
