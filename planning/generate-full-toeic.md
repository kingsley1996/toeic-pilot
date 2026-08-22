# Sinh trọn một đề TOEIC 200 câu — kể cả audio và ảnh

**Trạng thái:** 📋 KẾ HOẠCH, chưa code · lập 2026-08-22
**Phạm vi:** từ một dòng lệnh tới một đề đầy đủ nằm trong database ở trạng thái `draft`, đủ để một người duyệt rồi bấm publish.

> Tài liệu này là **kế hoạch**, không phải bản ghi hiện trạng. Khi code xong, trạng thái đi về [`ROADMAP.md`](ROADMAP.md); phần lý do ở lại đây.

---

## 0. Vì sao cần, và vì sao bây giờ

Nội dung là nút thắt lớn nhất của dự án và đã là như thế suốt nhiều sprint: **55 câu hỏi trên 2 đề**, 34 câu có giải thích. Công cụ soạn đã xong từ lâu ([ADR-005](ADR-005-CONTENT-TOOLING.md), [ADR-007](ADR-007-TEST-AUTHORING.md)) — dán, kiểm, commit, gắn media, publish. Cái thiếu không phải công cụ mà là **người ngồi viết 200 câu**.

Ba mảnh vừa xuất hiện làm việc này khả thi mà trước đây thì không:

- **Đường dán đã chặt chẽ.** `parse_listening_part` / `parse_reading_part` cộng `validate_question` bắt được câu thiếu đáp án, sai số lựa chọn, sai part, in nhầm đề bài của Part 1–2. Nghĩa là có một **cổng kiểm không cần người** đứng giữa "một mớ chữ" và database.
- **Audio nhiều giọng đã chạy.** `audio_join.py` ghép hội thoại nhiều lượt thành một clip ([MEDIA-PIPELINE](MEDIA-PIPELINE.md) §10.2), nên Part 3 và Part 4 — 69 câu, phần lớn nhất của bài nghe — không còn là vật cản.
- **Sinh ảnh tại máy đã đo được.** Bộ `agent-sprite-forge` chạy `flux2-klein-4b-4bit` qua mflux: **~2,5 phút một tấm, đỉnh 12,37 GB RAM** trên máy M2 16 GB. Đủ cho ảnh Part 1 và biểu đồ Part 3/4 mà không cần đi xin phép ai.

---

## 1. Một đề đầy đủ gồm những gì

Con số của bài thi thật, không làm tròn:

| Part | Số câu | Cụm | Đáp án | In đề bài | Audio | Ảnh |
|---|---|---|---|---|---|---|
| 1 — Photographs | 6 | không | 4 | **không** | 1 clip / câu | **1 ảnh / câu** |
| 2 — Question–Response | 25 | không | **3** | **không** | 1 clip / câu | không |
| 3 — Conversations | 39 | 13 hội thoại | 4 | có | 1 clip / cụm | ~3 cụm cuối có biểu đồ |
| 4 — Talks | 30 | 10 bài nói | 4 | có | 1 clip / cụm | ~2 cụm có biểu đồ |
| 5 — Incomplete Sentences | 30 | không | 4 | có | không | không |
| 6 — Text Completion | 16 | 4 đoạn | 4 | có | không | không |
| 7 — Reading Comprehension | 54 | ~15 (đơn/đôi/ba) | 4 | có | không | đôi khi biểu mẫu |
| **Tổng** | **200** | **~42 cụm** | | | **54 clip** | **~11 ảnh** |

Hai chỗ mà mọi bản sinh tự động hay làm sai vì chúng ngược trực giác, và cả hai đã có ràng buộc trong code:

- **Part 1 và Part 2 không in gì cả.** `prompt_text` và `question_option.content` là `None`, **không phải chuỗi rỗng** — `validate_question` hỏi `is not None`, nên `""` bị từ chối. Part 2 có **ba** đáp án, không phải bốn.
- **Audio treo ở hai tầng.** Part 1–2 gắn trên `question`, Part 3–4 gắn trên `question_set` — vì ba câu của một hội thoại dùng chung một clip.

---

## 2. Bốn ràng buộc không được phá

Chúng đã có trong hệ thống. Pipeline này phải đi *qua* chúng, không đi vòng.

**2.1 `question.source` là NOT NULL và không có mặc định.** `original` = viết mới theo cấu trúc đề (cấu trúc không được bảo hộ bản quyền, văn bản cụ thể thì có); `licensed` = đã thật sự xin phép. Mọi câu do pipeline này sinh ra là **`original`**, và prompt **không bao giờ** được chứa nguyên văn đề ETS để "viết cho giống". Bảo mô hình "viết lại đề ETS 2019" là đường ngắn nhất tới việc nó nhả lại đúng văn bản nó đã học thuộc, và lúc đó cái nhãn `original` là một lời khai sai.

**2.2 API không được import `app.content`.** Ảnh production build `--no-dev`, không có extra `content`. Pipeline này chạy **ngoài luồng**, trong image worker (`docker/worker.Dockerfile`, có sẵn ffmpeg và extra `content`). `tests/test_content_isolation.py` canh việc đó trong một tiến trình con.

**2.3 Bản thu ứng với KỊCH BẢN, và cổng publish so bằng vân tay.** `question.audio_script_hash` / `question_set.audio_script_hash` ghi `script_fingerprint(...)` lúc gắn audio; `_may_be_stale` tính lại và so. Sửa một chữ trong kịch bản sau khi đã có clip là clip cũ thành "cũ", và publish bị chặn. Pipeline phải **sinh chữ trước, sinh tiếng sau**, không bao giờ ngược lại.

**2.4 Đường vào database là đường dán đã có.** `POST /admin/tests/{slug}/parts/{part}/parse` rồi `POST /admin/tests/{slug}/parts`. Không viết `INSERT` riêng cho pipeline: một đường vào thứ hai nghĩa là mọi luật trong `validators.py` và `_check_question` phải được nhớ lại lần nữa ở chỗ mới, và chỗ nào quên thì hỏng im lặng.

---

## 3. Kiến trúc: bảy chặng, mỗi chặng một hiện vật trên đĩa

```
  blueprint.json ──► outline.md ──► paste/*.txt ──► kiểm ──┬──► audio/*.mp3
   (chặng 1)         (chặng 2)      (chặng 3)     (chặng 4)│    (chặng 5)
                                                            └──► images/*.png
                                                                 (chặng 6)
                                                    ▼
                                          nạp qua đường dán (chặng 7)
                                                    ▼
                                            người duyệt → publish
```

**Mỗi chặng ghi ra tệp, không giữ trạng thái trong bộ nhớ.** Đó không phải sở thích: một lượt sinh 200 câu tốn hàng chục phút và sẽ đứt — hết quota, mất mạng, máy ngủ. Có hiện vật thì chạy lại chặng sau mà không phải trả tiền lại cho chặng trước, và người ta đọc được cái mô hình vừa viết trước khi nó biến thành 54 clip audio.

Thư mục làm việc: `apps/api/content/generated/<slug>/`, gitignore giống `media/`, trừ `blueprint.json` và `paste/` — hai thứ đó nhẹ và là **bản ghi nội dung đã sinh**, đáng commit.

---

## 4. Chặng 1 — Blueprint: quyết định trước khi sinh

Một tệp JSON tả *cái đề sẽ là gì*, do người viết hoặc do một lệnh sinh ra rồi người sửa. Nó khoá bốn thứ **trước khi** mô hình được gọi:

```jsonc
{
  "slug": "tp-form-03",
  "title": "TOEIC Pilot — Đề luyện 03",
  "seed": 20260822,              // để chạy lại ra cùng chủ đề, không cùng câu chữ
  "parts": {
    "3": {
      "groups": [
        { "id": "p3-01", "topic": "OFFICE_LOGISTICS", "speakers": 2,
          "accents": ["us_female_1", "uk_male_1"], "graphic": false,
          "labels": { "question_type": ["DETAIL", "INFERENCE", "PURPOSE"] } },
        { "id": "p3-11", "topic": "SCHEDULING", "speakers": 3,
          "accents": ["au_female_1", "ca_male_1", "us_male_1"], "graphic": "schedule" }
      ]
    }
  }
}
```

Vì sao blueprint đứng riêng thay vì để mô hình tự quyết:

- **Mô hình viết câu hỏi giỏi hơn nhiều so với thiết kế đề.** Bảo nó "sinh Part 3" thì 13 hội thoại sẽ trôi về cùng một chủ đề văn phòng và cùng một dạng câu hỏi, vì đó là vùng xác suất cao nhất. Phân bố chủ đề và dạng câu là quyết định của người ra đề.
- **Nhãn được quyết định trước, không gắn sau.** Taxonomy có **72 mã trên 6 facet** ([`toeic_question_label_taxonomy.md`](toeic_question_label_taxonomy.md)), và `enrich_skills.py` hiện gắn nhãn *sau khi* câu đã tồn tại. Với đề tự sinh thì ngược lại rẻ hơn và đúng hơn: yêu cầu mô hình viết một câu *thuộc* nhãn đã chọn, rồi dùng `enrich_skills` như **bước đối chiếu** — nó đọc câu và đoán nhãn; đoán khác blueprint là dấu hiệu câu viết chưa đúng dạng, không phải nhãn sai.
- **Giọng đọc và số người nói cố định trước.** `audio_join` cần biết ai nói lượt nào; và một clip mà các lượt trộn accent **phải khai `accent`**, vì cột chỉ giữ đúng một giá trị.
- **`seed` để chạy lại ra cùng bố cục.** Cùng câu chữ thì không — mô hình không tất định, và giả vờ nó tất định là tự lừa mình.

---

## 5. Chặng 2 — Sinh văn bản: MỘT CỤM một lần gọi

Mô hình xuất thẳng ra **định dạng dán** mà `content_import.py` đã đọc được:

```
[SCRIPT]
us_female_1: Have you seen the shipment schedule for next week?
uk_male_1: Not yet — was it posted on the shared drive?

[QUESTION]
What are the speakers discussing?
(A) A delivery timetable
(B) A staff meeting
(C) A budget report
(D) A software update
Answer: A
Explanation: Người nói nhắc "shipment schedule for next week"…
Source: original
```

Định dạng đó là **hợp đồng**, không phải tiện tay: nó đi thẳng vào `parse_listening_part`, và mọi luật của `_check_listening_question` (số đáp án theo part, có đúng một đáp án đúng, Part 1–2 không in gì) áp lên bản sinh y như áp lên bản người dán.

**Một cụm một lần gọi, không phải một part một lần gọi.** Cùng lý do `enrich_skills` gọi một facet một lần: gộp thì rẻ hơn về số lượt nhưng khi mô hình trượt một chỗ thì cả part sai, phải chạy lại toàn bộ thay vì chạy lại đúng cụm hỏng, và menu ngữ cảnh rộng ra làm mô hình lệch khỏi dạng câu đã chọn.

**Commit từng cụm xuống đĩa ngay**, không gom cuối lượt. Một lượt 42 cụm là hàng chục phút; gom lại nghĩa là một lần Ctrl-C vứt sạch.

**Hai loại 429 phải phân biệt.** `LLMQuotaExhausted` khác lỗi quá tải tạm thời: hạn mức ngày không tự hết sau ba mươi giây, nên backoff sẽ cày hết mọi cụm còn lại, hỏng y hệt nhau, và chôn mất dòng nói đúng nguyên nhân. Tầng LLM đã có sẵn phân biệt này — pipeline phải tôn trọng nó và **dừng hẳn** khi hết quota. Với hạn mức miễn phí 50 lượt/ngày của OpenRouter, một đề 42 cụm **không sinh xong trong một ngày**; đó là lý do Ollama chạy tại máy tồn tại.

---

## 6. Chặng 3 — Kiểm tự động, đứng TRƯỚC mọi thứ tốn kém

Cổng này chạy trên tệp dán, trước khi có một giây audio hay một tấm ảnh nào. Ba tầng:

**6.1 Tầng cú pháp — dùng lại parser thật.** Gọi thẳng `parse_listening_part` / `parse_reading_part` trong tiến trình, không viết bản kiểm riêng. Bản kiểm riêng sẽ trôi khỏi parser, và ngày nó trôi thì pipeline báo "hợp lệ" cho thứ mà `POST /parts/parse` sẽ từ chối.

**6.2 Tầng ngữ nghĩa — những thứ parser không thể biết:**

- **Đáp án phải đúng.** Hỏi lại bằng một lượt gọi *khác*: đưa câu hỏi và bốn lựa chọn đã **xáo thứ tự**, không đưa đáp án, bắt mô hình chọn. Chọn khác đáp án đã ghi ⇒ gắn cờ cho người xem. Xáo thứ tự là phần quan trọng: không xáo thì mô hình có xu hướng chọn lại vị trí cũ và phép kiểm thành nghi thức.
- **Nhiễu phải sai một cách hợp lý** — không có hai lựa chọn đồng nghĩa (đúng cái bẫy `buildOptions` đã gặp ở quiz từ vựng: hai từ khác nhau cùng nghĩa tiếng Việt), không có lựa chọn dài bất thường (độ dài là một manh mối rò rỉ đáp án).
- **Không trùng lặp trong đề.** So chuẩn hoá `prompt_text` giữa 200 câu; mô hình lặp lại chính nó nhiều hơn người tưởng.
- **Phân bố nhãn** khớp blueprint, qua `enrich_skills --dry-run` như mô tả ở §4.

**6.3 Tầng đối chiếu bản quyền.** Không có cách kiểm tuyệt đối. Cái làm được: chặn ở đầu vào (§2.1) và kiểm ngẫu nhiên một mẫu bằng tìm kiếm nguyên văn. Ghi rõ trong tài liệu rằng đây là **giảm thiểu, không phải bảo đảm**.

---

## 7. Chặng 4 — Audio

Sinh tệp spec cho `app.content.generate` đúng hai hình dạng nó đã biết:

- **Part 1, Part 2** — một câu một clip. Part 2 là `turns`: lời hỏi một giọng, ba câu đáp một giọng khác, ghép liền.
- **Part 3, Part 4** — `turns` cho cả hội thoại/bài nói, `gap_ms` giữa các lượt.

Ba thứ đã đo được và sẽ cắn nếu quên ([MEDIA-PIPELINE](MEDIA-PIPELINE.md) §10.2):

- `gap_ms` là khoảng lặng **cộng thêm** vào ~1,1 giây mà edge-tts đã tự chèn ở mỗi ranh giới lượt. Đặt 800 không cho ra 0,8 giây.
- Clip trộn accent **phải khai `accent`**, vì cột chỉ giữ một giá trị.
- `source_hash` của clip nhiều lượt băm **cả danh sách lượt theo thứ tự** cộng `gap_ms`. Bỏ thứ tự ra khỏi vân tay là lần chạy lại "bỏ qua, đã có" trong khi nội dung đã đổi.

Giọng đọc lấy từ blueprint, và **tên logic** (`us_female_1`) chứ không phải id nhà cung cấp — chính lớp gián tiếp đó đã cứu thư viện khi Microsoft đổi tên `en-AU-WilliamNeural`.

Trước một lượt lớn: chạy `TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external` để đối chiếu toàn bộ `LOGICAL_VOICES` với danh mục sống. Một id đã bị gỡ sẽ hỏng **một clip một lần** giữa lượt dài, và đó là kiểu hỏng tốn thời gian nhất.

---

## 8. Chặng 5 — Ảnh: sinh, không đi xin

[ADR-004](ADR-004-IMAGES.md) chọn *lấy ảnh có giấy phép mở từ kho công cộng*, và lý do vẫn đúng nguyên văn cho ảnh đi mượn: giấy phép và ghi công là bắt buộc. **Đề tự sinh đảo ngược bài toán**, và đây là điểm mới của kế hoạch này:

- Với ảnh mượn, ta phải **tìm được** một tấm mà bốn câu mô tả viết được về nó — nên §4 của ADR-004 nói đúng rằng cần người quyết định.
- Với ảnh sinh, ta **viết bốn câu trước, rồi vẽ tấm ảnh khớp với chúng**. Chiều phụ thuộc đảo lại, và cái khó biến mất.

Đường đi đã có sẵn và đã chạy thật ở phần khung/huy hiệu:

```
image_gen (flux2 tại máy)  →  normalise_bg.py  →  chroma-key  →  PNG
```

Ba điều đã trả giá để biết, ghi lại kẻo lặp:

- **`normalise_bg.py` lan từ MÉP ảnh vào**, không lọc theo màu. Bản lọc-theo-màu ăn thủng linh vật: thân nâu chỉ cách nền hồng 90,7 trong khi ngưỡng là 90.
- **Prompt phải cấm nét hồng/magenta trong chính hình vẽ**, vì bước tách nền xoá theo màu và không phân biệt được nền với một nét vẽ cùng màu.
- **Model không nghe lời tuyệt đối.** Lượt sinh sheet đầu tiên có cây bút chì ở hai trong bốn ô dù prompt không yêu cầu. Với ảnh Part 1 thì tương đương là "vẽ thừa một người" — mà bốn câu mô tả đã viết theo giả định chỉ có hai. **Ảnh phải được người xem trước khi gắn**, không có đường tắt.

**Giấy phép của ảnh sinh vẫn phải điền**, vì `image_asset.license`/`attribution`/`source_url` là NOT NULL. Điền đúng sự thật: `license: "generated"`, `attribution: "TOEIC Pilot — ảnh do mô hình sinh"`, `source_url` trỏ tới tệp prompt đã lưu. Để trống không được, và bịa một giấy phép CC thì tệ hơn nhiều.

**Rủi ro thật cần nói thẳng:** `flux2-klein-4b-4bit` vẽ minh hoạ phẳng rất tốt — đó là thứ đã dựng khung và linh vật. Ảnh Part 1 của đề thật là **ảnh chụp người trong bối cảnh công sở**, và mức ảnh thực của một model 4B ở 4-bit là chỗ chưa đo. Chặng này phải bắt đầu bằng **một lượt thử 6 tấm rồi nhìn**, trước khi cam kết cả pipeline. Nếu không đạt: hoặc đổi sang model mạnh hơn qua API (`_imagegen` đã có nhánh Gemini), hoặc quay lại đường mượn ảnh của ADR-004 cho riêng Part 1.

---

## 9. Chặng 6 — Nạp vào database

Đi qua đúng đường mà người dán đi: `POST /parts/{part}/parse` → xem preview → `POST /parts`. Pipeline gọi HTTP với token của một tài khoản `editor` chuyên dụng, **không gọi thẳng vào service**.

Vì sao đắt hơn mà vẫn chọn: đường HTTP là đường **đã có test** và đã có mọi luật ở `validators.py`. Gọi thẳng service thì bỏ qua tầng schema, và chỗ đầu tiên nó lộ ra sẽ là một câu Part 2 có bốn đáp án nằm im trong database.

Sau khi commit chữ:

1. Gắn ảnh: `POST /questions/{id}/image` (Part 1), `POST /question-sets/{id}/passage-image` (biểu đồ Part 3/4 — **slot 1**, và alt text **bắt buộc** ở đây trong khi Part 1 thì **cố ý không có**: ảnh Part 1 *là* câu hỏi, mô tả nó là đưa luôn đáp án).
2. Gắn audio: đường bulk `import_media` đã có, khớp theo số trong tên tệp. Nó **từ chối làm nửa việc** — thừa tệp hoặc thiếu khe thì dừng, vì một lần nhập nửa vời để lại vài câu thiếu bản thu và chỗ hổng chỉ lộ ra khi có người học chạm đúng câu đó.
3. Audio sinh ra phải ghi `source="uploaded"`, không phải `tts`: đó là thứ đặt nó vào `AudioState.EXTERNAL` và chặn worker TTS ghi đè ở lượt quét sau.

**Bảng quy đổi điểm**: một đề 200 câu cần `score_scale` riêng. Bảng đang seed là **xấp xỉ và tự nói ra điều đó** trong `source_note`; `scoring.py` **từ chối nội suy** khi thiếu hàng, và đó là hành vi đúng — một điểm sai lặng lẽ được lưu vĩnh viễn trên lượt làm bài.

---

## 10. Chặng 7 — Người duyệt

Không có bước nào thay được bước này, và kế hoạch không giả vờ ngược lại.

Người duyệt xem trong `/admin/tests/{slug}`: nghe từng clip, nhìn từng ảnh, đọc từng câu bị cờ ở §6.2, sửa những chỗ cần. Cổng publish sẽ tự chặn phần còn lại — thiếu audio, thiếu ảnh, kịch bản đã đổi sau khi thu.

Ước lượng thật thà: **2–4 giờ cho 200 câu**. Đó là con số đáng so sánh với việc tự viết 200 câu (hàng tuần), chứ không phải với số không.

---

## 11. Chạy lại được, và hàng đợi vẫn là một truy vấn

Không có bảng job, không có trạng thái retry — cùng luật với `backfill_audio` và `enrich_skills`:

- Chặng 2 bỏ qua cụm đã có tệp dán.
- Chặng 4 bỏ qua clip đã có trong manifest **và** có tệp thật (chỉ manifest thì bản clone mới sẽ không bao giờ render lại).
- Chặng 5 bỏ qua ảnh đã có PNG đã xử lý.
- Chặng 6 idempotent theo `slug` + số câu chuẩn.

Chạy lại lệnh là tìm thấy ít việc hơn. Đó là toàn bộ cơ chế phục hồi, và nó đủ.

---

## 12. Chi phí và thời gian

| Chặng | Đơn vị | Ước lượng | Ghi chú |
|---|---|---|---|
| 2 — văn bản | ~42 lượt gọi | 20–60 phút (Ollama tại máy) | OpenRouter free 50/ngày ⇒ **không đủ cho một đề trong một ngày** |
| 3 — kiểm | ~200 lượt gọi ngắn | 15–40 phút | một lượt/câu để đối chiếu đáp án |
| 4 — audio | 54 clip | 15–30 phút | edge-tts phụ thuộc mạng; ffmpeg cho ~48 clip nhiều lượt |
| 5 — ảnh | ~11 tấm | **~30 phút** | đo được: 2,5 phút/tấm, đỉnh 12,37 GB RAM |
| 6 — nạp | — | vài phút | |
| 7 — người duyệt | 200 câu | **2–4 giờ** | chặng đắt nhất, và không bỏ được |

---

## 13. Rủi ro, xếp theo mức độ khó chịu

1. **Câu hỏi "trông giống TOEIC" mà không phải TOEIC.** Rủi ro lớn nhất và khó đo nhất: mô hình viết được câu đúng ngữ pháp, có bốn lựa chọn, mà độ khó và kiểu bẫy lệch hẳn đề thật. Giảm bằng blueprint (§4) cộng đối chiếu nhãn, nhưng **chỉ người từng dạy TOEIC mới kết luận được**. Lát đầu tiên nên sinh **một part** và đưa người có nghề đọc, trước khi sinh cả đề.
2. **Ảnh Part 1 không đủ thực.** Xem §8. Có đường lùi.
3. **Đáp án sai lọt lưới.** Phép kiểm ở §6.2 bắt được phần lớn nhưng không phải tất cả — hai lượt gọi cùng một mô hình sai giống nhau là chuyện có thật. Dùng mô hình **khác** cho lượt đối chiếu nếu có.
4. **Bản quyền.** Xem §2.1 và §6.3. Giảm thiểu, không bảo đảm.
5. **Hết quota giữa chừng.** Đã có `LLMQuotaExhausted` và hiện vật trên đĩa; chạy lại là hết.

---

## 14. Cố ý KHÔNG làm

- **Không sinh thẳng vào database.** Xem §2.4.
- **Không tự publish.** Đề tự sinh vào thẳng tay người học mà không ai đọc là cách nhanh nhất để mất niềm tin, và niềm tin không lấy lại được bằng một bản vá.
- **Không có bảng job.** Xem §11.
- **Không sinh giải thích ở chặng 2.** Giải thích cho câu sai đã có đường riêng trong tầng AI và **tính toán một lần cho mọi người học** ([AI-ENGINEERING-PLAN](AI-ENGINEERING-PLAN.md) §3). Nhồi vào đây là dựng bản thứ hai của cùng một thứ. *(Ngoại lệ: dòng `Explanation:` trong định dạng dán vẫn nhận, vì mô hình viết câu hỏi là chỗ biết rõ nhất vì sao đáp án đúng.)*
- **Không đụng vào `scoring.py`.** Bảng quy đổi là dữ liệu; sửa mã để "đoán" điểm cho đề mới là đúng thứ §9 cấm.

---

## 15. Thứ tự làm

Bốn lát, mỗi lát tự nó chạy được và kiểm được:

1. **Part 5 trọn vẹn (30 câu).** Không audio, không ảnh, không cụm — lát mỏng nhất đi hết đường từ blueprint tới database. Nó chứng minh hoặc bác bỏ giả thiết lớn nhất (§13.1) với chi phí thấp nhất.
2. **Part 1 (6 câu).** Thêm ảnh, và đây là lát trả lời câu hỏi ở §8 về mức ảnh thực. Ít câu, nhiều thông tin.
3. **Part 3 (13 hội thoại / 39 câu).** Thêm audio nhiều giọng và cụm. Part đông câu nhất; xong nó là xong phần khó của bài nghe.
4. **Phần còn lại** (2, 4, 6, 7) cộng bảng quy đổi điểm và một lượt duyệt đầy-đủ.

---

## 16. Kiểm

- Mỗi chặng có một bài test chạy trên **hiện vật cố định**, không gọi mô hình: một tệp dán mẫu đi qua parser thật và phải cho ra đúng số cụm, đúng số câu, đúng số đáp án theo part.
- Bài test bắc qua ranh giới: một cụm Part 2 sinh ra phải **vượt qua đúng cổng nó sẽ gặp lúc commit** — cùng khuôn với `test_a_pasted_part_1_question_passes_the_gate_it_will_meet_at_commit`, bài test đã tồn tại vì hai nửa từng xanh với test của riêng mình mà không nửa nào đi qua giữa.
- Lượt gọi mô hình thật đánh dấu `external` và bị deselect mặc định, như `test_tts_external.py`.
- **Một lượt đầu-cuối chạy tay, rồi ghi lại những gì học được vào đây.** Một pipeline chỉ chạy được với khoá thật và mạng thật thì đáng một ghi chú sống lâu hơn là một bài test không ai dám chạy.

---

## 17. Đã học được gì khi chạy lát 1 (2026-08-22)

§16 nói một pipeline chỉ chạy được với khoá thật và mạng thật thì đáng một ghi
chú sống lâu hơn một bài test không ai dám chạy. Đây là ghi chú đó.

**Lỗi lớn nhất nằm ở tầng ĐỀ, và không phép kiểm từng câu nào thấy được.** Lượt
sinh 30 câu bằng `nemotron-3-ultra-550b` cho **29/30 đáp án là (A)** — người chọn
bừa A được 97%. Mỗi câu riêng lẻ hoàn toàn hợp lệ. Model càng mạnh thì thiên lệch
càng gọn ghẽ chứ không mất đi (`gemma3` 4B: 20/30 là A). Sửa bằng **hoán vị** ở
`exam/balance.py` — cùng bốn phương án, cùng phương án đúng, chỉ khác chỗ in ra —
và gán đích vòng tròn thay vì xáo ngẫu nhiên, nên phân bố đều theo định nghĩa và
chạy lại không xê dịch. Thêm một cổng chặn nạp khi một chữ cái vượt 40%.

**Nhiễu đồng nghĩa là lỗi nội dung trội nhất, và nó sửa được bằng PROMPT chứ
không bằng model to hơn.** Bản đầu cho ra những câu như `verify / confirm /
validate / authenticate the references` — bốn đáp án đúng. Prompt v2 nêu thẳng
phép thử ("đọc câu bốn lần, mỗi lần thay một lựa chọn; hai lựa chọn cùng chấp
nhận được thì bỏ câu đó đi") và bắt giải thích **nêu lý do sai của TỪNG nhiễu**.
Đo trên cùng 8 ô, cùng người chấm: **3/8 bất đồng → 1/8**, và câu duy nhất còn
bất đồng đúng là câu thật sự còn hai đáp án (`arrive at / by the scheduled time`).

**Model suy luận phá hai giả định của chặng sinh.** Nó trích dẫn chính mốc
`[QUESTION]` trong lúc tự nhủ, nên phép "tìm mốc" bắt phải đoạn suy nghĩ và lưu
nó như thể là câu hỏi; và nó tiêu hết 600 token trước khi tới khối cần lấy. Bản
sửa: lấy mốc **đứng đầu dòng, lần cuối cùng**, đòi khối có đủ `(D)` lẫn `Answer:`,
`max_tokens` 2600, và **ném thay vì lưu** khi khối không hoàn chỉnh — lưu rác
nghĩa là ô coi như xong và lần chạy sau bỏ qua nó.

**Hạn mức ngày có thật và đã cắn.** Gói miễn phí của OpenRouter là 50 lượt/ngày;
một đề Part 5 tốn 30 lượt sinh cộng 30 lượt đối chiếu, tức **không xong trong một
ngày**. `LLMQuotaExhausted` dừng hẳn đúng như §5 mô tả và các ô đã ghi ở lại trên
đĩa; chạy lại lệnh hôm sau là làm tiếp. Đối chiếu đáp án nên để model chạy tại
máy — nó không tốn hạn mức, và vai người chấm cần *khác* người viết hơn là cần
mạnh.

**So sánh có ý nghĩa cần cùng một người chấm.** Con số 40% → 20% giữa `gemma3` và
`nemotron` chỉ đọc được vì cả hai đề đều do `gemma3` chấm. Đổi cả hai đầu cùng
lúc thì không kết luận được gì.

**Còn thiếu, và đây là việc tiếp theo:** một phép kiểm phát hiện "hơn một đáp án
dùng được" trực tiếp, thay vì suy gián tiếp từ chuyện người chấm bất đồng. Nó là
lỗi nội dung trội nhất mà cổng hiện tại mù hoàn toàn.

### 17b. Thử nhà cung cấp thật (2026-08-22)

**Một adapter cho mọi nhà cung cấp nói giao thức OpenAI.** Groq, Cerebras và
Google (Gemini qua điểm cuối tương thích) khác nhau đúng một `base_url`, nên
`app/services/llm/openai_compatible.py` là một tệp cộng một bảng tra tên →
endpoint — cùng hình dạng với "một driver `s3` phủ sáu nhà cung cấp" của
ADR-006 §2.8. Thêm nhà cung cấp mới là thêm một dòng.

**Ba lỗi chỉ chạy thật mới thấy, cả ba đã sửa:**

- **402 bị coi là lỗi tạm thời.** Một khoá Cerebras xác thực được, `GET /models`
  trả 200, mà mọi lượt suy luận trả 402 "payment required" (khoá thuộc tổ chức
  Team chưa có subscription). Nếu 402 là lỗi thường thì vòng lặp đi hết 30 ô,
  hỏng y hệt nhau, và dòng nói đúng nguyên nhân nằm dưới 29 dòng giống hệt. Giờ
  nó dừng hẳn như hạn mức ngày.
- **Chặng sinh thiếu backoff.** Gemini trả 503 "high demand" khá thường; không
  lùi thì một lượt chạy 30 ô ra **0 tệp** trong vài giây. `_with_backoff` vốn
  nằm riêng trong `enrich_skills` nay lên `app/services/llm/retry.py` để hai
  lệnh dùng chung — một bản sao thứ hai sẽ trôi ở đúng danh sách mã lỗi tạm thời.
- **Tên biến môi trường lệch nhau.** SDK của Google dùng `GEMINI_API_KEY`, tầng
  LLM ở đây dùng quy ước `<tên>_api_key` tức `GOOGLE_API_KEY`. Chỉ nhận một tên
  cho ra kiểu hỏng tệ nhất: khoá nằm ngay trong `.env` mà chương trình báo thiếu
  khoá. Nay nhận cả hai.

**Model sống và chết theo phút.** Đo trong cùng một phút: `gemini-3.7-flash`
**0/4** lượt thành công (503), `gemini-3.5-flash` **4/4**, `gemini-3.1-flash-lite`
**4/4**. Một pipeline chạy hàng chục lượt phải coi "model không trả lời" là
trạng thái bình thường, không phải sự cố.

**Hạn mức miễn phí nhỏ hơn con số quảng cáo.** Gemini cạn sau khoảng 20 lượt
sinh cộng phần dò; OpenRouter free cạn ở 50. Một đề Part 5 cần ~60 lượt (30 sinh
+ 30 đối chiếu), nên **gói miễn phí nào cũng phải chia làm hai ngày** — hoặc để
model chạy tại máy làm người chấm.

**Giá đo được:** cả đề 30 câu, sinh cộng đối chiếu, tốn **~0,12 USD** trên gói
trả tiền của `gemini-3.5-flash` (0 trên gói miễn phí). Giá công bố đã thêm vào
`_RATES`; ghi giá THẬT chứ không ghi 0 dù đang chạy miễn phí — gói miễn phí là
thuộc tính của tài khoản, không phải của model.

**Thiên lệch vị trí đáp án có ở MỌI người viết**, không riêng model nhỏ:
gemma3 4B 67% là (A), nemotron 550B 97%, gemini-3.5-flash 60%. Đây là tính chất
của việc sinh câu hỏi, không phải của một model — nên `balance` là một chặng bắt
buộc, không phải một tuỳ chọn.

### 17c. Loại câu không đạt — và vì sao phép kiểm quan trọng nhất vẫn chưa dùng được

**Bar cho một câu Part 5: đúng MỘT phương án điền được.** Đó là lỗi nội dung trội
nhất và là thứ mọi phép kiểm khác đều mù — bốn phương án đồng nghĩa không trùng
chuỗi, không lệch độ dài, và vẫn là bốn đáp án đúng.

`check.count_workable_options` hỏi thẳng câu đó thay vì suy gián tiếp từ chuyện
người chấm bất đồng. Suy gián tiếp không tách được "đáp án ghi sai" với "hai đáp
án cùng đúng", mà hai lỗi ấy cần hai cách xử lý khác nhau.

**Nhưng nó chỉ tốt bằng người chấm, và người chấm 4B thì không đủ.** Đo thật:
gemma3 gắn cờ 5/19 câu là có hai phương án; đọc tay ba câu trong số đó thì cả ba
đều rõ ràng một đáp án (`whose` vs `which`, `Although` vs `Despite`). Nên phép
kiểm này **ghi cờ, không chặn nạp**, và chỉ `prune --ambiguity` mới dựa vào nó.

**Guard "người chấm không dùng được" đo phân bố câu trả lời trên MỌI câu**, không
chỉ câu bị cờ. Một model nhỏ có thể trả lời phản xạ cùng một chuỗi cho tất cả, và
lúc đó ta sẽ xoá những câu ĐẠT dựa trên một phép đo không đo gì — rồi mỗi lần
chạy lại xoá tiếp, vì câu sinh lại cũng nhận đúng câu trả lời phản xạ ấy. Ở lượt
đo này guard KHÔNG nổ (phân bố là `C×5 D×5 AB×5 B×3 A×2`), và đó là kết quả đúng:
gemma3 không thoái hoá, nó chỉ sai. Hai chuyện khác nhau và cần hai cách xử lý.

**`prune` XOÁ tệp dán chứ không đánh dấu.** Hàng đợi của chặng sinh là một truy
vấn trên thư mục, nên xoá một tệp chính là đưa ô đó trở lại hàng đợi. Một cột
`status` bên cạnh sẽ là trạng thái thứ hai phải giữ đồng bộ với sự tồn tại của
tệp, và hai nguồn sự thật cho cùng một câu hỏi là chỗ chúng lệch nhau.

### 17d. TokenRouter, và ba lỗi mà model suy luận làm lộ ra

`opencode` trên máy này đã đăng nhập sẵn vào **TokenRouter** — một cổng OpenAI-
compatible với `qwen/qwen3.8-max-free`, model mở cỡ frontier, miễn phí. Nối vào
tốn đúng **một dòng** trong bảng `ENDPOINTS`, đúng như thiết kế một-adapter đã
hứa. Khoá đọc từ `~/.local/share/opencode/auth.json` hoặc `TOKENROUTER_API_KEY`.

Nó viết được câu đạt, nhưng **chậm: ~2,5 phút một câu**, vì suy luận rất dài. Ba
lỗi lộ ra từ đó, không lỗi nào thấy được nếu chỉ đọc mã:

- **`content` RỖNG kèm `reasoning_content` dài.** `finish_reason: length`, 2 600
  token đầu ra tiêu hết vào phần suy nghĩ (10 862 ký tự), câu trả lời chưa kịp
  bắt đầu. Không nói ra thì lỗi này đội lốt "model trả lời sai định dạng", và
  người sửa đi chỉnh prompt trong khi thứ cần chỉnh là `max_tokens`. Adapter nay
  báo đúng tên nguyên nhân kèm số ký tự đã nghĩ; `max_tokens` lên 6 000.
- **Hạn giờ 90 giây quá ngắn.** Một lượt sinh mất ~2,5 phút, nên hạn giờ cũ biến
  mọi lượt thành lỗi mạng. Nay 300 giây.
- **`with_backoff` không thử lại hết-giờ.** Nó chỉ nhận ra lỗi tạm thời qua mã
  số (429/5xx), mà "read operation timed out" không mang mã nào — nên một ô vượt
  giờ ở lượt đầu bị bỏ luôn, im lặng, vì vòng lặp chỉ ghi một dòng rồi đi tiếp.

**Kết quả: `tp-form-06` đủ 30 câu**, viết bằng `gemini-3.5-flash` (19 câu) và
`qwen3.8-max-free` (11 câu), qua hết cổng, đáp án cân A=7 B=7 C=8 D=8, đã nạp ở
trạng thái `draft`. Vòng `prune → write → balance → check` chạy đúng như thiết
kế: xoá tệp của ô hỏng là đưa nó về hàng đợi, và lượt `write` sau chỉ làm đúng
những ô đó.


---

## 18. Đã học được gì khi chạy lát 2 — Part 1 (2026-08-22)

Sáu câu, và mọi thứ khiến Part 1 khác Part 5 đều nằm ở chỗ **không có gì được
in ra**. Bốn "lựa chọn" là bốn câu nói, `content` là NULL và chữ nằm ở
`spoken_text`. Ba hệ quả, cả ba đều hỏng im lặng:

- **Mọi phép kiểm ngữ nghĩa đọc thẳng `option.content` đều trở thành phép so
  bốn chuỗi rỗng với nhau — và chúng đều "đạt".** Thấy được vì `check_options`
  báo "có hai lựa chọn trùng nhau" ở cả 6 câu; nếu nó báo *đạt* thay vì báo
  trùng, cổng kiểm đã tắt lặng lẽ và không ai biết. `option_text()` đọc
  `content or spoken_text` và mọi phép kiểm đi qua nó.
- **Khoá chống trùng cũng thế.** `_normalise(prompt_text)` cho ra chuỗi rỗng ở
  mọi ô Part 1, nên phép chống trùng tắt đúng vào part dễ lặp nhất. Khoá của
  Part 1 lấy từ chính bốn câu nói.
- **Đối chiếu đáp án cần phần mô tả ảnh**, thứ không nằm trong tệp dán. Không
  truyền vào thì người chấm đang chọn một trong bốn câu mà không biết tấm ảnh
  có gì — và nó vẫn trả về một chữ cái, nên phép kiểm trông như đang chạy.

**Mô tả ảnh là hiện vật RIÊNG (`photos/<slot>.txt`), không nằm trong tệp dán.**
Parser từ chối dòng lạ sau các đáp án, nên nhét vào cùng tệp là làm cả khối
không đọc được. Tách ra cũng đúng về vòng đời: mô tả phục vụ chặng vẽ, tệp dán
phục vụ chặng nạp, và hai chặng chạy lại độc lập.

**`plan` phải CỘNG DỒN, không ghi đè.** Lập kế hoạch Part 1 xoá mất kế hoạch
Part 5 — và các tệp dán của Part 5 vẫn nằm nguyên trên đĩa, nên không có gì báo
cho tới khi `check` nói "0 ô" về một part đã viết xong. `bp.merge` thay part
cùng số và giữ phần còn lại. Cùng lý do, `balance` gán đích **trong từng part**:
gán trên danh sách gộp thì thêm một part mới sẽ dịch đích của mọi part đã cân
trước đó, viết lại tệp dán của chúng, và chúng không còn khớp với những gì đã
nằm trong database. `load` cũng có `--part`, vì `commit_part` **cộng thêm** câu
chứ không thay thế.

**Một lượt gọi hỏng không được dừng cả chặng kiểm.** Model miễn phí của
tokenrouter trả 503 rồi 200 một cách ngẫu nhiên: đo được **ba lượt 503 liên tiếp
rồi lượt thứ tư trả 200**, tức là `tries=4` mặc định bỏ cuộc đúng một lượt trước
khi thành công. Chặng kiểm nay dùng `tries=7, delay=6.0`, và một lượt gọi hỏng
thành **cờ** trên ô đó thay vì một exception vứt hết kết quả của cả lượt chạy.

### 18.1 Ảnh: câu hỏi mở của §8 đã có câu trả lời

§8 nói mức ảnh thực của `flux2-klein-4b-4bit` là **chỗ chưa đo** và phải thử 6
tấm rồi nhìn trước khi cam kết. Đã thử. **Đạt** — ảnh ra là ảnh chụp văn phòng
thật, người thật, ánh sáng cửa sổ, không phải minh hoạ phẳng. Đường ảnh mượn của
ADR-004 không cần dùng tới cho Part 1.

**Nhưng phần mô tả không dùng thẳng làm prompt vẽ được.** Nó chứa đầy câu phủ
định — "No telephone, papers, or other people are visible" — vì đó chính là thứ
làm ba câu nhiễu sai một cách kiểm chứng được. Mô hình khuếch tán không có phủ
định, nên "no telephone" đọc ra gần như "telephone". `app/content/exam/photos.py`
tách chúng ra và đẩy sang vế `Avoid:`, cắt tới mức **mệnh đề** chứ không tới câu,
vì câu phủ định thường nấp ở nửa sau một câu ghép ("Both are standing; no chair
or desk is visible").

**Và §8 nói đúng rằng người phải xem từng tấm.** Tấm đầu tiên vẽ đúng người,
đúng động tác, đúng số người — nhưng có **một tờ giấy trên bàn** dù mô tả ghi
"no papers". Ở đây nó không làm hỏng câu nào ("The desk is covered with papers"
vẫn sai), nhưng nó chứng minh đúng điều đã trả giá để biết ở bộ linh vật: mô hình
vẽ thừa, và thứ nó vẽ thừa có thể là đúng thứ một câu nhiễu phủ nhận. Lệnh
`photo` chỉ vẽ ra đĩa; **không có gì tự gắn ảnh vào câu hỏi.**

Và một tấm ĐÃ bị loại vì đúng lý do đó: p1-04 nói "The bag is held in the air
between them and is not touching the counter", mô hình vẽ chiếc túi đặt trên
quầy, và câu nhiễu "The bag is resting on the counter" trở thành đáp án đúng thứ
hai. Vẽ lại với `--seed` khác thì đạt. Cờ `--seed` tồn tại chính vì việc đó: xoá
tệp rồi chạy lại mà không đổi seed sẽ cho ra **đúng tấm ảnh vừa bị loại**, và
người chạy tưởng lệnh hỏng trong khi hàng đợi đang làm đúng việc của nó.

Tỉ lệ đo được: **5/6 đạt ở lượt đầu**, tấm thứ sáu đạt ở lượt thứ hai.

### 18.2 Âm thanh Part 1 không cần một chặng nào cả

Không có lệnh mới, không có bước thủ công. `commit_part` ghi `audio_script` lên
câu (bốn lượt nói, một giọng cho cả bốn), và **worker TTS đang chạy trong Docker
tự nhặt cả sáu câu trong vòng một sweep** — 13–15 giây mỗi clip, bốn accent xoay
vòng đúng như blueprint đặt. Đây là cổ tức của "hàng đợi là một truy vấn": thêm
một part mới không cần dạy worker điều gì, vì câu hỏi của nó vẫn là "nội dung
nào thiếu audio hoặc không còn khớp với kịch bản".

### 18.3 Trạng thái sau lát 2

`tp-form-06` có **36 câu**: Part 1 câu 1–6, Part 5 câu 101–130. Sáu câu Part 1
qua hết `validate_question` — tức là chúng **xuất bản được**, chỉ đang chờ người
duyệt. Đáp án Part 1 rải C D A B C D.

---

## 19. Ba dạng tranh của Part 1 (2026-08-22)

Sáu câu đầu tiên qua sạch mọi cổng và vẫn **thiếu một dạng**: cả sáu tấm đều có
người. Bảng nhãn cũng thiếu — nó chỉ có `PART_1_PERSON_DESCRIPTION` và
`PART_1_PERSON_AND_OBJECT_DESCRIPTION`, cả hai đều có người, nên nó không nói
được sự khác nhau mà người luyện đề thật sự gặp. Đã thêm
`PART_1_OBJECT_OR_SCENE_DESCRIPTION` vào `toeic_question_label_taxonomy.md` và
`labels.py`.

Nhưng mã nhãn không đủ để diễn đạt ràng buộc, vì "một người" và "nhiều người"
dùng chung một mã. `QuestionSlot.people` (`one` / `several` / `none`) mang nó,
và `validate` từ chối một blueprint Part 1 thiếu bất kỳ dạng nào — **trước khi
nó tốn một lượt gọi**. Phân bố hiện tại: 2 một người, 3 nhiều người, 1 không
người.

Đây là **cùng hình dạng với thiên lệch vị trí đáp án** (§17): một lỗi ở tầng đề
mà mọi phép kiểm từng câu đều mù, vì mỗi câu riêng lẻ hoàn toàn hợp lệ.

**Số người đổi cả bộ mẫu câu, không chỉ đổi nội dung.** Không nói ra thì mô hình
viết "The man is ..." cho tấm ảnh không có ai. Prompt nay ghi rõ: dạng `none`
không câu nào được có người làm chủ ngữ, dùng "There is / There are", bị động
trạng thái, hoặc hiện tại tiếp diễn với chủ ngữ là đồ vật — và câu nhiễu tốt
nhất ở dạng này là câu nhắc tới một người không hề có trong ảnh.

**Một lỗi của PROMPT, không phải của mô hình.** Bản cũ viết "Dòng `voice:` phải
ghi đúng: ca_male_1" và gemma3 chép luôn cả dấu ngoặc ngược vào đầu ra —
`` `voice:` ca_male_1 `` — thứ parser từ chối. Ba lượt liên tiếp hỏng y hệt
nhau, đủ để loại trừ chuyện ngẫu nhiên. Prompt nay đưa **nguyên dòng cần in**,
không mô tả nó.

**Hạn mức của ba nhà cung cấp cạn trong cùng một buổi**, và đó là số đo đáng ghi
hơn là một phiền toái: Gemini hết hạn ngày, OpenRouter hết hạn model miễn phí
ngày, tokenrouter trả 503 cho **mọi** yêu cầu có system prompt (kể cả 500 ký tự)
trong khi vẫn trả 200 cho yêu cầu không có system prompt. Hai model Gemini có
hạn mức RIÊNG — `gemini-3.5-flash` vẫn chạy khi `gemini-3.7-flash` đã cạn, và đó
là thứ viết xong ô cuối. gemma3 4B tại máy viết đúng định dạng nhưng **đặt một
câu đúng vào ô nhiễu** (mô tả ảnh ghi "Some chairs have been arranged in rows"
và nó dùng đúng câu đó làm nhiễu), nên nó không dùng được cho Part 1.

`LLMQuotaExhausted` nay **dừng hẳn chặng kiểm** thay vì thành một cờ trên từng
ô: hạn mức ngày không hết sau vài giây, nên đi tiếp chỉ sinh ra ba mươi dòng cờ
giống hệt và chôn mất dòng nói đúng nguyên nhân. Cùng cách xử lý mà `write` đã
dùng từ đầu.

`prune` nay xoá **cả mô tả ảnh** của ô bị loại, không chỉ tệp dán — để lại thì
một ô đã bị loại vẫn còn mô tả của lần viết hỏng, và `check` sẽ đọc mô tả của
một câu hỏi không còn tồn tại.

---

## 20. Hai thứ chỉ lộ ra khi có người bấm play (2026-08-22)

**Audio Part 1 không phát được, và không truy vấn nào trong database thấy nổi.**
Worker TTS ghi clip xuống đĩa **local**, còn `audio_public_base_url` trỏ tới
Supabase — nên đề vừa nạp có đủ hàng `audio_asset`, `validate_question` trả OK,
giao diện hiện nút play, và không có gì phát ra. Database đúng; thứ sai nằm ở
nơi database không nhìn tới. `push_media` là bước còn thiếu, và trước đây không
có gì trong luồng sinh đề nhắc tới nó.

Nay có `generate_exam media --slug <slug> [--push]`: hỏi thẳng **nhà cung cấp**
từng khoá của đề, báo câu nào thiếu, và `--push` đẩy nốt. Ảnh không dính lỗi này
(`import_media` đẩy thẳng lên Cloudinary) nhưng vẫn kiểm cả hai — một lệnh trả
lời được trọn câu "đề này phát được chưa" thì đáng tin hơn một lệnh trả lời được
nửa câu.

Một cái bẫy khi tự kiểm bằng `curl`: URL công khai của Cloudinary có **thư mục**
(`CLOUDINARY_FOLDER`) chen giữa base và `storage_key`, còn của Supabase thì
không. Ghép thiếu thư mục ra 404 và đọc ra như "ảnh chưa lên", trong khi ảnh vẫn
ở đó. Dùng `public_url` của driver, đừng tự ghép.

**Ảnh Part 1 nay là ảnh đen trắng.** Đề thi thật in đen trắng, nên một tấm ảnh
màu đặt người học vào một bài khác với bài họ sẽ gặp: màu là manh mối mà phòng
thi không cho ("chiếc áo vàng", "cái hộp đỏ"). Làm **cả hai vế** — prompt xin
ảnh đơn sắc, và `to_greyscale` ép về đơn sắc sau khi vẽ:

- chỉ ép thôi thì mô hình bố cục theo màu, và bản khử màu của một cảnh hợp lý về
  màu có thể mất hết tương phản giữa chủ thể và nền;
- chỉ xin thôi thì mô hình vẫn trả ảnh màu ở một số lượt, và cái sai đó chỉ lộ
  ra khi có người nhìn.

Sáu tấm đã có được **chuyển tại chỗ chứ không vẽ lại**: bố cục của chúng đã được
soi và xác nhận khớp với bốn câu mô tả, còn vẽ lại thì phải soi lại từ đầu và có
nguy cơ mang về đúng lỗi "tấm ảnh làm một câu nhiễu thành đúng". Tương phản còn
lại sau khi khử màu (độ lệch chuẩn kênh xám) là 43–78 trên thang 255; tấm thấp
nhất (p1-03) vẫn tách rõ áo phản quang, thùng hàng và xe đẩy khỏi nền.

Đổi byte thì đổi luôn mã băm, nên sáu tấm mang khoá mới và cần `--overwrite` khi
nhập lại. Sáu hàng `image_asset` cũ thành mồ côi — `reconcile_media` là chỗ tìm
ra chúng.

---

## 21. Bản thu Part 1 phải đọc nhãn đáp án (2026-08-22)

Bản thu đọc bốn câu mô tả liền nhau, **không đọc "(A)", "(B)", "(C)", "(D)"**.
Người thi Part 1 không đọc gì cả — sách thi chỉ có tấm ảnh — nên không có nhãn
thì không cách nào biết câu vừa nghe là câu nào, và cả sáu câu trở thành không
trả lời được.

Không phép kiểm nào trong hệ thống thấy được: hàng `audio_asset` có,
`audio_script` có, `validate_question` trả OK, `media` báo clip đã lên nhà cung
cấp. Mọi thứ đúng, trừ nội dung bản thu. **Chỉ người bấm play mới biết** — cùng
loại với lỗi ở §20, và là lý do §8 nói người phải xem từng tấm ảnh.

Sửa ở `content_import`, không ở writer của pipeline: nhãn phải có với **mọi**
câu Part 1/2 dù ai soạn — dán tay, `import_media`, hay pipeline. Sửa ở writer thì
nội dung soạn tay vẫn hỏng y hệt và không ai biết.

`spoken_option(label, content)` là chỗ duy nhất quyết định hình dạng đó, vì nó là
thứ **chỉ nghe mới biết đúng sai** — khi cần đổi thì phải có đúng một chỗ để đổi.
Giữ dấu ngoặc chứ không viết `A.`: một chữ "A" đứng riêng trước câu tiếng Anh có
thể bị đọc thành mạo từ *a*. Đo với edge-tts (`en-AU-NatashaNeural`, cùng một
câu): không nhãn 2,71s · `(A)` 3,12s · `A.` 3,17s — cả hai dạng đều thật sự phát
ra tên chữ cái, và `(A)` là dạng ít rủi ro hơn.

`option.spoken_text` vẫn giữ câu **trần**. Hai cột trả lời hai câu hỏi khác nhau:
lượt nói là "người đọc phát ra cái gì", `spoken_text` là "đáp án A nói gì" — và
giao diện đã in nhãn ở chỗ khác rồi.

**Sáu câu đã nạp được sửa bằng `PATCH /admin/questions/{id}`, không xoá đi nạp
lại**, vì lúc đó chúng đã có hai lượt làm bài. Phần còn lại tự chạy đúng như
thiết kế: đổi kịch bản làm `script_fingerprint` lệch khỏi `audio_script_hash`,
`media_state` báo STALE, worker thu lại trong một sweep. Thời lượng đi từ
13,6–14,9s lên 15,2–17,0s — **+1,6 đến 2,1 giây, tức là 4 × 0,4 giây**, đúng
bằng bốn chữ cái. Rồi `generate_exam media --push` bắt đúng sáu clip chưa lên
nhà cung cấp và đẩy nốt: lệnh viết ở §20 đỏ vì một lý do thật ngay lần đầu dùng.
