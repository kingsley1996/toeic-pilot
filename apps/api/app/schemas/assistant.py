"""Hình dạng dữ liệu Trợ lý trang web gửi ra cho học viên."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["AssistantAsk"]


class AssistantAsk(BaseModel):
    # Không nhận `question_id` hay `attempt_id`: trợ lý không neo vào lượt làm
    # bài, và nhận một id rồi lờ đi là mời client gửi ngữ cảnh mình tự bịa.
    message: str
