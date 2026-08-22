"""Chỉnh cấu hình hệ level: mức XP, khe việc hôm nay, bậc level, bậc khung, luật badge.

Một router riêng thay vì nhét vào `admin.py`: tệp đó đã dài và nói về NỘI DUNG
(từ vựng, dictation, đề), còn ở đây là các tham số vận hành của hệ gamification.
Hai thứ đó thay đổi vì những lý do khác nhau và bởi những người khác nhau.

**Không có endpoint nào ở đây trao hay rút XP.** Sổ cái chỉ được ghi bởi
`app/services/progression.py` trên các đường học. Sửa cấu hình đổi cách tính từ
BÂY GIỜ trở đi, không đụng tới quá khứ — đó chính là điều sổ cái mua về, và cũng
là lý do các con số này an toàn để sửa.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.core.media import (
    PROGRESSION_KEY_PREFIX,
    progression_storage_key_for,
    upload_source_hash,
)
from app.core.storage import StorageError, get_driver
from app.models.progression import BadgeRule, DailyTaskSlot, FrameTier, LevelTier
from app.schemas.media import UploadTicket, UploadTicketRequest
from app.schemas.progression_admin import (
    BadgeRuleAdmin,
    BadgeRuleCreate,
    BadgeRuleUpdate,
    DailyTaskSlotAdmin,
    DailyTaskSlotCreate,
    DailyTaskSlotUpdate,
    FrameTierAdmin,
    FrameTierCreate,
    FrameTierUpdate,
    LevelTierAdmin,
    LevelTierUpdate,
    ProgressionConfigAdmin,
    ProgressionSettingAdmin,
    ProgressionSettingUpdate,
)
from app.services import progression_config

# `editor` KHÔNG đủ ở đây, khác với nội dung.
#
# Biên tập viên soạn bài; các con số này quyết định level của mọi tài khoản và
# đổ vào một sổ cái không sửa lại được. Đó là quyền vận hành, không phải quyền
# biên tập — nên cả router đứng sau `admin`.
router = APIRouter(
    prefix="/admin/progression",
    tags=["admin"],
    dependencies=[Depends(require_role("admin"))],
)


def _art_url(storage_key: str | None) -> str | None:
    return get_driver("image").public_url(storage_key) if storage_key else None


def _checked_art_key(storage_key: str | None) -> str | None:
    """Khoá tranh đã kiểm: đúng vùng, và file THẬT SỰ có trên kho.

    Hai lớp, và bỏ lớp nào cũng hỏng im lặng. Không kiểm tiền tố thì đây là một
    đường ghi chuỗi tuỳ ý — ai đó trỏ khung vào một ảnh nội dung, rồi lệnh dọn
    ảnh mồ côi xoá mất thứ đang được dùng (cùng lý do `avatar_confirm` kiểm).
    Không hỏi lại nhà cung cấp thì giao diện hiện ảnh vỡ cho tới khi có người
    để ý — và không ai để ý một cái khung.
    """
    if storage_key is None:
        return None
    if not storage_key.startswith(f"{PROGRESSION_KEY_PREFIX}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Khoá không thuộc vùng tranh của hệ level.",
        )
    try:
        get_driver("image").verify(storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None
    return storage_key


def _setting_admin(row: object) -> ProgressionSettingAdmin:
    return ProgressionSettingAdmin.model_validate(row, from_attributes=True)


def _slot_admin(row: DailyTaskSlot) -> DailyTaskSlotAdmin:
    return DailyTaskSlotAdmin(
        id=str(row.id),
        kind=row.kind,  # type: ignore[arg-type]
        label=row.label,
        target=row.target,
        xp=row.xp,
        position=row.position,
        enabled=row.enabled,
    )


def _frame_admin(row: FrameTier) -> FrameTierAdmin:
    return FrameTierAdmin(
        code=row.code,
        label=row.label,
        min_level=row.min_level,
        tone=row.tone,  # type: ignore[arg-type]
        ring=row.ring,
        image_storage_key=row.image_storage_key,
        image_url=_art_url(row.image_storage_key),
    )


def _badge_admin(row: BadgeRule) -> BadgeRuleAdmin:
    return BadgeRuleAdmin(
        code=row.code,
        label=row.label,
        hint=row.hint,
        icon=row.icon,  # type: ignore[arg-type]
        image_storage_key=row.image_storage_key,
        image_url=_art_url(row.image_storage_key),
        metric=row.metric,  # type: ignore[arg-type]
        target=row.target,
        position=row.position,
        enabled=row.enabled,
    )


def _config(db: Session) -> ProgressionConfigAdmin:
    return ProgressionConfigAdmin(
        setting=_setting_admin(progression_config.settings_row(db)),
        slots=[_slot_admin(row) for row in progression_config.slots(db, include_disabled=True)],
        levels=[
            LevelTierAdmin(level=row.level, xp_required=row.xp_required)
            for row in db.scalars(select(LevelTier).order_by(LevelTier.level))
        ],
        frames=[_frame_admin(row) for row in progression_config.frame_tiers(db)],
        badges=[
            _badge_admin(row) for row in progression_config.badge_rules(db, include_disabled=True)
        ],
    )


@router.get("", response_model=ProgressionConfigAdmin)
def read_config(db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    """Toàn bộ cấu hình. Seed bộ mặc định nếu đây là lần đọc đầu tiên."""
    progression_config.level_thresholds(db)  # sinh bảng level nếu chưa có
    return _config(db)


@router.patch("/setting", response_model=ProgressionConfigAdmin)
def update_setting(
    body: ProgressionSettingUpdate, db: Session = Depends(get_db)
) -> ProgressionConfigAdmin:
    """Sửa mức XP, trần ngày và tham số đường cong.

    **Đổi tham số đường cong KHÔNG tự sinh lại bảng level.** Bảng mới là sự thật
    của phép tra cứu, và admin có thể đã sửa tay vài bậc; ghi đè ngầm là xoá
    những chỉnh sửa đó mà không hỏi. Sinh lại là một hành động riêng, có nút
    riêng.
    """
    row = progression_config.settings_row(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    return _config(db)


@router.post("/levels/generate", response_model=ProgressionConfigAdmin)
def regenerate_levels(db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    """Ghi lại toàn bộ bảng level từ tham số đường cong.

    Tồn tại vì gõ tay 99 bậc là công việc không ai làm đúng tới hàng thứ mười.
    Nó GHI ĐÈ mọi chỉnh sửa thủ công, nên giao diện phải nói rõ trước khi bấm.
    """
    progression_config.generate_level_tiers(db, progression_config.settings_row(db))
    return _config(db)


@router.put("/levels", response_model=ProgressionConfigAdmin)
def replace_levels(body: LevelTierUpdate, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    """Ghi đè nguyên bảng level.

    Kiểm cả bảng như một khối trước khi ghi: level 1 phải là 0 XP, và ngưỡng phải
    TĂNG ĐỀU. Một bảng không tăng đều làm phép tra cứu dừng sai chỗ — người học
    đứng ở một level thấp hơn XP của họ, và vì `level_reached` chỉ đi lên, một
    mốc sai ghi xuống trong lúc đó thì ở lại vĩnh viễn.
    """
    tiers = sorted(body.tiers, key=lambda tier: tier.level)
    if tiers[0].level != 1 or tiers[0].xp_required != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Level 1 phải là bậc đầu tiên và cần 0 XP.",
        )
    for previous, current in zip(tiers, tiers[1:], strict=False):
        if current.level != previous.level + 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Thiếu level {previous.level + 1}: bảng phải liên tục.",
            )
        if current.xp_required <= previous.xp_required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Level {current.level} cần {current.xp_required} XP, "
                    f"không lớn hơn level {previous.level} ({previous.xp_required})."
                ),
            )

    db.query(LevelTier).delete()
    for tier in tiers:
        db.add(LevelTier(level=tier.level, xp_required=tier.xp_required))
    db.commit()
    return _config(db)


@router.post("/assets/ticket", response_model=UploadTicket)
def art_ticket(body: UploadTicketRequest) -> UploadTicket:
    """Vé tải tranh khung/huy hiệu lên.

    Khoá do PHÍA TA sinh từ một id ngẫu nhiên, y như mọi vé khác: để client chọn
    khoá thì một người có vé hợp lệ ghi đè được lên đường dẫn của người khác, và
    chữ ký khi đó chỉ chứng minh "được phép upload", không chứng minh "được phép
    upload vào đúng chỗ này".

    Không có bước `confirm` riêng. Bước đó là chính lệnh `PATCH` gắn khoá vào
    hàng — nó kiểm tiền tố và hỏi lại nhà cung cấp trước khi ghi, nên một khoá
    không có file thật không bao giờ vào tới bảng.
    """
    storage_key = progression_storage_key_for(upload_source_hash(str(uuid.uuid4())), ext=body.ext)
    return UploadTicket.of(get_driver("image").ticket(storage_key))


# --- khe việc hôm nay -------------------------------------------------------


@router.post("/slots", response_model=ProgressionConfigAdmin, status_code=status.HTTP_201_CREATED)
def create_slot(body: DailyTaskSlotCreate, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    progression_config.slots(db, include_disabled=True)  # seed trước khi thêm
    db.add(DailyTaskSlot(**body.model_dump()))
    db.commit()
    return _config(db)


@router.patch("/slots/{slot_id}", response_model=ProgressionConfigAdmin)
def update_slot(
    slot_id: uuid.UUID, body: DailyTaskSlotUpdate, db: Session = Depends(get_db)
) -> ProgressionConfigAdmin:
    """Sửa một khe. `id` không đổi, nên phần thưởng đã trao vẫn là đã trao."""
    row = db.get(DailyTaskSlot, slot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có khe này.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    return _config(db)


@router.delete("/slots/{slot_id}", response_model=ProgressionConfigAdmin)
def delete_slot(slot_id: uuid.UUID, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    """Xoá hẳn một khe.

    Tắt (`enabled = false`) gần như luôn là thứ bạn muốn thay vì xoá: `id` của
    khe là thứ chống trao lại XP, nên xoá rồi tạo lại một khe "y hệt" sẽ trao
    thưởng lần nữa cho những ngày đã trao. Endpoint vẫn tồn tại vì một khe tạo
    nhầm cần có đường dọn, nhưng giao diện mời tắt trước.
    """
    row = db.get(DailyTaskSlot, slot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có khe này.")
    db.delete(row)
    db.commit()
    return _config(db)


# --- bậc khung avatar -------------------------------------------------------


@router.post("/frames", response_model=ProgressionConfigAdmin, status_code=status.HTTP_201_CREATED)
def create_frame(body: FrameTierCreate, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    progression_config.frame_tiers(db)
    if db.get(FrameTier, body.code) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mã bậc đã tồn tại.")
    db.add(FrameTier(**body.model_dump()))
    db.commit()
    return _config(db)


@router.patch("/frames/{code}", response_model=ProgressionConfigAdmin)
def update_frame(
    code: str, body: FrameTierUpdate, db: Session = Depends(get_db)
) -> ProgressionConfigAdmin:
    # Seed trước khi tra: bộ mặc định chỉ tồn tại sau lần đọc đầu tiên, nên một
    # lệnh sửa gửi trước lần đọc đó sẽ 404 trên một hàng mà màn hình đang hiện.
    progression_config.frame_tiers(db)
    row = db.get(FrameTier, code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có bậc này.")
    changes = body.model_dump(exclude_unset=True)
    if "image_storage_key" in changes:
        changes["image_storage_key"] = _checked_art_key(changes["image_storage_key"])
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    return _config(db)


@router.delete("/frames/{code}", response_model=ProgressionConfigAdmin)
def delete_frame(code: str, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    # Seed trước khi tra: bộ mặc định chỉ tồn tại sau lần đọc đầu tiên, nên một
    # lệnh sửa gửi trước lần đọc đó sẽ 404 trên một hàng mà màn hình đang hiện.
    progression_config.frame_tiers(db)
    row = db.get(FrameTier, code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có bậc này.")
    db.delete(row)
    db.commit()
    return _config(db)


# --- luật huy hiệu ----------------------------------------------------------


@router.post("/badges", response_model=ProgressionConfigAdmin, status_code=status.HTTP_201_CREATED)
def create_badge(body: BadgeRuleCreate, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    progression_config.badge_rules(db, include_disabled=True)
    if db.get(BadgeRule, body.code) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mã huy hiệu đã tồn tại.")
    db.add(BadgeRule(**body.model_dump()))
    db.commit()
    return _config(db)


@router.patch("/badges/{code}", response_model=ProgressionConfigAdmin)
def update_badge(
    code: str, body: BadgeRuleUpdate, db: Session = Depends(get_db)
) -> ProgressionConfigAdmin:
    """Sửa một luật. `code` cố ý không nằm trong body — xem `BadgeRuleUpdate`."""
    progression_config.badge_rules(db, include_disabled=True)
    row = db.get(BadgeRule, code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có huy hiệu này.")
    changes = body.model_dump(exclude_unset=True)
    if "image_storage_key" in changes:
        changes["image_storage_key"] = _checked_art_key(changes["image_storage_key"])
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    return _config(db)


@router.delete("/badges/{code}", response_model=ProgressionConfigAdmin)
def delete_badge(code: str, db: Session = Depends(get_db)) -> ProgressionConfigAdmin:
    """Xoá một luật. Các hàng `user_badge` KHÔNG bị xoá theo.

    Đó là chủ ý: lịch sử "người này từng mở huy hiệu kia" là chuyện đã xảy ra.
    Bật lại một luật cùng mã sau này sẽ tìm lại đúng những hàng đó, nên không ai
    bị báo "huy hiệu mới" cho thứ họ đã có. Tắt vẫn tốt hơn xoá.
    """
    progression_config.badge_rules(db, include_disabled=True)
    row = db.get(BadgeRule, code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có huy hiệu này.")
    db.delete(row)
    db.commit()
    return _config(db)
