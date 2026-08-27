"""ruby_event + ruby_rule: đơn vị thứ hai, thưởng cho việc LÀM XONG (ADR-011)

Revision ID: 038_ruby
Revises: 037_pet_species
Create Date: 2026-08-27 11:10:00.000000

Vì sao không tiêu thẳng XP: XP nuôi level, và **level không bao giờ tụt** — đó
là thuộc tính mà sổ cái `xp_event` được dựng ra để có. Cho tiêu XP là phá đúng
thuộc tính ấy, hoặc buộc phải nuôi thêm một khái niệm "XP đã tiêu" chạy song
song rồi lệch khỏi sổ cái.

`ruby_event` mang cùng hình dạng với `xp_event` và khác đúng hai chỗ, cả hai đều
có lý do:

- **Không có `awarded_on`.** `xp_event` cần cột ngày vì nó có trần mỗi ngày phải
  cộng lại lúc ghi. Ruby không có trần: nội dung tự giới hạn tốc độ, vì một bài
  dictation chỉ xong được một lần và khoá duy nhất là thứ cưỡng chế điều đó.
- **`amount` cho phép ÂM.** Tiêu là một hàng âm chứ không phải một phép trừ lên
  số dư, nên lịch sử vẫn trả lời được "đã tiêu vào đâu". `CHECK (amount <> 0)`
  chặn hàng vô nghĩa; số dư âm được chặn ở tầng dịch vụ bằng khoá tư vấn
  (ADR-011 §5), không phải ở đây — một `CHECK` trên tổng là thứ Postgres không
  có, và một cột số dư để `CHECK` lên được thì đã là nguồn sự thật thứ hai.

**Bảng `ruby_rule` để RỖNG.** Bộ mặc định sống ở `app/models/ruby.py::
DEFAULT_RUBY_RULES` và gieo LƯỜI ở lần đọc đầu, đúng khuôn `pet_species` và
`frame_tier`: gieo trong migration nghĩa là danh sách nằm ở hai chỗ, và cái ở
migration đông cứng lại ở thời điểm viết.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038_ruby"
down_revision: Union[str, None] = "037_pet_species"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ruby_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Khoá này LÀM LUÔN việc chống cày, thay cho một đoạn `if` ai đó phải nhớ
        # viết ở mỗi đường trao. Lưu ý Postgres coi mọi NULL là khác nhau, nên nó
        # không chặn được hàng có `source_id` NULL — các nguồn lặp theo ngày phải
        # sinh uuid TẤT ĐỊNH từ (người, ngày địa phương, nguồn), đúng cách
        # `progression.task_source_id` đã làm.
        sa.UniqueConstraint("user_id", "source_type", "source_id", name="uq_ruby_event_source"),
        sa.CheckConstraint("amount <> 0", name="ck_ruby_event_amount"),
    )
    op.create_index("ix_ruby_event_user_id", "ruby_event", ["user_id"])

    op.create_table(
        "ruby_rule",
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.SmallInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("source_type"),
        sa.CheckConstraint("amount > 0", name="ck_ruby_rule_amount"),
    )


def downgrade() -> None:
    op.drop_table("ruby_rule")
    op.drop_index("ix_ruby_event_user_id", table_name="ruby_event")
    op.drop_table("ruby_event")
