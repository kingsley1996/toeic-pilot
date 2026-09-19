# ruff: noqa: E501
"""Ingest file mp4 tự host cho bài TikTok thư viện chưa có media.

    uv run python scripts/ingest_listening_media.py [--apply]

Mặc định DRY-RUN (chỉ in kế hoạch) — ghi DB/file thật cần `--apply`. Chạy TAY
ở local, CẤM CI. DATABASE_URL trỏ đâu thì ingest ở đó.

Mỗi bài public TikTok thiếu `media_storage_key`: yt-dlp tải best mp4 (giới hạn
MAX_VIDEO_BYTES) → upload qua driver → gắn key `listening/<id>.mp4`. Driver
local thì ghi trực tiếp; driver vé-ký-sẵn (S3 presigned PUT) thì PUT theo vé
rồi verify lại object (§2.3) — cùng đường upload như trình duyệt, chỉ khác là
script cầm file thay vì user.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from yt_dlp import YoutubeDL
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import YoutubeDLError

from app.core.database import SessionLocal
from app.core.storage import MAX_VIDEO_BYTES, StorageError, get_driver
from app.models import ListeningContent


def download_mp4(url: str, dest: Path) -> int:
    """Tải best mp4 về file. Trả cỡ byte. Lỗi yt-dlp nào cũng thành RuntimeError
    để caller in một dòng rồi đi tiếp — một video hỏng không dừng cả loạt."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "impersonate": ImpersonateTarget.from_str("chrome"),
        "socket_timeout": 20,
        "format": "best[ext=mp4]/best",
        "outtmpl": str(dest),
        "overwrites": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    except YoutubeDLError as exc:
        raise RuntimeError(f"yt-dlp: {exc}") from exc
    size = dest.stat().st_size
    if size > MAX_VIDEO_BYTES:
        raise RuntimeError(f"file {size} bytes quá trần {MAX_VIDEO_BYTES}")
    if size == 0:
        raise RuntimeError("file rỗng")
    return size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="tải + ghi thật (mặc định dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        pending = db.scalars(
            select(ListeningContent).where(
                ListeningContent.is_public.is_(True),
                ListeningContent.source_type == "tiktok",
                ListeningContent.media_storage_key.is_(None),
            )
        ).all()
        if not args.apply:
            print(f"DRY-RUN — {len(pending)} bài TikTok thiếu media, thêm --apply để ingest:")
            for content in pending:
                print(f"  would ingest {content.title} ({content.source_url})")
            return 0
        driver = get_driver("video")
        write = getattr(driver, "write", None)

        def store(key: str, payload: bytes) -> None:
            if callable(write):
                write(key, payload)
                return
            # Vé-ký-sẵn (S3 presigned PUT): cùng đường trình duyệt đi, script
            # cầm file thay user. Driver khác mà không phải PUT thì chịu.
            ticket = driver.ticket(key)
            if ticket.method != "PUT":
                raise RuntimeError(f"driver {type(driver).__name__} không ingest được từ script")
            try:
                response = httpx.put(
                    ticket.upload_url,
                    content=payload,
                    headers=ticket.fields,
                    timeout=120.0,
                )
            except httpx.HTTPError as exc:
                raise RuntimeError(f"upload: {exc}") from exc
            if response.status_code >= 400:
                raise RuntimeError(f"upload HTTP {response.status_code}")
            driver.verify(key)

        for content in pending:
            key = f"listening/{content.id}.mp4"
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "video.mp4"
                try:
                    size = download_mp4(content.source_url, dest)
                    store(key, dest.read_bytes())
                except (RuntimeError, StorageError) as exc:
                    print(f"SKIP {content.title}: {exc}", flush=True)
                    continue
            content.media_storage_key = key
            db.commit()
            print(f"OK {content.title} — {size / 1024 / 1024:.1f} MB -> {key}", flush=True)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
