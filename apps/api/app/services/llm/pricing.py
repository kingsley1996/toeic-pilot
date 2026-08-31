"""Bảng giá, và phép quy token thành tiền.

**Chi phí do TA tính từ bảng này, không phải đọc từ phản hồi của nhà cung cấp.**
Hai lý do độc lập: không phải nhà cung cấp nào cũng trả về tiền, và ngay cả khi
trả thì mỗi bên trả một đơn vị khác nhau — mà toàn bộ giá trị của
`ai_interaction` nằm ở chỗ so sánh được giữa các nhà cung cấp.

Giá được tính **tại thời điểm gọi** rồi lưu vào hàng. Đổi bảng giá sau này
không viết lại lịch sử, và đó là đúng: hàng cũ ghi số tiền đã thực sự phát sinh.

**Bảng này là dữ liệu có hạn sử dụng.** Nhà cung cấp đổi giá mà không báo ai,
nên nó phải được đối chiếu với trang giá chính thức trước mỗi đợt chạy lớn —
cùng loại nghĩa vụ với `LOGICAL_VOICES` của edge-tts, và cùng kiểu hỏng: im lặng.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.llm.base import Usage

__all__ = ["UnknownModel", "cost_usd", "known_models"]


class UnknownModel(LookupError):
    """Model không có trong bảng giá."""


# USD cho MỘT TRIỆU token. Khoá là (nhà cung cấp, model).
# `cached` là đơn giá đọc lại từ cache; None nghĩa là nhà cung cấp không tính
# riêng, và khi đó token cache được tính như token prompt thường.
_RATES: dict[tuple[str, str], tuple[Decimal, Decimal, Decimal | None]] = {
    # (đầu vào, đầu ra, đọc cache)
    ("anthropic", "claude-haiku-4-5-20251001"): (Decimal("1.00"), Decimal("5.00"), Decimal("0.10")),
    ("anthropic", "claude-sonnet-5"): (Decimal("3.00"), Decimal("15.00"), Decimal("0.30")),
    ("openai", "gpt-4o-mini"): (Decimal("0.15"), Decimal("0.60"), Decimal("0.075")),
    ("openai", "gpt-4o"): (Decimal("2.50"), Decimal("10.00"), Decimal("1.25")),
    # Tier miễn phí và model chạy tại máy: giá thật bằng 0. Vẫn phải có mặt ở
    # đây, vì thiếu thì `cost_usd` sẽ ném lỗi và chặn cả đường phát triển.
    ("google", "gemini-2.5-flash"): (Decimal("0"), Decimal("0"), Decimal("0")),
    # Giá CÔNG BỐ của gói trả tiền, tra ở ai.google.dev/gemini-api/docs/pricing
    # ngày 2026-08-22. Ghi giá thật chứ không ghi 0 dù ta đang chạy trên gói
    # miễn phí: gói miễn phí là thuộc tính của TÀI KHOẢN, không phải của model,
    # nên một hàng 0 ở đây sẽ báo cáo sai ngay ngày đầu tiên có người nạp tiền.
    #
    # Giá đầu vào tăng gấp đôi từ 2027-01-01 ($1.50 / $7.50) theo đúng trang đó.
    # Không mã hoá ngày vào bảng: một bảng giá tự đổi theo lịch là thứ không ai
    # đọc ra được từ một con số, và nó sẽ đúng đúng một lần rồi sai mãi.
    ("google", "gemini-3.7-flash"): (Decimal("0.75"), Decimal("3.75"), None),
    # Tra cùng trang, ngày 2026-08-24. Cùng đơn giá vào/ra với 3.7-flash, nhưng
    # trang có ghi RIÊNG giá đọc lại từ cache ($0.075) nên hàng này điền cả ba.
    # Thêm vào vì 3.7-flash trả 503 "high demand" liên tục ở thời điểm đó, còn
    # 3.6 thì phục vụ bình thường — và `cost_usd` TỪ CHỐI một model chưa có giá
    # thay vì ghi 0, nên không thêm là không chạy được.
    ("google", "gemini-3.6-flash"): (Decimal("0.75"), Decimal("3.75"), Decimal("0.075")),
    ("google", "gemini-3.5-flash"): (Decimal("1.50"), Decimal("9.00"), None),
    ("openrouter", "openai/gpt-oss-20b:free"): (Decimal("0"), Decimal("0"), Decimal("0")),
    # Hàng RIÊNG cho đúng một id, không phải một luật "hậu tố -free thì giá 0".
    # Luật hậu tố của OpenRouter đứng được vì `:free` là ký hiệu chính thức của
    # họ; ở đây `-free` mới chỉ là một cái tên, và một model tính tiền đặt tên
    # có chữ đó sẽ lọt qua luật mà không ai thấy.
    ("tokenrouter", "qwen/qwen3.8-max-free"): (Decimal("0"), Decimal("0"), Decimal("0")),
    # Tên model KHÁC hẳn tên ở bai: `z-ai/glm-5.3-free`, không phải `glm-5.3-flash`.
    # Hỏi `GET /v1/models` chứ không suy từ tên ở nhà cung cấp khác — id model là
    # của HỌ, và đoán sai thì lượt gọi hỏng với 404 chẳng nói gì về nguyên nhân.
    ("tokenrouter", "z-ai/glm-5.3-free"): (Decimal("0"), Decimal("0"), Decimal("0")),
    # Groq — giá công bố ở console.groq.com/docs/models, tra ngày 2026-08-22.
    # Groq có gói dùng thử miễn phí, nhưng giá ghi ở đây là giá THẬT của model,
    # cùng lý do đã ghi cho Gemini: gói miễn phí là thuộc tính của tài khoản chứ
    # không phải của model.
    ("groq", "qwen/qwen3.6-27b"): (Decimal("0.60"), Decimal("3.00"), None),
    ("groq", "openai/gpt-oss-120b"): (Decimal("0.15"), Decimal("0.60"), None),
    # Model chạy trên máy: chi phí biên bằng 0 thật, không phải bằng 0 vì
    # chưa ai điền giá. Token vẫn được ghi để ngoại suy nếu đổi sang model tính tiền.
    ("ollama", "llama3.2:latest"): (Decimal("0"), Decimal("0"), Decimal("0")),
    ("ollama", "gemma3:latest"): (Decimal("0"), Decimal("0"), Decimal("0")),
    ("ollama", "qwen2.5"): (Decimal("0"), Decimal("0"), Decimal("0")),
    ("fake", "fake-1"): (Decimal("0"), Decimal("0"), Decimal("0")),
    ("fake", "fake-2"): (Decimal("0"), Decimal("0"), Decimal("0")),
}

_MILLION = Decimal("1000000")


def cost_usd(provider: str, model: str, usage: Usage) -> Decimal:
    """Quy token thành tiền, hoặc TỪ CHỐI nếu không biết giá.

    Ném lỗi thay vì trả 0 cho model lạ. Trả 0 sẽ ghi một con số sai vào sổ cái
    một cách im lặng, và mọi báo cáo chi phí sau đó đều sai theo mà không ai
    phát hiện — cùng lập luận với `scoring.py`, nơi thiếu bảng quy đổi thì ném
    lỗi chứ không nội suy (nguyên tắc N4: từ chối đoán).
    """
    # Model có hậu tố `:free` của OpenRouter có giá bằng 0 theo đúng công bố của
    # họ — nhận ra nó KHÔNG phải là đoán, đó là đọc một dấu hiệu tường minh.
    # Model OpenRouter không có hậu tố đó vẫn phải tra bảng như mọi model khác,
    # nếu không thì một lần gõ nhầm tên model sẽ ghi chi phí 0 cho một lượt gọi
    # có tính tiền.
    if provider == "openrouter" and model.endswith(":free"):
        return Decimal("0.000000")

    rates = _RATES.get((provider, model))
    if rates is None:
        # Nguồn giá thứ hai: provider custom khai trong `llm_providers.json`.
        # File là chỗ DUY NHẤT để thêm provider không sửa mã, nên bảng giá tĩnh
        # mà không đọc nó là mỗi model custom đều UnknownModel vô cớ.
        from app.services.llm.registry import load_registry

        custom_model = load_registry(strict=False).get(provider)
        entry = custom_model.models.get(model) if custom_model else None
        if entry is None:
            raise UnknownModel(
                f"Chưa có giá cho {provider}/{model}. Thêm vào _RATES hoặc vào "
                f"llm_providers.json rồi hãy gọi — ghi chi phí 0 cho một lượt gọi "
                f"có tính tiền là làm hỏng toàn bộ sổ cái."
            ) from None
        rates = (entry.rate_in, entry.rate_out, entry.rate_cached)

    rate_in, rate_out, rate_cached = rates
    billed_prompt = usage.prompt
    total = Decimal(billed_prompt) * rate_in + Decimal(usage.completion) * rate_out
    total += Decimal(usage.cached) * (rate_cached if rate_cached is not None else rate_in)
    return (total / _MILLION).quantize(Decimal("0.000001"))


def known_models() -> list[tuple[str, str]]:
    """Các cặp (nhà cung cấp, model) mà hệ thống biết giá.

    Giao diện quản trị **chỉ được đưa ra danh sách này**. Cho gõ tay tên model
    nghĩa là một lần gõ nhầm sẽ làm mọi lượt gọi của tính năng đó hỏng ngay —
    `cost_usd` ném lỗi với model lạ chứ không ghi 0, và đó là hành vi đúng
    (nguyên tắc N4), nhưng nó phải hỏng ở chỗ CHỌN chứ không ở chỗ CHẠY.

    Bao gồm cả model custom khai trong `llm_providers.json` — nơi duy nhất để
    thêm model của một provider mới mà không sửa mã.
    """
    from app.services.llm.registry import load_registry

    pairs = set(_RATES)
    for name, provider in load_registry(strict=False).items():
        pairs.update((name, model) for model in provider.models)
    return sorted(pairs)


def rates_for(provider: str, model: str) -> tuple[Decimal, Decimal, Decimal | None]:
    """(giá vào, giá ra, giá đọc cache) của một model, hoặc None nếu lạ.

    Cùng nguồn với `cost_usd` — một hàm cho giao diện quản trị hiển thị giá,
    hàm kia cho sổ cái tính tiền, và cả hai đọc cùng một bảng nên không thể lệch.
    """
    rates = _RATES.get((provider, model))
    if rates is not None:
        return rates
    from app.services.llm.registry import load_registry

    custom = load_registry(strict=False).get(provider)
    entry = custom.models.get(model) if custom else None
    if entry is None:
        return Decimal(0), Decimal(0), Decimal(0)
    return entry.rate_in, entry.rate_out, entry.rate_cached
