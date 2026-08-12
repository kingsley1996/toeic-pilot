"""Trần chi tiêu cho mỗi học viên mỗi ngày.

**Chặn khi Redis hỏng** — ngược với bộ giới hạn đăng nhập, và giống hệt
`rate_limit` mặc định. Lập luận đã viết ở đó và đúng nguyên vẹn ở đây: Redis là
**thứ duy nhất** đứng giữa một tài khoản và hoá đơn. Cho qua khi Redis hỏng
nghĩa là ai hạ được Redis thì có LLM không giới hạn. Chặn khi hỏng làm mất một
tính năng một lúc; cho qua khi hỏng làm mất tiền, và số tiền đó không có trần.

Đơn vị là **micro-USD nguyên**, không phải số thực. `INCRBY` của Redis chỉ làm
việc với số nguyên, và micro-USD khớp đúng độ chính xác của
`ai_interaction.cost_usd` (`Numeric(12,6)`) — nên sổ cái và bộ đếm không bao giờ
lệch nhau vì làm tròn.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import redis

__all__ = ["Budget", "BudgetExceeded", "BudgetUnavailable", "micro_usd"]

_DAY_SECONDS = 24 * 60 * 60


class BudgetExceeded(Exception):
    def __init__(self, spent_micro: int, limit_micro: int) -> None:
        super().__init__("Đã dùng hết hạn mức AI trong ngày")
        self.spent_micro = spent_micro
        self.limit_micro = limit_micro


class BudgetUnavailable(Exception):
    """Không đọc được bộ đếm, nên không được phép tiêu."""


def micro_usd(amount: Decimal) -> int:
    return int((amount * 1_000_000).to_integral_value())


@dataclass(frozen=True, slots=True)
class Budget:
    """Cửa sổ cố định neo vào lần tiêu đầu tiên, y như `rate_limit.hit`.

    Sai số tệ nhất đã biết và chấp nhận được: kiểm TRƯỚC khi gọi mà chỉ cộng
    SAU khi gọi, nên một lượt gọi có thể vượt trần — nhiều nhất là đúng chi phí
    của một lượt. Cách làm chặt hơn là giữ chỗ trước rồi đối soát lại, và nó
    thêm một trạng thái phải hoà giải khi lượt gọi hỏng giữa chừng. Với một trần
    đặt ra để chặn lạm dụng chứ không phải để tính cước, đánh đổi đó không đáng.
    """

    limit_micro: int

    def _key(self, user_id: str) -> str:
        return f"aibudget:{user_id}"

    def check(self, client: redis.Redis, user_id: str) -> int:
        """Đã tiêu bao nhiêu. Ném `BudgetExceeded` nếu hết, `BudgetUnavailable` nếu Redis hỏng."""
        try:
            raw = client.get(self._key(user_id))
        except redis.RedisError as exc:
            raise BudgetUnavailable(str(exc)) from exc
        spent = int(raw) if raw else 0
        if spent >= self.limit_micro:
            raise BudgetExceeded(spent, self.limit_micro)
        return spent

    def charge(self, client: redis.Redis, user_id: str, amount_micro: int) -> None:
        """Ghi nhận chi phí đã phát sinh.

        Nuốt lỗi Redis có chủ ý, và đây là chỗ DUY NHẤT được phép: tiền đã tiêu
        rồi, lượt gọi đã xong, và ném lỗi ở đây chỉ làm hỏng một request đã
        thành công. Sổ cái bền là `ai_interaction`; bộ đếm này chỉ là bản sao
        nhanh để chặn lượt sau.
        """
        if amount_micro <= 0:
            return
        try:
            total = int(client.incrby(self._key(user_id), amount_micro))
            if total == amount_micro:
                client.expire(self._key(user_id), _DAY_SECONDS)
        except redis.RedisError:
            return
