# Đồng bộ một đề TOEIC mới từ dev lên production

Runbook cho thao tác "đề vừa generate xong trên máy dev, đưa lên production".
Khác với `export-content.sh`/`import-content.sql` (nạp TOÀN BỘ nội dung, dành cho
lần đầu dựng production), thao tác này chỉ thêm **một đề** vào một production đã
có sẵn mọi dữ liệu khác.

## 0. Điều kiện trước

- Production đã có đầy đủ các nội dung cũ (vocab, dictation, đề khác, media của
  chúng) — tức là thao tác này là "bổ sung", không phải "dựng lại".
- Đề mới đã qua toàn bộ pipeline trên máy dev: `plan` → `write` → `check`
  → `graphic`/`photo` → `load` → `backfill_audio` → `attach-images` → `media --push`.
- Connection string Supabase (`$SUPABASE_URL`) có quyền ghi.

## 1. Các bước trên máy dev

```bash
# Nạp nội dung vào DB dev (nếu chưa)
uv run python -m app.content.generate_exam load --slug tp-form-XX --token <editor token>

# Sinh audio (hàng đợi là một truy vấn, chạy lại chỉ tìm thấy ít việc hơn)
uv run python -m app.content.backfill_audio --only questions

# Gắn ảnh đã render (Part 1 + graphic Part 3/4/7). Mặc định chỉ in bảng khớp,
# cần --commit mới ghi — ảnh phải được người xem trước (§8).
uv run python -m app.content.generate_exam attach-images --slug tp-form-XX --commit

# Đẩy media từ đĩa local lên provider (Supabase S3 cho audio, Cloudinary cho ảnh)
uv run python -m app.content.generate_exam media --slug tp-form-XX --push
```

## 2. Export + import lên production — một lệnh

```bash
./scripts/export-test.sh tp-form-XX /tmp/tp-form-XX.sql
cat /tmp/tp-form-XX.sql | docker run --rm -i postgres:17 psql "$SUPABASE_URL" \
  -v ON_ERROR_STOP=1 -q
```

Script `export-test.sh` (đọc từ `scripts/`, chạy trên máy dev, không đụng DB dev):

1. Clone `toeic` → `toeic_export` (bản gốc không bị sửa).
2. Trên bản sao: xoá **mọi bảng ngoài tập bảng của đề** bằng `TRUNCATE ... RESTRICT`
   (không dùng CASCADE — nó lây sang bảng giữ như `practice_test`; `users` bị loại
   khỏi danh sách vì `practice_test` có FK trỏ tới nó, xoá riêng sau).
3. Lọc các bảng của đề xuống còn đúng một test bằng `DELETE ... NOT EXISTS`
   (**không** dùng `NOT IN`: `question.set_id` NULL ở Part 1/2/5, và `NOT IN`
   gặp NULL thì không khớp gì — DELETE âm thầm xoá 0 hàng).
4. Xuất hai phần nối vào một file:
   - **Assets** (`audio_asset`/`image_asset`) dưới dạng
     `INSERT ... ON CONFLICT (id) DO UPDATE SET ...` — production có thể đã có
     sẵn một phần (media sync trước), `DO UPDATE` đảm bảo chạy lại tự sửa.
     Giá trị dùng `E''` để `\n`/`\t` (COPY đã escape) thành ký tự thật; **không**
     nhân đôi backslash — trong COPY một backslash thật được ghi là `\\`, `E''`
     đọc `\\` thành một backslash, để nguyên là đúng.
   - **Nội dung** còn lại qua `pg_dump --data-only`, bỏ `score_scale`,
     `score_conversion`, `test_collection`, `alembic_version` (production đã có
     các bảng tham chiếu này).
5. Dọn bản sao `toeic_export`.

### Đầu file có khối reset (idempotent)

Script chèn một khối `BEGIN ... COMMIT` xoá test cũ theo slug nếu đích đã có,
để chạy lại được mà không đụng khoá chính. Nó **snapshot id vào bảng tạm
`_tp_q` trước khi xoá `practice_test_question`** — các bước sau (`question`,
`question_set`) không còn nguồn để tra nếu xoá bảng nối đó trước.

## 3. Vì sao không dùng export-content cho việc này

`scripts/export-content.sh` dump toàn bộ nội dung dev. Production đã có sẵn các
nội dung cũ, nên nạp lại toàn bộ sẽ đụng khoá chính ở hàng đầu tiên đã tồn tại
và dừng nửa chừng. Thao tác này chỉ chép đúng tập bảng + tập hàng của một đề.

## 4. Các bug đã gặp khi dựng script (ghi lại kẻo lặp)

- **`TRUNCATE ... CASCADE` lây sang bảng giữ.** CASCADE đi từ bảng đang xoá tới
  các bảng trỏ vào nó, nên `attempt` (trỏ `practice_test`) kéo theo cả
  `practice_test`. Dùng `RESTRICT` + loại `users` khỏi danh sách (vì
  `practice_test` có FK tới `users`), xoá `users` riêng sau khi đã NULL hết cột
  tác giả.
- **`NOT IN` gặp NULL trả "không khớp gì".** `question.set_id` NULL ở Part 1/2/5
  làm subquery chứa NULL, `id NOT IN (...)` trả false với mọi hàng, DELETE xoá 0
  mà không báo. Đổi toàn bộ sang `NOT EXISTS`.
- **`CHECK` constraint trong `pg_constraint` có `conrelid='-'`.** Query liệt kê
  bảng phải lọc `c.contype = 'f'`, nếu không `format('%I', '-')` thành lệnh
  `DELETE FROM "-"` báo lỗi `relation "-" does not exist`.
- **Thứ tự xoá con → cha.** `practice_test_question` phải xoá trước `question`
  và `practice_test`; `question_option`/`question_label` trước `question`;
  `question_set_label` trước `question_set`; `attempt` trước `practice_test`.
- **`ON CONFLICT DO NOTHING` không sửa dữ liệu đã tồn tại.** Lần đầu import phát
  hiện production đã có asset (media sync trước), `DO NOTHING` bỏ qua nên một
  lỗi `E''` trong `source_text` không tự sửa khi chạy lại. Đổi thành
  `ON CONFLICT (id) DO UPDATE SET ...`.
- **`E''` và backslash.** Nhân đôi backslash trong `E''` biến `\n` thành literal
  `\n` thay vì xuống dòng. COPY đã escape sẵn, chỉ cần escape quote đơn.

## 5. Sau khi import

Kiểm tra nhanh trên production:

```sql
SELECT count(*) FROM practice_test WHERE slug = 'tp-form-XX';
SELECT count(*) FROM practice_test_question
WHERE test_id = (SELECT id FROM practice_test WHERE slug = 'tp-form-XX');
-- audio: Part 1/2 trên câu + Part 3/4 trên question_set
SELECT count(*) FROM audio_asset WHERE id IN (
  SELECT q.audio_asset_id FROM question q
  JOIN practice_test_question tq ON tq.question_id = q.id
  WHERE tq.test_id = (SELECT id FROM practice_test WHERE slug = 'tp-form-XX'));
```

Bước publish vẫn là quyết định của người soạn (qua admin UI), không tự động —
đúng tinh thần "không tự publish" (§8 của kế hoạch đề).

## 6. Bảo mật

Connection string chứa mật khẩu — nếu từng dán vào chat/lỗi, hãy **rotate
password trên Supabase** sau khi xong việc. Không commit `$SUPABASE_URL` hay bản
dump vào git.
