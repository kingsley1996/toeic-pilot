"""Lùi rồi thử lại khi nhà cung cấp báo quá tải TẠM THỜI.

Nằm ở tầng chung vì cả `enrich_skills` lẫn lệnh sinh đề đều cần, và một bản sao
thứ hai sẽ trôi khỏi bản gốc — chỗ trôi sẽ là danh sách mã lỗi được coi là tạm
thời, tức là đúng chỗ khó phát hiện nhất.

Vòng thử lại nằm ở tầng GỌI chứ không trong gateway, nên **mỗi lượt gọi HTTP vẫn
là một hàng trong sổ cái**. Gộp lượt hỏng vào lượt thành công làm chi phí của
một hàng không còn tương ứng với một lượt gọi.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from app.services.llm.base import LLMError, LLMQuotaExhausted, LLMResult

__all__ = ["with_backoff"]

# Mã lỗi được coi là TẠM THỜI. 429 nằm đây vì quá tải nhóm dùng chung cũng dùng
# mã đó; hạn mức ngày thì đã được adapter dịch thành `LLMQuotaExhausted` và
# không bao giờ đi tới đây.
_TRANSIENT = ("429", "500", "502", "503", "504")

# Hết giờ đọc cũng là TẠM THỜI, và nó không mang mã số nào để nhận ra.
#
# Bỏ sót nhóm này là một lỗ có thật: một model suy luận chậm sẽ vượt hạn giờ ở
# lượt đầu rồi trả lời bình thường ở lượt sau, nhưng vì thông báo không chứa
# "503" nên `with_backoff` ném thẳng ra và cả ô bị bỏ qua.
#
# Nhóm ĐẮT: hỏng sau khi đã tiêu gần trọn cửa sổ, nên có ngân sách thử lại
# riêng (`expensive_tries`). Phân nhóm theo CHI PHÍ chứ không theo loại lỗi —
# "máy chủ ngắt kết nối" và "hết giờ đọc" là hai nguyên nhân khác nhau nhưng
# giống hệt nhau ở chỗ tốn: cả hai đều trả lời sau nhiều phút, rồi hỏng.
#
# `server disconnected` vào đây sau khi mất một lượt viết `p4-09`: nó hỏng sau
# 340 giây và KHÔNG khớp danh sách nào, nên bị ném thẳng ra, không thử lại lần
# nào. Đúng chỗ mà docstring trên đã cảnh báo là dễ trôi nhất.
_EXPENSIVE_TEXT = ("timed out", "timeout", "disconnected", "incomplete")
_TRANSIENT_TEXT = (*_EXPENSIVE_TEXT, "connection reset", "temporarily")


def with_backoff(
    call: Callable[[], LLMResult],
    *,
    tries: int = 4,
    delay: float = 4.0,
    expensive_tries: int = 2,
) -> LLMResult:
    """Thử lại tối đa `tries` lần, giãn gấp đôi mỗi lần.

    `LLMQuotaExhausted` KHÔNG đi qua đây — hạn mức ngày không hết đi trong ba
    mươi giây, và thử lại chỉ làm lượt chạy hỏng lâu hơn để rồi vẫn hỏng. Lỗi
    400 do prompt sai cũng vậy: nó sẽ sai y hệt ở lần thứ tư.

    **Lỗi ĐẮT có ngân sách RIÊNG (`expensive_tries`).** Một lượt
    429 hỏng sau vài giây; một lượt timeout hỏng sau trọn cửa sổ, và cửa sổ đó
    nay đi theo `max_tokens` — ở 40 000 token nó là 4 000 giây. Đếm chung thì
    bảy lần thử là gần tám tiếng cho MỘT lượt viết, im lặng. Hai lần là đủ để
    phân biệt "xui" với "cửa sổ không đủ cho yêu cầu này", và ca thứ hai thì thử
    thêm bao nhiêu cũng vẫn hỏng.
    """
    last: LLMError | None = None
    expensive = 0
    for attempt in range(tries):
        try:
            return call()
        except LLMQuotaExhausted:
            raise
        except LLMError as exc:
            message = str(exc)
            lowered = message.lower()
            if not any(code in message for code in _TRANSIENT) and not any(
                mark in lowered for mark in _TRANSIENT_TEXT
            ):
                raise
            if any(mark in lowered for mark in _EXPENSIVE_TEXT):
                expensive += 1
                if expensive >= expensive_tries:
                    raise
            last = exc
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
    raise last if last is not None else LLMError("hết lượt thử")
