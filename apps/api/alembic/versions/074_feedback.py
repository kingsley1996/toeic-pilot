"""feedback — góp ý của người học, kèm mức thưởng ruby

Revision ID: 074_feedback
Revises: 073_pet_lines
Create Date: 2026-09-08 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "074_feedback"
down_revision: Union[str, None] = "073_pet_lines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("screenshot_keys", JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        # SET NULL chứ không CASCADE: xoá tài khoản admin không được xoá góp ý
        # của người học. Ai duyệt là thông tin phụ, góp ý mới là dữ liệu.
        sa.Column(
            "reviewed_by",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('bug', 'feature', 'content', 'other')", name="ck_feedback_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_feedback_status"
        ),
    )
    op.create_index("ix_feedback_status_created", "feedback", ["status", "created_at"])
    op.create_index("ix_feedback_user", "feedback", ["user_id"])

    # Hàng mức thưởng phải đi bằng MIGRATION, không bằng `DEFAULT_RUBY_RULES`.
    #
    # `services/ruby.py::rules()` chỉ gieo mặc định khi bảng RỖNG — đúng thiết
    # kế, vì bảng ấy admin sửa được và gieo đè lên sẽ hoàn tác lựa chọn của họ.
    # Hệ quả: mọi cài đặt đang chạy đã có bảy hàng, nên hàng thứ tám thêm vào
    # hằng số sẽ KHÔNG BAO GIỜ xuất hiện ở đó. Không có INSERT này thì `earn()`
    # tìm mức thưởng không thấy và duyệt góp ý trao 0 ruby — im lặng, vì mọi
    # thứ khác vẫn chạy đúng.
    #
    # `ON CONFLICT DO NOTHING` trên `source_type`: cài đặt mới đã tự gieo đủ
    # tám hàng trước khi migration này chạy, và chạy lại migration không được
    # phép vỡ.
    op.execute(
        sa.text(
            """
            INSERT INTO ruby_rule (source_type, label, amount, position, enabled)
            VALUES ('feedback_reward', 'Góp ý được duyệt', 200, 8, true)
            ON CONFLICT (source_type) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM ruby_rule WHERE source_type = 'feedback_reward'"))
    op.drop_index("ix_feedback_user", table_name="feedback")
    op.drop_index("ix_feedback_status_created", table_name="feedback")
    op.drop_table("feedback")
