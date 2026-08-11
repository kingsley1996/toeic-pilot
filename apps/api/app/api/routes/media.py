"""Upload media: xin vé, rồi báo đã xong.

Bốn bước của ADR-006 §2.3, và API chỉ đứng ở bước 1 và 4:

    trình duyệt ──(1) xin vé────────> đây
    trình duyệt <──(2) vé đã ký──────┘
    trình duyệt ──(3) POST file─────> Cloudinary       ← không đi qua đây
    trình duyệt ──(4) báo xong──────> đây ──> ghi hàng image_asset

Bước 4 **phải hỏi lại nhà cung cấp**. Không có nó, endpoint xác nhận là một
đường ghi hàng asset tuỳ ý vào database: ai cũng gọi được nó với một
`storage_key` bịa ra, và hàng sinh ra sẽ trỏ tới một file không tồn tại. Đây
không phải lo xa — lần chạy thử thật đầu tiên có upload trả 200 mà `verify()`
trả 404 (ADR-006 §2.4b), và chính bước này bắt được.
"""

import uuid
from typing import Annotated

import redis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.audio_jobs import ring
from app.core.database import get_db
from app.core.media import (
    AUDIO_ACCENTS,
    image_storage_key_for,
    public_audio_url,
    storage_key_for,
    upload_source_hash,
)
from app.core.rate_limit import Quota, rate_limit
from app.core.redis_client import get_redis
from app.core.storage import (
    LOCAL_UPLOAD_PATH,
    MAX_IMAGE_BYTES,
    LocalDiskDriver,
    StorageError,
    get_driver,
    local_signature_valid,
)
from app.models.audio import AudioAsset
from app.models.image import ImageAsset
from app.schemas.media import (
    AudioAssetPublic,
    AudioConfirm,
    AudioRequestAck,
    AudioTicketRequest,
    ImageAssetPublic,
    ImageConfirm,
    UploadTicket,
    UploadTicketRequest,
)

router = APIRouter(prefix="/admin/media", tags=["media"])

can_edit = require_role("editor", "admin")

# Hạn mức của một biên tập viên đang nhập đề: đủ rộng để không bao giờ vướng khi
# làm việc thật, đủ hẹp để một script chạy loạn không kịp tốn tiền.
TICKET_QUOTA = Quota(limit=60, window_seconds=60 * 10)
CONFIRM_QUOTA = Quota(limit=120, window_seconds=60 * 10)


def _asset_public(asset: ImageAsset) -> ImageAssetPublic:
    return ImageAssetPublic(
        id=str(asset.id),
        storage_key=asset.storage_key,
        # URL lấy từ DRIVER, không phải phép nối chuỗi của audio: chỉ driver biết
        # tiền tố thư mục mà Cloudinary đòi trong `public_id` (ADR-006 §2.4b).
        # Vẫn không gọi object store — `public_url` là hàm thuần.
        url=get_driver("image").public_url(asset.storage_key),
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        source=asset.source,
        source_url=asset.source_url,
        license=asset.license,
        attribution=asset.attribution,
        alt_text=asset.alt_text,
    )


@router.post(
    "/images/ticket",
    response_model=UploadTicket,
    dependencies=[Depends(can_edit), Depends(rate_limit("media-ticket", TICKET_QUOTA))],
)
def image_ticket(body: UploadTicketRequest) -> UploadTicket:
    """Cấp một vé upload đã ký.

    Khoá do PHÍA TA sinh, từ một id ngẫu nhiên — client không được chọn nơi file
    sẽ nằm. Để client đặt khoá thì một người có vé hợp lệ có thể ghi đè lên
    đường dẫn của người khác, và chữ ký khi đó chỉ chứng minh "ai đó được phép
    upload", không chứng minh "được phép upload vào đúng chỗ này".
    """
    source_hash = upload_source_hash(str(uuid.uuid4()))
    storage_key = image_storage_key_for(source_hash, ext=body.ext)
    ticket = get_driver("image").ticket(storage_key)
    return UploadTicket.of(ticket)


@router.post(
    "/images/confirm",
    response_model=ImageAssetPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_edit), Depends(rate_limit("media-confirm", CONFIRM_QUOTA))],
)
def image_confirm(
    body: ImageConfirm,
    db: Session = Depends(get_db),
) -> ImageAssetPublic:
    existing = db.query(ImageAsset).filter(ImageAsset.storage_key == body.storage_key).one_or_none()
    if existing is not None:
        # Gọi lại bước 4 cho cùng một khoá là chuyện bình thường — mạng chập
        # chờn, người dùng bấm hai lần. Trả về hàng đã có thay vì 409: thao tác
        # đã thành công rồi, và báo lỗi ở đây chỉ khiến người ta upload lại.
        return _asset_public(existing)

    try:
        stored = get_driver("image").verify(body.storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None

    if stored.width is None or stored.height is None:
        # `image_asset` bắt buộc có kích thước (CHECK width > 0 AND height > 0).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kho lưu trữ không trả về kích thước ảnh.",
        )

    asset = ImageAsset(
        storage_key=body.storage_key,
        # Suy từ khoá, nên hàng và file luôn nối được với nhau mà không cần lưu
        # thêm id của nhà cung cấp (ADR-006 §2.5).
        source_hash=body.storage_key.rsplit("/", 1)[-1].rsplit(".", 1)[0],
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        width=stored.width,
        height=stored.height,
        source="uploaded",
        source_url=body.source_url,
        license=body.license,
        attribution=body.attribution,
        alt_text=body.alt_text,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_public(asset)


# --- nhận file ở môi trường dev ---------------------------------------------


# Router RIÊNG, và `app/main.py` chỉ gắn nó khi environment == "development" —
# cùng luật với mount `/media`. Ở production không có route này: file đi thẳng
# tới nhà cung cấp và không byte nào chạy qua FastAPI (ADR-006 §2.3).
@router.post(
    "/audio/requests",
    response_model=AudioRequestAck,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(can_edit)],
)
def request_audio(client: redis.Redis = Depends(get_redis)) -> AudioRequestAck:
    """Đánh chuông cho worker TTS. **Không** sinh audio ở đây (ADR-007 §2.7b).

    202 chứ không 200, và đó là điều duy nhất cần hiểu về endpoint này: nó
    KHÔNG hứa audio đã có. API không sinh audio được — không import được
    `app.content` (A4.1), ảnh production không có edge-tts lẫn ffmpeg.

    Không ghi bảng nào. Hàng đợi vẫn là *câu hỏi* "nội dung nào thiếu audio",
    nên bấm mười lần cũng không tạo ra mười job — worker chỉ hỏi lại database
    sớm hơn.

    Chuông không kêu (Redis chết) vẫn trả 202, chỉ khác `queued`. Vòng quét định
    kỳ vẫn bắt được việc; nói dối rằng thất bại sẽ khiến biên tập viên bấm lại
    một thứ vốn đã sẽ chạy.
    """
    return AudioRequestAck(queued=ring(client))


local_upload_router = APIRouter(tags=["media"])


@local_upload_router.post(LOCAL_UPLOAD_PATH + "/{storage_key:path}")
async def local_upload(
    storage_key: str,
    expires_at: Annotated[int, Form()],
    signature: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, object]:
    """Đứng thay nhà cung cấp khi chạy local.

    Nhận đúng hình dạng multipart mà Cloudinary nhận, nên mã frontend không phải
    rẽ nhánh theo môi trường — và do đó đường đi được dùng ở dev chính là đường
    đi được kiểm ở production, chứ không phải một bản mô phỏng gần giống.

    Không kèm `Depends(get_current_user)`: quyền đã nằm trong chữ ký của vé, và
    vé chỉ cấp cho `editor`/`admin`. Đó cũng là cách nhà cung cấp thật hoạt động
    — họ không biết gì về phiên đăng nhập của ta.
    """
    from app.core.config import settings

    if not local_signature_valid(storage_key, expires_at, signature, settings.secret_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Vé upload không hợp lệ hoặc đã hết hạn"
        )

    driver = get_driver("image")
    if not isinstance(driver, LocalDiskDriver):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không dùng kho lưu trữ local"
        )

    payload = await file.read()
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File vượt quá {MAX_IMAGE_BYTES} byte",
        )

    driver.write(storage_key, payload)
    return {"storage_key": storage_key, "bytes": len(payload)}


@router.post(
    "/audio/ticket",
    response_model=UploadTicket,
    dependencies=[Depends(can_edit), Depends(rate_limit("media-ticket", TICKET_QUOTA))],
)
def audio_ticket(body: AudioTicketRequest) -> UploadTicket:
    """Vé upload cho audio. Khoá do phía ta sinh, y như đường ảnh."""
    source_hash = upload_source_hash(str(uuid.uuid4()))
    return UploadTicket.of(get_driver("audio").ticket(storage_key_for(source_hash, ext=body.ext)))


@router.post(
    "/audio/confirm",
    response_model=AudioAssetPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_edit), Depends(rate_limit("media-confirm", CONFIRM_QUOTA))],
)
def audio_confirm(body: AudioConfirm, db: Session = Depends(get_db)) -> AudioAssetPublic:
    existing = db.query(AudioAsset).filter(AudioAsset.storage_key == body.storage_key).one_or_none()
    if existing is not None:
        # Gọi lại cho cùng một khoá là chuyện bình thường — mạng chập chờn,
        # người dùng bấm hai lần. Trả hàng đã có thay vì 409.
        return _audio_public(existing)

    if body.accent not in AUDIO_ACCENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Accent phải là một trong {list(AUDIO_ACCENTS)}",
        )
    if body.duration_ms <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Độ dài clip phải lớn hơn 0"
        )

    try:
        stored = get_driver("audio").verify(body.storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None

    asset = AudioAsset(
        storage_key=body.storage_key,
        source_hash=body.storage_key.rsplit("/", 1)[-1].rsplit(".", 1)[0],
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        duration_ms=body.duration_ms,
        # `uploaded`, không phải `tts`. Đây là chỗ hai đường phân biệt nhau, và
        # nó quyết định `media_state` có xác minh được clip hay không: hash của
        # file tải lên băm một id ngẫu nhiên, nên không suy ngược ra text được
        # (ADR-007 §2.7).
        source="uploaded",
        engine="upload",
        engine_version="1",
        voice=body.voice,
        accent=body.accent,
        source_text=None,
    )
    db.add(asset)
    db.commit()
    return _audio_public(asset)


def _audio_public(asset: AudioAsset) -> AudioAssetPublic:
    return AudioAssetPublic(
        id=str(asset.id),
        storage_key=asset.storage_key,
        url=public_audio_url(asset.storage_key),
        duration_ms=asset.duration_ms,
        accent=asset.accent,
        voice=asset.voice,
    )
