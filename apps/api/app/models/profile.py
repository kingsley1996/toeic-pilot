import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.media import AUDIO_ACCENTS
from app.models.mixins import TimestampMixin

# TOEIC Listening & Reading is reported as 10–990 in steps of 5. A target of 812
# is not a score anyone can be awarded, so it is not a goal anyone can reach.
MIN_TARGET_SCORE = 10
MAX_TARGET_SCORE = 990
TARGET_SCORE_STEP = 5

# Long enough for a full Vietnamese name; short enough that it stays a name.
MAX_DISPLAY_NAME = 80

_ACCENT_LIST = ", ".join(f"'{accent}'" for accent in AUDIO_ACCENTS)


class UserProfile(Base, TimestampMixin):
    """Everything about a learner that is not their identity.

    Separate from `users` on purpose. `users` is loaded by `get_current_user` on
    every authenticated request and answers exactly one question — who is this,
    and what may they do. Display preferences and study goals answer a different
    question, change far more often, and would put a migration on the
    authentication table every time the product grows a setting.

    The row is created **in the same transaction as registration**, never lazily.
    A 1:1 table whose row might not exist yet is a null check at every single
    read site, and the one place someone forgets it is the 500.
    """

    __tablename__ = "user_profile"
    __table_args__ = (
        CheckConstraint(
            f"target_score IS NULL OR ("
            f"target_score BETWEEN {MIN_TARGET_SCORE} AND {MAX_TARGET_SCORE} "
            f"AND target_score % {TARGET_SCORE_STEP} = 0)",
            name="ck_user_profile_target_score",
        ),
        CheckConstraint(
            "minutes_per_day IS NULL OR minutes_per_day BETWEEN 5 AND 480",
            name="ck_user_profile_minutes_per_day",
        ),
        CheckConstraint(
            "daily_new_limit IS NULL OR daily_new_limit BETWEEN 1 AND 200",
            name="ck_user_profile_daily_new_limit",
        ),
        CheckConstraint(
            f"preferred_accent IS NULL OR preferred_accent IN ({_ACCENT_LIST})",
            name="ck_user_profile_preferred_accent",
        ),
    )

    # The primary key *is* the foreign key: that is what makes this 1:1 rather
    # than a table that could quietly grow a second row per user.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Nullable rather than defaulted to the email. Falling back at render time is
    # reversible; writing the email in as a name means later telling real names
    # apart from filled-in ones is guesswork.
    display_name: Mapped[str | None] = mapped_column(String(MAX_DISPLAY_NAME), nullable=True)

    # Not decoration. A learning streak asks "did they study yesterday", and
    # yesterday ends at 17:00 UTC in Hanoi — computing it in UTC breaks the
    # streak of everyone who studies in the evening.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Asia/Ho_Chi_Minh"
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False, server_default="vi")

    # --- Study goals. These are the inputs PLAN.md §3.3 names for the AI Study
    # Planner: current score, target score, time available. Collected now so the
    # planner has real data to read on the day it is built rather than an empty
    # form to ask for it.
    target_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    minutes_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Session preferences.
    #
    # NULL means "whatever the system default is", NOT a copy of today's default.
    # SPEC-LEARNING-HUB §5 says outright that 20 new cards a day is borrowed from
    # Anki and unverified, so it will move. Copying 20 into every row at
    # registration would pin every existing learner to the old number the day it
    # changes, and nothing would report that.
    daily_new_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Level cao nhất từng đạt — mốc nước cao, không phải bản sao của level.
    #
    # Level vẫn suy ra từ tổng XP như cũ; cột này chỉ giữ cho nó KHÔNG TỤT khi
    # admin sửa bảng ngưỡng. Nâng chuẩn thì người mới lên chậm hơn còn người cũ
    # giữ nguyên; hạ chuẩn thì mọi người lên. Không có đường nào làm ai mất một
    # level họ đã có, và đó là cùng lý do khiến XP là sổ cái chứ không phải một
    # phép tính lại: người dùng không được mất thứ gì vì một quyết định vận hành
    # mà họ không tham gia.
    #
    # Đây KHÔNG vi phạm luật "không có bộ đếm song song với lịch sử": nó không
    # đếm gì cả, nó ghi một mốc đã xảy ra — cùng loại với `xp_event`, chỉ là một
    # hàng thay vì nhiều.
    level_reached: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    preferred_accent: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Con mascot của Petland. NULL nghĩa là "con mặc định của hệ thống", KHÔNG
    # phải một bản sao của con mặc định hôm nay — cùng lý do với daily_new_limit:
    # đổi mặc định thì mọi người chưa từng chọn phải đi theo, chứ không bị ghim
    # vào con cũ một cách lặng lẽ.
    #
    # Không có CHECK ở đây, và đó là chủ ý. Danh sách mascot sống ở
    # `app/schemas/profile.py::PetId`, nên nó đi qua OpenAPI ra tới TypeScript và
    # `tsc` bắt được frontend thiếu con nào. Một CHECK trong cơ sở dữ liệu chỉ
    # thêm một chỗ thứ hai phải nhớ sửa, và chỗ bị quên sẽ là chỗ báo lỗi muộn nhất.
    pet: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Ảnh đại diện đã tải lên. NULL là trạng thái bình thường, không phải dữ
    # liệu thiếu: ảnh chữ cái đầu vẫn là mặc định, và cột này rơi về NULL khi
    # một ảnh bị gỡ (ADR-006 §2.7).
    #
    # Không có hàng `image_asset`: avatar là media của người dùng, không có bản
    # quyền để ghi và không qua cổng duyệt (ADR-006 §2.1).
    avatar_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
