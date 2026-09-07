"""Schemas cho bài test đầu vào (SPEC-PLACEMENT)."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class PlacementStart(BaseModel):
    """Điểm mốc tự khai trước khi làm — mốc so sánh, không phải dữ liệu chấm.

    `target_score` / `exam_date` người dùng điền ở đây là NGUỒN DUY NHẤT của
    mục tiêu ôn thi: route ghi thẳng vào `user_profile` (form đã prefill giá
    trị cũ, nên submit là một hành động nhìn thấy, không phải ghi đè sau lưng).
    """

    self_reported_score: int | None = Field(default=None, ge=10, le=990)
    target_score: int | None = Field(default=None, ge=10, le=990)
    exam_date: date | None = None

    @field_validator("exam_date")
    @classmethod
    def exam_date_not_past(cls, value: date | None) -> date | None:
        if value is not None and value < date.today():
            raise ValueError("ngày thi dự kiến không thể ở quá khứ")
        return value


class PlacementGate(BaseModel):
    """Trả lời cho câu "được làm bài test đầu vào không, khi nào làm lại được"."""

    can_start: bool
    next_available_at: datetime | None = None
    # Lượt đang dở (nếu có) — mở lại nó thay vì tạo lượt mới.
    in_progress_attempt_id: str | None = None
    latest_attempt_id: str | None = None
    # Kết quả gần nhất — dashboard hiện trình độ ngay trên đầu trang. NULL khi
    # chưa từng làm xong; trong khi lượt đang dở thì hai trường này vẫn NULL.
    latest_cefr_overall: str | None = None
    latest_total_low: int | None = None
    latest_total_high: int | None = None
    # Giá trị `user_profile` để PREFILL form điểm mốc — một nguồn sự thật: giá
    # trị cũ hiện sẵn, người dùng đổi thì submit ghi về lại profile.
    profile_target_score: int | None = None
    profile_exam_date: date | None = None


class PlacementBand(BaseModel):
    low: int
    high: int


class PlacementResultPublic(BaseModel):
    attempt_id: str
    estimator_version: str
    listening_raw: int
    reading_raw: int
    listening_band: PlacementBand
    reading_band: PlacementBand
    cefr_listening: str
    cefr_reading: str
    cefr_overall: str
    self_reported_score: int | None
    target_score: int | None
    # Thời gian đã dùng, để "làm nhanh hay chậm" đọc được ngay cạnh dải điểm —
    # same figure the mock-test result screen shows alongside the time limit.
    elapsed_seconds: int
    created_at: datetime
    # Đường dọc cho UI: mỗi kỹ năng, câu đúng / tổng — nguồn của phần điểm
    # mạnh / yếu ở màn kết quả.
    strengths: list[str] = []
    weaknesses: list[str] = []
