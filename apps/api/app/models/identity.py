"""Đăng nhập bằng nhà cung cấp bên ngoài: Google, Apple.

**Bảng riêng, không phải cột `google_id` trên `users`.** Một cột cho mỗi nhà cung
cấp nghĩa là mỗi nhà cung cấp mới là một migration trên bảng nóng nhất hệ thống,
và một tài khoản dùng cả hai đường thì phải nhớ điền cả hai cột. Bảng riêng cũng
là chỗ đúng để ghi email lúc liên kết — thứ có thể khác email hiện tại của tài
khoản, và không được phép ghi đè lên nó.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Tập ĐÓNG. Mỗi nhà cung cấp cần một mô tả trong `app/services/oauth.py` (điểm
# cuối, cách xác thực client, cách ký), nên thêm một dòng ở đây mà không thêm mô
# tả kia thì được một giá trị hợp lệ với database và vô nghĩa với code.
IDENTITY_PROVIDERS = ("google", "apple")


class UserIdentity(Base):
    __tablename__ = "user_identity"
    __table_args__ = (
        # Khoá tra cứu là (nhà cung cấp, subject) — KHÔNG phải email.
        #
        # `sub` là định danh bền của tài khoản bên đó; email thì đổi được, và với
        # Apple nó còn có thể là một địa chỉ chuyển tiếp ẩn khác hẳn hộp thư
        # thật. Tra theo email nghĩa là ai đổi email bên Google sẽ thành một
        # người mới với hệ thống này, mất sạch lịch sử học.
        UniqueConstraint("provider", "subject", name="uq_user_identity_provider_subject"),
        # Một tài khoản chỉ liên kết MỘT lần với mỗi nhà cung cấp. Thiếu ràng
        # buộc này thì hai Apple ID khác nhau cùng trỏ vào một tài khoản, và
        # không có cách nào nói cái nào là cái đúng khi cần gỡ liên kết.
        UniqueConstraint("user_id", "provider", name="uq_user_identity_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # Email mà nhà cung cấp báo LÚC LIÊN KẾT, giữ nguyên về sau.
    #
    # Không đồng bộ lại: đây là bằng chứng cho quyết định liên kết đã xảy ra, chứ
    # không phải một bản sao của email hiện tại. Apple chỉ gửi email ở lần cấp
    # quyền ĐẦU TIÊN, nên một cột "luôn mới nhất" sẽ tự rỗng ở lần đăng nhập thứ
    # hai — và không có gì báo.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserIdentity {self.provider} user={self.user_id}>"
