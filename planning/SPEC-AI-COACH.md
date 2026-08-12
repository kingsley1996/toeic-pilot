# SPEC — AI Coach

**Ngày:** 2026-08-12 · **Trạng thái:** provisional, dựng để sửa (như `SPEC-LEARNING-HUB.md`)
**Dựa trên:** `ADR-003-AI-LAYER.md` (quyết định nền), `AI-ENGINEERING-PLAN.md` §3–§8

---

## 0. Coach đứng trên cái gì — đo, không ước lượng

Đo ngày 2026-08-12, đã loại tài khoản `e2e-*`:

| | | Dùng để làm gì |
|---|---|---|
| Câu có nhãn kỹ năng | **40 / 40** | neo lời giải vào một điểm ngữ pháp cụ thể |
| Câu Part 5–6 có nhãn `grammar` | **22** | gợi ý ôn tập cùng điểm ngữ pháp |
| Phương án sai | **120** | số lời giải nếu tính trước |
| Lượt trả lời **sai thật sự** | **52** | số lời giải nếu sinh lúc cần |
| Câu có `explanation` người viết | 17 / 40 | điểm neo cho giám khảo eval |

Đã có sẵn và không phải dựng lại: sổ cái `ai_interaction` (chi phí, độ trễ, token,
`prompt_version`, `cache_hit`), gateway với hạn mức **fail closed**, bộ định tuyến hai tầng,
prompt có phiên bản, và màn xem lại của học viên — nó **đã có** bộ lọc "Câu sai" cùng khối
render `question.explanation`, tức là chỗ đặt Coach đã tồn tại.

`attempt_item.selected_option_id` là **khoá ngoại thật**, nên "học viên hay sa vào bẫy nào" là
một câu `GROUP BY`. `ADR-001` §A4.1 chọn bảng `question_option` thay vì JSONB với đúng lý do
này, viết ra từ trước khi có tầng AI.

### 0.1 Một con số sửa lại kế hoạch cũ

`AI-ENGINEERING-PLAN` §3 khuyên **tính trước 600 lời giải**. Lập luận vẫn đúng — lời giải cho
một câu là như nhau với mọi học viên — nhưng phép tính đã sai chiều: **120 phương án cần sinh
so với 52 lượt sai đã từng xảy ra**. Điểm hoà vốn chưa tới, vì số học viên còn nhỏ hơn số câu.

Cách không phải chọn: **sinh lúc cần, cache theo khoá tất định**. Người đầu tiên gặp câu đó trả
tiền, mọi người sau miễn phí, và hệ thống **tự hội tụ về trạng thái tính-trước theo nhu cầu
thật** — không bao giờ sinh thứ không ai xem. Khi số học viên vượt số câu, hành vi tự đảo chiều
mà không phải sửa mã.

---

## 1. Ba năng lực, và một trong ba không gọi model

| | Năng lực | Gọi model? | Cache? |
|---|---|---|---|
| **A** | Giải thích câu vừa làm sai | có | **có** — khoá tất định |
| **B** | Gợi ý ôn tập theo nhãn kỹ năng | **không** | không cần |
| **C** | Hỏi đáp neo vào ngữ cảnh | có | không |

**B không gọi model, và đó là chủ ý.** "Bạn sai câu này, đây là bốn câu khác cùng
`GRAMMAR_TENSE` nên làm" là một truy vấn `WHERE code = ... AND id <> ...`. Đưa nó qua LLM là đổi
một câu SQL đúng-mọi-lúc lấy một câu trả lời đúng-hầu-hết, tốn tiền, và có thể trỏ tới câu không
tồn tại. Nguyên tắc N1 của `AI-ENGINEERING-PLAN`.

Năng lực B dùng được **ngay hôm nay** vì 40/40 câu đã có nhãn.

---

## 2. A — Giải thích câu sai

### 2.1 Ngữ cảnh gửi đi

Không phải "câu hỏi và đáp án". Là:

```
câu hỏi · các phương án · đáp án đúng · phương án học viên đã chọn
· explanation người viết (nếu có) · nhãn kỹ năng của câu và của nhóm
· thống kê distractor: bao nhiêu % học viên khác cũng chọn phương án đó
```

Dòng cuối là thứ một chatbot bọc API không có. Dòng áp chót là thứ **chỉ có được sau lát B** —
Coach nói *"câu này kiểm thì và thể"* thay vì giải thích trôi nổi.

### 2.2 Đầu ra có cấu trúc

```
chan_doan · vi_sao_ban_chon_sai · vi_sao_dap_an_dung · quy_tac · bay_tuong_tu
```

Có cấu trúc vì hai lý do độc lập: giao diện render theo mục, và **eval kiểm được từng trường**.
Một khối văn xuôi chỉ chấm được bằng cảm tính.

### 2.3 Cache — và `prompt_version` PHẢI nằm trong khoá

```
khoá = (question_id, selected_option_id, prompt_version)
```

Bỏ `prompt_version` ra khỏi khoá là một lỗi im lặng đắt: sửa prompt xong, mọi học viên đã có bản
cache vẫn nhận bản cũ **vĩnh viễn**, và người sửa không có cách nào biết bản sửa của mình chưa
tới ai. Có nó trong khoá thì đổi prompt tự động làm mới, và `cache_hit` tụt xuống rồi bò lên —
một tín hiệu nhìn thấy được.

Lưu ở **bảng** chứ không ở Redis: đây là nội dung, nó cần sống qua restart, cần duyệt được, và
cần gắn phản hồi của học viên vào. Redis giữ hạn mức; Postgres giữ nội dung.

### 2.4 Duyệt sau, không chặn trước

Học viên đầu tiên thấy bản chưa duyệt. Đổi lại, mọi bản sinh ra vào **hàng đợi duyệt** ở admin,
và bản bị bỏ sẽ được sinh lại ở lần gặp sau. Đây là đánh đổi có ý thức: chặn trước thì phải sinh
120 lời giải cho 52 lượt sai, còn để đó không duyệt thì §2.4 này không tồn tại.

---

## 3. C — Hỏi đáp NEO vào ngữ cảnh

### 3.1 Vì sao neo chứ không mở

Không có ngữ liệu thì model trả lời từ trí nhớ của nó: trôi chảy, đôi khi sai, và **học viên
không có cách nào biết là sai** — đúng thứ `PLAN.md` nói không làm. Neo vào câu đang xem hoặc
lượt làm bài đang xem thì mọi câu trả lời đều phải bám vào dữ liệu đã đưa.

**Ngưỡng mở rộng ghi thành số** (ADR-003 §3.3): ≥150 câu có explanation, hoặc corpus ngữ pháp
riêng ≥200 mục. Giao diện giống nhau ở cả hai giai đoạn — chỉ nguồn ngữ cảnh đổi.

### 3.2 Ranh giới an toàn

- **Ngữ cảnh dựng từ ID ở phía máy chủ**, không bao giờ từ văn bản client gửi lên. Client gửi
  `question_id`; máy chủ tự tra. Nhận ngữ cảnh từ client là để người khác tự viết đề bài cho model.
- **Chữ học viên gõ chỉ đi vào lượt `user`**, không bao giờ nối vào `system`. `LLMRequest` tách
  hai trường chính là để luật này có chỗ được thi hành.
- **Tool không nhận `user_id` từ model** — lấy từ phiên đăng nhập. Đây là lỗi bảo mật, không
  phải lỗi prompt.
- **Đầu ra không render thành HTML.**

### 3.3 Chi phí — đây là bề mặt không có trần tự nhiên

A cache được nên chi phí hội tụ về 0. **C thì không**: mỗi câu hỏi là mới. Nên hạn mức
fail-closed từ lát A trở thành thứ gánh chính, cộng ba lớp:

- trần token mỗi tin nhắn
- trần chi tiêu mỗi học viên mỗi ngày (đã có, `ai_budget`)
- giới hạn tần suất trên endpoint chat (`rate_limit` theo `user.id`, đã có)

---

## 4. Chọn provider theo TÍNH NĂNG, từ admin UI

### 4.1 Bảng cấu hình

```
ai_feature_config(feature PK, provider, model, enabled, updated_at, updated_by)
```

`feature` khớp đúng `ai_interaction.feature`, nên câu hỏi *"đổi Coach sang model rẻ hơn tiết
kiệm bao nhiêu"* trả lời được bằng một truy vấn trên sổ cái đã có.

### 4.2 Ba luật của màn cấu hình

- **Khoá API không bao giờ nhập từ UI.** Một ô nhập khoá là một khoá sẽ lọt vào log, ảnh chụp
  màn hình và bản sao lưu. UI chọn provider/model; khoá ở `.env`.
- **Chỉ chọn được model có trong bảng giá.** `cost_usd` **ném lỗi** với model lạ chứ không ghi 0
  (nguyên tắc N4), nên một model gõ tay sẽ làm mọi lượt gọi hỏng. UI đưa danh sách đã biết.
- **Công tắc bật/tắt từng tính năng.** Hoá đơn tăng đột biến hoặc nhà cung cấp sập thì tắt Coach
  mà không ảnh hưởng gắn nhãn. Tắt nghĩa là endpoint trả lời "tạm thời không dùng được", **không
  phải giả vờ thành công**.

### 4.3 Đọc cấu hình

Gateway đọc bảng này mỗi lượt gọi. Một lượt đọc hàng có khoá chính không đáng kể so với một lượt
gọi LLM mất vài giây — và cache nó lại sẽ tạo ra cửa sổ mà UI đã đổi còn hệ thống thì chưa, thứ
người vận hành không có cách nào phát hiện.

---

## 5. Đo hiệu suất — bốn lớp, và lớp rẻ nhất đứng trước

### 5.1 Vận hành (đã có sẵn)

Bày `ai_interaction` theo `feature`: chi phí, độ trễ p50/p95, tỉ lệ hỏng, **tỉ lệ cache trúng**.
Cột `cache_hit` dựng từ lát A và tới giờ chưa ai ghi vào; Coach là thứ đầu tiên ghi. Tỉ lệ cache
trúng chính là con số nói chi phí có giảm theo thời gian hay không.

### 5.2 Phản hồi học viên

```
coach_feedback(explanation_id, user_id, helpful bool, created_at)
```

Hai nút dưới mỗi lời giải. Đây là thước đo **chất lượng** duy nhất đến từ người thật — không có
nó thì mọi con số chỉ nói được "rẻ và nhanh", không nói được "có dạy được ai không". Gộp theo
`prompt_version` để trả lời "bản prompt mới có tốt hơn không".

### 5.3 Khẳng định tất định — chạy mỗi lần, gần như miễn phí

1. có nêu **đúng chữ cái đáp án đúng**
2. có nhắc **phương án học viên đã chọn**
3. là tiếng Việt
4. mỗi trường trong khoảng độ dài cho phép
5. **không nêu một điểm ngữ pháp KHÁC với nhãn của câu** — kiểm được vì bộ nhãn là danh sách
   đóng: nếu văn bản nhắc tên một nhãn `GRAMMAR_*`, nó phải là nhãn của chính câu đó

Khẳng định thứ 5 chỉ tồn tại được **nhờ lát B**. Nó bắt đúng kiểu hỏng nguy hiểm nhất: một lời
giải trôi chảy, đúng ngữ pháp, và giảng về sai điểm ngữ pháp.

Phần lớn lỗi thật rơi vào lớp này. Một lời giải trôi chảy nhưng **nêu sai chữ cái đáp án** là lỗi
tệ nhất sản phẩm này mắc được, và nó bị bắt bằng một phép so sánh chuỗi.

### 5.4 Giám khảo LLM có rubric

Cho phần không kiểm được bằng mã. Hai ràng buộc bắt buộc:

- **Giám khảo phải khác model sinh** — model chấm bài của chính nó thì thiên vị bản thân, và
  điểm đẹp lên mà chất lượng không đổi. Cấu hình theo tính năng ở §4 làm việc này thành một dòng.
- **17 explanation người viết là điểm neo** — không để so từng chữ, mà để giám khảo biết "đạt"
  trông như thế nào.

**Cổng hồi quy:** đổi prompt mà tỉ lệ đạt tụt thì không merge.

---

## 6. Bảng cần thêm

```
coach_explanation(id, question_id, selected_option_id, prompt_version,
                  body jsonb, status, reviewed_at, reviewed_by, created_at)
                  UNIQUE (question_id, selected_option_id, prompt_version)
coach_feedback(explanation_id, user_id, helpful, created_at)  PK (explanation_id, user_id)
ai_feature_config(feature PK, provider, model, enabled, updated_at, updated_by)
```

`UNIQUE` ba cột **là** cache: tra trước khi gọi, ghi sau khi gọi. Không cần Redis cho đường này.

`PK (explanation_id, user_id)` khiến một học viên chỉ bỏ được một phiếu — không có nó thì một
người bấm mười lần làm lệch con số duy nhất đo chất lượng.

---

## 7. Lộ trình

| Lát | Nội dung | Xong nghĩa là |
|---|---|---|
| **C1** | `ai_feature_config` + màn cấu hình admin | đổi model của Coach mà không sửa mã, không restart |
| **C2** | A — giải thích câu sai, cache, cổng eval §5.3 | mọi lời giải qua năm khẳng định tất định |
| **C3** | B — gợi ý ôn tập theo nhãn | không lượt gọi model nào, không tham chiếu treo |
| **C4** | Phản hồi học viên + bảng thống kê theo `feature` | tỉ lệ cache trúng và tỉ lệ hữu ích nhìn thấy được |
| **C5** | C — hỏi đáp neo ngữ cảnh + ba lớp chặn chi phí §3.3 | trần token, trần ngày, giới hạn tần suất đều có test |
| **C6** | Giám khảo LLM + cổng hồi quy | đổi prompt mà tụt thì CI đỏ |
| **—** | Mở hỏi đáp ra ngoài ngữ cảnh | **chặn** tới khi qua ngưỡng ADR-003 §3.3 |

C1 trước C2 có chủ ý: không có cấu hình theo tính năng thì giám khảo ở C6 không thể là model
khác model sinh mà không sửa mã.

---

## 8. Điều đã biết là sẽ phải sửa

- **Ngưỡng độ dài từng trường** ở §5.3 chưa có; phải đọc vài chục bản thật mới đặt được
- **Trần token mỗi tin nhắn chat** chưa đặt — lát C5 tồn tại để đo
- **"Duyệt sau" ở §2.4** là đánh đổi của giai đoạn ít học viên. Khi lượng học viên vượt lượng nội
  dung, tính trước + duyệt trước rẻ hơn và an toàn hơn; ngày đó §2.3 và §2.4 cùng đổi
- **Khẳng định thứ 5 ở §5.3** giả định nhãn của câu là đúng. Nhãn do máy gắn và mới có ~0% được
  người kiểm, nên nó đang canh sự nhất quán chứ chưa canh sự đúng đắn
