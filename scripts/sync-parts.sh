#!/usr/bin/env bash
# Đồng bộ nội dung CHIẾN THUẬT Part 1–7 từ markdown vào database.
#
# Một chiều: `apps/web/content/parts/part-N.md` là nguồn soạn, `part_tactics`
# là thứ web đọc lúc render (production container không có thư mục content —
# xem `app/models/part_practice.py`). Chạy lại bao nhiêu lần cũng vô hại:
# UPSERT theo `part`, và `updated_at` chỉ nhích khi body thật sự đổi.
#
# Cách dùng:
#   scripts/sync-parts.sh              # DB dev (container postgres)
#   SUPABASE_URL=... scripts/sync-parts.sh --prod
#
# h1 đầu tệp bị cắt: tiêu đề đã có ở PageHeader, cùng luật với lesson ngữ pháp.
set -euo pipefail

cd "$(dirname "$0")/.."
MODE="${1:-dev}"

SQL=$(python3 - <<'PY'
import pathlib, sys

lines = ["BEGIN;"]
for p in sorted(pathlib.Path("apps/web/content/parts").glob("part-*.md")):
    part = int(p.stem.split("-")[1])
    body = p.read_text(encoding="utf-8")
    if body.startswith("# "):
        body = body.split("\n", 1)[1].lstrip("\n")
    escaped = body.replace("'", "''")
    lines.append(
        "INSERT INTO part_tactics (part, body) VALUES "
        f"({part}, E'{escaped.replace(chr(92), chr(92)+chr(92))}') "
        "ON CONFLICT (part) DO UPDATE SET body = EXCLUDED.body, "
        "updated_at = now() WHERE part_tactics.body IS DISTINCT FROM EXCLUDED.body;"
    )
lines.append("COMMIT;")
print("\n".join(lines))
PY
)

if [ "$MODE" = "--prod" ]; then
  if [ -z "${SUPABASE_URL:-}" ]; then
    echo "--prod cần SUPABASE_URL (xem SYNC-TEST-TO-PRODUCTION.md)." >&2
    exit 1
  fi
  printf '%s\n' "$SQL" | docker run --rm -i postgres:17 psql "$SUPABASE_URL" -v ON_ERROR_STOP=1 -q
  target="production"
else
  printf '%s\n' "$SQL" | docker compose -f docker/docker-compose.yml exec -T postgres psql -U toeic -d toeic -v ON_ERROR_STOP=1 -q
  target="dev"
fi

echo "part_tactics ($target):"
if [ "$MODE" = "--prod" ]; then
  docker run --rm -i postgres:17 psql "$SUPABASE_URL" -t -c "SELECT part, length(body) FROM part_tactics ORDER BY part"
else
  docker compose -f docker/docker-compose.yml exec -T postgres psql -U toeic -d toeic -t -c "SELECT part, length(body) FROM part_tactics ORDER BY part"
fi
