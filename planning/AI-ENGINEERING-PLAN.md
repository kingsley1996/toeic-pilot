# Kế hoạch tầng AI

**Ngày:** 2026-08-12 · **Dựa trên:** `ADR-003-AI-LAYER.md` (các quyết định), `PLAN.md` §4 (tám năng lực), `REVIEW-OPUS.md` §7d–§7h

`PLAN.md` viết rõ mục tiêu: *"thể hiện kỹ thuật AI Engineering ở mức production
chứ không phải tích hợp một chatbot LLM"*. Tài liệu này là kế hoạch để câu đó
thành sự thật kiểm chứng được, chứ không phải một danh sách tính năng có gắn chữ
"AI".

---

## 0. Ba con số đo được, và chúng đổi thứ tự làm việc

Đo ngày 2026-08-12 trên database dev:

| | | Hệ quả |
|---|---|---|
| `question.explanation` | **17 / 40** | RAG không có gì để truy hồi (ADR-003 §3.3) |
| `question.skill_tag` | **0 / 40** | Phân tích điểm yếu **không có chiều nào để phân tích** |
| `user_profile.target_score` | **3 / 53** | Study Planner **không có đầu vào** |

Hai dòng dưới chưa từng được nêu ở đâu, và chúng quan trọng hơn dòng đầu.
`ROADMAP.md` chèn hồ sơ người dùng vào trước Sprint 5 với lý do *"tới Sprint 7
planner đã có dữ liệu thật để đọc"*. Mặt tiếp nhận đã dựng — nhưng **không ai
điền**, nên kết quả thực tế giống hệt tình huống nó định tránh.

Kết luận định hình cả kế hoạch: **việc đầu tiên của tầng AI không phải là nói
chuyện với học viên, mà là làm giàu dữ liệu để những tính năng sau có chỗ đứng.**
Đây cũng là use case AI thuyết phục nhất trong dự án — phân loại 200 câu hỏi vào
nhãn kỹ năng là việc con người làm chậm, chán, và không nhất quán.

---

## 1. Năm nguyên tắc

Mọi quyết định phía dưới suy ra từ đây. Bốn trong năm cái này **đã là luật của
dự án** ở chỗ khác — tầng AI không phát minh nguyên tắc mới, nó áp nguyên tắc cũ
vào một loại phụ thuộc mới.

**N1 — Model là thứ đắt nhất, chậm nhất và kém tin cậy nhất trong hệ. Chỉ dùng
cho việc mà chỉ nó làm được.** Chấm điểm, quy đổi điểm, SM-2, diff dictation đều
là số học thuần và đã có test. Đưa chúng qua LLM là đổi một hàm đúng-mọi-lúc lấy
một hàm đúng-hầu-hết, tốn tiền, và không kiểm được.

**N2 — Tính trước, đừng tính lúc request.** Dự án đã có sẵn khuôn mẫu và nó chạy
tốt: `app/content/` sinh audio ngoài luồng, API không bao giờ gọi TTS. Phần lớn
đầu ra AI ở đây cũng **tất định theo nội dung, không theo người học** — xem §3.

**N3 — Suy ra, đừng ghi song song.** Đã áp cho `StoryProgress`, `VocabularyProgress`,
`user_progress`. Áp tiếp cho "điểm yếu của học viên": nó là một truy vấn trên
`attempt_item`, không phải một bảng ghi kèm sẽ lệch khỏi lịch sử ở lần xoá đầu tiên.

**N4 — Từ chối đoán.** `scoring.py` ném lỗi thay vì nội suy khi thiếu bảng quy
đổi, vì một điểm số sai âm thầm sẽ nằm vĩnh viễn trên lượt làm bài. Cùng luật:
một kế hoạch học trỏ tới bài học không tồn tại thì **không được ghi**, chứ không
phải ghi rồi hỏng lúc học viên bấm vào.

**N5 — Đo trước khi tối ưu.** Không có bộ eval thì mọi thay đổi prompt là đoán,
và định tuyến theo chi phí là đoán có tổ chức.

---

## 2. Bản đồ: AI làm gì, và tuyệt đối không làm gì

**Không bao giờ dùng LLM** — đây là nửa quan trọng hơn của bản đồ:

| Việc | Vì sao không |
|---|---|
| Chấm câu trắc nghiệm | So sánh FK. Đúng 100%, miễn phí, tức thời |
| Quy đổi điểm thô → điểm quy đổi | `score_conversion` là dữ liệu; sai số ở đây nằm vĩnh viễn trên lượt làm bài |
| Lịch ôn SM-2 | Số học thuần, đã có test, đã có port sang JS |
| Chấm dictation | `SequenceMatcher`, và **hai phía phải khớp nhau từng bước** — một bên là LLM thì không bao giờ khớp |
| Quyết định điểm yếu | `GROUP BY skill_tag` trên dữ liệu thật. LLM **kể lại**, không **tính ra** |

Ranh giới chung: **LLM diễn giải, hệ thống quyết định.** Con số nào đi vào cơ sở
dữ liệu hoặc đi vào mắt học viên như một sự thật thì phải do code tính.

---

## 3. Bốn tầng phục vụ

Đây là phần kiến trúc quan trọng nhất, và nó đến từ một quan sát về miền:
**lời giải thích cho một câu hỏi là như nhau với mọi học viên.** Đề TOEIC là một
tập cố định; "vì sao đáp án B sai" không phụ thuộc người đọc.

| Tầng | Là gì | Dùng cho | Chi phí mỗi request |
|---|---|---|---|
| **T0** | Không gọi model. Đọc bản đã sinh sẵn hoặc cache | Giải thích câu hỏi, ví dụ từ vựng | **0** |
| **T1** | Model rẻ, có cấu trúc đầu ra | Diễn giải lỗi dictation, tóm tắt ngắn | thấp |
| **T2** | Model mạnh | Sinh kế hoạch học, phân tích nhiều lượt làm bài | cao, hiếm |
| **T3** | Pipeline offline trong `app/content/` | Làm giàu nội dung: `skill_tag`, `explanation`, embedding | trả một lần |

**Phần lớn lưu lượng phải rơi vào T0.** Với một đề 200 câu, số lời giải thích cần
có là 200 câu × 3 phương án sai = **600** — sinh một lần ở T3, duyệt một lần, phục
vụ mãi mãi. So với sinh lúc request: 600 × mỗi học viên × mỗi lần xem lại.

Điều này **không** làm tầng AI kém "AI" đi. Nó là khác biệt giữa một hệ thống có
người thiết kế và một hệ thống gọi API mỗi lần có người bấm nút. Đường gọi trực
tiếp vẫn tồn tại, dành cho phần đuôi thật sự cần cá nhân hoá.

Ba tính chất đi kèm, và cả ba là dividend chứ không phải công thêm:

- **Duyệt được trước khi học viên thấy.** `CONTENT_STATUSES` với trạng thái
  `draft` đã có sẵn; nội dung AI sinh ra đi đúng cổng duyệt mà nội dung người
  viết đang đi. Không có cổng đó, một câu giải thích sai ngữ pháp là một bài học
  sai được dạy cho mọi học viên.
- **Không có độ trễ.** Không có spinner, không có timeout, không có "AI đang suy nghĩ".
- **Nhà cung cấp sập không ảnh hưởng gì.** Cùng lập luận với `PHASE2-AUDIO` §A: sinh
  offline nghĩa là sự cố chặn **nội dung mới**, không làm hỏng thứ đang chạy.

---

## 4. Sáu use case, theo thứ tự phụ thuộc

### UC1 — Làm giàu nội dung (T3, offline) · **làm trước tiên**

Hai đầu ra, cùng một pipeline:

- **`skill_tag`** cho mọi câu hỏi. Đây là chiều mà UC3 phân tích. Không có nó,
  "bạn yếu phần nào" chỉ trả lời được ở mức *part*, mà "yếu Part 5" thì học viên
  đã tự biết và không hành động được. "Yếu thì quá khứ hoàn thành" thì hành động được.
- **`explanation`** cho từng phương án sai, không chỉ cho câu hỏi.

Chạy y như `backfill_audio`: hàng đợi là một **truy vấn** ("câu nào chưa có nhãn"),
không phải một bảng job — nên chạy lại chỉ đơn giản là tìm được ít việc hơn.

Nhãn kỹ năng lấy từ **một danh sách đóng** khai báo trong code, không để model tự
nghĩ ra chuỗi. Model tự đặt tên sẽ cho `"verb tense"`, `"tenses"`, `"Verb Tenses"`
là ba nhãn khác nhau, và `GROUP BY` sẽ chia đôi mọi thống kê mà không báo lỗi.

**Đây là use case AI thuyết phục nhất trong dự án**: 200 câu × phân loại là việc
người làm chậm và không nhất quán, còn máy làm nhất quán theo đúng định nghĩa của
danh sách đóng.

### UC2 — Coach giải thích câu vừa làm sai (T0 + dữ liệu thật)

Ngữ cảnh **không** phải "câu hỏi và đáp án". Nó là:

```
câu hỏi · các phương án · đáp án đúng · phương án học viên chọn
· explanation đã duyệt · skill_tag
· thống kê distractor: bao nhiêu % học viên khác cũng chọn phương án đó
```

Dòng cuối là thứ một chatbot bọc API không có, và nó có được vì
`attempt_item.selected_option_id` là **FK thật** — `ADR-001` §A4.1 chọn bảng
`question_option` thay vì JSONB với đúng lý do này, viết ra từ trước khi có tầng
AI. Câu hỏi "học viên hay sa vào bẫy nào" là một câu `GROUP BY`; với JSONB nó là
một cuộc migrate. Đã kiểm chạy được trên dữ liệu hiện có.

Đầu ra **có cấu trúc**, không phải văn xuôi:

```
chan_doan · vi_sao_phuong_an_ban_chon_sai · vi_sao_dap_an_dung
· quy_tac (trỏ tới skill_tag) · bay_tuong_tu
```

Có cấu trúc vì hai lý do độc lập: giao diện render theo mục, và **eval kiểm được
từng trường**. Một khối văn xuôi thì chỉ chấm bằng cảm tính.

### UC3 — Phân tích điểm yếu (SQL tính, LLM kể)

`GROUP BY skill_tag` cho ra tỉ lệ đúng theo từng kỹ năng. Đó là **con số**, và nó
do code tính (N1). Việc của model là xếp thứ tự ưu tiên và diễn đạt sao cho học
viên hành động được — *"ba buổi tới nên tập trung vào X"* — chứ không phải tính
ra X.

Kiểm được: con số trong câu trả lời phải **khớp** con số truy vấn ra. Đây là một
khẳng định tất định, không phải một điểm chấm của giám khảo — xem §6.

### UC4 — Study Planner (T2, structured output, có ràng buộc FK)

Chặn bởi đầu vào: **3/53 hồ sơ có điểm mục tiêu.** Hai đường đi, làm cả hai:

1. Hỏi lúc onboarding — đây là vấn đề sản phẩm, không phải vấn đề AI
2. **Suy từ lịch sử làm bài** khi hồ sơ trống. 31 lượt đã nộp đủ để ước lượng
   điểm hiện tại; điểm mục tiêu thì phải hỏi

Đầu ra là `study_plan` + `study_plan_item` (ADR-001 Phần C). Ràng buộc quan trọng
nhất: **mọi mục trong kế hoạch phải trỏ tới nội dung có thật.** Model đề xuất
"luyện bài đọc số 12" trong khi không có bài nào như vậy là ảo giác được ghi vào
database. Nên: model chọn **từ danh sách đã tra ra** qua tool calling, và tầng
ghi **từ chối** kế hoạch có tham chiếu treo (N4).

### UC5 — Giải thích lỗi dictation (T1)

Diff đã có và tất định. Model trả lời câu mà diff không trả lời được: *vì sao*
nghe nhầm — nối âm, âm cuối bật nhẹ, cặp âm dễ lẫn. Ngữ cảnh nhỏ, đầu ra ngắn,
đúng tầm model rẻ.

### UC6 — Hỏi đáp tự do + RAG · **chặn bởi ngữ liệu**

Ngưỡng mở khoá đã ghi thành số ở ADR-003 §3.3. Khi tới:
tìm kiếm lai (BM25 + vector) chứ không thuần vector — thuật ngữ ngữ pháp TOEIC
là loại khớp chính xác (*"present perfect continuous"*), mà tìm kiếm ngữ nghĩa
thuần lại yếu nhất đúng ở loại truy vấn đó.

---

## 5. Tám năng lực của `PLAN.md` §4 — kế hoạch cụ thể

Kèm ghi chú thật thà về việc làm ẩu thì cái nào thành hình thức.

| Năng lực | Làm gì | Làm ẩu thì thành gì |
|---|---|---|
| **Prompt Engineering** | Prompt là **tệp có phiên bản**, hash ghi vào `ai_interaction`. Đổi prompt là một diff xem lại được, và truy được kết quả nào sinh từ bản nào | Chuỗi ký tự trong code, không ai biết bản nào tạo ra câu trả lời nào |
| **Structured Output** | Schema Pydantic + structured output của nhà cung cấp. Hỏng validation → thử lại một lần → **hỏng to**, không nuốt | Regex bóc JSON ra khỏi markdown |
| **Tool Calling** | Coach tra dữ liệu qua tool thay vì nhồi hết vào prompt. **Tool không nhận `user_id` từ model** — xem §8 | Tool chỉ để khoe, trong khi ngữ cảnh vẫn nhồi sẵn |
| **RAG** | Hoãn có ngưỡng số (ADR-003 §3.3). Khi làm: tìm kiếm lai + rerank + đo retrieval tách khỏi đo sinh văn | Nhét mọi thứ vào vector store rồi tin vào top-5 |
| **Learning Memory** | **Phần lớn là dữ kiện có cấu trúc suy ra từ `attempt_item`** (N3), vector chỉ cho ghi chú mở | Một bảng embedding ghi song song, lệch dần khỏi lịch sử làm bài |
| **LLM Routing** | Tầng theo độ khó việc, và **đo tỉ lệ leo thang** — T1 phải leo lên T2 bao nhiêu % thì T1 hết đáng dùng | Một câu `if` chọn model, không ai biết chọn đúng hay sai |
| **Evaluation** | §6 | Vài prompt chạy tay, "trông ổn" |
| **Observability** | `ai_interaction` đã có. Thêm: phiên bản prompt, tool đã gọi, số lần thử lại, cache trúng hay trượt | Ghi log request, không ghi chi phí |

---

## 6. Eval — phần tách AI engineering khỏi gọi API

Đi **cùng** tính năng đầu tiên, không đi sau (`REVIEW-OPUS.md` §7e). Ba lớp, và
lớp đầu quan trọng hơn người ta tưởng.

### 6.1 Khẳng định tất định — chạy mỗi lần, gần như miễn phí

Kiểm được bằng code thường, không cần giám khảo:

- lời giải thích **có nêu đúng chữ cái đáp án đúng** không
- có nhắc tới **phương án học viên đã chọn** không
- `skill_tag` trả về có nằm trong **danh sách đóng** không
- con số ở UC3 có **khớp truy vấn** không
- có phải tiếng Việt không, và dài trong khoảng cho phép không

Phần lớn lỗi thật rơi vào đây. Một câu giải thích trôi chảy nhưng nêu sai chữ cái
đáp án là lỗi tệ nhất trong sản phẩm này, và nó bị bắt bằng một phép so sánh chuỗi.

### 6.2 Giám khảo LLM có rubric — chạy khi đổi prompt

Cho phần không kiểm được bằng code: giải thích có đúng về mặt ngữ pháp không, có
dạy được không, giọng có phù hợp người mới không.

Hai ràng buộc bắt buộc:

- **Giám khảo phải khác model sinh.** Model chấm bài của chính nó thì thiên vị bản
  thân, và điểm sẽ đẹp lên mà chất lượng không đổi.
- **Có bộ tham chiếu vàng.** 17 explanation người viết sẵn có là điểm neo — không
  phải để so từng chữ, mà để giám khảo biết "đạt" trông như thế nào.

### 6.3 Cổng hồi quy

Đổi prompt mà tỉ lệ đạt tụt thì **không merge**. Đây là điều biến prompt từ thứ
sửa theo cảm hứng thành thứ có kiểm soát phiên bản.

Giữ đúng luật test của dự án (`CLAUDE.md`): **một tệp trường hợp + một lệnh chạy.**
Một "eval framework" tự viết chính là loại giàn giáo mà tài liệu đó cấm.

---

## 7. Chi phí — các đòn bẩy, xếp theo hiệu quả thật

| Đòn bẩy | Mức giảm | Ghi chú |
|---|---|---|
| **Tính trước ở T3** | ~99% cho đường phổ biến | Sinh 600 lần thay vì 600 × số học viên |
| **Cache theo khoá tất định** | phần còn lại | Khoá là `(question_id, phương_án_đã_chọn)` — **không cần embedding**, vì cùng câu hỏi và cùng lựa chọn thì cùng câu trả lời |
| **Prompt caching** | 50–90% phần cố định | System prompt và ngữ cảnh dùng chung là phần cố định. `cached_tokens` tách riêng chính là để đo cái này |
| **Định tuyến theo tầng** | tuỳ tỉ lệ | Chỉ đo được sau khi có §6 |
| **Hạn mức mỗi học viên** | trần cứng | Redis, **fail closed** (ADR-003 §3.4) |

Hai dòng đầu là **kiến trúc**, không phải tối ưu — và chúng lớn hơn ba dòng dưới
cộng lại. Đó là lý do §3 đứng trước mọi thứ khác trong tài liệu này.

Lát cắt mỏng tồn tại để trả lời một câu chưa ai trả lời được: **một học viên tốn
bao nhiêu một tháng.** Đặt hạn mức trước khi biết con số đó là đoán.

---

## 8. Guardrails

**Ô nhập của học viên là dữ liệu, không phải mệnh lệnh.** Nội dung học viên gõ đi
vào lượt người dùng, **không bao giờ nối vào vai trò hệ thống**. Đây là cùng một
ranh giới mà phần còn lại của hệ đã áp cho nội dung đọc từ công cụ.

**Tool không nhận `user_id` làm tham số từ model.** Nó lấy từ phiên đăng nhập.
Một tool `get_attempts(user_id)` mà model điền tham số là một endpoint đọc dữ liệu
người khác, và câu khiến nó điền sai chỉ cần nằm trong ô nhập tự do. Đây là lỗi
bảo mật, không phải lỗi prompt.

**Đầu ra không bao giờ render thành HTML.** Văn bản là văn bản.

**Nhà cung cấp sập thì hạ cấp có phẩm giá:** T0 vẫn chạy (không cần model), và
đường trực tiếp báo rõ là tạm thời không dùng được — không giả vờ thành công.

**Gửi gì:** nội dung bài học và lựa chọn của học viên. Không email, không tên,
không id tài khoản (ADR-003 §3.5).

---

## 9. Lộ trình

| Lát | Nội dung | Xong nghĩa là |
|---|---|---|
| **A** | Bộ khung: adapter hai nhà cung cấp, bộ định tuyến, ghi `ai_interaction`, hạn mức Redis, prompt có phiên bản | Một lượt gọi thật để lại một hàng có `cost_usd` thật |
| **B** | UC1 làm giàu `skill_tag` (offline, có cổng duyệt) | 40/40 câu có nhãn từ danh sách đóng |
| **C** | UC2 Coach + eval §6.1 và §6.2 cùng lúc | Giải thích cho mọi phương án sai, qua cổng hồi quy |
| **D** | UC3 phân tích điểm yếu | Con số trong câu trả lời khớp truy vấn |
| **E** | UC4 Study Planner | Không kế hoạch nào ghi được với tham chiếu treo |
| **F** | UC6 + RAG | **Chỉ khi qua ngưỡng ngữ liệu** ở ADR-003 §3.3 |

A và B trước C là có chủ ý: C không đo được nếu B chưa có nhãn, và không tính được
chi phí nếu A chưa ghi sổ.

---

## 9b. KPI cho lát B — làm giàu dữ liệu

Đo ngày 2026-08-12, sau khi **loại 21 lượt của tài khoản e2e** (trung bình đúng
1 câu mỗi lượt — chính bộ test tạo ra chúng, và tính chung vào thì mọi trung
bình đều sai):

| | |
|---|---|
| Người thật | 45 lượt · 111 câu đã trả lời · **trung bình 4.7 câu/lượt** |
| Lượt dài nhất | 17 câu |
| Ngữ liệu | 40 câu hỏi · **120 phương án sai** · Part 5 chiếm 16/40 |

### B1 — Độ phủ · ngưỡng **100%**, không phải 95%

Mọi câu hỏi đã publish phải có `skill_tag`. Không đặt 95% vì một câu thiếu nhãn
**biến mất im lặng khỏi mọi `GROUP BY`** — báo cáo vẫn ra một con số trông hợp
lý, chỉ là nó bỏ sót. Không ai nhìn thấy phần bị bỏ sót.

Lời giải thích thì khác: pipeline phải **thử** 100% và **sinh được ≥98%**. Vài
câu hỏng được báo cáo rồi bỏ qua chứ không làm sập cả lượt chạy — cùng cách
`images.py` xử lý một ảnh tải hỏng, và vì cùng lý do: một lượt chạy dài mà đổ ở
câu thứ 180 thì mất cả 179 câu trước.

### B2 — Hình dạng bộ nhãn · nơi hỏng tinh vi nhất

Bộ nhãn quá mịn thì mỗi nhãn chỉ còn một hai câu, và học viên **không bao giờ
trả lời đủ** để báo cáo điểm yếu có nghĩa. Bộ nhãn quá thô thì mọi thứ là "ngữ
pháp" và báo cáo không nói được gì. Bốn ràng buộc, kiểm được bằng một câu SQL:

| Ràng buộc | Ngưỡng | Vì sao |
|---|---|---|
| Số nhãn | <100 câu → **6–8** · 100–300 → 10–14 · >300 → tối đa 20 | Bộ nhãn **giãn theo ngữ liệu**. Chia nhỏ về sau chỉ là chạy lại pipeline, vì hàng đợi là một truy vấn |
| Nhãn nhỏ nhất | **≥5%** ngữ liệu | Dưới mức đó học viên không gặp đủ câu để con số nói lên điều gì |
| Nhãn lớn nhất | **≤30%** | Một nhãn ôm một phần ba thì nó không phân biệt được gì |
| Nhãn `khác` | **<5%** | Đây là **cảm biến**: `khác` phình lên nghĩa là bộ nhãn thiếu, không phải nội dung lạ |

Với 40 câu hôm nay, luật này làm việc thật ngay: Part 5 có 16 câu, nếu để chung
một nhãn "ngữ pháp" là 40% — vượt trần, buộc phải tách thành thì, hoà hợp
chủ–vị, từ loại, giới từ…

### B3 — Độ đúng của nhãn · ngưỡng **≥90%**

Đo bằng cách gắn nhãn tay rồi so. Với 40 câu thì **gắn tay toàn bộ** — rẻ và cho
chắc chắn; từ 200 câu trở lên thì lấy mẫu 40.

**Tham chiếu ghi một TẬP nhãn chấp nhận được, không phải một nhãn.** Một câu
TOEIC có thể kiểm cả thì lẫn hoà hợp chủ–vị cùng lúc; đòi khớp đúng một nhãn là
phạt máy vì một câu hỏi vốn có hai câu trả lời đúng. KPI là *nhãn máy đoán ∈ tập
chấp nhận được*.

Vì sao 90 mà không phải 95: với mẫu 40, 90% nghĩa là **tối đa 4 câu sai**. Phân
biệt 90% với 95% cần cỡ mẫu lớn hơn nhiều so với mức gắn tay nổi — đặt một con
số mà phép đo không phân giải được là diễn.

### B4 — Tính nhất quán · ngưỡng **≥98%**

Chạy hai lượt ở `temperature=0`, so hai kết quả. Không ổn định ở đây nghĩa là
một phần của nhãn là **nhiễu**, và mọi `GROUP BY` về sau thừa hưởng nguyên phần
nhiễu đó mà không có gì báo.

### B5 — Lời giải thích · **cổng 100%**, không phải chỉ tiêu phần trăm

Năm khẳng định tất định ở §6.1 — nêu đúng chữ cái đáp án, có nhắc phương án
người học chọn, tiếng Việt, độ dài trong khoảng, không bịa ngoài đề. Đây là
**cổng**: không đạt thì sinh lại, không phải hạ chuẩn xuống 95%.

Lý do đặt cứng: một lời giải thích trôi chảy nhưng **nêu sai chữ cái đáp án** là
lỗi tệ nhất mà sản phẩm này có thể mắc — nó dạy sai, và người học tin. Nó bị bắt
bằng một phép so sánh chuỗi, nên không có cớ nào để cho qua.

### B6 — Tỉ lệ phải sửa tay · ngưỡng **≥70% dùng được ngay**

KPI mà người ta hay quên, và là KPI **kinh tế** thật sự của cả lát này. Mọi đầu
ra đều đi qua cổng duyệt `draft`, nên câu hỏi đúng không phải "máy viết có hay
không" mà là: **đáng duyệt hơn hay đáng viết tay hơn?**

Nếu người duyệt phải viết lại một nửa thì pipeline không tiết kiệm được gì —
đọc và sửa một bản nháp tệ tốn công ngang viết mới. Nên: ≥70% được publish mà
không sửa hoặc chỉ sửa vặt. Dưới ngưỡng đó, vấn đề nằm ở prompt chứ không ở
người duyệt.

### B7 — Chi phí · **đo, không đặt chỉ tiêu**

Lát B là lần đầu có số thật. Nhưng phép nhân sơ bộ đã trả lời được một câu quan
trọng — với một đề 200 câu, khoảng 400 lượt gọi (một cho nhãn, một cho cả ba
phương án sai của mỗi câu), tầm 1500 token vào và 400 ra mỗi lượt:

| | Model rẻ | Model mạnh |
|---|---|---|
| Toàn bộ đề 200 câu | ~**0,2 USD** | ~**4 USD** |

**Nên chi phí KHÔNG phải ràng buộc của T3, và kết luận đi ngược trực giác: lát
làm giàu dùng model MẠNH.** Nó chạy một lần, kết quả được duyệt rồi phục vụ mãi
mãi, và bốn đô cho một đề là rẻ hơn nhiều so với công người sửa lại một bản nháp
kém. Tầng rẻ tồn tại cho đường *lúc request*, không phải cho đây.

### B8 — Vận hành

- Chạy lại được, và chạy lại chỉ tìm thấy ít việc hơn — hàng đợi là một **truy
  vấn**, không phải bảng job, y như `backfill_audio`
- Một câu hỏng không làm sập cả lượt
- **Không gì tự publish.** Tất cả rơi vào `draft`

### Mức tối thiểu để coi là xong

| | Bắt buộc | Mong muốn |
|---|---|---|
| Độ phủ nhãn | 100% | — |
| Sinh được lời giải thích | ≥98% | 100% |
| Số nhãn | 6–8 (ở 40 câu) | — |
| Nhãn nhỏ nhất / lớn nhất / `khác` | ≥5% / ≤30% / <5% | — |
| Độ đúng của nhãn | **≥90%** trên mẫu gắn tay | ≥95% |
| Nhất quán giữa hai lượt chạy | **≥98%** | 100% |
| Cổng tất định của lời giải thích | **100%** | — |
| Dùng được ngay, không sửa | **≥70%** | ≥85% |

### Một điều KPI này KHÔNG hứa

Gắn nhãn đạt hết các ngưỡng trên **vẫn chưa** làm cho phân tích điểm yếu chạy
được. Người thật đang trả lời trung bình 4.7 câu mỗi lượt, lượt dài nhất 17 câu
— nên chưa ai có đủ dữ liệu để nói "bạn yếu thì quá khứ hoàn thành" mà không
phải đoán. Đó là **cổng riêng của lát D**, và nó phải được viết ra ở đó: không
báo cáo một nhãn cho tới khi học viên đã trả lời đủ số câu mang nhãn đó. Lát B
làm cho việc ấy *khả thi*; nó không làm cho việc ấy *đúng*.

---

## 10. Điều đã biết là sẽ phải sửa

Ghi rõ ra để chúng không lặng lẽ thành vĩnh viễn — cùng lý do `SPEC-LEARNING-HUB.md`
§5 tồn tại.

- **Danh sách nhãn kỹ năng đóng** sẽ sai ở lần chạm dữ liệu thật đầu tiên. Sai kiểu
  sửa được: thêm nhãn thì chạy lại pipeline, vì hàng đợi là một truy vấn
- **Ranh giới T1/T2** đang là phỏng đoán. Chỉ tỉ lệ leo thang mới định được
- **Hạn mức token mỗi ngày** chưa đặt, có chủ ý — lát A tồn tại để đo
- **Cache theo `(question_id, phương_án)`** giả định lời giải thích không phụ thuộc
  người học. Đúng ở hôm nay; sẽ sai vào ngày giải thích được cá nhân hoá theo
  trình độ, và khi đó khoá cache phải mang thêm một chiều
