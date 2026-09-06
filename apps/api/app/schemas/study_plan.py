"""Schemas kế hoạch học (SPEC-PLACEMENT §6)."""

from datetime import date, datetime

from pydantic import BaseModel


class StudyPlanItemPublic(BaseModel):
    position: int
    kind: str
    part: int
    ref_id: str | None
    label: str
    reason: str | None
    # SUY từ bản ghi học thật lúc đọc (SPEC §6) — không phải cột tick.
    done: bool


class StudyPlanPublic(BaseModel):
    id: str
    placement_attempt_id: str
    target_score: int | None
    exam_date: date | None
    source: str
    created_at: datetime
    items: list[StudyPlanItemPublic]
    done_count: int
