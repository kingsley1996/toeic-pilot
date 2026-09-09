#!/usr/bin/env bash
# Đồng bộ collocation từ dev lên production (Supabase) — khuôn export-test.sh.
#
# Chỉ chép đúng tập hàng collocation: entry `part_of_speech='phrase'`, detail
# của chúng, topic gắn vào, và asset audio mà các entry trỏ tới. Mọi INSERT
# được viết lại thành ON CONFLICT (khóa chính) DO UPDATE nên chạy lại tự sửa;
# production không bị đụng hàng nào ngoài tập này.
#
# Điều kiện:
#   * push_media đã đẩy audio lên object store (khoá content-addressed).
#   * Production đã chạy migration 079 (bảng collocation_detail tồn tại).
#   * $SUPABASE_URL set trong .env.
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-/tmp/opencode/collocation-sync.sql}"
COMPOSE="docker compose -f docker/docker-compose.yml"

pg() { $COMPOSE exec -T postgres "$@"; }

if ! pg pg_isready -U toeic -d toeic >/dev/null 2>&1; then
  echo "Postgres dev không chạy." >&2
  exit 1
fi

echo "1/4  Sao chép toeic -> toeic_export"
pg psql -U toeic -d postgres -q -c 'DROP DATABASE IF EXISTS toeic_export;'
pg psql -U toeic -d postgres -q -c 'CREATE DATABASE toeic_export;'
pg pg_dump -U toeic -d toeic | pg psql -U toeic -d toeic_export -q -v ON_ERROR_STOP=1 -o /dev/null

echo "2/4  Cắt bản sao xuống còn tập hàng collocation"
pg psql -U toeic -d toeic_export -q -v ON_ERROR_STOP=1 <<'SQL'
-- 2a. Dọn lịch sử học TRƯỚC, theo đúng cách `export-content.sql` đã học được:
--     CHỈ bảng có FK NOT NULL trỏ `users` bị TRUNCATE CASCADE. Bảng FK nullable
--     (audio_asset.created_by...) phải sống sót — CASCADE từ chúng sẽ quét mất
--     cả vocabulary_entry lẫn vocabulary_audio.
DO $$
DECLARE list text;
BEGIN
  SELECT string_agg(DISTINCT c.conrelid::regclass::text, ', ')
  INTO list
  FROM pg_constraint c
  JOIN unnest(c.conkey) k(attnum) ON true
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
  WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass AND a.attnotnull;
  EXECUTE 'TRUNCATE ' || list || ' CASCADE';
END $$;

-- 2b. Gỡ quyền tác giả: cột nullable trỏ users, nội dung ở production không
--     thuộc tài khoản dev nào.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.conrelid::regclass AS tbl, a.attname AS col
    FROM pg_constraint c
    JOIN unnest(c.conkey) k(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass AND NOT a.attnotnull
  LOOP
    EXECUTE format('UPDATE %s SET %I = NULL WHERE %I IS NOT NULL', r.tbl, r.col, r.col);
  END LOOP;
END $$;
DELETE FROM users;

-- 2c. Bây giờ cắt về tập collocation; attempt* đã gone nên FK không còn chặn.
--     question/dictation_item/question_set trỏ audio_asset bằng cột NULLABLE
--     (đề thi sống sót qua bước 2a vì users-FK của chúng nullable) — gỡ liên
--     kết trước trước rồi xoá, tránh TRUNCATE CASCADE quét mất audio_asset.
--     dictation_item xoá TRƯỚC khi gỡ liên kết: CHECK của nó đòi published
--     phải có audio, gỡ trước là vi phạm.
DELETE FROM dictation_item;
DELETE FROM attempt_item;
DELETE FROM attempt;
DELETE FROM attempt_part;
DELETE FROM practice_test_question;
DELETE FROM coach_conversation;
DELETE FROM coach_explanation;
DELETE FROM question_label;
DELETE FROM question_option;
DELETE FROM grammar_lesson_question;
DELETE FROM grammar_attempt;
DELETE FROM part_session_item;
DELETE FROM part_session;
DELETE FROM question;
DELETE FROM question_set;
UPDATE question SET audio_asset_id = NULL WHERE audio_asset_id IS NOT NULL;
UPDATE question_set SET audio_asset_id = NULL WHERE audio_asset_id IS NOT NULL;
DELETE FROM vocabulary_topic WHERE entry_id NOT IN (
  SELECT id FROM vocabulary_entry WHERE part_of_speech = 'phrase');
DELETE FROM vocabulary_audio WHERE entry_id NOT IN (
  SELECT id FROM vocabulary_entry WHERE part_of_speech = 'phrase');
DELETE FROM vocabulary_entry WHERE part_of_speech <> 'phrase';
DELETE FROM topic WHERE id NOT IN (SELECT topic_id FROM vocabulary_topic);
DELETE FROM audio_asset WHERE id NOT IN (SELECT audio_asset_id FROM vocabulary_audio);
DELETE FROM image_asset;
SQL

echo "3/4  Dump + viết lại thành ON CONFLICT DO UPDATE"
# Chỉ đúng tám bảng nội dung của đợt này (cuốn "300 collocations…" phải đi
# cùng topic); phần cài đặt (badge_rule, level_tier, progression_setting...)
# production đã có từ trước.
pg pg_dump -U toeic -d toeic_export --data-only --column-inserts \
  --table=audio_asset \
  --table=topic \
  --table=vocabulary_entry \
  --table=collocation_detail \
  --table=vocabulary_audio \
  --table=vocabulary_topic \
  --table=vocabulary_collection \
  --table=vocabulary_collection_item \
  | python3 "$(dirname "$0")/.export-add-on-conflict.py" > "$OUT"

echo "4/4  Dọn bản sao"
pg psql -U toeic -d postgres -q -c 'DROP DATABASE IF EXISTS toeic_export;'

echo
echo "Xong: $OUT ($(wc -c < "$OUT" | tr -d ' ') byte)"
echo "Nạp lên production:"
echo "  docker run --rm -i postgres:17 psql \"\$SUPABASE_URL\" -v ON_ERROR_STOP=1 -q < $OUT"
