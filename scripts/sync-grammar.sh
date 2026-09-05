#!/usr/bin/env bash
# Đồng bộ nội dung NGỮ PHÁP từ DB dev sang production (Supabase).
#
# Grammar khác đề thi: không media, không phụ thuộc user — chỉ ba bảng nội dung
# (`grammar_topic`, `grammar_lesson`, `grammar_lesson_question`) cộng một hàng
# `daily_task_slot` mà seed-lười của production không tự sinh (nó chỉ chạy khi
# bảng khe còn trống). Vì production chưa từng có grammar, "đồng bộ" = nạp lại
# trọn bộ: TRUNCATE 5 bảng grammar rồi INSERT từ dev, trong MỘT transaction —
# hoặc cả cây lên đúng, hoặc không có gì thay đổi.
#
# Hai cửa kiểm TRƯỚC khi chạm production, cả hai đều là kiểu hỏng im lặng:
#   · production chưa chạy migration grammar (057+) → INSERT chết giữa chừng;
#   · lesson practice gắn câu chỉ tồn tại ở dev → production phục vụ bài tập
#     thiếu câu mà không báo.
#
# Cột truy vết (`created_by`/`updated_by`/`published_by`) bị NULL hoá: chúng trỏ
# vào user DEV, không tồn tại ở production, và FK sẽ từ chối — giá của một con
# dấu "ai soạn bài" không đáng một bản sao users.
#
# Cách dùng:
#   SUPABASE_URL=postgresql://... scripts/sync-grammar.sh            # nạp thẳng
#   scripts/sync-grammar.sh --dry-run [file.sql]                     # chỉ sinh SQL
#
# SUPABASE_URL lấy từ đâu: connection string production nằm trong `.env` gốc
# (bị comment lại — xem `SYNC-TEST-TO-PRODUCTION.md`). Script KHÔNG tự đọc .env:
# một lệnh vô tình trỏ thẳng vào production là thứ không nên có mặc định.
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker/docker-compose.yml"
DRY_RUN=0
OUT=""
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; OUT="${2:-/tmp/sync-grammar.sql}"; fi

if [ "$DRY_RUN" = 0 ] && [ -z "${SUPABASE_URL:-}" ]; then
  echo "Thiếu SUPABASE_URL. Hoặc đặt biến môi trường, hoặc chạy --dry-run trước." >&2
  exit 1
fi

pg() { $COMPOSE exec -T postgres "$@"; }

if ! pg pg_isready -U toeic -d toeic >/dev/null 2>&1; then
  echo "Postgres của stack dev không chạy. Bật nó trước:" >&2
  echo "  $COMPOSE up postgres -d" >&2
  exit 1
fi

echo "1/4  Kiểm production: bảng grammar phải tồn tại (migration 057+)"
if [ "$DRY_RUN" = 0 ]; then
  TABLES=$(docker run --rm -i postgres:17 psql "$SUPABASE_URL" -t -A \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'grammar%'")
  if [ "$TABLES" -lt 5 ]; then
    echo "Production mới có $TABLES/5 bảng grammar — chạy migration trên prod trước." >&2
    exit 1
  fi
fi

echo "2/4  Kiểm mọi câu mà lesson practice tham chiếu đã ở production"
MISSING=$(pg psql -U toeic -d toeic -t -A -c "
  SELECT count(*) FROM grammar_lesson_question lq
  JOIN grammar_lesson l ON l.id = lq.lesson_id
  WHERE l.status = 'published' AND NOT EXISTS (
    SELECT 1 FROM question q WHERE q.id = lq.question_id AND q.status = 'published')")
if [ "$MISSING" != "0" ]; then
  echo "Dev có $MISSING hàng nối trỏ tới câu chưa published — đề thi chứa chúng" >&2
  echo "chưa được sync (xem SYNC-TEST-TO-PRODUCTION.md). Sửa trước khi nạp." >&2
  exit 1
fi
if [ "$DRY_RUN" = 0 ]; then
  PROD_MISSING=$(docker run --rm -i postgres:17 psql "$SUPABASE_URL" -t -A -c "
    SELECT count(*) FROM (
      SELECT DISTINCT question_id FROM grammar_lesson_question) lq
    WHERE NOT EXISTS (SELECT 1 FROM question q WHERE q.id = lq.question_id)")
  if [ "$PROD_MISSING" != "0" ]; then
    echo "$PROD_MISSING câu của lesson practice KHÔNG tồn tại ở production." >&2
    exit 1
  fi
fi

echo "3/4  Dựng SQL từ dev"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
{
  echo "BEGIN;"
  # Đủ cả 5 bảng trong một lệnh: FK completion/attempt → lesson bắt buộc liệt kê
  # hết. TRUNCATE là có chủ đích cho LẦN NẠP ĐẦU — production chưa từng có người
  # học grammar; nếu lần nào đó bảng completion/attempt của prod KHÔNG còn trống
  # thì script này sai bài toán, đừng chạy.
  echo "TRUNCATE grammar_attempt, grammar_lesson_completion, grammar_lesson_question, grammar_lesson, grammar_topic;"
  pg pg_dump -U toeic -d toeic --data-only --inserts \
    --table grammar_topic --table grammar_lesson --table grammar_lesson_question \
    | grep -v '^SET\|^SELECT pg_catalog\|^$\|^--'
  echo "INSERT INTO daily_task_slot (id, kind, label, target, xp, position, enabled)
  VALUES ('2b1c0d4e-0000-5000-8000-000000000004', 'grammar_lesson_complete', N'Học ngữ pháp', 3, 10, 4, true)
  ON CONFLICT (id) DO UPDATE SET kind=EXCLUDED.kind, label=EXCLUDED.label, target=EXCLUDED.target;"
  echo "COMMIT;"
} > "$TMP"

# NULL hoá user dev trong cột truy vết. pg_dump in VALUES theo vị trí, không có
# tên cột, nên thay literal uuid là đường ngắn nhất — và uuid đó chỉ xuất hiện
# ở các cột created_by/updated_by/published_by của đúng ba bảng vừa dump.
for uid in $(pg psql -U toeic -d toeic -t -A -c "
    SELECT created_by FROM grammar_topic
    UNION SELECT created_by FROM grammar_lesson"); do
  [ -n "$uid" ] && perl -pi -e "s/'\Q$uid\E'/NULL/g" "$TMP"
done

if [ "$DRY_RUN" = 1 ]; then
  cp "$TMP" "$OUT"
  echo "Dry-run: SQL ở $OUT ($(wc -c < "$OUT" | tr -d ' ') byte). Nạp bằng:"
  echo "  docker run --rm -i postgres:17 psql \"\$SUPABASE_URL\" -v ON_ERROR_STOP=1 -q < $OUT"
  exit 0
fi

echo "4/4  Nạp lên production"
docker run --rm -i postgres:17 psql "$SUPABASE_URL" -v ON_ERROR_STOP=1 -q < "$TMP"

docker run --rm -i postgres:17 psql "$SUPABASE_URL" -t -c \
  "SELECT 'topics: '||count(*) FROM grammar_topic
   UNION SELECT 'lessons published: '||count(*) FROM grammar_lesson WHERE status='published'"
