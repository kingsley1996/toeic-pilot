from datetime import date, datetime
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
    tour_done: bool
    """Đã xem tour giới thiệu chưa.

    Gửi ra dạng `bool` chứ không gửi cả mốc thời gian: frontend chỉ có một câu
    hỏi ở đây — chạy tour hay không. Mốc thật nằm ở cột `toured_at` và dùng để
    trả lời một câu khác (bao nhiêu người mới xem tới cuối), mà câu ấy hỏi ở
    database chứ không hỏi qua endpoint này.
    """


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
    grammar: int


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
    "BadgeIcon",
    "BadgeMetric",
    "BadgePublic",
    "BadgesPublic",
    "LearningStats",
    "StudyDay",
    "DailyTaskPublic",
    "DailyTaskKind",
    "DailyTasksPublic",
    "FramePublic",
    "FrameTone",
    "PETS",
    "ProgressionPublic",
    "PetId",
    "SUPPORTED_LOCALES",
    "UserProfilePublic",
    "UserProfileUpdate",
]


# Token màu của khung avatar. CHỈ token đã có trong design system: một ô nhập mã
# màu tự do là đường ngắn nhất tới một khung không đọc được ở chế độ tối, nơi
# không ai kiểm trước khi lưu. Thang bốn accent vắng mặt có chủ ý — nó phân loại
# giọng đọc, mượn sang bậc level là bắt một màu mang hai nghĩa.
FrameTone = Literal["ok", "action", "warn", "alert"]


class FramePublic(BaseModel):
    """Khung avatar đang mở, hoặc vắng mặt khi chưa tới bậc nào.

    Trả về cả CÁCH VẼ chứ không chỉ mã: bậc khung là dữ liệu admin thêm được, nên
    một bảng tra mã→màu nằm trong frontend sẽ thiếu ngay khi có bậc mới, và thiếu
    một cách im lặng (khung không hiện, không ai báo).
    """

    code: str
    label: str
    min_level: int
    tone: FrameTone
    ring: bool
    image_url: str | None
    """Tranh khung, nếu đã tải lên. Có ảnh thì ảnh THẮNG `tone`.

    `tone` vẫn gửi kèm chứ không biến mất: nó là thứ vẽ được ngay, còn ảnh thì
    phải tải về. Bỏ nó đi nghĩa là khung không tồn tại cho tới khi ảnh xong, và
    với kết nối chậm đó là một avatar nhấp nháy đổi hình.
    """


class ProgressionPublic(BaseModel):
    """Level của một học viên, suy ra từ sổ cái `xp_event`.

    Không có cột nào lưu `level` hay `xp_total`. Xem `app/models/progression.py`
    để biết vì sao một bộ đếm cộng dồn không được phép tồn tại ở đây.
    """

    xp_total: int
    level: int
    xp_into_level: int
    """0 khi đã kịch trần level."""
    xp_for_next: int
    frame: FramePublic | None
    xp_today: int
    daily_cap: int


# Loại việc mà hệ thống biết ĐO. Literal chứ không str: nó đi qua OpenAPI thành
# union TypeScript, nên frontend thiếu một loại là lỗi `tsc`.
#
# Danh sách KHE thì không còn cố định — khe là hàng trong `daily_task_slot` và
# admin thêm/sửa/tắt được. Cái đóng lại là loại việc, vì mỗi loại là một phép
# đếm có thật trong `app/services/daily_tasks.py`.
DailyTaskKind = Literal[
    "vocabulary_review", "dictation_complete", "attempt_answer", "grammar_attempt"
]


class DailyTaskPublic(BaseModel):
    """Một việc hôm nay.

    `target` là số CỐ ĐỊNH đã kẹp theo thứ thật sự có, không phải tình trạng hiện
    thời — xem `app/services/daily_tasks.py`. `progress` đếm hoạt động trong ngày
    nên nó chỉ tăng.
    """

    slot_id: str
    """uuid của HÀNG cấu hình. Đi vào `xp_event.source_id`, nên nó bền qua mọi
    lần đổi nhãn hay đổi mục tiêu — đó là điều khiến sửa cấu hình không trao
    thưởng lại cho những ngày đã trao."""
    kind: DailyTaskKind
    label: str
    """Chữ hiển thị, do admin đặt. Frontend chỉ quyết định biểu tượng và lối đi
    (theo `kind`), không quyết định tên."""
    target: int
    progress: int
    done: bool
    xp: int


class DailyTasksPublic(BaseModel):
    date: date
    """Hôm nay THEO MÚI GIỜ NGƯỜI HỌC, do máy chủ quyết định.

    Trình duyệt không được tự gọi `new Date()` ở đây: nếu múi giờ máy khác múi
    giờ hồ sơ thì danh sách việc sẽ lệch một ngày so với chuỗi ngày, và không có
    gì báo. Cùng lý do `LearningStats.today` tồn tại.
    """
    tasks: list[DailyTaskPublic]
    xp_awarded: int
    """XP vừa được trao trong chính lần đọc này, nếu có việc mới hoàn thành."""
    ruby_awarded: int
    """Ruby vừa được trao trong chính lần đọc này — xong CẢ BA việc, hoặc chuỗi
    ngày vừa chạm một mốc bảy ngày.

    Tách khỏi `xp_awarded` chứ không cộng chung: hai đơn vị đo hai thứ khác nhau
    (khối lượng và việc làm xong), và một tổng gộp là chỗ người dùng thôi phân
    biệt được chúng — đúng thứ ADR-011 §1 dựng cả hệ này để tránh."""


# Biểu tượng mà frontend biết vẽ. Đây là thứ DUY NHẤT còn đóng ở phía huy hiệu:
# `code` giờ là dữ liệu (admin thêm huy hiệu mới), nên `Record<BadgeCode, …>` với
# kiểm tra đủ-mã ở `tsc` không còn khả thi — đánh đổi có chủ ý để đổi lấy việc
# thêm huy hiệu không cần triển khai lại. Bù vào đó, `icon` là union: một huy
# hiệu không có hình là lỗi biên dịch chứ không phải một ô trống trên trang.
BadgeIcon = Literal[
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
]

# Số đo mà một luật badge so ngưỡng. Đóng vì mỗi số đo là một phép đếm có thật.
BadgeMetric = Literal[
    "reviews",
    "words_mastered",
    "dictation_items",
    "tests_submitted",
    "best_score",
    "longest_streak",
    "level",
]


class BadgePublic(BaseModel):
    """Một badge, kèm tiến độ tới ngưỡng của nó.

    `target` và `progress` gửi từ máy chủ chứ không để frontend tự biết ngưỡng:
    ngưỡng là một phần của điều kiện, và một bản sao ở phía trình duyệt sẽ trôi
    khỏi bản gốc mà không có gì báo — trang badge in "120/300" trong khi máy chủ
    đã mở badge từ 150.

    `label` và `hint` đi kèm vì chúng là DỮ LIỆU do admin đặt, không phải chữ cố
    định trong frontend. `icon` thì vẫn là một union đóng — frontend phải biết vẽ
    nó, và một chuỗi tự do ở đây là một huy hiệu không có hình.
    """

    code: str
    label: str
    hint: str
    icon: BadgeIcon
    image_url: str | None
    """Tranh huy hiệu, nếu đã tải lên. Thắng `icon` khi hiển thị."""
    target: int
    progress: int
    """Đã kẹp ở `target` — con số đáng nói là ngưỡng, không phải tổng tài sản."""
    earned: bool
    awarded_at: datetime | None
    """Lần đầu HỆ THỐNG nhìn thấy badge này, không phải lúc đạt điều kiện.

    Với tài khoản có sẵn lịch sử, hai mốc đó cách nhau rất xa: điều kiện có thể
    đã đạt từ nhiều tháng trước, còn hàng thì chỉ được ghi ở lần đọc đầu tiên sau
    khi tính năng ra mắt. Đừng in nó ra như "ngày đạt được".
    """
    seen: bool


class BadgesPublic(BaseModel):
    badges: list[BadgePublic]
    earned_count: int
    unseen_count: int
    """Số badge đã mở mà người dùng chưa xem — nguồn của chấm đỏ.

    Giao diện phải gộp chúng thành MỘT thông báo. Tài khoản cũ mở một loạt cùng
    lúc ở lần đọc đầu tiên, và mười thông báo liên tiếp đọc như hệ thống hỏng.
    """
