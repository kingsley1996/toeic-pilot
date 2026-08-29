"""Con thú đang nuôi của một học viên (ADR-010 §4).

**Một hàng cho mỗi người, và khoá chính CHÍNH LÀ khoá ngoại.** Đó là thứ ép quan
hệ 1-1 ở tầng database thay vì bằng một quy ước ai đó phải nhớ — cùng hình dạng
với `user_profile`.

Bản trước của góc thú cưng giữ trạng thái **trong bộ nhớ trang**: đóng tab là
mất. Bảng này là lời trả lời cho điều đó, và hai cột dưới đây mang gần hết ý
nghĩa của nó.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# JSONB trên PostgreSQL, JSON thường trên SQLite của bộ test — cùng lối dictation.py.
_JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class PetState(Base):
    """Góc thú cưng của MỘT NGƯỜI: đang nuôi con nào, và những gì thuộc về người.

    **Chỉ số của từng con KHÔNG nằm ở đây** — chúng ở `pet_owned`, một hàng cho
    mỗi con. Trước đó cả góc chỉ có một bộ chỉ số dùng chung, nên đổi con là con
    mới thừa hưởng độ no của con cũ và con cũ mất sạch quá trình được chăm: mỗi
    con là một sinh vật riêng với lịch sử riêng, mà bảng lại chỉ kể được một
    lịch sử.

    Hai thứ ở lại đây vì chúng thuộc về NGƯỜI CHƠI, không thuộc con nào:

      · `species` — đang nuôi con nào.
      · `rolls_since_rare` — bộ đếm an ủi của gacha; nó đo mấy quả trứng vừa mở,
        không đo con vật nào cả.

    Trần XP mỗi ngày từng ở đây và **đã chuyển sang từng con** (migration `042`):
    trần này bảo vệ tính chất "một con không lên max level trong một buổi", mà
    level là của từng con — để chung thì một con vừa nở ra không nhận nổi một
    điểm XP nào cho tới hôm sau, vì trần đã cạn bởi con trước đó.
    """

    __tablename__ = "pet_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    species: Mapped[str] = mapped_column(String(32), nullable=False)
    """Mã loài ĐANG NUÔI.

    **Không có CHECK, và đó là chủ ý** — cùng lý do `user_profile.pet` không có:
    danh sách loài sống ở bảng `pet_species` để admin sửa được mà không cần
    deploy. Một CHECK ở đây là chỗ thứ hai phải nhớ sửa mỗi lần thêm loài, và là
    chỗ bị quên báo lỗi muộn nhất.
    """

    rolls_since_rare: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    """Bộ đếm an ủi của gacha: đã mở bao nhiêu quả liên tiếp mà chưa ra hạng hiếm.

    Đây là một BỘ ĐẾM chứ không phải sổ cái, và đánh đổi ấy đúng: nó không mua
    được gì, không ai khiếu nại về nó, và mỗi lần ra hạng hiếm là nó lại về 0 —
    nó không có quá khứ để mà kể.
    """

    next_npc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_intruder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Lần chạm mặt kế tiếp SỚM NHẤT có thể xảy ra (ADR-012 §1).

    Hẹn giờ được **chốt ngay khi cuộc trước kết thúc**, kèm một khoảng ngẫu
    nhiên — chứ không phải bốc xúc xắc ở mỗi lần đọc. Khác biệt ấy là thứ chặn
    một hành vi rất cụ thể: nếu mỗi lần đọc là một lần bốc, thì bấm F5 mười lần
    sẽ gọi NPC ra nhanh gấp mười, và cái góc này lập tức dạy người ta bấm lại
    trang thay vì học.

    NULL = chưa hẹn lần nào; lần đọc đầu tiên đặt mốc chứ không sinh ngay, nên
    một tài khoản mới không bị NPC nhảy vào mặt ở giây thứ nhất.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<PetState nuôi {self.species}>"


class PetSpecies(Base):
    """Một loài thú nuôi được.

    **Dữ liệu, không phải hằng số trong mã** — cùng khuôn `frame_tier` và
    `badge_rule` (ROADMAP §4w): thêm một loài không cần deploy.

    `tile` là chỉ số ô trong `public/pet/creatures.png`, và đó là chỗ bản kế
    hoạch đoán sai. ADR-010 §6.3 viết rằng khoá sprite phải là **tập đóng** phía
    frontend, y như `BadgePublic.icon`, để backend thêm loài mà frontend chưa có
    ảnh thì thành lỗi `tsc`. Lập luận đó đúng cho huy hiệu, vì frontend phải BIẾT
    vẽ hình gì — nó gọi một component Lucide có tên. Ở đây frontend chỉ cắt một ô
    ra khỏi tấm ghép, nên mọi chỉ số hợp lệ đều có ảnh và không có gì để `tsc`
    bắt. Ràng buộc thật nằm ở khoảng số, và CHECK là chỗ đúng cho nó.
    """

    __tablename__ = "pet_species"
    __table_args__ = (
        # `creatures.png` là lưới 10x18. Ô ngoài khoảng đó vẽ ra một mảnh trong
        # suốt — con thú tàng hình, không có lỗi nào, và chỉ người mở trứng ra
        # mới biết.
        CheckConstraint("tile >= 0 AND tile < 180", name="ck_pet_species_tile"),
        CheckConstraint(
            "tier IN ('common', 'uncommon', 'rare', 'epic', 'legendary', 'god')",
            name="ck_pet_species_tier",
        ),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    """Tên hiện cho người học. Tiếng Việt: đây là phần học viên nhìn thấy."""

    tile: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False, server_default="common")
    """Hạng hiếm. Chưa dùng tới ở lát này — gacha đọc nó (ADR-010 §6.3).

    Có mặt từ bây giờ vì nó là thuộc tính của LOÀI, không phải của trứng: thêm nó
    sau nghĩa là mở màn quản trị ra lần nữa và điền lại cho từng hàng.
    """

    drop_weight: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="10")
    """Trọng số rơi khi mở trứng. Càng lớn càng hay ra.

    Trọng số chứ không phải phần trăm, và đó là điều khiến bảng này sửa được an
    toàn: phần trăm phải cộng lại đúng 100, nên tắt một loài hay thêm một loài
    biến cả bảng thành sai và ai đó phải chỉnh tay từng hàng. Trọng số thì tự
    chuẩn hoá — tỉ lệ in ra màn hình là `weight / tổng weight đang bật`, nên nó
    luôn khớp với bảng cấu hình dù bảng có thay đổi thế nào (ADR-010 §6.4).
    """

    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    """Tắt thay vì xoá.

    Xoá một loài mà ai đó đang nuôi để lại `pet_state.species` trỏ vào hư không —
    và vì không có khoá ngoại (xem migration), database sẽ không ngăn. Tắt thì
    loài biến khỏi gacha nhưng con thú đang nuôi vẫn vẽ ra được.
    """

    def __repr__(self) -> str:
        return f"<PetSpecies {self.code} tile={self.tile} {self.tier}>"


"""Mười hai loài đầu tiên, gieo LƯỜI ở lần đọc đầu — không gieo trong migration.

Một nguồn sự thật duy nhất, cùng hình dạng `DEFAULT_FRAME_TIERS`. Hệ quả: **bảng
rỗng nghĩa là "chưa từng cấu hình", không phải "cố ý để trống"** — xoá hết mọi
loài thì lần đọc sau gieo lại đủ mười hai. Muốn bỏ một loài thì TẮT nó.

Chỉ số ô đã soi từng con để xác nhận, không đoán theo mô tả — xem
`public/pet/CREDITS.md` để biết cách đổi chỉ số sang toạ độ.
"""
"""Bốn mươi loài mặc định, gieo LƯỜI ở lần đọc đầu.

Chọn tay từ `public/pet/creatures.png` bằng cách giải mã tấm ghép rồi phóng to
từng ô mà xem — xem `apps/web/src/components/petland-bestiary.ts` để biết ô nào
là con gì. **Không đoán theo tên hàng**: ô 170 trông như cá heo ở cỡ 16px và
thật ra là con tê giác, ô 103 là con vẹt chứ không phải gà trống, và ô 123 là
bình sữa chứ không phải vịt. Đặt nhầm tên thì hàng dữ liệu vẫn hợp lệ, chỉ có
người mở trứng ra mới biết.

Không loài nào dùng chung một ô: một ô hai tên là hai con thú giống hệt nhau
trong tủ, và người chơi đọc ra là hỏng chứ không phải là hai loài.

Thang năm hạng, tỉ lệ rơi tính từ trọng số (`drop_weight`) chứ không phải phần
trăm — xem `PetSpecies.drop_weight`. Với bảng này: thường 49,3% · ít gặp 34,2%
· hiếm 11,0% · cực hiếm 3,8% · **huyền thoại 1,6%** (0,27% cho mỗi con). Huyền
thoại hiếm tới mức ấy là cố ý, và bộ đếm an ủi mới là thứ giữ cho nó không thành
vô vọng: sau mười quả không ra hạng hiếm thì quả sau chắc chắn ra hạng hiếm trở
lên, và trong nhóm ấy huyền thoại chiếm 10%.
"""
DEFAULT_PET_SPECIES: tuple[dict[str, object], ...] = (
    {
        "code": "duck",
        "label": "Vịt",
        "tile": 150,
        "tier": "common",
        "position": 1,
        "drop_weight": 40,
    },
    {
        "code": "squirrel",
        "label": "Sóc",
        "tile": 175,
        "tier": "common",
        "position": 2,
        "drop_weight": 40,
    },
    {
        "code": "frog",
        "label": "Ếch",
        "tile": 147,
        "tier": "common",
        "position": 3,
        "drop_weight": 40,
    },
    {
        "code": "rabbit",
        "label": "Thỏ",
        "tile": 177,
        "tier": "common",
        "position": 4,
        "drop_weight": 40,
    },
    {
        "code": "sheep",
        "label": "Cừu",
        "tile": 153,
        "tier": "common",
        "position": 5,
        "drop_weight": 40,
    },
    {
        "code": "goat",
        "label": "Dê",
        "tile": 151,
        "tier": "common",
        "position": 6,
        "drop_weight": 40,
    },
    {
        "code": "hedgehog",
        "label": "Nhím",
        "tile": 143,
        "tier": "common",
        "position": 7,
        "drop_weight": 40,
    },
    {
        "code": "parrot",
        "label": "Vẹt",
        "tile": 103,
        "tier": "common",
        "position": 8,
        "drop_weight": 40,
    },
    {
        "code": "crab",
        "label": "Cua",
        "tile": 145,
        "tier": "common",
        "position": 9,
        "drop_weight": 40,
    },
    {
        "code": "cat",
        "label": "Mèo",
        "tile": 169,
        "tier": "uncommon",
        "position": 10,
        "drop_weight": 25,
    },
    {
        "code": "monkey",
        "label": "Khỉ",
        "tile": 168,
        "tier": "uncommon",
        "position": 11,
        "drop_weight": 25,
    },
    {
        "code": "turtle",
        "label": "Rùa",
        "tile": 149,
        "tier": "uncommon",
        "position": 12,
        "drop_weight": 25,
    },
    {
        "code": "otter",
        "label": "Rái cá",
        "tile": 176,
        "tier": "uncommon",
        "position": 13,
        "drop_weight": 25,
    },
    {
        "code": "skunk",
        "label": "Chồn hôi",
        "tile": 179,
        "tier": "uncommon",
        "position": 14,
        "drop_weight": 25,
    },
    {
        "code": "bat",
        "label": "Dơi",
        "tile": 130,
        "tier": "uncommon",
        "position": 15,
        "drop_weight": 25,
    },
    {
        "code": "lizard",
        "label": "Thằn lằn",
        "tile": 146,
        "tier": "uncommon",
        "position": 16,
        "drop_weight": 25,
    },
    {
        "code": "camel",
        "label": "Lạc đà",
        "tile": 129,
        "tier": "uncommon",
        "position": 17,
        "drop_weight": 25,
    },
    {
        "code": "bear_cub",
        "label": "Gấu con",
        "tile": 92,
        "tier": "uncommon",
        "position": 18,
        "drop_weight": 25,
    },
    {
        "code": "snake",
        "label": "Rắn",
        "tile": 148,
        "tier": "uncommon",
        "position": 19,
        "drop_weight": 25,
    },
    {
        "code": "owl",
        "label": "Cú",
        "tile": 117,
        "tier": "rare",
        "position": 20,
        "drop_weight": 10,
    },
    {
        "code": "deer",
        "label": "Hươu",
        "tile": 161,
        "tier": "rare",
        "position": 21,
        "drop_weight": 10,
    },
    {
        "code": "raccoon",
        "label": "Gấu mèo",
        "tile": 178,
        "tier": "rare",
        "position": 22,
        "drop_weight": 10,
    },
    {
        "code": "eagle",
        "label": "Đại bàng",
        "tile": 134,
        "tier": "rare",
        "position": 23,
        "drop_weight": 10,
    },
    {
        "code": "zebra",
        "label": "Ngựa vằn",
        "tile": 155,
        "tier": "rare",
        "position": 24,
        "drop_weight": 10,
    },
    {
        "code": "boar",
        "label": "Lợn rừng",
        "tile": 160,
        "tier": "rare",
        "position": 25,
        "drop_weight": 10,
    },
    {
        "code": "polar_bear",
        "label": "Gấu trắng",
        "tile": 164,
        "tier": "rare",
        "position": 26,
        "drop_weight": 10,
    },
    {
        "code": "ostrich",
        "label": "Đà điểu",
        "tile": 154,
        "tier": "rare",
        "position": 27,
        "drop_weight": 10,
    },
    {
        "code": "tiger",
        "label": "Hổ",
        "tile": 157,
        "tier": "epic",
        "position": 28,
        "drop_weight": 4,
    },
    {
        "code": "bear",
        "label": "Gấu",
        "tile": 165,
        "tier": "epic",
        "position": 29,
        "drop_weight": 4,
    },
    {
        "code": "giraffe",
        "label": "Hươu cao cổ",
        "tile": 159,
        "tier": "epic",
        "position": 30,
        "drop_weight": 4,
    },
    {
        "code": "lion",
        "label": "Sư tử",
        "tile": 156,
        "tier": "epic",
        "position": 31,
        "drop_weight": 4,
    },
    {
        "code": "elephant",
        "label": "Voi",
        "tile": 158,
        "tier": "epic",
        "position": 32,
        "drop_weight": 4,
    },
    {
        "code": "gorilla",
        "label": "Khỉ đột",
        "tile": 166,
        "tier": "epic",
        "position": 33,
        "drop_weight": 4,
    },
    {
        "code": "rhino",
        "label": "Tê giác",
        "tile": 170,
        "tier": "epic",
        "position": 34,
        "drop_weight": 4,
    },
    {
        "code": "unicorn",
        "label": "Kỳ lân",
        "tile": 51,
        "tier": "legendary",
        "position": 35,
        "drop_weight": 2,
    },
    {
        "code": "pegasus",
        "label": "Thiên mã",
        "tile": 30,
        "tier": "legendary",
        "position": 36,
        "drop_weight": 2,
    },
    {
        "code": "dragon_fire",
        "label": "Rồng lửa",
        "tile": 33,
        "tier": "legendary",
        "position": 37,
        "drop_weight": 2,
    },
    {
        "code": "dragon_ice",
        "label": "Rồng băng",
        "tile": 31,
        "tier": "legendary",
        "position": 38,
        "drop_weight": 2,
    },
    {
        "code": "fairy",
        "label": "Tiên",
        "tile": 12,
        "tier": "legendary",
        "position": 39,
        "drop_weight": 2,
    },
    {
        "code": "djinn",
        "label": "Thần đèn",
        "tile": 109,
        "tier": "legendary",
        "position": 40,
        "drop_weight": 2,
    },
    # --- bậc THẦN --------------------------------------------------------
    #
    # Năm ô này đều nằm sẵn trong `creatures.png` và chưa loài nào dùng: bốn
    # nguyên tố ở hàng 4 (45–48) và một ô thiên thần có vầng hào quang ở hàng 3
    # (37). Không phải tải thêm tài nguyên nào — ADR-010 §14.4 chọn gói này chính
    # vì nó có sẵn hơn một trăm sinh vật huyền thoại.
    #
    # Ô 37 vốn nằm trong hồ NPC. Lấy nó ra làm thú nuôi thì hồ ấy còn 5 ô, và đó
    # là cái giá chấp nhận được: hai thiên thần còn lại (35, 36) ở lại làm khách.
    {
        "code": "spirit_fire",
        "label": "Thần Lửa",
        "tile": 45,
        "tier": "god",
        "position": 41,
        "drop_weight": 1,
    },
    {
        "code": "spirit_water",
        "label": "Thần Nước",
        "tile": 46,
        "tier": "god",
        "position": 42,
        "drop_weight": 1,
    },
    {
        "code": "spirit_stone",
        "label": "Thần Đá",
        "tile": 47,
        "tier": "god",
        "position": 43,
        "drop_weight": 1,
    },
    {
        "code": "spirit_storm",
        "label": "Thần Bão",
        "tile": 48,
        "tier": "god",
        "position": 44,
        "drop_weight": 1,
    },
    {
        "code": "seraph",
        "label": "Thiên Thần",
        "tile": 37,
        "tier": "god",
        "position": 45,
        "drop_weight": 1,
    },
)


# --- gacha (ADR-010 lát 8) --------------------------------------------------
#
# Hạng được coi là HIẾM khi tính bộ đếm an ủi. Ngẫu nhiên thuần cho ra những
# chuỗi xui mà người chơi đọc là "hỏng", nên sau N quả không ra hạng hiếm thì quả
# sau chắc chắn ra một con trong hai hạng này.
RARE_TIERS = ("rare", "epic", "legendary", "god")

# Trọng số rơi mặc định theo hạng, dùng khi gieo `pet_species` và khi một hàng cũ
# chưa có trọng số. Là con số KHỞI ĐIỂM: cột `drop_weight` mới là thứ quyết định,
# và admin sửa nó không cần deploy.
DEFAULT_DROP_WEIGHT = {
    "common": 40,
    "uncommon": 25,
    "rare": 10,
    "epic": 4,
    "legendary": 2,
    # Một nửa huyền thoại. Bậc thần là năm loài trên bốn mươi lăm, và tổng trọng
    # số của nó chỉ chiếm khoảng 0,7% — đủ hiếm để mở ra được một con là một sự
    # kiện, và cũng đủ để không ai phải cày mới thấy bậc này tồn tại.
    "god": 1,
}


class PetOwned(Base):
    """MỘT con thú của một người: nó là con nào, và chỉ số của riêng nó.

    Khoá chính là `(user_id, species)`, nên "đã có con này chưa" là câu hỏi
    database trả lời được chứ không phải một phép đếm — và mở trứng trùng không
    thể tạo ra hàng thứ hai dù có bao nhiêu request cùng lúc.

    **Mỗi con có chỉ số riêng.** Đói, sức, vui, XP, level và chỗ đứng đều nằm ở
    đây chứ không ở `pet_state`: một con vật là một sinh vật riêng, và một bộ chỉ
    số dùng chung cho cả góc nghĩa là đổi con thì con mới thừa hưởng độ no của
    con cũ trong khi con cũ mất sạch quá trình được chăm. Đổi qua đổi lại giờ
    không mất gì — con nào giữ chỉ số của con nấy, kể cả chỗ nó đang đứng.

    Nhu cầu vẫn **suy ra lúc đọc** từ `needs_at`, không phải một bộ đếm chạy nền:
    một con thú không được ngó tới vẫn đói theo đồng hồ thật, kể cả khi chủ nó
    đang chơi với con khác.

    `species` KHÔNG phải khoá ngoại sang `pet_species`, cùng lý do đã ghi ở
    migration `037`: khoá ngoại biến "tắt một loài" thành một thao tác database,
    và xoá hẳn một loài sẽ chặn lại vì có người đang sở hữu.
    """

    __tablename__ = "pet_owned"
    __table_args__ = (
        # Ràng buộc phải nằm ở CẢ HAI chỗ, và đây là chỗ dễ quên: migration dựng
        # schema cho Postgres, `Base.metadata` dựng schema cho test (SQLite).
        # Chỉ viết ở migration thì bài kiểm "giá trị sai bị từ chối" xanh ở một
        # bên và đỏ ở bên kia, và `--autogenerate` không so CHECK đáng tin.
        CheckConstraint(
            "fullness BETWEEN 0 AND 1 AND energy BETWEEN 0 AND 1 AND mood BETWEEN 0 AND 1",
            name="ck_pet_owned_needs_range",
        ),
        CheckConstraint("facing IN ('left', 'right')", name="ck_pet_owned_facing"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    species: Mapped[str] = mapped_column(String(32), primary_key=True)

    copies: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    """Đã nở ra con này bao nhiêu lần.

    **Không hiện ra giao diện**, và đó là chủ ý: mở trúng con đã có thì được hoàn
    ruby, nên bản thứ hai không phải một thứ người chơi đang giữ — in "×2" bên
    cạnh tên là nói rằng có hai con trong khi chỉ có một, và ngụ ý con số ấy dùng
    được vào việc gì đó. Giữ cột lại vì nó là LỊCH SỬ ("đã nở mấy lần"), thứ mà
    sổ ruby không kể được sau khi mức hoàn thay đổi.
    """

    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)

    xp: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    """XP của CON NÀY, không phải của người học và không phải của cả góc.

    Không có cột `level`: level suy ra từ `xp` qua bảng ngưỡng, y như level người
    học suy ra từ `SUM(xp_event.amount)`. Lưu cả hai là hai nguồn sự thật cho một
    con số, và cái sai sẽ là cái không ai đọc.
    """

    level_reached: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    """Mốc cao nhất con này từng đạt, CHỈ TĂNG.

    Giống `user_profile.level_reached` và vì cùng một lý do: chỉnh lại đường cong
    XP về sau không được lấy mất level của con thú đã đạt tới nó.
    """

    xp_today: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    xp_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    """XP con này đã nhận trong NGÀY nào, theo múi giờ người học.

    Cặp này thay cho một sổ cái: trần ngày cần biết "hôm nay đã nhận bao nhiêu",
    và với một bộ đếm thì câu đó chỉ trả lời được nếu biết bộ đếm thuộc về ngày
    nào. Ngày đổi thì bộ đếm về 0 — kiểm lúc GHI, không phải lúc đọc, cùng luật
    với trần XP người học: kẹp lúc đọc sẽ biến nó thành một công thức, và đổi
    trần sau này sẽ viết lại quá khứ.

    **Của TỪNG CON, không phải của người** (migration `042`). Để ở người thì con
    vừa nở ra không nhận nổi một điểm nào cho tới hôm sau — mà người ta mở trứng
    sau khi đã chơi với con cũ, nên đó là trường hợp thường gặp chứ không phải
    ngoại lệ. Thứ trần này bảo vệ là "một con không lên max level trong một
    buổi", và trần theo từng con giữ nguyên đúng điều đó.

    NULL = con này chưa nhận XP ngày nào.
    """

    tile_x: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    tile_y: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="5")
    """Ô mặc định phải ĐỨNG ĐƯỢC trên `public/pet/map.json`.

    `(3, 8)` của bản đầu nằm trong tường — hàng 8 là `#####....#.#...#.#`. Không
    ai nhìn thấy chuyện đó, vì lượt nạp đầu gọi `nearestWalkable` kéo con thú ra
    rồi ghi lại vị trí; cái giá là một lần dịch chuyển và một `PUT` mà mọi tài
    khoản mới đều phải trả để sửa một con số lẽ ra đã đúng.

    `nearestWalkable` vẫn phải ở đó: bản đồ là tệp tĩnh mà máy chủ không đọc, nên
    không có cách nào bảo đảm một ô đứng được mãi mãi.
    """
    """Chỗ CON NÀY đang đứng, theo Ô chứ không theo pixel.

    Bản đồ đổi kích thước hay đổi hệ số phóng thì hai số này vẫn đúng. Lưu pixel
    là ghim vị trí vào một cỡ màn hình cụ thể, và không có gì báo khi cỡ đó đổi.

    Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại; phía client giải
    quyết bằng `nearestWalkable`, chứ không phải bằng một migration cho mỗi lần
    đổi bản đồ.
    """

    facing: Mapped[str] = mapped_column(String(5), nullable=False, server_default="right")

    fullness: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default="0.62")
    energy: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default="0.78")
    mood: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default="0.70")
    """Ba nhu cầu, 0..1. `Numeric` chứ không `Float`, theo đúng `ease_factor` của SM-2."""

    sleep_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Con này đang ngủ tới lúc nào, hoặc NULL nếu đang thức.

    Một MỐC HẾT HẠN chứ không phải một cờ `đang_ngủ`, và khác biệt ấy là toàn bộ
    lý do giấc ngủ không thành việc phải làm: giấc ngủ tự dứt khi tới mốc, không
    cần ai bấm gì, không cần một job chạy nền đi đánh thức, và một người đóng tab
    giữa chừng vẫn thấy con thú đã dậy khi quay lại. Một cái cờ thì phải có ai đó
    tắt nó, và "ai đó" cuối cùng luôn là người dùng.

    Cùng khuôn `needs_at`: trạng thái suy ra lúc đọc từ một mốc thời gian, không
    phải một bộ đếm chạy song song với đồng hồ.
    """

    needs_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    """MỐC THỜI GIAN của ba số trên, và đây là cột quan trọng nhất bảng này.

    Nhu cầu **suy ra lúc đọc**: `fullness_bây_giờ = decay(fullness, now -
    needs_at)`. Bản cũ trừ dần theo `dt` của vòng `requestAnimationFrame`, nên
    đồng hồ chỉ chạy khi bảng đang mở — mở cả buổi thì con thú đói, đóng tab một
    tuần thì nó vẫn no nguyên. Ngược hoàn toàn với trực giác của người nuôi.

    Vì mỗi con có mốc riêng, một con bị bỏ quên ba ngày sẽ đói đúng ba ngày khi
    được ngó lại — chứ không thừa hưởng cái mốc vừa mới của con đang được chăm.
    """

    def __repr__(self) -> str:
        return f"<PetOwned {self.species} lv{self.level_reached}>"


class EggSetting(Base):
    """Ba con số của gacha, một hàng duy nhất (`id = 1`).

    Cùng khuôn `progression_setting` và `backdrop_setting`: gieo LƯỜI ở lần đọc
    đầu, không gieo trong migration, và bảng rỗng nghĩa là "chưa từng cấu hình".

    Một HẠNG trứng duy nhất là quyết định của lát này, không phải một giới hạn
    của schema — nếu về sau cần trứng hiếm mở theo level thì bảng này lên thành
    `egg_tier` với nhiều hàng. Dựng sẵn ba hạng cho một sản phẩm mới có 12 loài
    là chia một cái bể nhỏ thành ba ngăn rỗng.
    """

    __tablename__ = "egg_setting"
    __table_args__ = (
        CheckConstraint("ruby_cost > 0", name="ck_egg_setting_cost"),
        CheckConstraint("pity_rolls > 0", name="ck_egg_setting_pity"),
        # Hoàn nhiều hơn giá trứng là một cỗ máy in ruby: mở trứng trùng liên tục
        # sẽ sinh ra ruby từ hư không. Ràng buộc này không thể diễn đạt trong một
        # CHECK trên một cột, nên nó so hai cột với nhau — chỗ duy nhất chặn được.
        CheckConstraint("duplicate_refund >= 0", name="ck_egg_setting_refund"),
        CheckConstraint("duplicate_refund < ruby_cost", name="ck_egg_setting_refund_below_cost"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ruby_cost: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="25")
    pity_rolls: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="10")
    duplicate_refund: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="10")

    def __repr__(self) -> str:
        return f"<EggSetting {self.ruby_cost} ruby, pity {self.pity_rolls}>"


EGG_DEFAULTS: dict[str, int] = {
    # 25 ruby ≈ một tới hai ngày của một người học chăm (ADR-011 §10.2). Đắt hơn
    # thì phần thưởng ở quá xa để đẩy ai đi học; rẻ hơn thì mở hết 12 loài trong
    # một tuần và không còn gì để mong.
    "ruby_cost": 25,
    "pity_rolls": 10,
    # Hoàn 10 trên 25: trứng trùng vẫn là một mất mát, nhưng nó không xoá sạch
    # hai ngày học. Bằng giá trứng thì trùng hoá ra miễn phí và cả bộ đếm hiếm
    # mất ý nghĩa.
    "duplicate_refund": 10,
}


class PetlandMap(Base):
    """Bản đồ góc thú cưng, sửa được ở `/admin/petland` (migration 048).

    Đúng một hàng, `id = 1`. Không có hàng nghĩa là chưa ai sửa trên web và
    `public/pet/map.json` đã commit đang là bản chạy — xem docstring migration.
    """

    __tablename__ = "petland_map"
    __table_args__ = (CheckConstraint("id = 1", name="ck_petland_map_single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    w: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    h: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ground: Mapped[list[object]] = mapped_column(_JSON_TYPE, nullable=False)
    objects: Mapped[list[object]] = mapped_column(_JSON_TYPE, nullable=False)
    solid: Mapped[list[object]] = mapped_column(_JSON_TYPE, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
