"""Hình dạng ví ruby gửi cho trình duyệt (ADR-011 §7)."""

from datetime import datetime

from pydantic import BaseModel, Field


class RubyEntryPublic(BaseModel):
    """Một dòng trong lịch sử. `amount` âm là một khoản tiêu."""

    id: str
    amount: int
    source_type: str
    label: str
    """Nhãn tiếng Việt của nguồn, tra ở máy chủ.

    Gửi kèm thay vì để trình duyệt tra: bảng mức thưởng là dữ liệu admin sửa
    được, nên một bảng tra thứ hai phía frontend sẽ trôi khỏi nó vào đúng ngày ai
    đó thêm nguồn — và hậu quả là một dòng lịch sử trống, không phải một lỗi.
    Cùng lý do `PetPublic.tile` được gửi kèm.
    """
    created_at: datetime


class RubyGiftPublic(BaseModel):
    """Quà hôm nay.

    Ba trạng thái chứ không phải hai, và giao diện cần cả ba để nói đúng câu:
    chưa học gì (`unlocked=false` — *học một chút là mở được*), mở được mà chưa
    nhận, và đã nhận rồi.
    """

    amount: int
    unlocked: bool
    claimed: bool


class RubyWallet(BaseModel):
    balance: int
    gift: RubyGiftPublic
    recent: list[RubyEntryPublic]


class RubyClaimResult(BaseModel):
    granted: int
    """0 nghĩa là chưa mở được hoặc đã nhận rồi — không phải lỗi, xem `claim_gift`."""
    balance: int
    gift: RubyGiftPublic


class RubyRulePublic(BaseModel):
    """Một dòng trong bảng mức thưởng, như màn quản trị nhìn thấy."""

    source_type: str
    label: str
    amount: int
    position: int
    enabled: bool


class RubyRuleEdit(BaseModel):
    """Sửa một mức thưởng.

    `source_type` KHÔNG sửa được và không có đường tạo hàng mới: mỗi nguồn là
    một truy vấn có thật trong mã (xong bài, thuộc chủ đề, nộp đề…), nên thêm
    một mã lạ chỉ tạo ra một hàng không bao giờ được trao — đúng ranh giới mà
    `kind` của daily task và `metric` của huy hiệu đã vẽ giữa dữ liệu và mã.

    Muốn bỏ một nguồn thì TẮT nó. Xoá hàng cuối cùng khiến bảng rỗng, và bảng
    rỗng nghĩa là "chưa từng cấu hình" — lần đọc sau gieo lại bộ mặc định.
    """

    label: str | None = Field(default=None, min_length=1, max_length=80)
    amount: int | None = Field(default=None, ge=1, le=1000)
    position: int | None = Field(default=None, ge=0, le=100)
    enabled: bool | None = None
