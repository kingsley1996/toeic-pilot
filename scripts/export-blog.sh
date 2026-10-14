#!/usr/bin/env bash
# Đồng bộ bài blog từ dev lên production (Supabase).
#
# Một bảng duy nhất, không ai tham chiếu tới: upsert theo `slug`, chạy lại
# tự sửa. `created_by`/`published_by` về NULL vì UUID user dev không tồn tại
# trên prod (cột ghi nhận tác giả thật là `author_name`, vẫn đi theo).
# Ảnh bìa nằm trong git (public/blog/) nên Vercel tự phục vụ — không có media
# nào phải push như audio (xem SYNC-TEST-TO-PRODUCTION §5b).
#
# Điều kiện:
#   * Production đã chạy migration 099 (bảng blog_post tồn tại).
#   * $SUPABASE_URL set trong .env.
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-/tmp/opencode/blog-sync.sql}"

echo "Xuất blog_post dev -> $OUT"
apps/api/.venv/bin/python scripts/export-blog-posts.py > "$OUT"

echo
echo "Xong: $OUT ($(wc -c < "$OUT" | tr -d ' ') byte)"
echo "Diễn tập scratch trước (SYNC-TEST-TO-PRODUCTION §5b), rồi nạp lên production:"
echo "  docker run --rm -i postgres:17 psql \"\$SUPABASE_URL\" -v ON_ERROR_STOP=1 -q < $OUT"
