"""dictation hierarchy: topic -> section -> story

Revision ID: 007_dictation_hierarchy
Revises: 006_dictation_audio_optional
Create Date: 2026-08-09 20:11:59.744388
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_dictation_hierarchy"
down_revision: Union[str, None] = "006_dictation_audio_optional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sinh bằng --autogenerate rồi sửa tay ĐÚNG MỘT CHỖ: khoá ngoại story_id
    # được đặt tên tường minh. Autogenerate ghi `create_foreign_key(None, ...)`,
    # để Postgres tự đặt tên, và cặp với nó ở downgrade là
    # `drop_constraint(None, ...)` — câu lệnh đó không bao giờ chạy được. Lỗi chỉ
    # lộ ra khi có người thật sự downgrade, tức là lúc tệ nhất.
    #
    # Không di chuyển dữ liệu: các câu dictation đã có giữ nguyên story_id NULL
    # và vẫn dùng được. Chúng không xuất hiện trong luồng duyệt theo cây cho tới
    # khi được gán vào một story; màn admin liệt kê chúng riêng.
    op.create_table(
        "dictation_topic",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="ck_dictation_topic_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_dictation_topic_status"), "dictation_topic", ["status"], unique=False)
    op.create_table(
        "dictation_section",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="ck_dictation_section_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["dictation_topic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dictation_section_status"), "dictation_section", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_dictation_section_topic_id"), "dictation_section", ["topic_id"], unique=False
    )
    op.create_table(
        "dictation_story",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="ck_dictation_story_status"
        ),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_dictation_story_difficulty"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["section_id"], ["dictation_section.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dictation_story_section_id"), "dictation_story", ["section_id"], unique=False
    )
    op.create_index(op.f("ix_dictation_story_status"), "dictation_story", ["status"], unique=False)
    op.add_column("dictation_item", sa.Column("story_id", sa.Uuid(), nullable=True))
    op.add_column("dictation_item", sa.Column("position", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_dictation_item_story_id"), "dictation_item", ["story_id"], unique=False
    )
    op.create_foreign_key(
        "fk_dictation_item_story_id",
        "dictation_item",
        "dictation_story",
        ["story_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_dictation_item_story_position",
        "dictation_item",
        "(story_id IS NULL) = (position IS NULL)",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("ck_dictation_item_story_position", "dictation_item", type_="check")
    op.drop_constraint("fk_dictation_item_story_id", "dictation_item", type_="foreignkey")
    op.drop_index(op.f("ix_dictation_item_story_id"), table_name="dictation_item")
    op.drop_column("dictation_item", "position")
    op.drop_column("dictation_item", "story_id")
    op.drop_index(op.f("ix_dictation_story_status"), table_name="dictation_story")
    op.drop_index(op.f("ix_dictation_story_section_id"), table_name="dictation_story")
    op.drop_table("dictation_story")
    op.drop_index(op.f("ix_dictation_section_topic_id"), table_name="dictation_section")
    op.drop_index(op.f("ix_dictation_section_status"), table_name="dictation_section")
    op.drop_table("dictation_section")
    op.drop_index(op.f("ix_dictation_topic_status"), table_name="dictation_topic")
    op.drop_table("dictation_topic")
    # ### end Alembic commands ###
