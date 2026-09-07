#!/usr/bin/env bash
# Đồng bộ bảng LOÀI THÚ lên production. Chỉ `pet_species`, không bảng nào khác.
#
# Bảng này gieo LƯỜI ở lần đọc đầu, nên production đã có sẵn các loài mặc định
# với ĐÚNG mã ấy. Vì thế mọi câu lệnh là `INSERT ... ON CONFLICT (code) DO
# UPDATE`: chạy lại được, và không đụng vào con thú ai đang nuôi.
#
# **KHÔNG bao giờ DELETE ở đây.** `pet_state.species` và `pet_owned.code` trỏ vào
# `pet_species.code` mà KHÔNG có khoá ngoại (xem migration của ADR-010), nên
# database sẽ không ngăn: xoá một loài để lại con thú của người ta trỏ vào hư
# không, và nó hiện ra là một ô trống chứ không phải một lỗi. Muốn bỏ một loài
# thì đặt `enabled = false`.
#
#   ./scripts/export-pet-species.sh /tmp/species.sql            # mọi tấm KHÁC creatures
#   ./scripts/export-pet-species.sh /tmp/species.sql all        # cả 3 tấm
#   docker run --rm -i --env-file <env> postgres:17 psql -v ON_ERROR_STOP=1 -q < /tmp/species.sql
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-pet-species.sql}"
SCOPE="${2:-new}"
COMPOSE="docker compose -f docker/docker-compose.yml"

pg() { $COMPOSE exec -T postgres psql -U toeic -d toeic -At -v ON_ERROR_STOP=1 "$@"; }

if ! $COMPOSE exec -T postgres pg_isready -U toeic -d toeic >/dev/null 2>&1; then
  echo "Postgres của stack dev không chạy: $COMPOSE up postgres -d" >&2
  exit 1
fi

if [ "$SCOPE" = "all" ]; then WHERE="TRUE"; else WHERE="sheet <> 'creatures'"; fi
COUNT=$(pg -c "SELECT count(*) FROM pet_species WHERE $WHERE;")
SHEETS=$(pg -c "SELECT string_agg(DISTINCT sheet, ', ' ORDER BY sheet) FROM pet_species WHERE $WHERE;")
[ "$COUNT" -eq 0 ] && { echo "Không có loài nào khớp phạm vi '$SCOPE'." >&2; exit 1; }

{
  echo "-- $COUNT loài, tấm: $SHEETS. scripts/export-pet-species.sh, $(date -u +%FT%TZ)."
  echo "BEGIN;"
  echo
  cat <<'SQL'
-- 1. Cổng. Cột `sheet` đến từ migration 072 và `lines` từ 073, và chúng chạy
--    khi ẢNH API deploy (`api-entrypoint.sh` gọi `alembic upgrade head` trước
--    khi uvicorn nghe cổng). Nạp tệp này TRƯỚC khi API mới lên thì mọi câu
--    INSERT đổ vì không có cột — ồn ào, nên không nguy hiểm. Cổng này chỉ để
--    lời báo nói đúng nguyên nhân thay vì để psql kêu "column does not exist"
--    ở dòng 12.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_name = 'pet_species' AND column_name = 'sheet'
  ) THEN
    RAISE EXCEPTION 'production chưa có pet_species.sheet — deploy API (migration 072) trước';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_name = 'pet_species' AND column_name = 'lines'
  ) THEN
    RAISE EXCEPTION 'production chưa có pet_species.lines — deploy API (migration 073) trước';
  END IF;
END $$;

SQL
  echo "-- 2. Loài. Chạy lại thì cập nhật; không DELETE, không đụng con ai đang nuôi."
  pg -c "SELECT format(
      'INSERT INTO pet_species (code, label, sheet, tile, tier, drop_weight, position, enabled, lines)'
      ' VALUES (%L, %L, %L, %s, %L, %s, %s, %L, %s)'
      ' ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label, sheet = EXCLUDED.sheet,'
      ' tile = EXCLUDED.tile, tier = EXCLUDED.tier, drop_weight = EXCLUDED.drop_weight,'
      ' position = EXCLUDED.position, enabled = EXCLUDED.enabled, lines = EXCLUDED.lines;',
      code, label, sheet, tile, tier, drop_weight, position, enabled,
      COALESCE(quote_nullable(lines::text), 'NULL'))
    FROM pet_species WHERE $WHERE ORDER BY sheet, tile;"
  cat <<SQL

-- 3. Đếm lại TRONG giao dịch.
DO \$\$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM pet_species WHERE $WHERE;
  IF n < $COUNT THEN
    RAISE EXCEPTION 'ghi % loài, cần ít nhất $COUNT', n;
  END IF;
  RAISE NOTICE 'OK: % loài trên các tấm: $SHEETS', n;
END \$\$;

COMMIT;
SQL
} > "$OUT"

echo "$OUT  ($COUNT loài · $SHEETS)"
echo
echo "  Trước khi nạp, production phải có ĐỦ BA thứ — thiếu thứ ba là thú tàng hình:"
echo "    1. ảnh API mới đã deploy  → migration 072 dựng cột \`sheet\`"
echo "    2. web đã deploy          → public/pet/*.png mới có mặt"
echo "    3. rồi mới nạp tệp này"
