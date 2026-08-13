"""Hình dạng dữ liệu tầng AI gửi ra giao diện quản trị."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

__all__ = [
    "AiFeatureRow",
    "AiFeatureWrite",
    "KnownModel",
    "FacetAccuracy",
    "FacetCatalog",
    "LabelValue",
    "LlmStatsPublic",
    "QuestionLabelRow",
    "SkillTagRequestAck",
    "LabelWrite",
    "UsageRow",
]


class SkillTagRequestAck(BaseModel):
    queued: bool


class UsageRow(BaseModel):
    key: str
    calls: int
    cost_usd: Decimal
    prompt_tokens: int
    completion_tokens: int


class LabelValue(BaseModel):
    facet: str
    code: str
    # Nhãn MÁY đề xuất, giữ nguyên sau khi người sửa `code`. Chênh lệch giữa hai
    # trường này chính là KPI độ đúng.
    proposed_code: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


class LabelCatalogItem(BaseModel):
    code: str
    label_vi: str
    parts: list[int]


class FacetCatalog(BaseModel):
    key: str
    label_vi: str
    # "question" hoặc "set" — giao diện dùng nó để biết ô chọn này ghi vào đâu.
    owner: str
    labels: list[LabelCatalogItem]


class QuestionLabelRow(BaseModel):
    id: uuid.UUID
    part: int
    question_number: int | None
    prompt_text: str | None
    test_slug: str | None
    test_title: str | None
    set_id: uuid.UUID | None
    labels: list[LabelValue]
    # Nhãn của NGỮ LIỆU DÙNG CHUNG. Gửi kèm chứ không để giao diện tự tra: ba
    # câu cùng một hội thoại phải hiện cùng chủ đề, và cách chắc chắn nhất là
    # tất cả đọc từ một nguồn.
    set_labels: list[LabelValue]


class LabelWrite(BaseModel):
    """Ghi nhãn cho MỘT mặt.

    Một mặt mỗi lần, không phải cả bộ: người duyệt xác nhận từng mặt một, và gửi
    cả bộ sẽ khiến một mặt chưa xem cũng bị đóng dấu "đã kiểm".
    """

    facet: str = Field(min_length=1, max_length=24)
    code: str = Field(min_length=1, max_length=48)


class FacetAccuracy(BaseModel):
    facet: str
    label_vi: str
    labelled: int
    reviewed: int
    agreeing: int


class FacetShare(BaseModel):
    facet: str
    code: str
    label_vi: str
    count: int
    share: float


class LlmStatsPublic(BaseModel):
    total_calls: int
    ok_calls: int
    error_calls: int
    refused_calls: int
    cost_usd: Decimal
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    latency_p50_ms: int
    latency_p95_ms: int
    by_feature: list[UsageRow]
    by_model: list[UsageRow]
    # KPI độ đúng theo TỪNG MẶT. Một con số gộp cho cả sáu mặt che mất chuyện
    # máy đoán rất tốt dạng câu hỏi mà rất tệ điểm ngữ pháp — mà đó đúng là
    # thông tin quyết định nên sửa prompt nào.
    facets: list[FacetAccuracy]
    distribution: list[FacetShare]
    questions_total: int
    questions_labelled: int
    budget_hit_users: int


class KnownModel(BaseModel):
    provider: str
    model: str


class AiFeatureRow(BaseModel):
    key: str
    label_vi: str
    description_vi: str
    provider: str | None = None
    model: str | None = None
    enabled: bool = True
    # `null` nghĩa là chưa cấu hình riêng — tính năng rơi về bảng tầng ở biến
    # môi trường. Giao diện phải nói rõ điều đó chứ không hiện một ô trống, vì
    # ô trống đọc như "chưa dùng được" trong khi nó vẫn đang chạy.
    configured: bool = False
    updated_at: datetime | None = None
    updated_by: str | None = None


class AiFeatureWrite(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=64)
    enabled: bool = True
