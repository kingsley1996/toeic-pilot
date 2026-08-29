import logging
import time

import redis
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.services import health_history

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Deliberately checks no dependencies —
    a failing database should not get the container killed and restarted."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    """Readiness: can this instance actually serve traffic?

    Returns 503 when Postgres is unreachable so a load balancer stops routing
    here. Redis is a soft dependency (see the startup path in app.main), so an
    outage there degrades rather than removes the instance.
    """
    checks: dict[str, str] = {}
    latencies: dict[str, float] = {}

    try:
        started = time.perf_counter()
        db.execute(text("SELECT 1"))
        latencies["database"] = (time.perf_counter() - started) * 1000
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        checks["database"] = "unavailable"
        logger.error("readiness_database_check_failed", extra={"error": str(exc)})

    try:
        started = time.perf_counter()
        get_redis().ping()
        latencies["redis"] = (time.perf_counter() - started) * 1000
        checks["redis"] = "ok"
    except (redis.RedisError, OSError) as exc:
        checks["redis"] = "degraded"
        logger.warning("readiness_redis_check_failed", extra={"error": str(exc)})

    ready_now = checks["database"] == "ok"
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Ghi lại phép đo vừa làm, để `/admin/health` có lịch sử mà không cần thêm
    # một bộ lập lịch nào. Tự giới hạn tần suất; hỏng thì im lặng bỏ qua, vì
    # readiness không được phụ thuộc vào việc ghi chép về chính nó.
    if ready_now:
        health_history.record(
            db,
            [
                ("database", "ok", latencies.get("database")),
                ("redis", "ok" if checks["redis"] == "ok" else "degraded", latencies.get("redis")),
            ],
        )

    return {"status": "ready" if ready_now else "not_ready", "checks": checks}
