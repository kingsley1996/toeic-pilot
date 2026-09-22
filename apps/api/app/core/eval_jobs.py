"""Chuông báo "có lượt eval chờ chạy", và không có gì hơn thế.

Cùng hình dạng `ai_jobs`: API **không thể** chạy suite eval — `app/main.py`
không được import `app.content` (PHASE2-AUDIO §A4.1), và ảnh production dựng
`--no-dev` không có extra `content`. Worker eval (cùng ảnh với worker TTS)
nghe kênh riêng này.
"""

import logging

import redis

logger = logging.getLogger(__name__)

CHANNEL = "toeic:eval:wanted"


def ring(client: redis.Redis) -> bool:
    """Publish một tiếng chuông. KHÔNG bao giờ ném lỗi — mất chuông thì vòng
    quét của worker vẫn nhặt lượt `queued` lên, chỉ muộn hơn."""
    try:
        client.publish(CHANNEL, "1")
    except redis.RedisError:
        logger.warning("eval_doorbell_unavailable")
        return False
    return True
