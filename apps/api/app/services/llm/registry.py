"""Danh mục nhà cung cấp custom đọc từ FILE CẤU HÌNH — thêm được không cần sửa mã.

File mặc định là `apps/api/llm_providers.json` (đổi được bằng `LLM_PROVIDERS_FILE`).
Mỗi mục khai **base_url, tên biến môi trường chứa khoá, và bảng giá** — ba thứ mà
trước đây nằm ở ba tệp mã (`ENDPOINTS`, `config.py`, `pricing._RATES`), tức là
mỗi provider mới là một lần sửa mã cộng một lần triển khai.

Hai luật của tầng LLM vẫn đứng nguyên, và file này được thiết kế để không phá:

- **Khoá không bao giờ nằm trong file.** File này được commit; khoá chỉ được
  *được nhắc tên* (`api_key_env`). Cùng lý do với `AiFeatureConfig` không có cột
  khoá: thứ được commit là thứ lọt vào git history, bản sao lưu và ảnh màn hình.
- **Bảng giá vẫn từ chối model lạ.** Mục khai ở đây là NGUỒN GIÁ chứ không phải
  lối né: model có mục ở đây thì có giá thật để quy, model không có ở đâu cả vẫn
  bị `cost_usd` từ chối như trước.

Đọc file MỖI lượt cần, không cache — cùng lập luận với `resolver_for` đọc DB mỗi
lượt: một lượt đọc file vài trăm byte không đáng kể so với vài giây gọi LLM, còn
cache tạo ra cửa sổ "file đã sửa mà hệ thống chưa thấy" mà không ai phát hiện.

`strict` chia theo cùng ranh giới với `build_providers`: CLI (pipeline) muốn chết
ngay với thông báo rõ; đường phục vụ ghi warning và coi file như rỗng, để một lần
sửa tay gõ thiếu dấu phẩy không đá sập Coach lẫn Trợ lý.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.config import settings

__all__ = ["CustomModel", "CustomProvider", "load_registry"]

logger = logging.getLogger(__name__)


class CustomModel(BaseModel):
    """Giá USD cho MỘT TRIỆU token, cùng hình dạng với một hàng `_RATES`."""

    rate_in: Decimal
    rate_out: Decimal
    rate_cached: Decimal | None = None
    comment: str | None = None
    # Đè lên `extra_payload` của provider, theo TỪNG KHOÁ. Cần vì một endpoint
    # có thể gom nhiều model rất khác nhau: b.ai bật `thinking` cho cả chín
    # model của nó, và `glm-5.3-flash` tiêu trọn hạn mức đầu ra vào phần nghĩ —
    # 32 712 ký tự suy nghĩ cho một câu trả lời bốn dòng, `content` về rỗng.
    # Một công tắc chung cho cả provider sẽ tắt luôn thinking của những model
    # đang cần nó.
    extra_payload: dict[str, object] = Field(default_factory=dict)


class CustomProvider(BaseModel):
    """Một nhà cung cấp nói giao thức OpenAI — khác builtin đúng một base_url."""

    base_url: str
    # Tên BIẾN MÔI TRƯỜNG chứa khoá, không phải khoá. Bỏ trống thì suy ra
    # `<TÊN>_API_KEY` theo đúng quy ước các provider builtin đang dùng.
    api_key_env: str | None = None
    # Payload phụ gửi kèm mọi lượt chat/completions. NVIDIA yêu cầu
    # `chat_template_kwargs: {"thinking": false}` để tắt suy luận — để nguyên
    # mặc định thì model suy nghĩ ăn hết max_tokens và content về rỗng.
    extra_payload: dict[str, object] = Field(default_factory=dict)
    comment: str | None = None
    models: dict[str, CustomModel] = Field(default_factory=dict)


def load_registry(*, strict: bool = True) -> dict[str, CustomProvider]:
    """Đọc file cấu hình; `strict` quyết định lỗi cấu hình nổ ở đâu.

    File KHÔNG TỒN TẠI không phải lỗi ở cả hai chế độ — đó là trạng thái "chưa có
    provider custom", đường mặc định của mọi cài đặt mới.
    """
    path = settings.llm_providers_file
    if not path.is_file():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw.get("providers", {})
        registry: dict[str, CustomProvider] = {
            name: CustomProvider.model_validate(entry) for name, entry in entries.items()
        }
    except (json.JSONDecodeError, ValueError) as exc:
        if strict:
            raise ValueError(f"File cấu hình provider sai ở {path}: {exc}") from None
        logger.warning("llm_registry_invalid", extra={"path": str(path), "reason": str(exc)})
        return {}

    # Không cho ghi đè builtin: `providers.py` tra builtin TRƯỚC, nên một mục
    # "ollama" sai base_url ở đây sẽ không bao giờ có hiệu lực — im lặng như vậy
    # là kiểu hỏng tệ nhất. Nói ra ở cả hai chế độ.
    from app.services.llm.openai_compatible import ENDPOINTS

    builtin = {"ollama", "openrouter", *ENDPOINTS}
    for name in [n for n in registry if n in builtin]:
        message = f"Provider {name!r} trong {path.name} ghi đè builtin — xoá mục này."
        if strict:
            raise ValueError(message)
        logger.warning("llm_registry_overrides_builtin", extra={"provider": name})
        del registry[name]
    return registry
