"""Adapter Ollama — model chạy trên máy, không mạng, không hạn mức.

Vì sao có mặt: tier miễn phí của OpenRouter cho **50 lượt/ngày**, mà một lượt
gắn nhãn 40 câu đã cần 40–60 lượt và một đề 200 câu cần 200–300. Con số đó
không đủ cho lát B, và phát hiện ra điều đó tốn đúng một ngày hạn mức.

Cũng khớp với quyết định đã chốt ở ADR-003 §3.2: embedding chạy offline bằng
model mã nguồn mở, nên máy soạn nội dung sẽ cần bộ công cụ này dù thế nào.

**`base_url` là cấu hình, không phải hằng số**, và lý do rất cụ thể: pipeline
chạy từ dòng lệnh trên host thì Ollama ở `localhost:11434`, còn worker chạy
trong container thì `localhost` là chính container đó — phải là
`host.docker.internal:11434`. Nhét `localhost` vào mã sẽ cho một lỗi "connection
refused" chỉ xảy ra trong container, tức là chỉ xảy ra ở nơi khó gỡ nhất.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from app.services.llm.base import LLMError, LLMRequest, LLMResult, ToolCall, Usage

__all__ = ["OllamaProvider"]


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, *, timeout_s: float = 300.0) -> None:
        self._base = base_url.rstrip("/")
        # Rộng tay hơn nhiều so với adapter gọi API: một model 3GB trên CPU có
        # thể mất hàng chục giây cho lượt đầu vì phải nạp trọng số vào bộ nhớ.
        # Timeout chặt ở đây sẽ biến "đang nạp model" thành "nhà cung cấp hỏng".
        self._timeout = timeout_s

    def complete(self, request: LLMRequest, model: str) -> LLMResult:
        if request.messages is not None:
            messages: list[dict[str, Any]] = list(request.messages)
        else:
            messages = [
                {"role": "system", "content": request.system},
                # Nội dung người dùng CHỈ đi vào vai trò này — cùng ranh giới an
                # toàn mà mọi adapter khác giữ.
                {"role": "user", "content": request.user},
            ]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.tools:
            # `/api/chat` bản địa của Ollama nhận `tools` cùng schema OpenAI và
            # trả `message.tool_calls` với `arguments` là DICT (đã parse sẵn) —
            # khác giao thức OpenAI trả chuỗi JSON, nên phải serialize lại.
            payload["tools"] = request.tools
        # `format: json` của Ollama ép đầu ra là JSON hợp lệ. Bật nó vì nó rẻ và
        # bỏ được cái rào ```json mà model hay thêm — nhưng KHÔNG thay cho việc
        # tự kiểm: JSON hợp lệ vẫn có thể mang một nhãn không nằm trong danh
        # sách đóng, và đó mới là phép kiểm quan trọng.
        if request.schema is not None:
            payload["format"] = "json"

        started = perf_counter()
        try:
            response = httpx.post(f"{self._base}/api/chat", json=payload, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise LLMError(f"không gọi được Ollama tại {self._base}: {exc}") from exc

        if response.status_code != 200:
            raise LLMError(f"Ollama {response.status_code}: {response.text[:400]}")

        body = response.json()
        if "message" not in body:
            raise LLMError(f"Ollama trả 200 nhưng không có message: {str(body)[:300]}")

        import json as _json

        tool_calls = tuple(
            ToolCall(
                id=str(call.get("id") or ""),
                name=str((call.get("function") or {}).get("name") or ""),
                arguments=_json.dumps(
                    (call.get("function") or {}).get("arguments") or {}, ensure_ascii=False
                ),
            )
            for call in (body["message"].get("tool_calls") or [])
        )
        return LLMResult(
            text=body["message"].get("content") or "",
            usage=Usage(
                # Ollama gọi hai trường này là `prompt_eval_count` và
                # `eval_count`. Đọc đúng tên chứ không để mặc định 0: chi phí ở
                # đây bằng 0 thật, nhưng SỐ TOKEN vẫn là dữ liệu — nó là thứ để
                # ngoại suy hoá đơn nếu sau này đổi sang model tính tiền.
                prompt=int(body.get("prompt_eval_count", 0)),
                completion=int(body.get("eval_count", 0)),
            ),
            model=model,
            provider=self.name,
            latency_ms=int((perf_counter() - started) * 1000),
            tool_calls=tool_calls,
        )
