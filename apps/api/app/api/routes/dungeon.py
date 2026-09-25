"""Leo tháp dungeon: trạng thái run và đánh lại từ checkpoint (migration 098).

Trả lời từng lượt đi qua `POST /pet/encounters/{id}/answer` như mọi chạm mặt —
ở đây chỉ giữ việc "đứng ở đâu trong tháp". Battle tự mở ở `GET` khi chưa có,
cùng triết lý spawn-on-read của ADR-012 §1: không job nền, không bỏ lỡ.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.pet import _encounter_public, _require_pet
from app.core.database import get_db
from app.models import DungeonRun, User
from app.schemas.dungeon import DungeonState
from app.schemas.pet import EncounterPublic
from app.services import dungeon
from app.services import pet as needs_service
from app.services.pet_state import current_pet

router = APIRouter(tags=["dungeon"])


def _state_of(run: DungeonRun, max_hp: int, battle: EncounterPublic | None) -> DungeonState:
    return DungeonState(
        floor=run.floor,
        checkpoint=run.checkpoint,
        pet_hp=run.pet_hp,
        pet_max_hp=max_hp,
        status=run.status,
        updated_at=run.updated_at,
        battle=battle,
    )


def _run_for(db: Session, user: User) -> tuple[DungeonRun, int]:
    """Run + máu đầy của pet đang nuôi. 409 khi chưa mở trứng."""
    _state, pet = current_pet(db, user.id)
    pet_row = _require_pet(pet)
    # Mốc cao nhất, không phải level vừa tính — cùng công thức `_as_public`,
    # để chỉnh đường cong XP về sau không lấy mất máu pet cũ.
    progress = needs_service.level_progress(pet_row.xp)
    level = max(progress.level, pet_row.level_reached)
    run = dungeon.ensure_run(db, user.id, level)
    return run, dungeon.pet_max_hp(level)


@router.get("/dungeon/state", response_model=DungeonState)
def read_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DungeonState:
    run, max_hp = _run_for(db, current_user)
    at = datetime.now(UTC)
    battle: EncounterPublic | None = None
    if run.status == "fighting":
        row = dungeon.live_battle(db, run, at)
        if row is None:
            row = dungeon.start_battle(db, user_id=current_user.id, run=run, at=at)
        if row is not None:
            battle = _encounter_public(db, row)
    db.commit()
    db.refresh(run)
    return _state_of(run, max_hp, battle)


@router.post("/dungeon/retry", response_model=DungeonState)
def retry_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DungeonState:
    """Đánh lại từ checkpoint sau khi chết. Chỉ khi `dead`, còn sống mà xin
    về checkpoint là một nút hồi máu miễn phí."""
    run, max_hp = _run_for(db, current_user)
    if run.status != "dead":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Chỉ đánh lại khi đã thua."
        )
    dungeon.retry(db, run, pet_max_hp=max_hp)
    db.commit()
    db.refresh(run)
    return _state_of(run, max_hp, None)
