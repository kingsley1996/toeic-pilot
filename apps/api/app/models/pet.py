"""Con thú đang nuôi của một học viên (ADR-010 §4).

**Một hàng cho mỗi người, và khoá chính CHÍNH LÀ khoá ngoại.** Đó là thứ ép quan
hệ 1-1 ở tầng database thay vì bằng một quy ước ai đó phải nhớ — cùng hình dạng
với `user_profile`.

Bản trước của góc thú cưng giữ trạng thái **trong bộ nhớ trang**: đóng tab là
mất. Bảng này là lời trả lời cho điều đó, và hai cột dưới đây mang gần hết ý
nghĩa của nó.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PetState(Base):
    __tablename__ = "pet_state"
    __table_args__ = (
        # Ràng buộc phải nằm ở CẢ HAI chỗ, và đây là chỗ dễ quên.
        #
        # Migration dựng schema cho Postgres; `Base.metadata` dựng schema cho
        # test (SQLite trong bộ nhớ). Chỉ viết ở migration thì test chạy trên một
        # bảng KHÔNG có ràng buộc — nên một bài kiểm "giá trị sai bị từ chối" sẽ
        # xanh ở CI mà đỏ ở đời thật, hoặc ngược lại. `--autogenerate` cũng không
        # so CHECK một cách đáng tin, nên không có gì báo chỗ lệch này.
        CheckConstraint(
            "fullness BETWEEN 0 AND 1 AND energy BETWEEN 0 AND 1 AND mood BETWEEN 0 AND 1",
            name="ck_pet_state_needs_range",
        ),
        CheckConstraint("facing IN ('left', 'right')", name="ck_pet_state_facing"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    species: Mapped[str] = mapped_column(String(32), nullable=False)
    """Mã loài.

    **Không có CHECK, và đó là chủ ý** — cùng lý do `user_profile.pet` không có:
    danh sách loài sẽ sống ở bảng `pet_species` (ADR-010 §6.3, lát 7) để admin
    sửa được mà không cần deploy. Một CHECK ở đây là chỗ thứ hai phải nhớ sửa mỗi
    lần thêm loài, và là chỗ bị quên báo lỗi muộn nhất.
    """

    nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)

    xp: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    """XP của CON THÚ, không phải của người học.

    Không có cột `level`: level suy ra từ `xp` qua bảng ngưỡng, y như level người
    học suy ra từ `SUM(xp_event.amount)`. Lưu cả hai là hai nguồn sự thật cho một
    con số, và cái sai sẽ là cái không ai đọc.
    """

    level_reached: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")

    xp_today: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    xp_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    """XP đã nhận trong NGÀY nào, theo múi giờ người học.

    Cặp này thay cho một sổ cái: trần ngày cần biết "hôm nay đã nhận bao nhiêu",
    và với một bộ đếm thì câu đó chỉ trả lời được nếu biết bộ đếm thuộc về ngày
    nào. Ngày đổi thì bộ đếm về 0 — kiểm lúc GHI, không phải lúc đọc, cùng luật
    với trần XP người học: kẹp lúc đọc sẽ biến nó thành một công thức, và đổi
    trần sau này sẽ viết lại quá khứ.

    NULL = chưa nhận XP ngày nào.
    """
    """Mốc cao nhất từng đạt, CHỈ TĂNG.

    Giống `user_profile.level_reached` và vì cùng một lý do: chỉnh lại đường cong
    XP về sau không được lấy mất level của người đã đạt tới nó.
    """

    tile_x: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    tile_y: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="8")
    """Vị trí theo Ô, không theo pixel.

    Bản đồ đổi kích thước hay đổi hệ số phóng thì hai số này vẫn đúng. Lưu pixel
    là ghim vị trí vào một cỡ màn hình cụ thể, và không có gì báo khi cỡ đó đổi.

    Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại; phía client giải
    quyết bằng `nearestWalkable`, chứ không phải bằng một migration cho từng lần
    đổi bản đồ.
    """

    facing: Mapped[str] = mapped_column(String(5), nullable=False, server_default="right")

    fullness: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default="0.62")
    energy: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default="0.78")
    mood: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default="0.70")
    """Ba nhu cầu, 0..1. `Numeric` chứ không `Float`, theo đúng `ease_factor` của SM-2."""

    needs_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    """MỐC THỜI GIAN của ba số trên, và đây là cột quan trọng nhất bảng này.

    Nhu cầu **suy ra lúc đọc**: `fullness_bây_giờ = decay(fullness, now -
    needs_at)`. Bản cũ trừ dần theo `dt` của vòng `requestAnimationFrame`, nên
    đồng hồ chỉ chạy khi bảng đang mở — mở cả buổi thì con thú đói, đóng tab một
    tuần thì nó vẫn no nguyên. Ngược hoàn toàn với trực giác của người nuôi.

    Cùng luật đã dùng cho chuỗi ngày ở `profile_stats.py` và cho tiến độ ở
    `StoryProgress`: suy ra ở mỗi lần đọc, không nuôi một bộ đếm chạy song song
    với lịch sử.
    """

    hatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<PetState {self.species} lv{self.level_reached} @({self.tile_x},{self.tile_y})>"
