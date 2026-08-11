# ADR-003 — Tầng AI: nhà cung cấp, embedding, và thứ tự làm

**Trạng thái:** đã chốt · 2026-08-12
**Chặn:** toàn bộ Sprint 7. `ADR-001` cắt `knowledge_chunk` / `learning_memory` /
`study_plan` ra khỏi migration `003` với đúng một lý do — chiều `vector(n)` phụ
thuộc quyết định ở đây, và đoán sai thì phải tính lại toàn bộ corpus.

---

## 1. Vì sao tài liệu này tồn tại

`PLAN.md` §4 liệt kê tám năng lực AI. Đọc nhanh thì đó là danh sách việc phải
làm; đọc kỹ thì ba trong tám năng lực **phụ thuộc lẫn nhau qua những quyết định
một chiều**, và làm sai thứ tự sẽ phải làm lại chứ không phải sửa:

- chiều vector quyết định corpus, và corpus quyết định chi phí tính lại
- nhà cung cấp quyết định cách đo chi phí, mà `REVIEW-OPUS.md` §7d gọi chi phí
  LLM hiện tại là **không giới hạn**
- eval harness phải có **trước** khi prompt thay đổi lần đầu, không phải sau
  (§7e), nếu không mọi thay đổi prompt đều là đoán mò

---

## 2. Số liệu đã đo, không phải ước lượng

Đo ngày 2026-08-12 trên database dev:

| | |
|---|---|
| `question` | 40 (38 đã publish) — trên 200 của một đề đầy đủ |
| …có `explanation` | **17** |
| `vocabulary_entry` | 43 |
| `dictation_item` | 15 |
| `attempt` đã nộp | 31, với 122 câu đã trả lời |

Con số thứ hai là con số quan trọng nhất trong bảng này, và nó định đoạt §3.3.

---

## 3. Các quyết định

### 3.1 — Hai nhà cung cấp, định tuyến theo chi phí

| | |
|---|---|
| **Chốt** | Anthropic **và** OpenAI, chọn theo từng việc qua một bộ định tuyến |
| **Thay vì** | Một nhà cung cấp duy nhất |
| **Vì sao** | Đây chính là nghĩa thực tế của "LLM Routing" ở `PLAN.md` §4 — việc rẻ đi model rẻ, việc khó đi model mạnh. Không có nó thì mục đó chỉ là một dòng trong danh sách |
| **Đánh đổi** | **Có thật và đã được nêu ra trước khi chốt:** hai khoá, hai bảng giá, hai kiểu lỗi, ngay từ ngày đầu — tức là nhiều hạ tầng trước khi có một tính năng chạy |

Ràng buộc để cái giá đó không phình ra: **bộ định tuyến là một hàm chọn tầng,
không phải một tầng trừu tượng hoá hai SDK.** Mỗi nhà cung cấp có một adapter
mỏng trả về cùng một dataclass kết quả; phần chung dừng ở đó. Một lớp trừu
tượng "LLM universal" sẽ phải mô phỏng phần giao của hai API và mất đúng những
thứ đáng dùng nhất của từng bên — prompt caching là ví dụ đầu tiên.

`ai_interaction` lưu `provider` và `model` **tách rời** chính là để trả lời được
câu hỏi mà quyết định này sinh ra: *đổi việc X sang model rẻ hơn tiết kiệm được
bao nhiêu.* Gộp thành một chuỗi thì phải parse mới trả lời được.

### 3.2 — Embedding chạy offline bằng model mã nguồn mở, `vector(1024)`

| | |
|---|---|
| **Chốt** | `bge-m3` hoặc `multilingual-e5-large` — cả hai đều **1024 chiều** |
| **Thay vì** | `text-embedding-3-small` (1536) · Voyage |
| **Vì sao** | Ngữ liệu **song ngữ**: nội dung tiếng Anh, giải thích tiếng Việt. Và quan trọng hơn — nó khớp đúng kiến trúc đã có: embedding tính **offline** trong `app/content/`, y như edge-tts, nên API không có thêm phụ thuộc lúc request, chi phí biên bằng 0, và không nội dung nào rời khỏi máy |
| **Đánh đổi** | Máy authoring phải cài model. Cùng loại điều kiện với ffmpeg cho clip nhiều giọng và mạng cho edge-tts — ảnh production không cần và không được có |

**`vector(1024)` là con số chốt.** Ghi ở đây để `knowledge_chunk` và
`learning_memory` không còn bị chặn — nhưng chúng **chưa được tạo**, xem §3.3.

Một hệ quả cần biết trước: đổi model embedding sau này không phải là một
migration cột, mà là **tính lại toàn bộ corpus**. Cùng hình dạng với
`source_hash` của audio — nên chunk phải lưu kèm tên model đã sinh ra nó, để
"vector này có còn đúng model hiện tại không" là một phép so sánh chứ không phải
một giả định.

### 3.3 — Lát cắt mỏng trước, RAG sau

| | |
|---|---|
| **Chốt** | Một use case đầu-cuối **không dùng RAG**: Coach giải thích một câu học viên vừa làm sai |
| **Thay vì** | Dựng corpus + chunking + retrieval + đánh giá trước, theo thứ tự roadmap |
| **Vì sao** | 17 explanation và 43 từ vựng thì **retrieval không có gì để truy hồi**, và §7e đòi eval đi cùng tính năng — không có ngữ liệu thì eval không kết luận được điều gì. Trong khi đó ngữ cảnh mà Coach thật sự cần đã có sẵn dưới dạng **có cấu trúc**: câu hỏi, các phương án, phương án học viên đã chọn, explanation nếu có, và 31 lượt làm bài thật |
| **Đánh đổi** | RAG — một mục trong `PLAN.md` §4 — lùi lại. Không bị bỏ: nó bị chặn bởi ngữ liệu, và đó là một sự thật chứ không phải một lựa chọn |

**Mục tiêu của lát cắt này không phải ship.** Nó là §7f: xác nhận kiến trúc và
**đo chi phí thật** trước khi dự án đi thêm. Xong nghĩa là: một endpoint chạy
được, mọi lượt gọi có một hàng `ai_interaction` với `cost_usd` thật, và từ đó
ngoại suy được chi phí mỗi học viên mỗi tháng.

Điều kiện để mở khoá RAG được ghi thành số, không thành cảm tính: **≥150 câu hỏi
có explanation, hoặc một corpus ngữ pháp riêng ≥200 mục.** Dưới ngưỡng đó,
retrieval trả về gần như toàn bộ corpus với mọi truy vấn, và đo nó là đo nhiễu.

### 3.4 — Ngân sách token: Redis chặn, Postgres ghi sổ

| | |
|---|---|
| **Chốt** | Bộ đếm hạn mức trên Redis; `ai_interaction` là sổ cái bền |
| **Thay vì** | `SUM(cost_usd)` trên Postgres mỗi lượt gọi · một bảng `ai_usage` ghi tổng song song |
| **Vì sao** | Hạn mức phải đọc được **trong một request**, nên nó thuộc về Redis — y như `rate_limit`. Một bảng tổng ghi song song sẽ lệch khỏi sổ cái ngay lần đầu có ai xoá một hàng, và không gì phát hiện ra. Cùng lập luận đã dùng cho `StoryProgress` và `user_progress`: **suy ra, đừng ghi song song** |
| **Đánh đổi** | Redis hỏng thì bộ đếm mất. Xem đoạn dưới — đó là lý do chỗ này **chặn khi hỏng** |

**`fail_open=False` ở đây, ngược với bộ giới hạn đăng nhập.** Lập luận đã viết
sẵn trong `rate_limit`: Redis là **thứ duy nhất** đứng giữa một tài khoản và hoá
đơn của bạn. Cho qua khi Redis hỏng nghĩa là ai hạ được Redis thì có LLM không
giới hạn. Chặn khi hỏng làm mất một tính năng một lúc; cho qua khi hỏng làm mất
tiền, và số tiền đó không có trần.

### 3.5 — Gửi gì sang nhà cung cấp

| | |
|---|---|
| **Chốt** | Nội dung bài học và lựa chọn của học viên. **Không** email, tên, id tài khoản |
| **Thay vì** | Gửi cả ngữ cảnh người dùng cho tiện |
| **Vì sao** | `REVIEW-OPUS.md` §7h nêu đây là một quyết định chưa có. Câu hỏi, phương án, và "học viên chọn B" là **nội dung**, không phải danh tính — mà toàn bộ giá trị của Coach nằm ở phần nội dung đó. Ghép thêm định danh không làm câu trả lời tốt hơn một chút nào, nên đó là rủi ro không mua được gì |
| **Đánh đổi** | Cá nhân hoá theo tên phải làm ở phía ta, sau khi có câu trả lời. Rẻ |

Prompt được dựng từ dữ liệu đã tra, **không bao giờ nối thẳng chuỗi do người
dùng gõ vào vai trò hệ thống**. Đây không phải lo xa: khung chat của Coach là
một ô nhập tự do, và nội dung học viên gõ là dữ liệu, không phải mệnh lệnh —
cùng ranh giới mà phần còn lại của hệ đã áp cho nội dung đọc từ công cụ.

### 3.6 — Eval harness đi cùng tính năng đầu tiên, không đi sau

| | |
|---|---|
| **Chốt** | Bộ eval ra đời cùng endpoint Coach đầu tiên |
| **Thay vì** | Sprint riêng cho evaluation |
| **Vì sao** | §7e nói thẳng: không đo được thì không cải thiện được. Prompt thay đổi nhiều nhất đúng ở quãng đầu, và đó là quãng duy nhất không thể lấy lại nếu không có số |
| **Đánh đổi** | Tính năng đầu tiên tốn gấp rưỡi thời gian |

Giữ đúng luật test của dự án: bộ eval là **một tệp trường hợp + một lệnh chạy**,
không phải một khung. `CLAUDE.md` đã cấm dựng giàn giáo lớn cho test, và một
"eval framework" tự viết là đúng thứ nó cấm.

---

## 4. Cái gì được mở khoá, cái gì vẫn chặn

| | |
|---|---|
| ✅ `ai_interaction` | **đã tạo** (migration `015`), trước request LLM đầu tiên đúng như §7d |
| ✅ Rate limiting | P1-8 xong ở Sprint 6 — điều kiện tiên quyết cứng của endpoint LLM |
| ✅ Chiều vector | chốt 1024, `knowledge_chunk` / `learning_memory` hết bị chặn |
| ⛔ Tạo hai bảng đó | **chưa**, có chủ ý: chưa có gì ghi vào chúng, và §3.3 hoãn RAG |
| ⛔ RAG | chặn bởi **ngữ liệu**, không phải bởi kỹ thuật. Ngưỡng mở ở §3.3 |
| ⛔ Learning Memory | phụ thuộc RAG |

---

## 5. Điều đã biết là sẽ phải sửa

Ba con số dưới đây được đặt để **có cái mà đo**, không phải vì chúng đúng:

- ngưỡng ngữ liệu 150/200 ở §3.3 — chọn theo lập luận, chưa qua thực nghiệm
- ranh giới giữa hai tầng model ở §3.1 — phải đợi số liệu chi phí thật của lát
  cắt mỏng mới định được
- hạn mức token mỗi học viên mỗi ngày — chưa đặt, vì đặt trước khi biết một lượt
  Coach tốn bao nhiêu là đoán. Lát cắt mỏng tồn tại để trả lời đúng câu này

`SPEC-LEARNING-HUB.md` §5 đã có tiền lệ cho cách viết này, và lý do giống hệt:
một con số ghi rõ là tạm thì sửa được; một con số không ai nhớ là tạm thì thành
vĩnh viễn.
