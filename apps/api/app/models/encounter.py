"""Chạm mặt ở Petland: NPC giao việc và những đợt xâm nhập (ADR-012).

**Không có ô sprite, không có toạ độ.** Bảng này chỉ giữ *nhiệm vụ là gì* và
*còn hiệu lực tới bao giờ*; còn con vật trông thế nào và nó đứng ở đâu trên bản
đồ thì trình duyệt tự quyết từ `encounter.id`.

Đó không phải chuyện lười. Bản đồ sống ở `public/pet/map.json` — một tệp tĩnh mà
máy chủ không đọc và **không nên đọc**, đúng lý do đã ghi cho `PUT /pet/position`:
bắt nó biết bố cục nghĩa là mỗi lần vẽ lại bản đồ trong trình sửa lại phải deploy
API. Và bảng phân vai sinh vật (`petland-bestiary.ts`) nằm ở frontend; chép một
danh sách ô sang Python là dựng bản sao thứ hai của thứ đã có một bản.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ENCOUNTER_KINDS = ("npc", "intruder", "rescue")
"""Hai loại chạm mặt, và chúng dùng CHUNG bộ máy.

Kẻ xâm nhập chỉ khác NPC ở ba con số — nhiều bước hơn, thưởng lớn hơn, hiếm hơn
— chứ không phải một cơ chế thứ hai. Và **không loại nào phạt người dùng khi bị
bỏ qua** (ADR-012 §4): hết hạn thì biến mất, thế thôi.
"""

TASK_KINDS = ("vocabulary", "dictation", "quiz")
"""Ba dạng bài, mỗi dạng mượn đúng một bộ chấm đã có (ADR-012 §2).

`quiz` khai sẵn nhưng **chưa mở**: kho chỉ có 55 câu trắc nghiệm, nên người học
chăm sẽ gặp lại câu cũ trong vài ngày và nhiệm vụ sẽ dạy thuộc lòng đáp án chứ
không dạy tiếng Anh (ADR-012 §8.3). Có mặt ở đây để không phải sửa CHECK khi kho
đủ lớn.
"""

ENCOUNTER_STATES = ("waiting", "done", "expired")

MAX_HINTS = 2
"""Số lần xin gợi ý tối đa cho mỗi bước.

Hai chứ không phải vô hạn: gợi ý thứ nhất mở một phần tư số chữ, thứ hai mở một
nửa, nên lần thứ ba sẽ gần như in ra cả từ. Hai lần là đủ để gỡ một chỗ bí mà
vẫn còn phần phải nhớ — mà "còn phần phải nhớ" chính là thứ phân biệt một bài
kiểm với một ô điền sẵn.
"""


class Encounter(Base):
    """Một lần chạm mặt: ai đó xuất hiện, giao một việc, và có hạn."""

    __tablename__ = "encounter"
    __table_args__ = (
        CheckConstraint("kind IN ('npc', 'intruder', 'rescue')", name="ck_encounter_kind"),
        CheckConstraint(
            "task_kind IN ('vocabulary', 'dictation', 'quiz')", name="ck_encounter_task"
        ),
        CheckConstraint("state IN ('waiting', 'done', 'expired')", name="ck_encounter_state"),
        CheckConstraint("steps_total > 0", name="ck_encounter_steps_total"),
        CheckConstraint("steps_done >= 0 AND steps_done <= steps_total", name="ck_encounter_steps"),
        CheckConstraint("hints_used >= 0", name="ck_encounter_hints"),
        # Đường đọc luôn hỏi "người này còn cuộc nào đang chờ không".
        Index("ix_encounter_user_state", "user_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    task_kind: Mapped[str] = mapped_column(String(16), nullable=False)

    target_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    """Từ vựng / câu chép chính tả / câu hỏi mà nhiệm vụ này trỏ tới.

    **Không phải khoá ngoại.** Nó trỏ vào ba bảng khác nhau, và một khoá ngoại sẽ
    chặn việc xoá nội dung chỉ vì có một cuộc chạm mặt cũ trỏ vào — đúng cái bẫy
    mà `dictation_attempt` RESTRICT đã dựng ra ở chỗ khác. Nội dung biến mất thì
    cuộc chạm mặt hết hạn, thế thôi.
    """

    steps_total: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    steps_done: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    reward_ruby: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="5")
    """Số ruby, **chốt lúc sinh ra** chứ không tra lại lúc trả thưởng.

    Cùng luật khiến sổ cái XP và sổ ruby an toàn để admin sửa: hạ mức thưởng giữa
    lúc một NPC đang đứng chờ không được đổi lời hứa đã hiện trên màn hình.
    """

    hints_used: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    """Số lần đã xin gợi ý cho BƯỚC hiện tại, đếm ở máy chủ.

    Ở đây chứ không ở trình duyệt, vì trần gợi ý là thứ giữ cho nhiệm vụ gõ lại
    từ còn là một bài kiểm: xin đủ nhiều lần thì gợi ý in ra cả từ, và lúc đó
    phần thưởng ruby chỉ còn là một cái nút bấm nhiều lần. Một bộ đếm trong
    `useState` thì devtools đặt lại được trong hai giây.

    Đặt lại về 0 mỗi khi `target_id` đổi — mỗi bước của một đợt xâm nhập là một
    từ khác, nên nó xứng đáng có phần gợi ý của riêng nó.
    """

    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="waiting")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """Hết hạn **suy ra lúc đọc**, không có job nền nào đi dọn.

    `state` chỉ đổi khi có người nhìn tới. Cùng khuôn `pet_owned.sleep_until`, và
    vì cùng một lý do: một trạng thái cần người khác dọn hộ là một trạng thái sẽ
    có lúc không được dọn.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Encounter {self.kind}/{self.task_kind} {self.state}>"


class EncounterSetting(Base):
    """Mọi con số của cơ chế chạm mặt, một hàng duy nhất (`id = 1`).

    Cùng khuôn `egg_setting` và `progression_setting`: gieo LƯỜI ở lần đọc đầu,
    không gieo trong migration, và bảng rỗng nghĩa là "chưa từng cấu hình".

    **Nhịp sinh phải là hàng**, và đó là điều kiện để lập luận ở ADR-012 §6 đứng
    được: phần thưởng của một cuộc chạm mặt không bị cày được vì thứ giới hạn nó
    là nhịp xuất hiện — mà một trần nằm rải rác trong mã thì không ai chỉnh được
    khi thấy nó sai.
    """

    __tablename__ = "encounter_setting"
    __table_args__ = (
        CheckConstraint("npc_gap_seconds > 0", name="ck_encounter_npc_gap"),
        CheckConstraint("npc_life_seconds > 0", name="ck_encounter_npc_life"),
        CheckConstraint("intruder_gap_seconds > 0", name="ck_encounter_intruder_gap"),
        CheckConstraint("intruder_life_seconds > 0", name="ck_encounter_intruder_life"),
        CheckConstraint("intruder_steps > 0", name="ck_encounter_intruder_steps"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    npc_gap_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1200")
    npc_life_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="600")
    npc_reward: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="5")
    intruder_gap_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3600"
    )
    intruder_life_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="600"
    )
    intruder_reward: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="20")
    intruder_steps: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")

    def __repr__(self) -> str:
        return f"<EncounterSetting npc {self.npc_gap_seconds}s>"


ENCOUNTER_DEFAULTS: dict[str, int] = {
    # 20 phút một lần, sống 10 phút: một buổi học 30–40 phút gặp một tới hai NPC
    # — đủ hiếm để mỗi lần gặp là một sự kiện, đủ dài để không phải bỏ dở việc
    # đang làm. Nhắc lại ADR-012 §1: khoảng cách này đếm **thời gian người dùng
    # có mặt**, không phải thời gian trên đồng hồ.
    "npc_gap_seconds": 20 * 60,
    "npc_life_seconds": 10 * 60,
    # 5 ruby: ngang một bài dictation cho một việc nhỏ hơn nhiều, bù lại bằng
    # chuyện nó hiếm. Khoảng 15 ruby một buổi, không lấn át các nguồn "làm xong".
    "npc_reward": 5,
    "intruder_gap_seconds": 60 * 60,
    "intruder_life_seconds": 10 * 60,
    "intruder_reward": 20,
    "intruder_steps": 3,
}
