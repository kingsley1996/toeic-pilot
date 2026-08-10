# ADR-007 — Đường đưa một đề thi vào hệ thống

> **Trạng thái:** đã quyết 2026-08-10, sửa thứ tự §2.7 cùng ngày (xem §2.7) · **Thay thế:** không · **Liên quan:** [`ADR-001-DATA-MODEL.md`](ADR-001-DATA-MODEL.md) §A2/§B4, [`ADR-005-CONTENT-TOOLING.md`](ADR-005-CONTENT-TOOLING.md), [`ADR-006-MEDIA-UPLOAD.md`](ADR-006-MEDIA-UPLOAD.md), [`PHASE2-AUDIO.md`](PHASE2-AUDIO.md) §A4, [`MEDIA-PIPELINE.md`](MEDIA-PIPELINE.md) §10.2

---

## 1. Vấn đề

Schema đề thi đã có từ migration `003`, sửa lại ở `011`. Luồng làm bài đã chạy đầu-cuối. Nhưng **không có đường nào đưa một đề vào hệ thống**: `app/api/routes/admin.py` có 28 endpoint, toàn bộ là vocabulary và dictation. Thứ duy nhất từng tạo ra một đề là `app/content/seed_demo_test.py` — một script Python viết tay.

Và trong script đó có một thứ không được phép sống sót sang production:

```python
AudioAsset.source_text.like(f"{starts_with}%")   # "Questions three through five"
```

Câu hỏi tìm clip của nó bằng cách **dò tiền tố văn bản**. Với 5 clip demo thì chạy. Với một đề 200 câu, nơi nhiều bài nói mở đầu bằng cùng một câu dẫn, nó gắn nhầm clip vào câu hỏi và **không có gì báo** — người học nghe một đoạn rồi trả lời câu của đoạn khác.

Gốc rễ không nằm ở phép dò. Nó nằm ở chỗ **kịch bản audio và câu hỏi sống ở hai nơi khác nhau**: kịch bản ở `content/sources/*.jsonl`, câu hỏi ở trong đầu người viết script. Chừng nào còn tách, bước gắn còn phải đoán.

## 2. Các quyết định

### 2.1 Kịch bản audio là một CỘT trên câu hỏi, không phải một file bên cạnh

`question.audio_script` và `question_set.audio_script` — JSON các lượt nói `[{text, voice}]` kèm `gap_ms` và `accent`, đúng hình dạng `ConversationItem` mà `generate.py` đã dùng.

Đây là quyết định trung tâm, và nó gỡ ba thứ cùng lúc:

- **Phép dò biến mất.** Cùng một `conversation_source_hash` vừa dùng để sinh audio vừa dùng để suy ra `storage_key` mà gắn. Một phép tính, một kết quả — không tra cứu, không đoán.
- **`media_state` kiểm được clip nhiều giọng.** `MEDIA-PIPELINE` §10.2 để ngỏ đúng chỗ này: `audio_asset.voice` của clip hội thoại là `"multi"` nên không xác minh được. Có `audio_script` trong database thì xác minh được, và sửa một chữ trong kịch bản sẽ làm đề **không xuất bản được** cho tới khi thu lại — đúng luật đã áp cho transcript dictation.
- **Biên tập viên thấy kịch bản ở nơi họ đang làm việc**, không phải trong một file họ không có quyền sửa.

Đổi lại: kịch bản bị nhân đôi giữa spec file cũ và database. Spec file trong `content/sources/` giữ lại cho nội dung đã sinh; nội dung mới đi qua database.

**Cột này thuộc mảnh TTS (§2.7b), không thuộc lượt đầu.** Một câu có audio tải lên thì `audio_script` là NULL, và đó là giá trị đúng — không có kịch bản nào để đối chiếu.

### 2.2 Soạn TRONG một đề, nhưng không phá bảng nối

Biên tập viên mở một đề rồi soạn lần lượt Part 1 → 7. Không có màn "kho câu hỏi" ở vòng này.

Nhưng `practice_test_question` **vẫn là bảng nối**, và không được biến thành khoá ngoại trên `question`. Màn kho là việc thêm vào sau, không phải viết lại — và luyện theo part sẽ cần nó.

### 2.3 Dán để tạo hàng loạt, form để sửa từng câu

Theo đúng ADR-005: **parse không bao giờ ghi thẳng vào database**. Dán → xem trước → mới ghi.

200 câu mà điền form 200 lần thì không ai làm nổi; nhưng gắn ảnh Part 1, chỉnh kịch bản, viết giải thích thì dán không diễn đạt được. Nên hai bước, không phải hai lựa chọn.

#### Mốc và khoá là **ASCII tiếng Anh**, còn `explanation` viết tiếng Việt

Bản đầu dùng `[CÂU]`, `[NGỮ LIỆU]`, `đáp án:`, `nguồn:` — và hỏng **ngay lần dán đầu tiên**. macOS trả chữ Â ở dạng phân rã, nên `"[CÂU]"` dán vào dài **6** ký tự chứ không phải 5, trong khi hai chuỗi hiện lên **giống hệt nhau**. Trình dán không nhận ra mốc nào, trả về 0 cụm và **0 lỗi**, nên giao diện báo "hợp lệ" cho một thứ nó không đọc được dòng nào.

Vá được thì hết một ca. Đổi bảng chữ cái thì hết **cả lớp lỗi** — ASCII không có dạng phân rã. Nên định dạng chính thức là `[PASSAGE]`, `[QUESTION]`, `answer:`, `source:`, `explanation:`, và nó cũng dễ soát hơn: mốc nổi bật khỏi phần nội dung tiếng Anh xung quanh.

Nội dung của `explanation` thì **viết tiếng Việt**, vì người học đọc nó — định dạng là chuyện của công cụ, lời giải thích là chuyện của người học. Placeholder trong màn quản trị dạy đúng sự phân đôi đó bằng ví dụ.

Dạng tiếng Việt cũ (`[CÂU]`, `đáp án:`) vẫn được nhận để nội dung soạn dở không mất, nhưng thông báo lỗi chỉ nêu dạng tiếng Anh. `_fold` (bỏ dấu + viết hoa) vẫn giữ, vì `[question]` gõ thường là chuyện bình thường.

Và một luật rút ra rộng hơn cái mốc: **không nhận ra gì là một kết quả, và nó phải được nói ra.** Nội dung không rỗng mà không sinh ra cụm nào thì trình dán *từ chối* (400), chứ không trả về danh sách rỗng kèm "0 lỗi".

Mỗi part một định dạng dán riêng, vì bảy part có bảy hình dạng khác nhau — Part 2 in ba đáp án và không in câu hỏi, Part 1 không in gì cả, Part 6/7 có ngữ liệu dùng chung.

### 2.3b Cây có **ba** tầng, và cả ba đều xuất bản riêng

`test_collection` → `practice_test` → `question`/`question_set`. Bản đầu của ADR này chỉ mô tả hai tầng dưới, và màn quản trị dựng theo nó thì **không tạo được bộ đề** cũng **không chuyển được đề vào bộ** — đề tạo ra rơi thẳng vào trạng thái mồ côi, và mồ côi thì người học không có đường nào tới.

Cổng chặn §2.8 vì thế có ba bậc, không phải hai:

| Tầng | Từ chối khi |
|---|---|
| Câu hỏi | `validate_question` còn báo lỗi |
| Đề | còn câu chưa xuất bản — nêu **đúng số câu** |
| Bộ đề | chưa có đề nào đã xuất bản |

Bậc thứ ba tồn tại vì một bộ đề mở ra rỗng không là thứ người học không giải thích được, và không có gì trong giao diện nói cho họ biết vì sao. Cùng luật với cây dictation lọc `published` ở cả bốn tầng.

**Đề không thuộc bộ nào vẫn hợp lệ** (`collection_id` nullable) nhưng người học không nhìn thấy, nên màn quản trị hiện chúng dưới một mục riêng có ghi rõ điều đó — giấu đi thì chúng biến mất khỏi tầm mắt mà vẫn nằm trong database.

`PATCH /admin/tests/{slug}` phân biệt khoá **vắng mặt** với khoá **bằng null**, qua `exclude_unset`: vắng nghĩa là đừng đụng tới, null nghĩa là gỡ khỏi bộ. Một phép gộp `giá trị or cũ` không phân biệt được hai thứ đó, và lỗi thì im lặng — lệnh gỡ trả về 200 mà không đổi gì.

### 2.4 Ảnh Part 1 gắn từ thư viện, không tải lên trong luồng soạn đề

`/admin/media` đã có: tải lên, ba trường bản quyền bắt buộc, ghi công hiện ra. Luồng soạn đề chỉ **chọn** từ đó.

Tách ra vì bản quyền là quyết định riêng: người chọn ảnh cho câu hỏi và người chịu trách nhiệm giấy phép không nhất thiết là một, và ADR-004 §2.2 nói giấy phép chỉ ghi lại trung thực được vào **đúng lúc** thêm ảnh, khi trang nguồn còn đang mở.

### 2.5 `question.source` không có giá trị mặc định, ở bất kỳ tầng nào

NOT NULL, và không được default trong code, trong UI, hay trong định dạng dán. Trình dán **từ chối** cả lô nếu thiếu.

`original` = viết theo định dạng (định dạng không có bản quyền, câu chữ cụ thể thì có). `licensed` = đã thật sự xin được phép. Trả lời sai câu này là rủi ro pháp lý, và một giá trị mặc định là cách chắc chắn nhất để không ai từng trả lời nó.

### 2.6 Số câu là dữ liệu, không phải phép suy ra

`practice_test_question.number` — NOT NULL, tách khỏi `position` (thứ tự sắp xếp).

Khoảng số chuẩn của TOEIC dùng để **gợi ý** lúc lắp đề:

| Part | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Số câu | 1–6 | 7–31 | 32–70 | 71–100 | 101–130 | 131–146 | 147–200 |

Vì sao lưu chứ không suy ra: đề mini sẽ **nhảy cóc** (câu 1, rồi 101, 102). Số nhảy cóc phải là thứ có người nhìn thấy và đồng ý, không phải thứ một hàm tính ra sau lưng. `attempt.py` đọc cột này thay cho `enumerate(start=1)` hiện tại, nên luyện riêng Part 5 hiện đúng 101–130.

### 2.7 Audio: **tải lên trước, sinh tự động sau** — và đó là hai đường riêng

> **Sửa 2026-08-10.** Bản đầu chỉ mô tả đường sinh tự động và đặt nó vào lượt 2. Thứ tự đảo lại: **biên tập viên tự tải file audio lên** là đường chính của luồng soạn đề; sinh tự động bằng TTS là một mảnh **tách riêng**, làm sau.

Đảo thứ tự này gỡ được thứ đắt nhất trong cả ADR: **lượt 2 không cần container mới nữa.** Upload đi qua đúng luồng bốn bước của `ADR-006` §2.3 — xin vé, trình duyệt PUT thẳng lên object store, xác nhận có xác minh — và luồng đó chạy hoàn toàn trong tiến trình HTTP đã có.

Nó cũng cho nội dung chất lượng cao hơn: giọng người thật thay vì TTS, và đó là điều `MEDIA-PIPELINE` §10.6 vẫn để ngỏ.

**Nhưng nó khoét một lỗ trong §2.8, và lỗ này phải nói thẳng.**

`audio_asset.source_hash` của một file tải lên là `upload_source_hash(id ngẫu nhiên)` — **cố ý không suy ra từ nội dung**, vì file người ta tải lên không tái tạo được (đó chính là lý do phải tải lên). Hệ quả: `media_state` **không thể** trả lời "clip này có còn khớp kịch bản không" cho audio tải lên. Nó chỉ trả lời được "có hay không có".

Nên cổng chặn ở §2.8 yếu hơn cho audio tải lên: **thiếu thì chặn được, lệch thì không.** Sửa lời thoại của một câu Part 3 sau khi đã tải bản thu lên sẽ *không* làm đề mất quyền xuất bản — và không có gì báo. Đây là đánh đổi có thật của việc chọn upload, không phải chi tiết cài đặt.

Hai thứ khoanh vùng được nó, và cả hai đều rẻ:

- Màn quản trị hiện **ngày tải lên** cạnh ngày sửa câu hỏi lần cuối. Sửa sau khi tải là thứ nhìn ra được.
- Sửa `prompt_text` hoặc kịch bản của một câu đã có audio tải lên thì **cảnh báo**, không chặn.

#### 2.7b Sinh tự động (TTS) — mảnh riêng, làm sau

Khi làm tới, hình dạng là thế này:

API **không thể** sinh audio — `app/main.py` không được import `app.content` (A4.1), ảnh production không có extra `content`, edge-tts cần mạng, ffmpeg cần cài. Đây là ràng buộc, không phải thiếu sót.

API **không thể** sinh audio — `app/main.py` không được import `app.content` (A4.1), ảnh production không có extra `content`, edge-tts cần mạng, ffmpeg cần cài. Đây là ràng buộc, không phải thiếu sót.

Biên tập viên vẫn cần một nút. Hình dạng rẻ nhất giữ được cả A4.1 lẫn A2.5:

```
bấm nút   → API publish một message Redis. KHÔNG ghi bảng nào.
worker    → thức dậy sớm, chạy đúng truy vấn của backfill_audio
Redis/worker chết → vòng quét định kỳ vẫn bắt được, chỉ muộn hơn
```

**Không có bảng hàng đợi, không có trạng thái retry** — A2.5 nguyên vẹn. Hàng đợi vẫn là *câu hỏi* "nội dung nào thiếu audio hoặc audio không còn khớp kịch bản", nên chạy lại chỉ đơn giản là thấy ít việc hơn, và một job chết không để lại rác.

Redis ở đây là phụ thuộc **mềm**, giống mọi chỗ khác trong dự án (`/ready` báo `degraded` chứ không fail). Nút hỏng thì nội dung vẫn được sinh, chỉ chậm hơn.

**Cái giá thật:** một tiến trình chạy dài mới, có ffmpeg và mạng — hạ tầng mới, không phải code mới. Vì §2.7 đã đảo thứ tự, cái giá này **không còn nằm trên đường tới một đề chạy được**; nó chỉ phải trả khi thật sự muốn TTS.

Một điểm cộng của việc làm sau: đường TTS **có** `audio_script` nên `media_state` xác minh được nó, tức là cổng chặn ở §2.8 mạnh trở lại cho phần nội dung sinh tự động. Hai đường vì thế có hai mức bảo đảm khác nhau, và `audio_asset.source` (`tts` hay `uploaded`) chính là chỗ phân biệt.

### 2.8 Xuất bản bị chặn ở hai tầng, và cả hai đều cần

- **Câu hỏi** không publish được nếu `validate_question` còn báo lỗi, hoặc audio/ảnh thiếu hoặc lệch.
- **Đề** không publish được nếu còn bất kỳ câu nào chưa publish.

`validate_question` đã tồn tại từ ADR-001 §B4 nhưng **chỉ `seed_demo_test` gọi nó** — nó chưa bao giờ là cổng chặn trên đường ghi. Đây là chỗ nó trở thành cổng.

Chặn ở hai tầng vì cùng lý do cây dictation lọc `published` ở cả bốn tầng: một câu nháp nằm trong một đề đã publish sẽ lọt ra, và nội dung đó **trông hoàn toàn bình thường** — không có gì để phát hiện.

## 3. Ràng buộc bất biến

1. **`app/main.py` không được import `app.content`.** Trình dán và trình xác thực chạy lúc có request nên thuộc `app/services/`; sinh audio thuộc `app/content/` và chạy ở worker.
2. **Parse không ghi vào database** (ADR-005). Dán → xem trước → commit là ba bước, không phải một.
3. **`question.source` không bao giờ có default.**
4. **`audio_script` là nguồn để băm.** Sửa nó phải làm `media_state` báo lệch. Nếu một ngày hash không còn suy ra được từ cột này, phép dò tiền tố sẽ quay lại bằng cửa sau.
5. **Số câu lưu, không suy ra** (§2.6).

## 3b. Thứ tự thi công

| Lượt | Phạm vi | Vì sao |
|---|---|---|
| **1** | Part 5, 6, 7 (Đọc) | Không cần audio, không cần worker. Đi hết được luồng dán → sửa → xuất bản → làm bài, nên mọi thứ sai sẽ lộ ra trước khi phần nghe làm nó phức tạp hơn |
| **2** | Part 1, 2, 3, 4 (Nghe) + **tải audio lên** | Dùng lại luồng vé/xác minh của ADR-006 §2.3, mở rộng cho audio. Không hạ tầng mới |
| **3** | Sinh audio bằng TTS (§2.7b) | Mảnh riêng, có container riêng. Chỉ làm khi thật sự cần |

## 4. Chưa làm (có chủ ý)

- **Kho câu hỏi dùng chung.** Schema đã đỡ; UI thì chưa. Đợi tới khi có đề thứ hai cần tái sử dụng câu.
- **Nhập từ file .docx/PDF.** Đề giấy scan cần OCR, và OCR sai một ký tự trong đáp án là một câu hỏi sai vĩnh viễn. Dán văn bản thì người dán đã đọc qua nội dung.
- **Bản thu giọng người thật cho đề.** ADR-006 §2.3 có đường; chưa nối vào luồng soạn đề.
- **Sửa hàng loạt** (đổi accent cả part, thu lại toàn bộ Part 3). Thêm khi thấy đau.

## 5. Điều ADR này KHÔNG giải quyết

**Nội dung.** Sau khi dựng xong toàn bộ đường này, hệ thống vẫn có 0 câu hỏi thật. Viết 200 câu cho một đề — kèm kịch bản nghe, ảnh Part 1 có giấy phép, và giải thích cho từng đáp án — là công việc lớn hơn phần công cụ, và không có công cụ nào rút ngắn được nó.

Đó cũng chính là lý do `ADR-005` tồn tại, và lý do công cụ đi trước nội dung.
