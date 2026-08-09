# ADR-005 — Công cụ nhập nội dung (Admin UI)

**Trạng thái:** Đã chốt · 2026-08-09
**Giải quyết:** `ADR-001` §A6.3 (chưa có nội dung thật) — phần *cơ chế*, không phải phần *nội dung*
**Liên quan:** `PHASE2-AUDIO.md` §A2.6 (đường đi dữ liệu — tài liệu này **thu hẹp** phạm vi của nó) · `ADR-004` (ảnh) · `ADR-001` §B4 (ràng buộc cần validator)

---

## 1. Vấn đề

Schema đã đầy đủ, migration đã chạy, nhưng **không có đường nào đưa một câu hỏi vào database.** Không CLI, không UI, không import. `app/content/` chỉ xử lý media (audio, ảnh) chứ không xử lý câu hỏi hay từ vựng.

Lỗ hổng này cùng khuôn với hai lỗ hổng vừa đóng ở Sprint 2: nội dung được liệt kê như một task trong lộ trình, còn **cơ chế** thì không ai quyết.

Có một hệ quả cụ thể hơn và nó đang tồn tại ngay lúc này: `ADR-001` §A4.8 chọn `status = draft/published/archived` thay vì xoá mềm, với lý do "nội dung do AI sinh cần được duyệt trước khi xuất bản". Nhưng **duyệt là một hành động cần giao diện**, và không có gì thực hiện được nó. Nên `draft` hiện là một trạng thái **không ai thoát ra được** — một cột được thiết kế cho một quy trình chưa tồn tại.

## 2. Ràng buộc pháp lý, và vì sao nó làm công cụ *nhỏ đi*

Mục tiêu là nhập đề các năm trước. Chính sách của ETS rất rõ: sao chép hoặc tái sử dụng **bất kỳ phần nào** của tài liệu TOEIC là bất hợp pháp; license điện tử chỉ cấp theo từng năm và phải qua Office of General Counsel; chữ "TOEIC" là nhãn hiệu đã đăng ký. Với sản phẩm cho người dùng cuối, đây là rủi ro thật.

Hai đường hợp lệ, và `question.source` (NOT NULL, `ADR-001` §A4.7) tồn tại chính là để ép trả lời ở **từng hàng**:

| `source` | Nghĩa |
|---|---|
| `licensed` | Đã thật sự xin được license từ ETS hoặc đối tác được uỷ quyền |
| `original` | Câu mới, soạn theo đúng cấu trúc 7 part. **Định dạng đề không có bản quyền; nội dung cụ thể mới có** |
| `generated` | AI sinh, phải qua duyệt (Sprint sau) |

Điều bất ngờ: ràng buộc này làm công cụ **đơn giản hơn**, không phải phức tạp hơn.

- Audio đề gốc không dùng lại được ⇒ nhưng pipeline TTS đã sinh được 4 giọng từ transcript. Admin **chỉ cần nhập text**.
- Ảnh Part 1 gốc không dùng lại được ⇒ thay bằng ảnh CC qua `ADR-004`.

Nên trình nhập **không cần** upload file, không cần cắt audio, không cần quản lý media. Chỉ có văn bản. Đó là một công cụ nhỏ hơn hẳn so với hình dung ban đầu.

> ⚠️ **Hệ quả về quy trình:** đổi ảnh Part 1 thì **bốn câu mô tả phải viết lại theo ảnh mới**. Không có cách nào nhập nguyên văn statement của đề cũ rồi gắn vào một bức ảnh khác — ba phương án sai phải sai một cách hợp lý *với đúng bức ảnh đó*.

## 3. Các quyết định

### 3.1 — Admin tự viết, không headless CMS

| | |
|---|---|
| **Chốt** | Route `/admin` trong chính app Next.js, dựa trên endpoint FastAPI |
| **Thay vì** | Strapi / Directus / Payload · Django admin cạnh FastAPI |
| **Vì sao** | Headless CMS **không phải database** và quá hạn chế cho logic ứng dụng. Trộn CMS với một database quan hệ tạo ra **hai nguồn sự thật về schema** — kinh nghiệm được ghi nhận là dự án dùng CMS thành công dài hạn thường là dự án có 100% dữ liệu nằm ở CMS, không có DB quan hệ song song |
| **Cụ thể hơn** | Schema này không chuyển sang CMS được: `question_set` nhóm câu theo part, số phương án khác nhau theo part, partial unique index cho đáp án đúng, CHECK theo part. Diễn đạt ngần đó bằng field type của CMS là cuộc chiến không đáng |
| **Đánh đổi** | Phải tự viết CRUD. Chấp nhận được vì phần lớn giá trị nằm ở **trình nhập hàng loạt**, mà cái đó thì CMS nào cũng không có sẵn cho định dạng TOEIC |

### 3.2 — Admin UI ghi thẳng vào database

| | |
|---|---|
| **Chốt** | UI ghi vào DB mà nó đang kết nối. Manifest export tồn tại song song cho backup và bootstrap |
| **Thay vì** | UI xuất ra manifest rồi `seed` nạp vào DB |
| **Vì sao** | **Đây là chỗ thu hẹp phạm vi của `PHASE2-AUDIO` §A2.6.** Lập luận ở đó — "ghi thẳng vào DB ngầm giả định chỉ có một database" — đúng cho *media do script sinh trên máy dev*, nơi DB không phải nguồn sự thật. Với nội dung do nhân viên soạn trong sản phẩm đang chạy, **DB chính là nguồn sự thật**, và đó là hành vi bình thường của mọi hệ CMS. Bắt nó đi vòng qua file commit vào git là bắt người soạn nội dung phải mở pull request |
| **Đánh đổi** | Nội dung không còn được review trong PR. Bù lại bằng quy trình `draft → published` có người duyệt (§3.5) và audit trail (§3.6) |

Hai thứ phục vụ hai mục đích khác nhau, **không phải chọn một**:

```
media do pipeline sinh   → manifest commit vào repo → seed → DB     (PHASE2-AUDIO §A2.6)
nội dung do người soạn   → admin UI → DB                            (tài liệu này)
                                       ↓ export
                             manifest cho backup / bootstrap môi trường mới
```

### 3.3 — Dán-và-parse, không phải điền form từng câu

| | |
|---|---|
| **Chốt** | Dán một khối văn bản từ PDF → parse → lưới review → commit |
| **Thay vì** | Form từng câu · upload file · OCR |
| **Vì sao** | Một đề đầy đủ ≈ 200 câu, ~800 phương án, ~25 đoạn đọc, ~50 transcript — cỡ 40–60 nghìn từ. Điền form từng câu là nhiều ngày. Đề TOEIC đánh số **cực kỳ đều đặn**, nên parser bắt đúng phần lớn và phần còn lại sửa trong lưới |
| **Vì sao không OCR** | Nguồn là PDF **có lớp text**, dán trực tiếp được. OCR sẽ là cả một tầng phụ thuộc thêm cho một vấn đề không tồn tại. Nếu sau này có bản scan thì thêm sau, không phải bây giờ |
| **Đánh đổi** | Parser phải bảo trì khi gặp định dạng lạ. Giảm nhẹ bằng §3.4: parse không bao giờ ghi thẳng, người luôn nhìn thấy trước |

### 3.4 — Parse và commit là hai endpoint tách rời

| | |
|---|---|
| **Chốt** | `POST /admin/import/parse` **không ghi gì** — nhận text, trả cấu trúc đã parse kèm lỗi từ `validate_question()`. `POST /admin/import/commit` mới ghi, và ghi ở trạng thái `draft` |
| **Thay vì** | Một endpoint parse-rồi-insert |
| **Vì sao** | Parser sai ở đâu đó là chuyện chắc chắn xảy ra. Parse-rồi-insert sẽ đặt 200 hàng nửa đúng vào database, và dọn chúng khó hơn là gõ tay lại từ đầu. Tách ra thì lần parse hỏng **không tốn gì cả** — sửa text dán vào, parse lại |
| **Đánh đổi** | Một round-trip nữa. Không đáng kể so với việc mất một buổi dọn dữ liệu rác |

Đây cũng là chỗ **ba ràng buộc ở `ADR-001` §B4 cuối cùng có hiệu lực**. Chúng được viết ra kèm ghi chú "chỉ có hiệu lực nếu có thứ gọi tới nó"; endpoint parse chính là thứ đó.

### 3.5 — Vai trò nằm trên `users`, không phải bảng riêng

| | |
|---|---|
| **Chốt** | `users.role` ∈ {`learner`, `editor`, `admin`} + CHECK, mặc định `learner` |
| **Thay vì** | Bảng `role` + `user_role` (RBAC đầy đủ) |
| **Vì sao** | Ba vai trò, không phân cấp, không quyền theo tài nguyên. RBAC đầy đủ là ba bảng và một tầng kiểm tra quyền cho một bài toán chưa tồn tại |
| **Đánh đổi** | Thêm vai trò thứ tư có ràng buộc phức tạp thì phải migrate. Chấp nhận được — lúc đó sẽ biết rõ ràng buộc là gì, còn bây giờ thì không |

Ranh giới: `editor` soạn và sửa nội dung `draft`; **`admin` mới được publish**. Người viết không tự duyệt bài của mình.

### 3.6 — Audit trail là bắt buộc, không phải tuỳ chọn

| | |
|---|---|
| **Chốt** | `question.created_by`, `published_by`, `published_at` (và tương tự cho `vocabulary_entry`) |
| **Thay vì** | Chỉ có `created_at`/`updated_at` như hiện tại |
| **Vì sao** | Đây là sản phẩm cho người dùng cuối, có nhiều người soạn. Khi một đáp án sai lọt ra tới học viên, câu hỏi đầu tiên là "ai duyệt cái này". Không có cột thì không có câu trả lời, và bổ sung sau thì toàn bộ nội dung cũ vĩnh viễn không truy nguyên được |
| **Đánh đổi** | Ba cột. Cùng lập luận với `question.source` và `image_asset.attribution`: ghi lại **tại thời điểm hành động**, vì sau đó không ai nhớ |

### 3.7 — Audio sinh ngay trong luồng nhập, không upload

| | |
|---|---|
| **Chốt** | Nhập transcript → gọi pipeline TTS hiện có → gắn `audio_asset` |
| **Thay vì** | Upload file mp3 qua UI |
| **Vì sao** | Audio đề gốc không dùng được vì bản quyền, nên upload phục vụ một luồng công việc không tồn tại. Còn `python-multipart`, giới hạn dung lượng, và quét file upload là cả một bề mặt tấn công mới cho đúng con số không lợi ích |
| **Đánh đổi** | Không nhập được audio thu bởi người thật. Đó là quyết định `PHASE2-AUDIO` §A2.2 đã chốt, không phải hạn chế mới |

## 4. Định dạng dán

Không phát minh lại: mượn **ergonomics của Aiken** (dán text thuần, không cú pháp rườm rà). Nhưng Aiken và GIFT đều **không có khái niệm kích thích dùng chung**, nên Part 3 (một đoạn audio, ba câu) và Part 7 (một đoạn văn, nhiều câu) không diễn đạt được. QTI thì có, nhưng là đặc tả XML nặng hơn cả ứng dụng này.

Nên: định dạng riêng, tối thiểu, bám sát đúng cái đã in trên đề.

**Mỗi lần dán là một part, admin chọn part.** Điều này bỏ đi cả một lớp mơ hồ — ví dụ Part 6 và Part 7 đều mở đầu bằng "refer to the following memo", không phân biệt được bằng văn bản.

**Đáp án dán vào ô riêng.** Đề thật để đáp án ở cuối tài liệu, tách rời khỏi câu hỏi.

```
Questions 32-34 refer to the following conversation.

M: Hi, I'm calling about the delivery scheduled for Thursday.
W: Let me check that for you.

32. Why is the man calling?
(A) To reschedule a meeting
(B) To ask about a delivery
(C) To place an order
(D) To report a problem
```

Parser nhận diện: `Questions X-Y refer to the following <loại>.` mở một `question_set`; văn bản tiếp theo là stimulus cho tới câu đánh số đầu tiên; `NNN.` mở một câu; `(A)`–`(D)` là các phương án.

### 4.1 — Part 1 và 2 phải nhập từ phần audioscript

Đây là hệ quả không hiển nhiên của quy tắc "Part 1 và 2 không in gì" (`ADR-001` §A2, `ADR-004` §4.3): **phần đề của Part 1 và 2 trong PDF gần như trống** — chỉ có số câu và ảnh. Bốn câu mô tả và ba phương án nằm ở phần **audioscript** ở cuối tài liệu.

Ai không biết điều này sẽ dán phần đề của Part 1 vào rồi thấy parser trả về rỗng, và tưởng parser hỏng. UI phải nói rõ ngay trên màn hình chọn part.

## 5. Ràng buộc bất biến

### 5.1 — Parse không bao giờ ghi database
Kể cả khi kết quả parse sạch 100%. Người phải nhìn thấy trước rồi mới commit.

### 5.2 — Commit luôn ghi ở `draft`
Không có đường tắt từ import thẳng ra `published`. Publish là hành động riêng, của `admin`, có ghi lại người thực hiện.

### 5.3 — `question.source` không có giá trị mặc định trong UI
Bắt buộc chọn, không pre-select. Một dropdown đã chọn sẵn `original` sẽ biến câu hỏi bản quyền thành một cú Enter vô ý. Đây là cột duy nhất trong hệ thống mà giá trị sai gây hậu quả pháp lý.

### 5.4 — Endpoint admin không bao giờ lộ ra cho `learner`
`require_role` là dependency, không phải kiểm tra trong thân hàm — dễ quên khi thêm route mới. Mỗi endpoint admin cần một test khẳng định `learner` nhận 403.

## 6. Chưa làm (có chủ ý)

- **OCR cho bản scan.** Nguồn hiện tại có lớp text. Thêm khi thật sự gặp bản scan.
- **Nhập từ Excel/Sheets.** Cùng parser, khác adapter đầu vào. Chờ tới khi có nhu cầu thật.
- **Màn hình duyệt nội dung AI sinh.** Quy trình `draft → published` ở đây **dùng lại được nguyên vẹn**; Sprint AI chỉ cần thêm nguồn tạo ra `draft`, không cần thêm quy trình duyệt.
- **Sửa hàng loạt / thao tác theo lô.** Chờ tới khi biết thao tác lặp lại thật sự là gì.
- **Phiên bản hoá nội dung.** `updated_at` và audit trail đủ cho MVP. Lịch sử sửa đổi đầy đủ là một bảng nữa cho một nhu cầu chưa xuất hiện.
