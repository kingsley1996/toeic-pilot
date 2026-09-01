"""Nơi file thật sự nằm, và cách trình duyệt đưa được file lên đó.

Nằm ở `core/` chứ không phải `content/`, và đây là ràng buộc chứ không phải sở
thích: `app/content/**` nằm sau extra `content`, còn ảnh production được build
`--no-dev` không kèm extra đó. Code chạy lúc có request mà đặt nhầm vào đấy sẽ
làm container không khởi động được, và `tests/test_content_isolation.py` bắt
đúng lỗi này trong một giây.

Quyết định đầy đủ: `planning/adr/ADR-006-MEDIA-UPLOAD.md`. Ba điều dễ phá nhất:

  §2.3  File KHÔNG đi qua FastAPI, cả chiều lên lẫn chiều xuống.
  §2.3  Bước xác nhận phải hỏi lại nhà cung cấp, không tin lời trình duyệt.
  §2.5  `storage_key` là nguồn sự thật; id của nhà cung cấp thì không.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

MediaKind = Literal["image", "audio"]

# Định dạng được nhận, theo từng loại.
#
# SVG KHÔNG có trong danh sách và sẽ không bao giờ có. Nó là XML có thể chứa
# `<script>`, nên phục vụ một file SVG do người dùng tải lên từ cùng origin là
# một lỗ XSS — "ảnh" ở đây là tên gọi, không phải bảo đảm về nội dung.
ALLOWED_IMAGE_FORMATS = ("jpg", "jpeg", "png", "webp")
ALLOWED_AUDIO_FORMATS = ("mp3", "m4a", "wav")

# Trần dung lượng. Ghim vào chữ ký chứ không kiểm sau khi lưu: kiểm sau nghĩa là
# file đã nằm trên đĩa của nhà cung cấp và đã tính tiền rồi.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Hạn dùng của một vé upload. Ngắn có chủ ý — vé bị lộ chỉ dùng được trong vài
# phút, mà người dùng thật thì bấm chọn file xong là tải lên ngay.
TICKET_TTL_SECONDS = 600

# Cạnh dài tối đa sau khi chuẩn hoá. Áp ở incoming transformation, tức là trước
# khi file được lưu, nên ảnh 40 megapixel không bao giờ chiếm chỗ.
MAX_IMAGE_EDGE = 2000


class StorageError(RuntimeError):
    """Nhà cung cấp từ chối, hoặc trả về thứ không dùng được."""


@dataclass(frozen=True)
class UploadTicket:
    """Thứ trình duyệt cần để tự tải file lên, không đi qua API."""

    upload_url: str
    # Các trường đi kèm trong multipart form. Với Cloudinary đây là chữ ký và
    # mọi tham số đã được ký; đổi bất kỳ giá trị nào cũng làm chữ ký hỏng.
    #
    # Với `method="PUT"` thì đây là các HEADER trình duyệt bắt buộc phải gửi,
    # không phải trường form — và chúng cũng đã nằm trong chữ ký, nên gửi thiếu
    # hoặc gửi khác đều bị nhà cung cấp trả 403.
    fields: dict[str, str]
    storage_key: str
    max_bytes: int
    allowed_formats: tuple[str, ...]
    expires_at: int
    # Cloudinary và driver local nhận multipart POST; object store kiểu S3 nhận
    # PUT thẳng vào URL đã ký. Frontend phải đọc trường này chứ không đoán theo
    # môi trường, vì cùng một môi trường có thể chạy hai nhà cung cấp khác nhau
    # cho ảnh và cho audio (§2.2).
    method: Literal["POST", "PUT"] = "POST"


@dataclass(frozen=True)
class StoredObject:
    """Thứ nhà cung cấp xác nhận là đang thật sự nằm ở đó."""

    storage_key: str
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None


class StorageDriver(Protocol):
    """Một nơi chứa file.

    Cố ý nhỏ. Mọi thứ đặc thù của nhà cung cấp phải nằm sau bốn phương thức này,
    vì đó là điều khiến §2.2 (ảnh một nơi, audio một nơi khác) chỉ là cấu hình
    chứ không phải một nhánh `if` rải khắp codebase.
    """

    kind: MediaKind

    def ticket(self, storage_key: str) -> UploadTicket: ...

    def verify(self, storage_key: str) -> StoredObject: ...

    def delete(self, storage_key: str) -> None: ...

    def public_url(self, storage_key: str) -> str: ...


# --- driver đĩa local -------------------------------------------------------


def sign_local_key(storage_key: str, expires_at: int, secret: str) -> str:
    """Chữ ký của vé upload local.

    Dev không có nhà cung cấp để ký, nhưng vé vẫn phải ký — nếu không thì luồng
    ở môi trường dev khác luồng ở production đúng tại chỗ dễ sai nhất, và lỗi
    phân quyền sẽ chỉ lộ ra sau khi đã deploy.
    """
    message = f"{storage_key}\x1f{expires_at}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def local_signature_valid(storage_key: str, expires_at: int, signature: str, secret: str) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = sign_local_key(storage_key, expires_at, secret)
    # `compare_digest`, không phải `==`: so sánh chuỗi thường thoát ra sớm ở byte
    # đầu tiên khác nhau, và thời gian đó đo được.
    return hmac.compare_digest(expected, signature)


def read_dimensions(payload: bytes) -> tuple[int, int] | None:
    """Đọc kích thước từ header ảnh, thuần stdlib.

    Tồn tại vì driver local phải điền được `image_asset.width/height` (NOT NULL,
    kèm CHECK > 0) mà không có Pillow — Pillow nằm sau extra `content`, và kéo
    nó vào dependency runtime chỉ để phục vụ một đường dành cho dev là đắt hơn
    nhiều so với ba chục dòng này.

    Điền số giả thì rẻ hơn nữa và sai: kích thước là thứ giao diện dùng để đặt
    khung ảnh, nên một con số bịa sẽ làm vỡ bố cục ở một trang khác, rất xa chỗ
    nó được ghi vào.

    Trả `None` khi không nhận ra — nơi gọi phải coi đó là lỗi, không phải 0.
    """
    if payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) >= 24:
        return (
            int.from_bytes(payload[16:20], "big"),
            int.from_bytes(payload[20:24], "big"),
        )

    if payload.startswith(b"\xff\xd8"):
        # Duyệt qua các marker tới khung SOF. Không thể đọc ở offset cố định:
        # số lượng và độ dài các đoạn APPn/DQT trước SOF thay đổi theo từng máy
        # ảnh và từng phần mềm đã lưu lại file.
        index = 2
        while index + 9 < len(payload):
            if payload[index] != 0xFF:
                index += 1
                continue
            marker = payload[index + 1]
            # C4 = bảng Huffman, C8 = mở rộng JPEG, CC = bảng số học — ba cái
            # này nằm trong dải 0xC0–0xCF nhưng KHÔNG phải khung SOF.
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height = int.from_bytes(payload[index + 5 : index + 7], "big")
                width = int.from_bytes(payload[index + 7 : index + 9], "big")
                return (width, height) if width and height else None
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            index += 2 + int.from_bytes(payload[index + 2 : index + 4], "big")
        return None

    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP" and len(payload) >= 30:
        chunk = payload[12:16]
        if chunk == b"VP8 ":
            return (
                int.from_bytes(payload[26:28], "little") & 0x3FFF,
                int.from_bytes(payload[28:30], "little") & 0x3FFF,
            )
        if chunk == b"VP8L":
            bits = int.from_bytes(payload[21:25], "little")
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        if chunk == b"VP8X":
            return (
                int.from_bytes(payload[24:27], "little") + 1,
                int.from_bytes(payload[27:30], "little") + 1,
            )
    return None


@dataclass
class LocalDiskDriver:
    """Ghi thẳng xuống `media_root`. Chỉ dùng cho dev và test.

    Giữ đúng hình dạng bốn bước của ADR §2.3 — xin vé, tải lên, xác nhận, ghi
    hàng — để mã frontend không phải rẽ nhánh theo môi trường. Điểm khác duy
    nhất là "nhà cung cấp" ở đây là một route chỉ được gắn khi
    `environment == "development"`, đúng như `/media` hiện nay.
    """

    kind: MediaKind
    root: Path
    base_url: str
    upload_endpoint: str
    secret: str

    def ticket(self, storage_key: str) -> UploadTicket:
        expires_at = int(time.time()) + TICKET_TTL_SECONDS
        return UploadTicket(
            upload_url=f"{self.upload_endpoint.rstrip('/')}/{storage_key.lstrip('/')}",
            fields={
                "expires_at": str(expires_at),
                "signature": sign_local_key(storage_key, expires_at, self.secret),
            },
            storage_key=storage_key,
            max_bytes=_max_bytes(self.kind),
            allowed_formats=_allowed_formats(self.kind),
            expires_at=expires_at,
        )

    def _path(self, storage_key: str) -> Path:
        # `storage_key` do phía ta sinh ra từ hash, nhưng nó cũng đi qua request
        # ở bước xác nhận. Chặn `..` ở đây chứ không tin vào nơi gọi.
        candidate = (self.root / storage_key).resolve()
        if not candidate.is_relative_to(self.root.resolve()):
            raise StorageError(f"Storage key escapes the media root: {storage_key}")
        return candidate

    def verify(self, storage_key: str) -> StoredObject:
        path = self._path(storage_key)
        if not path.is_file():
            raise StorageError(f"No object at {storage_key}")
        payload = path.read_bytes()
        dimensions = read_dimensions(payload) if self.kind == "image" else None
        return StoredObject(
            storage_key=storage_key,
            mime_type=guess_mime(storage_key),
            size_bytes=len(payload),
            width=dimensions[0] if dimensions else None,
            height=dimensions[1] if dimensions else None,
        )

    def delete(self, storage_key: str) -> None:
        self._path(storage_key).unlink(missing_ok=True)

    def write(self, storage_key: str, payload: bytes) -> None:
        """Chỉ driver local mới có. Không nằm trong `StorageDriver`.

        Nhà cung cấp thật không bao giờ nhận byte từ tiến trình này — đó là toàn
        bộ ý nghĩa của §2.3. Đưa `write` vào giao diện chung sẽ biến một đường
        chỉ dành cho dev thành một thứ trông như dùng được ở mọi nơi.
        """
        target = self._path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    def public_url(self, storage_key: str) -> str:
        return f"{self.base_url.rstrip('/')}/{storage_key.lstrip('/')}"


# --- driver Cloudinary (ảnh) ------------------------------------------------


@dataclass
class CloudinaryDriver:
    """Upload ký trực tiếp từ trình duyệt lên Cloudinary.

    Chữ ký ghim thư mục, `public_id`, định dạng cho phép và phép biến đổi đầu
    vào. Đó là điểm mấu chốt của §2.4: ký một request tự do là ký séc trắng, và
    upload preset KHÔNG ký thì cho phép bất kỳ ai trên Internet tải file vào tài
    khoản của bạn.
    """

    kind: MediaKind
    cloud_name: str
    api_key: str
    api_secret: str
    folder: str
    base_url: str
    timeout_seconds: float = 10.0
    resource_type: str = field(default="image")

    def _signature(self, params: dict[str, str]) -> str:
        # Cloudinary ký chuỗi "k=v&k=v" đã sắp theo alphabet, nối api_secret vào
        # cuối, rồi SHA-1. `file`, `api_key`, `cloud_name` và `resource_type`
        # không nằm trong chuỗi ký.
        payload = "&".join(f"{key}={params[key]}" for key in sorted(params))
        return hashlib.sha1(f"{payload}{self.api_secret}".encode()).hexdigest()  # noqa: S324

    def _signed_params(self, storage_key: str, timestamp: int) -> dict[str, str]:
        """Ràng buộc được ký, dùng chung cho CẢ hai đường lên Cloudinary.

        Một hàm chứ không hai bản sao: đường trình duyệt (`ticket`) và đường
        công cụ offline (`upload_file`) phải tạo ra object giống hệt nhau. Nếu
        chúng khai khác nhau — khác `transformation`, khác `allowed_formats` —
        thì ảnh do biên tập viên tải lên và ảnh do đường ống lấy về sẽ được xử
        lý khác nhau, mà không có gì trong hệ thống nói ra điều đó.
        """
        return {
            "timestamp": str(timestamp),
            # KHÔNG gửi `folder`. Gửi nó thì Cloudinary tự ghép thư mục vào
            # trước `public_id` ở tài khoản dùng chế độ thư mục cố định, nhưng
            # KHÔNG ghép ở tài khoản dùng chế độ thư mục động — nên id thật của
            # object sẽ khác nhau tuỳ thiết lập của tài khoản, và mọi lần tra
            # cứu về sau thành trò may rủi. Đưa thư mục vào thẳng `public_id`
            # thì id là thứ ta tự quyết, giống nhau ở mọi chế độ.
            #
            # Phát hiện khi chạy thử thật: bản đầu gửi `folder` riêng, upload
            # trả 200 nhưng `verify()` 404 vì tra cứu bằng id không có tiền tố.
            "public_id": self._remote_id(storage_key),
            "allowed_formats": ",".join(_allowed_formats(self.kind)),
            # Chuẩn hoá TRƯỚC khi lưu: giới hạn cạnh dài, và `fl_strip_profile`
            # tước EXIF — thứ mang theo toạ độ GPS của nơi bức ảnh được chụp.
            "transformation": (
                f"c_limit,w_{MAX_IMAGE_EDGE},h_{MAX_IMAGE_EDGE},q_auto/fl_strip_profile"
            ),
            "overwrite": "false",
        }

    @property
    def _upload_url(self) -> str:
        return f"https://api.cloudinary.com/v1_1/{self.cloud_name}/{self.resource_type}/upload"

    def ticket(self, storage_key: str) -> UploadTicket:
        timestamp = int(time.time())
        signed = self._signed_params(storage_key, timestamp)
        return UploadTicket(
            upload_url=self._upload_url,
            fields={**signed, "api_key": self.api_key, "signature": self._signature(signed)},
            storage_key=storage_key,
            max_bytes=_max_bytes(self.kind),
            allowed_formats=_allowed_formats(self.kind),
            expires_at=timestamp + TICKET_TTL_SECONDS,
        )

    def verify(self, storage_key: str) -> StoredObject:
        """Hỏi lại Cloudinary xem object đó có thật không, và thật ra là gì.

        Bước này KHÔNG được bỏ (§2.3). Endpoint xác nhận nhận `storage_key` từ
        trình duyệt, và ai cũng gọi được nó với một khoá bịa ra — không hỏi lại
        thì đó là một đường ghi hàng asset tuỳ ý vào database, trỏ tới file
        không tồn tại.
        """
        url = (
            f"https://api.cloudinary.com/v1_1/{self.cloud_name}"
            f"/resources/{self.resource_type}/upload/{self._remote_id(storage_key)}"
        )
        try:
            response = httpx.get(
                url, auth=(self.api_key, self.api_secret), timeout=self.timeout_seconds
            )
        except httpx.HTTPError as error:
            raise StorageError(f"Cloudinary unreachable: {error}") from error
        if response.status_code == 404:
            raise StorageError(f"No object at {storage_key}")
        if response.status_code >= 400:
            raise StorageError(f"Cloudinary refused the lookup: {response.status_code}")

        body = response.json()
        return StoredObject(
            storage_key=storage_key,
            # Qua bảng tra, không phải `f"image/{format}"`: Cloudinary trả
            # `format: "jpg"`, mà `image/jpg` KHÔNG phải MIME type có thật —
            # tên đúng là `image/jpeg`. Ghi giá trị bịa vào `mime_type` thì
            # trình duyệt nào chặt chẽ về Content-Type sẽ từ chối, và lỗi đó
            # xuất hiện rất xa chỗ sinh ra nó.
            mime_type=_MIME_BY_EXT.get(str(body.get("format", "")).lower(), "image/jpeg"),
            size_bytes=int(body.get("bytes", 0)),
            width=body.get("width"),
            height=body.get("height"),
        )

    def delete(self, storage_key: str) -> None:
        timestamp = int(time.time())
        signed = {"public_id": self._remote_id(storage_key), "timestamp": str(timestamp)}
        try:
            httpx.post(
                f"https://api.cloudinary.com/v1_1/{self.cloud_name}/{self.resource_type}/destroy",
                data={
                    **signed,
                    "api_key": self.api_key,
                    "signature": self._signature(signed),
                },
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as error:
            raise StorageError(f"Cloudinary unreachable: {error}") from error

    def upload_file(self, storage_key: str, path: Path) -> None:
        """Đẩy một file từ đĩa lên Cloudinary. **Chỉ dành cho công cụ offline.**

        Không nằm trong `StorageDriver`, cùng lý do với `LocalDiskDriver.write`:
        §2.3 nói byte không bao giờ đi qua FastAPI, và đưa một đường ghi byte
        vào giao diện chung sẽ biến thứ chỉ dùng ở `app/content/**` thành thứ
        trông như gọi được từ một request handler.

        Nó tồn tại vì ADR-004 vẫn còn hiệu lực: `app/content/images.py` lấy ảnh
        CC về đĩa, và nếu không có đường này thì mọi ảnh nó lấy về đều không
        bao giờ tới được production — đường duy nhất còn lại là biên tập viên
        tự tải từng tấm qua màn quản trị, đúng thứ ADR-004 dựng ra để tránh.
        """
        timestamp = int(time.time())
        signed = self._signed_params(storage_key, timestamp)
        try:
            response = httpx.post(
                self._upload_url,
                data={**signed, "api_key": self.api_key, "signature": self._signature(signed)},
                files={"file": (path.name, path.read_bytes(), guess_mime(storage_key))},
                timeout=self.timeout_seconds * 6,
            )
        except httpx.HTTPError as error:
            raise StorageError(f"Cloudinary unreachable: {error}") from error
        if response.status_code >= 400:
            raise StorageError(
                f"Cloudinary từ chối upload: {response.status_code} {response.text[:200]}"
            )

    def _remote_id(self, storage_key: str) -> str:
        """Id của object bên Cloudinary: thư mục + khoá, đã bỏ phần mở rộng.

        Suy ra hoàn toàn từ `storage_key`, nên §2.5 vẫn đứng: `storage_key` là
        nguồn sự thật, còn id của nhà cung cấp chỉ là một hàm của nó.
        """
        return f"{self.folder.strip('/')}/{_public_id(storage_key)}"

    def public_url(self, storage_key: str) -> str:
        # Phần mở rộng phải có: URL phân phối không đuôi vẫn chạy nhưng trả về
        # định dạng gốc, bỏ mất phần chuyển đổi mà ta đã trả tiền để làm.
        # Không kèm `v<version>` — nó chỉ dùng để phá cache, và `overwrite=false`
        # nghĩa là một khoá luôn trỏ tới đúng một file.
        return f"{self.base_url.rstrip('/')}/{self.folder.strip('/')}/{storage_key.lstrip('/')}"


# --- driver S3 (mọi object store nói giao thức S3) ---------------------------


@dataclass
class S3Driver:
    """Supabase Storage, Backblaze B2, R2, DO Spaces, Wasabi, MinIO — một driver.

    Cố ý KHÔNG mang tên nhà cung cấp. Bản đầu của ADR-006 gọi nó là "driver R2",
    và cái tên đó đóng băng một quyết định thương mại vào mã nguồn: đổi nhà cung
    cấp hoá ra phải sửa code, trong khi thứ thật sự khác nhau chỉ là một endpoint
    và một cặp khoá. Ở đây nhà cung cấp là **giá trị cấu hình**.

    Hai chi tiết bắt buộc, cả hai đều hỏng theo kiểu khó truy nếu làm sai:

    - **Địa chỉ kiểu đường dẫn.** Mặc định của boto3 là kiểu virtual-host, tức
      ghép bucket thành `<bucket>.<host>`. Đúng với AWS, sai với Supabase
      (`<ref>.supabase.co/storage/v1/s3`) và MinIO, nơi bucket là một đoạn
      đường dẫn. Triệu chứng khi sai không phải "cấu hình sai" mà là **DNS
      không phân giải được** — nên người ta đi kiểm mạng thay vì kiểm cấu hình.
    - **SigV4.** Supabase từ chối các phiên bản chữ ký cũ hơn.
    """

    kind: MediaKind
    endpoint_url: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    base_url: str
    # Dựng ở lần dùng đầu tiên, không phải lúc import: một triển khai chỉ dùng
    # Cloudinary cho ảnh không nên trả giá khởi động cho một driver nó không gọi.
    _client: Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        return self._client

    def ticket(self, storage_key: str) -> UploadTicket:
        """URL PUT đã ký, hạn dùng ngắn, ghim sẵn khoá và Content-Type.

        Một chỗ yếu hơn Cloudinary phải nói thẳng ra: **presigned PUT không mang
        được `content-length-range`** như policy của form POST, nên chữ ký này
        KHÔNG chặn được file quá cỡ. Trần dung lượng vì thế được áp ở hai nơi
        khác — giới hạn kích thước của chính bucket (đặt ở bảng điều khiển nhà
        cung cấp, và đó là hàng rào thật sự), cộng với `verify()` bên dưới, chỗ
        file quá cỡ bị xoá chứ không chỉ bị từ chối.
        """
        expires_at = int(time.time()) + TICKET_TTL_SECONDS
        mime = guess_mime(storage_key)
        try:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": storage_key, "ContentType": mime},
                ExpiresIn=TICKET_TTL_SECONDS,
                HttpMethod="PUT",
            )
        except Exception as error:  # botocore gói lỗi cấu hình vào nhiều lớp
            raise StorageError(f"Không ký được vé upload: {error}") from error
        return UploadTicket(
            upload_url=str(url),
            fields={"Content-Type": mime},
            storage_key=storage_key,
            max_bytes=_max_bytes(self.kind),
            allowed_formats=_allowed_formats(self.kind),
            expires_at=expires_at,
            method="PUT",
        )

    def verify(self, storage_key: str) -> StoredObject:
        """Hỏi lại object store, đúng như §2.3 yêu cầu — không tin lời trình duyệt."""
        head = self._head(storage_key)
        size_bytes = int(head.get("ContentLength", 0))

        # File quá cỡ bị XOÁ, không chỉ bị từ chối. Từ chối suông để lại một
        # object không ai tham chiếu tới nhưng vẫn tính tiền hàng tháng — đúng
        # thứ file mồ côi mà ADR-006 §4 đã ghi là chưa có đường dọn.
        if size_bytes > _max_bytes(self.kind):
            self.delete(storage_key)
            raise StorageError(
                f"Object vượt trần {_max_bytes(self.kind)} byte và đã bị xoá: {storage_key}"
            )

        width = height = None
        if self.kind == "image":
            # Kích thước ảnh không có trong HEAD, nên đọc phần đầu file và tự
            # phân tích header — cùng `read_dimensions` mà driver local dùng,
            # nên hai đường cho ra cùng một con số. Lấy 64 KB đầu là dư: header
            # PNG/JPEG/WebP nằm trong vài trăm byte đầu tiên.
            dimensions = read_dimensions(self._head_bytes(storage_key))
            if dimensions:
                width, height = dimensions

        return StoredObject(
            storage_key=storage_key,
            # Không tin `ContentType` do người upload khai: nó là thứ trình duyệt
            # gửi lên, còn đuôi file thì do `storage_key` quyết định, mà khoá đó
            # là của ta (§2.5).
            mime_type=guess_mime(storage_key),
            size_bytes=size_bytes,
            width=width,
            height=height,
        )

    def delete(self, storage_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_key)
        except Exception as error:
            raise StorageError(f"Object store từ chối lệnh xoá: {error}") from error

    def public_url(self, storage_key: str) -> str:
        # Nối chuỗi, y như driver local. Runtime KHÔNG BAO GIỜ gọi object store
        # để dựng URL phát — đó là điều khiến audio không phải đi qua FastAPI.
        return f"{self.base_url.rstrip('/')}/{storage_key.lstrip('/')}"

    def upload_file(self, storage_key: str, path: Path) -> None:
        """Đẩy một file từ đĩa lên object store. **Chỉ dành cho công cụ offline.**

        Cùng lý do với `CloudinaryDriver.upload_file` và `LocalDiskDriver.write`:
        không nằm trong `StorageDriver`, vì §2.3 nói byte không đi qua FastAPI.
        """
        try:
            self.client.upload_file(
                str(path),
                self.bucket,
                storage_key,
                ExtraArgs={
                    "ContentType": guess_mime(storage_key),
                    # Khoá là địa chỉ nội dung, nên một khoá luôn trỏ tới đúng
                    # một file không bao giờ đổi — điều kiện để nói với CDN rằng
                    # nó được giữ mãi. Với hạn mức egress của gói free thì đây
                    # không phải tinh chỉnh.
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
        except Exception as error:
            raise StorageError(f"Không đẩy được {storage_key}: {error}") from error

    def _head(self, storage_key: str) -> dict[str, Any]:
        from botocore.exceptions import ClientError

        try:
            return dict(self.client.head_object(Bucket=self.bucket, Key=storage_key))
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status in (403, 404):
                # 403 cũng gộp vào đây: bucket riêng tư trả 403 thay vì 404 cho
                # khoá không tồn tại, để không tiết lộ khoá nào có thật.
                raise StorageError(f"No object at {storage_key}") from error
            raise StorageError(f"Object store từ chối tra cứu: {error}") from error
        except Exception as error:
            raise StorageError(f"Object store không truy cập được: {error}") from error

    def _head_bytes(self, storage_key: str, length: int = 65_536) -> bytes:
        try:
            response = self.client.get_object(
                Bucket=self.bucket, Key=storage_key, Range=f"bytes=0-{length - 1}"
            )
            return bytes(response["Body"].read())
        except Exception as error:
            raise StorageError(f"Không đọc được phần đầu của {storage_key}: {error}") from error


# --- dùng chung -------------------------------------------------------------


def _public_id(storage_key: str) -> str:
    """`image/ab12….jpg` -> `image/ab12…`.

    Cloudinary tự gắn phần mở rộng theo định dạng thật của file, nên `public_id`
    mang sẵn đuôi sẽ cho ra `…jpg.jpg`.
    """
    return storage_key.rsplit(".", 1)[0]


def _allowed_formats(kind: MediaKind) -> tuple[str, ...]:
    return ALLOWED_IMAGE_FORMATS if kind == "image" else ALLOWED_AUDIO_FORMATS


def _max_bytes(kind: MediaKind) -> int:
    return MAX_IMAGE_BYTES if kind == "image" else MAX_AUDIO_BYTES


_MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
}


def guess_mime(storage_key: str) -> str:
    ext = storage_key.rsplit(".", 1)[-1].lower()
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


# --- chọn driver ------------------------------------------------------------

# Đường mà driver local dùng làm "nhà cung cấp". Chỉ được gắn khi
# `environment == "development"`, cùng luật với mount `/media`.
LOCAL_UPLOAD_PATH = "/media-upload"


def get_driver(kind: MediaKind) -> StorageDriver:
    """Driver đang cấu hình cho loại media này.

    Đọc `settings` tại thời điểm gọi chứ không dựng sẵn ở tầng module: test cần
    trỏ sang thư mục tạm mà không phải nạp lại cả module, và ảnh production thì
    không bao giờ dùng nhánh local.
    """
    from app.core.config import settings

    driver = (
        settings.image_storage_driver if kind == "image" else settings.audio_storage_driver
    ).lower()

    if driver == "cloudinary":
        if kind != "image":
            # Cloudinary xử lý audio dưới `resource_type=video`, nhưng ADR-006
            # §2.2 chọn KHÔNG đi đường đó: audio là bài toán băng thông, và băng
            # thông ở đây ăn chung hạn mức credit với ảnh.
            raise StorageError("Cloudinary is configured for images only (ADR-006 §2.2)")
        return CloudinaryDriver(
            kind=kind,
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret.get_secret_value(),
            folder=settings.cloudinary_folder,
            base_url=settings.image_public_base_url,
        )

    if driver == "s3":
        return S3Driver(
            kind=kind,
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            base_url=(
                settings.image_public_base_url
                if kind == "image"
                else settings.audio_public_base_url
            ),
        )

    if driver != "local":
        raise StorageError(f"Unknown storage driver: {driver}")

    return LocalDiskDriver(
        kind=kind,
        root=settings.media_root,
        base_url=(
            settings.image_public_base_url if kind == "image" else settings.audio_public_base_url
        ),
        upload_endpoint=LOCAL_UPLOAD_PATH,
        secret=settings.secret_key,
    )
