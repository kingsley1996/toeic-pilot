#!/usr/bin/env bash
# Rút MỘT đề thi khỏi database dev, để bổ sung vào production đã có đủ dữ liệu.
#
# Production đã có mọi nội dung cũ (vocab, dictation, đề khác, media của chúng)
# nên bản dump KHÔNG được chứa những hàng đó — sẽ đụng khoá chính khi nạp.
# Cách làm: clone dev DB, trên bản sao xoá sạch mọi bảng không thuộc tập bảng
# của đề, lọc các bảng của đề xuống còn đúng một test, rồi `pg_dump --data-only`.
#
# Các bảng giữ lại và lý do:
#   practice_test / practice_test_question / question / question_set /
#   question_option / question_label / question_set_label  — nội dung của đề.
#   audio_asset / image_asset  — media của đề (đã push lên provider, chỉ cần row).
#   score_scale / score_conversion / test_collection  — bảng tham chiếu TINY;
#   production đã có nên bị LOẠI khỏi dump (`--exclude-table-data`).
set -euo pipefail

cd "$(dirname "$0")/.."
SLUG="${1:-tp-form-07}"
OUT="${2:-${SLUG}.sql}"
COMPOSE="docker compose -f docker/docker-compose.yml"

pg() { $COMPOSE exec -T postgres "$@"; }

if ! pg pg_isready -U toeic -d toeic >/dev/null 2>&1; then
  echo "Postgres của stack dev không chạy. Bật nó trước:" >&2
  echo "  $COMPOSE up postgres -d" >&2
  exit 1
fi

echo "1/4  Sao chép toeic -> toeic_export (bản gốc không bị đụng tới)"
pg psql -U toeic -d postgres -q -c 'DROP DATABASE IF EXISTS toeic_export;'
pg psql -U toeic -d postgres -q -c 'CREATE DATABASE toeic_export;'
pg pg_dump -U toeic -d toeic | pg psql -U toeic -d toeic_export -q -v ON_ERROR_STOP=1 -o /dev/null

echo "2/4  Xoá mọi bảng ngoài tập bảng của đề, lọc xuống đúng test $SLUG"
pg psql -U toeic -d toeic_export -v ON_ERROR_STOP=1 -v slug="$SLUG" <<'SQL'
-- Gỡ quyền tác giả (cột nullable trỏ users) trước khi xoá users.
DO $$ DECLARE r record; BEGIN FOR r IN
  SELECT c.conrelid::regclass AS tbl, a.attname AS col
  FROM pg_constraint c
  JOIN unnest(c.conkey) k(attnum) ON true
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
  WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass AND NOT a.attnotnull
LOOP EXECUTE format('UPDATE %s SET %I = NULL WHERE %I IS NOT NULL', r.tbl, r.col, r.col); END LOOP;
END $$;

-- Xoá MỌI bảng không nằm trong tập giữ lại (trên bản sao, không ảnh hưởng dev).
-- Dùng TRUNCATE ... CASCADE: cascade đi theo chiều con → cha (từ bảng đang xoá
-- đến các bảng khác trỏ vào nó). Bảng giữ là CHA của bảng lịch sử (attempt →
-- practice_test) nên cascade không chạm tới bảng giữ — chỉ xoá con.
DO $$ DECLARE list text; BEGIN
  SELECT string_agg(DISTINCT format('%I', x.tbl), ', ')
  INTO list
  FROM (
    SELECT c.conrelid::regclass::text AS tbl
    FROM pg_constraint c
    WHERE c.contype = 'f' AND c.conrelid NOT IN (
      'practice_test'::regclass,'practice_test_question'::regclass,'question'::regclass,'question_set'::regclass,
      'question_option'::regclass,'question_label'::regclass,'question_set_label'::regclass,
      'audio_asset'::regclass,'image_asset'::regclass,'score_scale'::regclass,'score_conversion'::regclass,
      'test_collection'::regclass,'users'::regclass,'alembic_version'::regclass)
    UNION
    SELECT t.tablename
    FROM pg_tables t
    WHERE t.schemaname='public' AND t.tablename NOT IN (
      'practice_test','practice_test_question','question','question_set',
      'question_option','question_label','question_set_label',
      'audio_asset','image_asset','score_scale','score_conversion',
      'test_collection','users','alembic_version')
  ) x;
  IF list IS NOT NULL THEN
    EXECUTE 'TRUNCATE ' || list || ' RESTRICT';
  END IF;
END $$;
DELETE FROM users;

-- Lọc các bảng của đề xuống còn đúng một test (con trước, cha sau).
-- Dùng NOT EXISTS thay NOT IN: `question.set_id` NULL với Part 1/2/5, và
-- `NOT IN` gặp NULL trong danh sách thì KHÔNG khớp gì — DELETE âm thầm xoá 0.
DELETE FROM question_option
WHERE NOT EXISTS (
  SELECT 1 FROM practice_test_question tq
  WHERE tq.question_id = question_option.question_id
    AND tq.test_id = (SELECT id FROM practice_test WHERE slug = :'slug'));
DELETE FROM question_label
WHERE NOT EXISTS (
  SELECT 1 FROM practice_test_question tq
  WHERE tq.question_id = question_label.question_id
    AND tq.test_id = (SELECT id FROM practice_test WHERE slug = :'slug'));
DELETE FROM practice_test_question
WHERE test_id <> (SELECT id FROM practice_test WHERE slug = :'slug');
DELETE FROM question
WHERE NOT EXISTS (
  SELECT 1 FROM practice_test_question tq
  WHERE tq.question_id = question.id);
DELETE FROM question_set_label
WHERE NOT EXISTS (
  SELECT 1 FROM question q
  JOIN practice_test_question tq ON tq.question_id = q.id
  WHERE q.set_id = question_set_label.set_id
    AND tq.test_id = (SELECT id FROM practice_test WHERE slug = :'slug'));
DELETE FROM question_set
WHERE NOT EXISTS (
  SELECT 1 FROM question q
  JOIN practice_test_question tq ON tq.question_id = q.id
  WHERE q.set_id = question_set.id
    AND tq.test_id = (SELECT id FROM practice_test WHERE slug = :'slug'));
DELETE FROM practice_test WHERE slug <> :'slug';
DELETE FROM test_collection
WHERE id <> (SELECT collection_id FROM practice_test WHERE slug = :'slug');

-- Media: chỉ giữ row được đề này tham chiếu.
DO $$ DECLARE
  tbl text; col text; not_exists text := '';
BEGIN
  FOR tbl, col IN
    SELECT c.conrelid::regclass::text, a.attname
    FROM pg_constraint c
    JOIN unnest(c.conkey) k(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f' AND c.confrelid = 'audio_asset'::regclass
  LOOP
    not_exists := not_exists || format(' AND NOT EXISTS (SELECT 1 FROM %I t WHERE t.%I = a.id)', tbl, col);
  END LOOP;
  EXECUTE 'DELETE FROM audio_asset a WHERE TRUE' || not_exists;
END $$;
DO $$ DECLARE
  tbl text; col text; not_exists text := '';
BEGIN
  FOR tbl, col IN
    SELECT c.conrelid::regclass::text, a.attname
    FROM pg_constraint c
    JOIN unnest(c.conkey) k(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f' AND c.confrelid = 'image_asset'::regclass
  LOOP
    not_exists := not_exists || format(' AND NOT EXISTS (SELECT 1 FROM %I t WHERE t.%I = i.id)', tbl, col);
  END LOOP;
  EXECUTE 'DELETE FROM image_asset i WHERE TRUE' || not_exists;
END $$;
SQL

echo "3/4  Reset (nếu test đã có trên đích) + dump assets (INSERT ON CONFLICT) + nội dung"
# Đầu file: xoá test cũ theo slug nếu đích đã có, để chạy lại được mà không đụng
# khoá chính. Snapshot id vào bảng tạm TRƯỚC khi xoá practice_test_question —
# các bước sau (question, question_set) không còn nguồn để tra nếu xoá nó trước.
{
  echo "BEGIN;"
  echo "CREATE TEMP TABLE _tp_q AS"
  echo "  SELECT tq.question_id, q.set_id"
  echo "  FROM practice_test_question tq"
  echo "  JOIN question q ON q.id = tq.question_id"
  echo "  WHERE tq.test_id = (SELECT id FROM practice_test WHERE slug = '$SLUG');"
  echo "DELETE FROM question_option WHERE question_id IN (SELECT question_id FROM _tp_q);"
  echo "DELETE FROM question_label WHERE question_id IN (SELECT question_id FROM _tp_q);"
  echo "DELETE FROM question_set_label WHERE set_id IN ("
  echo "  SELECT DISTINCT set_id FROM _tp_q WHERE set_id IS NOT NULL);"
  echo "DELETE FROM practice_test_question"
  echo "  WHERE test_id = (SELECT id FROM practice_test WHERE slug = '$SLUG');"
  echo "DELETE FROM question WHERE id IN (SELECT question_id FROM _tp_q);"
  echo "DELETE FROM question_set WHERE id IN ("
  echo "  SELECT DISTINCT set_id FROM _tp_q WHERE set_id IS NOT NULL);"
  echo "DELETE FROM attempt WHERE test_id = (SELECT id FROM practice_test WHERE slug = '$SLUG');"
  echo "DELETE FROM practice_test WHERE slug = '$SLUG';"
  echo "DROP TABLE _tp_q;"
  echo "COMMIT;"
} > "$OUT"
# Assets của đề (đã lọc trong toeic_export) xuất thành INSERT ... ON CONFLICT
# DO NOTHING: production có thể đã có sẵn một phần (media sync trước), chèn lại
# bản COPY thuần sẽ đụng khoá chính và dừng nửa chừng.
pg pg_dump -U toeic -d toeic_export --data-only \
  --table=audio_asset --table=image_asset \
  > "$OUT.assets.pg"
python3 - "$OUT.assets.pg" "$OUT" <<'PY'
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
with open(dst, "a") as out:
    out.write("-- assets của đề, chèn an toàn nếu production chưa có\n")
    for table in ("audio_asset", "image_asset"):
        m = re.search(
            r"^COPY public\." + table + r" \((.*?)\) FROM stdin;\n(.*?)\n\\\.",
            text, re.S | re.M,
        )
        if not m:
            continue
        cols = m.group(1)
        col_list = [c.strip() for c in cols.split(",")]
        assign = ", ".join(f"{c} = EXCLUDED.{c}" for c in col_list if c != "id")
        for line in m.group(2).strip().splitlines():
            if not line:
                continue
            # Dùng E'' để `\n`/`\t` (COPY đã escape) thành ký tự thật trong SQL.
            # KHÔNG nhân đôi backslash: trong COPY một backslash thật được ghi là
            # `\\`, E'' đọc `\\` thành một backslash — để nguyên là đúng.
            vals = ",".join(
                "E'" + c.replace("'", "''") + "'" for c in line.split("\t")
            )
            out.write(
                f"INSERT INTO {table} ({cols}) VALUES ({vals}) "
                f"ON CONFLICT (id) DO UPDATE SET {assign};\n"
            )
PY
rm -f "$OUT.assets.pg"
pg pg_dump -U toeic -d toeic_export --data-only \
  --exclude-table-data=score_scale \
  --exclude-table-data=score_conversion \
  --exclude-table-data=test_collection \
  --exclude-table-data=audio_asset \
  --exclude-table-data=image_asset \
  --exclude-table-data=alembic_version >> "$OUT"
echo "4/4  Dọn bản sao"
pg psql -U toeic -d postgres -q -c 'DROP DATABASE IF EXISTS toeic_export;'

echo
echo "Xong: $OUT ($(wc -c < "$OUT" | tr -d ' ') byte)"
echo "Nội dung dump gồm đúng 1 test:"
grep -c '^COPY public.practice_test ' "$OUT" || true
echo
echo "Nạp lên Supabase:"
echo "  docker run --rm -i postgres:17 psql \"\$SUPABASE_URL\" -v ON_ERROR_STOP=1 -q < $OUT"