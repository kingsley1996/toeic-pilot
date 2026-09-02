"""Nhập một tệp paste từ vựng vào database, không qua giao diện admin.

    uv run python -m app.content.import_vocabulary \
        --file content/sources/vocabulary_meetings.paste.txt \
        --topic-slug meetings --topic-name "Meetings & Presentations"

    uv run python -m app.content.import_vocabulary --publish

Bảy chủ đề đầu tiên được dán tay qua `/admin/vocabulary`, và đó là đường đúng khi
một người ngồi xem bản parse trước lúc lưu (ADR-005 §3.4). Nhưng nó không chạy
được từ dòng lệnh, nên một đợt nhập bốn chủ đề thành bốn lượt dán thủ công.

**Dùng lại đúng `parse_vocabulary` của route admin**, không viết bộ tách thứ hai:
một bộ tách song song sẽ trôi khỏi bộ kia, và kiểu trôi ấy chỉ lộ ra khi cùng một
tệp cho hai kết quả khác nhau ở hai lối vào.

**Không bao giờ publish thẳng lúc nhập.** Hàng mới luôn là `draft`, giống hệt
route admin, vì `vocabulary_audio_slots` chưa có gì để nói lúc chưa có audio.
`--publish` là bước RIÊNG và nó gọi đúng cổng mà API gọi — không tự lật cột
`status`, vì làm thế là dựng một đường publish thứ hai không có kiểm.
"""

import argparse
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models.topic import Topic
from app.models.vocabulary import VocabularyEntry, VocabularyTopic
from app.services.content_import import parse_vocabulary
from app.services.media_state import vocabulary_audio_slots


def _topic(db: Session, slug: str, name: str, item_id: str | None) -> Topic:
    topic = db.scalars(select(Topic).where(Topic.slug == slug)).first()
    if topic is not None:
        return topic
    # `position` nối tiếp chủ đề cuối: chủ đề mới xuống cuối danh sách chứ không
    # chen vào giữa thứ tự người học đã quen.
    last = db.scalar(select(func.max(Topic.position))) or 0
    # `published` ngay, giống hệt `POST /admin/topics`: chủ đề là thứ người học
    # thấy trước khi có nội dung nào, và một chủ đề trống thì vô hại. Để `draft`
    # ở đây sẽ tạo một đường tạo chủ đề thứ hai cư xử khác đường kia — và cái
    # khác đó chỉ lộ ra khi chủ đề mới không hiện trên trang học.
    # `collection_item_id` KHÔNG phải tuỳ chọn trang trí: chủ đề không nằm trong
    # một cuốn nào chỉ hiện ở trục phẳng "chủ đề chưa xếp", không nằm trong cây
    # mà học viên thật sự duyệt. Nhập xong mà quên bước này thì nội dung có
    # trong database và vô hình trên màn hình.
    topic = Topic(
        slug=slug,
        name=name,
        position=last + 1,
        status="published",
        collection_item_id=uuid.UUID(item_id) if item_id else None,
    )
    db.add(topic)
    db.flush()
    return topic


def import_file(
    db: Session, path: Path, slug: str, name: str, item_id: str | None
) -> tuple[int, int, list[str]]:
    rows = parse_vocabulary(path.read_text(encoding="utf-8"))
    topic = _topic(db, slug, name, item_id)

    created = 0
    skipped = 0
    problems: list[str] = []

    for row in rows:
        if row.problems:
            skipped += 1
            problems.append(f"dòng {row.line}: {'; '.join(row.problems)}")
            continue

        entry = VocabularyEntry(
            headword=row.headword,
            part_of_speech=row.part_of_speech,
            phonetic=row.phonetic,
            meaning_en=row.meaning_en,
            meaning_vi=row.meaning_vi,
            example=row.example,
            example_vi=row.example_vi,
            difficulty=2,
            status="draft",
        )
        try:
            # Savepoint mỗi hàng, và `add` NẰM TRONG nó — cùng lý do đã ghi ở
            # `admin_vocabulary.commit_vocabulary`: rollback cả transaction sẽ
            # vứt luôn những hàng đã flush trước đó trong khi bộ đếm vẫn nhận.
            with db.begin_nested():
                db.add(entry)
                db.flush()
        except IntegrityError:
            skipped += 1
            problems.append(f"dòng {row.line}: {row.headword!r} ({row.part_of_speech}) đã có")
            continue

        db.add(VocabularyTopic(entry_id=entry.id, topic_id=topic.id))
        created += 1

    db.commit()
    return created, skipped, problems


def publish_ready(db: Session) -> tuple[int, int]:
    """Publish mọi bản nháp đã đủ audio, theo đúng cổng của API."""
    drafts = db.scalars(
        select(VocabularyEntry)
        .where(VocabularyEntry.status == "draft")
        .options(selectinload(VocabularyEntry.audio))
    ).all()

    published = 0
    waiting = 0
    for entry in drafts:
        slots = vocabulary_audio_slots(entry)
        if any(slot.state.value != "current" for slot in slots):
            waiting += 1
            continue
        entry.status = "published"
        entry.published_at = datetime.now(UTC)
        published += 1
    db.commit()
    return published, waiting


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nhập từ vựng từ tệp paste.")
    parser.add_argument("--file", type=Path, help="tệp .paste.txt")
    parser.add_argument("--topic-slug", help="slug chủ đề, tạo mới nếu chưa có")
    parser.add_argument("--topic-name", help="tên hiển thị của chủ đề")
    parser.add_argument(
        "--collection-item",
        help="uuid của mục trong bộ sưu tập; thiếu thì chủ đề không vào cây học viên duyệt",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="publish mọi bản nháp đã đủ audio, rồi dừng",
    )
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.publish:
            published, waiting = publish_ready(db)
            print(f"{published} từ vừa publish · {waiting} còn chờ audio")
            return 0

        if args.file is None or args.topic_slug is None or args.topic_name is None:
            parser.error("cần --file, --topic-slug và --topic-name (hoặc --publish)")

        created, skipped, problems = import_file(
            db, args.file, args.topic_slug, args.topic_name, args.collection_item
        )
        print(f"{args.topic_slug}: {created} từ mới · {skipped} bỏ qua")
        for line in problems[:20]:
            print(f"  {line}")
        if len(problems) > 20:
            print(f"  … và {len(problems) - 20} dòng nữa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
