"""nhiệm vụ hồi phục là một loại chạm mặt riêng

Revision ID: 054_encounter_rescue_kind
Revises: 053_pet_xp_raw_today
Create Date: 2026-09-04 12:40:00.000000

Con thú ốm được vực dậy bằng một nhiệm vụ, và bản đầu mượn luôn làn NPC cho
việc ấy. Mượn thì kéo theo cả những thứ không thuộc về nó: nhịp sinh hai mươi
phút, trần hai cuộc mỗi loại, số bước, và mức thưởng ruby của NPC — nên cứu con
thú lại hoá ra là một nguồn thu, và một lần cứu lại tiêu mất suất NPC của người
học.

`rescue` tách hẳn: sinh **theo yêu cầu** chứ không theo đồng hồ, đúng **một
bước**, và **không trả ruby** — phần thưởng của nó là con thú đứng dậy được.

CHECK phải viết lại chứ không nới được tại chỗ; downgrade xoá các hàng `rescue`
trước khi thắt lại, vì để lại thì ràng buộc cũ không dựng nổi.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "054_encounter_rescue_kind"
down_revision: Union[str, None] = "053_pet_xp_raw_today"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_constraint("ck_encounter_kind", "encounter", type_="check")
    op.create_check_constraint(
        "ck_encounter_kind", "encounter", "kind IN ('npc', 'intruder', 'rescue')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM encounter WHERE kind = 'rescue'")
    op.drop_constraint("ck_encounter_kind", "encounter", type_="check")
    op.create_check_constraint("ck_encounter_kind", "encounter", "kind IN ('npc', 'intruder')")
