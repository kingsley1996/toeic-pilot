"""Nhà cung cấp giả — bản duy nhất bộ test được phép chạm tới.

Không phải để né việc kiểm thứ thật. Thứ đáng kiểm ở lát A là **quyết định**:
có vượt hạn mức không, chọn tầng nào, ghi được hàng nào, đầu ra có hợp schema
không. Không quyết định nào trong số đó cần một lượt đi mạng, và gắn chúng vào
một lượt đi mạng sẽ làm bộ test vừa chậm vừa chập chờn vừa tốn tiền.

Ngữ nghĩa thật của từng nhà cung cấp — structured output có ra đúng schema
không, tool calling có chạy không — là thứ **phải** kiểm bằng API thật, và được
kiểm một lần bằng tay rồi ghi lại, đúng như luật test ở `CLAUDE.md`.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from app.services.llm.base import LLMError, LLMRequest, LLMResult, Usage

__all__ = ["FakeProvider"]


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        *,
        reply: str | Callable[[LLMRequest], str] = "câu trả lời giả",
        usage: Usage | None = None,
        fail: Exception | None = None,
        latency_ms: int = 7,
    ) -> None:
        self._reply = reply
        self._usage = usage or Usage(prompt=100, completion=20)
        self._fail = fail
        self._latency_ms = latency_ms
        # Ghi lại mọi yêu cầu đã nhận, để test khẳng định được ĐIỀU GÌ đã được
        # gửi đi — đặc biệt là khẳng định nội dung học viên không lọt vào
        # `system`, thứ không kiểm được nếu chỉ nhìn đầu ra.
        self.seen: list[tuple[LLMRequest, str]] = []

    def complete(self, request: LLMRequest, model: str) -> LLMResult:
        self.seen.append((request, model))
        if self._fail is not None:
            raise LLMError(str(self._fail)) from self._fail
        text = self._reply(request) if callable(self._reply) else self._reply
        if request.schema is not None and not _is_json(text):
            raise LLMError("bản giả được yêu cầu trả JSON nhưng reply không phải JSON")
        return LLMResult(
            text=text,
            usage=self._usage,
            model=model,
            provider=self.name,
            latency_ms=self._latency_ms,
        )


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True
