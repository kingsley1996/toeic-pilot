#!/usr/bin/env bash
# Đồng bộ MỘT đề placement lên production. Chỉ hàng đề + bảng nối, không câu hỏi.
#
# Vì sao không dùng `export-test.sh`: đề placement KHÔNG có câu hỏi của riêng nó
# — 84 câu của nó là câu của `tp-test-09`, đã nằm trên production từ lâu. Script
# kia xuất cả câu hỏi và mở đầu bằng một khối reset xoá câu của đề theo slug;
# chạy nó cho đề placement sẽ **xoá luôn câu của `tp-test-09`**, tức thủng cả
# một đề 200 câu mà bản dump không hề nhắc tới. Nó cũng có
# `DELETE FROM attempt ... WHERE test_id = …`, tức xoá lịch sử làm bài.
#
# Ở đây chỉ có: một hàng `practice_test`, 84 hàng `practice_test_question`, và
# một `UPDATE` lưu trữ đề placement cũ. Không đụng `question` một dòng nào.
#
# ID CÂU HỎI TRÙNG NHAU GIỮA DEV VÀ PRODUCTION — cùng giả định mà
# `export-explanations.sh` đã ghi, và §1 của tệp sinh ra là chỗ kiểm nó: thiếu
# một câu thì cả giao dịch bị huỷ, chứ không phải đề placement ngắn đi lặng lẽ.
#
#   ./scripts/export-placement.sh tp-placement-02 /tmp/p02.sql
#   docker run --rm -i --env-file <env> postgres:17 psql -v ON_ERROR_STOP=1 -q < /tmp/p02.sql
set -euo pipefail

cd "$(dirname "$0")/.."
SLUG="${1:?cần slug đề placement, ví dụ tp-placement-02}"
OUT="${2:-${SLUG}.sql}"
COMPOSE="docker compose -f docker/docker-compose.yml"

pg() { $COMPOSE exec -T postgres psql -U toeic -d toeic -At -v ON_ERROR_STOP=1 "$@"; }

if ! $COMPOSE exec -T postgres pg_isready -U toeic -d toeic >/dev/null 2>&1; then
  echo "Postgres của stack dev không chạy: $COMPOSE up postgres -d" >&2
  exit 1
fi

COUNT=$(pg -c "SELECT count(*) FROM practice_test_question ptq
  JOIN practice_test t ON t.id = ptq.test_id WHERE t.slug = '$SLUG';")
if [ "$COUNT" -eq 0 ]; then
  echo "Không có đề $SLUG trên dev, hoặc nó chưa có câu nào." >&2
  exit 1
fi

{
  echo "-- $SLUG: $COUNT câu. Sinh bởi scripts/export-placement.sh, $(date -u +%FT%TZ)."
  echo "BEGIN;"
  echo
  echo "-- 1. Đề. Chạy lại thì cập nhật, không đụng khoá chính."
  pg -c "SELECT format(
      'INSERT INTO practice_test (id, slug, title, description, kind, status, is_placement,'
      ' time_limit_seconds, score_scale_slug, position) '
      'VALUES (%L, %L, %L, %L, %L, %L, true, %s, %L, 0) '
      'ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title,'
      ' description = EXCLUDED.description, kind = EXCLUDED.kind, status = EXCLUDED.status,'
      ' is_placement = true, time_limit_seconds = EXCLUDED.time_limit_seconds,'
      ' score_scale_slug = EXCLUDED.score_scale_slug;',
      id, slug, title, description, kind, status, time_limit_seconds, score_scale_slug)
    FROM practice_test WHERE slug = '$SLUG';"
  echo
  echo "-- 2. Danh sách câu, vào bảng tạm trước khi kiểm."
  echo "CREATE TEMP TABLE _place (number smallint, question_id uuid) ON COMMIT DROP;"
  pg -c "SELECT format('INSERT INTO _place VALUES (%s, %L);', ptq.number, ptq.question_id)
    FROM practice_test_question ptq JOIN practice_test t ON t.id = ptq.test_id
    WHERE t.slug = '$SLUG' ORDER BY ptq.number;"
  cat <<SQL

-- 3. Cổng. Một câu thiếu, chưa xuất bản, hay nằm dưới một cụm còn nháp thì đề
--    placement NGẮN ĐI mà không có gì báo: \`open_attempt\` lọc published ở cả
--    hai tầng, nên câu ấy biến mất khỏi lượt làm và tổng 84 câu — con số cả
--    lập luận §0 của SPEC-PLACEMENT dựa vào — lặng lẽ sai.
DO \$\$
DECLARE bad int;
BEGIN
  SELECT count(*) INTO bad FROM _place p
   WHERE NOT EXISTS (
     SELECT 1 FROM question q
      LEFT JOIN question_set qs ON qs.id = q.set_id
      WHERE q.id = p.question_id AND q.status = 'published'
        AND (q.set_id IS NULL OR qs.status = 'published')
   );
  IF bad > 0 THEN
    RAISE EXCEPTION 'production thiếu % câu (chưa có, chưa xuất bản, hoặc cụm còn nháp)', bad;
  END IF;
END \$\$;

-- 4. Bảng nối. Xoá rồi ghi lại: chạy lại cho đúng cùng một kết quả.
DELETE FROM practice_test_question
 WHERE test_id = (SELECT id FROM practice_test WHERE slug = '$SLUG');
INSERT INTO practice_test_question (test_id, question_id, position, number)
SELECT (SELECT id FROM practice_test WHERE slug = '$SLUG'), p.question_id, p.number, p.number
  FROM _place p;

-- 5. Một đề placement published mỗi thời điểm. \`_placement_test()\` chọn bằng
--    \`db.scalar\` trên (is_placement, published); hai đề cùng thoả thì nó lấy một
--    cái tuỳ ý, và hai người học làm hai đề khác nhau mà kết quả vẫn đem so với
--    nhau. Đề cũ chuyển \`archived\`, KHÔNG xoá — lượt làm cũ vẫn trỏ vào nó.
UPDATE practice_test SET status = 'archived'
 WHERE is_placement AND status = 'published' AND slug <> '$SLUG';

-- 6. Đếm lại TRONG giao dịch. Sai thì huỷ, không để lại một đề dở dang.
DO \$\$
DECLARE rows int; live int;
BEGIN
  SELECT count(*) INTO rows FROM practice_test_question
   WHERE test_id = (SELECT id FROM practice_test WHERE slug = '$SLUG');
  IF rows <> $COUNT THEN
    RAISE EXCEPTION 'ghi % câu, cần $COUNT', rows;
  END IF;
  SELECT count(*) INTO live FROM practice_test
   WHERE is_placement AND status = 'published';
  IF live <> 1 THEN
    RAISE EXCEPTION 'có % đề placement đang published, phải đúng một', live;
  END IF;
  RAISE NOTICE 'OK: $SLUG, % câu, đúng một đề placement published', rows;
END \$\$;

COMMIT;
SQL
} > "$OUT"

echo "$OUT  ($COUNT câu)"
