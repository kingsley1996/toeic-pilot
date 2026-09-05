"""grammar topic code nullable — giáo trình rộng hơn taxonomy

Revision ID: 060_grammar_topic_code_nullable
Revises: 059_grammar_lesson_kind
Create Date: 2026-09-05 18:00:00.000000

Taxonomy có 12 mã grammar; giáo trình người soạn cần 18 chủ đề, gồm những bài
nền tảng ("Kiến thức cơ bản", "Câu điều kiện", "Danh động từ") nằm ngoài 12 mã
đó. Không nới `code` thì chỉ hai đường: nhét mã bịa vào (giết dây nối nhãn ↔
câu — `code` được kiểm bằng registry là để không ai làm được thế) hoặc nhốt
người soạn trong 12 chủ đề.

NULL = chủ đề theory thuần: không "luyện tập theo nhãn", không cổng ngưỡng 12
câu; lesson practice của nó vẫn gắn câu tay. UNIQUE giữ nguyên — Postgres cho
nhiều NULL, và đó đúng là语义 muốn nói: các bài không mã không đụng nhau.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "060_grammar_topic_code_nullable"
down_revision: Union[str, None] = "059_grammar_lesson_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("grammar_topic", "code", existing_type=sa.String(length=48), nullable=True)


def downgrade() -> None:
    # Sẽ chết nếu còn topic null-code — đúng: những chủ đề đó không có chỗ nào
    # để về trong thế giới cũ.
    op.alter_column("grammar_topic", "code", existing_type=sa.String(length=48), nullable=False)
