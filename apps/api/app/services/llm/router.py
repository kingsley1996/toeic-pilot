"""Chọn tầng, và chọn model cho tầng đó.

`PLAN.md` §4 gọi đây là "LLM Routing". Phần khó không phải là câu `if` chọn
model — phần khó là **biết mình chọn đúng hay sai**, và câu trả lời cho việc đó
là `escalations`: bao nhiêu phần trăm lượt gọi ở tầng rẻ phải leo lên tầng mạnh.
Tỉ lệ đó cao thì tầng rẻ không đủ dùng và đang tốn tiền hai lần; tỉ lệ đó bằng
không kéo dài thì tầng mạnh có thể thừa. Không đo được nó thì định tuyến chỉ là
đoán có tổ chức (nguyên tắc N5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ["Route", "Tier", "route_for"]


class Tier(StrEnum):
    """Chỉ hai tầng có gọi model.

    T0 (đọc bản đã tính trước) và T3 (pipeline offline) không xuất hiện ở đây —
    chúng không gọi model, nên chúng không phải là lựa chọn của bộ định tuyến mà
    là những đường hoàn toàn khác. Đưa chúng vào enum này sẽ gợi ý sai rằng mọi
    thứ đều là một lượt gọi LLM với giá khác nhau.
    """

    CHEAP = "t1"
    STRONG = "t2"


@dataclass(frozen=True, slots=True)
class Route:
    tier: Tier
    provider: str
    model: str


def route_for(tier: Tier, table: dict[Tier, tuple[str, str]]) -> Route:
    """Tra bảng, không suy diễn.

    Bảng đến từ cấu hình chứ không nằm trong hàm, vì đổi model là việc vận hành
    — không nên là một lần sửa mã và một lần triển khai.
    """
    try:
        provider, model = table[tier]
    except KeyError:
        raise LookupError(f"Chưa cấu hình model cho tầng {tier}") from None
    return Route(tier=tier, provider=provider, model=model)
