"""Dựng adapter cho các nhà cung cấp một lượt chạy cần — CHỖ DUY NHẤT.

Cùng một nhu cầu ở hai phía: đường phục vụ (`app/api/deps.get_gateway`) và
pipeline ngoài luồng (`enrich_skills`, `generate_exam`). Hai bản dựng riêng sẽ
trôi khỏi nhau đúng ngày thêm một nhà cung cấp — đường phục vụ vẫn chỉ biết
ollama còn pipeline đã biết nói với Google, và lỗi đó chỉ lộ ở lượt gọi thật.

Nguồn của danh mục, theo thứ tự tra:

1. `ollama` — model chạy máy, luôn dựng được, không cần khoá.
2. `openrouter` — khoá từ `OPENROUTER_API_KEY`.
3. `ENDPOINTS` (`openai_compatible.py`) — các builtin nói giao thức OpenAI
   (Google, Groq, Cerebras, …), khoá theo quy ước `<tên>_api_key` trong settings.
4. **`llm_providers.json`** — provider custom, thêm được KHÔNG CẦN sửa mã: file
   khai base_url + tên biến môi trường chứa khoá + bảng giá; khoá không bao giờ
   nằm trong file vì file được commit.

Thiếu khoá hoặc thiếu adapter:
- `strict=True` (CLI) — chết ngay với thông báo rõ, vì lượt chạy pipeline dài
  hàng chục phút và im lặng lúc khởi động là đốt tiền về sau.
- `strict=False` (đường phục vụ) — bỏ qua, để một tính năng trỏ vào provider
  thiếu khoá không kéo sập các tính năng khác. Lượt gọi tới provider thiếu sẽ
  nhận `LLMError` từ `Gateway` và trả 503 có ghi sổ.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.llm.base import Provider
from app.services.llm.openai_compatible import ENDPOINTS, OpenAICompatibleProvider
from app.services.llm.registry import load_registry

__all__ = ["build_providers"]


def build_providers(names: set[str], *, strict: bool = True) -> dict[str, Provider]:
    """Chỉ dựng adapter cho nhà cung cấp thật sự được cấu hình.

    Dựng hết rồi mới chọn sẽ bắt phải có khoá của MỌI nhà cung cấp mới chạy
    được — kể cả nhà cung cấp lượt chạy này không dùng tới.
    """
    built: dict[str, Provider] = {}

    def _skip(name: str, reason: str) -> None:
        if strict:
            raise RuntimeError(reason)
        # Bỏ qua lặng lẽ ở chế độ rộng: lỗi thật sẽ nổ ở lượt gọi, nơi Gateway
        # ghi một hàng "refused" vào sổ cái — một vết còn readable hơn log.

    for name in sorted(names):
        if name == "ollama":
            from app.services.llm.ollama import OllamaProvider

            built[name] = OllamaProvider(settings.ollama_base_url)
        elif name == "openrouter":
            from app.services.llm.openrouter import OpenRouterProvider

            if not settings.openrouter_api_key:
                _skip(name, "Thiếu OPENROUTER_API_KEY. Đặt vào .env ở gốc repo.")
                continue
            built[name] = OpenRouterProvider(settings.openrouter_api_key)
        elif name in ENDPOINTS:
            key = getattr(settings, f"{name}_api_key", None)
            if not key:
                _skip(name, f"Thiếu {name.upper()}_API_KEY. Đặt vào .env ở gốc repo.")
                continue
            built[name] = OpenAICompatibleProvider(name, ENDPOINTS[name], key)
        elif (custom := load_registry(strict=strict).get(name)) is not None:
            # Provider khai trong `llm_providers.json` — chỗ thêm provider mới
            # KHÔNG cần sửa mã. Khoá đọc từ biến môi trường mà file nhắc tên:
            # file được commit nên khoá không bao giờ được nằm trong đó.
            import os

            env_var = custom.api_key_env or f"{name.upper()}_API_KEY"
            key = os.environ.get(env_var)
            if not key:
                _skip(name, f"Thiếu {env_var}. Đặt vào .env ở gốc repo.")
                continue
            built[name] = OpenAICompatibleProvider(name, custom.base_url, key)
        else:
            _skip(
                name,
                f"Chưa có adapter cho nhà cung cấp {name!r} — thêm vào "
                f"ENDPOINTS hoặc vào llm_providers.json (nó nói giao thức OpenAI).",
            )
    return built
