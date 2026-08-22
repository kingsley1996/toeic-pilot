"""Hình dạng của cấu hình hệ level trên đường quản trị.

Tách khỏi `schemas/profile.py` vì hai bên phục vụ hai người khác nhau: phía kia
là thứ người học nhìn thấy (đã đo, đã kẹp, đã dịch sang chữ), còn ở đây là các
con số thô mà người vận hành sửa.

Mọi tập đóng đều kiểm ở tầng này chứ không bằng CHECK ở database: thêm một loại
việc hay một biểu tượng là sửa code (một phép đếm mới, một hình mới), nên bắt nó
đi kèm một migration là bắt phải trả giá hai lần cho cùng một thay đổi.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.profile import BadgeIcon, BadgeMetric, DailyTaskKind, FrameTone

__all__ = [
    "BadgeRuleAdmin",
    "BadgeRuleCreate",
    "BadgeRuleUpdate",
    "DailyTaskSlotAdmin",
    "DailyTaskSlotCreate",
    "DailyTaskSlotUpdate",
    "FrameTierAdmin",
    "FrameTierCreate",
    "FrameTierUpdate",
    "LevelTierAdmin",
    "LevelTierUpdate",
    "ProgressionConfigAdmin",
    "ProgressionSettingAdmin",
    "ProgressionSettingUpdate",
]


class ProgressionSettingAdmin(BaseModel):
    xp_vocabulary_review: int
    xp_dictation_complete: int
    xp_attempt_submit: int
    daily_xp_cap: int
    curve_coefficient: float
    curve_exponent: float
    curve_break: int
    curve_linear_step: int
    max_level: int
    updated_at: datetime


class ProgressionSettingUpdate(BaseModel):
    """Sửa một phần. Khoá vắng mặt = để nguyên, cùng luật với `PATCH /profile`.

    Giới hạn trên không phải để phòng kẻ xấu — đường này đã sau `require_role` —
    mà để chặn lỗi gõ phím. `xp_attempt_submit = 3000` không phải một quyết định
    vận hành, nó là một con số thừa số 0, và hậu quả của nó nằm vĩnh viễn trong
    sổ cái vì các hàng đã trao thì không sửa lại.
    """

    xp_vocabulary_review: int | None = Field(default=None, ge=0, le=100)
    xp_dictation_complete: int | None = Field(default=None, ge=0, le=100)
    xp_attempt_submit: int | None = Field(default=None, ge=0, le=500)
    daily_xp_cap: int | None = Field(default=None, ge=1, le=10_000)
    curve_coefficient: float | None = Field(default=None, gt=0, le=10_000)
    curve_exponent: float | None = Field(default=None, ge=1.0, le=3.0)
    curve_break: int | None = Field(default=None, ge=2, le=200)
    curve_linear_step: int | None = Field(default=None, ge=1, le=100_000)
    max_level: int | None = Field(default=None, ge=2, le=200)


class DailyTaskSlotAdmin(BaseModel):
    id: str
    kind: DailyTaskKind
    label: str
    target: int
    xp: int
    position: int
    enabled: bool


class DailyTaskSlotCreate(BaseModel):
    kind: DailyTaskKind
    label: str = Field(min_length=1, max_length=80)
    target: int = Field(ge=1, le=1000)
    xp: int = Field(ge=0, le=200)
    position: int = Field(default=0, ge=0, le=100)
    enabled: bool = True


class DailyTaskSlotUpdate(BaseModel):
    kind: DailyTaskKind | None = None
    label: str | None = Field(default=None, min_length=1, max_length=80)
    target: int | None = Field(default=None, ge=1, le=1000)
    xp: int | None = Field(default=None, ge=0, le=200)
    position: int | None = Field(default=None, ge=0, le=100)
    enabled: bool | None = None


class LevelTierAdmin(BaseModel):
    level: int
    xp_required: int


class LevelTierUpdate(BaseModel):
    """Ghi đè NGUYÊN bảng, không sửa từng hàng.

    Bảng ngưỡng chỉ đúng khi đọc như một khối: nó phải tăng đều và bắt đầu từ 0.
    Một endpoint sửa-một-bậc sẽ để bảng ở trạng thái không tăng đều giữa hai lần
    gọi, và trong khoảng đó mọi người học đọc ra một level sai — không lâu, nhưng
    đủ để `level_reached` ghi lại một mốc không có thật, và mốc đó thì vĩnh viễn.
    """

    tiers: list[LevelTierAdmin] = Field(min_length=1, max_length=200)


class FrameTierAdmin(BaseModel):
    code: str
    label: str
    min_level: int
    tone: FrameTone
    ring: bool
    image_storage_key: str | None
    image_url: str | None


class FrameTierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=80)
    min_level: int = Field(ge=1, le=200)
    tone: FrameTone
    ring: bool = False


class FrameTierUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    min_level: int | None = Field(default=None, ge=1, le=200)
    tone: FrameTone | None = None
    ring: bool | None = None
    image_storage_key: str | None = Field(default=None, max_length=255)
    """Khoá vắng mặt = để nguyên, `null` = gỡ ảnh. Cùng luật `exclude_unset` với
    `PATCH /profile`: một phép gộp `value or existing` không phân biệt được hai
    trường hợp đó, và cái hỏng thì im lặng — gỡ ảnh trả về 200 và không đổi gì."""


class BadgeRuleAdmin(BaseModel):
    code: str
    label: str
    hint: str
    icon: BadgeIcon
    image_storage_key: str | None
    image_url: str | None
    metric: BadgeMetric
    target: int
    position: int
    enabled: bool


class BadgeRuleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=80)
    hint: str = Field(min_length=1, max_length=160)
    icon: BadgeIcon
    metric: BadgeMetric
    target: int = Field(ge=1, le=1_000_000)
    position: int = Field(default=0, ge=0, le=200)
    enabled: bool = True


class BadgeRuleUpdate(BaseModel):
    """`code` KHÔNG sửa được sau khi tạo.

    Nó là thứ nằm trong `user_badge.code`, nên đổi mã là bỏ lại toàn bộ lịch sử
    dưới một cái tên không còn ai đọc — và huy hiệu quay về trạng thái "mới" với
    tất cả những người đã có nó. Muốn đổi tên hiển thị thì sửa `label`.
    """

    label: str | None = Field(default=None, min_length=1, max_length=80)
    hint: str | None = Field(default=None, min_length=1, max_length=160)
    icon: BadgeIcon | None = None
    image_storage_key: str | None = Field(default=None, max_length=255)
    """Khoá vắng mặt = để nguyên, `null` = gỡ ảnh."""
    metric: BadgeMetric | None = None
    target: int | None = Field(default=None, ge=1, le=1_000_000)
    position: int | None = Field(default=None, ge=0, le=200)
    enabled: bool | None = None


class ProgressionConfigAdmin(BaseModel):
    """Toàn bộ cấu hình trong MỘT lần đọc.

    Màn hình quản trị hiển thị cả bốn phần cùng lúc và chúng chỉ có nghĩa khi
    đứng cạnh nhau — một bậc khung ở level 30 là vô nghĩa nếu bảng level dừng ở
    25. Bốn request riêng cho một màn hình cũng là bốn trạng thái tải rời rạc.
    """

    setting: ProgressionSettingAdmin
    slots: list[DailyTaskSlotAdmin]
    levels: list[LevelTierAdmin]
    frames: list[FrameTierAdmin]
    badges: list[BadgeRuleAdmin]
