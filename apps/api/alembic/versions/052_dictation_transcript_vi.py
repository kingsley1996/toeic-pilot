"""bản dịch tiếng Việt cho câu dictation

Revision ID: 052_dictation_transcript_vi
Revises: 051_knowledge_chunk
Create Date: 2026-09-02 23:10:00.000000

Dictation đo được người học có NGHE ra chữ không, chứ không đo họ có hiểu
không: gõ đúng trọn một câu vẫn có thể chẳng biết nó nói gì, và trước cột này
không có chỗ nào trong luồng nói cho họ biết. Từ vựng đã mang `example_vi` đúng
vì lý do ấy, nên chỗ thiếu nằm ở đây.

Nullable, và đó không phải sự lười: 134 câu có sẵn phải sống tiếp trong lúc bản
dịch được viết dần, và một câu chưa dịch thì khối lời thoại chỉ hiện tiếng Anh
— không hỏng gì.

Cột này KHÔNG vào `source_hash`. Hash là `sha256(text|voice|engine|version)` và
cổng publish so nó với hash đã lưu để phát hiện clip thu từ bản chữ cũ; kéo bản
dịch vào đó thì sửa một dấu phẩy tiếng Việt là 134 clip bị đánh dấu lỗi thời và
đòi thu lại — hỏng im lặng, vì mọi thứ vẫn phát được.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "052_dictation_transcript_vi"
down_revision: Union[str, None] = "051_knowledge_chunk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("dictation_item", sa.Column("transcript_vi", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("dictation_item", "transcript_vi")
