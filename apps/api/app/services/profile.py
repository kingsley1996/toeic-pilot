"""Đọc và bảo đảm sự tồn tại của hàng hồ sơ.

Nằm ở đây chứ không nằm trong một router, vì cả `routes/auth.py` lẫn
`routes/profile.py` đều cần — và một router import router kia là thứ trông vô
hại cho tới lần đầu có ai đó thêm chiều import ngược lại.
"""

from sqlalchemy.orm import Session

from app.core.storage import get_driver
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.profile import UserProfilePublic


def ensure_profile(db: Session, user: User) -> UserProfile:
    """Hàng hồ sơ của người dùng, tạo nếu chưa có.

    Đăng ký đã tạo hàng này trong cùng transaction và migration `009` đã điền cho
    mọi tài khoản có từ trước, nên nhánh tạo ở đây chỉ chạy với hàng `users` được
    chèn tay hoặc bởi fixture test.

    Tạo thay vì ném lỗi là lựa chọn có cân nhắc: thiếu hàng hồ sơ là lỗi dữ liệu
    của phía chúng ta, và biến nó thành 404 sẽ khiến người dùng thấy một tài
    khoản "không tồn tại" trong khi họ vừa đăng nhập vào chính nó.
    """
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def profile_public(profile: UserProfile) -> UserProfilePublic:
    return UserProfilePublic(
        display_name=profile.display_name,
        timezone=profile.timezone,
        locale=profile.locale,
        target_score=profile.target_score,
        exam_date=profile.exam_date,
        minutes_per_day=profile.minutes_per_day,
        daily_new_limit=profile.daily_new_limit,
        preferred_accent=profile.preferred_accent,
        avatar_url=(
            get_driver("image").public_url(profile.avatar_storage_key)
            if profile.avatar_storage_key
            else None
        ),
    )
