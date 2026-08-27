"""pet_species: danh sách loài, admin sửa được mà không cần deploy

Revision ID: 037_pet_species
Revises: 036_pet_xp_day
Create Date: 2026-08-27 02:40:00.000000

**Bảng để RỖNG, không gieo dữ liệu ở đây.** Mười hai loài mặc định sống ở
`app/models/pet.py::DEFAULT_PET_SPECIES` và được gieo LƯỜI ở lần đọc đầu tiên,
đúng khuôn `frame_tier` và `badge_rule`.

Một nguồn sự thật duy nhất là điều đáng giá: gieo trong migration nghĩa là danh
sách nằm ở HAI chỗ, và cái ở migration đông cứng ở thời điểm viết — thêm loài
thứ mười ba về sau thì máy mới có mười ba còn máy cũ có mười hai, cùng một mã
nguồn.

**Không có khoá ngoại từ `pet_state.species` sang đây**, và đó là chủ ý. Khoá
ngoại sẽ chặn việc xoá một loài đang có người nuôi — nghe như bảo vệ, nhưng nó
biến "tắt một loài" thành một thao tác database thay vì một cái công tắc, và
màn quản trị lại phải giải thích một lỗi ràng buộc. Đường đúng là `enabled`:
loài biến khỏi gacha, con thú đang nuôi vẫn vẽ ra được. Giá phải trả là một mã
mồ côi có thể tồn tại; `tileForSpecies` rơi về ô mặc định nên nó không thành ô
trống.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "037_pet_species"
down_revision: Union[str, None] = "036_pet_xp_day"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pet_species",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("tile", sa.SmallInteger(), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False, server_default="common"),
        sa.Column("position", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("code"),
        # `creatures.png` là lưới 10x18. Ô ngoài khoảng đó vẽ ra một mảnh trong
        # suốt — con thú tàng hình, không lỗi nào, chỉ người mở trứng mới biết.
        sa.CheckConstraint("tile >= 0 AND tile < 180", name="ck_pet_species_tile"),
        sa.CheckConstraint(
            "tier IN ('common', 'uncommon', 'rare', 'epic')", name="ck_pet_species_tier"
        ),
    )


def downgrade() -> None:
    op.drop_table("pet_species")
