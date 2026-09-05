# SPEC — Ngữ pháp TOEIC

Trạng thái: **G1–G5 đã dựng** trên `main` (2026-09-06). P1 (lý thuyết part) còn
mở. Bài học ngữ pháp theo chủ đề, mỗi bài có lý thuyết và/hoặc bài tập.

## 0. Chỗ nó đứng, nói thẳng

`PLAN.md` §3 khai **bốn** module cho MVP: Learning Hub (dictation + từ vựng),
TOEIC Practice, AI Study Planner, AI Coach. Ngữ pháp **không nằm trong bốn cái
đó** — chỗ duy nhất nó xuất hiện là "Explaining grammar", một năng lực của AI
Coach, tức là trả lời một câu hỏi cụ thể chứ không phải một giáo trình.

Nên đây là **module thứ năm**, và nó được làm vì có người quyết định thế, không
phải vì kế hoạch đã xếp sẵn. Ghi ra để lần sau đọc `PLAN.md` không ai tưởng nó
bị bỏ sót.

## 1. Chủ đề: theo mã nhãn, và cả những bài nền tảng ngoài taxonomy

`toeic_question_label_taxonomy.md` mang danh sách chủ đề ngữ pháp **đã gắn vào
câu hỏi thật**: `GRAMMAR_PREPOSITION` (29 câu), `GRAMMAR_TENSE` (18),
`GRAMMAR_PRONOUN` (17), `GRAMMAR_VOICE` (17), `GRAMMAR_ADJECTIVE` (12),
`GRAMMAR_ADVERB` (12), `GRAMMAR_NOUN` (12), `GRAMMAR_PARTICIPLE` (11),
`GRAMMAR_CONJUNCTION` (8), `GRAMMAR_RELATIVE_CLAUSE` (7), `GRAMMAR_COMPARISON`
(4), `GRAMMAR_TO_INFINITIVE` (4) — 151 câu, Part 5 (111) và Part 6 (40).

Chủ đề gắn mã **là** các mã trên, không phải danh sách thứ hai chép lại.
`grammar_topic.code` là khoá ngoại logic tới facet `grammar` trong `labels.py`.

**Đã sửa so với kế hoạch ban đầu:** `code` giờ **nullable** (migration 060).
Sáu chủ đề nền tảng — "Kiến thức cơ bản 1/2", "Động từ nguyên mẫu", "Danh động
từ", "Câu điều kiện", "Cấu trúc phân từ" — dạy từ loại và cấu trúc câu, không
tương ứng mã nhãn nào, và chúng phải đứng TRƯỚC các chủ đề taxonomy trong chuỗi
học. Không có mã thì không có kho nhãn để đo ngưỡng, nên cổng publish của chúng
là "≥1 bài đã publish" — đừng mở trang trống.

## 2. Bài tập: là bài học, không phải truy vấn theo nhãn

Kế hoạch ban đầu chia hai tầng: "luyện tập cuối CHỦ ĐỀ rút theo nhãn" (miễn phí)
và "bài tập của từng BÀI HỌC soạn tay". Tầng một đã được dựng thật (G3, endpoint
rút câu theo nhãn) rồi **bị bỏ**. Lý do chính là cái giá đã ghi ở §8 của bản
kế hoạch: nhãn thô hơn bài học — ba bài trong cùng chủ đề rút theo nhãn sẽ ra
cùng một bộ câu, và không gì báo hiệu điều đó.

Hình thái hiện tại: **luyện tập là bài học loại `practice`** (`kind`, migration
059), cùng tầng với bài lý thuyết, cùng cây chủ đề → bài. Câu của nó là hàng
`question` thật gắn qua `grammar_lesson_question` — chọn từ kho theo nhãn bằng
bộ picker trong admin, hoặc soạn mới tại chỗ. "Bài tập của bài nào" do người
soạn quyết, không do truy vấn suy ra.

Kho vẫn là nguồn: màn chọn câu lọc theo `code` của chủ đề, và nó tự lớn lên mỗi
đợt gắn nhãn. Ngưỡng **12 câu published** vẫn là cổng publish cho chủ đề CÓ mã.

## 3. Lý thuyết Part 1–7: TÁCH RA, và không đối xứng

Câu hỏi đặt ra là nên gộp vào đây hay tách. Quyết định: **tách**, và hai bên
không cùng hình dạng — đó mới là phần quan trọng.

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
`ROADMAP.md` §3. Lý thuyết part nên ship cùng lát đó (P1), không cùng ngữ pháp.

Cái **dùng chung** là bộ render lý thuyết ở §5 — một bộ, hai chỗ gọi.

## 4. Dữ liệu — năm bảng, như đang chạy

```
grammar_topic   (id, code?, slug, title, summary, position, status)
grammar_lesson  (id, topic_id, slug, title, kind, body, position, status)
grammar_lesson_question (lesson_id, question_id, position)   -- bảng nối
grammar_lesson_completion (user_id, lesson_id, created_at)   -- UNIQUE(user, lesson)
grammar_attempt (id, user_id, question_id, option_id?, is_correct, created_at)
```

Bốn điều đáng nói:

**`code` nullable**, như §1. Chủ đề có mã đo ngưỡng bằng truy vấn câu published
mang nhãn (`GRAMMAR_MIN_QUESTIONS = 12`); chủ đề không mã đo bằng "có bài publish".
Cả hai ngả đều ở `publish_grammar_topic`, không phải một cơ chế mới.

**Bài tập LÀ hàng `question`, không phải một loại nội dung mới.** Một câu ngữ
pháp đúng là hình dạng của một câu Part 5. Dùng lại `question` thì được không mất
gì: `validate_question`, hình dạng giải thích ` | `, `question_option`, màn soạn
đề của admin, và cả cổng publish. Dựng `grammar_exercise` riêng là chép lại từng
thứ một, rồi hai bên trôi khỏi nhau.

**`status` ở cả hai tầng, và cả hai được lọc độc lập** — đúng cái mà cây dictation
đã học được bằng cách hỏng: một bài `published` nằm dưới một chủ đề `draft` phải
404, và không phép kiểm nào ngoài một bài test nhìn thấy điều đó.

**Tiến độ LÀ bảng ghi, không suy ra — đây là quyết định ĐẢO so với kế hoạch
ban đầu.** Bản kế hoạch nói "một bài xong khi mọi câu đã trả lời đúng, tính từ
`grammar_attempt`". Lý do đảo: phần lớn bài ngữ pháp là **lý thuyết, không có
câu hỏi nào** — tiến độ suy ra không có gì mà suy. Nên người học bấm "Đã học
xong", và nút đó hợp lệ với mọi `kind`. `grammar_attempt` vẫn ghi mọi lượt làm
câu (kể cả lượt sai và làm lại) — lịch sử không bị xoá khi bấm/bỏ bấm hoàn
thành; bỏ đánh dấu xong không thu hồi được việc đã làm một câu.

## 5. Lý thuyết: markdown-lite, đã nới

Kế hoạch chọn "nới `markdown-lite`" thay vì lưu khối có cấu trúc, và đường đó
đã đi hết. Từ 81 dòng nó thành 242, thêm: tiêu đề `#`→`####` (cỡ tương đối theo
`em`, nên cùng một bài dựng đúng ở mọi chỗ nó được nhúng), bảng `|` với `<br>`,
blockquote `> `, phân cách `---`, in nghiêng, gạch ngang `~~`, `<u>` gạch chân,
`code`. Vẫn **không `dangerouslySetInnerHTML`** — mọi thứ là React node, chữ
không bao giờ thành HTML.

**Tuyệt đối không thêm `react-markdown`.** Lý do đã ghi ngay trong
`markdown-lite`: một cây parser đầy đủ cho vài quy tắc. Và có một lý do thứ hai
nặng hơn — mỗi dependency chạy trên trang là một lần nữa phải trả lời câu hỏi
XSS, mà `ADR-015` §6 vừa tiêu mất lý lẽ hoãn P1-7b của dự án này.

Nguồn bài viết nằm ở `apps/api/content/grammar/*.md` (noun-01, noun-02,
pronouns, basic-knowledge-01/02), load vào lesson qua admin API. Quy ước format
đã trả giá bằng hai lần sửa: **không dùng bảng để căn nhãn S/V/O dưới từ** —
markdown-lite không có colspan, nhãn phải merge thành `<u>**từ**</u> (S)` inline
ngay câu; danh sách chỉ `- `, không `1.`; `*` đứng một mình trong ngoặc đơn là
nghiêng, không phải bullet.

## 6. Giao diện người học

- `/learn/grammar` — cây chủ đề published, mỗi chủ đề liệt bài, Meter tiến độ
  tính theo hàng completion.
- Trang chủ đề → trang bài. Trang bài có sidebar danh sách bài (cuộn tới bài
  hiện tại, mobile thành dải ngang), nút hoàn thành, và thanh dưới chân ba trạng
  thái.
- **Chuỗi học tuyến tính:** `next_topic` được tính theo `position` của chủ đề
  (bỏ qua chủ đề chưa publish), hiện ở đáy sidebar và ở thanh chân khi làm hết
  bài cuối. Đây là cách duy nhất hai nhóm "nền tảng không mã" và "chủ đề theo
  nhãn" đan được vào nhau — thứ tự là dữ liệu, không phải suy luận.
- Admin: `/admin/grammar` cây chủ đề/bài + màn soạn bài theo trang riêng
  (`lesson-form.tsx`, hai cột soạn|xem trước), picker câu theo nhãn, soạn câu
  mới tại chỗ, và endpoint đổi thứ tự topic/lesson (PUT cả khối, kiểu
  `StoryReorder`).

## 7. XP và việc hôm nay — ĐÃ DỰNG (G5)

Ba đường, cả ba đi trên hệ có sẵn, không bảng mới:

- **Một câu đúng = XP.** Nguồn `grammar_attempt`, mức là cột
  `xp_grammar_attempt` trong `progression_setting` (mặc định 2, admin sửa được
  như mọi mức khác — migration 061). `source_id` là uuid tất định từ
  (người, câu), KHÔNG phải id lượt: đường nộp bài ghi mọi lượt, và khoá bằng id
  lượt biến "làm lại cho thuộc" thành máy in XP. Sai không được gì; đúng rồi
  làm lại không được lần hai.
- **Việc hôm nay.** Loại `grammar_attempt` đếm CÂU RIÊNG đã làm trong ngày
  (đúng sai đều tính — cùng nghĩa với `attempt_answer`). Khe mặc định "Làm câu
  ngữ pháp" 10 câu / 10 XP, id cố định như ba khe kia. Môi trường đã seed từ
  trước không tự có khe mới — seed chỉ chạy khi bảng trống — nên dev nhận nó
  bằng một hàng INSERT; production muốn thì POST qua admin.
- **Chuỗi ngày.** Một `grammar_attempt` là một ngày học: `gather_stats` và
  `ruby_daily.studied_today` cùng nạp thêm nguồn này, lưới lịch có cột
  `grammar`. Cố ý KHÔNG đếm hàng completion vào chuỗi — completion bị xoá khi
  bấm "Bỏ hoàn thành", và lịch sử của chuỗi không được phép co lại sau lưng
  người ta.

Bấm "Hoàn thành" bài **không cộng XP** — nó là tự báo, không phải làm được;
phần thưởng của nó là thanh tiến độ. Trần XP ngày vẫn chặn ở tầng ghi như cũ.

## 8. Lát cắt — trạng thái thật

| Lát | Nội dung | Trạng thái |
|---|---|---|
| **G1** | Schema + admin CRUD chủ đề/bài học | ✅ migrations 057–060 |
| **G2** | Trang học: cây chủ đề → bài → lý thuyết | ✅ |
| **G3** | Luyện tập cuối chủ đề rút theo nhãn | ❌ **đã dựng rồi bỏ** — xem §2 |
| **G4** | Bài `practice` + gắn câu + `grammar_attempt` + tiến độ | ✅ (tiến độ là bảng ghi, không suy ra — §4) |
| **G5** | XP + việc hôm nay + chuỗi ngày | ✅ migration 061 — xem §7 |
| **P1** | Lý thuyết Part 1–7, đi cùng `GET /practice/parts/{part}` | mở, xem §3 |

## 9. Ba chỗ sẽ hỏng im lặng

**Chủ đề dưới ngưỡng.** Một chủ đề bốn câu vẫn dựng ra trang, vẫn chấm, và người
học làm xong trong ba phút rồi tưởng mình đã học xong "So sánh". Cổng `status`
chặn ở tầng chủ đề, ngưỡng kiểm bằng truy vấn thật (`GRAMMAR_MIN_QUESTIONS`),
và chủ đề không mã thì cổng là "≥1 bài publish".

**Một câu hỏi nằm ở hai chỗ.** Câu đã gắn vào bài học vẫn nằm trong đề thi. Người
học làm đề rồi vào bài học sẽ gặp lại đúng câu ấy. Đó **không phải lỗi** — gặp
lại là cách ôn — nhưng nó phải là một quyết định được ghi ra, vì lần đầu ai đó
thấy sẽ tưởng là trùng dữ liệu.

**Tiến độ lưu tay lệch với làm bài.** Vì hoàn thành là một cái bấm, một bài
`practice` có thể bị đánh dấu xong mà không làm câu nào, và ngược lại làm đúng
mọi câu mà chưa bấm. Đó là cái giá đổi lấy việc lý thuyết có tiến độ — chấp
nhận có ý thức. `grammar_attempt` vẫn là sự thật về lượt làm; đừng bao giờ suy
lại tiến độ từ cả hai nguồn cùng lúc.
