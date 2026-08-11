import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["AI_INTERACTION_STATUSES", "AiInteraction"]

# `error` là một kết quả, không phải một sự vắng mặt. Chỉ ghi lượt gọi thành
# công thì tỉ lệ hỏng của nhà cung cấp là bằng không trong mọi báo cáo, và cái
# nhìn thấy được sẽ là "AI thỉnh thoảng không trả lời" mà không con số nào đỡ.
AI_INTERACTION_STATUSES = ("ok", "error", "refused")


class AiInteraction(Base):
    """Một lượt gọi LLM: đã tiêu bao nhiêu, mất bao lâu, cho ai, vì việc gì.

    **Dựng trước request LLM đầu tiên chứ không phải sau** (`REVIEW-OPUS.md`
    §7d/§7e). Không đo được thì không cải thiện được, và không đếm được thì
    không giới hạn được — thêm bảng này sau nghĩa là quãng đầu tiên, đúng quãng
    prompt thay đổi nhiều nhất, sẽ không có số nào để so.

    **Đây là sổ cái bền, KHÔNG phải bộ đếm hạn mức.** Chặn theo ngân sách phải
    đọc được trong một request nên nó thuộc về Redis, y như `rate_limit` — hỏi
    Postgres `SUM(cost_usd)` ở mỗi lượt gọi là đặt một phép quét lên đường đi
    nóng và nó chậm dần theo đúng tốc độ sản phẩm lớn lên. Cũng vì thế **không
    có bảng `ai_usage`**: mọi báo cáo dùng được suy ra từ bảng này, còn một bảng
    tổng ghi song song sẽ lệch khỏi sổ cái ngay lần đầu có ai xoá một hàng, và
    không gì phát hiện ra. Cùng lập luận với `StoryProgress` và `user_progress`.
    """

    __tablename__ = "ai_interaction"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'error', 'refused')",
            name="ck_ai_interaction_status",
        ),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND cached_tokens >= 0",
            name="ck_ai_interaction_tokens_non_negative",
        ),
        # Câu hỏi hay hỏi nhất là "người này đã tiêu bao nhiêu hôm nay". Không
        # có index này thì nó là một lần quét toàn bảng, và bảng này lớn nhanh
        # hơn mọi bảng khác trong hệ.
        Index("ix_ai_interaction_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # NULL được phép: một lượt gọi trong job nền hay trong eval harness không
    # thuộc về học viên nào. ON DELETE SET NULL chứ không CASCADE — xoá tài
    # khoản không được xoá mất chi phí đã thực sự phát sinh.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Việc gì gọi: "coach_explain", "study_plan", "eval". Chuỗi tự do chứ không
    # phải enum, vì danh sách này sẽ dài ra mỗi sprint và một CHECK ở đây biến
    # mỗi tính năng AI mới thành một migration.
    feature: Mapped[str] = mapped_column(String(48), nullable=False, index=True)

    # Nhà cung cấp VÀ model, tách rời. Gộp thành một chuỗi thì câu hỏi "đổi sang
    # model rẻ hơn tiết kiệm được bao nhiêu" — tức là toàn bộ lý do LLM routing
    # tồn tại — phải parse chuỗi mới trả lời được.
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Tách riêng token đọc từ cache. Prompt caching là đòn bẩy chi phí lớn nhất
    # của tầng này, và nó được tính giá khác hẳn — gộp vào `prompt_tokens` thì
    # không đo được nó có hiệu quả hay không, tức là không biết có nên giữ.
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Numeric chứ không phải float. Tiền cộng dồn qua hàng trăm nghìn hàng, và
    # sai số nhị phân của float tích lại thành một con số không khớp hoá đơn.
    # Sáu chữ số thập phân vì một lượt gọi rẻ có thể là 0.000042 USD.
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)

    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nối vào `X-Request-ID` mà `RequestContextMiddleware` đã gán. Đây chính là
    # thứ `app/core/logging.py` được dựng sẵn từ Phase 1 để phục vụ: một dòng
    # log và một hàng chi phí chỉ ghép lại được khi có cùng một định danh.
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
