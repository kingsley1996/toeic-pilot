"""Ảnh cho từng ô ngữ liệu của Part 6/7

Revision ID: 013_passage_images
Revises: 012_question_number
Create Date: 2026-08-11

Ngữ liệu Part 6/7 vẫn là văn bản ở phần lớn trường hợp, và nên thế: bảng giá,
lịch trình, mẫu đơn viết thành text thì đọc được bằng máy đọc màn hình, phóng
to được và tìm được. Cột này dành cho chỗ quan hệ không gian mang nghĩa — biểu
đồ, sơ đồ mặt bằng, bản đồ — nơi trước đây không có chỗ nào để đặt (ADR-007).

Một ảnh cho MỖI ô chứ không phải một ảnh cho cả cụm, vì thứ tự ngữ liệu mang
nghĩa (ADR-001): "ngữ liệu 1 là biểu đồ, ngữ liệu 2 là email" phải nói được.
"""

import typing

import sqlalchemy as sa
from alembic import op

revision: str = "013_passage_images"
down_revision: typing.Union[str, None] = "012_question_number"
branch_labels: typing.Union[str, typing.Sequence[str], None] = None
depends_on: typing.Union[str, typing.Sequence[str], None] = None

_COLUMNS = ("passage_image_id", "passage_2_image_id", "passage_3_image_id")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("question_set", sa.Column(column, sa.Uuid(as_uuid=True), nullable=True))
        # RESTRICT chứ không SET NULL: xoá một ảnh đang là ngữ liệu sẽ làm câu
        # hỏi mất thứ cần để trả lời, và SET NULL biến việc đó thành im lặng.
        op.create_foreign_key(
            f"fk_question_set_{column}",
            "question_set",
            "image_asset",
            [column],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.drop_constraint(f"fk_question_set_{column}", "question_set", type_="foreignkey")
        op.drop_column("question_set", column)
