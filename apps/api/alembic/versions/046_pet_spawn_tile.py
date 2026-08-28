"""ô mặc định của thú cưng phải ĐỨNG ĐƯỢC (ADR-010)

Revision ID: 046_pet_spawn_tile
Revises: 045_encounter_hints
Create Date: 2026-08-28 11:20:00.000000

Mặc định cũ là `(3, 8)`, mà ô ấy nằm trong tường của `public/pet/map.json` —
hàng 8 là `#####....#.#...#.#`, cột 3 là dấu `#`. Không ai thấy con thú đứng
trong tường, vì lượt nạp đầu tiên gọi `nearestWalkable` kéo nó ra rồi ghi lại
vị trí mới. Nhưng cái kéo ấy là một lần dịch chuyển và một request `PUT` mà MỌI
tài khoản mới đều phải trả, chỉ để sửa một con số lẽ ra đã đúng.

`(3, 5)` nằm giữa dải trống lớn nhất bản đồ (`#................#`), nên nó còn
đứng được kể cả khi bản đồ được vẽ lại đôi chút trong trình sửa. `nearestWalkable`
vẫn giữ nguyên vai trò của nó: bản đồ là một tệp tĩnh mà máy chủ không đọc, nên
không có cách nào bảo đảm một ô nào đó đứng được mãi mãi.

Chỉ đổi MẶC ĐỊNH, không đụng tới hàng đã có: một con thú đang đứng ở đâu là nơi
người nuôi nó dắt tới, và viết đè lên đó là xoá một thứ đã thật sự xảy ra.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "046_pet_spawn_tile"
down_revision: Union[str, None] = "045_encounter_hints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("pet_owned", "tile_y", server_default="5")


def downgrade() -> None:
    op.alter_column("pet_owned", "tile_y", server_default="8")
