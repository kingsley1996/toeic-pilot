import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["BackdropSetting", "BACKDROP_COLORS", "BACKDROP_DEFAULTS"]

# Chỉ cho chọn trong bảng token của hệ thiết kế, KHÔNG nhận mã màu tự do.
#
# Mỗi token ở đây có sẵn một giá trị cho nền sáng và một cho nền tối
# (`globals.css`), nên đổi màu vẫn giữ nguyên lời hứa về tương phản. Một ô nhập
# hex sẽ hỏng đúng ở chỗ không ai thử: người chỉnh ở chế độ sáng chọn một màu
# đẹp, rồi cùng màu đó chìm nghỉm hoặc chói gắt trên nền tối, và không có gì
# báo vì nó vẫn là một màu hợp lệ.
BACKDROP_COLORS = (
    "action",
    "ok",
    "warn",
    "alert",
    "accent-us",
    "accent-uk",
    "accent-au",
    "accent-ca",
)

# Giá trị mặc định, và cũng là thứ giao diện rơi về khi không đọc được cấu hình.
# Giữ ở đây để một chỗ duy nhất định nghĩa "trông như thế nào khi chưa ai chỉnh".
BACKDROP_DEFAULTS = {
    "spark_count": 2,
    "twinkle_count": 5,
    "color": "action",
    "speed_percent": 100,
    "enabled": True,
}

MAX_SPARKS = 6
MAX_TWINKLES = 12
# Tốc độ là HỆ SỐ phần trăm, không phải số giây. Chu kỳ gốc của mỗi vệt khác
# nhau (chúng cố ý lẻ nhau để không rơi vào một nhịp đều đặn), nên một ô nhập
# "số giây" sẽ san phẳng đúng thứ khiến nền không có nhịp. Hệ số giữ nguyên tỉ
# lệ giữa chúng.
MIN_SPEED = 25
MAX_SPEED = 300


class BackdropSetting(Base):
    """Cấu hình nền lưới động, sửa được từ giao diện quản trị.

    **Một hàng duy nhất, và điều đó được DATABASE bảo đảm** bằng
    `CHECK (id = 1)` chứ không bằng quy ước "nhớ đừng chèn hàng thứ hai". Một
    bảng cấu hình đơn hàng mà chỉ dựa vào quy ước sẽ có hàng thứ hai vào đúng
    ngày ai đó viết một script seed, và từ đó `SELECT ... LIMIT 1` trả về cái
    nào là chuyện của thứ tự vật lý — một lỗi không hiện ra ở đâu cả.

    Không lưu vị trí từng tia hay từng đốm: vị trí sinh ra từ một bảng cố định
    trong `components/shell.tsx`, còn ở đây chỉ lưu SỐ LƯỢNG. Lưu toạ độ nghĩa
    là toạ độ phải hợp lệ với mọi kích thước màn hình, và không có kích thước
    màn hình nào để kiểm lúc lưu.

    Số lượng bị chặn trên ở tầng schema (`MAX_SPARKS`, `MAX_TWINKLES`), không
    phải vì hiệu năng mà vì hình thức: nền có mười hai tia không còn là nền.
    """

    __tablename__ = "backdrop_setting"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_backdrop_setting_singleton"),
        CheckConstraint(
            f"spark_count BETWEEN 0 AND {MAX_SPARKS}", name="ck_backdrop_setting_spark_count"
        ),
        CheckConstraint(
            f"twinkle_count BETWEEN 0 AND {MAX_TWINKLES}", name="ck_backdrop_setting_twinkle_count"
        ),
        CheckConstraint(
            "color IN ('" + "', '".join(BACKDROP_COLORS) + "')", name="ck_backdrop_setting_color"
        ),
        CheckConstraint(
            f"speed_percent BETWEEN {MIN_SPEED} AND {MAX_SPEED}",
            name="ck_backdrop_setting_speed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    spark_count: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    twinkle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="action")
    # 100 = tốc độ gốc. Chia chu kỳ cho hệ số này, nên số CÀNG LỚN càng nhanh —
    # ngược với trực giác "thời lượng", và đó là lý do cột tên là `speed` chứ
    # không phải `duration`.
    speed_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # Tắt hẳn hiệu ứng động mà vẫn giữ lưới tĩnh. Cần một công tắc riêng vì
    # "0 tia, 0 đốm" và "tắt" nói hai điều khác nhau với người đọc cấu hình.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Ai đổi. `SET NULL` vì xoá tài khoản không được xoá cấu hình đang có hiệu
    # lực — mất tên người đổi thì chấp nhận được, mất cấu hình thì không.
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
