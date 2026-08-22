"""user_identity: đăng nhập bằng Google và Apple

Revision ID: 034_user_identity
Revises: 033_progression_art
Create Date: 2026-08-22 14:00:00.000000

Hai thay đổi, và cái thứ hai mới là cái đáng chú ý: `users.hashed_password` bỏ
NOT NULL. Cách rẻ hơn để tránh migration đó là nhét một chuỗi băm rác vào cho tài
khoản đăng nhập bằng nhà cung cấp — và đó chính là cái bẫy: hàng như thế trông y
hệt tài khoản có mật khẩu, nên mọi phép hỏi "người này đặt mật khẩu chưa" đều trả
lời sai, kể cả đường đổi mật khẩu.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034_user_identity"
down_revision: str | None = "033_progression_art"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_identity",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=16), nullable=False),
        # Định danh bền bên nhà cung cấp. Khoá tra cứu là cột này, KHÔNG phải
        # email: email đổi được, và với Apple nó có thể là địa chỉ chuyển tiếp ẩn.
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("provider", "subject", name="uq_user_identity_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_identity_user_provider"),
    )
    op.create_index("ix_user_identity_user_id", "user_identity", ["user_id"])

    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Hạ cấp sẽ HỎNG nếu có tài khoản chưa từng đặt mật khẩu, và đó là hành vi
    # đúng: những hàng đó không hợp lệ dưới lược đồ cũ, và một lệnh xoá âm thầm
    # ở đây là xoá tài khoản người dùng thật.
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_user_identity_user_id", table_name="user_identity")
    op.drop_table("user_identity")
