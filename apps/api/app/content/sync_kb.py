"""Đồng bộ knowledge base từ file markdown vào bảng `knowledge_chunk`.

uv run python -m app.content.sync_kb [--dir <thư mục>] [--dry-run]

Nguồn sự thật là CÂY FILE (`apps/api/content/kb/*.md`) — nội dung đi qua review
như mã, và bảng chỉ là bản tính sẵn. Lệnh này chạy NGOÀI LUỒNG, không bao giờ
được gọi từ request handler: nó viết database, và viết database là việc của
lệnh vận hành chứ không phải của đường phục vụ.

File nào mất khỏi thư mục sẽ bị XOÁ khỏi bảng — thêm tài liệu là thêm file,
bớt tài liệu là bớt file; không có trạng thái "tắt tạm" ở đây.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.services.knowledge import sync_knowledge

# app/content/sync_kb.py → apps/api → `content/kb` của pipeline. KB là NGUỒN
# ĐỒNG BỘ, phải chỉ đúng cây file đã commit — sai thư mục là sync xoá toàn bộ
# bảng (đã xảy ra đúng một lần ngày 2026-08-29).
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "content" / "kb"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        # sync_knowledge không tự commit, nên rollback một mình là đủ dry-run.
        session = SessionLocal()
        try:
            result = sync_knowledge(session, args.dir)
            session.rollback()
        finally:
            session.close()
        print(
            "[dry-run] tạo mới:",
            result.created,
            "· cập nhật:",
            result.updated,
            "· xoá:",
            result.removed,
        )
        return 0

    session = SessionLocal()
    try:
        result = sync_knowledge(session, args.dir)
        session.commit()
    finally:
        session.close()
    print(f"tạo mới: {result.created}")
    print(f"cập nhật: {result.updated}")
    print(f"xoá: {result.removed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
