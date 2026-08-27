"""Ví ruby: số dư, lịch sử, quà hàng ngày (ADR-011).

Router riêng chứ không nhét vào `profile` hay `pet`: ruby kiếm được ở chỗ HỌC và
tiêu ở chỗ CHƠI, nên nó không thuộc về bên nào. Đặt nó dưới `/pet` sẽ dựng đúng
cái liên tưởng mà §3 cấm — rằng con thú cần ruby.

**Không có endpoint cộng ruby.** Ruby sinh ra bên trong những đường ghi đã tồn
tại (xong bài, thuộc chủ đề, nộp đề); một endpoint "cộng cho tôi" là endpoint
người ta gọi thẳng. Quà hàng ngày là ngoại lệ duy nhất và nó có cổng riêng: chỉ
mở sau khi hôm nay đã học thật.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.ruby import RubyClaimResult, RubyEntryPublic, RubyGiftPublic, RubyWallet
from app.services import ruby, ruby_daily
from app.services.profile import ensure_profile

router = APIRouter(prefix="/ruby", tags=["ruby"])

HISTORY_LIMIT = 20


def _labels(db: Session) -> dict[str, str]:
    labels = {rule.source_type: rule.label for rule in ruby.rules(db, include_disabled=True)}
    # Đường TIÊU không nằm trong bảng mức thưởng — bảng đó chỉ nói "kiếm được bao
    # nhiêu". Nhãn của nó sống ở đây, cạnh chỗ hiển thị.
    labels.setdefault("egg", "Mở trứng")
    labels.setdefault("egg_refund", "Trứng trùng, hoàn lại")
    labels.setdefault("admin_grant", "Ruby cấp cho quản trị")
    return labels


def _wallet(db: Session, user: User) -> RubyWallet:
    profile = ensure_profile(db, user)
    # Tài khoản quản trị luôn có sẵn ruby để thử tính năng. Bù ở đây, tức ngay
    # trước khi đọc số dư, nên con số hiện ra đã là con số sau khi bù — bù sau
    # thì màn hình in ra số cũ và phải tải lại mới thấy.
    if ruby.top_up_admin(db, user_id=user.id, role=user.role):
        db.commit()
    _, gift = ruby_daily.gift_state(db, user.id, profile.timezone)
    labels = _labels(db)
    return RubyWallet(
        balance=ruby.balance(db, user.id),
        gift=RubyGiftPublic(amount=gift.amount, unlocked=gift.unlocked, claimed=gift.claimed),
        recent=[
            RubyEntryPublic(
                id=str(event.id),
                amount=event.amount,
                source_type=event.source_type,
                label=labels.get(event.source_type, event.source_type),
                created_at=event.created_at,
            )
            for event in ruby.history(db, user.id, limit=HISTORY_LIMIT)
        ],
    )


@router.get("", response_model=RubyWallet)
def read_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RubyWallet:
    """Số dư, quà hôm nay, và các khoản gần nhất.

    Lịch sử đi kèm số dư chứ không nằm ở một endpoint riêng: nó là thứ DUY NHẤT
    trả lời được "tôi có 40 ruby, giờ còn 10", và một câu hỏi như thế được hỏi
    ngay tại chỗ nhìn thấy số dư.
    """
    return _wallet(db, current_user)


@router.post("/gift", response_model=RubyClaimResult)
def claim_gift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RubyClaimResult:
    """Nhận quà hôm nay.

    Bấm khi chưa học gì, hay bấm lần thứ hai, đều trả `granted = 0` với HTTP 200
    chứ không phải một mã lỗi: cả hai đều là trạng thái bình thường của cái nút,
    và giao diện đã có đủ dữ kiện trong `gift` để nói ra chuyện gì đang xảy ra.
    Một mã 409 ở đây chỉ tạo ra một hộp thoại lỗi cho một cú bấm đúp.
    """
    profile = ensure_profile(db, current_user)
    granted = ruby_daily.claim_gift(db, current_user.id, profile.timezone)
    if granted:
        db.commit()
    wallet = _wallet(db, current_user)
    return RubyClaimResult(granted=granted, balance=wallet.balance, gift=wallet.gift)
