"""Hợp đồng của góp ý người học. Tên theo quy ước `XCreate` / `XPublic`."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import MAX_SCREENSHOTS as _MAX_SCREENSHOTS

FeedbackType = Literal["bug", "feature", "content", "other"]
FeedbackStatus = Literal["pending", "approved", "rejected"]

# Đủ dài để mô tả một lỗi kèm các bước tái hiện, đủ ngắn để không ai dán cả một
# tệp log vào ô này. Trần nằm ở schema chứ không ở cột: cột là `Text`, và một
# giới hạn đọc được ở hợp đồng thì frontend đếm ký tự được mà không phải đoán.
DESCRIPTION_MAX = 4000

# Trần số ảnh — nguồn sự thật ở model, hợp đồng chỉ nhắc lại nó.
MAX_SCREENSHOTS = _MAX_SCREENSHOTS


class FeedbackCreate(BaseModel):
    type: FeedbackType
    # `min_length=1` sau khi cắt khoảng trắng: một ô toàn dấu cách là ô rỗng, và
    # nếu chỉ dựa vào NOT NULL của cột thì nó lọt qua.
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX)
    # Trần ở hợp đồng, không chỉ ở giao diện: giới hạn nào chỉ sống trong
    # React thì một request viết tay đi vòng qua được.
    screenshot_keys: list[str] = Field(default_factory=list, max_length=MAX_SCREENSHOTS)


class FeedbackRejectBody(BaseModel):
    admin_note: str | None = None


class FeedbackNoteBody(BaseModel):
    admin_note: str | None = None


class FeedbackPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: FeedbackType
    description: str
    status: FeedbackStatus
    admin_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    # Sinh từ `driver.public_url`, không phải khoá thô: khoá là chi tiết lưu trữ
    # và nhà cung cấp là một biến cấu hình (ADR-006 §2.8), nên để frontend tự
    # ghép URL là dựng một chỗ thứ hai phải nhớ tiền tố của Cloudinary.
    image_urls: list[str] = Field(default_factory=list)


class FeedbackReward(BaseModel):
    """Mức thưởng hiện hành. 0 nghĩa là nguồn đang tắt — đừng hứa gì."""

    amount: int
