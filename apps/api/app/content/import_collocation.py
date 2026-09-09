"""Nhập một tệp paste collocation vào database, không qua giao diện admin.

    uv run python -m app.content.import_collocation \
        --file content/sources/collocations_200.paste.txt \
        --topic-slug collocations-verbs --topic-name "Collocations: Động từ"

    uv run python -m app.content.import_collocation --publish

Cùng khuôn với `import_vocabulary.py` và **dùng lại đúng `parse_collocation`
của route admin**: một bộ tách song song sẽ trôi khỏi bộ kia. Hàng mới luôn
`draft` và `--publish` gọi đúng `vocabulary_is_publishable` — không tự lật
cột `status`, không dựng đường publish thứ hai không có kiểm.

`meaning_en` bị NOT NULL ở `vocabulary_entry` mà format collocation không có
cột nghĩa tiếng Anh, nên nó nhận chính `headword` — giống đường commit của
admin (`admin_vocabulary.commit_collocations`).
"""

import argparse
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.topic import Topic
from app.models.vocabulary import CollocationDetail, VocabularyEntry, VocabularyTopic
from app.services.content_import import parse_collocation


def _topic(db: Session, slug: str, name: str) -> Topic:
    topic = db.scalars(select(Topic).where(Topic.slug == slug)).first()
    if topic is not None:
        return topic
    last = db.scalar(select(func.max(Topic.position))) or 0
    topic = Topic(
        slug=slug,
        name=name,
        position=last + 1,
        # `published` ngay — chủ đề trống vô hại, và cư xử đúng như
        # `POST /admin/topics`; xem lập luận đầy đủ ở `import_vocabulary._topic`.
        status="published",
        # Không gắn collection_item: collocation chưa có cuốn trong cây tuyển
        # tập, nó hiện ở trục phẳng "chủ đề chưa xếp" cho tới khi có ai đó xếp.
        collection_item_id=None,
    )
    db.add(topic)
    db.flush()
    return topic


def import_file(db: Session, path: Path, slug: str, name: str) -> tuple[int, int, list[str]]:
    rows = parse_collocation(path.read_text(encoding="utf-8"))
    topic = _topic(db, slug, name)

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
            part_of_speech="phrase",
            meaning_en=row.headword,
            meaning_vi=row.meaning_vi,
            example=row.example,
            example_vi=row.example_vi,
            difficulty=2,
            status="draft",
            collocation=CollocationDetail(
                base_word=row.base_word,
                gap_word=row.gap_word,
                pattern=row.pattern,
                distractors=row.distractors or None,
            ),
        )
        try:
            # Savepoint mỗi hàng — cùng lý do đã ghi ở `import_vocabulary`:
            # rollback cả transaction vứt luôn những hàng đã flush trước đó
            # trong khi bộ đếm vẫn nhận.
            with db.begin_nested():
                db.add(entry)
                db.flush()
        except IntegrityError:
            skipped += 1
            problems.append(f"dòng {row.line}: {row.headword!r} (phrase) đã có")
            continue

        db.add(VocabularyTopic(entry_id=entry.id, topic_id=topic.id))
        created += 1

    db.commit()
    return created, skipped, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nhập collocation từ tệp paste.")
    parser.add_argument("--file", type=Path, help="tệp paste, một collocation mỗi dòng")
    parser.add_argument("--topic-slug", help="slug chủ đề, tạo mới nếu chưa có")
    parser.add_argument("--topic-name", help="tên hiển thị của chủ đề")
    args = parser.parse_args(argv)

    if args.file is None or args.topic_slug is None or args.topic_name is None:
        parser.error("cần --file, --topic-slug và --topic-name")

    with SessionLocal() as db:
        created, skipped, problems = import_file(db, args.file, args.topic_slug, args.topic_name)
        print(f"{args.topic_slug}: {created} collocation mới · {skipped} bỏ qua")
        for line in problems[:20]:
            print(f"  {line}")
        if len(problems) > 20:
            print(f"  … và {len(problems) - 20} dòng nữa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
