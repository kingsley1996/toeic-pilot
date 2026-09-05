"""Trao XP và suy ra level.

Đây là đường ghi DUY NHẤT vào `xp_event`. Không có endpoint "cộng XP cho tôi":
một endpoint như thế là endpoint người ta gọi thẳng. XP sinh ra bên trong chính
những đường ghi đã tồn tại — ôn một từ, hoàn thành một câu dictation, nộp một
lượt làm đề.

Hai tính chất phải giữ, cả hai đều hỏng im lặng nếu làm khác:

1. **Hoạt động không bao giờ phụ thuộc vào việc trao XP.** Chạm trần, nguồn lạ,
   hay va phải ràng buộc chống trùng đều KHÔNG được làm hỏng lượt ôn SM-2, tiến
   độ dictation hay lượt làm đề. Học vẫn là học; luật gamification không được
   với tới đó.
2. **Trần cưỡng chế lúc GHI, không lúc đọc.** Sổ cái phải nói đúng số điểm đã
   trao. Cưỡng chế lúc đọc thì trần trở thành một công thức, và đổi trần sẽ đổi
   cả quá khứ — mất đúng cái lợi khiến ta chọn sổ cái thay vì tính lại từ đầu.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import UserProfile
from app.models.progression import XP_SOURCES, XpEvent
from app.services import progression_config
from app.services.leveling import Progress, frame_for_level, level_from_xp

# Mức XP và trần mỗi ngày KHÔNG còn là hằng số ở đây — chúng là hàng trong
# `progression_setting`, admin sửa được, và `progression_config` là chỗ đọc ra.
#
# Sổ cái làm cho việc đó an toàn, và đó chính là điều §2.1 của USER-ROAD mua về:
# mỗi hàng ghi số điểm ĐÃ TRAO lúc đó, nên hạ giá một hoạt động hôm nay không
# rút XP của ai trong quá khứ.

# Namespace để sinh uuid tất định cho nguồn không lấy id hàng gốc làm khoá chống
# trùng. Cố định vĩnh viễn: đổi nó là mọi daily task trong quá khứ trở thành
# "chưa trao" và được trao lại.
_TASK_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def local_today(when: datetime, timezone: str) -> date:
    """Ngày theo múi giờ người học.

    Cùng định nghĩa "ngày" mà `profile_stats.compute_streaks` dùng. Một định
    nghĩa thứ hai là chỗ chuỗi ngày và daily task nói hai điều khác nhau về cùng
    một hôm, và không có gì báo.
    """
    try:
        zone = ZoneInfo(timezone)
    except Exception:
        # Múi giờ lạ không được làm hỏng một lượt ôn. `user_profile.timezone` có
        # kiểm ở tầng schema; đây là lưới an toàn cuối.
        zone = ZoneInfo("UTC")
    return when.astimezone(zone).date()


def task_source_id(user_id: uuid.UUID, day: date, slot: str) -> uuid.UUID:
    """uuid TẤT ĐỊNH cho một daily task.

    Postgres coi mọi NULL là khác nhau, nên `uq_xp_event_source` không chặn được
    hàng có `source_id` NULL — hai lần trao cho cùng một task sẽ lọt cả hai. Sinh
    uuid từ (người, ngày, khe) làm ràng buộc đó có hiệu lực trở lại, và không cần
    thêm bảng nào để nhớ đã trao chưa.
    """
    return uuid.uuid5(_TASK_NAMESPACE, f"{user_id}:{day.isoformat()}:{slot}")


def grammar_source_id(user_id: uuid.UUID, question_id: uuid.UUID) -> uuid.UUID:
    """uuid tất định cho XP một câu ngữ pháp, khoá (người, câu) chứ KHÔNG phải id
    lượt làm.

    Đường nộp bài ghi MỌI lượt — làm lại câu đã đúng là thao tác bình thường ở
    đây. Lấy id lượt làm `source_id` thì mỗi lần bấm lại là một XP mới, và khác
    dictation (thứ cũng dùng id lượt), ngữ pháp không có bước "nghe lại từ đầu"
    nào tự nhiên giới hạn tần suất bấm.
    """
    return uuid.uuid5(_TASK_NAMESPACE, f"grammar-attempt:{user_id}:{question_id}")


def daily_cap(db: Session) -> int:
    return progression_config.settings_row(db).daily_xp_cap


# Nguồn XP → cột giữ mức điểm của nó. `daily_task` vắng mặt có chủ ý: mức thưởng
# của một khe nằm trên chính hàng khe đó, vì hai khe khác nhau có thể đáng những
# số điểm khác nhau.
_XP_COLUMN = {
    "vocabulary_review": "xp_vocabulary_review",
    "dictation_complete": "xp_dictation_complete",
    "attempt_submit": "xp_attempt_submit",
    "grammar_attempt": "xp_grammar_attempt",
}


def xp_for(db: Session, source_type: str) -> int:
    """Mức XP hiện hành của một nguồn.

    Đọc lúc TRAO, không phải lúc đọc sổ cái: hàng `xp_event` giữ số điểm đã trao,
    nên hạ mức hôm nay không rút lại XP đã cho ai. Đó là toàn bộ lý do §2.1 chọn
    sổ cái thay vì tính lại, và nó chính là thứ khiến mức điểm an toàn để sửa.
    """
    column = _XP_COLUMN.get(source_type)
    if column is None:
        raise ValueError(f"nguồn XP không có mức cấu hình: {source_type}")
    return int(getattr(progression_config.settings_row(db), column))


def xp_awarded_on(db: Session, user_id: uuid.UUID, day: date) -> int:
    """XP đã trao cho người này trong ngày đó."""
    total = db.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(
            XpEvent.user_id == user_id, XpEvent.awarded_on == day
        )
    )
    return int(total or 0)


def award(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID | None,
    amount: int,
    timezone: str,
    now: datetime | None = None,
) -> int:
    """Trao XP nếu còn trần. Trả về số điểm THỰC SỰ trao (có thể là 0).

    Không `commit`: người gọi đang ở giữa một giao dịch của chính nó (ghi lượt
    ôn, nộp bài) và XP phải sống chết cùng giao dịch đó. Trao XP cho một lượt ôn
    bị rollback là sổ cái nói về một việc chưa từng xảy ra.
    """
    if source_type not in XP_SOURCES:
        raise ValueError(f"nguồn XP không hợp lệ: {source_type}")
    if amount <= 0:
        return 0

    when = now or datetime.now(tz=ZoneInfo("UTC"))
    day = local_today(when, timezone)

    # Trần: cắt phần vượt thay vì bỏ cả lần trao. Trao 3 trong 5 điểm còn lại
    # đúng hơn là trao 0 — người dùng thấy thanh nhích chậm dần rồi dừng, chứ
    # không thấy nó đứng khựng giữa chừng.
    used = xp_awarded_on(db, user_id, day)
    room = daily_cap(db) - used
    if room <= 0:
        return 0
    granted = min(amount, room)

    # Chèn rồi bắt vi phạm ràng buộc, KHÔNG phải "kiểm tra rồi chèn". Kiểm trước
    # để lại một khe giữa lần đọc và lần ghi, và hai request song song của cùng
    # một lần bấm đúp lọt qua khe đó cùng lúc — chính kịch bản mà ràng buộc tồn
    # tại để chặn. Ràng buộc mới là thứ quyết định, `try` chỉ dịch nó thành "đã
    # trao rồi".
    #
    # Dùng SAVEPOINT chứ không `ON CONFLICT` của Postgres: `ON CONFLICT` không
    # chạy trên SQLite, mà bộ test mặc định là SQLite — một đường ghi nóng như
    # thế này mà chỉ kiểm được trên Postgres thì phần lớn bộ test không phủ nổi.
    # SAVEPOINT có ở cả hai, và khi bị huỷ nó chỉ cuộn lại đúng lần chèn này,
    # không đụng tới lượt ôn đang nằm cùng giao dịch.
    try:
        with db.begin_nested():
            db.add(
                XpEvent(
                    user_id=user_id,
                    source_type=source_type,
                    source_id=source_id,
                    amount=granted,
                    awarded_on=day,
                )
            )
    except IntegrityError:
        # Trùng thì im lặng bỏ qua, KHÔNG phải lỗi: một lần bấm đúp hay một
        # request lặp là chuyện bình thường và không được làm hỏng hoạt động đi
        # kèm.
        return 0
    return granted


def total_xp(db: Session, user_id: uuid.UUID) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(XpEvent.user_id == user_id)
    )
    return int(total or 0)


def level_of(db: Session, user_id: uuid.UUID) -> Progress:
    """Tiến độ level theo bảng ngưỡng ĐANG hiệu lực, chưa áp mốc nước cao."""
    return level_from_xp(total_xp(db, user_id), progression_config.level_thresholds(db))


def bump_level_reached(db: Session, user_id: uuid.UUID, level: int) -> int:
    """Nâng mốc nước cao nếu level vừa tính cao hơn. Trả về level SẼ hiển thị.

    Level không bao giờ tụt. Bảng ngưỡng là thứ admin sửa được, nên không có cột
    này thì một lần nâng chuẩn sẽ lấy lại level của những người đã đạt — họ mất
    một thứ vì một quyết định vận hành mà họ không tham gia. Cùng tinh thần với
    việc XP là sổ cái thay vì một phép tính lại.

    Không `commit`: phía gọi đang ở giữa giao dịch của nó (ghi lượt ôn, nộp bài),
    và mốc nước cao phải sống chết cùng giao dịch đó.
    """
    profile = db.get(UserProfile, user_id)
    if profile is None:
        return level
    if level > profile.level_reached:
        profile.level_reached = level
        return level
    return profile.level_reached


def progression_of(
    db: Session,
    user_id: uuid.UUID,
    timezone: str,
    now: datetime | None = None,
    *,
    top_frame: bool = False,
) -> tuple[Progress, str | None, int]:
    """(tiến độ level, mã khung avatar, XP hôm nay).

    Level trả về đã áp mốc nước cao, nên nó có thể CAO HƠN mức mà tổng XP hiện
    tại đạt được theo bảng ngưỡng hôm nay. Đó là chủ ý — xem `bump_level_reached`.

    `top_frame` mở sẵn bậc khung CAO NHẤT cho tài khoản quản trị. Nó chạm đúng
    một thứ — khung, vốn thuần trang trí — và **không** đụng tới level, XP hay
    huy hiệu: một admin ở level 1 vẫn hiện level 1, chỉ là đeo khung đẹp nhất.
    Cho cả level thì con số trên hồ sơ họ trở thành một lời nói dối, và nó lây
    sang huy hiệu `level_*` vốn đo bằng chính con số đó.

    Chọn bậc theo `min_level` cao nhất chứ không cứng mã "challenger": bảng bậc
    là dữ liệu admin sửa được, nên một mã cứng sẽ thành `None` im lặng vào ngày
    ai đó đổi tên hoặc xoá bậc đó.
    """
    when = now or datetime.now(tz=ZoneInfo("UTC"))
    progress = level_of(db, user_id)
    shown = bump_level_reached(db, user_id, progress.level)
    if shown != progress.level:
        # Đã từng ở level cao hơn: giữ level, và thanh tiến độ trong level không
        # còn nghĩa gì để so nên đặt về 0 thay vì in một tỉ lệ của bậc khác.
        progress = Progress(level=shown, xp_total=progress.xp_total, xp_into_level=0, xp_for_next=0)
    tiers = [(tier.min_level, tier.code) for tier in progression_config.frame_tiers(db)]
    today = xp_awarded_on(db, user_id, local_today(when, timezone))
    if top_frame and tiers:
        return progress, max(tiers)[1], today
    return progress, frame_for_level(progress.level, tiers), today
