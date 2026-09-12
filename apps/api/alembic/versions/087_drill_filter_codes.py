"""Nhãn bộ lọc của mục drill — `study_plan_item.filter_codes`.

Bug người học bắt (2026-09-12): hoàn thành MỘT câu "tìm thông tin" Part 7 →
lịch tick xong MỌI mục Part 7, vì derivation chỉ so `part`. Spec §18 đã nói
từ đầu: drill khép bằng phiên có câu ĐÚNG NHÃN. Nhãn trước đây chỉ sống trong
chuỗi `link` (`?labels=`) — hết sức cho người, vô dụng cho SQL. Một cột JSONB
mới để `min(started_at) theo (part, code)` khớp được bằng JOIN, không bằng
parse URL.

Cột NULL với hàng cũ và mục không có nhãn ("đều tay"): rơi về luật cũ theo
part — đó là Ý NGHĨA của chính nó ("Luyện Part 7" chung = mọi phiên Part 7).

Revision ID: 087_drill_filter_codes
Revises: 086_plan_versions
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "087_drill_filter_codes"
down_revision: Union[str, None] = "086_plan_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "study_plan_item",
        sa.Column("filter_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("study_plan_item", "filter_codes")
