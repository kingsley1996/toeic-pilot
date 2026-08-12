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
from typing import Protocol

__all__ = ["LLMError", "LLMRequest", "LLMResult", "Provider", "Usage"]


class LLMError(RuntimeError):
    """Nhà cung cấp từ chối hoặc không trả lời được.

    Cố ý là một loại lỗi riêng chứ không để `httpx.HTTPError` trồi lên: nơi gọi
    cần phân biệt "nhà cung cấp hỏng" với "mã của ta hỏng", vì cái thứ nhất có
    đường lui (đổi tầng, phục vụ bản đã tính trước) còn cái thứ hai thì không.
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
    """

    system: str
    user: str
    max_tokens: int = 1024
    temperature: float = 0.0
    # Schema JSON cho structured output. `None` nghĩa là trả văn bản thường.
    schema: dict[str, object] | None = None


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


class Provider(Protocol):
    """Cái seam. Bộ test cắm bản giả vào đây, y như `get_db` và `get_redis`."""

    name: str

    def complete(self, request: LLMRequest, model: str) -> LLMResult: ...
