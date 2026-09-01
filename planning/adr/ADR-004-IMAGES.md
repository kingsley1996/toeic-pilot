# ADR-004 — Ảnh cho TOEIC Part 1

**Trạng thái:** Đã chốt · 2026-08-09
**Giải quyết:** `ADR-001-DATA-MODEL.md` §A6.1 — lỗ hổng cuối cùng của schema
**Liên quan:** `PHASE2-AUDIO.md` (tiền lệ trực tiếp) · `ADR-001` §A2 (cấu trúc part)

---

## 1. Vấn đề, và vì sao nó quen thuộc

Part 1 có 6 câu mỗi đề. Mỗi câu là **một bức ảnh** cộng bốn câu mô tả đọc lên; thí sinh chọn câu đúng nhất. Không có ảnh thì Part 1 không tồn tại.

Đây **đúng là lỗ hổng §7b từng gặp với audio, lặp lại nguyên xi**: không nguồn, không storage, không quyết định, và một cột `image_url` để trống trong schema giả vờ như vấn đề đã được giải. `ADR-001` §A6.1 gọi thẳng nó là "chỗ trống có tên" chứ không phải lời giải.

Điểm khác biệt duy nhất, và nó khiến ảnh **khó hơn** audio: audio ta tự sinh được từ text, còn ảnh thì không. Không có "TTS cho ảnh" miễn phí, không cần tài khoản. Nên bài toán chuyển từ *sinh* sang *tìm nguồn có giấy phép dùng được*.

Một hệ quả bị bỏ qua, phát hiện khi viết tài liệu này: **Part 1 không in gì ngoài ảnh.** Hướng dẫn của ETS ghi rõ *"The statements will not be printed in your test book and will be spoken only one time."* Nghĩa là Part 1 giống Part 2 ở chỗ không in đề lẫn đáp án — chỉ khác là có 4 phương án thay vì 3, và có thêm ảnh. Validator trước đó bắt Part 1 phải có `prompt_text`; đã sửa cùng lúc với tài liệu này. Lỗi này tồn tại được chính là **vì** Part 1 chưa dựng nổi: không ai chạm vào phần mà mình không build được.

## 2. Các quyết định

### 2.1 — Nguồn ảnh: curation thủ công từ nguồn giấy phép mở

| | |
|---|---|
| **Chốt** | Người soạn nội dung chọn ảnh từ nguồn giấy phép mở (Wikimedia Commons, Openverse, Unsplash/Pexels), ghi URL + giấy phép + ghi công vào file spec. Pipeline chỉ tải về và chuẩn hoá |
| **Thay vì** | Tích hợp API tìm ảnh tự động · sinh ảnh bằng model · chụp/vẽ tự sản xuất |
| **Vì sao** | Một câu Part 1 chỉ dùng được khi **ảnh và bốn câu mô tả khớp nhau** — trong đó ba câu phải sai một cách hợp lý. Không có cách nào tự động hoá phần đó; ảnh dù tìm bằng API vẫn phải qua mắt người. Xây tích hợp tìm kiếm là xây một thứ mà kết quả của nó **vẫn cần duyệt tay** — tức tốn công cho một bước không tiết kiệm được gì |
| **Thêm một lý do** | Trình tự soạn bài thực tế đi ngược: chọn ảnh **trước**, rồi viết bốn câu mô tả về nó. Spec file phản ánh đúng trình tự đó |
| **Đánh đổi** | Không mở rộng quy mô tự động được. Chấp nhận: MVP cần vài chục ảnh, không phải vài nghìn |

Loại model sinh ảnh vì ba lý do cộng lại: tốn tiền, và ảnh sinh ra hay có lỗi giải phẫu/chữ viết khiến "mô tả đúng" trở nên mơ hồ — mà mơ hồ thì phá hỏng chính thứ Part 1 đo.

### 2.2 — `license` và `attribution` là NOT NULL

| | |
|---|---|
| **Chốt** | `image_asset.license`, `.attribution`, `.source_url` đều NOT NULL |
| **Thay vì** | Nullable, điền sau |
| **Vì sao** | Phần lớn ảnh CC là **CC-BY**: dùng được miễn phí **nhưng bắt buộc ghi công**. Ghi công thiếu không phải lỗi kỹ thuật mà là vi phạm giấy phép. NOT NULL ép người thêm ảnh trả lời câu hỏi giấy phép **ngay lúc thêm** — lúc còn đang mở trang nguồn. Bổ sung sau nghĩa là truy nguyên hàng trăm ảnh mà không ai còn nhớ lấy từ đâu |
| **Đánh đổi** | Không có. Cùng một lập luận với `question.source` ở `ADR-001` §A4.7, và cùng một loại rủi ro: pháp lý, không phải kỹ thuật |

Đây là ứng dụng trực tiếp của bài học §7b: **rủi ro bản quyền phải được quyết định trước khi build content pipeline, không phải sau.**

### 2.3 — `image_asset` là bảng riêng, không nhét vào `audio_asset`

| | |
|---|---|
| **Chốt** | Bảng `image_asset` riêng, cùng hình dạng content-addressed |
| **Thay vì** | Gộp thành `media_asset` chung có cột `media_type` |
| **Vì sao** | Hai bảng chỉ **trông** giống nhau. Audio có `duration_ms`, `voice`, `accent`, `engine` — vô nghĩa với ảnh. Ảnh có `width`, `height`, `license`, `attribution` — vô nghĩa với audio. Gộp lại được một bảng mà **quá nửa số cột luôn NULL**, và mọi CHECK constraint đều phải mở đầu bằng "nếu media_type là…" |
| **Đánh đổi** | Trùng lặp phần khung (id, storage_key, source_hash, size, mime, created_at). Chấp nhận được: trùng cột rẻ hơn nhiều so với một bảng mà không constraint nào phát biểu được điều gì chắc chắn |

### 2.4 — `source_hash` cho ảnh vẫn là hash của INPUT

| | |
|---|---|
| **Chốt** | `sha256(source_url \| transform_version)` |
| **Thay vì** | sha256 của bytes ảnh gốc tải về |
| **Vì sao** | Nghe có vẻ ngược, vì **ảnh tải về thì hash bytes được** — khác hẳn TTS. Nhưng ta không lưu bytes gốc: pipeline chuẩn hoá (đổi kích thước, ép JPEG) trước khi lưu, và Pillow **không đảm bảo cùng bytes giữa các phiên bản**. Hash đầu ra sẽ đổi khi nâng cấp Pillow, phá vỡ tính idempotent y hệt trường hợp TTS |
| **Vì sao có `transform_version`** | Nó là thứ tương đương với `tts_engine_version`: một núm vặn thủ công. Đổi tham số chuẩn hoá mà muốn tải lại toàn bộ thì tăng số này; không muốn thì đừng đụng vào |
| **Đánh đổi** | Hai URL khác nhau trỏ tới cùng một bức ảnh sẽ thành hai asset. Hiếm, và vô hại |

Giữ nguyên nguyên tắc của `PHASE2-AUDIO` §A4.2 — **hash cái đưa vào, không hash cái lấy ra** — nên `app/core/media.py::source_hash` dùng lại được nguyên vẹn.

### 2.5 — Lưu trữ và phục vụ: dùng lại nguyên đường ống audio

| | |
|---|---|
| **Chốt** | Cùng `ObjectStore`, cùng thư mục, cùng `/media`, cùng manifest, cùng lệnh `seed` |
| **Thay vì** | Bucket riêng, đường phục vụ riêng |
| **Vì sao** | Quyết định ở `PHASE2-AUDIO` §A2.1 và §A2.4 không có gì riêng cho audio: key content-addressed, URL công khai cố định, runtime không gọi object store. Áp cho ảnh y nguyên. Đường nâng cấp R2 ở §A5 cũng dùng lại được không sửa gì |
| **Đánh đổi** | Không có |

Khác biệt duy nhất về vận hành: `Content-Type` phải là `image/jpeg` thay vì `audio/mpeg`, và điều đó đã nằm sẵn trong tham số `content_type` của `ObjectStore.put()` — tham số mà `LocalDirStore` bỏ qua nhưng `S3ObjectStore` bắt buộc phải gửi (`PHASE2-AUDIO` §A5).

### 2.6 — `question.image_url` đổi thành `image_asset_id`

| | |
|---|---|
| **Chốt** | FK tới `image_asset`, bỏ cột chuỗi |
| **Thay vì** | Giữ `image_url` |
| **Vì sao** | Một cột chuỗi không có chỗ nào để đặt giấy phép và ghi công — mà theo §2.2 thì đó là dữ liệu bắt buộc. Nó cũng cho phép trỏ tới URL bên ngoài, tức là hotlink vào máy chủ người khác: hỏng lúc nào không biết, và bất lịch sự |
| **Đánh đổi** | Một migration. Rẻ **ngay bây giờ** vì chưa có hàng nào và chưa có endpoint nào; đắt sau này |

## 3. Chuẩn hoá ảnh

| Tham số | Giá trị | Vì sao |
|---|---|---|
| Cạnh dài tối đa | 1280 px | Đủ nét trên màn hình retina ở khổ hiển thị Part 1; lớn hơn chỉ tốn băng thông |
| Định dạng | JPEG chất lượng 82 | Ảnh chụp. PNG cho ảnh chụp là lãng phí; WebP tốt hơn nhưng thêm một trục tương thích cho lợi ích không đáng ở quy mô này |
| Màu | Ép sang RGB | Ảnh CMYK và ảnh có alpha sẽ hỏng khi lưu JPEG nếu không ép |
| Metadata | Xoá EXIF | EXIF hay chứa toạ độ GPS và thông tin thiết bị của người chụp. Không cần, và không nên phát tán |

Ước lượng dung lượng: ảnh 1280 px JPEG q82 ≈ 150–250 KB. Một đề đầy đủ có 6 ảnh ≈ 1,5 MB. Vẫn nằm gọn trong free tier 10 GB của R2 cùng với audio.

## 4. Ràng buộc bất biến

### 4.1 — Không bao giờ trỏ trực tiếp tới URL nguồn
Ảnh phải được tải về và phục vụ từ store của mình. Hotlink làm bài học hỏng khi nguồn đổi đường dẫn, và đẩy chi phí băng thông sang máy chủ người khác mà họ không đồng ý.

### 4.2 — Ghi công phải hiển thị được ở nơi ảnh xuất hiện
Lưu `attribution` trong DB mà không bao giờ render ra thì vẫn là vi phạm CC-BY. Endpoint nào trả ảnh Part 1 phải trả kèm chuỗi ghi công, và UI phải hiện nó.

### 4.3 — Part 1 chỉ in ảnh
Không `prompt_text`, không `question_option.content`. Bốn câu mô tả nằm trong audio. Đã có `validators.py` và test bảo vệ.

## 5. Chưa làm (có chủ ý)

- **Chưa có ảnh thật.** Pipeline đã chạy được và có test, nhưng chọn ảnh là việc của người soạn nội dung, cùng một tình trạng với nội dung câu hỏi (`ADR-001` §A6.3).
- **Chưa có kiểm tra giấy phép tự động.** Không có API nào nói cho ta biết một URL đang ở giấy phép gì một cách đáng tin. Cột NOT NULL ép người điền; nó không xác minh được.
- **Chưa có ảnh cho Part 3, 4, 7.** Đề thật đôi khi có biểu đồ/bảng biểu ở Part 7. Cùng bảng `image_asset` dùng được khi tới lúc.
