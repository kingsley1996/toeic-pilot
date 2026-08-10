"""Đẩy media đã sinh sẵn ở máy lên object store.

    uv run python -m app.content.push_media [--dry-run] [--prefix audio]

Vì sao đây là một lệnh riêng chứ không phải luồng upload của ADR-006: **hai bài
toán khác nhau bị gọi chung một cái tên.**

- Audio sinh offline (toàn bộ nội dung hiện có) là bài toán **triển khai** —
  file đã nằm trên đĩa, việc còn lại là đồng bộ. Không cần vé, không cần chữ ký,
  không có trình duyệt nào tham gia.
- Audio do người thật thu và tải lên qua màn quản trị mới cần `ticket/verify`
  của §2.3, vì lúc đó byte đi từ một máy ta không kiểm soát.

Gộp hai thứ lại sẽ bắt đường đơn giản phải trả giá cho đường phức tạp. Lệnh này
chạy ở máy dev, sau `--extra content`, và **không bao giờ** chạy lúc có request —
cùng luật với `generate` và `images`.

Chạy lại là không tốn gì: khoá đã có ở đích với đúng dung lượng thì bỏ qua. Khoá
là content-addressed nên "đúng dung lượng" đã đủ chắc — nội dung khác thì hash
khác, mà hash khác thì khoá khác.
"""

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from app.content.settings import content_settings
from app.core.config import settings
from app.core.storage import S3Driver, StorageError, guess_mime

# Khoá là hash của đầu vào tổng hợp, nên một khoá luôn trỏ tới đúng một file và
# file đó không bao giờ đổi nội dung. Đó chính là điều kiện để nói với CDN rằng
# nó được giữ mãi — và với gói free 5 GB egress/tháng thì đây không phải tinh
# chỉnh, nó là khác biệt giữa "đủ dùng" và "hết hạn mức giữa tháng".
CACHE_CONTROL = "public, max-age=31536000, immutable"


def iter_local_objects(root: Path, prefixes: tuple[str, ...]) -> Iterator[tuple[str, Path]]:
    """(storage_key, đường dẫn thật) cho mọi file dưới các tiền tố đã chọn."""
    for prefix in prefixes:
        base = root / prefix
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                yield path.relative_to(root).as_posix(), path


def push(
    driver: S3Driver,
    objects: list[tuple[str, Path]],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    tally = {"uploaded": 0, "skipped": 0, "failed": 0}

    for storage_key, path in objects:
        local_size = path.stat().st_size
        try:
            remote = driver.verify(storage_key)
            if remote.size_bytes == local_size:
                tally["skipped"] += 1
                continue
        except StorageError:
            # Chưa có ở đích, hoặc có mà hỏng. Cả hai đều dẫn tới việc đẩy lên.
            pass

        if dry_run:
            print(f"  sẽ đẩy  {storage_key}  ({local_size:,} byte)")
            tally["uploaded"] += 1
            continue

        try:
            # `driver.client` là lối thoát riêng của S3Driver, KHÔNG nằm trong
            # `StorageDriver` — cùng lý do `LocalDiskDriver.write` không nằm
            # trong đó: đưa một đường ghi byte vào giao diện chung sẽ biến thứ
            # chỉ dành cho công cụ offline thành thứ trông như gọi được từ
            # tiến trình HTTP, mà §2.3 nói thẳng là không.
            driver.client.upload_file(
                str(path),
                driver.bucket,
                storage_key,
                ExtraArgs={
                    "ContentType": guess_mime(storage_key),
                    "CacheControl": CACHE_CONTROL,
                },
            )
        except Exception as error:
            # Một file hỏng không được làm hỏng cả lượt chạy — cùng luật với
            # `images.py`: báo rồi bỏ qua, để những file đã lên vẫn còn đó và
            # lần chạy sau chỉ phải làm nốt phần thiếu.
            print(f"  LỖI    {storage_key}: {error}", file=sys.stderr)
            tally["failed"] += 1
            continue
        tally["uploaded"] += 1

    return tally


def _default_prefixes() -> tuple[str, ...]:
    """Chỉ đẩy thứ mà object store này thật sự phục vụ.

    Ảnh có thể đang nằm ở Cloudinary (§2.2) — đẩy chúng lên đây nữa là trả tiền
    lưu trữ hai lần cho những file không ai đọc tới.
    """
    prefixes = []
    if settings.audio_storage_driver == "s3":
        prefixes.append("audio")
    if settings.image_storage_driver == "s3":
        prefixes.append("image")
    return tuple(prefixes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        help="thư mục con cần đẩy (audio | image); mặc định suy ra từ driver đang bật",
    )
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    prefixes = tuple(args.prefix) if args.prefix else _default_prefixes()
    if not prefixes:
        print(
            "Không có driver nào đặt thành s3 — đặt AUDIO_STORAGE_DRIVER=s3 "
            "(và/hoặc IMAGE_STORAGE_DRIVER=s3), hoặc chỉ định --prefix.",
            file=sys.stderr,
        )
        return 1

    missing = [
        name
        for name, value in (
            ("S3_ENDPOINT_URL", settings.s3_endpoint_url),
            ("S3_BUCKET", settings.s3_bucket),
            ("S3_ACCESS_KEY_ID", settings.s3_access_key_id),
            ("S3_SECRET_ACCESS_KEY", settings.s3_secret_access_key.get_secret_value()),
        )
        if not value
    ]
    if missing:
        print("thiếu cấu hình: " + ", ".join(missing), file=sys.stderr)
        return 1

    root = args.root or content_settings.object_store_dir
    objects = list(iter_local_objects(root, prefixes))
    if not objects:
        print(f"không có file nào dưới {root} với tiền tố {', '.join(prefixes)}")
        return 0

    driver = _driver()
    total = sum(path.stat().st_size for _, path in objects)
    print(
        f"{len(objects)} file ({total / 1_048_576:.1f} MB) -> "
        f"{settings.s3_bucket} @ {settings.s3_endpoint_url}"
    )

    tally = push(driver, objects, dry_run=args.dry_run)
    print(
        f"đã đẩy {tally['uploaded']} · bỏ qua {tally['skipped']} · lỗi {tally['failed']}"
        + ("  (chạy thử)" if args.dry_run else "")
    )
    return 1 if tally["failed"] else 0


def _driver() -> S3Driver:
    # Dựng thẳng chứ không qua `get_driver`: lệnh này đẩy cả audio lẫn ảnh, mà
    # `get_driver("image")` có thể đang trả về Cloudinary. `kind` ở đây chỉ ảnh
    # hưởng trần dung lượng khi xác minh, không ảnh hưởng đường đi của byte.
    return S3Driver(
        kind="audio",
        endpoint_url=settings.s3_endpoint_url,
        region=settings.s3_region,
        bucket=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        base_url=settings.audio_public_base_url,
    )


if __name__ == "__main__":
    raise SystemExit(main())
