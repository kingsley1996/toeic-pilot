# SPEC — Ngữ pháp TOEIC

Trạng thái: **kế hoạch, chưa dựng.** Khảo sát ngày **2026-09-05** trên `main`.

Bài học ngữ pháp theo chủ đề, mỗi bài có lý thuyết và bài tập. Tài liệu này chốt
hình dạng trước khi viết dòng mã nào.

---

## 0. Chỗ nó đứng, nói thẳng

`PLAN.md` §3 khai **bốn** module cho MVP: Learning Hub (dictation + từ vựng),
TOEIC Practice, AI Study Planner, AI Coach. Ngữ pháp **không nằm trong bốn cái
đó** — chỗ duy nhất nó xuất hiện là "Explaining grammar", một năng lực của AI
Coach, tức là trả lời một câu hỏi cụ thể chứ không phải một giáo trình.

Nên đây là **module thứ năm**, và nó được làm vì có người quyết định thế, không
phải vì kế hoạch đã xếp sẵn. Ghi ra để lần sau đọc `PLAN.md` không ai tưởng nó
bị bỏ sót.

## 1. Danh sách chủ đề đã có sẵn, đừng nghĩ lại

`toeic_question_label_taxonomy.md` đã mang đúng danh sách ấy, và nó **đã được gắn
vào câu hỏi thật**:

| Mã | Chủ đề | Số câu đã gắn |
|---|---|---|
| `GRAMMAR_PREPOSITION` | Giới từ | 29 |
| `GRAMMAR_TENSE` | Thì | 18 |
| `GRAMMAR_PRONOUN` | Đại từ | 17 |
| `GRAMMAR_VOICE` | Thể | 17 |
| `GRAMMAR_ADJECTIVE` | Tính từ | 12 |
| `GRAMMAR_ADVERB` | Trạng từ | 12 |
| `GRAMMAR_NOUN` | Danh từ | 12 |
| `GRAMMAR_PARTICIPLE` | Phân từ | 11 |
| `GRAMMAR_CONJUNCTION` | Liên từ | 8 |
| `GRAMMAR_RELATIVE_CLAUSE` | Mệnh đề quan hệ | 7 |
| `GRAMMAR_COMPARISON` | So sánh | 4 |
| `GRAMMAR_TO_INFINITIVE` | To-infinitive | 4 |

**151 câu, 12 mã, nằm ở Part 5 (111) và Part 6 (40).** 838/855 câu của kho đã có
nhãn, và sau đợt backfill ngày 2026-09-04 thì gần như tất cả đã có giải thích.

Chủ đề của module này **là** các mã trên, không phải một danh sách thứ hai chép
lại. Hai danh sách cho cùng một thứ là hai chỗ phải sửa cùng lúc khi taxonomy
đổi, và chỗ thứ hai sẽ không ai nhớ. `labels.py` vốn được **sinh ra** từ tệp
taxonomy; module này đọc cùng nguồn đó.

Lưu ý một chỗ không đối xứng, và nó có lý: `GRAMMAR_NOUN` hợp lệ ở Part 5 nhưng
không ở Part 6 — Part 6 kiểm năm điểm ngữ pháp, Part 5 kiểm mười một. Rút bài tập
theo nhãn vì thế **tự lấy đúng part**, không cần lọc thêm.

## 2. Bài tập RÚT ra, không soạn mới — nhưng chỉ tới một mức

Đây là quyết định tiết kiệm nhất của cả kế hoạch: một bài học về giới từ có ngay
29 câu TOEIC thật, đã có giải thích, chỉ bằng một truy vấn theo nhãn. Và kho ấy
**tự lớn lên** mỗi khi có đề mới được gắn nhãn — không phải làm gì thêm.

Nhưng phải nói thẳng cái giá: **kho đang mỏng**. Bốn câu cho So sánh và bốn cho
To-infinitive là một buổi học là hết. Nên:

- **Ngưỡng đề nghị: 12 câu** cho một chủ đề mới được mở ra cho người học. Dưới
  ngưỡng thì chủ đề vẫn tồn tại nhưng ở trạng thái `draft` — cùng cổng publish mà
  mọi nội dung khác đang dùng, không phải một cơ chế mới.
- Hôm nay **7/12 chủ đề** qua ngưỡng đó.

**Nhãn thô hơn bài học, và đó là chỗ dễ vấp.** Chủ đề "Thì" có 18 câu, nhưng bên
trong nó sẽ có nhiều bài — hiện tại hoàn thành, quá khứ đơn, tương lai. Cả ba bài
mà rút cùng 18 câu ấy thì người học gặp lại y một bộ ở mỗi bài, và "bài tập của
bài học này" thành một lời hứa sai.

Nên chia hai tầng, và nói rõ tầng nào lấy từ đâu:

| | Nguồn | Chi phí |
|---|---|---|
| **Luyện tập cuối CHỦ ĐỀ** | Rút theo nhãn | Miễn phí, có ngay |
| **Bài tập của từng BÀI HỌC** | Soạn tay, gắn vào bài | Tốn người |

Tầng một có ngay ở lát đầu. Tầng hai lớn dần, và màn soạn đề xuất sẵn danh sách
"câu mang nhãn này chưa gắn vào bài nào" để việc gắn rẻ nhất có thể.

## 3. Lý thuyết Part 1–7: TÁCH RA, và không đối xứng

Câu hỏi đặt ra là nên gộp vào đây hay tách. Đề nghị: **tách**, và hai bên không
cùng hình dạng — đó mới là phần quan trọng.

Chúng khác nhau ở bốn chỗ, và không chỗ nào là chuyện thẩm mỹ:

- **Khác trục.** Ngữ pháp cắt theo **điểm ngôn ngữ**; lý thuyết part cắt theo
  **phần của bài thi**. Người hỏi "làm Part 7 thế nào" không đang hỏi một câu
  ngữ pháp.
- **Khác thời điểm.** Lý thuyết part được cần **ngay trước hoặc ngay sau khi
  luyện part đó** — tức là ở khu luyện thi, chỗ người học đang đứng. Ngữ pháp là
  giáo trình để đi qua dần.
- **Khác vòng đời.** Ngữ pháp ổn định hàng chục năm. Chiến thuật part đổi khi ETS
  đổi định dạng, và điều đó đã xảy ra thật năm 2016.
- **Khác nguồn bài tập.** Bài tập ngữ pháp = câu mang nhãn ấy. Bài tập part =
  câu thuộc part ấy — mà **thứ đó đã có sẵn** ở khu luyện thi.

Chỗ cuối là chỗ quyết định: **lý thuyết part không cần bộ máy bài học.** Nó cần
một trang chiến thuật gắn cạnh phần luyện của chính part đó. Bọc một trang văn
xuôi vào một cái cây chỉ có một tầng là dựng bộ máy cho thứ không cần bộ máy.

Và nó có sẵn chỗ để đi cùng: `GET /practice/parts/{part}` **đang là mục mở** ở
`ROADMAP.md` §3 ("luyện theo part rời"). Lý thuyết part nên ship cùng lát đó, chứ
không cùng ngữ pháp.

Cái **dùng chung** là bộ render lý thuyết ở §5 — một bộ, hai chỗ gọi.

## 4. Dữ liệu

**Hai tầng, không phải bốn.** Dictation cần bốn (chủ đề → mục → bài → câu) vì một
bài là một đơn vị audio. Ngữ pháp không có ràng buộc đó:

```
grammar_topic   (id, code, slug, title, summary, position, status)
grammar_lesson  (id, topic_id, slug, title, position, status, body)
grammar_lesson_question (lesson_id, question_id, position)   -- bảng nối
grammar_attempt (id, user_id, question_id, option_id, is_correct, created_at)
```

Bốn điều đáng nói:

**`grammar_topic.code` trỏ vào mã nhãn** (`GRAMMAR_TENSE`), và đó là dây nối duy
nhất tới kho câu hỏi. Nó là khoá ngoại logic tới taxonomy — mã phải tồn tại,
kiểm bằng cùng hàm mà `enrich_skills` đang dùng, không phải bằng một danh sách
chép tay.

**Bài tập LÀ hàng `question`, không phải một loại nội dung mới.** Một câu ngữ
pháp đúng là hình dạng của một câu Part 5. Dùng lại `question` thì được không mất
gì: `validate_question`, hình dạng giải thích ` | `, `question_option`, màn soạn
đề của admin, và cả cổng publish. Dựng `grammar_exercise` riêng là chép lại từng
thứ một, rồi hai bên trôi khỏi nhau.

**`status` ở cả hai tầng, và cả hai được lọc độc lập** — đúng cái mà cây dictation
đã học được bằng cách hỏng: một bài `published` nằm dưới một chủ đề `draft` phải
404, và không phép kiểm nào ngoài một bài test nhìn thấy điều đó.

**Tiến độ SUY RA, không lưu.** Cùng luật với `StoryProgress`: một bài học "xong"
khi mọi câu của nó đã được trả lời đúng ít nhất một lần, tính từ `grammar_attempt`.
Bảng tiến độ ghi song song sẽ lệch khỏi lịch sử ngay lần đầu có ai xoá một lượt
làm, và không gì phát hiện.

## 5. Lý thuyết: lưu thế nào, hiện thế nào

Đây là chỗ chưa có sẵn và phải quyết.

`components/markdown-lite.tsx` đã tồn tại — 81 dòng, hiểu **đậm**, `code`, gạch
đầu dòng, xuống dòng. Nó **cố ý không dùng `dangerouslySetInnerHTML`**: mọi thứ
là React node với text thẳng, nên chữ không bao giờ thành HTML.

Nhưng nó viết cho bong bóng chat. Bài ngữ pháp cần thêm **tiêu đề** và **bảng**
(bảng chia thì là ví dụ hiển nhiên nhất). Hai đường:

- **Nới `markdown-lite`** thêm `##` và bảng `|`. Giữ nguyên tính chất không-HTML,
  thêm chừng 40 dòng. Cùng bộ render cho cả chat lẫn bài học.
- **Lưu theo khối có cấu trúc** (JSON: đoạn văn / bảng / ví dụ / lưu ý). Hình
  dạng kiểm được bằng Pydantic, không bao giờ có cú pháp hỏng, nhưng soạn nặng
  tay hơn và cần màn soạn riêng.

Đề nghị **đường thứ nhất**, vì cái thứ hai trả tiền trước cho một sự chặt chẽ mà
nội dung ngữ pháp chưa đòi. Đổi lại phải chấp nhận: cú pháp markdown viết sai thì
hiện ra sai chứ không nổ — nên màn soạn cần ô xem trước.

**Tuyệt đối không thêm `react-markdown`.** Lý do đã ghi ngay trong
`markdown-lite`: một cây parser đầy đủ cho bốn quy tắc. Và có một lý do thứ hai
nặng hơn — mỗi dependency chạy trên trang là một lần nữa phải trả lời câu hỏi
XSS, mà `ADR-015` §6 vừa tiêu mất lý lẽ hoãn P1-7b của dự án này.

## 6. Nối vào XP và việc hôm nay

`xp_event.source_type` là chuỗi tự do — đang dùng `attempt_submit`, `daily_task`,
`dictation_complete`, `vocabulary_review`. Thêm `grammar_exercise` không cần đổi
schema.

`daily_task_slot.kind` thì **là tập đóng**, cố ý: mỗi `kind` là một truy vấn thật
trong mã. Muốn có việc hôm nay kiểu "làm 10 câu ngữ pháp" thì phải thêm một
`kind` mới — một thay đổi mã, không phải một hàng dữ liệu. Đó là lựa chọn đã
được ghi ở `frontend.md`, không phải chỗ bỏ sót.

Trần XP ngày vẫn chặn ở tầng ghi như cũ; không có gì riêng cho module này.

## 7. Lát cắt

Mỗi lát tự ship được, và lát sau không phải sửa lát trước.

| Lát | Nội dung | Xong nghĩa là |
|---|---|---|
| **G1** | Schema + admin CRUD chủ đề/bài học | Soạn được một bài, chưa ai học được |
| **G2** | Trang học: cây chủ đề → bài → lý thuyết | Đọc được, chưa có bài tập |
| **G3** | Luyện tập cuối chủ đề, **rút theo nhãn** | 7 chủ đề có bài tập ngay, không soạn gì |
| **G4** | Gắn câu vào từng bài + `grammar_attempt` + tiến độ | Bài tập theo bài học, tiến độ suy ra |
| **G5** | XP + việc hôm nay | Ngữ pháp tính vào chuỗi ngày |
| **P1** | Lý thuyết Part 1–7, **đi cùng** `GET /practice/parts/{part}` | Tách hẳn, xem §3 |

**G3 trước G4 là cố ý.** Nó cho người học thứ dùng được ngay bằng dữ liệu đã có,
và nó chứng minh dây nối nhãn ↔ câu hỏi chạy thật trước khi ai bỏ công soạn tay.

## 8. Ba chỗ sẽ hỏng im lặng

**Nhãn thô hơn bài học.** Nếu G4 lỡ rút theo nhãn thay vì theo bảng nối, ba bài
trong cùng một chủ đề sẽ ra cùng một bộ câu, và nó trông hoàn toàn bình thường —
mỗi bài đều có bài tập, đều chấm được, đều cộng XP. Chỉ người làm hết ba bài mới
phát hiện.

**Chủ đề dưới ngưỡng.** Một chủ đề bốn câu vẫn dựng ra trang, vẫn chấm, và người
học làm xong trong ba phút rồi tưởng mình đã học xong "So sánh". Cổng `status`
phải chặn ở tầng chủ đề, và ngưỡng phải kiểm bằng truy vấn thật chứ không bằng
một con số ai đó nhớ.

**Một câu hỏi nằm ở hai chỗ.** Câu đã gắn vào bài học vẫn nằm trong đề thi. Người
học làm đề rồi vào bài học sẽ gặp lại đúng câu ấy. Đó **không phải lỗi** — gặp
lại là cách ôn — nhưng nó phải là một quyết định được ghi ra, vì lần đầu ai đó
thấy sẽ tưởng là trùng dữ liệu.
