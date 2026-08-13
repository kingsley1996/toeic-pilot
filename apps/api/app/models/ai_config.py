import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["AiFeatureConfig"]


class AiFeatureConfig(Base):
    """Nhà cung cấp và model cho MỘT tính năng AI, sửa được từ giao diện quản trị.

    Khoá chính là `feature`, và nó khớp đúng `ai_interaction.feature` — nên câu
    hỏi *"đổi Coach sang model rẻ hơn tiết kiệm bao nhiêu"* trả lời được bằng
    một truy vấn trên sổ cái đã có, không cần thêm cột nào.

    **Không có cột nào chứa khoá API, và sẽ không bao giờ có.** Một ô nhập khoá
    trên giao diện là một khoá sẽ lọt vào log, ảnh chụp màn hình và bản sao lưu
    database. Khoá ở `.env`; bảng này chỉ chọn *dùng cái gì*.

    `enabled=False` nghĩa là tính năng bị tắt hẳn — dùng khi hoá đơn tăng đột
    biến hoặc nhà cung cấp sập. Tắt Coach không được ảnh hưởng gắn nhãn, và đó
    là lý do cấu hình chia theo tính năng chứ không theo tầng rẻ/mạnh.
    """

    __tablename__ = "ai_feature_config"

    feature: Mapped[str] = mapped_column(String(48), primary_key=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Ai đổi. `SET NULL` vì xoá tài khoản không được xoá bản ghi cấu hình đang
    # có hiệu lực — mất tên người đổi thì chấp nhận được, mất cấu hình thì không.
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
