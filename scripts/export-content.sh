#!/usr/bin/env bash
# Rút NỘI DUNG khỏi database dev để đẩy lên production.
#
# Không bao giờ ghi vào `toeic`. Nó dựng một bản sao (`toeic_export`), dọn trên
# bản sao ấy, rồi dump ra. Xem scripts/export-content.sql cho lằn ranh giữa
# nội dung và lịch sử học, và planning/ADR-014-DEPLOY-FREE.md §11 cho lý do.
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-content.sql}"
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

echo "2/4  Bỏ lịch sử người học, gỡ quyền tác giả"
pg psql -U toeic -d toeic_export -q -v ON_ERROR_STOP=1 < scripts/export-content.sql

echo "3/4  Dump dữ liệu"
pg pg_dump -U toeic -d toeic_export --data-only \
  --exclude-table-data=alembic_version > "$OUT"

echo "4/4  Dọn bản sao"
pg psql -U toeic -d postgres -q -c 'DROP DATABASE IF EXISTS toeic_export;'

echo
echo "Xong: $OUT ($(wc -c < "$OUT" | tr -d ' ') byte)"
echo "Nạp lên Supabase — dùng ảnh postgres:17 để khỏi cài psql lên máy:"
echo
echo "  docker run --rm -i postgres:17 psql \"\$SUPABASE_URL\" \\"
echo "    -v ON_ERROR_STOP=1 -q < scripts/import-content.sql"
echo "  docker run --rm -i postgres:17 psql \"\$SUPABASE_URL\" \\"
echo "    -v ON_ERROR_STOP=1 -q < $OUT"
