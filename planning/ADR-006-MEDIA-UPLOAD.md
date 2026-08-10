# ADR-006 — Đường upload media

> **Trạng thái:** đã quyết 2026-08-10, sửa §2.2 ngày 2026-08-10 (xem §2.8) · **Thay thế:** không · **Liên quan:** [`PHASE2-AUDIO.md`](PHASE2-AUDIO.md) (= ADR-002), [`ADR-004-IMAGES.md`](ADR-004-IMAGES.md), [`MEDIA-PIPELINE.md`](MEDIA-PIPELINE.md) §10.5
>
> Đóng nợ §10.5: *"`AUDIO_SOURCES` và `IMAGE_SOURCES` đều đã có giá trị `uploaded` — schema hỗ trợ, đường đi thì chưa xây."*

---

## 1. Vấn đề

Mọi media trong hệ thống hiện nay đều được **sinh ra ngoài luồng**: audio từ edge-tts, ảnh từ kho ảnh CC. Không có cách nào đưa vào một file mà con người tự tạo — ảnh tự chụp, ảnh đã mua bản quyền, hay bản thu bởi giọng người thật.

Bốn nhu cầu cụ thể, tất cả đều đã hoặc sắp có thật:

| Nhu cầu | Đóng lỗ hổng nào |
|---|---|
| Ảnh Part 1 do biên tập viên tự đưa | §10.3 — ảnh không tái tạo được, và kho CC không đủ cho một đề hoàn chỉnh |
| Audio thu bởi người thật | §10.6 — chất lượng TTS; và là đường vòng khả dĩ cho §10.2 (clip nhiều giọng) |
| Ảnh minh hoạ cho mục từ vựng | tính năng mới, chưa có trong `PLAN.md` |
| Avatar người dùng | thay ảnh chữ cái đầu ở `/profile` |

## 2. Các quyết định

### 2.1 Hai loại media, hai đường đi — không gộp

Đây là quyết định gốc, mọi quyết định còn lại chảy ra từ nó.

| | **Media nội dung** | **Media người dùng** |
|---|---|---|
| Ví dụ | ảnh Part 1, audio thu người thật, ảnh từ vựng | avatar |
| Ai đưa lên | `editor` / `admin` | bất kỳ `learner` nào |
| Tái tạo được | không (đó chính là lý do phải upload) | không |
| Bản quyền | `license`/`attribution`/`source_url` **NOT NULL** | không áp dụng |
| Kiểm duyệt | biên tập viên duyệt trước khi publish | **không ai duyệt trước** |
| Vòng đời | theo nội dung, `archived` chứ không xoá | theo tài khoản, xoá được |

Gộp chúng vào một `POST /media/upload` chung nghe gọn hơn và sai ở cả hai đầu: hoặc avatar bị lôi qua quy trình bản quyền vô nghĩa, hoặc ảnh Part 1 đi vòng qua cổng duyệt. Nên có **hai nhóm endpoint**, và chúng chỉ dùng chung đúng một thứ — lớp lưu trữ.

### 2.2 Tách nhà cung cấp: Cloudinary cho ảnh, object store cho audio

> **Đã sửa 2026-08-10.** Bản đầu viết "R2 cho audio" và đó là một sai lầm về *cách diễn đạt quyết định*, không phải về quyết định. Xem §2.8.

Không phải vì thích nhiều nhà cung cấp, mà vì **hai loại file này có hình dạng chi phí ngược nhau**:

- **Ảnh** cần biến đổi (crop avatar, nhiều kích cỡ, WebP/AVIF), dung lượng nhỏ, băng thông thấp. Cloudinary bán đúng thứ đó.
- **Audio** không cần biến đổi gì — một mp3 phát nguyên trạng — nhưng **ngốn băng thông**. Một đề TOEIC đầy đủ có ~100 clip nghe; vài trăm học viên luyện mỗi ngày là hàng chục GB egress/tháng, tăng tuyến tính theo số người dùng.

Mô hình credit của Cloudinary quy đổi lưu trữ, băng thông và số lần biến đổi về **cùng một đơn vị**, nên băng thông audio sẽ ăn vào hạn mức của ảnh.

Và đây mới là lập luận sống lâu nhất, vì nó **không phụ thuộc quy mô**: credit là một hồ chung, nên một đợt cao điểm luyện nghe làm hỏng *upload ảnh*. Triệu chứng xuất hiện rất xa nguyên nhân — người ta đi tìm lỗi ở đường ảnh, trong khi thứ đã tiêu hết hạn mức là audio. Object store tính riêng băng thông thì không có kiểu hỏng đó.

> Bảng giá cụ thể của cả hai bên thay đổi theo thời gian. Con số phải kiểm lại tại thời điểm triển khai; điều **không** đổi là hình dạng: ảnh = biến đổi, audio = băng thông.

### 2.3 File không bao giờ đi qua FastAPI

Đây là mở rộng của luật đã có trong `CLAUDE.md` (*"audio must never be proxied through FastAPI — that loses range requests and burns the API's bandwidth"*), và nó áp dụng cho cả chiều lên:

```
trình duyệt ──(1) xin chữ ký──> FastAPI
trình duyệt <──(2) chữ ký + ràng buộc──┘
trình duyệt ──(3) PUT/POST file──────> Cloudinary / R2
trình duyệt ──(4) báo đã xong────────> FastAPI ──> ghi hàng asset
```

FastAPI chỉ ký và ghi nhận. Không có byte nào của file chạy qua nó.

Hệ quả bắt buộc: **bước (4) phải xác minh với nhà cung cấp**, không tin lời trình duyệt. Ai cũng gọi được bước (4) với một `public_id` bịa ra. Xác minh = hỏi lại kích thước/định dạng/dung lượng thật của object trước khi ghi hàng.

### 2.4 Chữ ký ghim ràng buộc, không ký séc trắng

Chữ ký phải bao gồm và do đó khoá chặt: thư mục đích, định dạng cho phép, dung lượng tối đa, và hạn dùng ngắn.

**Tuyệt đối không dùng unsigned upload preset.** Nó cho phép bất kỳ ai upload vào tài khoản của bạn, và đó không phải rủi ro lý thuyết — preset lộ ra trong mã nguồn trình duyệt là thứ có người quét tìm.

### 2.4b Thư mục nằm TRONG `public_id`, không gửi tham số `folder`

Phát hiện khi chạy thử lên tài khoản thật, không phải khi đọc tài liệu.

Gửi `folder` như một tham số riêng thì Cloudinary **ghép** thư mục vào trước
`public_id` ở tài khoản dùng chế độ thư mục cố định, nhưng **không ghép** ở tài
khoản dùng chế độ thư mục động. Nghĩa là id thật của object phụ thuộc vào một
thiết lập ở phía tài khoản mà code không nhìn thấy, và mọi lần tra cứu về sau
trở thành trò may rủi.

Triệu chứng ở lần chạy đầu rất dễ hiểu nhầm: **upload trả HTTP 200, nhưng
`verify()` trả 404** — file có thật, chỉ là code hỏi bằng một id không tồn tại.
Nếu bỏ qua bước xác minh của §2.3 thì lỗi này sẽ không lộ ra cho tới khi có
người mở một trang và thấy ảnh vỡ.

Đưa thư mục vào thẳng `public_id` thì id là thứ ta tự quyết, giống nhau ở mọi
chế độ tài khoản.

### 2.5 `storage_key` vẫn là nguồn sự thật, nhà cung cấp thì không

`audio_asset`/`image_asset` **không lưu URL**. Chúng lưu `storage_key`, và URL công khai dựng bằng một phép nối chuỗi với tiền tố lấy từ cấu hình. Đây là thiết kế đã có từ ADR-002 và nó chính là thứ khiến quyết định 2.2 rẻ: **đổi nơi chứa file là đổi một biến môi trường.**

Kèm theo hai điều dễ vi phạm:

- `public_id`/`version` của Cloudinary **không được** thay thế `source_hash`. `source_hash` băm **input** (text | giọng | engine), và đó là thứ duy nhất cho phép `media_state.py` trả lời "clip này có còn khớp với text hiện tại không". Băm bytes hay lấy id của nhà cung cấp đều làm mất khả năng đó.
- Cloudinary **không theo dõi bản quyền**. `image_asset` vẫn là nơi ghi `license`/`attribution`/`source_url`, và ba cột đó vẫn NOT NULL. Nhà cung cấp chỉ là chỗ để file.

### 2.6 Ảnh upload phải được chuẩn hoá và tước sạch metadata

- **Chặn SVG.** Nó là định dạng có thể chứa `<script>`; xem nó như ảnh là một lỗ XSS.
- **Tước EXIF.** Ảnh chụp bằng điện thoại mang theo toạ độ GPS — với avatar, đó là địa chỉ nhà người dùng.
- Giới hạn kích thước và dung lượng ngay tại **incoming transformation**, không phải sau khi lưu.

### 2.7 Avatar mở khoá được, nhưng kèm một câu hỏi chưa trả lời

Ảnh chữ cái đầu hiện tại không cần hạ tầng nào và không có rủi ro nào. Avatar thật là **nội dung do người dùng tải lên và hiển thị cho người khác** ⇒ cần một đường báo cáo/gỡ.

Quyết định: làm avatar, nhưng **`user_profile.avatar_storage_key` nullable và ảnh chữ cái đầu vẫn là mặc định** — nó vừa là dự phòng khi chưa upload, vừa là thứ để rơi về khi một ảnh bị gỡ.

### 2.8 Driver mang tên **giao thức**, không mang tên nhà cung cấp

Bản đầu của ADR này gọi driver audio là "driver R2", và `get_driver` có hẳn một nhánh `if driver == "r2"`. Cái tên đó **đóng băng một quyết định thương mại vào mã nguồn**: đổi nhà cung cấp hoá ra phải sửa code, trong khi thứ thật sự khác nhau giữa R2, Supabase Storage, Backblaze B2, DO Spaces, Wasabi và MinIO chỉ là **một endpoint và một cặp khoá**. Tất cả đều nói S3.

Driver vì thế tên là `s3`, và nhà cung cấp là giá trị của `S3_ENDPOINT_URL`.

Điều này có giá trị thực tế ngay: R2 là lựa chọn duy nhất có ma sát phụ — URL `r2.dev` bị rate-limit và không dùng cho production, nên nó bắt buộc phải có custom domain **nằm trên DNS của Cloudflare**, đúng thứ đã chặn mục 4d suốt. Với driver theo giao thức, ràng buộc đó không còn là ràng buộc của kiến trúc nữa.

**Lựa chọn hiện tại: Supabase Storage** (gói free: 1 GB lưu, 5 GB egress/tháng, không cần thẻ tín dụng). Quy ra đơn vị của dự án, ở 48 kbps: 1 GB ≈ 46 giờ audio ≈ 70–80 đề đầy đủ phần nghe; 5 GB egress ≈ 300–400 lượt làm phần nghe mỗi tháng. Egress **phẳng** là điểm hơn B2 ở giai đoạn này — B2 cho 3× dung lượng đang lưu, tức rộng rãi khi đã có nhiều nội dung và chật đúng lúc còn ít.

**Bẫy phải biết trước:** project free của Supabase **tự ngủ sau 7 ngày không có request**, và storage ngủ theo. Kiểu hỏng khó chẩn đoán: web chạy, Postgres chạy (nó vẫn ở Docker của ta), **chỉ audio 404**. Cần cron ping giữ nhịp.

#### 2.8a Audio sinh sẵn KHÔNG cần đường upload

Hai bài toán bị gọi chung một cái tên, và tách ra thì việc nhẹ hẳn:

| | Audio sinh offline | Audio người thật thu |
|---|---|---|
| Byte đi từ | máy dev, đã nằm trên đĩa | máy ta không kiểm soát |
| Cần gì | **đồng bộ** — `app/content/push_media.py` | vé + chữ ký + xác minh (§2.3) |
| Chặn bởi | không gì | §10.2, và nó là bài toán sản xuất |

Nghĩa là **đường tới production không đi qua §2.3**. `push_media` đẩy thẳng bằng khoá ghi, chạy ở máy dev sau `--extra content`, và khoá ghi không cần có mặt trong môi trường của tiến trình HTTP.

Nó đặt `Cache-Control: public, max-age=31536000, immutable` — hợp lệ vì khoá là content-addressed, một khoá luôn trỏ tới đúng một file không bao giờ đổi nội dung. Với hạn mức 5 GB egress thì đây không phải tinh chỉnh, nó là khác biệt giữa "đủ dùng" và "hết hạn mức giữa tháng".

#### 2.8b Presigned PUT không ghim được dung lượng — và bù ở đâu

Một chỗ yếu hơn Cloudinary, phải nói thẳng: chữ ký của presigned PUT **không mang được `content-length-range`** như policy của form POST. Nên §2.4 ("ghim ràng buộc, không ký séc trắng") ở đường S3 chỉ ghim được khoá, Content-Type và hạn dùng.

Trần dung lượng được bù ở hai chỗ khác:

1. **Giới hạn kích thước của chính bucket**, đặt ở bảng điều khiển nhà cung cấp. Đây là hàng rào thật sự, và nó nằm ngoài code — nhớ đặt.
2. **`verify()` xoá file quá cỡ** thay vì chỉ từ chối. Từ chối suông để lại một object không ai tham chiếu tới nhưng vẫn tính tiền hàng tháng — đúng loại file mồ côi mà §4 đã ghi là chưa có đường dọn.

### 2.8c Ảnh chỉ sống ở Cloudinary — kể cả ảnh do đường ống lấy về

Quyết định 2026-08-10: **không có đường ảnh local nào ở production.** `IMAGE_STORAGE_DRIVER=cloudinary`, và đó là nơi duy nhất ảnh tồn tại.

Điều này để lộ một lỗ hổng mà không màn hình nào từng chạm tới, cho tới khi màn làm bài dựng xong: `app/content/images.py` lấy ảnh CC về **đĩa local**, `seed` ghi hàng `image_asset` với khoá local, rồi `public_url` dựng một URL Cloudinary cho file **chưa bao giờ được tải lên đó**. Kết quả là ảnh Part 1 hỏng — và nó hỏng im lặng suốt nhiều sprint, vì chưa có gì hiển thị ảnh nội dung.

Cách gỡ là `CloudinaryDriver.upload_file`, dùng bởi `push_media`. Không nằm trong `StorageDriver`, cùng lý do với `LocalDiskDriver.write`: §2.3 nói byte không đi qua FastAPI, và đưa một đường ghi byte vào giao diện chung sẽ biến thứ chỉ dùng ở `app/content/**` thành thứ trông như gọi được từ một request handler.

Không làm thế thì ADR-004 mất đường ra production: mọi ảnh đường ống lấy về sẽ không bao giờ tới được người học, và lối duy nhất còn lại là biên tập viên tự tải từng tấm qua màn quản trị — đúng thứ ADR-004 dựng ra để tránh.

Hai chi tiết đáng giữ:

- **Cả hai đường lên Cloudinary dùng chung một hàm ký** (`_signed_params`). Đường trình duyệt và đường offline phải tạo ra object giống hệt nhau; hai bản sao sẽ lệch ở `transformation` hoặc `allowed_formats` mà không có gì báo. Đã kiểm: ảnh đẩy bằng `push_media` ra 239 131 byte từ file gốc 259 780 — tức `q_auto` và `fl_strip_profile` đã chạy, y như một lượt upload từ trình duyệt.
- **`push_media` không so dung lượng với Cloudinary.** Cloudinary chuẩn hoá ảnh lúc nhận, nên kích thước ở đích luôn khác trên đĩa. Với ảnh, "có mặt" đã là đủ — khoá là địa chỉ nội dung.

### 2.9 `StaticFiles` **có** hỗ trợ Range — luật cũ bị đọc rộng hơn ý nó

`CLAUDE.md` viết *"audio must never be proxied through FastAPI — that loses range requests and burns the API's bandwidth"*. Kiểm lại trên Starlette 1.4.1 đang cài: `FileResponse` đặt `accept-ranges: bytes`, phân tích header `Range`, trả 206 và trả 416 khi không thoả. **Mount `/media` không hề mất range request.**

Luật đó đúng cho một endpoint tự viết đọc byte từ object store rồi phát lại — chỗ đó thật sự mất range và thật sự đốt băng thông của API. Nó **không** đúng cho một mount static đọc đĩa local. Lý do thật còn lại chỉ là băng thông, tức là chuyện *quy mô*, không phải chuyện đúng/sai.

Ghi lại để lần sau không ai tự chặn mình khỏi một phương án hợp lệ vì một luật được đọc rộng hơn ý nó.

## 3. Ràng buộc bất biến

Bốn thứ hỏng âm thầm nếu ai đó vi phạm:

1. **`app.content` không được import từ `app/main.py`.** Code upload chạy lúc có request **không** thuộc `app/content/` — nó thuộc `app/core/storage.py`. `tests/test_content_isolation.py` bắt lỗi này trong một giây; ảnh production build `--no-dev` thì bắt bằng cách không khởi động được.
2. **Hash input, không hash bytes** (§2.5).
3. **Xác minh ở bước (4)** (§2.3). Không có nó, endpoint xác nhận là một đường ghi hàng asset tuỳ ý vào database.
4. **Rate limiting (P1-8) là điều kiện tiên quyết cứng**, đúng lập luận `ROADMAP.md` đã viết cho endpoint LLM: một endpoint ký-upload không đo đếm vừa là hoá đơn không giới hạn, vừa là dịch vụ hosting file miễn phí cho người lạ.

## 4. Chưa làm (có chủ ý)

- **Video.** `PLAN.md` không nhắc tới video ở đâu, và TOEIC Listening & Reading không có phần hình động. Video là loại media đắt nhất ở mọi chiều — lưu trữ, encode, băng thông, player. Dựng đường cho nó "phòng khi cần" là chi phí có thật đổi lấy một nhu cầu chưa tồn tại.
- **Kiểm duyệt tự động.** Add-on của Cloudinary tính tiền riêng. Ở quy mô hiện tại, gỡ thủ công khi có báo cáo là đủ; điều phải có ngay là *đường gỡ*, không phải bộ lọc.
- **Dọn file mồ côi.** §10.4 đã ghi: `seed` không bao giờ xoá. Thêm một nơi lưu trữ nữa mà không có đường xoá thì file mồ côi tích tụ ở cả hai đầu — và giờ là file mồ côi **tính tiền hàng tháng**. Cần một lệnh đối chiếu, nhưng nó không chặn phần còn lại.
- **Nén/chuẩn hoá độ lớn audio** (§10.6). Vẫn mở.

## 5. Điều ADR này KHÔNG giải quyết

**§10.2 — clip nhiều giọng.** ADR này không gỡ nó, và câu đó vẫn đúng: **không nhà cung cấp lưu trữ nào giải quyết một bài toán sinh file.**

> Cập nhật 2026-08-10: §10.2 **đã được gỡ**, bằng một đường hoàn toàn khác — `app/content/audio_join.py`, ghép bằng ffmpeg ngoài luồng. Điều ADR này khẳng định vẫn nguyên giá trị; nó chỉ không còn là blocker của Sprint 5.

Bản gốc còn viết rằng upload audio thu bởi người thật là *đường vòng*, không phải lời giải — vì nó đổi bài toán kỹ thuật thành bài toán sản xuất nội dung, mà sản xuất thì đắt hơn. Điều đó vẫn đúng, và giờ upload chỉ còn là lựa chọn về **chất lượng giọng**, không phải lối thoát duy nhất.
