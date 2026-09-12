"""Kế hoạch theo spec planner: ngày nghỉ + mục kiểm tra + phase.

Ba thay đổi một migration — cả ba chỉ phục vụ hàng đợi kế hoạch/profile, không ai
đọc chéo ai:

* `user_profile.study_days_per_week` — input §2 của SPEC-STUDY-PLANNER mà
  planner đã thiếu từ đầu: lịch trước đó trải MỌI ngày, tức ai học 5 ngày/tuần
  vẫn nhận mục vào ngày nghỉ và bị đếm là "bỏ hôm". NULL = 7 (hành vi cũ).
* `study_plan_item.kind` mở `mini_test` / `mock_test`: kiểm tra định kỳ là mục
  kế hoạch thật, tự-đóng bằng attempt chứ không bằng tick.
* `study_plan_item.phase` — nhãn đường ống §15 (foundation → weakness →
  integrated → final), ghi lúc sinh, chỉ để hiển thị/nhóm; thứ tự mục vẫn là
  hàng đợi packing.

Revision ID: 084_planner_spec_columns
Revises: 083_study_plan_manual_tick
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "084_planner_spec_columns"
down_revision: Union[str, None] = "083_study_plan_manual_tick"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("study_days_per_week", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_profile_study_days_per_week",
        "user_profile",
        "study_days_per_week IS NULL OR study_days_per_week BETWEEN 1 AND 7",
    )
    op.drop_constraint("ck_study_plan_item_kind", "study_plan_item", type_="check")
    op.create_check_constraint(
        "ck_study_plan_item_kind",
        "study_plan_item",
        "kind IN ('grammar_lesson', 'part_drill', 'vocab_review', 'dictation',"
        " 'mini_test', 'mock_test')",
    )
    op.add_column(
        "study_plan_item",
        sa.Column("phase", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_study_plan_item_phase",
        "study_plan_item",
        "phase IS NULL OR phase IN ('foundation', 'weakness', 'integrated', 'final')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_study_plan_item_phase", "study_plan_item", type_="check")
    op.drop_column("study_plan_item", "phase")
    op.drop_constraint("ck_study_plan_item_kind", "study_plan_item", type_="check")
    op.create_check_constraint(
        "ck_study_plan_item_kind",
        "study_plan_item",
        "kind IN ('grammar_lesson', 'part_drill', 'vocab_review', 'dictation')",
    )
    op.drop_constraint("ck_user_profile_study_days_per_week", "user_profile", type_="check")
    op.drop_column("user_profile", "study_days_per_week")
