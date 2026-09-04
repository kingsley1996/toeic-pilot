#!/usr/bin/env bash
# Rút phần GIẢI THÍCH của một đề khỏi dev, thành một tệp SQL chỉ toàn UPDATE.
#
# Vì sao có script riêng thay vì dùng `export-test.sh`: script kia thay CẢ đề,
# và khối reset của nó có dòng
#
#     DELETE FROM attempt WHERE test_id = (SELECT id FROM practice_test WHERE slug = …)
#
# — tức là **xoá sạch lịch sử làm bài của học viên trên đề đó**. Điều ấy vô hại
# hồi các đề còn chưa ai làm; bây giờ production đã có người dùng thật thì nó là
# một thao tác phá dữ liệu, và nó phá im lặng: import chạy xong, báo thành công,
# và thứ mất đi không nằm trong tệp dump nên không ai đối chiếu ra.
#
# Ở đây chỉ có `UPDATE question SET explanation`. Không DELETE, không INSERT,
# không đụng bảng nào khác. Chạy lại được bao nhiêu lần cũng ra cùng một kết quả.
#
# ID CÂU HỎI TRÙNG NHAU GIỮA DEV VÀ PRODUCTION — đã đối chiếu ngày 2026-09-04
# trên `tp-form-06` ở bốn vị trí (1, 7, 101, 200), khớp tuyệt đối, vì lần import
# đầu chép nguyên hàng kèm id. Nhờ vậy khoá đồng bộ là `question.id`, không phải
# một phép ghép theo số thứ tự. Nếu một ngày đề được dựng lại trên production
# bằng đường khác, giả định này hỏng — và §5 dưới đây là chỗ phát hiện ra.
#
#   ./scripts/export-explanations.sh tp-form-06 /tmp/expl-06.sql
#   docker run --rm -i --env-file <env> postgres:17 psql -v ON_ERROR_STOP=1 -q < /tmp/expl-06.sql
set -euo pipefail

cd "$(dirname "$0")/.."
SLUG="${1:?cần slug của đề, ví dụ tp-form-06}"
OUT="${2:-${SLUG}-explanations.sql}"
COMPOSE="docker compose -f docker/docker-compose.yml"

pg() { $COMPOSE exec -T postgres psql -U toeic -d toeic -t -A "$@"; }

if ! $COMPOSE exec -T postgres pg_isready -U toeic -d toeic >/dev/null 2>&1; then
  echo "Postgres của stack dev không chạy. Bật nó trước:" >&2
  echo "  $COMPOSE up postgres -d" >&2
  exit 1
fi

# `format('%L')` là `quote_literal` của chính Postgres, nên chuỗi được escape
# đúng theo luật của Postgres — dấu nháy, backslash, xuống dòng, tất cả.
#
# Đây là chỗ `export-test.sh` từng sai hai lần (xem SYNC §4: `E''` và
# backslash). Tự dựng chuỗi escape bằng sed/awk là mời lại đúng lỗi đó, và lỗi
# ấy không nổ — nó chỉ làm một dấu `\n` thành hai ký tự literal trong bài học
# viên đọc.
BODY=$(pg -c "
SELECT format('UPDATE question SET explanation = %L WHERE id = %L;', q.explanation, q.id)
FROM practice_test pt
JOIN practice_test_question ptq ON ptq.test_id = pt.id
JOIN question q ON q.id = ptq.question_id
WHERE pt.slug = '${SLUG}'
  AND q.explanation IS NOT NULL AND q.explanation <> ''
ORDER BY ptq.number;")

COUNT=$(printf '%s\n' "$BODY" | grep -c '^UPDATE ' || true)
if [ "$COUNT" -eq 0 ]; then
  echo "Không có giải thích nào cho '${SLUG}' ở dev. Chạy backfill trước." >&2
  exit 1
fi

{
  echo "-- Giải thích của ${SLUG}, rút từ dev $(date -u +%Y-%m-%dT%H:%M:%SZ)."
  echo "-- ${COUNT} câu. CHỈ UPDATE cột explanation — không xoá, không thêm hàng nào."
  echo "BEGIN;"
  printf '%s\n' "$BODY"
  # Đếm lại NGAY TRONG giao dịch, trước khi COMMIT. Một tệp chạy xong không
  # chứng minh nó chạm đúng số hàng: id không tồn tại thì UPDATE khớp 0 hàng và
  # psql vẫn báo `UPDATE 0`, một dòng không ai đọc trong 170 dòng giống hệt.
  echo "DO \$\$"
  echo "DECLARE n int;"
  echo "BEGIN"
  echo "  SELECT count(*) INTO n FROM practice_test pt"
  echo "  JOIN practice_test_question ptq ON ptq.test_id = pt.id"
  echo "  JOIN question q ON q.id = ptq.question_id"
  echo "  WHERE pt.slug = '${SLUG}' AND q.explanation IS NOT NULL AND q.explanation <> '';"
  echo "  RAISE NOTICE '${SLUG}: % câu có giải thích sau khi cập nhật', n;"
  echo "  IF n < ${COUNT} THEN"
  echo "    RAISE EXCEPTION 'chỉ % câu có giải thích, chờ ít nhất ${COUNT} — id không khớp?', n;"
  echo "  END IF;"
  echo "END \$\$;"
  echo "COMMIT;"
} > "$OUT"

echo "${COUNT} câu → ${OUT}"
echo
echo "Nạp lên production:"
echo "  docker run --rm -i --env-file <env-file> postgres:17 psql -v ON_ERROR_STOP=1 < ${OUT}"
