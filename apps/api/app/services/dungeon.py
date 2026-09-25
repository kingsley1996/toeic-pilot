"""Leo tháp dungeon: số má và chuyển trạng thái (migration 098).

Mọi con số của tháp nằm ở đây, không nằm ở route hay schema — cùng luật
"nhịp sinh phải là hàng/cấu hình tập trung" mà ADR-012 đặt cho chạm mặt.
Khác chạm mặt ở chỗ tháp KHÔNG qua `sync()`: battle do `start_battle` mở
thẳng khi người chơi đứng trước quái, không giờ hẹn, không trần.

Vòng đời một tầng: `ensure_run` → `start_battle` (một `Encounter`
kind=`dungeon`, `steps_total` = HP quái) → mỗi lượt trả lời đúng là một nhát
chém (`steps_done+1`, máy encounter lo), sai là một nhát quái chém
(`register_miss`) → hết bước là `register_clear` (sang tầng, checkpoint,
hồi máu) → HP về 0 là chết (`status=dead`, chờ `retry` về checkpoint).
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import DungeonRun, Encounter
from app.services import encounters

MAX_FLOOR = 100
"""Pha hiện tại: 100 tầng. Số này dời được mà không đụng DB (CHECK giữ 100,
nới khi pha sau mở thêm)."""

CHECKPOINT_EVERY = 10
HEAL_PER_CLEAR = 6
BATTLE_LIFE_SECONDS = 24 * 3600
"""Battle sống một ngày: bỏ dở giữa tầng thì hôm sau đánh tiếp tầng ấy, không
phạt (ADR-012 §4) — hết hạn thật thì `live_battle` mở lại cùng tầng."""


def monster_hp(floor: int) -> int:
    """HP quái = số câu phải đúng để qua tầng. Tầng 1: 3, tầng 100: 13."""
    return 3 + floor // 10


def monster_dmg(floor: int) -> int:
    """Sát thương một lượt sai. 2 ở chân tháp, 8 ở đỉnh."""
    return 2 + floor // 15


def pet_max_hp(level: int) -> int:
    """HP đầy của pet theo level (level lấy như `_as_public`: max tính được và
    mốc đã đạt, để chỉnh đường cong XP không lấy mất máu pet cũ)."""
    return 20 + 2 * level


def battle_reward(floor: int) -> int:
    """Ruby chốt lúc mở battle, như mọi encounter (thưởng không đổi giữa trận)."""
    return 10 + floor // 5


def battle_xp(floor: int) -> int:
    """XP pet khi xong tầng. Cao hơn intruder thường (15) từ tầng 25."""
    return 10 + floor // 2


def ensure_run(db: Session, user_id: uuid.UUID, level: int) -> DungeonRun:
    """Run của người này, hoặc hàng mới (tầng 1, máu đầy)."""
    run = db.get(DungeonRun, user_id)
    if run is None:
        run = DungeonRun(
            user_id=user_id,
            floor=1,
            checkpoint=1,
            pet_hp=pet_max_hp(level),
            status="fighting",
        )
        db.add(run)
        db.flush()
    return run


def live_battle(db: Session, run: DungeonRun, at: datetime) -> Encounter | None:
    """Battle đang đánh của run, hoặc `None` (chưa mở, xong, hay hết hạn)."""
    if run.battle_id is None:
        return None
    row = db.get(Encounter, run.battle_id)
    if row is None or row.kind != "dungeon" or row.state != "waiting":
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires <= at:
        row.state = "expired"
        return None
    return row


def start_battle(
    db: Session,
    *,
    user_id: uuid.UUID,
    run: DungeonRun,
    at: datetime,
    rng: random.Random | None = None,
) -> Encounter | None:
    """Mở battle cho tầng hiện tại. `None` khi kho từ vựng cạn.

    Battle là encounter thường loại `dungeon`: cùng bộ chấm, cùng SM-2, cùng
    đường thưởng — chỉ khác số bước (= HP quái tầng này) và hạn một ngày.
    """
    picker = rng or random.SystemRandom()
    target = encounters.pick_target(db, user_id, "vocabulary", picker)
    if target is None:
        return None
    row = Encounter(
        user_id=user_id,
        kind="dungeon",
        task_kind="vocabulary",
        target_id=target,
        steps_total=monster_hp(run.floor),
        steps_done=0,
        reward_ruby=battle_reward(run.floor),
        state="waiting",
        expires_at=at + timedelta(seconds=BATTLE_LIFE_SECONDS),
    )
    db.add(row)
    db.flush()
    run.battle_id = row.id
    db.flush()
    return row


def register_miss(db: Session, run: DungeonRun) -> bool:
    """Một lượt sai/`give_up`: quái chém. Trả `True` nếu pet chết."""
    run.pet_hp = max(0, run.pet_hp - monster_dmg(run.floor))
    if run.pet_hp <= 0:
        run.status = "dead"
        if run.battle_id is not None:
            lost = db.get(Encounter, run.battle_id)
            if lost is not None and lost.state == "waiting":
                lost.state = "expired"
            run.battle_id = None
        return True
    return False


def register_clear(db: Session, run: DungeonRun, *, pet_max_hp: int) -> None:
    """Xong tầng: sang tầng, checkpoint mỗi 10 tầng, hồi máu, gỡ battle.

    Tầng 100 xong là `done` — leo hết tháp, không mở battle nữa.
    """
    if run.floor >= MAX_FLOOR:
        run.status = "done"
        run.battle_id = None
        return
    run.floor += 1
    if (run.floor - 1) % CHECKPOINT_EVERY == 0:
        run.checkpoint = run.floor - 1
    run.pet_hp = min(pet_max_hp, run.pet_hp + HEAL_PER_CLEAR)
    run.battle_id = None


def retry(db: Session, run: DungeonRun, *, pet_max_hp: int) -> None:
    """Đánh lại từ checkpoint sau khi chết: máu đầy, battle mở lại ở lượt sau."""
    run.floor = run.checkpoint
    run.pet_hp = pet_max_hp
    run.status = "fighting"
    run.battle_id = None


def current_monster_hp(battle: Encounter) -> tuple[int, int]:
    """(HP còn lại, HP tối đa) của quái từ battle đang đánh."""
    return battle.steps_total - battle.steps_done, battle.steps_total
