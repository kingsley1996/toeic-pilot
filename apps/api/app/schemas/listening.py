"""Request/response cho Listening Lab (slice paste-YouTube-URL).

Tách khỏi `schemas/learning.py`: cây dictation cũ và lab của user là hai miền
riêng (nội dung biên soạn vs nội dung user tự tạo), trộn chung là ép người đọc
sau phân biệt bằng tên class.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.learning import WordDiff


class ListeningSourceIn(BaseModel):
    # Slice này chỉ nhận "youtube" — TikTok/Upload gửi lên nhận UNSUPPORTED từ
    # resolver, chứ không phải 422 của schema: user cần biết link họ đúng mà
    # tính năng chưa có.
    type: Literal["youtube", "tiktok", "upload"]
    url: str


class ListeningTranscriptIn(BaseModel):
    # Một parser xử cả hai (VTT là SRT thêm header + dấu chấm) — giữ trường này
    # để UI nói rõ đang gửi gì và log sau này biết sub nguồn nào hay hỏng.
    format: Literal["srt", "vtt"]
    raw: str


class ListeningCaptionsRequest(BaseModel):
    url: str


class ListeningCaptionsPublic(BaseModel):
    language: str
    kind: Literal["manual", "asr"]
    format: Literal["vtt"] = "vtt"
    raw: str
    segment_count: int
    title: str | None = None


class ListeningContentCreate(BaseModel):
    source: ListeningSourceIn
    title: str = Field(min_length=1, max_length=512)
    transcript: ListeningTranscriptIn


class ListeningSegmentPublic(BaseModel):
    id: str
    index: int
    start: float
    end: float
    text: str


class ListeningContentPublic(BaseModel):
    id: str
    source_type: str
    source_url: str
    external_id: str | None
    # URL phát file tự host (bài TikTok đã ingest) — NULL thì UI dùng embed
    # gốc + link ngoài như cũ.
    media_url: str | None = None
    title: str
    duration_seconds: int | None
    transcript_status: str
    segments: list[ListeningSegmentPublic]
    # Segment đã gõ đúng trọn (≥1 attempt is_complete của chính user) — list
    # riêng để trang học seeding highlight/reveal sau F5 mà không cần endpoint
    # progress mới. Tính lúc đọc (rẻ: 1 query distinct), không lưu riêng vì
    # derive được từ attempts và lưu là lệch đi theo thời gian.
    completed_segment_ids: list[str] = []
    created_at: datetime


class ListeningContentCreated(BaseModel):
    id: str
    status: str
    segment_count: int
    warnings: list[str] = []


class ListeningContentSummary(BaseModel):
    id: str
    title: str
    source_type: str
    # URL gốc để UI nhúng/oEmbed (TikTok không dựng lại URL xem được từ ID
    # như YouTube) — public như mọi field khác của thư viện.
    source_url: str
    external_id: str | None
    segment_count: int
    completed_count: int
    created_at: datetime


class ListeningContentAdmin(BaseModel):
    """Hàng thư viện cho màn admin: chỉ bài PUBLIC (bài riêng của user không
    bao giờ lọt vào đây — xem route). completed_count vô nghĩa ở góc nhìn
    toàn cục nên thay bằng attempt_count (tổng lượt học mọi user)."""

    id: str
    title: str
    source_type: str
    source_url: str
    external_id: str | None
    segment_count: int
    attempt_count: int
    owner_email: str
    is_public: bool
    created_at: datetime


class ListeningVisibilityUpdate(BaseModel):
    is_public: bool


class ListeningSegmentUpdate(BaseModel):
    # PUT admin là full-replace theo thứ tự list: có id = giữ + sửa câu cũ
    # (field nào vắng thì giữ nguyên), vắng id = thêm câu mới, câu cũ vắng mặt
    # trong list = xoá. UI luôn gửi toàn bộ transcript nên một list nói hết.
    id: uuid.UUID | None = None
    text: str | None = None
    start: float | None = None
    end: float | None = None


class ListeningContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    segments: list[ListeningSegmentUpdate] | None = None


class ListeningAttemptSubmit(BaseModel):
    segment_id: uuid.UUID
    answer: str = ""
    time_spent_seconds: int | None = Field(default=None, ge=0)


class ListeningAttemptResult(BaseModel):
    attempt_id: str
    is_correct: bool
    # `accuracy` của bộ chấm dictation (matched/expected*100) — đóng vai
    # `similarity` của SPEC, không đẻ khái niệm mới cho cùng một con số.
    similarity: str
    expected_text: str
    diff: list[WordDiff]
