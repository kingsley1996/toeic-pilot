"""Mục định hướng trên lịch kế hoạch.

`study_plan_item.kind` mở thêm `vocab_review` và `dictation`: khi ngày thi còn
xa (>14 ngày), generator nối sau các mục lõi những buổi "Ôn từ theo Due" /
"Chép chính tả" xen kẽ để lịch không trống giữa hai kỹ năng. Hai kind này không
trỏ nội dung cụ thể nào (`ref_id` NULL, `part` 0) — chúng là nhịp nền đã có sẵn
module thật ở `/learn/review` và `/learn/dictation`, không phải lời hứa câu nào.

Revision ID: 082_study_plan_filler_kinds
Revises: 081_placement_source_slug
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "082_study_plan_filler_kinds"
down_revision: Union[str, None] = "081_placement_source_slug"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_study_plan_item_kind", "study_plan_item", type_="check")
    op.create_check_constraint(
        "ck_study_plan_item_kind",
        "study_plan_item",
        "kind IN ('grammar_lesson', 'part_drill', 'vocab_review', 'dictation')",
    )


def downgrade() -> None:
    # Sẽ nổ nếu đã có hàng kind mới — đúng, dữ liệu đó vô nghĩa dưới CHECK cũ
    # (cùng lý do migration 025 ghi cho grade 6).
    op.drop_constraint("ck_study_plan_item_kind", "study_plan_item", type_="check")
    op.create_check_constraint(
        "ck_study_plan_item_kind",
        "study_plan_item",
        "kind IN ('grammar_lesson', 'part_drill')",
    )
