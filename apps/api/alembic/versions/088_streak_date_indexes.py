"""Index (nguoi, ngay) cho bon bang su kien cua streak.

`_streak_days` (profile_stats) UNION bon nhanh, moi nhanh loc
`(user_id, timestamp >= since)` — chay moi lan mo dashboard. Bon bang nay
thieu index ngay nen quet toan lich su user, cang hoc lau cang cham.

`IF NOT EXISTS`: dev dung `create_all` o moi lan reload nen index da co tu
model truoc khi migration chay — `op.create_index` thuong se no.

Revision ID: 088_streak_date_indexes
Revises: 087_drill_filter_codes
Create Date: 2026-09-12 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "088_streak_date_indexes"
down_revision: Union[str, None] = "087_drill_filter_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("ix_vocabulary_review_log_user_reviewed", "vocabulary_review_log", "reviewed_at"),
    ("ix_dictation_attempt_user_created", "dictation_attempt", "created_at"),
    ("ix_grammar_attempt_user_created", "grammar_attempt", "created_at"),
    ("ix_grammar_completion_user_created", "grammar_lesson_completion", "created_at"),
)


def upgrade() -> None:
    for name, table, column in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} (user_id, {column})")


def downgrade() -> None:
    for name, table, _column in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
