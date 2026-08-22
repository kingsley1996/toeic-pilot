"""Đọc cấu hình hệ level ra khỏi database, seed lười khi bảng còn trống.

Mọi con số của hệ này từng là hằng số trong code. Giờ chúng là hàng, và tệp này
là chỗ duy nhất biết cách lấy chúng ra — các dịch vụ khác (`progression`,
`daily_tasks`, `badges`) hỏi ở đây chứ không tự truy vấn.

**Seed lười, không seed trong migration.** Bộ mặc định sống một chỗ duy nhất ở
`app/models/progression.py`; bảng trống thì lần đọc đầu tiên ghi nó ra. Cùng
khuôn với `backdrop_setting`, và nó cũng là thứ khiến bộ test (chạy `create_all`
trên SQLite trống) hoạt động y như production mà không cần fixture nào.

Hệ quả cần biết: **bảng trống nghĩa là "chưa từng cấu hình", không phải "cố ý
không có gì".** Muốn tắt một khe daily task thì đặt `enabled = false`, đừng xoá
hàng cuối cùng — xoá hết rồi thì lần đọc sau seed lại bộ mặc định.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.progression import (
    DEFAULT_BADGE_RULES,
    DEFAULT_DAILY_TASK_SLOTS,
    DEFAULT_FRAME_TIERS,
    PROGRESSION_DEFAULTS,
    BadgeRule,
    DailyTaskSlot,
    FrameTier,
    LevelTier,
    ProgressionSetting,
)
from app.services.leveling import curve_thresholds


def settings_row(db: Session) -> ProgressionSetting:
    """Hàng cấu hình duy nhất, tạo từ bộ mặc định nếu chưa có."""
    row = db.get(ProgressionSetting, 1)
    if row is None:
        row = ProgressionSetting(id=1, **PROGRESSION_DEFAULTS)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def slots(db: Session, *, include_disabled: bool = False) -> list[DailyTaskSlot]:
    """Các khe việc hôm nay, theo thứ tự hiển thị."""
    rows = list(
        db.scalars(select(DailyTaskSlot).order_by(DailyTaskSlot.position, DailyTaskSlot.id))
    )
    if not rows:
        for spec in DEFAULT_DAILY_TASK_SLOTS:
            db.add(DailyTaskSlot(**spec))
        db.commit()
        rows = list(
            db.scalars(select(DailyTaskSlot).order_by(DailyTaskSlot.position, DailyTaskSlot.id))
        )
    return rows if include_disabled else [row for row in rows if row.enabled]


def generate_level_tiers(db: Session, row: ProgressionSetting) -> list[int]:
    """Ghi lại toàn bộ `level_tier` từ tham số đường cong. Trả về bảng ngưỡng.

    XOÁ SẠCH rồi ghi lại, chứ không cập nhật từng hàng: `max_level` giảm đi thì
    các bậc thừa phải biến mất, và một phép cập nhật-từng-hàng sẽ để chúng nằm
    lại — bảng khi đó vừa mang đường cong mới vừa mang phần đuôi của đường cong
    cũ, mà không có gì trông khác thường.
    """
    thresholds = curve_thresholds(
        coefficient=float(row.curve_coefficient),
        exponent=float(row.curve_exponent),
        break_at=row.curve_break,
        linear_step=row.curve_linear_step,
        max_level=row.max_level,
    )
    db.query(LevelTier).delete()
    for level in range(1, row.max_level + 1):
        db.add(LevelTier(level=level, xp_required=thresholds[level]))
    db.commit()
    return thresholds


def level_thresholds(db: Session) -> list[int]:
    """Bảng ngưỡng, chỉ số = level. Sinh từ tham số nếu bảng còn trống.

    Đọc HÀNG chứ không tính lại công thức mỗi lần: sau khi sinh, admin có thể đã
    sửa một bậc riêng lẻ, và tính lại sẽ lặng lẽ ghi đè lên chỉnh sửa đó.
    """
    rows = list(db.scalars(select(LevelTier).order_by(LevelTier.level)))
    if not rows:
        return generate_level_tiers(db, settings_row(db))

    thresholds = [0] * (rows[-1].level + 1)
    for row in rows:
        thresholds[row.level] = row.xp_required
    return thresholds


def frame_tiers(db: Session) -> list[FrameTier]:
    rows = list(db.scalars(select(FrameTier).order_by(FrameTier.min_level)))
    if not rows:
        for spec in DEFAULT_FRAME_TIERS:
            db.add(FrameTier(**spec))
        db.commit()
        rows = list(db.scalars(select(FrameTier).order_by(FrameTier.min_level)))
    return rows


def badge_rules(db: Session, *, include_disabled: bool = False) -> list[BadgeRule]:
    rows = list(db.scalars(select(BadgeRule).order_by(BadgeRule.position, BadgeRule.code)))
    if not rows:
        for position, (code, label, hint, icon, metric, target) in enumerate(
            DEFAULT_BADGE_RULES, start=1
        ):
            db.add(
                BadgeRule(
                    code=code,
                    label=label,
                    hint=hint,
                    icon=icon,
                    metric=metric,
                    target=target,
                    position=position,
                )
            )
        db.commit()
        rows = list(db.scalars(select(BadgeRule).order_by(BadgeRule.position, BadgeRule.code)))
    return rows if include_disabled else [row for row in rows if row.enabled]
