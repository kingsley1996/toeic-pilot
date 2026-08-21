from datetime import date
from typing import Annotated, Literal, get_args
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, Field

from app.core.media import AUDIO_ACCENTS
from app.models.profile import (
    MAX_DISPLAY_NAME,
    MAX_TARGET_SCORE,
    MIN_TARGET_SCORE,
    TARGET_SCORE_STEP,
)

SUPPORTED_LOCALES = ("vi", "en")

# Mascot của Petland. Danh sách sống ở ĐÂY chứ không ở frontend, dù ảnh thì nằm
# bên đó: khai báo kiểu này đi qua OpenAPI thành một union TypeScript, nên bảng
# `Record<PetId, Mascot>` bên frontend thiếu một con là lỗi `tsc` chứ không phải
# một `undefined` lộ ra lúc chạy. Thêm mascot mới thì sửa ở đây trước.
PetId = Literal["cat", "rex"]
PETS: tuple[str, ...] = get_args(PetId)


def _known_timezone(value: str) -> str:
    # Checked against the system's own IANA database rather than a list we keep,
    # because a list we keep goes stale the next time a country changes its rules.
    # `available_timezones()` builds a set, so it is looked up once per call and
    # not worth caching for a field that changes about once per user per lifetime.
    if value not in available_timezones():
        raise ValueError(f"Unknown time zone: {value}")
    return value


def _whole_step_score(value: int) -> int:
    if value % TARGET_SCORE_STEP != 0:
        raise ValueError(
            f"TOEIC scores go in steps of {TARGET_SCORE_STEP}; {value} is not one that exists."
        )
    return value


TimeZone = Annotated[str, Field(max_length=64), AfterValidator(_known_timezone)]
TargetScore = Annotated[
    int, Field(ge=MIN_TARGET_SCORE, le=MAX_TARGET_SCORE), AfterValidator(_whole_step_score)
]
DisplayName = Annotated[str, Field(min_length=1, max_length=MAX_DISPLAY_NAME)]


class UserProfilePublic(BaseModel):
    """A learner's own profile. Never anyone else's — nothing here is public in
    the sense of being visible to other users, and no endpoint serves it by id.
    """

    display_name: str | None
    timezone: str
    locale: str
    target_score: int | None
    exam_date: date | None
    minutes_per_day: int | None
    daily_new_limit: int | None
    preferred_accent: str | None
    # NULL nghĩa là "chưa chọn", và frontend rơi về con mặc định của nó. Không
    # điền sẵn một con ở đây: xem chú thích trên cột `pet` của model.
    pet: PetId | None
    # URL, không phải `storage_key`. Frontend không bao giờ được tự ghép URL từ
    # khoá: chỉ driver biết tiền tố thư mục mà Cloudinary đòi, và ghép ở phía
    # client nghĩa là quy tắc đó bị nhân bản ra một nơi không có test nào phủ.
    avatar_url: str | None


class AvatarConfirm(BaseModel):
    storage_key: str


class UserProfileUpdate(BaseModel):
    """A partial update. Every field is optional in two different ways.

    `None` means **clear this**, and an absent key means **leave it alone**. They
    are not the same thing, and a plain `field or existing` merge cannot tell them
    apart — which is how "xoá ngày thi" turns into a no-op that nobody reports.
    The route reads `model_dump(exclude_unset=True)` so absence stays visible.

    `timezone` and `locale` are `NOT NULL` in the table, so they take a value or
    stay as they are; there is no meaningful "no time zone".
    """

    display_name: DisplayName | None = None
    timezone: TimeZone | None = None
    locale: str | None = Field(default=None, pattern="^(" + "|".join(SUPPORTED_LOCALES) + ")$")
    target_score: TargetScore | None = None
    exam_date: date | None = None
    minutes_per_day: int | None = Field(default=None, ge=5, le=480)
    daily_new_limit: int | None = Field(default=None, ge=1, le=200)
    preferred_accent: str | None = Field(
        default=None, pattern="^(" + "|".join(AUDIO_ACCENTS) + ")$"
    )
    pet: PetId | None = None


class StudyDay(BaseModel):
    """One day of activity, in the learner's own time zone."""

    date: date
    reviews: int
    dictation_items: int


class LearningStats(BaseModel):
    """Derived on read, every time, from the attempt and review tables.

    There is no statistics table and there should not be one. The same reasoning
    is already written on `StoryProgress` and `VocabularyProgress`: a counter
    maintained alongside the history drifts from it the first time a row is
    deleted or re-graded, and nothing anywhere reports the disagreement.
    """

    vocabulary_total: int
    vocabulary_mastered: int
    vocabulary_due: int
    reviews_total: int
    dictation_completed: int
    dictation_attempts: int
    # Consecutive days up to and including today, counted in `timezone`. A streak
    # computed in UTC breaks for every learner who studies in the evening, since
    # their day ends at 17:00 UTC.
    current_streak: int
    longest_streak: int
    active_days: int

    # Hôm nay THEO MÚI GIỜ CỦA HỌC VIÊN. Gửi kèm chứ không để trình duyệt tự
    # tính: lưới lịch phải khớp với chuỗi ngày ở trên, mà chuỗi ngày do máy chủ
    # tính. Để hai bên tự tính riêng thì đồng hồ lệch hoặc múi giờ trình duyệt
    # khác múi giờ hồ sơ là ô "hôm nay" nằm sai cột, không ai báo.
    today: date
    window_days: int
    # THƯA — chỉ những ngày CÓ hoạt động. Một năm đặc là 365 hàng mà phần lớn
    # toàn số 0; lưới là thứ trình duyệt dựng được từ `today` và `window_days`.
    calendar: list[StudyDay]


__all__ = [
    "LearningStats",
    "StudyDay",
    "PETS",
    "PetId",
    "SUPPORTED_LOCALES",
    "UserProfilePublic",
    "UserProfileUpdate",
]
