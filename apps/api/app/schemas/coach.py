"""Hình dạng dữ liệu Coach gửi ra cho học viên."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

__all__ = [
    "ChatAsk",
    "ChatMessagePublic",
    "ChatTurn",
    "CoachExplanationPublic",
    "CoachFeedbackWrite",
]


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


class ChatAsk(BaseModel):
    # Neo vào một câu cụ thể, hoặc `None` để hỏi về cả lượt làm bài. Client gửi
    # ID, máy chủ tự tra nội dung — nhận ngữ cảnh do client gửi lên là để người
    # khác tự viết đề bài cho model.
    question_id: uuid.UUID | None = None
    message: str


class ChatMessagePublic(BaseModel):
    id: uuid.UUID
    role: str
    content: str


class ChatTurn(BaseModel):
    conversation_id: uuid.UUID
    question: ChatMessagePublic
    answer: ChatMessagePublic
