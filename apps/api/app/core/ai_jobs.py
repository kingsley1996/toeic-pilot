"""Chuông báo "có việc gắn nhãn", và không có gì hơn thế.

Sao chép nguyên hình dạng của `audio_jobs`, vì ràng buộc giống hệt: API **không
thể** chạy pipeline làm giàu — `app/main.py` không được import `app.content`
(PHASE2-AUDIO §A4.1), và ảnh production dựng `--no-dev` không có extra `content`.

Kênh riêng chứ không dùng chung kênh với TTS: hai worker khác nhau, hai loại
việc khác nhau, và gộp lại thì mỗi lần bấm nút sinh audio sẽ đánh thức cả worker
gắn nhãn đi hỏi database một câu hỏi chắc chắn không có việc.
"""

import logging

import redis

logger = logging.getLogger(__name__)

CHANNEL = "toeic:skilltag:wanted"


def ring(client: redis.Redis) -> bool:
    """Publish một tiếng chuông. KHÔNG bao giờ ném lỗi.

    Chuông mất là chuyện chấp nhận được vì nó **không mang thông tin**: worker
    có vòng quét định kỳ chạy đúng truy vấn ấy. Báo thất bại chỉ khiến biên tập
    viên bấm lại một thứ vốn đã sẽ chạy.
    """
    try:
        client.publish(CHANNEL, "1")
    except redis.RedisError:
        logger.warning("skilltag_doorbell_unavailable")
        return False
    return True
