"""trợ lý AI: cuộc hội thoại không neo vào lượt làm bài

Revision ID: 050_assistant_chat
Revises: 049_health_sample
Create Date: 2026-08-29 14:00:00.000000

`coach_conversation` từng mặc định mọi cuộc hỏi đáp neo vào một lượt làm bài —
điểm neo là NGUỒN NGỮ CẢNH, và `attempt_id NOT NULL` là cách ép điều đó. Trợ lý
trang web hỏi về chính trang web và tiến độ của người hỏi; nó không có lượt nào
để neo, và buộc nó phải có một lượt là buộc nó nói dối về nguồn ngữ cảnh.

Không thêm cột `kind`: `attempt_id NULL` đã là dấu hiệu "đây là trợ lý". Hai
nguồn sự thật cho cùng một phân loại sẽ lệch nhau ở lần đầu ai đó đặt `kind`
không khớp `attempt_id` — và không gì báo sự lệch đó.

Chỉ mục duy nhất TỪNG PHẦN là thứ ép "mỗi người một cuộc trợ lý" ở tầng
database, thay vì bằng một phép đọc-rồi-ghi trong Python. Không có nó, hai
request đồng thời đều thấy "chưa có cuộc nào" và đều tạo một cuộc: lịch sử tách
làm hai, trợ lý thỉnh thoảng quên các lượt trước, và người dùng kết luận là AI
kém chứ không phải là lỗi. Cùng hình dạng với `ensure_pet` và gieo lười
`pet_species` — hai lần repo này đã dính đúng kiểu ấy.

`postgresql_where` chứ không phải UNIQUE cả cột: cuộc của coach neo vào lượt
làm bài và một người có nhiều lượt, nên chỉ hàng `attempt_id IS NULL` mới bị
ràng buộc là một.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "050_assistant_chat"
down_revision: Union[str, None] = "049_health_sample"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("coach_conversation", "attempt_id", existing_type=sa.Uuid(), nullable=True)
    op.create_index(
        "uq_coach_conversation_assistant",
        "coach_conversation",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("attempt_id IS NULL"),
        sqlite_where=sa.text("attempt_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_coach_conversation_assistant", table_name="coach_conversation")
    # Cố ý để Postgres TỰ từ chối khi còn hàng trợ lý (attempt_id NULL): xoá
    # lịch sử hội thoại của người dùng là quyết định của con người, không phải
    # của một lệnh downgrade chạy silently.
    op.alter_column("coach_conversation", "attempt_id", existing_type=sa.Uuid(), nullable=False)
