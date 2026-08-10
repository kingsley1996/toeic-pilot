"""bộ đề, phạm vi lượt làm, chế độ xem đáp án, tạm dừng

Revision ID: 011_mock_test
Revises: 010_avatar
Create Date: 2026-08-10 19:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_mock_test"
down_revision: Union[str, None] = "010_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- bộ đề ---------------------------------------------------------------
    op.create_table(
        "test_collection",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Hai nhãn hiện trên thẻ bộ đề. `source_tag` là nơi phát hành ("TOEIC",
        # "parroto"), KHÔNG phải `question.source` — cột kia trả lời câu hỏi bản
        # quyền và không được lẫn với một nhãn hiển thị.
        sa.Column("source_tag", sa.String(length=32), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("published_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="ck_test_collection_status"
        ),
        sa.CheckConstraint("year IS NULL OR year BETWEEN 2000 AND 2100", name="ck_test_collection_year"),
    )
    op.create_index("ix_test_collection_status", "test_collection", ["status"])

    # Nullable: một đề lẻ vẫn phải tồn tại được. Bắt buộc thuộc bộ đề nghĩa là
    # phải bịa ra một bộ đề một phần tử mỗi lần muốn thêm một đề đơn.
    op.add_column("practice_test", sa.Column("collection_id", sa.Uuid(as_uuid=True), nullable=True))
    op.add_column("practice_test", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "practice_test", sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False)
    )
    op.create_foreign_key(
        "fk_practice_test_collection",
        "practice_test",
        "test_collection",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- lượt làm bài --------------------------------------------------------
    #
    # Ràng buộc cũ CẤM đúng thứ giao diện cho phép: nó buộc phải chọn giữa "cả
    # một đề" và "một part rời không thuộc đề nào", trong khi màn hình chọn phần
    # muốn làm sinh ra tổ hợp thứ ba — MỘT ĐỀ, MỘT TẬP PART.
    op.drop_constraint("ck_attempt_mode_fields", "attempt", type_="check")
    op.drop_constraint("ck_attempt_mode", "attempt", type_="check")
    op.drop_constraint("ck_attempt_part", "attempt", type_="check")
    op.drop_column("attempt", "mode")
    op.drop_column("attempt", "part")

    # Lượt làm LUÔN thuộc một đề. Luyện theo part giờ là "đề này, chỉ part ấy",
    # nên vẫn giữ được liên kết tới đề — thứ mà mô hình cũ đánh mất.
    op.alter_column("attempt", "test_id", nullable=False)

    op.add_column("attempt", sa.Column("scope", sa.String(length=16), server_default="full", nullable=False))
    # Trục THỨ HAI, không phải cách gọi khác của `scope`: phạm vi trả lời "làm
    # phần nào", còn cái này trả lời "có được xem đáp án khi đang làm không".
    op.add_column(
        "attempt", sa.Column("review_mode", sa.String(length=16), server_default="exam", nullable=False)
    )
    op.add_column(
        "attempt", sa.Column("status", sa.String(length=16), server_default="in_progress", nullable=False)
    )
    # Thời gian đã dùng, cộng dồn. KHÔNG tính bằng `now() - started_at`: lượt
    # làm tạm dừng được, nên đồng hồ treo tường sẽ ăn mất thời gian người học
    # không hề ngồi trước màn hình, và họ mất bài vì một lần nghỉ trưa.
    op.add_column("attempt", sa.Column("elapsed_seconds", sa.Integer(), server_default="0", nullable=False))
    op.add_column("attempt", sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_check_constraint("ck_attempt_scope", "attempt", "scope IN ('full', 'partial')")
    op.create_check_constraint(
        "ck_attempt_review_mode", "attempt", "review_mode IN ('exam', 'practice')"
    )
    op.create_check_constraint(
        "ck_attempt_status",
        "attempt",
        "status IN ('in_progress', 'submitted', 'expired', 'abandoned')",
    )
    # Nộp rồi thì phải có mốc nộp, và ngược lại. Hai cột nói cùng một chuyện nên
    # chúng không được phép nói khác nhau.
    op.create_check_constraint(
        "ck_attempt_submitted_consistent",
        "attempt",
        "(status IN ('submitted', 'expired')) = (submitted_at IS NOT NULL)",
    )

    op.create_table(
        "attempt_part",
        sa.Column("attempt_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("part", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id", "part"),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempt.id"], ondelete="CASCADE"),
        sa.CheckConstraint("part BETWEEN 1 AND 7", name="ck_attempt_part_range"),
    )

    # Cờ "Đánh dấu". Nằm trên attempt_item chứ không phải một bảng riêng: nó chỉ
    # có nghĩa trong phạm vi một lượt làm, và biến mất cùng lượt làm đó.
    op.add_column(
        "attempt_item", sa.Column("flagged", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("attempt_item", "flagged")
    op.drop_table("attempt_part")
    for name in (
        "ck_attempt_submitted_consistent",
        "ck_attempt_status",
        "ck_attempt_review_mode",
        "ck_attempt_scope",
    ):
        op.drop_constraint(name, "attempt", type_="check")
    for column in ("resumed_at", "elapsed_seconds", "status", "review_mode", "scope"):
        op.drop_column("attempt", column)
    op.alter_column("attempt", "test_id", nullable=True)
    op.add_column("attempt", sa.Column("part", sa.SmallInteger(), nullable=True))
    op.add_column("attempt", sa.Column("mode", sa.String(length=16), nullable=False, server_default="full_test"))
    op.create_check_constraint("ck_attempt_part", "attempt", "part IS NULL OR part BETWEEN 1 AND 7")
    op.create_check_constraint("ck_attempt_mode", "attempt", "mode IN ('full_test', 'part_practice')")
    op.create_check_constraint(
        "ck_attempt_mode_fields",
        "attempt",
        "(mode = 'full_test' AND test_id IS NOT NULL AND part IS NULL)"
        " OR (mode = 'part_practice' AND part IS NOT NULL AND test_id IS NULL)",
    )

    op.drop_constraint("fk_practice_test_collection", "practice_test", type_="foreignkey")
    for column in ("position", "description", "collection_id"):
        op.drop_column("practice_test", column)
    op.drop_index("ix_test_collection_status", table_name="test_collection")
    op.drop_table("test_collection")
