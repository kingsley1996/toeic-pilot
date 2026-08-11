"""Tiến trình chạy dài sinh audio cho nội dung đang thiếu (ADR-007 §2.7b).

    uv run python -m app.content.tts_worker [--sweep-seconds N] [--once]

Nó là `backfill_audio` đặt trong một vòng lặp, cộng một tai nghe chuông. Không
có logic riêng nào về "việc gì cần làm" — câu đó chỉ có một chỗ trả lời, là
`run_backfill`, và cả CLI lẫn worker đều đi qua đó.

Hai nhịp, và **cái chậm mới là cái đảm bảo**:

  chuông Redis  -> thức dậy ngay, cho biên tập viên thấy kết quả trong vài giây
  quét định kỳ  -> chạy dù chuông có kêu hay không

Nghĩa là Redis chết, worker khởi động lại giữa lúc bấm nút, hay message rơi mất
đều không làm nội dung nào bị bỏ quên — chỉ muộn hơn. Đây là lý do chuông được
phép là pub/sub không bền: nó không mang thông tin nào để mà mất.

Một lượt quét hỏng **không** giết worker. edge-tts thỉnh thoảng trả 403 hàng
loạt khi Microsoft xoay token ký, và một tiến trình chết vì thế sẽ nằm im cho
tới khi có người để ý — trong khi thứ đúng phải làm là thử lại ở lượt sau.
"""

import argparse
import logging
import signal
import sys
import threading
import types

import redis

from app.content.backfill_audio import run_backfill
from app.content.settings import content_settings
from app.core.audio_jobs import CHANNEL
from app.core.config import settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

DEFAULT_SWEEP_SECONDS = 300.0

# Gộp nhiều tiếng chuông liên tiếp thành một lượt quét. Ghi mười câu rồi bấm nút
# mười lần thì mười lượt quét chồng lên nhau chẳng tìm thấy gì thêm — lượt đầu
# đã làm hết. Chờ một nhịp ngắn rồi mới chạy cũng gom được cả loạt bấm đó.
DEBOUNCE_SECONDS = 2.0


class Doorbell:
    """Tai nghe chuông, tự nối lại, và không bao giờ giết vòng lặp chính.

    Chạy ở luồng riêng vì `pubsub.listen()` chặn, còn vòng quét thì phải chạy
    theo đồng hồ của nó. Hai bên gặp nhau ở đúng một `threading.Event`.
    """

    def __init__(self, url: str, wake: threading.Event, stop: threading.Event) -> None:
        self._url = url
        self._wake = wake
        self._stop = stop

    def listen_forever(self) -> None:
        while not self._stop.is_set():
            try:
                client = redis.from_url(self._url, decode_responses=True)
                # redis-py không có type stub cho `pubsub()`; đây là ranh giới
                # thư viện, không phải chỗ nới lỏng kiểu của mình.
                pubsub = client.pubsub(ignore_subscribe_messages=True)  # type: ignore[no-untyped-call]
                pubsub.subscribe(CHANNEL)
                logger.info("doorbell_listening", extra={"channel": CHANNEL})
                for message in pubsub.listen():
                    if self._stop.is_set():
                        return
                    if message and message.get("type") == "message":
                        logger.info("doorbell_rung")
                        self._wake.set()
            except redis.RedisError as exc:
                # Phụ thuộc mềm: mất chuông chỉ có nghĩa là chậm hơn, nên ghi log
                # rồi thử lại chứ không tắt worker.
                logger.warning("doorbell_unavailable", extra={"error": str(exc)})
                self._stop.wait(5.0)


def sweep() -> None:
    try:
        counts = run_backfill(settings=content_settings)
    except Exception:
        # Cố ý bắt hết: một lượt hỏng phải thành một dòng log, không phải một
        # tiến trình chết nằm im tới khi có người để ý.
        logger.exception("sweep_failed")
        return
    if counts.synthesised or counts.linked or counts.failed:
        logger.info("sweep_done", extra={"result": counts.as_line()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh audio cho nội dung đang thiếu.")
    parser.add_argument("--sweep-seconds", type=float, default=DEFAULT_SWEEP_SECONDS)
    parser.add_argument("--once", action="store_true", help="quét một lượt rồi thoát")
    args = parser.parse_args(argv)

    configure_logging()

    if args.once:
        sweep()
        return 0

    stop = threading.Event()
    wake = threading.Event()

    def shutdown(_signum: int, _frame: types.FrameType | None) -> None:
        # `docker stop` gửi SIGTERM. Không bắt thì container mất mười giây rồi
        # ăn SIGKILL giữa lúc đang ghi manifest.
        logger.info("worker_stopping")
        stop.set()
        wake.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    listener = threading.Thread(
        target=Doorbell(settings.redis_url, wake, stop).listen_forever,
        name="doorbell",
        daemon=True,
    )
    listener.start()

    logger.info("worker_started", extra={"sweep_seconds": args.sweep_seconds})
    while not stop.is_set():
        sweep()
        # Chờ chuông HOẶC hết giờ, cái nào tới trước. `wait` trả True khi có
        # chuông; lúc đó nghỉ thêm một nhịp ngắn để gộp cả loạt bấm liên tiếp.
        if wake.wait(timeout=args.sweep_seconds) and not stop.is_set():
            stop.wait(DEBOUNCE_SECONDS)
        wake.clear()

    logger.info("worker_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
