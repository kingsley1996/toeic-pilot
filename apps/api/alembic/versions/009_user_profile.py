"""user profile, and a mark for when the password last changed

Revision ID: 009_user_profile
Revises: 008_dictation_completion_flag
Create Date: 2026-08-10 15:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_user_profile"
down_revision: Union[str, None] = "008_dictation_completion_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, và cố ý KHÔNG backfill bằng now(). Cột này có nghĩa là "mật khẩu
    # đã đổi vào lúc này", nên điền giá trị cho tài khoản chưa từng đổi là ghi
    # một sự kiện không xảy ra. Nó cũng sẽ vô hiệu hoá mọi phiên đang đăng nhập
    # ngay khi migration chạy, vì token phát hành trước bản này không mang `iat`.
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "user_profile",
        # Khoá chính CHÍNH LÀ khoá ngoại: đó là thứ bảo đảm quan hệ 1-1, chứ
        # không phải một quy ước mà tầng ứng dụng phải tự nhớ.
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=True),
        sa.Column(
            "timezone", sa.String(length=64), server_default="Asia/Ho_Chi_Minh", nullable=False
        ),
        sa.Column("locale", sa.String(length=10), server_default="vi", nullable=False),
        sa.Column("target_score", sa.Integer(), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("minutes_per_day", sa.Integer(), nullable=True),
        sa.Column("daily_new_limit", sa.Integer(), nullable=True),
        sa.Column("preferred_accent", sa.String(length=8), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint(
            "target_score IS NULL OR "
            "(target_score BETWEEN 10 AND 990 AND target_score % 5 = 0)",
            name="ck_user_profile_target_score",
        ),
        sa.CheckConstraint(
            "minutes_per_day IS NULL OR minutes_per_day BETWEEN 5 AND 480",
            name="ck_user_profile_minutes_per_day",
        ),
        sa.CheckConstraint(
            "daily_new_limit IS NULL OR daily_new_limit BETWEEN 1 AND 200",
            name="ck_user_profile_daily_new_limit",
        ),
        sa.CheckConstraint(
            "preferred_accent IS NULL OR "
            "preferred_accent IN ('en-US', 'en-GB', 'en-AU', 'en-CA')",
            name="ck_user_profile_preferred_accent",
        ),
    )

    # Tài khoản đã tồn tại phải có hàng hồ sơ NGAY tại đây, không phải tạo lười
    # lúc đọc lần đầu. Nếu để lười thì mọi chỗ đọc hồ sơ đều phải xử lý trường
    # hợp thiếu, và chỗ nào quên thì đó là lỗi 500 — trong khi ở đây chỉ là một
    # câu INSERT chạy đúng một lần.
    op.execute(
        "INSERT INTO user_profile (user_id) SELECT id FROM users "
        "ON CONFLICT (user_id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("user_profile")
    op.drop_column("users", "password_changed_at")
