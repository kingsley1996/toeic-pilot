"""Tick thủ công trên mục kế hoạch.

`study_plan_item.done_at` (nullable): người học tự đánh dấu một mục đã xong
ngay trên lịch. Trước đây kế hoạch chỉ có tiến độ SUY từ bản ghi học thật —
đúng cho mục lõi nhưng vô vọng với nhịp nền ("Ôn từ đến hạn" không có một hàng
nào để suy ra) và không có đường nào nói "hôm nay mình xong rồi" mà không cần
học lại. Hai nguồn giữ riêng biệt: `done_at` là quyết định của người học,
bản ghi học là sự kiện đã xảy ra; UI hiển thị gộp và nói rõ cái nào là cái nào.

Revision ID: 083_study_plan_manual_tick
Revises: 082_study_plan_filler_kinds
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "083_study_plan_manual_tick"
down_revision: Union[str, None] = "082_study_plan_filler_kinds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "study_plan_item",
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("study_plan_item", "done_at")
