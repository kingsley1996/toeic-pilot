"""Worker chạy eval AI từ hàng đợi `eval_run`.

Cùng hình dạng `skilltag_worker` (chuông + vòng quét, tiến trình riêng, cùng
ảnh worker có extra `content`), vì cùng ràng buộc: API không được import
`app.content` (PHASE2-AUDIO §A4.1). Khác ở một chỗ: eval là việc theo YÊU CẦU
(bấm nút mới có), không phải việc nền định kỳ — nên không có quét "tìm việc
mới", chỉ nhặt hàng `queued` cũ nhất khi chuông reo hoặc tới kỳ quét.

    uv run python -m app.content.eval_worker --once   # một lượt rồi thoát
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import types
from collections.abc import Callable
from datetime import UTC, datetime

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.eval_run import EvalRun

logger = logging.getLogger(__name__)

CHANNEL = "toeic:eval:wanted"
DEFAULT_SWEEP_SECONDS = 60.0


def process_one(session_factory: Callable[[], Session] = SessionLocal) -> str | None:
    """Nhặt lượt `queued` cũ nhất và chạy. Trả về id đã chạy, None nếu không có việc.

    Nhận factory để test được trên database của test (SessionLocal mặc định trỏ
    vào database của tiến trình gọi — ở test là SQLite memory riêng).
    """
    session = session_factory()
    try:
        run = (
            session.query(EvalRun)
            .filter_by(status="queued")
            .order_by(EvalRun.created_at.asc())
            .first()
        )
        if run is None:
            return None
        run_id = str(run.id)
        _run_eval_job(session, run)
        return run_id
    finally:
        session.close()


def _run_eval_job(session: Session, run: EvalRun) -> None:
    """Chạy một lượt eval và ghi báo cáo vào hàng. Mọi ngoại lệ thành `error`,
    không bao giờ để hàng kẹt ở `running`."""
    from app.content.eval_ai import DATASETS, EVAL_DIR, KB_DIR, run_suite
    from app.content.eval_core import SUITES, _report_json, load_cases, load_thresholds

    run.status = "running"
    run.started_at = datetime.now(UTC)
    session.commit()
    try:
        params = run.params or {}
        if run.suite == "judge":
            judge_model = params.get("judge_model")
            gen_model = params.get("gen_model")
            if not judge_model or not gen_model:
                raise ValueError("judge cần judge_model + gen_model")
            if judge_model == gen_model:
                raise ValueError("judge trùng model sinh")
            from app.content.eval_suites.coach import judge_coach
            from app.content.exam_cli.paths import _gateway

            cases = load_cases(DATASETS / "coach_explain.jsonl", {"id", "question", "reply"})
            reports = [judge_coach(cases, _gateway(judge_model))]
            floors: dict[str, float] = {}
        else:
            if run.suite != "all" and run.suite not in SUITES:
                raise ValueError(f"suite lạ: {run.suite!r}")
            names = list(SUITES) if run.suite == "all" else [run.suite]
            mode = str(params.get("retrieval_mode", "lexical"))
            reports = [run_suite(name, DATASETS, KB_DIR, mode) for name in names]
            floors = load_thresholds(EVAL_DIR / "thresholds.json")
        run.report = _report_json(
            reports, against=None, suite_arg=run.suite, floors=floors, datasets=DATASETS
        )
        run.status = "done"
    except Exception as exc:  # noqa: BLE001 — hàng error vẫn hơn hàng kẹt running
        run.status = "error"
        run.error = str(exc)[:2000]
    run.finished_at = datetime.now(UTC)
    session.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker chạy eval AI từ hàng đợi")
    parser.add_argument("--once", action="store_true", help="chạy một lượt rồi thoát")
    parser.add_argument("--sweep-seconds", type=float, default=DEFAULT_SWEEP_SECONDS)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    if args.once:
        done = process_one()
        print("đã chạy:", done or "(không có việc)")
        return 0

    wake = threading.Event()
    stop = threading.Event()

    def shutdown(_signum: int, _frame: types.FrameType | None) -> None:
        stop.set()
        wake.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Vòng nghe riêng (không mượn Doorbell của skilltag_worker vì kênh cứng
    # khác nhau): cùng hình — luồng riêng, Redis chết không giết worker.
    def listen_forever() -> None:
        while not stop.is_set():
            try:
                client = redis.from_url(settings.redis_url, decode_responses=True)
                pubsub = client.pubsub(ignore_subscribe_messages=True)  # type: ignore[no-untyped-call]
                pubsub.subscribe(CHANNEL)
                for _message in pubsub.listen():
                    if stop.is_set():
                        return
                    wake.set()
            except redis.RedisError as exc:
                logger.warning("eval_doorbell_down", extra={"error": str(exc)})
                stop.wait(10.0)

    threading.Thread(target=listen_forever, daemon=True).start()

    while not stop.is_set():
        try:
            process_one()
        except Exception:  # noqa: BLE001 — một lượt hỏng không được giết worker
            logger.exception("eval_sweep_failed")
        wake.wait(args.sweep_seconds)
        wake.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
