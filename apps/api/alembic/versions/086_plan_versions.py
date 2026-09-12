"""Phiên bản kế hoạch — V3 của SPEC-STUDY-PLANNER (§29, §32).

`study_plan.version` + `reason`: lịch sử kế hoạch VỐN đã nằm lại trong DB
(sinh kế hoạch mới chỉ hạ `is_current`, không xoá), nhưng không ai đọc được
nó — "kế hoạch này là bản thứ mấy, mọc từ sự kiện nào" là câu hỏi của người
đã đo lại vài lần, và trả lời sai một câu ở đây là phủ nhận cả lộ trình của
họ. Số phiên ĐÁNH LÚC SINH (max+1 của người đó), không suy lúc đọc: thứ tự
`created_at` chỉ chính xác tới giây và hai bản cùng giây là có thật.

`reason` do route sinh suy từ CHÍNH hai hàng mà nó đang so (lượt placement
khác? đầu vào profile đổi?) — một chuỗiHard-code ở UI sẽ nói dối khi logic
generate đổi.

Backfill: mỗi người đánh số 1..N theo `created_at` (đồng hạng giữ nguyên thứ
tự id), reason NULL = "không rõ từ trước", UI hiển thị "Kế hoạch trước đó".

Revision ID: 086_plan_versions
Revises: 085_plan_item_link
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "086_plan_versions"
down_revision: Union[str, None] = "085_plan_item_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "study_plan",
        sa.Column("version", sa.SmallInteger(), nullable=False, server_default="1"),
    )
    op.add_column("study_plan", sa.Column("reason", sa.String(length=120), nullable=True))
    op.drop_column("study_plan", "note")  # chưa từng có ai ghi vào cột này

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, user_id FROM study_plan ORDER BY user_id, created_at, id")
    ).all()
    seen: dict = {}
    for plan_id, user_id in rows:
        seen[user_id] = seen.get(user_id, 0) + 1
        bind.execute(
            sa.text("UPDATE study_plan SET version = :v WHERE id = :i"),
            {"v": seen[user_id], "i": plan_id},
        )


def downgrade() -> None:
    op.add_column("study_plan", sa.Column("note", sa.Text(), nullable=True))
    op.drop_column("study_plan", "reason")
    op.drop_column("study_plan", "version")
