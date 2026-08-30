"""Hình dạng chung của một lượt gọi LLM, và cái seam mà mọi nhà cung cấp cắm vào.

**Adapter mỏng, không phải một tầng trừu tượng hoá SDK** (ADR-003 §3.1). Mỗi
nhà cung cấp là vài chục dòng dựng payload HTTP và đọc kết quả về `LLMResult`.
Một lớp "LLM universal" sẽ phải mô phỏng phần giao của mọi API và mất đúng
những thứ đáng dùng nhất của từng bên — prompt caching là ví dụ đầu tiên.

Vì thế ở đây dùng `httpx` thẳng, không SDK: nó đã là dependency sẵn có, không
thêm gì vào ảnh production, và không kéo theo một lịch nâng cấp của bên thứ ba
vào đường phục vụ request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = [
    "FeatureDisabled",
    "LLMError",
    "LLMQuotaExhausted",
    "LLMRequest",
    "LLMResult",
    "Provider",
    "ToolCall",
    "Usage",
    "tool_calls_from_openai",
]


class LLMError(RuntimeError):
    """Nhà cung cấp từ chối hoặc không trả lời được.

    Cố ý là một loại lỗi riêng chứ không để `httpx.HTTPError` trồi lên: nơi gọi
    cần phân biệt "nhà cung cấp hỏng" với "mã của ta hỏng", vì cái thứ nhất có
    đường lui (đổi tầng, phục vụ bản đã tính trước) còn cái thứ hai thì không.
    """


class LLMQuotaExhausted(LLMError):
    """Hết hạn mức của kỳ tính (ngày, tháng) — KHÁC với quá tải tạm thời.

    Phân biệt hai thứ này là bắt buộc chứ không phải cho gọn: cả hai đều trả
    HTTP 429, nhưng quá tải tạm thời thì lùi vài giây là qua, còn hết hạn mức
    ngày thì chờ bao lâu trong một lượt chạy cũng vô nghĩa. Gộp lại thì một lượt
    chạy 200 câu sẽ nghiến qua 800 lượt gọi chắc chắn hỏng, mất hàng chục phút,
    rồi báo 200 lỗi giống hệt nhau — che mất đúng một dòng nói lên nguyên nhân.
    """


class FeatureDisabled(LLMError):
    """Tính năng bị tắt từ giao diện quản trị.

    Là lớp con của `LLMError` để không nơi gọi nào quên bắt, nhưng là loại
    riêng vì cách xử lý khác hẳn: nhà cung cấp hỏng thì thử lại có nghĩa, còn
    tắt có chủ ý thì thử lại bao nhiêu lần cũng thế. Nó cũng phải hiện ra với
    người dùng như "tạm thời không dùng được" chứ **không phải giả vờ thành
    công** — một tính năng tắt mà giao diện im lặng là một tính năng hỏng.
    """


@dataclass(frozen=True, slots=True)
class Usage:
    """Số token đã tiêu, tách theo cách chúng được TÍNH GIÁ khác nhau.

    `cached` tách khỏi `prompt` vì token đọc từ cache có đơn giá riêng — gộp
    lại thì không đo được prompt caching có hiệu quả không, tức là không biết
    có nên giữ nó (`ai_interaction.cached_tokens` tồn tại vì đúng lý do này).
    """

    prompt: int = 0
    completion: int = 0
    cached: int = 0


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Một yêu cầu, đã tách sẵn phần cố định và phần thay đổi.

    `system` tách khỏi `user` không chỉ vì hai API đều có hai vai trò, mà vì
    **đó là ranh giới an toàn**: nội dung học viên gõ vào chỉ được đi qua
    `user`, không bao giờ được nối vào `system`. Gộp hai trường này lại là bỏ
    mất chỗ duy nhất mà luật đó có thể được thi hành.

    `system` cũng là phần cố định giữa các lượt gọi, nên nó là thứ prompt
    caching thật sự tiết kiệm được.

    `messages` cho VÒNG LẶP TOOL: khi có, nó thay thế cặp system/user trong
    payload — và luật an toàn chuyển sang được thi hành ở NƠI DỰNG messages
    (`services/assistant.py`): chữ người học chỉ bao giờ ở vai `user`, phần
    `system` do ta viết toàn phần. Adapter không dựng được luật này khi nhận
    sẵn danh sách, nên ai thêm nơi gọi thứ hai với `messages` phải đọc lại
    docstring đó.
    """

    system: str
    user: str
    max_tokens: int = 1024
    temperature: float = 0.0
    # Schema JSON cho structured output. `None` nghĩa là trả văn bản thường.
    schema: dict[str, object] | None = None
    # Danh sách công cụ, đúng schema `tools` của OpenAI Chat Completions —
    # giao thức mà các adapter tương thích đều nói.
    tools: list[dict[str, object]] | None = None
    # Toàn bộ hội thoại khi chạy vòng tool; `None` nghĩa là chỉ cặp system/user.
    messages: list[dict[str, object]] | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Một lượt model muốn gọi công cụ. `arguments` là JSON THÔ — parse là việc
    của người thực thi, vì một JSON hỏng là kết quả trả về cho model (nó tự sửa
    được), chứ không phải một exception đâm chết cả lượt."""

    id: str
    name: str
    arguments: str


def tool_calls_from_openai(message: dict[str, Any]) -> tuple[ToolCall, ...]:
    """Đọc `message.tool_calls` của giao thức OpenAI — dùng chung cho mọi
    adapter nói giao thức đó (openai_compatible, openrouter); không có thì
    tuple rỗng."""
    out: list[ToolCall] = []
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        out.append(
            ToolCall(
                id=str(call.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments=str(fn.get("arguments") or "{}"),
            )
        )
    return tuple(out)


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str
    usage: Usage
    model: str
    provider: str
    latency_ms: int = 0
    # Số lần đã thử lại vì đầu ra không hợp schema. Ghi lại chứ không nuốt:
    # tỉ lệ phải thử lại chính là tín hiệu nói model ở tầng này có đủ dùng không.
    retries: int = 0
    raw: dict[str, object] = field(default_factory=dict)
    # Model muốn gọi công cụ thay vì trả lời — vòng lặp ở nơi gọi thực thi rồi
    # gọi lại với kết quả, cho tới khi model trả văn bản.
    tool_calls: tuple[ToolCall, ...] = ()


class Provider(Protocol):
    """Cái seam. Bộ test cắm bản giả vào đây, y như `get_db` và `get_redis`."""

    name: str

    def complete(self, request: LLMRequest, model: str) -> LLMResult: ...
