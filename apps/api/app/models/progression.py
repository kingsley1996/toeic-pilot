"""Sổ cái XP — lịch sử, không phải bộ đếm.

`profile_stats.py` phát biểu luật: một bộ đếm ghi song song với lịch sử sẽ lệch
khỏi lịch sử ngay lần đầu có một hàng bị xoá hoặc chấm lại, và không có gì phát
hiện ra sự bất đồng đó. Một cột `user_profile.xp` cộng dồn CHÍNH LÀ bộ đếm đó.

Sổ cái thì không: mỗi hàng là một sự kiện đã xảy ra, bất biến, trỏ về nguyên
nhân của nó. Tổng XP là `SUM` — vẫn suy ra khi đọc, vẫn đúng luật.

Cái mà sổ cái mua thêm so với việc tính lại hoàn toàn từ lịch sử học: **đổi công
thức XP sau này không làm ai tụt level.** Nếu XP được tính lại mỗi lần đọc thì hạ
giá một hoạt động là hạ level của mọi người đã làm nó — người dùng mất level mà
không làm gì sai. Sổ cái ghi số điểm ĐÃ TRAO lúc đó, nên quá khứ đứng yên.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Nguồn sinh XP. Chuỗi chứ không enum của cơ sở dữ liệu: thêm một nguồn không nên
# đòi một migration, và tập hợp này đã được `app/services/progression.py` kiểm
# trước khi ghi.
XP_SOURCES = (
    "vocabulary_review",
    "dictation_complete",
    "attempt_submit",
    "grammar_attempt",
    "daily_task",
    "streak_bonus",
)


class XpEvent(Base):
    """Một lần trao XP. Bất biến: không sửa, không xoá ở đường chạy bình thường."""

    __tablename__ = "xp_event"
    __table_args__ = (
        # Cột sống của thiết kế này, không phải một ràng buộc phòng xa. Thiếu nó,
        # một lần bấm đúp, một request lặp hay một job chạy lại là XP nhân đôi —
        # và vì sổ cái bất biến, không có cách sửa nào ngoài xoá hàng, tức là phá
        # đúng thứ làm nó đáng tin. Đường ghi dùng `ON CONFLICT DO NOTHING`.
        #
        # Postgres coi mọi NULL là khác nhau, nên ràng buộc này KHÔNG chặn được
        # nguồn có `source_id` NULL. Đó là lý do `daily_task` và `streak_bonus`
        # sinh uuid TẤT ĐỊNH từ (user, ngày, khe) thay vì để trống — xem
        # `app/services/progression.py`.
        UniqueConstraint("user_id", "source_type", "source_id", name="uq_xp_event_source"),
        # Mọi truy vấn đều là "người này, ngày này" (trần mỗi ngày) hoặc "người
        # này, tất cả" (tổng XP).
        Index("ix_xp_event_user_day", "user_id", "awarded_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Hàng đã sinh ra XP này. Cố ý KHÔNG phải khoá ngoại: nó trỏ vào ba bảng khác
    # nhau tuỳ `source_type`, và với `daily_task` thì nó không trỏ vào hàng nào
    # cả. Cùng lý do `vocabulary_topic_session.entry_ids` không phải khoá ngoại —
    # đây là một tham chiếu để chống trùng, không phải một quan hệ.
    source_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    # NGÀY THEO MÚI GIỜ NGƯỜI HỌC, quy đổi lúc ghi chứ không lúc đọc.
    #
    # Trần mỗi ngày và daily task đều hỏi "hôm nay được bao nhiêu", và nhét phép
    # quy đổi múi giờ vào `WHERE` của mọi truy vấn là chỗ để lệch. Người học đổi
    # múi giờ thì các hàng cũ giữ nguyên ngày cũ — đúng, vì chúng đã xảy ra trong
    # ngày đó, ở nơi đó.
    awarded_on: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserBadge(Base):
    """Hàng này KHÔNG quyết định người dùng có badge hay không.

    Điều kiện ở `app/services/badges.py` mới quyết định, và chúng đọc thẳng lịch
    sử học — nên badge đúng ngay lần đọc đầu tiên, không cần một lần chạy
    backfill nào cho tài khoản cũ.

    Bảng này giữ đúng hai thứ mà lịch sử không tự nói được: **lần đầu hệ thống
    nhìn thấy** badge này, và **người dùng đã xem thông báo chưa**. Thiếu nó thì
    không có "bạn vừa mở badge mới", vì mỗi lần đọc trang badge cái nào cũng mới.

    Ghi lười: đủ điều kiện mà chưa có hàng thì chèn, trùng thì bỏ qua. Với tài
    khoản cũ, lần đọc đầu tiên sau khi ra mắt trao một loạt cùng lúc — giao diện
    phải gộp thành MỘT thông báo, không phải mười.
    """

    __tablename__ = "user_badge"

    # Khoá chính ghép, không phải id thay thế: "một người một badge một lần" là
    # ràng buộc thật của miền, và đặt nó làm khoá chính thì không có đường nào
    # ghi trùng được. Một cột `id` riêng sẽ cần thêm một UNIQUE nói đúng điều
    # này, tức là hai chỗ nói cùng một chuyện.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    code: Mapped[str] = mapped_column(String(32), primary_key=True)

    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # NULL = chưa xem. Không dùng cờ boolean: mốc thời gian trả lời được cả "đã
    # xem chưa" lẫn "xem lúc nào", và một cờ thì không bao giờ nâng cấp ngược lại
    # được mà không mất dữ liệu.
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<UserBadge {self.code} user={self.user_id}>"


# --- cấu hình: mọi con số của hệ level đều là DỮ LIỆU ------------------------
#
# Trước đây tất cả là hằng số trong code, và mỗi lần muốn chỉnh một mức XP là một
# lần sửa code + triển khai. Giờ chúng là hàng trong database, admin sửa được.
#
# Ba tập hợp dưới đây thì KHÔNG mở: chúng không phải con số, chúng là những thứ
# mà code phải biết cách đo hoặc biết cách vẽ. Một hàng cấu hình trỏ tới một khe
# mà không tồn tại đường đo nào cho nó thì không có gì hiển thị được — nên tập
# hợp đóng, và giao diện quản trị chỉ cho chọn trong đó.

# Loại việc của một khe daily task. Mỗi loại ứng với một phép đếm có sẵn trong
# `app/services/daily_tasks.py`.
DAILY_TASK_KINDS = (
    "vocabulary_review",
    "dictation_complete",
    "attempt_answer",
    "grammar_lesson_complete",
)

# Số đo mà một badge có thể so ngưỡng. Ứng với `app/services/badges.py`.
BADGE_METRICS = (
    "reviews",
    "words_mastered",
    "dictation_items",
    "tests_submitted",
    "best_score",
    "longest_streak",
    "level",
)

# Biểu tượng mà frontend biết vẽ. Chuỗi tự do ở đây sẽ cho ra một huy hiệu không
# có hình, và lỗi đó chỉ lộ ra khi ai đó mở trang huy hiệu.
BADGE_ICONS = (
    "footprints",
    "book",
    "library",
    "graduation",
    "headphones",
    "target",
    "medal",
    "trophy",
    "flame",
    "star",
    "sparkles",
    "award",
)

# Token màu của khung avatar. CHỈ token đã có trong design system: thêm màu mới
# là việc của DESIGN-SYSTEM.md, không phải của một hàng cấu hình. Thang bốn accent
# `--accent-{us,uk,au,ca}` cố ý vắng mặt — nó phân loại GIỌNG ĐỌC, mượn sang bậc
# level là bắt một màu mang hai nghĩa.
FRAME_TONES = ("ok", "action", "warn", "alert")


class ProgressionSetting(Base):
    """Hàng cấu hình DUY NHẤT (id=1) cho mức XP và tham số sinh đường cong level.

    Hàng này được tạo lười ở lần đọc đầu tiên từ `PROGRESSION_DEFAULTS`, giống
    `backdrop_setting`. Migration chỉ tạo bảng và KHÔNG chèn dữ liệu: chèn ở cả
    hai nơi là hai nguồn sự thật cho cùng một bộ mặc định, và chúng sẽ lệch nhau
    ở lần đầu ai đó sửa một con số mà quên nơi kia.
    """

    __tablename__ = "progression_setting"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_progression_setting_singleton"),
        CheckConstraint("daily_xp_cap > 0", name="ck_progression_setting_cap"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    xp_vocabulary_review: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_dictation_complete: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_attempt_submit: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_grammar_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_xp_cap: Mapped[int] = mapped_column(Integer, nullable=False)

    # Tham số của MÁY SINH bảng level, không phải của phép tra cứu.
    #
    # Phép tra cứu chỉ đọc `level_tier`. Bốn con số này là thứ nút "sinh lại
    # bảng" dùng để ghi ra các hàng đó — vì gõ tay 50 hàng ngưỡng là công việc
    # mà không ai làm đúng tới hàng thứ mười. Sau khi sinh, admin sửa từng hàng
    # được, và các hàng mới là sự thật.
    curve_coefficient: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    curve_exponent: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    curve_break: Mapped[int] = mapped_column(Integer, nullable=False)
    curve_linear_step: Mapped[int] = mapped_column(Integer, nullable=False)
    max_level: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DailyTaskSlot(Base):
    """Một khe việc hôm nay.

    **`id` là uuid và nó đi thẳng vào `xp_event.source_id`** (qua uuid5 tất định
    cùng với người học và ngày). Đó là lý do khe phải là một HÀNG chứ không phải
    một chuỗi mã: đổi tên một khe không được phép biến nó thành việc chưa từng
    hoàn thành và trao lại XP cho cả ngày hôm đó. Đổi nhãn, đổi mục tiêu, đổi
    điểm — `id` không đổi, nên phần thưởng đã trao vẫn là đã trao.

    Xoá một khe thì mất luôn tính chống-trao-lại của nó; muốn tắt thì đặt
    `enabled = false`, đúng như `status='archived'` ở nội dung. Giao diện quản
    trị vì thế mời tắt trước, và chỉ cho xoá như một hành động riêng.
    """

    __tablename__ = "daily_task_slot"
    __table_args__ = (
        CheckConstraint("target > 0", name="ck_daily_task_slot_target"),
        CheckConstraint("xp >= 0", name="ck_daily_task_slot_xp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Một trong `DAILY_TASK_KINDS`. Kiểm ở tầng schema chứ không bằng CHECK:
    # thêm một loại việc mới là thêm một phép đếm trong code, và một CHECK ở
    # database sẽ bắt migration đi kèm mỗi lần đó.
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DailyTaskSlot {self.kind} target={self.target}>"


class LevelTier(Base):
    """Ngưỡng XP tích luỹ để ĐẠT một level. Level 1 luôn là 0.

    Bảng này là sự thật của phép tra cứu; công thức chỉ là cách sinh ra nó. Lưu
    thành hàng thay vì tính bằng hàm mua đúng một thứ: admin sửa được một bậc
    riêng lẻ mà không phải bẻ cả đường cong — và cũng có nghĩa đường cong sau này
    đổi hình dạng mà không cần ai viết lại code.
    """

    __tablename__ = "level_tier"
    __table_args__ = (CheckConstraint("xp_required >= 0", name="ck_level_tier_xp"),)

    level: Mapped[int] = mapped_column(Integer, primary_key=True)
    xp_required: Mapped[int] = mapped_column(Integer, nullable=False)


class FrameTier(Base):
    """Khung avatar mở theo level. Thuần trang trí.

    `tone` là một token màu đã có trong design system, không phải mã màu: một ô
    nhập mã màu tự do là đường ngắn nhất để một khung không đọc được ở chế độ tối
    — nơi mà không ai kiểm tra trước khi lưu.
    """

    __tablename__ = "frame_tier"
    __table_args__ = (
        CheckConstraint("min_level >= 1", name="ck_frame_tier_min_level"),
        UniqueConstraint("min_level", name="uq_frame_tier_min_level"),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    min_level: Mapped[int] = mapped_column(Integer, nullable=False)
    tone: Mapped[str] = mapped_column(String(16), nullable=False)
    # Tranh khung, nếu có. Khoá thô dưới `progression/`, KHÔNG phải hàng trong
    # `image_asset` — cùng cách avatar được lưu, và cùng lý do: ba cột giấy phép
    # NOT NULL của `image_asset` nói về ảnh mượn về, còn đây là tranh của chính
    # sản phẩm. Có ảnh thì ảnh thắng `tone`; `tone` ở lại làm phương án rơi về
    # khi ảnh chưa tải xong hoặc bị gỡ.
    image_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Vòng ngoài mảnh cho bậc cao nhất. Một cờ chứ không phải một ô CSS tự do:
    # design system cấm `box-shadow`, và một ô tự do là chỗ nó quay lại.
    ring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BadgeRule(Base):
    """Điều kiện của một huy hiệu: một số đo, một ngưỡng.

    `metric` thuộc `BADGE_METRICS` và `icon` thuộc `BADGE_ICONS` — hai tập đóng,
    vì cái thứ nhất là thứ code phải biết cách đo và cái thứ hai là thứ frontend
    phải biết cách vẽ. Ngoài hai cột đó thì mọi thứ đều sửa được, kể cả thêm huy
    hiệu mới, miễn là nó đo bằng một số đo đã tồn tại.

    `code` là khoá chính và cũng là thứ nằm trong `user_badge.code`. **Đổi mã là
    mất lịch sử**: hàng cũ trỏ tới một mã không còn ai đọc, và huy hiệu trở lại
    trạng thái "mới" với mọi người. Giao diện quản trị không cho sửa mã sau khi
    tạo, vì lý do đó.
    """

    __tablename__ = "badge_rule"
    __table_args__ = (CheckConstraint("target > 0", name="ck_badge_rule_target"),)

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    hint: Mapped[str] = mapped_column(String(160), nullable=False)
    icon: Mapped[str] = mapped_column(String(32), nullable=False)
    # Tranh huy hiệu, nếu có — thắng `icon` khi hiển thị. `icon` vẫn bắt buộc và
    # đó là chủ ý: một huy hiệu mới luôn vẽ được ngay, còn tranh thì tới sau.
    image_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<BadgeRule {self.code} {self.metric}>={self.target}>"


# --- bộ mặc định -------------------------------------------------------------
#
# MỘT nguồn duy nhất, đọc bởi lớp dịch vụ khi bảng còn trống. Migration chỉ tạo
# bảng và không chèn gì: chèn ở cả hai nơi là hai bộ mặc định phải giữ đồng bộ
# bằng tay, và chúng lệch nhau ở đúng lần đầu ai đó sửa một con số.

PROGRESSION_DEFAULTS: dict[str, object] = {
    # Mức hiệu chỉnh theo nhịp thật đo được: trung vị 2 lượt ôn mỗi ngày hoạt
    # động, p90 là 4. Một thang cho rằng người ta ôn 50 từ/ngày khiến level 2
    # thành thứ không ai với tới.
    "xp_vocabulary_review": 2,
    "xp_dictation_complete": 5,
    "xp_attempt_submit": 30,
    # Một câu ngữ pháp đúng = một hành động vi mô, cùng cỡ với một lượt ôn từ.
    "xp_grammar_attempt": 2,
    "daily_xp_cap": 120,
    # Hạ từ (50 · n^1.6, tuyến tính 500) xuống sau khi đối chiếu với NHỊP THẬT.
    #
    # Đường cong cũ đọc trên giấy thì hợp lý, nhưng nó được đặt cạnh giả định
    # "~50 XP mỗi ngày" — mà nhịp đo được của người học ở đây là trung vị 2 lượt
    # ôn/ngày, tức khoảng 14 XP kể cả khi làm xong một daily task. Ở nhịp đó,
    # level 2 mất 11 ngày và level 10 mất gần năm tháng: phần thưởng đầu tiên
    # rơi vào lúc người ta đã quyết định xong là có quay lại hay không.
    #
    # Bộ mới, đo ở cùng hai nhịp:
    #                     nhịp nhẹ (14 XP/ngày)   nhịp chăm (43 XP/ngày)
    #   level 2                  3 ngày                  1 ngày
    #   level 5                 11 ngày                  4 ngày
    #   level 10                30 ngày                 10 ngày
    #   level 20                82 ngày                 27 ngày
    "curve_coefficient": 15.0,
    "curve_exponent": 1.45,
    "curve_break": 20,
    # Xấp xỉ khoảng cách level 19→20 (83, làm tròn lên 90) nên chỗ nối hai đoạn
    # không có bước nhảy. Con số này phải tính lại MỖI LẦN đổi hệ số hoặc số mũ:
    # bản đầu của kế hoạch ghi 1800 cho đường cong cũ trong khi bậc thật là 476,
    # và một bậc đột ngột đắt gấp bốn ngay tại điểm gãy rơi đúng vào người học
    # đã đi xa nhất.
    "curve_linear_step": 90,
    "max_level": 99,
}

# uuid CỐ ĐỊNH cho ba khe mặc định, không phải uuid ngẫu nhiên lúc seed.
#
# `xp_event.source_id` của một daily task sinh từ (người, ngày, id khe), nên id
# khe mà đổi giữa hai môi trường — hoặc đổi sau một lần seed lại — là trao thưởng
# lần nữa cho những ngày đã trao. Cố định thì seed lại bao nhiêu lần cũng vô hại.
SLOT_ID_REVIEW = uuid.UUID("2b1c0d4e-0000-5000-8000-000000000001")
SLOT_ID_DICTATION = uuid.UUID("2b1c0d4e-0000-5000-8000-000000000002")
SLOT_ID_TEST = uuid.UUID("2b1c0d4e-0000-5000-8000-000000000003")
SLOT_ID_GRAMMAR = uuid.UUID("2b1c0d4e-0000-5000-8000-000000000004")

DEFAULT_DAILY_TASK_SLOTS: tuple[dict[str, object], ...] = (
    {
        "id": SLOT_ID_REVIEW,
        "kind": "vocabulary_review",
        "label": "Ôn từ vựng",
        "target": 10,
        "xp": 10,
        "position": 1,
    },
    {
        "id": SLOT_ID_DICTATION,
        "kind": "dictation_complete",
        "label": "Nghe chép chính tả",
        "target": 3,
        "xp": 10,
        "position": 2,
    },
    {
        "id": SLOT_ID_TEST,
        "kind": "attempt_answer",
        "label": "Luyện đề",
        "target": 10,
        "xp": 10,
        "position": 3,
    },
    {
        "id": SLOT_ID_GRAMMAR,
        "kind": "grammar_lesson_complete",
        "label": "Học ngữ pháp",
        "target": 3,
        "xp": 10,
        "position": 4,
    },
)

DEFAULT_FRAME_TIERS: tuple[dict[str, object], ...] = (
    {"code": "bronze", "label": "Đồng", "min_level": 5, "tone": "ok", "ring": False},
    {"code": "silver", "label": "Bạc", "min_level": 10, "tone": "action", "ring": False},
    {"code": "gold", "label": "Vàng", "min_level": 20, "tone": "warn", "ring": False},
    {"code": "master", "label": "Bậc thầy", "min_level": 30, "tone": "action", "ring": True},
)

# (code, label, hint, icon, metric, target) — thứ tự hiển thị là thứ tự ở đây.
DEFAULT_BADGE_RULES: tuple[tuple[str, str, str, str, str, int], ...] = (
    ("first_steps", "Bước đầu tiên", "Ôn từ đầu tiên", "footprints", "reviews", 1),
    ("words_50", "50 từ", "Thuộc 50 từ", "book", "words_mastered", 50),
    ("words_150", "150 từ", "Thuộc 150 từ", "library", "words_mastered", 150),
    ("words_300", "300 từ", "Thuộc 300 từ", "graduation", "words_mastered", 300),
    ("dictation_10", "10 câu chép", "Chép đúng trọn 10 câu", "headphones", "dictation_items", 10),
    ("dictation_50", "50 câu chép", "Chép đúng trọn 50 câu", "headphones", "dictation_items", 50),
    ("first_test", "Đề đầu tiên", "Làm hết một lượt đề", "target", "tests_submitted", 1),
    ("test_700", "700 điểm", "Đạt 700 điểm quy đổi", "medal", "best_score", 700),
    ("test_850", "850 điểm", "Đạt 850 điểm quy đổi", "trophy", "best_score", 850),
    ("streak_7", "7 ngày liền", "Chuỗi 7 ngày học", "flame", "longest_streak", 7),
    ("streak_30", "30 ngày liền", "Chuỗi 30 ngày học", "flame", "longest_streak", 30),
    ("streak_100", "100 ngày liền", "Chuỗi 100 ngày học", "flame", "longest_streak", 100),
    ("level_5", "Level 5", "Đạt level 5", "star", "level", 5),
    ("level_10", "Level 10", "Đạt level 10", "sparkles", "level", 10),
    ("level_20", "Level 20", "Đạt level 20", "award", "level", 20),
)
