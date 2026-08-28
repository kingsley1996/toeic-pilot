-- Tách NỘI DUNG khỏi LỊCH SỬ HỌC, để đẩy lên production.
--
-- Chạy trên một BẢN SAO của database dev, không bao giờ trên chính nó.
--
-- Lằn ranh không do người viết file này nghĩ ra — nó đã nằm trong schema:
-- quyền tác giả trên nội dung (`created_by`, `published_by`, `reviewed_by`)
-- đều NULLABLE, còn lịch sử của một người học (`user_id`) đều NOT NULL. Nên
-- danh sách bảng dưới đây được suy ra từ catalog chứ không gõ tay: thêm một
-- bảng mới về sau, kịch bản này tự biết nó thuộc phía nào.

BEGIN;

-- 1. Gỡ quyền tác giả. Nội dung ở production không thuộc về tài khoản dev nào.
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

-- 2. Bỏ lịch sử người học: mọi bảng có khoá ngoại NOT NULL trỏ vào `users`,
--    cascade xuống con của chúng (attempt_item, attempt_part, coach_message).
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

-- 3. Nhật ký gọi LLM ở máy dev. `user_id` của nó nullable nên bước 2 không
--    chạm tới, nhưng đây là nhật ký chứ không phải nội dung.
TRUNCATE ai_interaction;

-- 4. Không còn gì trỏ tới users nữa.
DELETE FROM users;

COMMIT;
