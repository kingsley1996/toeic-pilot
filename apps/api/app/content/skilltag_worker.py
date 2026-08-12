"""Worker gắn nhãn: nghe chuông Redis, và quét định kỳ dù chuông có kêu hay không.

Cùng hình dạng với `tts_worker`, vì cùng ràng buộc — API không chạy được việc
này. Nhưng là **tiến trình riêng**, không nhét chung vào worker TTS: hai loại
việc khác nhau, và gộp lại thì mỗi lần bấm nút sinh audio sẽ đánh thức cả nhánh
gắn nhãn đi hỏi database một câu chắc chắn không có việc.

Vòng quét vẫn còn dù đã có chuông, và đó không phải thừa: pub/sub của Redis
không bền, nên một message publish lúc worker đang khởi động lại là mất hẳn.
Vòng quét là thứ khiến việc đó chỉ có nghĩa "muộn hơn" chứ không phải "không bao
giờ".
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import types

import redis

from app.core.ai_jobs import CHANNEL
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SWEEP_SECONDS = 300.0


class Doorbell:
    """Chạy ở luồng riêng vì `pubsub.listen()` chặn, còn vòng quét phải chạy tiếp."""

    def __init__(self, url: str, wake: threading.Event, stop: threading.Event) -> None:
        self._url = url
        self._wake = wake
        self._stop = stop

    def listen_forever(self) -> None:
        while not self._stop.is_set():
            try:
                client = redis.from_url(self._url, decode_responses=True)
                # redis-py không có stub cho `pubsub()`; ranh giới đã biết.
                pubsub = client.pubsub(ignore_subscribe_messages=True)  # type: ignore[no-untyped-call]
                pubsub.subscribe(CHANNEL)
                for _message in pubsub.listen():
                    if self._stop.is_set():
                        return
                    self._wake.set()
            except redis.RedisError as exc:
                # Redis chết KHÔNG được giết worker: vòng quét vẫn tìm được việc.
                logger.warning("skilltag_doorbell_down", extra={"error": str(exc)})
                self._stop.wait(10.0)


def sweep() -> int:
    from app.content.enrich_skills import main as run_enrichment

    return run_enrichment([])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker gắn skill_tag")
    parser.add_argument("--once", action="store_true", help="quét một lượt rồi thoát")
    parser.add_argument("--sweep-seconds", type=float, default=DEFAULT_SWEEP_SECONDS)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    if args.once:
        return sweep()

    wake = threading.Event()
    stop = threading.Event()

    def shutdown(_signum: int, _frame: types.FrameType | None) -> None:
        stop.set()
        wake.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    doorbell = Doorbell(settings.redis_url, wake, stop)
    threading.Thread(target=doorbell.listen_forever, daemon=True).start()

    while not stop.is_set():
        try:
            sweep()
        except Exception:  # noqa: BLE001 — một lượt quét hỏng không được giết worker
            logger.exception("skilltag_sweep_failed")
        wake.wait(args.sweep_seconds)
        wake.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
