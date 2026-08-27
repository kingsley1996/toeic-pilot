"""Ruby: đơn vị của góc thú cưng, kiếm bằng việc học (ADR-011).

Sổ cái chứ không phải bộ đếm, và lần này là bắt buộc chứ không phải một lựa chọn
đẹp: ruby có đường TIÊU ngay từ ngày đầu, mà một bộ đếm chạy lên xuống không trả
lời được câu "điểm này từ đâu ra, tiêu vào đâu" — thứ duy nhất giải quyết được
khiếu nại "tôi có 40 ruby, giờ còn 10".
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

RUBY_SOURCES = (
    "story_complete",
    "topic_mastered",
    "attempt_full",
    "attempt_mini",
    "daily_all",
    "daily_gift",
    "streak_week",
    # Hoàn ruby khi mở trứng ra con đã có. Là một đường KIẾM, nhưng không nằm
    # trong `ruby_rule`: mức hoàn là thuộc tính của quả trứng (`egg_setting`),
    # không phải một phần thưởng cho việc học, và đặt nó vào bảng mức thưởng sẽ
    # cho phép chỉnh nó lên cao hơn giá trứng — tức là một cỗ máy in ruby.
    "egg_refund",
    # Ruby cấp cho tài khoản QUẢN TRỊ để thử tính năng. Không nằm trong
    # `ruby_rule`: nó không phải một mức thưởng cho việc học, và một hàng trong
    # bảng đó là một hàng ai đó có thể vô tình bật cho người học.
    "admin_grant",
    # Thưởng cho một cuộc chạm mặt (ADR-012). Không nằm trong `ruby_rule`: mức
    # thưởng chốt trên từng cuộc lúc nó sinh ra, cùng lý do `egg_refund` không
    # nằm ở đó. Nó KHÔNG phá luật "không trả theo lượt nhỏ" của §1 vì thứ giới
    # hạn nó là nhịp xuất hiện, không phải số lần người ta làm bài.
    "encounter",
    # Đường TIÊU. Nằm chung một danh sách với đường kiếm vì chúng chung một sổ:
    # tách ra sẽ cần hai bảng, và lúc đó số dư không còn là một phép `SUM`.
    "egg",
)

SPEND_SOURCES = ("egg",)


class RubyEvent(Base):
    """Một lần ruby đổi chủ. Bất biến: không sửa, không xoá ở đường chạy bình thường."""

    __tablename__ = "ruby_event"
    __table_args__ = (
        # Khoá duy nhất LÀM LUÔN việc chống cày: xong bài dictation số 7 sinh
        # `source_id = story_id`, nên lần thứ hai bị database từ chối chứ không
        # bị một đoạn `if` ai đó phải nhớ viết. Đây là lý do bảng mức thưởng
        # không cần trần ngày — nội dung tự giới hạn tốc độ.
        UniqueConstraint("user_id", "source_type", "source_id", name="uq_ruby_event_source"),
        CheckConstraint("amount <> 0", name="ck_ruby_event_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    """DƯƠNG là kiếm, ÂM là tiêu.

    Tiêu là một hàng âm chứ không phải một phép trừ lên số dư: lịch sử giữ được
    câu "đã tiêu vào đâu", và số dư vẫn là `SUM` của đúng một bảng.
    """

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    """Thứ sinh ra khoản này: bài dictation, chủ đề, lượt làm đề, hay một uuid
    TẤT ĐỊNH sinh từ (người, ngày địa phương, nguồn) cho các khoản lặp theo ngày.

    Không phải khoá ngoại: nó trỏ tới bốn bảng khác nhau, và một khoá ngoại sẽ
    chặn việc xoá nội dung chỉ vì có người từng được thưởng vì nó — đúng cái bẫy
    mà `dictation_attempt` RESTRICT đã dựng ra ở chỗ khác.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<RubyEvent {self.amount:+} {self.source_type}>"


class RubyRule(Base):
    """Mức thưởng của một nguồn. Hàng, không phải hằng số (ADR-011 §6)."""

    __tablename__ = "ruby_rule"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_ruby_rule_amount"),)

    source_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def __repr__(self) -> str:
        return f"<RubyRule {self.source_type}={self.amount}>"


"""Mức mặc định, gieo LƯỜI ở lần đọc đầu — không gieo trong migration.

Một nguồn sự thật duy nhất, cùng hình dạng `DEFAULT_PET_SPECIES` và
`DEFAULT_FRAME_TIERS`. Hệ quả: bảng rỗng nghĩa là "chưa từng cấu hình", không
phải "cố ý để trống".

Nhãn bằng tiếng Việt vì nó là thứ người học đọc trong lịch sử ruby.
"""
DEFAULT_RUBY_RULES: tuple[dict[str, object], ...] = (
    {
        "source_type": "story_complete",
        "label": "Nghe xong một bài",
        "amount": 5,
        "position": 1,
    },
    {
        "source_type": "topic_mastered",
        "label": "Thuộc trọn một chủ đề",
        "amount": 15,
        "position": 2,
    },
    {"source_type": "attempt_full", "label": "Làm xong một đề", "amount": 25, "position": 3},
    {"source_type": "attempt_mini", "label": "Làm xong một đề ngắn", "amount": 8, "position": 4},
    {"source_type": "daily_all", "label": "Xong cả ba việc hôm nay", "amount": 10, "position": 5},
    {"source_type": "daily_gift", "label": "Quà hàng ngày", "amount": 3, "position": 6},
    {"source_type": "streak_week", "label": "Giữ chuỗi bảy ngày", "amount": 20, "position": 7},
)
