-- Dọn database đích trước khi nạp bản dump nội dung.
--
-- Cần thiết vì `alembic upgrade head` KHÔNG để lại một schema rỗng: migration
-- 027 và 041/047 có seed sẵn `backdrop_setting` và `pet_species`, nên bản dump
-- đụng khoá chính và việc nạp dừng giữa chừng — các bảng phía sau im lặng không
-- có gì.
--
-- Danh sách suy ra từ catalog chứ không gõ tay, nên một migration seed thêm
-- bảng mới về sau không làm hỏng kịch bản này. Cũng nhờ vậy mà nạp lại được
-- nhiều lần: lần chạy hỏng giữa chừng không để lại trạng thái nửa vời.
--
-- `alembic_version` được giữ nguyên: schema là do Alembic dựng, và bản dump
-- không mang nó theo.

DO $$
DECLARE list text;
BEGIN
  SELECT string_agg(format('%I', tablename), ', ')
  INTO list
  FROM pg_tables
  WHERE schemaname = 'public' AND tablename <> 'alembic_version';
  EXECUTE 'TRUNCATE ' || list || ' CASCADE';
END $$;
