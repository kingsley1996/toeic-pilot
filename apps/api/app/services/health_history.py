"""Ghi lại và tổng hợp tình trạng dịch vụ theo thời gian (migration 049).

`/ready` vốn đã kiểm Postgres và Redis mỗi lần được gọi; ở đây chỉ lưu kết quả
lại. Không có bộ lập lịch nào ở production, và tài liệu này không thêm cái nào —
nhịp lấy mẫu chính là nhịp của monitor bên ngoài đang ping để giữ dịch vụ khỏi
ngủ.

**Một sự cố Postgres không ghi vào Postgres được.** Nó để lại KHOẢNG TRỐNG, và
người đọc phải thấy khoảng trống đó là khoảng trống chứ không phải màu xanh.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import HealthSample

# Ghi nhiều nhất một mẫu mỗi dịch vụ mỗi phút. Render tự gọi `/ready` để kiểm
# sức khoẻ container, nên không chặn thì bảng phình theo nhịp của Render chứ
# không theo nhịp của phép đo.
MIN_GAP_SECONDS = 60.0
# Bộ nhớ của TIẾN TRÌNH, không phải của cụm. Render free chạy một instance nên
# nó đúng; thêm instance thứ hai thì tần suất ghi tăng theo số instance, chứ
# không hỏng.
_last_written: dict[str, float] = {}

RETENTION_DAYS = 7
_PRUNE_GAP_SECONDS = 3600.0
_last_pruned = 0.0

# Cùng tập giá trị với CHECK của bảng và với `DependencyState` ở tầng schema.
State = Literal["ok", "degraded", "down"]

_SEVERITY: dict[str, int] = {"ok": 0, "degraded": 1, "down": 2}


def record(db: Session, samples: list[tuple[str, State, float | None]]) -> None:
    """Lưu một lượt đo. Không bao giờ ném ra — đây là ghi chép, không phải nghiệp vụ."""
    now = time.monotonic()
    fresh = [s for s in samples if now - _last_written.get(s[0], -1e9) >= MIN_GAP_SECONDS]
    if not fresh:
        return
    try:
        for service, state, latency in fresh:
            db.add(
                HealthSample(
                    service=service,
                    state=state,
                    latency_ms=None if latency is None else int(latency),
                )
            )
        _prune(db, now)
        db.commit()
        for service, _, _ in fresh:
            _last_written[service] = now
    except SQLAlchemyError:
        db.rollback()


def _prune(db: Session, now: float) -> None:
    global _last_pruned
    if now - _last_pruned < _PRUNE_GAP_SECONDS:
        return
    _last_pruned = now
    db.execute(
        delete(HealthSample).where(
            HealthSample.checked_at < datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        )
    )


@dataclass
class Bucket:
    start: datetime
    state: State | None  # None = không có mẫu nào rơi vào khoảng này
    latency_ms: int | None


@dataclass
class ServiceUptime:
    service: str
    buckets: list[Bucket]
    samples: int
    ok_ratio: float | None  # None khi chưa có mẫu nào
    worst: State | None


def uptime(db: Session, service: str, hours: int, slots: int) -> ServiceUptime:
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = (
        db.execute(
            select(HealthSample.state, HealthSample.latency_ms, HealthSample.checked_at)
            .where(HealthSample.service == service, HealthSample.checked_at >= since)
            .order_by(HealthSample.checked_at)
        )
        .tuples()
        .all()
    )
    width = timedelta(hours=hours) / slots
    grouped: list[list[tuple[str, int | None]]] = [[] for _ in range(slots)]
    for state, latency, at in rows:
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        index = min(slots - 1, max(0, int((at - since) / width)))
        grouped[index].append((state, latency))

    buckets: list[Bucket] = []
    for i, group in enumerate(grouped):
        start = since + width * i
        if not group:
            buckets.append(Bucket(start=start, state=None, latency_ms=None))
            continue
        # Trạng thái TỆ NHẤT trong khoảng, không phải trạng thái cuối: một phút
        # hỏng giữa một giờ khoẻ vẫn phải nhìn thấy được.
        # CHECK của bảng chỉ cho ba giá trị, nên thu hẹp kiểu ở đây là an toàn.
        worst = cast(State, max(group, key=lambda g: _SEVERITY.get(g[0], 0))[0])
        seen = [latency for _, latency in group if latency is not None]
        buckets.append(
            Bucket(
                start=start, state=worst, latency_ms=round(sum(seen) / len(seen)) if seen else None
            )
        )

    ok = sum(1 for state, _, _ in rows if state == "ok")
    return ServiceUptime(
        service=service,
        buckets=buckets,
        samples=len(rows),
        ok_ratio=(ok / len(rows)) if rows else None,
        worst=cast(State, max((r[0] for r in rows), key=lambda s: _SEVERITY.get(s, 0)))
        if rows
        else None,
    )
