"""Mỗi mục kế hoạch mang ĐÍCH ĐẾN của nó.

`study_plan_item.link` — generator biết đích cụ thể của từng mục (board từ
vựng theo chủ đề, drill KÈM BỘ LỌC NHÃN `?labels=`, topic chép chính tả, bài
học ngữ pháp, đề thi thử). Trước đây UI tự nối URL từ `kind`+`part` và chỉ
nối được tới CỬA module — nói "Luyện Part 7 — Câu hỏi suy luận" rồi thả người
học trước bảy checkbox là đi được nửa đường. Để server dựng một lần, UI chỉ
theo. `link` NULL = hàng cũ hoặc đường do kind suy ra — bảng `planItemHref`
còn đó làm fallback, không phải nguồn chính nữa.

`study_plan.starts_at` — móc neo của lịch. Ngày của mục suy từ
`starts_at + pack(vị trí)`, KHÔNG từ "hôm nay": tick xong một mục không được
kéo cả lịch trôi về sớm (người học gọi đó là "dồn task", và họ đúng — lịch
phải là lời hẹn đọc được, không phải khối nhảy theo từng cú bấm). "Dời lịch"
là hành động tường minh, ghi lại móc neo; suy lúc đọc vẫn nguyên bất biến
"không lưu ngày từng mục".

Revision ID: 085_plan_item_link
Revises: 084_planner_spec_columns
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "085_plan_item_link"
down_revision: Union[str, None] = "084_planner_spec_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("study_plan_item", sa.Column("link", sa.String(length=200), nullable=True))
    op.add_column("study_plan", sa.Column("starts_at", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("study_plan", "starts_at")
    op.drop_column("study_plan_item", "link")
