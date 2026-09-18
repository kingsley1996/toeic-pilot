# ruff: noqa: E501
"""Seed thư viện Listening Lab: lấy phụ đề trước cho loạt video chọn sẵn.

    uv run python scripts/seed_listening_library.py [--apply] [--owner-email ...]

Mặc định DRY-RUN (chỉ in kế hoạch) — ghi DB thật cần `--apply`. Chạy TAY ở
local (IP sạch, không bị tường bot YouTube), CẤM CI (gọi mạng ngoài + ghi DB).
DATABASE_URL trỏ đâu thì seed ở đó: local để thử, prod để lên sóng thật.

Mỗi video: resolve → fetch captions → validate → lọc dòng không lời (cùng luật
endpoint create) → bỏ qua nếu trùng (source_type, external_id) đã có → tạo bài
`is_public` dưới chủ sở hữu thư viện. Video nào hỏng in lý do rồi đi tiếp,
không dừng cả loạt.
"""

from __future__ import annotations

import argparse
import secrets

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import ListeningContent, ListeningSegment, User
from app.services import dictation as dictation_grader
from app.services.listening_source import SourceError, resolve_source
from app.services.listening_transcript import (
    is_speakable,
    merge_fragments,
    validate_transcript,
)
from app.services.listening_youtube_captions import (
    CaptionError,
    fetch_youtube_captions,
)

# Loạt đầu: tiếng Anh rõ + phụ đề tay đã thử thật. Thêm video = thêm dòng, rồi
# chạy lại (trùng thì bỏ qua, không đẻ đôi). Cột 3 là excerpt (giây): video dài
# mà hay thì lấy đoạn đầu thay vì bỏ — mở đầu thường rõ ràng + tự trọn ý nhất.
VIDEOS: list[tuple[str, str | None, int | None]] = [
    ("https://www.youtube.com/watch?v=TL61VKkme14", None, 180),
    ("https://www.youtube.com/watch?v=HrCbXNRP7eg", None, 180),
    ("https://www.youtube.com/watch?v=eHJnEHyyN1Y", None, 180),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", None, None),
    ("https://www.youtube.com/watch?v=yPYZpwSpKmA", None, None),
]

LIBRARY_EMAIL = "library@toeic-pilot.local"


def get_owner(db, email: str) -> User:
    """Hàng user đứng tên bài thư viện. Mật khẩu ngẫu nhiên không ai biết —
    đây là kệ sách, không phải tài khoản đăng nhập."""
    owner = db.scalars(select(User).where(User.email == email)).first()
    if owner is None:
        owner = User(
            email=email,
            hashed_password=get_password_hash(secrets.token_hex(32)),
            role="learner",
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
    return owner


def seed_one(
    db, url: str, title_override: str | None, owner_email: str, max_seconds: int | None = None
) -> str:
    try:
        source = resolve_source(url)
    except SourceError as exc:
        return f"SKIP {url}: resolve {exc.code}"
    if source.type != "youtube":
        return f"SKIP {url}: captions tự động mới có YouTube (TikTok ở Phase 2)"
    exists = db.scalars(
        select(ListeningContent.id).where(
            ListeningContent.source_type == source.type,
            ListeningContent.external_id == source.external_id,
            ListeningContent.is_public.is_(True),
        )
    ).first()
    if exists is not None:
        return f"SKIP {url}: thư viện đã có bài {exists}"
    try:
        captions = fetch_youtube_captions(source.external_id or "")
    except CaptionError as exc:
        return f"SKIP {url}: captions {exc.code}"
    validation = validate_transcript(captions.segments)
    if not validation.valid:
        return f"SKIP {url}: transcript lỗi ({'; '.join(validation.errors)})"
    speakable = [s for s in captions.segments if is_speakable(s.text)]
    if not speakable:
        return f"SKIP {url}: không có câu thoại nào"
    if max_seconds is not None:
        # Excerpt: chỉ giữ câu nằm TRỌN trong đoạn đầu — câu dở dang ở mốc cắt
        # mà giữ là bài hỏng (nghe nửa chừng), bỏ còn hơn.
        speakable = [s for s in speakable if s.end <= max_seconds]
        if not speakable:
            return f"SKIP {url}: excerpt {max_seconds}s không còn câu nào"
    # Cùng pipeline với endpoint create (filter-rồi-merge) để bài thư viện và
    # bài user tự tạo chia câu giống nhau.
    merged = merge_fragments(speakable)
    # Tiêu chí thư viện: video dưới 5 phút, ưu tiên 1–3 phút. Đo bằng span
    # transcript (max end) — cùng thước với warning ở endpoint create.
    span = max(s.end for s in speakable)
    if span > 300:
        return f"SKIP {url}: dài {float(span) / 60:.1f} phút, quá 5 phút"
    owner = get_owner(db, owner_email)
    content = ListeningContent(
        user_id=owner.id,
        source_type=source.type,
        source_url=source.url,
        external_id=source.external_id,
        title=(title_override or captions.title or source.url).strip()[:512],
        transcript_status="ready",
        is_public=True,
        segments=[
            ListeningSegment(
                segment_index=index,
                start_seconds=seg.start,
                end_seconds=seg.end,
                text=seg.text,
                normalized_text=" ".join(dictation_grader.normalise(seg.text)),
            )
            for index, seg in enumerate(merged)
        ],
    )
    db.add(content)
    db.commit()
    dropped = len(captions.segments) - len(merged)
    extra = f" (gộp/bỏ {dropped} dòng)" if dropped else ""
    return f"OK {content.title} — {len(merged)} câu{extra}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="ghi DB thật (mặc định dry-run)")
    parser.add_argument("--owner-email", default=LIBRARY_EMAIL)
    args = parser.parse_args()

    if not args.apply:
        print(f"DRY-RUN — {len(VIDEOS)} video, thêm --apply để ghi:")
        for url, _ in VIDEOS:
            print(f"  would seed {url}")
        return 0

    db = SessionLocal()
    try:
        for url, title, excerpt in VIDEOS:
            print(seed_one(db, url, title, args.owner_email, excerpt), flush=True)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
