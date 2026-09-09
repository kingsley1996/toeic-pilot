# SPEC-GRAMMAR-VIDEO — Video bài học cho lesson ngữ pháp

Trạng thái: **nháp, chờ duyệt** (2026-09-09). Plan trước, implement sau — cùng
cách làm với `SPEC-FEEDBACK.md`.

## 0. Mục tiêu và ranh giới

Admin soạn bài học ngữ pháp `kind='theory'` đính kèm **một video giảng bài**
(mp4/webm) alongside phần markdown `body`. Người học mở bài học thì thấy player
dưới tiêu đề, trước phần chữ.

**Chủ ý KHÔNG làm** (đọc ADR-006 §"Video" trước khi phàn nàn): nhiều video
một bài, phụ đề, thumbnail tự sinh, transcode, stream adaptive (HLS/DASH),
video cho lesson `practice` (không có chỗ để hiển thị), video cho module khác.

## 1. Vì sao cần đụng ADR-006

ADR-006 ghi rõ video bị loại: *"PLAN.md không nhắc tới video ở đâu… Video là
loại media đắt nhất ở mọi chiều — lưu trữ, encode, băng thông, player. Dựng
đường cho nó 'phòng khi cần' là chi phí có thật đổi lấy một nhu cầu chưa tồn
tại."*

Nhu cầu bây giờ **đã tồn tại** (người soạn muốn giảng bằng video), nên điều
đúng là **sửa ADR-006 §2.2** thêm một đoạn: video là media của NGƯỜI SOẬN
(không phải media người dùng), đi đúng luồng ticket→POST→confirm có sẵn, và
**đi object store (S3/Supabase) chứ KHÔNG Cloudinary** — băng thông video ăn
credit Cloudinary là thứ ảnh đang sống bằng, và ADR-002 đã chốt audio đi S3
vì đúng bài toán băng thông. Không dựng driver mới: `S3Driver` đã bỏ tên nhà
cung cấp và giữ cờ `resource_type` — video chỉ là một `kind` nữa.

## 2. Dữ liệu

### Migration `077_grammar_video`

`grammar_lesson` thêm **hai cột**, nullable:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `video_storage_key` | String(512) NULL | Pattern avatar/feedback: khoá thô dưới prefix `grammar-video/`, KHÔNG hàng `media_asset` — video của người soạn không mang giấy phép/provenance như ảnh CC |
| `video_duration_s` | Integer NULL | Điền lúc confirm từ metadata client gửi lên; chỉ để hiển thị "12:34", không chấm điểm |

Một bài **một video**: cột trên bảng, không bảng nối. Đổi video = ghi đè khoá
(file cũ thành mồ côi, `reconcile_media` dọn — cùng chủ sách với avatar).

### `MediaKind` và driver

- `core/storage.py`: `MediaKind = Literal["image", "audio", "video"]`.
- `S3Driver` dùng lại y nguyên — khoá video có prefix riêng nên không đụng
  vùng audio/image; **không** biến đổi, **không** `transformation` (S3 giữ
  nguyên byte).
- `get_driver("video")` chỉ tới `S3Driver` (`driver == "cloudinary"` với
  `kind="video"` → `StorageError`, cùng kiểu từ chối như audio-cloudinary).
- `core/media.py`: `VIDEO_KEY_PREFIX = "grammar-video"`,
  `video_storage_key_for(source_hash_value, ext)`, và
  `public_video_url(storage_key)` join `settings.video_public_base_url` —
  **cấu hình mới**, cùng bộ với `AUDIO_PUBLIC_BASE_URL`/`IMAGE_PUBLIC_BASE_URL`.

## 3. API

### Soạn nội dung — `routes/admin_grammar.py`, `require_role("admin")`

| Endpoint | Ghi chú |
|---|---|
| `POST /admin/grammar/lessons/{id}/video/ticket` | Body `{ext: "mp4"|"webm"|"mov"}`. Khoá `grammar-video/<aa>/<hash>.<ext>`, trả `UploadTicket` (presigned PUT). Quota chặt `Quota(limit=5, window=600)` — vài lần mỗi buổi soạn, mở rộng chỉ mời dùng bucket làm ổ đĩa |
| `DELETE /admin/grammar/lessons/{id}/video` | Gỡ khoá khỏi bài (file để mồ côi cho `reconcile_media`), idempotent |

**Trình duyệt PUT thẳng object store** với presigned URL (đúng §2.1 — byte
không đi qua FastAPI). Limits nằm ở tầng schema: `ext` trong tập đóng; kiểm
kích thước làm ở bước confirm chứ không tin client.

### Confirm — `PUT /admin/grammar/lessons/{id}/video`

Body `{storage_key, duration_s?}`. Ba kiểm, cùng khuôn `avatar_confirm`:

1. `storage_key` bắt đầu `grammar-video/` — không thì 400 (đúng bẫy trỏ vào
   vùng media người khác).
2. `driver.verify(storage_key)` — file thật sự nằm trên store; thiếu bước này
   là đường ghi chuỗi tuỳ ý và người học sẽ thấy player vỡ.
3. Bài phải `kind='theory'` — `practice` không có chỗ hiển thị video, chặn ở
   biên thay vì nuôi một cột không bao giờ đọc.

Ghi hai cột + `db.commit()`. Trả `GrammarAdmin` đã cập nhật.

### Người học — không endpoint mới

`GrammarLessonPublic` (schemas/grammar.py) thêm `video_url: str | None` —
sinh từ khoá bằng `public_video_url`, chỉ set khi có khoá. Route đọc lesson
cũ không đổi.

## 4. Frontend

### Admin — `app/admin/grammar/lessons/[lessonId]` (màn soạn)

Một khối "Video bài giảng" cạnh khối body:

- Chưa có: nút "Tải video lên" → chọn file → `PUT` presigned → `PUT confirm`
  → thumbnail placeholder + nút Xoá.
- Có: hiện duration + nút Xoá + nút Thay thế (cùng luồng).
- Lỗi vượt quota/verify → hiển thị y hệt thông báo `messageFor` của feedback.
- Chỉ hiện với `kind='theory'`.

### Người học — `learn/grammar/[topicId]/[lessonId]`

Trên `shown.body` (page.tsx:272), nếu `video_url`:

```tsx
<video controls preload="metadata" src={video_url} className="w-full rounded" />
```

`preload="metadata"` — video là ~50-200 MB, tải nguyên file trước khi bấm
phát là băng thông bỏ đi. KHÔNG autoplay, KHÔNG `muted` hack. CSS thuần, không
thư viện player — `<video>` native là đủ cho một bài giảng.

## 5. Publish gate

Cổng publish lesson theory (admin_grammar.py:434 chặn body rỗng) **không**
đổi: video là phụ kiện, rỗng vẫn publish được. Nhưng confirm đã `verify()`,
nên không thể có khoá-đã-ghi-mà-file-mất trừ khi ai đó xoá tay trên store —
đó là việc `reconcile_media` phát hiện, không phải việc chặn publish.

## 6. Cấu hình + triển khai

- `.env.example`: `VIDEO_PUBLIC_BASE_URL` + ghi chú Supabase public bucket.
- Render: thêm env cho api + web nếu player cần origin đầy đủ.
- `docker/web` không đổi; CDN/cache header để mặc định của Supabase
  (`public, max-age=3600` kiểm tra được sau khi có file thật).

## 7. Tests (`tests/test_grammar_video.py`)

1. Ticket trả presigned URL, khoá nằm dưới `grammar-video/`; ext lạ → 422.
2. Confirm khoá sai vùng → 400 (bẫy prefix, đúng bài `avatar_confirm`).
3. Confirm khi `driver.verify` fail → 400 (fake driver test được — cùng cách
   `test_media.py` dựng driver giả).
4. Confirm lên lesson `practice` → 400.
5. Đường `video/ticket` + confirm đều từ chối role `editor`/`learner` (403).
6. Gỡ video → `video_url` về `None`; gọi lần 2 vẫn 200 (idempotent).
7. `GET` lesson public mang `video_url` đúng khi có khoá, `None` khi không.
8. DELETE /video + route *publish* vẫn xanh khi video rỗng (§5).

## 8. Cái chủ ý KHÔNG làm — và điều kiện mở lại

- **Nhiều video/bài** — chưa có nhu cầu thật, cột riêng đủ.
- **Transcode/adaptive bitrate** — cần ffmpeg + job queue; chỉ mở khi có video
  thực tế quá nặng cho 4G (đo rồi mới làm).
- **Phụ đề/VTT** — thêm khi có bài giảng nói nhiều; schema không chặn (thêm
  cột `video_subtitle_key` sau, không phá gì).
- **Video cho dictation/vocab/practice** — mỗi module một luồng media riêng;
  gộp chung là dựng "media-asset tổng quát" mà không ai đang cần.
