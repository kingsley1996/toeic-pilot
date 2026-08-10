"""Đẩy media đã sinh sẵn ở máy lên nơi nó sẽ được phục vụ.

    uv run python -m app.content.push_media [--dry-run] [--prefix audio]

Vì sao đây là một lệnh riêng chứ không phải luồng upload của ADR-006: **hai bài
toán khác nhau bị gọi chung một cái tên.**

- Media sinh/lấy về ngoài luồng (audio từ edge-tts, ảnh CC từ `images.py`) là
  bài toán **triển khai** — file đã nằm trên đĩa, việc còn lại là đồng bộ.
- File do người thật tải lên qua màn quản trị mới cần `ticket/verify` của §2.3,
  vì lúc đó byte đi từ một máy ta không kiểm soát.

Gộp hai thứ lại sẽ bắt đường đơn giản phải trả giá cho đường phức tạp. Lệnh này
chạy ở máy dev, sau `--extra content`, và **không bao giờ** chạy lúc có request.

**Mỗi loại media đi tới nhà cung cấp của nó** (ADR-006 §2.2): ảnh lên Cloudinary,
audio lên object store S3. Lệnh này chỉ đọc cấu hình rồi gọi đúng driver, nên
không có nơi thứ hai để hai quyết định đó lệch nhau.

Chạy lại là không tốn gì: khoá đã có ở đích với đúng dung lượng thì bỏ qua. Khoá
là content-addressed nên "đúng dung lượng" đã đủ chắc — nội dung khác thì hash
khác, mà hash khác thì khoá khác.
"""

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from app.content.settings import content_settings
from app.core.storage import (
    CloudinaryDriver,
    LocalDiskDriver,
    MediaKind,
    S3Driver,
    StorageError,
    get_driver,
)

# Thư mục con dưới media root, theo loại media. Khớp với tiền tố của
# `storage_key`, nên khoá suy ra thẳng từ đường dẫn tương đối.
PREFIXES: dict[str, MediaKind] = {"audio": "audio", "image": "image", "avatar": "image"}

Uploader = CloudinaryDriver | S3Driver


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
    driver: Uploader,
    objects: list[tuple[str, Path]],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    tally = {"uploaded": 0, "skipped": 0, "failed": 0}

    for storage_key, path in objects:
        local_size = path.stat().st_size
        try:
            remote = driver.verify(storage_key)
            # Cloudinary chuẩn hoá ảnh lúc nhận (giới hạn cạnh, tước EXIF), nên
            # dung lượng ở đích KHÁC dung lượng trên đĩa và không so được. Với
            # ảnh, "có mặt" đã là đủ: khoá là địa chỉ nội dung.
            if isinstance(driver, CloudinaryDriver) or remote.size_bytes == local_size:
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
            driver.upload_file(storage_key, path)
        except Exception as error:
            # Một file hỏng không được làm hỏng cả lượt chạy — cùng luật với
            # `images.py`: báo rồi bỏ qua, để những file đã lên vẫn còn đó và
            # lần chạy sau chỉ phải làm nốt phần thiếu.
            print(f"  LỖI    {storage_key}: {error}", file=sys.stderr)
            tally["failed"] += 1
            continue
        tally["uploaded"] += 1

    return tally


def uploader_for(kind: MediaKind) -> Uploader:
    driver = get_driver(kind)
    if isinstance(driver, LocalDiskDriver):
        raise StorageError(
            f"{kind.upper()}_STORAGE_DRIVER đang là 'local' — không có nơi nào để đẩy tới. "
            f"Đặt nó thành 'cloudinary' (ảnh) hoặc 's3' (audio)."
        )
    if not isinstance(driver, CloudinaryDriver | S3Driver):
        raise StorageError(f"driver cho {kind} không hỗ trợ đẩy file offline")
    return driver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đẩy media sinh sẵn lên nhà cung cấp.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        choices=sorted(PREFIXES),
        help="thư mục con cần đẩy; mặc định là tất cả",
    )
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    prefixes: tuple[str, ...] = tuple(args.prefix) if args.prefix else tuple(sorted(PREFIXES))
    root = args.root or content_settings.object_store_dir

    total = {"uploaded": 0, "skipped": 0, "failed": 0}
    for prefix in prefixes:
        objects = list(iter_local_objects(root, (prefix,)))
        if not objects:
            continue

        try:
            driver = uploader_for(PREFIXES[prefix])
        except StorageError as error:
            print(f"{prefix}: bỏ qua — {error}", file=sys.stderr)
            continue

        size = sum(path.stat().st_size for _, path in objects)
        print(
            f"{prefix}: {len(objects)} file ({size / 1_048_576:.1f} MB) -> {type(driver).__name__}"
        )
        tally = push(driver, objects, dry_run=args.dry_run)
        for key, value in tally.items():
            total[key] += value

    print(
        f"đã đẩy {total['uploaded']} · bỏ qua {total['skipped']} · lỗi {total['failed']}"
        + ("  (chạy thử)" if args.dry_run else "")
    )
    return 1 if total["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
