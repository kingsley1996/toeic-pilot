"""Cấu hình nền lưới động."""

from pydantic import BaseModel, Field

from app.models.appearance import (
    BACKDROP_COLORS,
    MAX_SPARKS,
    MAX_SPEED,
    MAX_TWINKLES,
    MIN_SPEED,
)

__all__ = ["BackdropPublic", "BackdropUpdate", "BACKDROP_COLORS"]


class BackdropUpdate(BaseModel):
    """Những gì quản trị viên chỉnh được.

    Không có toạ độ: vị trí tia và đốm sinh từ một bảng cố định phía giao diện,
    còn ở đây chỉ là SỐ LƯỢNG. Cho nhập toạ độ nghĩa là toạ độ phải hợp lệ với
    mọi kích thước màn hình, mà lúc lưu thì không có màn hình nào để kiểm.

    `color` là TÊN TOKEN, không phải mã màu. Mỗi token có sẵn giá trị cho nền
    sáng và nền tối, nên đổi màu vẫn giữ nguyên lời hứa về tương phản; một mã
    hex hợp lệ vẫn có thể chìm nghỉm ở chế độ còn lại mà không có gì báo.
    """

    spark_count: int = Field(ge=0, le=MAX_SPARKS)
    twinkle_count: int = Field(ge=0, le=MAX_TWINKLES)
    color: str = Field(description=f"One of {list(BACKDROP_COLORS)}")
    # Hệ số phần trăm, 100 = gốc. Số càng lớn càng NHANH: chu kỳ bị chia cho nó.
    speed_percent: int = Field(ge=MIN_SPEED, le=MAX_SPEED)
    # Tách khỏi "0 tia, 0 đốm": hai thứ đó nói rằng nền đang được cấu hình để
    # trống, còn `enabled=False` nói rằng nó bị tắt — và người đọc lại cấu hình
    # sau ba tháng cần phân biệt được hai điều đó.
    enabled: bool


class BackdropPublic(BackdropUpdate):
    """Đường đọc CÔNG KHAI: khách chưa đăng nhập cũng thấy nền này.

    Không trả `updated_by` hay `updated_at` — người xem trang giới thiệu không
    cần biết ai chỉnh nền lúc mấy giờ, và tên người chỉnh là dữ liệu nội bộ.
    """
