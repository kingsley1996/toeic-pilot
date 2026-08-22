"""Adapter dùng chung cho các nhà cung cấp nói giao thức OpenAI.

Không bài nào gọi ra mạng. Thứ đáng kiểm là ba chỗ mà một adapter sai sẽ hỏng
IM LẶNG:

  · ghép sai `base_url` → lỗi DNS hoặc 404 chẳng nói gì về nguyên nhân;
  · nhét nội dung người dùng vào vai `system` → mất ranh giới an toàn duy nhất
    mà adapter có thể thi hành;
  · dịch mọi 429 thành "thử lại" → một hạn mức NGÀY sẽ cày hết việc còn lại,
    hỏng y hệt nhau, và chôn mất dòng nói đúng nguyên nhân.
"""

import httpx
import pytest

from app.services.llm.base import LLMError, LLMQuotaExhausted, LLMRequest
from app.services.llm.openai_compatible import ENDPOINTS, OpenAICompatibleProvider


class _Response:
    def __init__(self, status: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status
        self._payload = payload or {}
        self.text = text or str(payload)

    def json(self) -> dict:
        return self._payload


def _ok() -> dict:
    return {
        "choices": [{"message": {"content": "xong"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
    }


def test_every_endpoint_is_an_https_origin_without_a_trailing_path():
    """Bảng endpoint là thứ duy nhất phân biệt các nhà cung cấp.

    Một `base_url` sai không hỏng lúc build — nó hỏng ở lượt gọi đầu tiên, với
    một lỗi mạng chẳng nói gì về nguyên nhân.
    """
    for name, url in ENDPOINTS.items():
        assert url.startswith("https://"), name
        assert not url.endswith("/"), name
        assert "/chat/completions" not in url, f"{name}: đường dẫn ghép ở adapter, không ở bảng"


def test_the_request_keeps_system_and_user_apart(monkeypatch):
    """Nội dung người dùng CHỈ đi vào vai `user`.

    Gộp hai vai lại là bỏ mất chỗ duy nhất mà luật đó được thi hành — và chỗ đó
    là adapter, không phải tầng gọi.
    """
    seen: dict = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["json"] = kwargs["json"]
        seen["headers"] = kwargs["headers"]
        return _Response(200, _ok())

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAICompatibleProvider("groq", ENDPOINTS["groq"], "khoa-gia")
    result = provider.complete(
        LLMRequest(system="luật", user="dữ liệu người dùng", max_tokens=99, temperature=0.4),
        "llama-3.3-70b-versatile",
    )

    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer khoa-gia"
    assert seen["json"]["messages"] == [
        {"role": "system", "content": "luật"},
        {"role": "user", "content": "dữ liệu người dùng"},
    ]
    assert seen["json"]["max_tokens"] == 99
    assert result.text == "xong"
    assert result.usage.prompt == 11 and result.usage.completion == 7
    assert result.provider == "groq"


def test_a_daily_quota_stops_the_run_but_overload_does_not(monkeypatch):
    """Hai loại 429, và gộp chúng lại là thứ tốn nhiều thời gian nhất.

    Hạn mức ngày không tự hết sau ba mươi giây; lùi rồi thử lại sẽ cày hết mọi
    việc còn lại và hỏng y hệt nhau. Quá tải tạm thời thì ngược lại — lùi vài
    giây là qua, nên nó phải là `LLMError` để tầng trên thử lại.
    """
    provider = OpenAICompatibleProvider("cerebras", ENDPOINTS["cerebras"], "k")

    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Response(429, text="Rate limit: tokens per day exceeded")
    )
    with pytest.raises(LLMQuotaExhausted):
        provider.complete(LLMRequest(system="s", user="u"), "qwen3-32b")

    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Response(429, text="Too many concurrent requests")
    )
    with pytest.raises(LLMError) as caught:
        provider.complete(LLMRequest(system="s", user="u"), "qwen3-32b")
    assert not isinstance(caught.value, LLMQuotaExhausted)


def test_a_200_without_choices_says_why(monkeypatch):
    """Một số nhà cung cấp trả 200 kèm khối `error`.

    Không kiểm thì nó nổ thành `KeyError` ở dòng dưới, và thông báo sẽ không
    nhắc gì tới nguyên nhân thật.
    """
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Response(200, {"error": {"message": "model đang bận"}})
    )
    provider = OpenAICompatibleProvider("google", ENDPOINTS["google"], "k")
    with pytest.raises(LLMError, match="không có choices"):
        provider.complete(LLMRequest(system="s", user="u"), "gemini-2.5-flash")


def test_payment_required_stops_the_run_instead_of_retrying(monkeypatch):
    """402 không bao giờ tự hết bằng cách thử lại.

    Gặp thật với một khoá Cerebras: xác thực qua, `GET /models` trả 200, mọi
    lượt suy luận trả 402. Nếu nó là lỗi thường thì vòng lặp sinh đề đi hết 30
    ô, hỏng y hệt nhau, và dòng nói đúng nguyên nhân nằm dưới 29 dòng giống hệt.
    """
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: _Response(
            402, text='{"message":"Payment required","code":"payment_required"}'
        ),
    )
    provider = OpenAICompatibleProvider("cerebras", ENDPOINTS["cerebras"], "k")
    with pytest.raises(LLMQuotaExhausted, match="402"):
        provider.complete(LLMRequest(system="s", user="u"), "gpt-oss-120b")


def test_reasoning_that_eats_the_whole_budget_says_so(monkeypatch):
    """`content` rỗng + `reasoning_content` dài + `finish_reason: length`.

    Đo thật với `qwen3.8-max-free`: 2 600 token đầu ra tiêu hết vào phần suy
    nghĩ (10 862 ký tự), `content` rỗng. Không nói ra thì lỗi này đội lốt "model
    trả lời sai định dạng", và người sửa đi chỉnh prompt trong khi thứ cần chỉnh
    là `max_tokens`.
    """
    payload = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {"content": "", "reasoning_content": "nghĩ " * 500},
            }
        ],
        "usage": {"prompt_tokens": 640, "completion_tokens": 2600},
    }
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Response(200, payload))
    provider = OpenAICompatibleProvider("tokenrouter", "https://x/v1", "k")
    with pytest.raises(LLMError, match="suy luận"):
        provider.complete(LLMRequest(system="s", user="u"), "qwen/qwen3.8-max-free")
