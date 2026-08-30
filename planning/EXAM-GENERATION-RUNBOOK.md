# Runbook: sinh trọn một đề TOEIC — từ dòng lệnh tới production

> Hướng dẫn thao tác đầy đủ, cập nhật 2026-08-31. Bản kế hoạch + lý do thiết kế
> nằm ở [`generate-full-toeic.md`](generate-full-toeic.md); bản ghi hiện trạng ở
> [`ROADMAP.md`](ROADMAP.md). Tài liệu này chỉ trả lời một câu: **làm gì, theo
> thứ tự nào, lệnh nào**.

---

## 0. Tổng quan pipeline

```
plan ──► write ──► check ──► graphic/photo ──► load ──► backfill_audio
                                                        │
                          attach-images ◄───────────────┘
                              │
                        media --push ──► check --verify ──► publish ──► sync lên production
```

| Chặng | Lệnh | Sản phẩm |
|---|---|---|
| 1. Blueprint | `plan` | `content/generated/<slug>/blueprint.json` |
| 2. Sinh text | `write` | `paste/*.txt`, `graphics/*.txt` |
| 3. Kiểm | `check` | báo cáo chặn nạp / cần người nhìn |
| 4. Vẽ hình, ảnh | `graphic`, `photo` | `graphic-images/`, `images/` |
| 5. Nạp DB dev | `load` | đề ở trạng thái `draft` |
| 6. Audio | `backfill_audio` | clip mp3 + hàng `audio_asset` |
| 7. Gắn ảnh | `attach-images` | `image_asset_id` / `passage_image_id` |
| 8. Đẩy media | `media --push` | bytes lên Supabase S3 / Cloudinary |
| 9. Đối chiếu đáp án | `check --verify` | đối chiếu đáp án bằng LLM |
| 10. Publish | admin UI | đề hiển thị cho học viên |
| 11. Sync production | `export-test.sh` | đề lên Supabase production |

Mọi lệnh chạy trong `apps/api` với `uv run`, **ngoài luồng** — API không bao giờ
import `app.content` (A4.1).

---

## 1. Chặng 1 — Blueprint (`plan`)

```bash
cd apps/api

# Cách 1: tự sinh bằng model (gợi ý bối cảnh + brief hình)
uv run python -m app.content.generate_exam plan --slug tp-form-08 --part 1 \
  --model bai/glm-5.3-flash
# ...lặp cho từng part 1..7

# Cách 2: wizard tương tác (dẫn từng bước)
uv run python -m app.content.generate_exam interact --slug tp-form-08
```

Blueprint khoá **trước khi** gọi model: số câu, dạng câu, vị trí hình, giọng đọc.
Model chỉ sinh nội dung (bối cảnh, brief hình). `seed` để chạy lại ra cùng chủ
đề. Vị trí hình cố định theo đề thật: Part 3 ba hình ở ba cụm cuối, Part 4 hai
hình, Part 7 năm passage hình rải trong bốn cụm.

## 2. Chặng 2 — Sinh text (`write`)

```bash
uv run python -m app.content.generate_exam write --slug tp-form-08 \
  --model <provider/model> [--limit 3]   # --limit để thử vài ô đầu
```

- Mỗi **cụm** một lần gọi model, ghi xuống đĩa ngay — chạy lại chỉ sinh ô còn thiếu.
- Model xuất thẳng định dạng dán mà `content_import.py` đọc được; mọi luật
  (`validate_question`, `_check_question`) áp lên bản sinh y như bản người dán.
- Mọi question block phải có `Answer:` **và** `Source: original` — không có
  default ở bất kỳ tầng nào (ADR-007 §2.5).
- Hết quota (`LLMQuotaExhausted`) thì lệnh **dừng hẳn**, các ô đã ghi vẫn còn.
- Part 2 chỉ có ba đáp án; Part 1–2 không in đề bài (`None`, không phải `""`).

## 3. Chặng 3 — Kiểm (`check`)

```bash
uv run python -m app.content.generate_exam check --slug tp-form-08
```

Ba tầng: cú pháp (parser thật), ngữ nghĩa (đáp án đúng, nhiễu hợp lý, trùng lặp),
đối chiếu đáp án bằng LLM (`--verify`, tốn lượt gọi — chạy sau khi text sạch).

Kết quả đọc theo mã màu:

- **✗ chặn nạp** — phải sửa trước khi load. Thường gặp:
  - `thiếu dòng 'source:'` — thêm `Source: original` vào question block
  - `hình dạng schedule cần 2–4 hàng` — sửa `graphics/<slot>.txt`
  - `trục đáp án ... phải có đúng 4 mục` — kind hình không khớp dữ liệu
    (`schedule` lấy tiêu đề cột, `table` lấy tên hàng, `form` không có hàng tiêu đề)
- **⚠ cần người nhìn** — không chặn, duyệt bằng mắt: lựa chọn dài bất thường,
  ảnh Part 1 thiếu mô tả.

## 4. Chặng 4 — Vẽ hình ngữ liệu và ảnh Part 1

```bash
# Hình Part 3/4/7 vẽ từ dữ liệu bảng (graphics/*.txt) → PNG + alt text
uv run python -m app.content.generate_exam graphic --slug tp-form-08

# Ảnh Part 1 sinh bằng model ảnh (cần _imagegen cài sẵn ở ~/.claude/skills)
uv run python -m app.content.generate_exam photo --slug tp-form-08
```

Lưu ý:
- Hình tự render **không cần giấy phép**; giá trị nằm ở chữ đọc được.
- Ảnh Part 1 **phải được người xem trước khi gắn** — model vẽ thừa người là lỗi
  đã xảy ra thật. Xoá tấm bị loại rồi chạy lại `photo` (hàng đợi là một truy vấn
  trên thư mục).

## 5. Chặng 5 — Nạp vào DB dev (`load`)

```bash
uv run python -m app.content.generate_exam load --slug tp-form-08 \
  --token <editor token> [--part N]
```

Đi qua đúng đường dán của admin (`POST /parts/{part}/parse` → `POST /parts`),
nên mọi cổng `validators.py` vẫn chạy. `--part` không phải tiện nghi: `commit_part`
**cộng thêm** câu chứ không thay thế — nạp lại cả blueprint sẽ dán Part 5 vào đề
lần thứ hai.

## 6. Chặng 6 — Sinh audio (`backfill_audio`)

```bash
# Kiểm giọng còn sống trước lượt lớn (edge-tts hay rút id)
TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external

uv run python -m app.content.backfill_audio --only questions
```

- Hàng đợi là một **truy vấn**: "thứ nào thiếu audio hoặc script đã đổi". Chạy
  lại chỉ tìm thấy ít việc hơn.
- Audio treo ở **hai tầng**: Part 1/2 trên `question`, Part 3/4 trên `question_set`.
- Kết quả `0 synthesised` nghĩa là mọi thứ đã đủ — không phải bỏ sót (Part 5/6/7
  là phần đọc, không bao giờ cần audio).

## 7. Chặng 7 — Gắn ảnh vào DB (`attach-images`)

```bash
uv run python -m app.content.generate_exam attach-images --slug tp-form-08
#   → chỉ in bảng khớp (mặc định, để người xem trước)
uv run python -m app.content.generate_exam attach-images --slug tp-form-08 --commit
#   → ghi thật
```

Tự chọn chế độ khớp theo part: Part 1 `number`, Part 3/4 `index`, Part 7
`passage`. Tự điền `license: generated` + attribution cho ảnh tự sinh. Giữ
`--commit` cho bước người xác nhận — ảnh phải được nhìn trước khi gắn (§8).

## 8. Chặng 8 — Đẩy media lên provider (`media --push`)

```bash
uv run python -m app.content.generate_exam media --slug tp-form-08           # chỉ kiểm
uv run python -m app.content.generate_exam media --slug tp-form-08 --push    # kiểm + đẩy
```

Chặng này tồn tại vì một lỗ có thật: worker TTS ghi clip xuống **đĩa local**,
`audio_public_base_url` trỏ tới Supabase — đề vừa nạp xong có nút play và
**không có gì phát ra**. DB đúng, thứ sai nằm ở nơi DB không nhìn tới. Nó hỏi cả
**hai tầng** media (câu cho Part 1/2, cụm cho Part 3/4).

## 9. Chặng 9 — Đối chiếu đáp án (`check --verify`)

```bash
uv run python -m app.content.generate_exam check --slug tp-form-08 --verify
```

Một lượt gọi **khác** với bốn lựa chọn **xáo thứ tự** — không xáo thì model chọn
lại đúng vị trí cũ và phép kiểm thành nghi thức. Tốn lượt gọi, chạy sau khi text
sạch. Kết quả có cờ thì đưa người duyệt quyết.

## 10. Chặng 10 — Publish (admin UI)

Publish là quyết định của người soạn, qua `/admin/tests/<slug>` — **không tự
động** (§8: đề tự sinh vào thẳng tay người học mà không ai đọc là mất niềm tin).
Cổng publish từ chối khi audio thiếu hoặc lệch (`media_state`).

## 11. Chặng 11 — Đồng bộ lên production

```bash
./scripts/export-test.sh tp-form-08 /tmp/tp-form-08.sql
cat /tmp/tp-form-08.sql | docker run --rm -i postgres:17 psql "$SUPABASE_URL" \
  -v ON_ERROR_STOP=1 -q
```

Chi tiết, cơ chế và các bug đã gặp: [`SYNC-TEST-TO-PRODUCTION.md`](SYNC-TEST-TO-PRODUCTION.md).
Tóm tắt:

- Clone dev DB → xoá mọi bảng ngoài tập bảng của đề → dump đúng một test.
- Đầu file có khối **reset idempotent** (xoá test cũ nếu đã có trên đích).
- Assets chèn bằng `INSERT ... ON CONFLICT (id) DO UPDATE` — an toàn chạy lại.
- Khác `export-content.sh` (nạp toàn bộ, dành cho lần đầu dựng production).

## 12. Git: cái gì commit, cái gì bỏ

| Thư mục | Git | Vì sao |
|---|---|---|
| `blueprint.json`, `paste/`, `graphics/`, `graphic-images/` | ✅ commit | nguồn để tái tạo lại đề, nhẹ, diff được |
| `images/` (ảnh Part 1 model sinh) | ❌ ignore | tái sinh từ `*.prompt.txt`; giống mp3 |
| `photos/` (mô tả ảnh) | ❌ ignore | phụ phẩm của `photo` |
| `apps/api/media/` (mp3) | ❌ ignore | lớn, tái sinh từ manifest |
| `content/manifest/*.jsonl` | ✅ commit | manifest là bản ghi nội dung đã sinh |

## 13. Chi phí và thời gian (đo ở tp-form-07)

- `write`: chục phút cho 200 câu tuỳ model; Ollama tại máy tồn tại vì hạn mức
  OpenRouter free 50 lượt/ngày không đủ một đề.
- Audio: 54 clip, vài phút; trước lượt lớn luôn kiểm giọng bằng test external.
- `check --verify`: tốn lượt gọi LLM cho 200 câu.

## 14. Khi gặp lỗi

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| `media --push` báo "không có trên đĩa" | chạy `--push` trước `backfill_audio`/`graphic` | sinh xong rồi push |
| Nút play có nhưng không kêu | media chưa lên provider | `media --push` |
| `attach-images` khớp sai cụm | số trong tên file là thứ tự cụm, không phải số câu | script tự chọn `--match` theo part, đừng ghi đè |
| Import đụng khoá chính trên production | test cũ còn sót | khối reset đầu file dump xử lý; nếu vẫn lỗi, xoá bằng tay theo §5 của SYNC doc |
| Hết quota giữa chừng | OpenRouter free tier | dừng hẳn, chạy lại sau — ô đã ghi không mất |
