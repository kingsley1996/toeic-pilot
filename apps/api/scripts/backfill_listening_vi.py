"""Điền bản dịch tiếng Việt cho segment video (`listening_segment.text_vi`).

    uv run python scripts/backfill_listening_vi.py [--apply]

Mặc định DRY-RUN (chỉ đếm). Ghi thật cần `--apply`. DATABASE_URL trỏ đâu thì
điền ở đó: local để thử, prod để lên sóng (prod cần migration 092 đã deploy,
vì entrypoint chạy `alembic upgrade head` lúc deploy ảnh API).

Nguồn: `scripts/data/listening_segment_vi.json` — 405 câu của 15 bài public
trên prod, dịch tay. Khớp theo (source_type, external_id, segment_index) và
ĐỐI CHIẾU text gốc: index trôi mà vẫn ghi là ghi nhầm câu — câu lệch thì bỏ
qua + in cảnh báo, không đoán. Chạy lại idempotent (câu đã đúng thì bỏ qua).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import ListeningContent, ListeningSegment

DATA = Path(__file__).with_name("data") / "listening_segment_vi.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="ghi DB thật (mặc định dry-run)")
    args = parser.parse_args()

    entries = json.loads(DATA.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        contents = {
            (c.source_type, c.external_id): c.id for c in db.scalars(select(ListeningContent)).all()
        }
        updated = skipped = same = 0
        for entry in entries:
            content_id = contents.get((entry["source_type"], entry["external_id"]))
            if content_id is None:
                skipped += 1
                print(f"SKIP no-content {entry['source_type']}/{entry['external_id']}")
                continue
            seg = db.scalars(
                select(ListeningSegment).where(
                    ListeningSegment.content_id == content_id,
                    ListeningSegment.segment_index == entry["index"],
                )
            ).first()
            if seg is None:
                skipped += 1
                print(f"SKIP no-segment {entry['external_id']}#{entry['index']}")
                continue
            if seg.text.strip() != entry["text"].strip():
                skipped += 1
                print(f"SKIP text-drift {entry['external_id']}#{entry['index']}: {seg.text[:60]!r}")
                continue
            if seg.text_vi == entry["text_vi"]:
                same += 1
                continue
            if args.apply:
                seg.text_vi = entry["text_vi"]
            updated += 1
        if args.apply:
            db.commit()
        verb = "wrote" if args.apply else "would write"
        print(f"{verb} {updated}, unchanged {same}, skipped {skipped}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
