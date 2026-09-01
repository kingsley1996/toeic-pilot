-- Xoá tp-form-06 và tp-form-07 cùng mọi thứ phụ thuộc.
--
-- Chạy:  psql "$PROD_DB" -v ON_ERROR_STOP=1 -f scripts/drop_tests.sql
--
-- Ba điều quyết định tệp này đúng hay hỏng:
--
--   * **Chụp id TRƯỚC khi xoá.** Sau khi `practice_test_question` mất, không còn
--     đường nào suy ra câu nào thuộc đề nào. Ba bảng tạm giữ lại danh sách.
--   * **Chỉ xoá câu KHÔNG thuộc đề khác.** `practice_test_question` là bảng nối
--     nhiều-nhiều: một câu dùng chung với đề thứ ba mà bị xoá là làm hỏng đề đó.
--     Điều kiện `NOT EXISTS` bên dưới là cái chặn duy nhất.
--   * **Thứ tự theo luật khoá ngoại**, và hai luật RESTRICT là lý do:
--     `attempt_item.question_id` và `attempt_item.selected_option_id` đều chặn.
--     Xoá `attempt` trước sẽ CASCADE hết `attempt_item`, gỡ cả hai cùng lúc.
--
-- Cái mất IM LẶNG mà không luật nào cản: `coach_conversation` và
-- `coach_explanation` đều CASCADE theo câu hỏi. Cái thứ nhất là hội thoại thật
-- của người học với trợ lý; cái thứ hai chỉ là cache, dựng lại được nhưng tốn
-- tiền LLM. Đếm chúng trước khi chạy.

BEGIN;

CREATE TEMP TABLE doomed_test ON COMMIT DROP AS
SELECT id FROM practice_test WHERE slug IN ('tp-form-06', 'tp-form-07');

-- Chỉ những câu KHÔNG còn đề nào khác dùng tới.
CREATE TEMP TABLE doomed_question ON COMMIT DROP AS
SELECT DISTINCT ptq.question_id AS id
FROM practice_test_question ptq
WHERE ptq.test_id IN (SELECT id FROM doomed_test)
  AND NOT EXISTS (
    SELECT 1 FROM practice_test_question other
    WHERE other.question_id = ptq.question_id
      AND other.test_id NOT IN (SELECT id FROM doomed_test)
  );

-- Chỉ những cụm mà MỌI câu của nó đều nằm trong danh sách xoá.
CREATE TEMP TABLE doomed_set ON COMMIT DROP AS
SELECT DISTINCT q.set_id AS id
FROM question q
WHERE q.set_id IS NOT NULL
  AND q.id IN (SELECT id FROM doomed_question)
  AND NOT EXISTS (
    SELECT 1 FROM question other
    WHERE other.set_id = q.set_id
      AND other.id NOT IN (SELECT id FROM doomed_question)
  );

-- Mốc để so ở cuối. Đo CHÊNH LỆCH chứ không đo trạng thái tuyệt đối: database
-- có thể đã sẵn có câu mồ côi từ trước, và một con số tuyệt đối ở cuối sẽ đọc
-- ra như báo động do chính lệnh này gây ra.
CREATE TEMP TABLE baseline ON COMMIT DROP AS
SELECT
  (SELECT count(*) FROM question q
     WHERE NOT EXISTS (SELECT 1 FROM practice_test_question p WHERE p.question_id = q.id)) AS mo_coi,
  (SELECT count(*) FROM question_set s
     WHERE NOT EXISTS (SELECT 1 FROM question q WHERE q.set_id = s.id)) AS cum_rong;

-- Những gì sắp mất, in ra trước khi mất.
SELECT 'đề'                AS doi_tuong, count(*) FROM doomed_test
UNION ALL SELECT 'câu',        count(*) FROM doomed_question
UNION ALL SELECT 'cụm',        count(*) FROM doomed_set
UNION ALL SELECT 'lượt thi',   count(*) FROM attempt WHERE test_id IN (SELECT id FROM doomed_test)
UNION ALL SELECT 'hội thoại trợ lý (MẤT)', count(*) FROM coach_conversation
          WHERE question_id IN (SELECT id FROM doomed_question)
             OR attempt_id IN (SELECT id FROM attempt WHERE test_id IN (SELECT id FROM doomed_test))
UNION ALL SELECT 'giải thích đã cache (MẤT)', count(*) FROM coach_explanation
          WHERE question_id IN (SELECT id FROM doomed_question);

-- 1. Lượt thi trước tiên: CASCADE sẽ dọn `attempt_item`, `attempt_part` và
--    `coach_conversation`, gỡ hai ràng buộc RESTRICT chặn ở bước 3.
DELETE FROM attempt WHERE test_id IN (SELECT id FROM doomed_test);

-- 2. Bảng nối: gỡ RESTRICT của `practice_test_question.question_id`.
DELETE FROM practice_test_question WHERE test_id IN (SELECT id FROM doomed_test);

-- 3. Câu hỏi: CASCADE dọn lựa chọn, nhãn, và phần trợ lý.
DELETE FROM question WHERE id IN (SELECT id FROM doomed_question);

-- 4. Cụm: CASCADE dọn nhãn của cụm.
DELETE FROM question_set WHERE id IN (SELECT id FROM doomed_set);

-- 5. Bản thân đề.
DELETE FROM practice_test WHERE id IN (SELECT id FROM doomed_test);

-- Phải ra 0 ở cả bốn dòng. Hai dòng cuối là CHÊNH LỆCH so với lúc bắt đầu:
-- lệnh này không được để lại câu mồ côi hay cụm rỗng nào mới.
SELECT 'đề còn lại'          AS kiem, count(*)::bigint AS con
  FROM practice_test WHERE slug IN ('tp-form-06', 'tp-form-07')
UNION ALL
SELECT 'câu đáng xoá còn lại', count(*)::bigint
  FROM question WHERE id IN (SELECT id FROM doomed_question)
UNION ALL
SELECT 'câu mồ côi MỚI',
       (SELECT count(*) FROM question q
          WHERE NOT EXISTS (SELECT 1 FROM practice_test_question p WHERE p.question_id = q.id))
       - (SELECT mo_coi FROM baseline)
UNION ALL
SELECT 'cụm rỗng MỚI',
       (SELECT count(*) FROM question_set s
          WHERE NOT EXISTS (SELECT 1 FROM question q WHERE q.set_id = s.id))
       - (SELECT cum_rong FROM baseline);

-- Đổi thành ROLLBACK để chạy thử mà không ghi gì.
COMMIT;
