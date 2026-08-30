"""Adapter OpenRouter — một cổng, nhiều model, gồm cả model miễn phí.

Dựng bằng `httpx` thẳng, không SDK (ADR-003 §3.1). Toàn bộ adapter là dựng một
payload JSON và đọc kết quả về `LLMResult`; một lớp trừu tượng hoá SDK ở đây sẽ
dài hơn chính nó.

**KHÔNG gửi `response_format`.** Hai lý do độc lập, và lý do thứ hai mới là lý
do thật:

1. Model miễn phí và model chạy tại máy hỗ trợ tham số này rất khác nhau, và
   nhà cung cấp nào không hiểu thì trả 400 — tức là ràng buộc schema phía họ
   biến thành một lỗi vận hành thay vì một bảo đảm.
2. Ngay cả khi họ ép được schema, nó **vẫn không bảo đảm nội dung đúng**: một
   nhãn `"grammar_tenses"` là JSON hợp lệ, đúng kiểu chuỗi, và vẫn không nằm
   trong danh sách đóng của ta. Ta buộc phải tự kiểm dù thế nào — nên ràng buộc
   phía nhà cung cấp giỏi lắm là một lớp thừa.

Vậy nên: yêu cầu JSON bằng lời trong prompt, rồi **tự kiểm và thử lại một lần**.
Cách này chạy trên mọi model, kể cả Ollama.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from app.services.llm.base import (
    LLMError,
    LLMQuotaExhausted,
    LLMRequest,
    LLMResult,
    Usage,
    tool_calls_from_openai,
)

__all__ = ["OpenRouterProvider"]

_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key: str, *, timeout_s: float = 90.0) -> None:
        self._key = api_key
        # Timeout mặc định của httpx là 5 giây — quá ngắn cho một lượt sinh văn,
        # và model miễn phí thường phải xếp hàng. Đặt rõ ràng thay vì để nó
        # hỏng theo cách trông như lỗi mạng.
        self._timeout = timeout_s

    def complete(self, request: LLMRequest, model: str) -> LLMResult:
        if request.messages is not None:
            messages: list[dict[str, Any]] = list(request.messages)
        else:
            messages = [
                {"role": "system", "content": request.system},
                # Nội dung do người dùng cung cấp CHỈ đi vào vai trò này. Đây là
                # chỗ duy nhất luật đó được thi hành trong adapter.
                {"role": "user", "content": request.user},
            ]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            payload["tools"] = request.tools
        started = perf_counter()
        try:
            response = httpx.post(
                _URL,
                json=payload,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    # OpenRouter dùng hai header này để ghi công. Không bắt buộc,
                    # nhưng thiếu thì một số model miễn phí bị hạ ưu tiên.
                    "HTTP-Referer": "https://github.com/toeic-pilot",
                    "X-Title": "TOEIC Pilot",
                },
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"không gọi được OpenRouter: {exc}") from exc

        if response.status_code != 200:
            body = response.text
            # OpenRouter dùng CÙNG mã 429 cho hai chuyện rất khác nhau: nhóm
            # dùng chung của model miễn phí đang quá tải (lùi vài giây là qua),
            # và hạn mức ngày của tài khoản đã cạn (chờ tới sáng mai). Chỉ có
            # `limit_source` trong thân phản hồi phân biệt được.
            if response.status_code == 429 and (
                "free-models-per-day" in body or "openrouter_free_tier_daily" in body
            ):
                raise LLMQuotaExhausted(
                    "Hết hạn mức model miễn phí trong ngày của OpenRouter. "
                    "Chờ tới lúc reset, nạp credit, hoặc đổi nhà cung cấp."
                )
            raise LLMError(f"OpenRouter {response.status_code}: {body[:400]}")

        body = response.json()
        # Model miễn phí thỉnh thoảng trả 200 kèm một khối `error` thay vì
        # `choices` — hết hạn mức, model đang bận. Không kiểm thì nó nổ thành
        # KeyError ở dòng dưới, và thông báo sẽ không nói gì về nguyên nhân.
        if "choices" not in body:
            raise LLMError(f"OpenRouter trả 200 nhưng không có choices: {str(body)[:400]}")

        usage = body.get("usage") or {}
        return LLMResult(
            text=body["choices"][0]["message"]["content"] or "",
            usage=Usage(
                prompt=int(usage.get("prompt_tokens", 0)),
                completion=int(usage.get("completion_tokens", 0)),
            ),
            model=model,
            provider=self.name,
            latency_ms=int((perf_counter() - started) * 1000),
            tool_calls=tool_calls_from_openai(body["choices"][0]["message"]),
        )
