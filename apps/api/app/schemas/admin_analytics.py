"""Dashboard phân tích chất lượng đề: độ khó, taxonomy, media, so sánh liên đề.

Chỉ ĐỌC: mọi endpoint là SELECT (+ đọc blueprint.json trên đĩa). Không có gì ở
đây ghi vào database, nên không có gì phải "duyệt" hay "phát hành".
"""

from pydantic import BaseModel, Field


class PartKey(BaseModel):
    part: int
    count: int
    answers: dict[str, int] = Field(default_factory=dict)
    difficulty: dict[str, int] = Field(default_factory=dict)
    hard_planned: int | None = None
    audio_covered: int = 0
    image_covered: int = 0
    explained: int = 0


class FacetCodeCount(BaseModel):
    code: str
    label_vi: str
    count: int


class FacetKey(BaseModel):
    facet: str
    label_vi: str
    codes: list[FacetCodeCount] = Field(default_factory=list)
    missing: int = 0


class ReviewKey(BaseModel):
    labels_total: int = 0
    reviewed: int = 0
    agree: int = 0


class PerformanceKey(BaseModel):
    attempts: int = 0
    avg_p: float | None = None
    per_part: dict[str, float | None] = Field(default_factory=dict)


class AnalyticsFlag(BaseModel):
    code: str
    message: str
    part: int | None = None


class TestAnalytics(BaseModel):
    slug: str
    title: str
    kind: str
    status: str
    total: int
    parts: list[PartKey] = Field(default_factory=list)
    facets: list[FacetKey] = Field(default_factory=list)
    review: ReviewKey = Field(default_factory=ReviewKey)
    performance: PerformanceKey = Field(default_factory=PerformanceKey)
    flags: list[AnalyticsFlag] = Field(default_factory=list)


class TestAnalyticsRow(BaseModel):
    slug: str
    title: str
    kind: str
    status: str
    total: int


class CompareOut(BaseModel):
    tests: list[TestAnalytics] = Field(default_factory=list)
