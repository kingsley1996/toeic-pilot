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

## 5b. Đồng bộ TỪ VỰNG và DICTATION (khác hẳn đồng bộ một đề)

`scripts/export-test.sh` chép một đề và **cố ý nổ** nếu đích đã có nó — một đề chỉ
nạp một lần, trùng nghĩa là sai. Từ vựng và dictation ngược lại: đích đã có phần
cũ, việc cần làm là *thêm phần mới rồi sửa phần cũ tại chỗ*. Nên chúng có đường
riêng:

```bash
cd apps/api
uv run python scripts/dump_learning_content.py > /tmp/learning.sql
docker run --rm -i postgres:17 psql "$SUPABASE_URL" -v ON_ERROR_STOP=1 -q < /tmp/learning.sql
```

Mọi hàng đi bằng `ON CONFLICT ... DO UPDATE`, nên chạy lại không tốn gì.

**Vì sao phải UPDATE chứ không chỉ INSERT phần mới.** `source_hash` gồm cả
`engine_version`, nên một lượt `backfill_audio --force` tạo hàng `audio_asset`
MỚI và trỏ `vocabulary_audio` sang id mới. Chỉ chèn phần mới thì đích giữ nguyên
liên kết cũ và **ở lại dàn giọng cũ vĩnh viễn** — im lặng, vì mọi clip vẫn phát
được. Đây chính là cách production tụt lại phía sau dev suốt nhiều sprint.

**Phải `push_media` TRƯỚC.** Đích dùng chung object store với dev, nên hàng trỏ
tới khoá chưa đẩy sẽ trả 400 ở mọi clip trong khi database trông hoàn hảo. Xem
`.claude/rules/content-pipeline.md`.

**Không đụng lịch sử học.** Danh sách bảng cố ý bỏ `vocabulary_review_state`,
`review_log`, `dictation_attempt`, `topic_session` — chúng trỏ vào
`vocabulary_entry.id` và `dictation_item.id`, mà những id đó không đổi. Cũng vì
vậy tuyệt đối không xoá-rồi-nạp-lại.

**Diễn tập trước khi chạy thật**, vì đây là ghi vào production:

```bash
# 1. dựng scratch có đúng schema
docker compose -f docker/docker-compose.yml exec -T postgres pg_dump -U toeic -d toeic --schema-only > /tmp/schema.sql
# 2. chép TRẠNG THÁI HIỆN TẠI của production vào scratch (chỉ đọc production)
docker run --rm -i postgres:17 pg_dump "$SUPABASE_URL" --data-only --no-owner --no-privileges \
  -t users -t audio_asset -t vocabulary_collection -t vocabulary_collection_item \
  -t topic -t vocabulary_entry -t vocabulary_topic -t vocabulary_audio \
  -t dictation_topic -t dictation_section -t dictation_story -t dictation_item > /tmp/prod_state.sql
# 3. áp learning.sql lên bản sao đó và đếm lại
```

Lần chạy 2026-09-02 diễn tập theo đúng ba bước trên: 303 → 483 từ, 7 → 11 chủ đề,
62 → 134 câu dictation, và cả 3 860 clip từ vựng chuyển sang `engine_version` 3.
Áp hai lần cho ra cùng con số.

Sau khi áp, các hàng `audio_asset` cũ trở thành mồ côi (production giữ chúng, vô
hại — object vẫn còn trên provider). Dọn bằng `reconcile_media --delete-rows`,
là một quyết định riêng.

## 6. Bảo mật

Connection string chứa mật khẩu — nếu từng dán vào chat/lỗi, hãy **rotate
password trên Supabase** sau khi xong việc. Không commit `$SUPABASE_URL` hay bản
dump vào git.
