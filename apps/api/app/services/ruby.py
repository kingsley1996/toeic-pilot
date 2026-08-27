"""Kiếm và tiêu ruby. Đây là đường ghi DUY NHẤT vào `ruby_event`.

Cùng luật với `progression.award`, vì cùng một lý do: không có endpoint "cộng
ruby cho tôi" — một endpoint như thế là endpoint người ta gọi thẳng. Ruby sinh
ra bên trong những đường ghi đã tồn tại (xong một bài dictation, thuộc trọn một
chủ đề, nộp một lượt làm đề), và **việc học không bao giờ phụ thuộc vào việc
trao ruby**: va phải ràng buộc chống trùng hay một nguồn bị tắt đều không được
làm hỏng lượt ôn hay lượt nộp bài đi kèm.

Khác XP đúng một chỗ về hình dạng và đó là chỗ khó: ruby có đường TIÊU, nên số
dư — một phép `SUM` — trở thành thứ hai luồng đọc cùng lúc rồi cùng trừ. Xem
`spend`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ruby import DEFAULT_RUBY_RULES, RUBY_SOURCES, SPEND_SOURCES, RubyEvent, RubyRule
from app.services.progression import local_today

# "Ngày" là ngày theo múi giờ người học, và định nghĩa ấy được MƯỢN chứ không
# viết lại: `progression.local_today` đã ghi rõ rằng một định nghĩa thứ hai là chỗ
# chuỗi ngày và daily task nói hai điều khác nhau về cùng một hôm mà không có gì
# báo. Ruby là sổ thứ ba đọc cùng con số ấy.
__all__ = [
    "NotEnoughRuby",
    "amount_for",
    "balance",
    "daily_source_id",
    "earn",
    "history",
    "local_today",
    "rules",
    "spend",
    "top_up_admin",
]

# Namespace sinh uuid tất định cho các nguồn lặp theo ngày. Cố định VĨNH VIỄN:
# đổi nó là mọi khoản đã trao trong quá khứ trở thành "chưa trao" và được trao
# lại. Khác namespace của daily task XP có chủ ý — cùng một (người, ngày, khe)
# phải cho hai uuid khác nhau ở hai sổ, nếu không thì không phân biệt được.
_RUBY_NAMESPACE = uuid.UUID("2f1c9d5e-6a83-4f7b-9c21-0d4a7e5b8c30")


def daily_source_id(user_id: uuid.UUID, day: date, source_type: str) -> uuid.UUID:
    """uuid TẤT ĐỊNH cho một khoản lặp theo ngày.

    Postgres coi mọi NULL là khác nhau, nên `uq_ruby_event_source` không chặn nổi
    hàng có `source_id` NULL — hai lần trao cho cùng một ngày sẽ lọt cả hai. Sinh
    uuid từ (người, ngày địa phương, nguồn) làm ràng buộc đó có hiệu lực trở lại,
    và không cần thêm bảng nào để nhớ đã trao chưa. Đúng cách
    `progression.task_source_id` đã làm.
    """
    return uuid.uuid5(_RUBY_NAMESPACE, f"{user_id}:{day.isoformat()}:{source_type}")


def rules(db: Session, *, include_disabled: bool = False) -> list[RubyRule]:
    """Bảng mức thưởng, gieo mặc định ở lần đọc đầu.

    **Bảng rỗng nghĩa là "chưa từng cấu hình", không phải "cố ý để trống"** —
    cùng tính chất với `pet_species` và `frame_tier`, và cùng hệ quả: xoá hết
    thì lần đọc sau gieo lại đủ bảy. Muốn bỏ một nguồn thì TẮT nó.
    """
    rows = _ordered(db)
    if not rows:
        # Gieo trong SAVEPOINT và nuốt va chạm: hai request đầu tiên sau một lần
        # triển khai đọc bảng rỗng cùng lúc và cùng gieo, và người thua sẽ vỡ
        # khoá chính. Đây không phải chuyện lý thuyết — `tests/test_ruby_race.py`
        # đỏ đúng vì nó, vì tám luồng cùng hỏi mức thưởng trước khi bảng có gì.
        # Người thua chỉ cần đọc lại: hàng đã ở đó rồi, và một lượt học không
        # được hỏng vì một cuộc đua trên bảng cấu hình.
        try:
            with db.begin_nested():
                for spec in DEFAULT_RUBY_RULES:
                    db.add(RubyRule(**spec))
        except IntegrityError:
            pass
        else:
            db.commit()
        rows = _ordered(db)
    return rows if include_disabled else [row for row in rows if row.enabled]


def _ordered(db: Session) -> list[RubyRule]:
    return list(db.scalars(select(RubyRule).order_by(RubyRule.position, RubyRule.source_type)))


def amount_for(db: Session, source_type: str) -> int:
    """Mức thưởng hiện hành của một nguồn; 0 nếu nguồn đang tắt.

    Đọc lúc TRAO, không lúc đọc sổ cái: mỗi hàng giữ số ruby đã trao lúc đó, nên
    hạ mức hôm nay không rút lại của ai. Cùng tính chất khiến mức XP an toàn để
    admin sửa.
    """
    for row in rules(db):
        if row.source_type == source_type:
            return int(row.amount)
    return 0


def balance(db: Session, user_id: uuid.UUID) -> int:
    """Số dư = `SUM(amount)`. Không có cột số dư, cố ý.

    Một cột chạy song song là nguồn sự thật thứ hai, và cái sai sẽ là cái không
    ai đọc. Cùng lập luận với `StoryProgress` và `VocabularyProgress`.
    """
    total = db.scalar(
        select(func.coalesce(func.sum(RubyEvent.amount), 0)).where(RubyEvent.user_id == user_id)
    )
    return int(total or 0)


def earn(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID | None,
    amount: int | None = None,
    now: datetime | None = None,
) -> int:
    """Trao ruby một lần cho một nguồn. Trả về số ruby THỰC SỰ trao (có thể 0).

    `amount=None` nghĩa là "lấy mức đang cấu hình", đường dùng bình thường.

    Không `commit`: người gọi đang ở giữa giao dịch của chính nó (ghi tiến độ,
    nộp bài) và khoản ruby phải sống chết cùng giao dịch đó. Trao ruby cho một
    việc bị rollback là sổ cái nói về một việc chưa từng xảy ra.
    """
    if source_type not in RUBY_SOURCES:
        raise ValueError(f"nguồn ruby không hợp lệ: {source_type}")
    if source_type in SPEND_SOURCES:
        raise ValueError(f"{source_type} là đường tiêu, phải đi qua spend()")

    granted = amount_for(db, source_type) if amount is None else amount
    if granted <= 0:
        # Nguồn đang tắt, hoặc mức đặt về 0. Im lặng bỏ qua chứ không lỗi: đây là
        # một quyết định vận hành, không phải một sự cố, và nó không được làm
        # hỏng hoạt động học đang gọi tới đây.
        return 0

    # Chèn rồi bắt vi phạm ràng buộc, KHÔNG phải "kiểm tra rồi chèn". Kiểm trước
    # để lại một khe giữa lần đọc và lần ghi, và hai request của cùng một cú bấm
    # đúp lọt qua khe đó cùng lúc — đúng kịch bản ràng buộc tồn tại để chặn.
    #
    # SAVEPOINT chứ không `ON CONFLICT` của Postgres: `ON CONFLICT` không chạy
    # trên SQLite, mà bộ test mặc định là SQLite. Khi bị huỷ, SAVEPOINT chỉ cuộn
    # lại đúng lần chèn này, không đụng tới việc học nằm cùng giao dịch.
    try:
        with db.begin_nested():
            db.add(
                RubyEvent(
                    user_id=user_id,
                    source_type=source_type,
                    source_id=source_id,
                    amount=granted,
                    **({"created_at": now} if now is not None else {}),
                )
            )
    except IntegrityError:
        # Đã trao rồi. Không phải lỗi: một bài dictation xong lần thứ hai, một
        # request lặp, một job chạy lại — tất cả đều bình thường.
        return 0
    return granted


def history(db: Session, user_id: uuid.UUID, *, limit: int = 50) -> list[RubyEvent]:
    """Các khoản gần nhất. Thứ duy nhất trả lời được "tôi có 40 ruby, giờ còn 10".

    `id` chỉ là dấu ngắt hoà để thứ tự TẤT ĐỊNH giữa hai lần đọc — nó là uuid
    ngẫu nhiên, nên hai khoản trong cùng một giây xếp trước sau không theo nghĩa
    nào cả. Chấp nhận được ở một danh sách lịch sử; nếu về sau nó được phân
    trang bằng offset thì cần một khoá thật sự tăng dần, vì lúc đó một dấu ngắt
    hoà vô nghĩa vẫn đủ tất định nhưng không còn đủ ĐÚNG.
    """
    return list(
        db.scalars(
            select(RubyEvent)
            .where(RubyEvent.user_id == user_id)
            .order_by(RubyEvent.created_at.desc(), RubyEvent.id)
            .limit(limit)
        )
    )


class NotEnoughRuby(Exception):
    """Số dư không đủ cho khoản định tiêu. Người gọi dịch thành 409, không phải 500."""

    def __init__(self, needed: int, available: int) -> None:
        super().__init__(f"cần {needed} ruby, còn {available}")
        self.needed = needed
        self.available = available


def _lock_user(db: Session, user_id: uuid.UUID) -> None:
    """Nối tiếp hoá mọi đường tiêu của ĐÚNG một người, trong giao dịch hiện tại.

    `pg_advisory_xact_lock` nhả khi giao dịch kết thúc — commit hay rollback —
    nên không có đường nào để lại một khoá treo. Khoá theo `user_id` chứ không
    theo bảng: hai người mua trứng cùng lúc không việc gì phải chờ nhau.

    Khoá nhận hai `int4`; lấy 64 bit đầu của uuid rồi tách đôi cho ổn định giữa
    các lần chạy. Va chạm băm chỉ khiến hai người dùng chung một khoá, tức là
    chậm hơn một chút — không bao giờ sai.

    **SQLite không có khoá tư vấn, và ở đó nó không cần**: bộ test mặc định chạy
    một luồng trên một kết nối. Bài kiểm đua thật là `integration`, chạy trên
    Postgres, và có `threading.Barrier` — vì bắn N luồng không kiểm được chuyện
    đua ở đây (`tests/test_concurrency.py` đã ghi lại bài học ấy).
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    key = int.from_bytes(user_id.bytes[:8], "big", signed=False)
    hi = ((key >> 32) & 0xFFFFFFFF) - 0x80000000
    lo = (key & 0xFFFFFFFF) - 0x80000000
    db.execute(text("SELECT pg_advisory_xact_lock(:hi, :lo)"), {"hi": hi, "lo": lo})


def spend(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID | None,
    amount: int,
) -> int:
    """Trừ ruby. Trả về số dư CÒN LẠI. Ném `NotEnoughRuby` nếu không đủ.

    **Mọi đường tiêu phải đi qua hàm này.** Đó là cái giá của việc giữ sổ cái làm
    nguồn sự thật duy nhất (ADR-011 §5): số dư là một phép `SUM`, nên "kiểm đủ
    tiền rồi trừ" có khe hở kinh điển — hai lần mở trứng gửi cùng lúc đều đọc
    thấy 30, đều thấy đủ cho một quả 25, đều ghi một hàng −25, và số dư thành
    −20 mà không ràng buộc nào bị vi phạm, không lỗi nào được ném. Khoá tư vấn
    khép khe đó lại; một đường tiêu thứ hai viết ở chỗ khác sẽ không có khoá, sẽ
    chạy đúng trong mọi lần thử tay, và sẽ hỏng đúng vào ngày có hai người bấm
    cùng lúc.

    Không `commit`, cùng lý do như `earn`: khoản tiêu phải sống chết cùng giao
    dịch của thứ nó mua. Khoá cũng chỉ nhả lúc đó.
    """
    if source_type not in RUBY_SOURCES:
        raise ValueError(f"nguồn ruby không hợp lệ: {source_type}")
    if amount <= 0:
        raise ValueError("khoản tiêu phải dương")

    _lock_user(db, user_id)
    available = balance(db, user_id)
    if available < amount:
        raise NotEnoughRuby(amount, available)

    db.add(
        RubyEvent(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            amount=-amount,
        )
    )
    # `flush` chứ không `commit`: hàng phải nằm trong giao dịch để lần `SUM` sau
    # nhìn thấy nó, nhưng người gọi mới là bên quyết định lúc nào việc mua hoàn
    # tất. Session chạy `autoflush=False`, nên không flush ở đây thì một lần tiêu
    # thứ hai trong CÙNG request vẫn đọc ra số dư cũ.
    db.flush()
    return available - amount


"""Số dư tối thiểu của một tài khoản QUẢN TRỊ, để thử được tính năng tiêu ruby.

Mở trứng giá 25, nên chừng này là hai chục quả — đủ để xem hết bảng tỉ lệ, chạm
được bộ đếm an ủi (10 quả) và gặp cả trường hợp trùng, mà không phải học hết một
chủ đề từ vựng trước mỗi lần thử.
"""
ADMIN_RUBY_FLOOR = 500


def top_up_admin(db: Session, *, user_id: uuid.UUID, role: str) -> int:
    """Kéo số dư của một admin lên `ADMIN_RUBY_FLOOR`. Trả về số ruby vừa cấp.

    **Là một hàng trong sổ cái, không phải một ngoại lệ lúc đọc.** Cho `balance()`
    trả về một con số khác cho admin là để màn hình nói một đằng và sổ cái nói
    một nẻo, rồi `spend` trừ trên con số thật và số dư tụt xuống âm. Một hàng
    `admin_grant` giữ nguyên tính chất "số dư là `SUM` của đúng một bảng", và nó
    còn trả lời được câu "chỗ ruby này ở đâu ra" — đúng thứ sổ cái tồn tại để trả
    lời.

    **Chỉ `admin`, không phải `editor`.** Cùng ranh giới mà `/admin/ruby/rules`
    đã vẽ: đây là quyền vận hành, không phải quyền biên tập.

    Cái giá phải nói ra: số dư ruby của một admin THẬT không còn là con số họ
    kiếm được. Đó là cùng đánh đổi với khung avatar bậc cao nhất mà admin được
    đeo sẵn — perk chạm đúng một thứ, và ở đây thứ đó là ví ruby. Level, XP và
    huy hiệu vẫn là con số thật của họ, vì ruby không nuôi cái nào trong ba cái
    đó (khác hẳn trường hợp XP, nơi một perk sẽ thổi phồng cả huy hiệu `level_*`).

    Lấy khoá tư vấn quanh bước kiểm-và-ghi, cùng lý do `spend` phải lấy: đây
    cũng là "đọc `SUM` rồi ghi", và hai request song song đều thấy thiếu sẽ cùng
    cấp. Ở đây hậu quả chỉ là thừa ruby thử nghiệm chứ không phải một quả trứng
    miễn phí, nhưng dùng lại đúng một cơ chế thì không có chỗ nào để nhớ nhầm.
    """
    if role != "admin":
        return 0
    _lock_user(db, user_id)
    available = balance(db, user_id)
    missing = ADMIN_RUBY_FLOOR - available
    if missing <= 0:
        return 0
    # `source_id` là uuid MỚI mỗi lần, không tất định: mỗi lần bù là một sự kiện
    # khác, không phải cùng một sự kiện được ghi lại. Tất định sẽ cấp đúng một
    # lần trong đời tài khoản, và admin tiêu hết là hết đường thử.
    return earn(
        db,
        user_id=user_id,
        source_type="admin_grant",
        source_id=uuid.uuid4(),
        amount=missing,
    )
