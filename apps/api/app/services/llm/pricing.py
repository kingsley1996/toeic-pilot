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

__all__ = ["UnknownModel", "cost_usd"]


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
    ("ollama", "qwen2.5"): (Decimal("0"), Decimal("0"), Decimal("0")),
    ("fake", "fake-1"): (Decimal("0"), Decimal("0"), Decimal("0")),
}

_MILLION = Decimal("1000000")


def cost_usd(provider: str, model: str, usage: Usage) -> Decimal:
    """Quy token thành tiền, hoặc TỪ CHỐI nếu không biết giá.

    Ném lỗi thay vì trả 0 cho model lạ. Trả 0 sẽ ghi một con số sai vào sổ cái
    một cách im lặng, và mọi báo cáo chi phí sau đó đều sai theo mà không ai
    phát hiện — cùng lập luận với `scoring.py`, nơi thiếu bảng quy đổi thì ném
    lỗi chứ không nội suy (nguyên tắc N4: từ chối đoán).
    """
    try:
        rate_in, rate_out, rate_cached = _RATES[(provider, model)]
    except KeyError:
        raise UnknownModel(
            f"Chưa có giá cho {provider}/{model}. Thêm vào _RATES rồi hãy gọi — "
            f"ghi chi phí 0 cho một model có tính tiền là làm hỏng toàn bộ sổ cái."
        ) from None

    billed_prompt = usage.prompt
    total = Decimal(billed_prompt) * rate_in + Decimal(usage.completion) * rate_out
    total += Decimal(usage.cached) * (rate_cached if rate_cached is not None else rate_in)
    return (total / _MILLION).quantize(Decimal("0.000001"))
