"""knowledge base của TOEIC Pilot — corpus cho Trợ lý trang

Revision ID: 051_knowledge_chunk
Revises: 050_assistant_chat
Create Date: 2026-08-29 16:00:00.000000

Trợ lý hôm nay trả lời dựa trên MỘT khối SITE_GUIDE viết cứng trong mã — mọi
câu hỏi vượt khỏi khối đó hoặc bị trả "chưa có thông tin" hoặc bị trả sai theo
cảm tính. Bảng này là corpus THỨ HAI: các mục tài liệu về chính trang, đồng bộ
từ `apps/api/content/kb/*.md` bằng `app/content/sync_kb.py`.

`ref` là nguồn sự thật của chunk — nó đi vào ngữ cảnh để câu trả lời trích dẫn
lại được, và là khoá idempotent của lượt đồng bộ.

Cố ý CHƯA có cột `embedding`: retrieval hôm nay là lexical trong Python, đủ cho
một corpus vài chục chunk do người viết (ADR-003 §3.3 — dưới ngưỡng thì đo
vector là đo nhiễu). Khi corpus vượt trần, thêm cột `vector(1024)` là một
migration cộng một lớp scoring — chi phí rẻ, không phải trả trước.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "051_knowledge_chunk"
down_revision: Union[str, None] = "050_assistant_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunk",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ref", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_knowledge_chunk_ref", "knowledge_chunk", ["ref"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunk_ref", table_name="knowledge_chunk")
    op.drop_table("knowledge_chunk")
