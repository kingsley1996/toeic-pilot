"""Một adapter cho MỌI nhà cung cấp nói giao thức OpenAI.

Groq, Cerebras, Google (Gemini qua điểm cuối tương thích), Mistral, DeepSeek,
Together — tất cả nhận cùng một payload `chat/completions` và khác nhau đúng
**một `base_url`**. Nên ở đây là một adapter cộng một bảng tra tên → endpoint,
không phải sáu tệp gần giống nhau.

Cùng hình dạng với quyết định đã chốt ở `ADR-006` §2.8: **một driver `s3` phủ sáu
nhà cung cấp, và `S3_ENDPOINT_URL` quyết định đó là ai**. Đổi nhà cung cấp là đổi
một dòng env, không phải viết thêm một lớp.

**Không gửi `response_format`**, cùng lý do đã ghi ở adapter OpenRouter: nhà cung
cấp nào không hiểu thì trả 400, và ngay cả khi hiểu thì nó vẫn không bảo đảm nội
dung nằm trong tập đóng của ta — ta buộc phải tự kiểm dù thế nào.
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

__all__ = ["ENDPOINTS", "OpenAICompatibleProvider"]

# Tên nhà cung cấp → gốc API. Tên ở đây chính là phần trước dấu `/` trong
# `LLM_TIER_STRONG`, ví dụ `groq/llama-3.3-70b-versatile`.
#
# Ba endpoint này lấy từ tài liệu chính thức của từng bên (kiểm 2026-08-22), chứ
# không suy từ trí nhớ: một `base_url` sai không hỏng lúc build, nó hỏng ở lượt
# gọi đầu tiên với một lỗi DNS hoặc 404 chẳng nói gì về nguyên nhân.
ENDPOINTS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    # Cổng gộp nhiều model mở. `opencode` trên máy này đã đăng nhập sẵn vào nó,
    # nên khoá lấy từ `~/.local/share/opencode/auth.json` hoặc từ .env — cùng
    # một khoá, hai chỗ đọc.
    "tokenrouter": "https://api.tokenrouter.com/v1",
}


class OpenAICompatibleProvider:
    """Một nhà cung cấp cụ thể. `name` đi vào sổ cái và vào bảng giá."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        *,
        timeout_s: float = 300.0,
        extra_payload: dict[str, object] | None = None,
    ) -> None:
        self.name = name
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._extra = extra_payload or {}
        # Mặc định của httpx là 5 giây, và 90 giây cũng vẫn ngắn: đo với
        # `qwen3.8-max-free` thì một lượt sinh một câu hỏi mất ~2,5 phút, vì
        # model suy luận viết hàng nghìn token suy nghĩ trước khi trả lời. Cả
        # hai mốc đó đều hỏng theo cách trông như lỗi mạng chứ không như "model
        # đang nghĩ", nên người đọc lỗi sẽ đi tìm sai chỗ.
        self._timeout = timeout_s

    def complete(self, request: LLMRequest, model: str) -> LLMResult:
        if request.messages is not None:
            # Vòng tool: nơi dựng messages chịu trách nhiệm luật an toàn (xem
            # docstring `LLMRequest.messages`) — adapter gửi nguyên trạng.
            messages: list[dict[str, Any]] = list(request.messages)
        else:
            messages = [
                {"role": "system", "content": request.system},
                # Nội dung do người dùng cung cấp CHỈ đi vào vai trò này — ranh
                # giới an toàn duy nhất mà adapter có thể thi hành.
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
        payload.update(self._extra)
        started = perf_counter()
        try:
            response = httpx.post(
                self._url,
                json=payload,
                timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._key}"},
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"không gọi được {self.name}: {exc}") from exc

        if response.status_code != 200:
            body = response.text
            if response.status_code == 402:
                # "Payment required" KHÔNG bao giờ tự hết bằng cách thử lại.
                # Dịch nó thành lỗi thường nghĩa là vòng lặp ở tầng trên đi hết
                # 30 ô, hỏng y hệt nhau, và dòng nói đúng nguyên nhân bị chôn
                # dưới 29 dòng giống hệt. Cùng lập luận với hạn mức ngày.
                #
                # Gặp thật ở Cerebras: khoá xác thực được, `GET /models` trả 200,
                # nhưng mọi lượt suy luận trả 402 — tức là hợp lệ mà không có
                # quyền chạy. Không phân biệt thì triệu chứng đọc ra là "adapter
                # hỏng" chứ không phải "tài khoản chưa có hạn mức".
                raise LLMQuotaExhausted(
                    f"{self.name} từ chối: tài khoản chưa có hạn mức suy luận "
                    f"(402 payment required). Bật gói dùng thử hoặc nạp credit."
                )
            if response.status_code == 429:
                # Phân biệt hạn mức CẠN với quá tải tạm thời, cùng lý do đã ghi
                # ở adapter OpenRouter: một hạn mức ngày không tự hết sau ba
                # mươi giây, nên backoff sẽ cày hết mọi việc còn lại và hỏng y
                # hệt nhau, chôn mất dòng nói đúng nguyên nhân.
                #
                # Không nhà cung cấp nào trong bảng này có trường máy đọc được
                # để phân biệt, nên phải dò chữ. Dò TRẬT thì rơi về `LLMError`,
                # tức là thử lại — hướng hỏng ít tệ hơn.
                lowered = body.lower()
                if any(
                    mark in lowered
                    for mark in ("per day", "daily", "quota", "free_tier", "exceeded your current")
                ):
                    raise LLMQuotaExhausted(
                        f"Hết hạn mức của {self.name} trong ngày. Chờ reset, nạp credit, "
                        f"hoặc đổi nhà cung cấp."
                    )
            raise LLMError(f"{self.name} {response.status_code}: {body[:400]}")

        body_json = response.json()
        if "choices" not in body_json:
            # Một số nhà cung cấp trả 200 kèm khối `error` thay vì `choices`.
            # Không kiểm thì nó nổ thành KeyError ở dòng dưới, và thông báo sẽ
            # không nói gì về nguyên nhân.
            raise LLMError(f"{self.name} trả 200 nhưng không có choices: {str(body_json)[:400]}")

        choice = body_json["choices"][0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        if not text:
            # Model suy luận có thể tiêu HẾT hạn mức đầu ra vào phần suy nghĩ và
            # trả về `content` rỗng kèm `reasoning_content` dài. Đo thật với
            # `qwen3.8-max-free`: 2 600 token đầu ra, `reasoning_content` 10 862
            # ký tự, `content` rỗng.
            #
            # Không nói ra thì lỗi này đội lốt "model trả lời sai định dạng", và
            # người sửa sẽ đi chỉnh prompt — trong khi thứ cần chỉnh là `max_tokens`.
            reasoning = message.get("reasoning_content") or ""
            if choice.get("finish_reason") == "length" and reasoning:
                raise LLMError(
                    f"{self.name}: hết hạn mức đầu ra khi đang suy luận "
                    f"({len(reasoning)} ký tự suy nghĩ, chưa kịp trả lời). Tăng `max_tokens`."
                )

        usage = body_json.get("usage") or {}
        return LLMResult(
            text=text,
            usage=Usage(
                prompt=int(usage.get("prompt_tokens", 0)),
                completion=int(usage.get("completion_tokens", 0)),
            ),
            model=model,
            provider=self.name,
            latency_ms=int((perf_counter() - started) * 1000),
            tool_calls=tool_calls_from_openai(message),
        )
