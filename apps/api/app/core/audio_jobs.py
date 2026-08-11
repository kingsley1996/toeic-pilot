"""Chuông báo "có việc sinh audio", và không có gì hơn thế.

Đây là toàn bộ phần mà API được phép biết về đường TTS (ADR-007 §2.7b). API
**không thể** sinh audio: `app/main.py` không được import `app.content` (A4.1),
ảnh production dựng `--no-dev` không có extra `content`, edge-tts cần mạng,
ffmpeg cần cài. Đó là ràng buộc, không phải thiếu sót.

Nhưng biên tập viên vẫn cần một cái nút. Hình dạng rẻ nhất giữ được cả A4.1 lẫn
A2.5 là một tiếng chuông:

    bấm nút   -> API publish một message Redis. KHÔNG ghi bảng nào.
    worker    -> thức dậy sớm, chạy đúng truy vấn của `backfill_audio`
    chuông mất -> vòng quét định kỳ vẫn bắt được, chỉ muộn hơn

**Không bảng hàng đợi, không trạng thái retry.** Hàng đợi vẫn là *câu hỏi* "nội
dung nào thiếu audio hoặc audio không còn khớp lời thoại", nên chạy lại chỉ đơn
giản là thấy ít việc hơn, và một job chết không để lại rác.

Pub/sub chứ không phải danh sách, và đó là lựa chọn có chủ ý: message publish
lúc worker đang tắt sẽ **mất**. Không sao — nó không mang thông tin nào. Nó chỉ
nói "sớm hơn đi", còn *việc gì cần làm* thì worker tự hỏi database. Dùng danh
sách bền vững ở đây sẽ dựng lại đúng cái hàng đợi có trạng thái mà A2.5 tránh.

Redis là phụ thuộc **mềm**, như mọi chỗ khác trong dự án (`/ready` báo
`degraded` chứ không fail). Chuông hỏng thì nội dung vẫn được sinh, chỉ chậm hơn.
"""

import logging

import redis

logger = logging.getLogger(__name__)

CHANNEL = "toeic:audio:wanted"


def ring(client: redis.Redis) -> bool:
    """Đánh chuông. Trả về việc chuông có kêu không, và không bao giờ ném lỗi.

    Bên gọi là một request handler: Redis chết không được biến thành 500 cho một
    thao tác mà đường chậm vẫn hoàn thành được.
    """
    try:
        client.publish(CHANNEL, "1")
    except redis.RedisError:
        logger.warning("audio_doorbell_unavailable")
        return False
    return True
