# ADR-006 — Đường upload media

> **Trạng thái:** đã quyết 2026-08-10 · **Thay thế:** không · **Liên quan:** [`PHASE2-AUDIO.md`](PHASE2-AUDIO.md) (= ADR-002), [`ADR-004-IMAGES.md`](ADR-004-IMAGES.md), [`MEDIA-PIPELINE.md`](MEDIA-PIPELINE.md) §10.5
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

### 2.2 Tách nhà cung cấp: Cloudinary cho ảnh, R2 cho audio

Không phải vì thích nhiều nhà cung cấp, mà vì **hai loại file này có hình dạng chi phí ngược nhau**:

- **Ảnh** cần biến đổi (crop avatar, nhiều kích cỡ, WebP/AVIF), dung lượng nhỏ, băng thông thấp. Cloudinary bán đúng thứ đó.
- **Audio** không cần biến đổi gì — một mp3 phát nguyên trạng — nhưng **ngốn băng thông**. Một đề TOEIC đầy đủ có ~100 clip nghe; vài trăm học viên luyện mỗi ngày là hàng chục GB egress/tháng, tăng tuyến tính theo số người dùng.

Mô hình credit của Cloudinary quy đổi lưu trữ, băng thông và số lần biến đổi về **cùng một đơn vị**, nên băng thông audio sẽ ăn vào hạn mức của ảnh. Cloudflare R2 **không tính phí egress** — đó là khác biệt về bản chất mô hình giá, không phải chênh vài phần trăm.

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

**§10.2 — không sinh được clip nhiều giọng — vẫn là blocker của Sprint 5.** Không nhà cung cấp lưu trữ nào giải quyết nó. Upload audio thu bởi người thật là *đường vòng* (thu sẵn cả đoạn hội thoại rồi tải lên), không phải lời giải: nó đổi bài toán kỹ thuật thành bài toán sản xuất nội dung, và bài toán sản xuất thì đắt hơn.

Đừng bước vào Sprint 5 với niềm tin rằng ADR này đã gỡ xong đường đi cho Part 2 và Part 3.
