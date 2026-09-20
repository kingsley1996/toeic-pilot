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

CẢNH BÁO khi trỏ prod: script chỉ THÊM, không đồng bộ xoá — bài nào đã gỡ public
thủ công trên prod (5 bài Ms James, 2026-09-19) mà còn trong list dưới thì chạy
lại sẽ seed chúng về. Muốn seed đúng 5 bài TED thì lọc list trước khi chạy.
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
    passes_quality,
    validate_transcript,
)
from app.services.listening_tiktok_captions import fetch_tiktok_captions
from app.services.listening_youtube_captions import (
    CaptionError,
    fetch_youtube_captions,
)

# Loạt 10: tiếng Anh rõ + sub tay, toàn dưới 5 phút, KHÔNG phụ đề cháy trong
# hình (đã soi frame từng video — chữ hiện sẵn là lộ đáp án, mask vô nghĩa).
# ĐÃ LOẠI, đừng thêm lại:
# - TL61VKkme14/HrCbXNRP7eg/eHJnEHyyN1Y (dài quá 5 phút), Wb6Oc1_SdJw (ASR
#   word-salad, 3.6% câu trọn), xowuC3keDcA (trùng chủ đề shopping),
#   bgfdqVmVjfk (ASR kém, 24/42), IWMMkp35d6Y (ASR kém, 1/6),
#   oE2IZvpOlGk + Qo6VHK5n_LU + viE3Xez8IQ0 (region-block),
#   wyqfYJX23lg + r3ga_G-nMbk + dqdUoM4gVrM + bq6GBbh3uhU (CHÁY phụ đề thoại),
#   UNP03fDSj1U (ASR salad như meetings),
#   Y6bbMQXQ180 (slide từ khoá cháy hình — FOCUS/IDEAS hiện sẵn, mask vô nghĩa).
VIDEOS: list[tuple[str, str | None, int | None]] = [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", None, None),
    ("https://www.youtube.com/watch?v=yPYZpwSpKmA", None, None),
    ("https://www.youtube.com/watch?v=s8YxQkCCwAc", None, None),
    ("https://www.youtube.com/watch?v=CqgmozFr_GM", None, None),
    ("https://www.youtube.com/watch?v=JAyuHIthHco", None, None),
    ("https://www.youtube.com/watch?v=bVRIpmjTSxM", None, None),
    ("https://www.youtube.com/watch?v=w0YQwglgtTM", None, None),
    ("https://www.youtube.com/watch?v=NHopJHSlVo4", None, None),
    ("https://www.youtube.com/watch?v=NiKtZgImdlY", None, None),
    ("https://www.youtube.com/watch?v=1aA1WGON49E", None, None),
    # TikTok: sub auto eng-US qua yt-dlp (xem listening_tiktok_captions). Thumbnail
    # đã soi: chỉ cháy chữ CHỦ ĐỀ ("from vs of", "picturesque" trên bảng) chứ
    # không cháy lời thoại — ngang gợi ý ở tiêu đề, nhận cho thư viện thử.
    (
        "https://www.tiktok.com/@englishteacherclaire/video/7253146839854222619",
        "Of vs from — English Teacher Claire",
        None,
    ),
    (
        "https://www.tiktok.com/@iamthatenglishteacher/video/7222796674282966314",
        "Picturesque — Ms James (Grammar)",
        None,
    ),
    (
        "https://www.tiktok.com/@englishteacherclaire/video/7686577902040747286",
        "Basic vs advanced idioms — English Teacher Claire",
        None,
    ),
    (
        "https://www.tiktok.com/@englishteacherclaire/video/7685726743226797334",
        "Asking for a photo — English Teacher Claire",
        None,
    ),
    (
        "https://www.tiktok.com/@englishteacherclaire/video/7684383549750840598",
        "Kitchen vocabulary — English Teacher Claire",
        None,
    ),
    (
        "https://www.tiktok.com/@englishteacherclaire/video/7682779913849457923",
        "Ordering politely — English Teacher Claire",
        None,
    ),
    (
        "https://www.tiktok.com/@iamthatenglishteacher/video/7686854847089397022",
        "Starting with Because — Ms James (Grammar)",
        None,
    ),
    (
        "https://www.tiktok.com/@iamthatenglishteacher/video/7686676227331001631",
        "Why learn? — Ms James",
        None,
    ),
    (
        "https://www.tiktok.com/@iamthatenglishteacher/video/7686638187334192414",
        "Apostrophes — Ms James (Grammar)",
        None,
    ),
    (
        "https://www.tiktok.com/@iamthatenglishteacher/video/7686332407477194014",
        "See, saw, seen — Ms James (Grammar)",
        None,
    ),
    # Đợt TED 5 bài (2026-09-19): playlist "TED in 3 minutes" chính chủ, toàn
    # sub tay, span 2–3.5 phút. Soi frame từng video: St. John loại vì slide từ
    # khoá cháy hình, Matt Cutts loại vì ASR salad (xem ĐÃ LOẠI trên).
    (
        "https://www.youtube.com/watch?v=cHKs2aVxOmQ",
        "How to deal with your insomnia - Matt Walker",
        None,
    ),
    (
        "https://www.youtube.com/watch?v=_H4C-08GkKo",
        "How accurate is the weather forecast? - Mona Chalabi",
        None,
    ),
    (
        "https://www.youtube.com/watch?v=j-Mys_05D78",
        "A simple 2-step plan for saving more money - Wendy De La Rosa",
        None,
    ),
    (
        "https://www.youtube.com/watch?v=eeVCz-9SUc8",
        "The function and fashion of eyeglasses - Debbie Millman",
        None,
    ),
    (
        "https://www.youtube.com/watch?v=3NFTa9kTVRU",
        "How your sense of smell helps you savor flavor - Jen Gunter",
        None,
    ),
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
    if source.type not in ("youtube", "tiktok"):
        return f"SKIP {url}: captions tự động mới có YouTube/TikTok"
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
        if source.type == "youtube":
            captions = fetch_youtube_captions(source.external_id or "")
        else:
            captions = fetch_tiktok_captions(source.url)
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
    # Cổng chất lượng: word-salad thì bỏ video chứ không ráng (xem passes_quality).
    ok, quality_reason = passes_quality(merged)
    if not ok:
        return f"SKIP {url}: transcript kém ({quality_reason})"
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
