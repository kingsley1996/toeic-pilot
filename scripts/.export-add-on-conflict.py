"""Viết lại INSERT của pg_dump thành ON CONFLICT (khóa chính) DO UPDATE.

`pg_dump --column-inserts` cho INSERT thuần; nạp vào production đã có sẵn hàng
thì đụng khoá chính và dừng giữa đường (lý do trong SYNC-TEST-TO-PRODUCTION §3).
Mỗi bảng một khoá chính khác nhau — `vocabulary_audio` là composite
(entry_id, kind, accent) — nên tra siêu dữ liệu từ chính file dump qua các
lệnh `CREATE TABLE` mà pg_dump in trước các INSERT.

Chạy lại tự sửa: DO UPDATE SET mọi cột trừ khoá, giá trị dùng EXCLUDED.
"""

import re
import sys

# Bảng → cột khoá chính (khớp migration; giữ dạng chữ thường như trong dump).
PRIMARY_KEYS = {
    "audio_asset": ["id"],
    "topic": ["id"],
    "vocabulary_entry": ["id"],
    "collocation_detail": ["entry_id"],
    "vocabulary_audio": ["entry_id", "kind", "accent"],
    "vocabulary_topic": ["entry_id", "topic_id"],
    "vocabulary_collection": ["id"],
    "vocabulary_collection_item": ["id"],
}

INSERT_RE = re.compile(r"INSERT INTO (?:public\.)?(\w+) \(([^)]*)\) VALUES \((.*)\);\s*$")

current_table = None
for line in sys.stdin:
    created = re.match(r"CREATE TABLE (?:public\.)?(\w+) ", line)
    if created:
        current_table = created.group(1)

    match = INSERT_RE.match(line)
    if not match:
        sys.stdout.write(line)
        continue

    table, cols, vals = match.groups()
    if table not in PRIMARY_KEYS:
        # Bảng ngoài danh sách (SET, SELECT, ...) đi qua nguyên văn.
        sys.stdout.write(line)
        continue

    collist = [c.strip() for c in cols.split(",")]
    keys = [c for c in collist if c in PRIMARY_KEYS[table]]
    if len(keys) != len(PRIMARY_KEYS[table]):
        sys.stderr.write(f"WARN: {table}: thiếu cột khoá {PRIMARY_KEYS[table]} trong INSERT\n")
        sys.stdout.write(line)
        continue

    conflict = ", ".join(keys)
    # Bảng nối thuần khoá (vocabulary_topic...) không còn cột nào để SET —
    # DO UPDATE SET rỗng là lỗi cú pháp; DO NOTHING đủ vì hàng nối không có
    # gì cần cập nhật.
    updates = [c for c in collist if c not in keys]
    if not updates:
        sys.stdout.write(
            f"INSERT INTO public.{table} ({cols}) VALUES ({vals}) "
            f"ON CONFLICT ({conflict}) DO NOTHING;\n"
        )
        continue
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
    sys.stdout.write(
        f"INSERT INTO public.{table} ({cols}) VALUES ({vals}) "
        f"ON CONFLICT ({conflict}) DO UPDATE SET {set_clause};\n"
    )
