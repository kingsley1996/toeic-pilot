"""Shim tương thích: toàn bộ logic đã chuyển vào package `upgraded/`.

Giữ module này (thay vì xoá) vì `full.py` và CLI nhập `run_pending`/`main`
từ đây — xoá là vỡ hai chỗ đó mà không được gì.

    Kiến trúc (xem package `upgraded/`):

    START → write → structural_check → content_check → verdict
              ├── accept ──→ END
              ├── escalate → END
              └── evaluator → write (revise) / escalate
"""

from app.content.exam_agents.upgraded import (
    ArtifactVersion,
    Finding,
    RetryPolicy,
    RevisionPlan,
    RunMetrics,
    SlotState,
    build,
    main,
    parts_of,
    run_pending,
)

__all__ = [
    "ArtifactVersion",
    "Finding",
    "RetryPolicy",
    "RevisionPlan",
    "RunMetrics",
    "SlotState",
    "build",
    "main",
    "parts_of",
    "run_pending",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
