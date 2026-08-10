from typing import Literal

from pydantic import BaseModel, Field

from app.core.storage import ALLOWED_IMAGE_FORMATS
from app.core.storage import UploadTicket as DriverTicket

ImageExtension = Literal["jpg", "jpeg", "png", "webp"]


class UploadTicketRequest(BaseModel):
    # Phần mở rộng do client khai, nhưng KHÔNG được tin: nó chỉ dùng để đặt tên
    # khoá. Định dạng thật của file được nhà cung cấp báo lại ở bước xác nhận, và
    # `allowed_formats` trong chữ ký mới là thứ thật sự chặn.
    ext: ImageExtension = "jpg"


class UploadTicket(BaseModel):
    """Vé để trình duyệt tự tải file lên, không đi qua API (ADR-006 §2.3)."""

    upload_url: str
    fields: dict[str, str]
    storage_key: str
    max_bytes: int
    allowed_formats: list[str]
    expires_at: int
    # Cloudinary và driver local nhận multipart POST; object store S3 nhận PUT
    # thẳng vào URL đã ký, và khi đó `fields` là các header bắt buộc chứ không
    # phải trường form. Frontend phải đọc trường này thay vì đoán theo môi
    # trường — cùng một môi trường có thể chạy hai nhà cung cấp khác nhau cho
    # ảnh và cho audio (§2.2).
    method: Literal["POST", "PUT"] = "POST"

    @classmethod
    def of(cls, ticket: DriverTicket) -> "UploadTicket":
        """Chuyển vé của driver thành vé trên dây.

        Là một classmethod chứ không phải sáu dòng gán lặp ở mỗi route, vì kiểu
        hỏng của bản lặp đã xảy ra thật: thêm `method` vào driver mà quên sửa
        một trong hai route thì route đó im lặng phát vé POST cho một URL PUT,
        và lỗi chỉ hiện ra ở nhà cung cấp dưới dạng 403.
        """
        return cls(
            upload_url=ticket.upload_url,
            fields=ticket.fields,
            storage_key=ticket.storage_key,
            max_bytes=ticket.max_bytes,
            allowed_formats=list(ticket.allowed_formats),
            expires_at=ticket.expires_at,
            method=ticket.method,
        )


class ImageConfirm(BaseModel):
    """Bước 4: báo đã tải xong, kèm thông tin bản quyền.

    Ba trường bản quyền là **bắt buộc**, khớp với ba cột NOT NULL trên
    `image_asset`. ADR-004 §2 nêu lý do: phần lớn ảnh mở là CC-BY — được dùng
    *với điều kiện* ghi công — và thông tin đó chỉ ghi lại trung thực được vào
    đúng lúc người ta thêm ảnh, khi trang nguồn còn đang mở.

    Với ảnh tự chụp thì `source_url` là nơi giữ bản gốc và `license` ghi rõ là
    của mình; trường này không phải thủ tục, nó là câu trả lời cho "ai được phép
    dùng ảnh này".
    """

    storage_key: str
    source_url: str = Field(min_length=1, max_length=1024)
    license: str = Field(min_length=1, max_length=64)
    attribution: str = Field(min_length=1)
    # Cố ý KHÔNG phải đáp án: một chú thích tiết lộ câu nào đúng sẽ làm câu hỏi
    # mất giá trị với cả người sáng mắt lẫn người dùng trình đọc màn hình.
    alt_text: str | None = None


class ImageAssetPublic(BaseModel):
    id: str
    storage_key: str
    url: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    source: str
    source_url: str
    license: str
    attribution: str
    alt_text: str | None


ALLOWED_IMAGE_FORMAT_LIST = list(ALLOWED_IMAGE_FORMATS)
