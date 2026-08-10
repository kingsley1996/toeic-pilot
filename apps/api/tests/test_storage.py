import hashlib
import time
from pathlib import Path

import pytest

from app.core.storage import (
    ALLOWED_IMAGE_FORMATS,
    CloudinaryDriver,
    LocalDiskDriver,
    StorageError,
    local_signature_valid,
    read_dimensions,
)

SECRET = "test-secret"


def png(width: int, height: int) -> bytes:
    """Chỉ 24 byte đầu là có nghĩa — đó là tất cả những gì bộ đọc nhìn tới."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )


def local(tmp_path: Path) -> LocalDiskDriver:
    return LocalDiskDriver(
        kind="image",
        root=tmp_path,
        base_url="http://localhost:8000/media",
        upload_endpoint="/media-upload",
        secret=SECRET,
    )


def cloudinary() -> CloudinaryDriver:
    return CloudinaryDriver(
        kind="image",
        cloud_name="demo-cloud",
        api_key="123456789",
        api_secret="abc-secret",
        folder="toeic-pilot",
        base_url="https://res.cloudinary.com/demo-cloud/image/upload",
    )


def test_svg_is_never_an_allowed_image_format():
    """SVG là XML có thể chứa `<script>`.

    Phục vụ một file SVG người dùng tải lên từ cùng origin là một lỗ XSS. Test
    này tồn tại để việc thêm nó vào danh sách phải là hành động có ý thức.
    """
    assert "svg" not in ALLOWED_IMAGE_FORMATS


def test_a_ticket_only_opens_the_key_it_was_issued_for(tmp_path: Path):
    """Chữ ký phải bao gồm khoá VÀ hạn dùng.

    Thiếu khoá thì một vé hợp lệ mở được mọi đường ghi; thiếu hạn thì một vé lộ
    ra dùng được mãi mãi.
    """
    ticket = local(tmp_path).ticket("image/abc.jpg")
    expires_at = int(ticket.fields["expires_at"])
    signature = ticket.fields["signature"]

    assert local_signature_valid("image/abc.jpg", expires_at, signature, SECRET)
    assert not local_signature_valid("image/other.jpg", expires_at, signature, SECRET)
    assert not local_signature_valid("image/abc.jpg", int(time.time()) - 1, signature, SECRET)
    assert not local_signature_valid("image/abc.jpg", expires_at, signature, "another-secret")


def test_a_key_cannot_escape_the_media_root(tmp_path: Path):
    # `storage_key` do phía ta sinh ra, nhưng nó cũng đi qua request ở bước xác
    # nhận — nên nơi ghi file phải tự chặn, không tin vào nơi gọi.
    with pytest.raises(StorageError):
        local(tmp_path).verify("../../etc/passwd")


def test_verify_reads_the_file_that_is_actually_there(tmp_path: Path):
    driver = local(tmp_path)
    with pytest.raises(StorageError):
        driver.verify("image/missing.png")

    driver.write("image/abc.png", png(1200, 800))
    stored = driver.verify("image/abc.png")
    assert stored.mime_type == "image/png"
    assert (stored.width, stored.height) == (1200, 800)


def test_cloudinary_signature_matches_the_documented_recipe():
    """Chuỗi ký là "k=v&k=v" đã sắp alphabet, nối api_secret, rồi SHA-1.

    Tính lại bằng tay ở đây vì một chữ ký sai chỉ lộ ra khi Cloudinary trả 401
    giữa lúc ai đó đang tải file lên, và lúc đó không rõ tham số nào hỏng.
    """
    ticket = cloudinary().ticket("image/abc.jpg")
    signed = {k: v for k, v in ticket.fields.items() if k not in {"api_key", "signature"}}
    payload = "&".join(f"{key}={signed[key]}" for key in sorted(signed))

    assert (
        ticket.fields["signature"]
        == hashlib.sha1(  # noqa: S324
            f"{payload}abc-secret".encode()
        ).hexdigest()
    )
    # Bí mật không bao giờ rời máy chủ; `api_key` thì công khai được.
    assert "abc-secret" not in "".join(ticket.fields.values())


def test_the_ticket_pins_its_constraints():
    """Chữ ký GHIM ràng buộc, không ký séc trắng (ADR-006 §2.4).

    Thư mục nằm TRONG `public_id`, không gửi tham số `folder` riêng: gửi riêng
    thì Cloudinary ghép thư mục ở tài khoản chế độ cố định nhưng không ghép ở
    chế độ động, nên id thật khác nhau tuỳ thiết lập tài khoản. Đây là lỗi thật,
    tìm ra khi chạy lên tài khoản thật — upload trả 200 mà `verify()` trả 404
    (ADR-006 §2.4b).
    """
    driver = cloudinary()
    fields = driver.ticket("image/abc.jpg").fields

    assert "folder" not in fields
    assert fields["public_id"] == "toeic-pilot/image/abc"
    assert fields["allowed_formats"] == "jpg,jpeg,png,webp"
    # Giới hạn cạnh và tước EXIF xảy ra TRƯỚC khi lưu — EXIF của ảnh chụp bằng
    # điện thoại mang theo toạ độ GPS.
    assert "c_limit" in fields["transformation"]
    assert "fl_strip_profile" in fields["transformation"]
    # URL phân phối phải mang đuôi, `public_id` thì không.
    assert driver.public_url("image/abc.jpg").endswith("/toeic-pilot/image/abc.jpg")


def test_dimensions_come_from_the_header_or_not_at_all():
    """`None` chứ không phải `(0, 0)`.

    `image_asset` có CHECK `width > 0`, nên số 0 sẽ bị database chặn — nhưng
    chặn ở đó nghĩa là lỗi hiện ra dưới dạng IntegrityError 500 thay vì một câu
    400 nói rõ file không đọc được.
    """
    assert read_dimensions(png(1200, 800)) == (1200, 800)
    assert read_dimensions(b"not an image at all") is None
