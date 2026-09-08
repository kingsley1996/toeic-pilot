"""Gieo đủ bảng mức ruby — `074` để lại bảng nửa vời trên cài đặt mới

Revision ID: 076_seed_ruby_rules
Revises: 075_placement_kind
Create Date: 2026-09-08 00:00:00.000000

`rules()` gieo mặc định khi bảng RỖNG. `074` chèn đúng một hàng
(`feedback_reward`) vào bảng ấy, nên trên một database mới migrate bảng không
còn rỗng — bảy mức kia không bao giờ tới, và mọi khoản thưởng học tập trả 0
ruby mà không có gì báo. Cài đặt đang chạy không thấy gì, vì bảy hàng đã được
gieo lười từ lâu; nó chỉ nổ ở nơi bắt đầu từ số không, tức CI và bản triển khai
kế tiếp.

`ON CONFLICT DO NOTHING` để mức admin đã chỉnh không bị kéo về mặc định.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "076_seed_ruby_rules"
down_revision: Union[str, None] = "075_placement_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Chép cứng, không import `DEFAULT_RUBY_RULES`: một migration ghim một thời
# điểm, còn hằng số kia còn đổi.
_RULES = (
    ("story_complete", "Nghe xong một bài", 5, 1),
    ("topic_mastered", "Thuộc trọn một chủ đề", 15, 2),
    ("attempt_full", "Làm xong một đề", 25, 3),
    ("attempt_mini", "Làm xong một đề ngắn", 8, 4),
    ("daily_all", "Xong cả ba việc hôm nay", 10, 5),
    ("daily_gift", "Quà hàng ngày", 3, 6),
    ("streak_week", "Giữ chuỗi bảy ngày", 20, 7),
)


def upgrade() -> None:
    statement = sa.text(
        "INSERT INTO ruby_rule (source_type, label, amount, position, enabled) "
        "VALUES (:source_type, :label, :amount, :position, true) "
        "ON CONFLICT (source_type) DO NOTHING"
    )
    for source_type, label, amount, position in _RULES:
        op.execute(
            statement.bindparams(
                source_type=source_type, label=label, amount=amount, position=position
            )
        )


def downgrade() -> None:
    # Không xoá: không phân biệt được hàng do migration này chèn với hàng đã
    # gieo lười từ trước, và xoá nhầm là mất mức admin đã chỉnh.
    pass
