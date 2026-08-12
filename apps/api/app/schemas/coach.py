"""Hình dạng dữ liệu Coach gửi ra cho học viên."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

__all__ = ["CoachExplanationPublic", "CoachFeedbackWrite"]


class CoachExplanationPublic(BaseModel):
    id: uuid.UUID
    # Năm mục, không phải một khối văn xuôi: giao diện render theo mục, và bộ
    # eval kiểm được từng trường.
    body: dict[str, str]
    # Phiếu của CHÍNH người đang xem, không phải tổng phiếu. Hiện tổng sẽ là một
    # tín hiệu xã hội đẩy người sau bấm theo số đông, và làm hỏng đúng phép đo.
    helpful: bool | None = None


class CoachFeedbackWrite(BaseModel):
    explanation_id: uuid.UUID
    helpful: bool
