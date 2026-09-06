"""Schemas cho màn quản trị thành viên (`admin_users.py`)."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AdminUserPublic(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime
    ruby_balance: int
    # Lần thao tác cuối trên BẤT KỲ đường nào (đề thi, dictation, ngữ pháp,
    # phiên part, sổ ruby). NULL = tài khoản chưa làm gì.
    last_activity: datetime | None
    attempt_count: int


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="learner", pattern="^(learner|editor|admin)$")


class AdminUserEdit(BaseModel):
    role: str = Field(pattern="^(learner|editor|admin)$")


class RubyGrant(BaseModel):
    amount: int = Field(gt=0, le=10000)


class UserActivity(BaseModel):
    kind: str
    label: str
    at: datetime


class GrowthDay(BaseModel):
    day: str
    count: int


class AdminUserStats(BaseModel):
    total: int
    new_7d: int
    new_30d: int
    active_7d: int
    growth: list[GrowthDay]
