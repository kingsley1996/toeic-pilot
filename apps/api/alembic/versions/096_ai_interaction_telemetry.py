"""Telemetry retrieval/agent cho sổ cái AI (guides §11, AI-PRODUCTION-PLAN P2).

Revision ID: 096_ai_interaction_telemetry
Revises: 095_knowledge_chunk_metadata
Create Date: 2026-09-21 00:00:00.000000

Nullable toàn bộ (trừ cờ reranker có default): hàng cũ giữ NULL nghĩa là
"chưa đo", không phải dữ liệu thiếu. Per-tool latency/error KHÔNG vào đây —
vào transcript JSONL theo `request_id`, tránh phình bảng nóng.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "096_ai_interaction_telemetry"
down_revision: Union[str, None] = "095_knowledge_chunk_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("ai_interaction", sa.Column("workflow", sa.String(32), nullable=True))
    op.add_column("ai_interaction", sa.Column("retrieved_refs", JSONB(), nullable=True))
    op.add_column("ai_interaction", sa.Column("retrieval_ms", sa.Integer(), nullable=True))
    op.add_column(
        "ai_interaction",
        sa.Column("reranker_used", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("ai_interaction", sa.Column("step_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_interaction", "step_count")
    op.drop_column("ai_interaction", "reranker_used")
    op.drop_column("ai_interaction", "retrieval_ms")
    op.drop_column("ai_interaction", "retrieved_refs")
    op.drop_column("ai_interaction", "workflow")
