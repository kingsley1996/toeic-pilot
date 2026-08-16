"""vocabulary tree: collection -> collection_item -> topic

Revision ID: 024_vocabulary_tree
Revises: 023_option_translation
Create Date: 2026-08-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "024_vocabulary_tree"
down_revision: str | None = "023_option_translation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Khoá ngoại được đặt tên tường minh — cùng luật với migration 007: để
    # Postgres tự đặt tên thì cặp `drop_constraint(None, ...)` ở downgrade không
    # bao giờ chạy được, và lỗi chỉ lộ khi có người thật sự downgrade.
    #
    # Không di chuyển dữ liệu: các topic hiện có giữ collection_item_id NULL và
    # vẫn dùng được qua danh sách phẳng. Màn admin liệt kê topic chưa xếp riêng.
    op.create_table(
        "vocabulary_collection",
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
            "status IN ('draft', 'published', 'archived')", name="ck_vocabulary_collection_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        op.f("ix_vocabulary_collection_status"), "vocabulary_collection", ["status"], unique=False
    )
    op.create_table(
        "vocabulary_collection_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
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
            "status IN ('draft', 'published', 'archived')",
            name="ck_vocabulary_collection_item_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["vocabulary_collection.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vocabulary_collection_item_status"),
        "vocabulary_collection_item",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vocabulary_collection_item_collection_id"),
        "vocabulary_collection_item",
        ["collection_id"],
        unique=False,
    )
    op.add_column("topic", sa.Column("collection_item_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_topic_collection_item_id"), "topic", ["collection_item_id"], unique=False
    )
    op.create_foreign_key(
        "fk_topic_collection_item_id",
        "topic",
        "vocabulary_collection_item",
        ["collection_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_topic_collection_item_id", "topic", type_="foreignkey")
    op.drop_index(op.f("ix_topic_collection_item_id"), table_name="topic")
    op.drop_column("topic", "collection_item_id")
    op.drop_index(
        op.f("ix_vocabulary_collection_item_collection_id"),
        table_name="vocabulary_collection_item",
    )
    op.drop_index(
        op.f("ix_vocabulary_collection_item_status"), table_name="vocabulary_collection_item"
    )
    op.drop_table("vocabulary_collection_item")
    op.drop_index(op.f("ix_vocabulary_collection_status"), table_name="vocabulary_collection")
    op.drop_table("vocabulary_collection")
