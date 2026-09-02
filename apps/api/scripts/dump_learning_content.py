r"""Kết xuất toàn bộ từ vựng và dictation thành SQL **nâng cấp tại chỗ**.

    uv run python scripts/dump_learning_content.py > /tmp/learning.sql

Chỉ ĐỌC database nguồn. Anh em với `dump_test.py`, nhưng khác nó ở đúng một
điểm và điểm đó quyết định cả thiết kế:

**`dump_test.py` cố ý NỔ khi đề đã có ở đích. Script này cố ý KHÔNG.** Một đề
chỉ được nạp một lần, nên trùng nghĩa là sai. Từ vựng và dictation thì ngược
lại: đích đã có phần cũ, và việc cần làm là *thêm phần mới rồi sửa phần cũ tại
chỗ*. Nên mọi hàng đi bằng `ON CONFLICT ... DO UPDATE`, và chạy lại là không
tốn gì.

**Vì sao phải UPDATE chứ không chỉ thêm.** `source_hash` gồm cả
`engine_version`, nên một lượt `backfill_audio --force` đẩy mọi clip sang khoá
nội-dung-địa-chỉ mới và tạo hàng `audio_asset` MỚI. `vocabulary_audio` ở nguồn
đã trỏ sang id mới; nếu chỉ chèn hàng mới thì đích giữ nguyên liên kết cũ và ở
lại dàn giọng cũ mãi mãi — im lặng, vì mọi thứ vẫn phát được.

**Không đụng tới lịch sử học.** `vocabulary_review_state`, `review_log`,
`dictation_attempt` và `topic_session` không nằm trong danh sách: chúng trỏ vào
`vocabulary_entry.id` và `dictation_item.id`, mà những id đó không đổi. Đó cũng
là lý do không được xoá-rồi-nạp-lại.

**Cột trỏ sang `users` bị đặt NULL** — cùng lý do đã ghi ở `dump_test.py`: uuid
tài khoản của máy nguồn không tồn tại ở đích, và cả ba cột đều nullable.
`published_at` thì GIỮ, vì nó mới là thứ quyết định học viên có thấy hay không.

**Nhiều hàng trong MỘT lệnh, và đó là khác biệt về bậc độ lớn.** `dump_test.py`
sinh mỗi hàng một `INSERT`, hợp lý cho vài trăm hàng của một đề. Ở đây là gần
chín nghìn hàng, và đích nằm sau một đường mạng xuyên quốc gia: đo được ~85 ms
cho mỗi vòng round-trip, nên chín nghìn lệnh là **mười ba phút** ngồi đợi mà
`psql -q` không in lấy một dòng — nhìn y hệt treo máy (2026-09-02). Gộp lô đưa
nó xuống vài chục lệnh.

Lô cắt theo **cả số hàng lẫn số byte**: `audio_asset` mang `source_text` dài
gấp nhiều lần các bảng khác, nên chỉ đếm hàng sẽ dựng ra những lệnh vài megabyte.

Gộp lô an toàn với `ON CONFLICT` vì khoá trong một lô là duy nhất — chúng là
khoá chính của chính bảng đó. Nếu một ngày nào đó lô chứa hai hàng cùng khoá,
Postgres sẽ nổ chứ không ghi sai: *ON CONFLICT DO UPDATE command cannot affect
row a second time*.

**Có `\echo` giữa các bảng.** `psql -q` tắt mọi thông báo, nhưng `\echo` vẫn in
— nên lượt nạp nói ra nó đang ở đâu thay vì im lặng suốt.
"""

import json
import sys
from typing import Any

from sqlalchemy import text

from app.core.database import SessionLocal

USER_COLUMNS = {"created_by", "published_by", "reviewed_by"}

# Chỉ những asset mà từ vựng/dictation thật sự dùng. Asset của đề thi đi đường
# riêng (`dump_test.py`) và đích đã có sẵn.
AUDIO_SCOPE = """
select * from audio_asset where id in (
    select audio_asset_id from vocabulary_audio
    union
    select audio_asset_id from dictation_item where audio_asset_id is not null
)
"""

# Thứ tự theo chiều phụ thuộc khoá ngoại. Đổi thứ tự là đổi thành một lượt nạp
# nổ giữa chừng.
TABLES: list[tuple[str, str, tuple[str, ...]]] = [
    ("audio_asset", AUDIO_SCOPE, ("id",)),
    ("vocabulary_collection", "select * from vocabulary_collection", ("id",)),
    ("vocabulary_collection_item", "select * from vocabulary_collection_item", ("id",)),
    ("topic", "select * from topic", ("id",)),
    ("vocabulary_entry", "select * from vocabulary_entry", ("id",)),
    ("vocabulary_topic", "select * from vocabulary_topic", ("entry_id", "topic_id")),
    ("vocabulary_audio", "select * from vocabulary_audio", ("entry_id", "kind", "accent")),
    ("dictation_topic", "select * from dictation_topic", ("id",)),
    ("dictation_section", "select * from dictation_section", ("id",)),
    ("dictation_story", "select * from dictation_story", ("id",)),
    ("dictation_item", "select * from dictation_item", ("id",)),
]


def literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


# Trần của một lệnh. 200 hàng là đủ để số vòng round-trip không còn đáng kể;
# 256 KB giữ cho lệnh vẫn đọc được khi phải mở file ra xem lúc có sự cố.
BATCH_ROWS = 200
BATCH_BYTES = 256 * 1024


def emit(table: str, key: tuple[str, ...], cols: list[str], tuples: list[str]) -> str:
    # Cột khoá không nằm trong SET: gán lại chính nó là vô nghĩa, và với khoá tổ
    # hợp thì Postgres từ chối.
    updates = [f"{c} = EXCLUDED.{c}" for c in cols if c not in key]
    tail = (
        f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {', '.join(updates)}"
        if updates
        else f"ON CONFLICT ({', '.join(key)}) DO NOTHING"
    )
    body = ",\n       ".join(tuples)
    return f"INSERT INTO {table} ({', '.join(cols)})\nVALUES {body}\n{tail};"


def main() -> int:
    out = [
        "-- Từ vựng + dictation: nâng cấp tại chỗ, chạy lại được.",
        "-- Sinh bởi scripts/dump_learning_content.py — không sửa tay.",
        "-- Một giao dịch: hỏng giữa chừng thì đích không giữ lại nửa vời.",
        "BEGIN;",
        "",
    ]
    statements = 0
    with SessionLocal() as session:
        for table, sql, key in TABLES:
            rows = session.execute(text(sql)).mappings().all()
            out.append(f"\\echo '  {table}: {len(rows)} hàng'")
            if not rows:
                out.append("")
                continue

            cols = list(rows[0].keys())
            batch: list[str] = []
            size = 0
            for row in rows:
                vals = [literal(None if c in USER_COLUMNS else row[c]) for c in cols]
                tup = f"({', '.join(vals)})"
                if batch and (len(batch) >= BATCH_ROWS or size + len(tup) > BATCH_BYTES):
                    out.append(emit(table, key, cols, batch))
                    statements += 1
                    batch, size = [], 0
                batch.append(tup)
                size += len(tup)
            if batch:
                out.append(emit(table, key, cols, batch))
                statements += 1
            out.append("")
    out.append("COMMIT;")
    out.append("\\echo 'xong'")
    print("\n".join(out))
    print(f"-- {statements} lệnh INSERT", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
