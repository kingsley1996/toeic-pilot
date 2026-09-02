-- Xoá HÀNG `audio_asset` không còn ai trỏ tới. KHÔNG đụng object trên provider.
--
--     docker run --rm -i postgres:17 psql "$SUPABASE_URL" \
--       -v ON_ERROR_STOP=1 -v expected=4047 < scripts/delete_orphan_audio.sql
--
-- Bản SQL của `app.content.reconcile_media --delete-rows`, dành cho đích mà công
-- cụ Python không nói chuyện được (production).
--
-- **Bốn điều kiện NOT EXISTS phải là ĐỦ MỌI khoá ngoại trỏ vào `audio_asset`.**
-- Thiếu một cột thì lệnh này lặng lẽ xoá thứ đang được dùng — cùng kiểu hỏng đã
-- ghi ở `.claude/rules/frontend.md` về `passage_2_image_id`. Kiểm lại khi schema
-- đổi:
--
--     SELECT c.relname, a.attname FROM pg_constraint con
--     JOIN pg_class c ON c.oid = con.conrelid
--     JOIN pg_class f ON f.oid = con.confrelid
--     JOIN LATERAL unnest(con.conkey) k(att) ON true
--     JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.att
--     WHERE con.contype = 'f' AND f.relname = 'audio_asset';
--
-- `:expected` là con số vừa đếm được, và nó không phải thủ tục cho vui: giữa lúc
-- đếm và lúc xoá, một lượt đồng bộ khác có thể đã đổi trạng thái, và xoá theo con
-- số cũ lúc đó là xoá nhầm. Lệch thì giao dịch nổ và không mất gì.
--
-- Một phép thử nhanh cho thấy điều kiện còn đúng: sau một lượt recast, **không**
-- asset nào ở `engine_version` hiện hành được coi là mồ côi. Thấy có là danh sách
-- tham chiếu đã thiếu cột.

BEGIN;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM audio_asset aa
  WHERE NOT EXISTS (SELECT 1 FROM vocabulary_audio v WHERE v.audio_asset_id = aa.id)
    AND NOT EXISTS (SELECT 1 FROM dictation_item d WHERE d.audio_asset_id = aa.id)
    AND NOT EXISTS (SELECT 1 FROM question q WHERE q.audio_asset_id = aa.id)
    AND NOT EXISTS (SELECT 1 FROM question_set s WHERE s.audio_asset_id = aa.id);
  IF n <> :expected THEN
    RAISE EXCEPTION 'mồ côi = %, không phải % như lúc đo — dừng lại', n, :expected;
  END IF;
  RAISE NOTICE 'xác nhận % hàng mồ côi, đang xoá', n;
END $$;

DELETE FROM audio_asset aa
WHERE NOT EXISTS (SELECT 1 FROM vocabulary_audio v WHERE v.audio_asset_id = aa.id)
  AND NOT EXISTS (SELECT 1 FROM dictation_item d WHERE d.audio_asset_id = aa.id)
  AND NOT EXISTS (SELECT 1 FROM question q WHERE q.audio_asset_id = aa.id)
  AND NOT EXISTS (SELECT 1 FROM question_set s WHERE s.audio_asset_id = aa.id);

COMMIT;
