# TOEIC Pilot — Tiến độ & Lộ trình

> **Đây là file theo dõi duy nhất của dự án.** Sprint, task, trạng thái thật của code — tất cả ở đây.
> Cập nhật **ngay khi** hoàn thành một task, không để dồn.
>
> Các tài liệu khác có vai trò khác và **không** chứa trạng thái sprint:
> `PLAN.md` = spec sản phẩm · `ARCHITECTURE.md` = kiến trúc hiện trạng · `ADR-001` / `PHASE2-AUDIO` (= ADR-002) / `ADR-004` / `ADR-005` = quyết định + lý do · `MEDIA-PIPELINE.md` = media hoạt động thế nào + điểm yếu · `DESIGN-SYSTEM.md` = hệ thống thiết kế giao diện (đã viết, **chưa triển khai**) · `SPEC-LEARNING-HUB.md` = bộ mặc định tạm thời của Learning Hub, dựng để sửa · `REVIEW-OPUS.md` = review kỹ thuật (ảnh chụp 2026-08-08, không cập nhật tiếp)

**Cập nhật lần cuối:** 2026-08-10

---

## 1. Đang ở đâu

| | |
|---|---|
| **Phase hiện tại** | Sprint 3 + 4 chạy đầu-cuối cho **từ vựng và dictation**; dictation đã có cây phân cấp 4 tầng |
| **Chặn Phase 2** | **Không còn gì.** Cả hai blocker đã gỡ (audio, data model) |
| **Sprint kế tiếp** | Sprint 5 — TOEIC Practice (kèm phần question của Sprint 3 còn nợ) |
| **Test** | 378 thu thập — **376 chạy** + 2 `external` deselect mặc định |
| **Gate CI** | 13, tất cả xanh |
| **Migration** | `001_initial_users` → `002_audio_assets` → `003_domain_schema` → `004_images_and_scoring` → `005_roles_and_audit` → `006_dictation_audio_optional` → `007_dictation_hierarchy` → `008_dictation_completion_flag` → `009_user_profile` → `010_avatar` |
| **Bảng** | 24 |
| **Endpoint** | **52** — auth (4), health (2), học viên (14), hồ sơ (3), admin (29) |
| **Trang web** | 18 route |
| **Media** | **387** clip audio, 3 ảnh (`apps/api/media/`: 390 file) |
| **Nội dung trong repo** | **43 từ vựng** (42 thuộc Business), 4 câu dictation ← vẫn là nút thắt |
| **Giao diện** | Design system đã triển khai toàn bộ ([`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md)); 3 route dictation dùng tham số động, còn lại dựng tĩnh |

**Kiểm chứng lại toàn bộ ngày 2026-08-09:** `pytest` **294 passed / 2 deselected** — gồm cả 3 test `integration` chạy trên PostgreSQL thật (`tests/test_concurrency.py`, dùng `TEST_DATABASE_URL` trỏ vào database riêng để không làm bẩn dev DB) · `ruff check` sạch · `ruff format --check` 67 file đúng · `mypy` strict 46 file không lỗi · `pnpm lint` sạch · `pnpm build` xanh · `pnpm gen:api-types` sinh lại **không drift** · `alembic upgrade → downgrade → upgrade` sạch tới `008`.

### Điều quan trọng nhất cần biết

**Vòng đời nội dung đã khép kín và chạy thật.** Admin dán từ → lưu ở `draft` → worker sinh audio 4 accent → publish (bị chặn nếu audio thiếu hoặc lệch) → học viên ôn tập bằng flashcard SM-2 và làm dictation. Đã chạy đầu-cuối qua stack Docker, không phải chỉ qua test.

**Dictation có cây phân cấp riêng và chấm ở client.** `dictation_topic → section → story → item`, câu có thứ tự trong bài, tiến độ theo bài. Chấm chạy trong trình duyệt (`apps/web/src/lib/dictation.ts`, bản port từng bước của bộ chấm Python — 20/20 ca kiểm khớp tuyệt đối), server vẫn chấm lại và điểm của server mới là bản được lưu. Giao diện **không hiện phần trăm**: chỉ "đúng rồi / chưa đúng" và "3/6 câu đã xong".

**Thiếu là nội dung, không phải tính năng.** Hiện có **3 từ và 4 câu dictation** — đủ để chứng minh đường đi, không đủ để dạy ai.

**Nút thắt thật là nội dung, không phải code.** Viết endpoint từ vựng mất vài ngày; soạn 500 từ có nghĩa, ví dụ và audio 4 giọng thì lâu hơn nhiều. Đó là lý do Sprint 3 là **công cụ nhập nội dung** chứ không phải Learning Hub: không có công cụ thì không có dữ liệu để test endpoint bằng gì ngoài fixture, và việc soạn nội dung không chạy song song được với việc code.

**`draft` đã có lối ra — nhưng chỉ cho hai loại nội dung.** `vocabulary_entry` và `dictation_item` publish được qua `POST /admin/{loại}/{id}/publish`, và cổng publish **từ chối** khi audio thiếu hoặc lệch khỏi text. `question.status` thì vẫn là trạng thái không ai thoát ra được, vì chưa có endpoint nào chạm tới `question` — đóng ở Sprint 5.

---

## 2. Thứ tự sprint

Đã sắp lại theo yêu cầu: **Learning Hub và TOEIC Practice trước, AI layer sau cùng.**

```
Sprint 3  Content Tooling       🟡 từ vựng + dictation XONG · phần question còn nợ
Sprint 4  Learning Hub          🟡 backend + frontend XONG · thiếu nội dung
Sprint 4b Dictation phân cấp    ✅ XONG (mục 4b)
Sprint 4c Hồ sơ người dùng      ✅ XONG (mục 4c)
Sprint 4d Media upload          🟡 ĐANG LÀM (mục 4d)
Sprint 5  TOEIC Practice        ← tiếp theo
Sprint 6  Hardening & bảo mật   ← bắt buộc trước AI
Sprint 7  AI Layer
Sprint 8  Analytics & Production
```

Sprint 3 và 4 chạy chồng lên nhau chứ không nối tiếp: mỗi phần công cụ nhập vừa xong là phần học viên tương ứng dựng được ngay. Cái còn nợ của Sprint 3 — trình nhập **câu hỏi** — không chặn Learning Hub, nó chặn Sprint 5, nên nó chuyển sang làm cùng Sprint 5.

### ⚠️ Rủi ro đã biết của thứ tự này

`REVIEW-OPUS.md` §7f khuyến nghị chèn một **lát cắt AI mỏng sớm** để giảm rủi ro. Đẩy toàn bộ AI về Sprint 6 nghĩa là phần **khó nhất, khác biệt nhất và rủi ro nhất** của sản phẩm chưa được kiểm chứng cho tới khi dự án đã đi được ~70%. Nếu tới lúc đó mới phát hiện RAG không đủ tốt hoặc chi phí quá cao thì đã muộn.

Đây là lựa chọn có ý thức, không phải sơ suất. Hai thứ giảm thiểu, đã đưa vào Sprint 6:

1. **Rate limiting** (P1-8) phải xong **trước** endpoint LLM đầu tiên. Endpoint LLM không đo đếm là hoá đơn không giới hạn.
2. **`ai_interaction`** (đếm token + chi phí) phải tồn tại từ request LLM đầu tiên, không phải sau. Không đo được thì không cải thiện được; không đếm được thì không giới hạn được.

Nếu muốn giảm rủi ro sớm hơn: chèn một lát cắt AI mỏng **một** use case (ví dụ "giải thích một câu ngữ pháp") vào cuối Sprint 5. Mục tiêu không phải ship mà là xác nhận kiến trúc và đo chi phí thật.

---

## 3. Sprint 3 — Content Tooling · 🟡 từ vựng + dictation XONG · question CÒN NỢ

> **Đọc mục này cho đúng:** tất cả các ô chưa tick dưới đây nói về trình nhập **câu hỏi TOEIC** (part 1–7), không phải về từ vựng/dictation. Phần từ vựng và dictation đã đầy đủ parse → commit → publish, cả backend lẫn `/admin` UI. Phần question chuyển sang làm cùng Sprint 5, vì nó chặn Sprint 5 chứ không chặn gì khác.

**Mục tiêu:** admin nhập được một đề hoàn chỉnh trong vài giờ, và nội dung phải qua duyệt trước khi học viên thấy.

Quyết định đầy đủ: [`ADR-005-CONTENT-TOOLING.md`](ADR-005-CONTENT-TOOLING.md).

Không có sprint này thì Sprint 4–5 không có dữ liệu để test bằng gì ngoài fixture, và việc soạn nội dung — nút thắt thật của dự án — không thể bắt đầu song song với việc code.

### Tại sao công cụ này nhỏ hơn vẻ ngoài

Đề TOEIC thật thuộc bản quyền ETS, nên audio và ảnh gốc **không dùng lại được**. Nghe như một hạn chế, nhưng nó cắt bỏ phần lớn công cụ: audio sinh lại từ transcript bằng pipeline đã có, ảnh thay bằng ảnh CC qua `ADR-004`. Trình nhập **chỉ xử lý văn bản** — không upload file, không cắt audio, không quản lý media.

Nguồn là PDF **có lớp text** ⇒ dán thẳng, không cần OCR.

### Schema
- [x] `users.role` ∈ `learner`/`editor`/`admin` + CHECK, mặc định `learner`
- [x] `created_by`, `published_by`, `published_at` trên mọi bảng nội dung (qua `PublishableMixin`)
- [x] Migration `005` + `006` (dictation cho phép chưa có audio)

### Backend
- [x] Dependency `require_role` — **là dependency, không phải kiểm tra trong thân hàm**, vì thân hàm dễ quên khi thêm route
- [x] `POST /admin/{vocabulary,dictation}/parse` — nhận text thô + đáp án, trả cấu trúc đã parse kèm lỗi `validate_question()`. **Không ghi database**
- [x] `POST /admin/{vocabulary,dictation}` — commit, luôn `draft` — ghi ở trạng thái `draft`, không có đường tắt ra `published`
- [x] CRUD cho `vocabulary_entry`, `dictation_item`, `topic` · [ ] `question*` (→ Sprint 5)
- [x] `POST /admin/{vocabulary,dictation}/{id}/publish` — chỉ `admin`, **chặn khi audio thiếu/lệch**
- [x] `uv run python -m app.content.backfill_audio` — worker ngoài luồng, hàng đợi là một câu truy vấn
- [x] ~~Parser~~ **đã làm khác thiết kế ban đầu**: mốc là `[PASSAGE]`/`[QUESTION]`/`[SCRIPT]` do người soạn gõ, không phải dò câu tiếng Anh trong PDF (ADR-007 §2.2). Parser: `Questions X-Y refer to the following …` mở `question_set`; `NNN.` mở câu; `(A)`–`(D)` là phương án

### Frontend `/admin`
- [x] Màn dán **từ vựng và dictation** — ô text dán hàng loạt, chọn topic, xem trước rồi mới lưu (`/admin/vocabulary`, `/admin/dictation`)
- [x] Màn dán **câu hỏi**: chọn part, ô text đề, ô text đáp án riêng
- [x] **Cảnh báo Part 1 và 2 phải dán từ phần audioscript** — phần đề của hai part này trong PDF gần như trống, ai không biết sẽ tưởng parser hỏng
- [x] Lưới review: lỗi hiện ngay tại dòng
- [x] Editor từng câu **có xem trước** — bắt buộc cho Part 1: không nhìn thấy ảnh thì không viết được bốn câu mô tả
- [x] Bảng nội dung có badge audio (`missing`/`stale`/`current`) + nút publish
- [x] Trường `source` **không được pre-select** — đây là cột duy nhất mà giá trị sai gây hậu quả pháp lý

### Test
- [x] Parser từ vựng + dictation: dòng đúng, dòng thiếu cột, dòng rỗng (`tests/test_services.py`)
- [x] Parser câu hỏi: đề đúng chuẩn, đề thiếu đáp án, đánh số nhảy cóc, stimulus thiếu
- [x] Mỗi endpoint admin: `learner` nhận **403**
- [x] `editor` không publish được — publish là `require_role("admin")`
- [x] Commit luôn cho ra `status='draft'`
- [x] Publish bị chặn khi audio `missing` hoặc `stale`

### Định nghĩa hoàn thành
Một admin dán 7 part từ PDF, sửa những chỗ parser bắt sai, publish, và nội dung xuất hiện đúng ở API — trong khi tài khoản `learner` không chạm được vào bất kỳ endpoint admin nào.

---

## 4. Sprint 4 — Learning Hub · 🟡 backend + frontend ĐÃ XONG

**Mục tiêu:** học viên đăng nhập được, học từ vựng theo chủ đề có phát âm 4 giọng, làm bài dictation và được chấm.

Schema đã sẵn sàng (`ADR-001` §B2). Việc còn lại là endpoint, UI và nội dung.

### Backend
- [x] `GET /api/v1/topics`
- [x] `GET /api/v1/vocabulary` — lọc theo topic, phân trang
- [x] `GET /api/v1/vocabulary/{id}` — kèm 4 accent audio
- [x] `GET /api/v1/vocabulary-review/session` — đến hạn trước, rồi từ mới, giới hạn 20/ngày
- [x] `POST /api/v1/vocabulary/{id}/review` — SM-2, ghi `state` **và** `log`
- [x] `GET /api/v1/dictation` + `/{id}` — **không trả transcript**
- [x] `POST /api/v1/dictation/{id}/attempts` — chấm theo `transcript`, giữ nguyên văn bài nộp
- [x] `app/services/srs.py` — SM-2 thuần hàm, có test từng nhánh
- [x] `app/services/dictation.py` — chuẩn hoá, `SequenceMatcher`, `word_diff`

### Frontend
- [x] `/learn` — chủ đề + lối vào
- [x] `/learn/vocabulary` — chọn accent, phát bằng `Audio` thuần
- [x] `/learn/review` — flashcard 4 nút
- [x] `/learn/dictation` — phát, nhập, diff tô màu
- [x] **Revamp UI vòng 1 (2026-08-09)** — hệ token màu sáng/tối, bộ component dùng chung, app shell có nav theo vai trò, skeleton thay cho chữ "Loading…", empty state nói rõ bước tiếp theo, `not-found` và `error` boundary
- [x] **Design system + revamp vòng 2 (2026-08-09)** — [`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md), triển khai trên toàn bộ 12 route. Bỏ mặc định của công cụ (Geist, indigo, `rounded-xl`, `shadow-sm`); token màu kiểm bằng công thức WCAG; 17 emoji → Lucide; thang bốn giọng US/UK/AU/CA; **nút chuyển sáng/tối ba trạng thái**; landing page dựng lại quanh cơ chế chấm từng từ
- [x] **Đã kiểm thật toàn bộ trang cần đăng nhập (2026-08-09)** — dựng nội dung thật qua chính API admin, đi hết 8 trang, thử cổng publish và cả bốn trạng thái badge audio. Ba lỗi chỉ lộ ra khi chạy: nav xuống dòng ở vai trò `admin`, một icon dùng cho hai khái niệm, và một import lệch khỏi JSX mà `next dev` không bắt (`DESIGN-SYSTEM` §13.4)
- [x] **Tách khu quản trị thành dashboard riêng (2026-08-09)** — `/admin/**` có `AdminShell` với thanh trên và sidebar riêng; header khu học trở về 3 mục cộng **một** nút `Quản trị` chỉ hiện với `editor`/`admin`. Đã kiểm bằng tài khoản `learner` thật: không thấy nút, `/admin/**` redirect về `/dashboard`, và endpoint trả 403 — cả ba lớp đều giữ
- [x] **Dictation: chấm ở client + đối chiếu từng từ (2026-08-09)** — `lib/dictation.ts` là bản port từng bước của bộ chấm Python; **20/20 ca kiểm khớp tuyệt đối** (diff, matched, expected, accuracy), gồm đảo thứ tự từ, từ lặp, nháy cong, chữ có dấu. Kết quả hiện ngay dưới ô nhập, xanh = đúng / cam = chưa đúng. Chỉ lần kiểm tra **đầu tiên** được ghi nhận — đã xác nhận trong Postgres: bấm hai lần, DB có đúng một hàng, và điểm server ghi (90.00) khớp con số client hiện
- [x] **Che từ chưa gõ tới (2026-08-09)** — bấm Kiểm tra khi gõ dở từng in nguyên đáp án. Bản sửa đầu tiên của chính tôi **vẫn sai** ở ca gõ dở + sai từ cuối (che 0 từ), phát hiện nhờ chạy thử chứ không nhờ đọc code; ranh giới đúng là số từ đã gõ, không phải vị trí trong diff. Parity với server giữ nguyên 20/20 sau khi sửa
- [x] **Gộp hai trang hub, sửa lại điều hướng (2026-08-10)** — `/dashboard` và `/learn` cũ làm cùng một việc mà không trang nào bao trùm trang kia: số "cần ôn hôm nay" chỉ có ở `/dashboard`, lối vào "Gõ lại từ" chỉ có ở `/learn`, và `/dashboard` **không nằm trong nav** nên rời khỏi nó một lần là không quay lại được — con số đáng lẽ điều khiển hành vi mỗi ngày lại nằm ở chỗ khó tới nhất. Giờ `/learn` là nhà duy nhất ("Hôm nay"), `/dashboard` chuyển hướng ở server (giữ route vì nó nằm trong bookmark và lịch sử của người đang dùng). Nav đổi từ `Learning Hub · Ôn tập · Dictation` — một lỗi phân loại, vì hai mục sau nằm BÊN TRONG mục đầu — sang ba mục ngang hàng `Hôm nay · Từ vựng · Dictation`. `Ôn tập`/`Gõ lại từ` rời khỏi nav vì chúng là hai **chế độ** của cùng một hàng đợi SM-2: mở cái nào trước thì cái đó tiêu hết hàng đợi của ngày, và cái còn lại hiện "không còn từ nào đến hạn". Logo khi đã đăng nhập trỏ `/learn` thay vì trang giới thiệu
- [x] **Nội dung Business đầu tiên có thật (2026-08-10)** — 40 từ soạn mới, rải đủ 5 loại từ (noun 13 · verb 11 · adj 8 · adv 4 · phrase 4) vì trắc nghiệm cần ≥ 4 từ **cùng `part_of_speech`** mới sinh nổi distractor. Nhập qua chính API admin (parse 40/40, commit 40 draft), `backfill_audio` sinh **320 clip · 0 lỗi**, rồi publish 40/40. Kiểm danh mục giọng edge-tts **trước** khi chạy hàng loạt, đúng như `CLAUDE.md` dặn — một voice id lỗi thời sẽ hỏng từng clip một giữa chừng
- [x] **Từ vựng có trạng thái thuộc/chưa thuộc + lối vào (2026-08-10)** — `GET /vocabulary-progress` (có auth) và `srs.mastery()`; ba mức `new`/`learning`/`mastered` **suy ra từ `interval_days ≥ 21`**, không phải từ `repetitions` — số lần ôn chỉ tăng nên một từ đã quên vẫn mãi khoe là đã thuộc, còn interval bị lapse kéo về 1 ngày nên tự hạ cấp. Endpoint **riêng** chứ không thêm cột vào `/vocabulary` công khai: với khách chưa đăng nhập thì mọi từ hoá ra `new`, đó là nói dối chứ không phải thiếu dữ liệu. Trang từ vựng thôi là một cuốn từ điển — có thanh "Đã thuộc 0/42", badge từng dòng và nút vào ôn tập
- [x] **Sửa một lỗi accessibility có thật** — viền ô nhập cũ chỉ đạt 1.48 tương phản (WCAG 1.4.11 đòi 3.0), tức gần như vô hình với người thị lực kém. Token `rule-strong` mới đạt 3.09–3.64

### Nội dung — **việc duy nhất còn lại của sprint này**
- [ ] Soạn ≥ 300 từ vựng cho ≥ 6 chủ đề — hiện có **43** trên **2** chủ đề (2026-08-11)
- [x] Sinh audio 4 accent × {headword, example} cho toàn bộ số từ đang có — **387 clip**, 0 lỗi
- [ ] Soạn ≥ 50 câu dictation — hiện có **15** (2026-08-11)

Công cụ để làm việc này đã xong và đã chạy thật: dán ở `/admin`, `backfill_audio` sinh audio ngoài luồng, publish chặn nếu audio chưa khớp. Không còn code nào chặn phần này.

### Hợp đồng & chất lượng
- [x] `pnpm gen:api-types` — đã chạy, sinh lại cho ra file y hệt
- [x] `API_ROUTES` đã có đủ 17 lối vào mới
- [x] Test `draft` không lọt ra, cho mọi endpoint đọc

### Định nghĩa hoàn thành
Học viên tạo tài khoản, học một chủ đề, ôn lại hôm sau và thấy đúng những từ đến hạn, làm dictation và nhận điểm chính xác.

---

## 4b. Dictation — phân cấp nội dung · ✅ ĐÃ XONG (2026-08-09)

```
dictation_topic          Short stories · Conversation · TOEIC Listening
   └── dictation_section  admin tự đặt tên: "Unit 1", "Level A", "Tuần 3"
        └── dictation_story   một bài văn liền mạch
             └── dictation_item   các câu CÓ THỨ TỰ (position), mỗi câu một audio
```

### Đã làm
- [x] Migration `007_dictation_hierarchy` — 3 bảng mới + `story_id`/`position` trên `dictation_item`, CHECK `(story_id IS NULL) = (position IS NULL)`. Chu trình upgrade → downgrade → upgrade sạch
- [x] 4 endpoint duyệt cây cho học viên, **mỗi tầng tự lọc `published`**
- [x] 6 endpoint admin: tạo + xuất bản cho cả ba tầng
- [x] Dán câu vào story: mỗi dòng thành một câu theo đúng thứ tự, nối tiếp sau câu đã có
- [x] Cổng publish story: **từ chối 409** khi chưa có câu nào đã xuất bản
- [x] Tiến độ theo story, **suy ra từ `dictation_attempt`** — không có bảng tiến độ song song
- [x] Frontend: 4 trang duyệt + breadcrumb + dải câu + màn quản trị cây
- [x] Câu chưa thuộc bài nào vẫn với tới được qua `?standalone=true` và lối "Câu lẻ" tự ẩn khi hết
- [x] 23 test mới (`tests/test_dictation_tree.py`), tổng **294**

### Sửa / xoá / sắp xếp (2026-08-09)
- [x] PATCH + DELETE cho cả ba tầng; sửa tên ngay tại chỗ trên màn cây
- [x] Chuyển câu vào bài hoặc gỡ ra thành câu lẻ (`story_id: ""`), `position` tự đặt cuối
- [x] Đổi thứ tự câu bằng mũi tên — gửi **cả danh sách** nên không có lúc nào hai câu trùng số
- [x] Xoá câu đã có người làm bị **chặn 409**, chỉ sang `archived`
- [x] Xoá bài/phần/chủ đề **không xoá câu**: chúng trở lại thành câu lẻ
- [x] Nút xoá hai bước, nói rõ hậu quả ("Xoá cả 3 phần?") thay vì "Bạn có chắc không?"
- [x] **Sửa lỗi Enter nhảy câu (2026-08-09)** — lần bấm làm câu trở thành đúng bị nhảy luôn sang câu sau vì giữ phím sinh ra `keydown` tự lặp. Chặn bằng `event.repeat` + chỉ mở khoá khi `keyup`: một lần bấm = một việc
- [x] **Hoàn thiện UX dictation (2026-08-09)** — gạch bỏ chuyển từ từ-đúng sang từ-gõ-sai (mã hoá cũ bị ngược); Enter kiểm tra, và Enter lần nữa khi đã đúng thì sang câu sau; từ gõ sai được gạch chân lượn sóng ngay trong ô nhập bằng lớp phủ khớp pixel
- [x] **Đơn giản hoá luồng dictation (2026-08-09)** — bỏ điểm số khỏi giao diện, chỉ còn "đúng rồi / chưa đúng" và tiến độ "3/6 câu đã xong". Migration `008` thêm `dictation_attempt.is_complete`; tiến độ đếm cột đó chứ không đếm `accuracy = 100`, vì gõ đủ rồi gõ thêm vẫn cho 100. Bỏ luôn luật "chỉ lần kiểm tra đầu tiên được ghi nhận" — nó sinh ra để chống nâng điểm, mà giờ không còn điểm để nâng
- [x] **Lưu trữ / Bỏ lưu trữ** ngay cạnh nút Xoá, và `PublishTag` có đủ **ba** trạng thái — `archived` từng hiện ra là "nháp", nói ngược hẳn sự thật
- [x] Thông báo 409 khi xoá được dịch sang tiếng Việt và chỉ đúng nút đang nằm cạnh
- [x] Giọng đọc theo **story**, không theo từng câu — một bài văn không còn bị bốn giọng đọc luân phiên

### Ba thứ chỉ lộ ra khi chạy thật
1. **`/dictation/topics` bị `/dictation/{item_id}` bắt trước** và 422 khi parse "topics" thành UUID. Đổi sang đường dẫn gạch nối, theo tiền lệ `/vocabulary-review/session`.
2. **`create_all` của container dev đã kịp tạo 3 bảng mới** trước khi kịp dừng nó — đúng cái bẫy `CLAUDE.md` ghi. Phải drop rồi mới autogenerate được.
3. **Autogenerate sinh khoá ngoại không tên**, kéo theo `drop_constraint(None, ...)` ở `downgrade` — câu lệnh không bao giờ chạy được. Chỉ lộ khi có người thật sự downgrade.

## 4c. Hồ sơ người dùng · ✅ ĐÃ XONG (2026-08-10)

**Mục tiêu:** người học có danh tính, mục tiêu và tuỳ chọn — và tài khoản có đường tự quản lý.

Chèn trước Sprint 5 chứ không phải sau, vì `PLAN.md` §3.3 nói AI Study Planner cần **điểm hiện tại, điểm mục tiêu, thời gian học mỗi ngày**. Đó chính là dữ liệu hồ sơ. Dựng mặt tiếp nhận trước thì tới Sprint 7 planner đã có dữ liệu thật để đọc, thay vì một biểu mẫu trống để đi xin.

### Schema — migration `009_user_profile`
- [x] Bảng `user_profile` **1-1**, khoá chính chính là khoá ngoại tới `users.id`
- [x] Hàng hồ sơ tạo trong **cùng transaction** với đăng ký, không tạo lười; migration backfill mọi tài khoản có sẵn
- [x] `users.password_changed_at` — nullable, **không** backfill bằng `now()`
- [x] `daily_new_limit` NULL = "theo mặc định hệ thống", **không** phải bản sao của số 20 hôm nay. `SPEC-LEARNING-HUB` §5 nói thẳng con số đó sẽ đổi; sao chép vào từng hàng sẽ ghim mọi học viên cũ vào số cũ đúng ngày nó đổi

### Backend
- [x] `GET /profile`, `PATCH /profile`, `GET /profile/stats`, `POST /auth/password`
- [x] `UserPublic` nhúng luôn hồ sơ — `SessionProvider` chỉ giải quyết phiên **một lần**, thêm một request nữa là thêm một trạng thái đang tải vào đúng chỗ đã quyết định chỉ có một
- [x] PATCH phân biệt **khoá vắng mặt** với **khoá mang null** qua `exclude_unset` — gộp kiểu `giá_trị or giá_trị_cũ` biến thao tác xoá thành lệnh không làm gì mà vẫn trả 200
- [x] Thống kê **suy ra mỗi lần đọc**, không có bảng đếm — cùng lý do đã ghi ba lần cho `StoryProgress` và `VocabularyProgress`
- [x] Múi giờ kiểm theo CSDL IANA của hệ thống, không theo danh sách tự giữ

### Thu hồi token khi đổi mật khẩu
- [x] Claim riêng `pwc` mang **thế hệ mật khẩu**, so **bằng nhau** chứ không so "phát hành sau"
- [x] Đo bằng **micro-giây**. Đây là điểm không hiển nhiên: `iat` chỉ có độ phân giải 1 giây, nên token phát hành cùng giây với lần đổi không phân biệt được — phép so theo thứ tự hoặc thả lọt token đó, hoặc từ chối chính token thay thế mà lần đổi vừa cấp
- [x] Không có claim = thế hệ 0, nên triển khai **không** đăng xuất người đang đăng nhập
- [x] `POST /auth/password` trả **token mới**, không trả 204 — không trả thì người dùng đổi mật khẩu xong bị đăng xuất tại chỗ và trông hệt như lỗi
- [x] Sai mật khẩu hiện tại trả **403 chứ không 401**: token vẫn hợp lệ, thứ bị từ chối là hành động

### Frontend
- [x] Trang `/profile` — hồ sơ, mục tiêu, tuỳ chọn, thống kê, đổi mật khẩu
- [x] `Avatar` sinh từ chữ cái đầu, màu suy từ **id** chứ không từ tên (đổi tên mà đổi màu thì người dùng tưởng nhìn nhầm tài khoản). **Vuông**, không tròn — §6.2 chỉ có một bán kính
- [x] `session.refresh()` — hồ sơ nằm trong phiên nên lưu xong phải đọc lại, nếu không header vẫn hiện tên cũ
- [x] `/learn` chào bằng tên hiển thị, không còn bằng phần đầu email

### Vòng thứ hai: giao diện (2026-08-10)
- [x] **Menu tài khoản ở header** thay cho khối chữ tĩnh — `shadow-overlay`, một trong **ba** ngoại lệ của luật cấm đổ bóng (§6.3). Đóng theo ba đường: Escape, bấm ra ngoài, và điều hướng; đường thứ ba suy từ `pathname` chứ không viết bằng effect, cùng thủ thuật menu mobile ở `app-shell.tsx`
- [x] **`ContributionGraph`** kiểu lịch đóng góp, phủ **365 ngày**. `LearningStats` đổi `recent: StudyDay[14]` thành `calendar` **thưa** (chỉ ngày có hoạt động) + `today` + `window_days`. Gửi thưa vì một năm đặc là 365 hàng mà phần lớn toàn số 0; gửi kèm `today` **theo múi giờ hồ sơ** vì lưới phải khớp với chuỗi ngày do máy chủ tính — để trình duyệt tự tính thì đồng hồ lệch hoặc múi giờ trình duyệt khác múi giờ hồ sơ là ô "hôm nay" nằm sai cột và không ai báo
- [x] Thang màu lưới dùng `ok` chứ **không** dùng `action`: chu sa là màu của hành động (§2.1), ba trăm ô chu sa sẽ đánh nhau với chính nút Lưu ở cuối trang
- [x] Ngưỡng bốn bậc là **số lượt tuyệt đối**, không phải phân vị — phân vị làm một ngày đã qua nhạt đi vì hôm nay học nhiều, tức là thang đo tự viết lại quá khứ
- [x] **`TargetScale`** — dựng đúng thành phần chữ ký §10: vạch chia là sáu bậc năng lực ETS thật, `radius-none`, vạch mục tiêu là vạch riêng chứ không phải điểm cuối. Và tôn trọng luật đi kèm: **chưa có điểm ước tính thì nói thẳng**, không vẽ 0, không nội suy
- [x] Khối danh tính dùng bậc nền `recess`, không phải card `panel` nổi — đó là cách hệ này diễn đạt độ sâu thay cho đổ bóng

### Vòng thứ ba: xem trước, sửa sau (2026-08-10)
- [x] **Sửa lỗi lệch của `Field`** — chú thích một dòng cạnh chú thích hai dòng đẩy hai ô nhập xuống hai độ cao khác nhau, và độ lệch đổi theo bề rộng màn hình nên trông như trục trặc ngẫu nhiên. Nay là cột flex với `mt-auto` ở ô nhập; bố cục một cột không có khoảng thừa nên không đổi gì
- [x] **`Modal`** dựng trên `<dialog>` gốc — có sẵn bẫy tiêu điểm, Escape và `inert`, ba thứ mà bản tự viết bằng `div` hầu như luôn thiếu
- [x] **Sự kiện `cancel` KHÔNG nổi bọt, nên prop `onCancel` của React không bao giờ chạy.** Escape đóng hộp thoại ở tầng trình duyệt còn state React vẫn tưởng nó đang mở, và lần bấm Sửa kế tiếp không mở ra gì. Đã phát hiện khi thử tay, không phải khi đọc code. Nay gắn listener bằng `addEventListener` trong effect
- [x] Tên hiển thị + múi giờ chuyển lên **khối danh tính**, sửa qua hộp thoại thay vì biểu mẫu dài
- [x] Mục tiêu và cách học chuyển sang **ô hiển thị** (`ValueTile`) — biểu mẫu luôn nói "chỗ này đang chờ bạn nhập", câu đó sai với người đã điền xong từ tuần trước
- [x] Trạng thái rỗng của mục tiêu là lời mời **"Đặt mục tiêu ngay"** chứ không phải dấu `—` (§9.6)
- [x] `ValueTile` phân biệt số đo với chữ: mono tabular là kiểu chữ của **số liệu** (§5.2), đặt "Cả bốn giọng" vào đó thì trông như lỗi font
- [x] `TargetScale` bỏ phần in lại con số — ô "Điểm mục tiêu" ngay trên đã có; thay bằng **dải tên sáu bậc năng lực**, thứ duy nhất trả lời được "850 đứng ở đâu"
- [x] Icon theo đúng bảng tra §8.4: `Pencil` cho Sửa, `UserRound` cho Tài khoản (trước đó dùng nhầm `User`)

### Test — 26 test mới (363 tổng)
- [x] Đăng ký tạo hàng hồ sơ · null xoá được trường · null bị bỏ qua với cột NOT NULL
- [x] Điểm mục tiêu không chia hết cho 5 → 422 · múi giờ không có thật → 422
- [x] Token cũ chết sau khi đổi mật khẩu · token thay thế sống · mật khẩu chưa đổi thì phiên không bị đụng
- [x] Số học chuỗi ngày tách thành hàm thuần `compute_streaks`, test không cần database
- [x] Lịch chỉ chứa ngày **có** hoạt động, và ngày trong lịch là ngày **theo múi giờ hồ sơ** — một lượt ôn lúc 00:30 giờ Hà Nội thuộc ngày hôm đó, không thuộc ngày UTC hôm trước

### Một thứ chỉ lộ ra khi chạy thật
**`create_all` của container dev lại tạo `user_profile` trước khi alembic kịp chạy** — đúng cái bẫy đã ghi ở mục 4b và trong `CLAUDE.md`, lần thứ hai. Lần này còn khó thấy hơn: `create_all` tạo được **bảng mới** nhưng không thêm được **cột mới vào bảng cũ**, nên `users.password_changed_at` vẫn thiếu trong khi `user_profile` đã có. Phải drop bảng rồi mới cho alembic chạy lại.

---

## 4d. Sprint media upload · 🟡 ĐANG LÀM

**Mục tiêu:** đưa được vào hệ thống một file do con người tạo ra — ảnh tự chụp, ảnh đã mua bản quyền, bản thu giọng người thật.

Quyết định đầy đủ: [`ADR-006-MEDIA-UPLOAD.md`](ADR-006-MEDIA-UPLOAD.md). Đóng nợ `MEDIA-PIPELINE` §10.5.

### ⚠️ Đọc trước khi tưởng sprint này gỡ xong Sprint 5

**Nó KHÔNG gỡ §10.2** — và cũng không cần nữa. Sprint media upload không đụng tới clip nhiều giọng, đúng như đã ghi; §10.2 được gỡ riêng bằng `app/content/audio_join.py` (ffmpeg, offline). Lập luận cũ vẫn đúng ở chỗ nó đúng: **không nhà cung cấp lưu trữ nào giải quyết một bài toán sinh file.**

### Phạm vi đã chốt
- [x] Ảnh Part 1 do biên tập viên đưa · Avatar · Audio thu người thật · Ảnh minh hoạ từ vựng
- [x] **Không làm video** — `PLAN.md` không nhắc tới nó ở đâu, và TOEIC L&R không có phần hình động
- [x] Tách nhà cung cấp: **Cloudinary cho ảnh, object store cho audio** — hai loại file này có hình dạng chi phí ngược nhau (ADR-006 §2.2). Sửa 2026-08-10: driver mang tên **giao thức** (`s3`), không mang tên nhà cung cấp — §2.8

### Việc
- [x] `app/core/storage.py` — giao diện driver + driver đĩa local. **Không** đặt trong `app/content/`: code chạy lúc có request mà nằm đó sẽ phá `test_content_isolation`
- [x] Driver Cloudinary (ảnh), chọn bằng cấu hình; thiếu credential thì API **từ chối khởi động** kèm tên biến còn thiếu
- [x] Endpoint xin vé, ghim `public_id` + định dạng + biến đổi đầu vào + hạn dùng ngắn
- [x] Endpoint xác nhận, **có xác minh lại với nhà cung cấp** — không tin lời trình duyệt (ADR-006 §2.3)
- [x] Tước EXIF, chặn SVG, giới hạn cạnh dài ở incoming transformation
- [x] **P1-8 rate limiting**, fail **closed**: Redis là thứ duy nhất đứng giữa một tài khoản và hoá đơn, nên cho qua khi nó hỏng là mất tiền
- [x] `read_dimensions` thuần stdlib — driver local phải điền được `width`/`height` (NOT NULL) mà không kéo Pillow vào runtime
- [x] **Đã chạy thật lên Cloudinary một vòng** và sửa hai lỗi chỉ dịch vụ thật mới bộc lộ (ADR-006 §2.4b, và `image/jpg` không phải MIME hợp lệ)
- [x] Migration `010_avatar` — `user_profile.avatar_storage_key` nullable; ảnh chữ cái đầu vẫn là mặc định và là chỗ rơi về khi ảnh bị gỡ
- [x] Avatar dùng tiền tố khoá **`avatar/`** riêng, và endpoint gắn avatar **từ chối khoá ngoài vùng đó** — thiếu kiểm tra này thì một người trỏ avatar vào ảnh nội dung, và lệnh dọn ảnh mồ côi sau này sẽ xoá mất thứ đang dùng
- [x] Gỡ avatar **không** xoá file đồng bộ: request của người dùng không nên chờ một dịch vụ bên ngoài, và nếu nó lỗi thì hồ sơ giữ ảnh cũ trong khi người dùng đã thấy báo thành công
- [x] ~~Trang `/admin/media` — thư viện ảnh~~ **đã xoá 2026-08-11**: dropdown chọn ảnh hỏng theo số lượng, và chọn nhầm thì khớp thành công. Thay bằng tải lên tại chỗ; ba trường bản quyền vẫn bắt buộc, vẫn hiện ghi công (ADR-004 §4.2)
- [x] `Avatar` nhận `src`; header và trang hồ sơ dùng ảnh thật, thiếu thì rơi về chữ cái đầu
- [x] **Đã chạy thật lên Cloudinary** cả hai luồng (ảnh nội dung + avatar) qua chính các endpoint
- [x] **Driver `s3` (audio)** — một driver cho Supabase / B2 / R2 / DO Spaces / MinIO; nhà cung cấp là `S3_ENDPOINT_URL`, không phải một nhánh `if` trong code (ADR-006 §2.8). Địa chỉ **kiểu đường dẫn** + SigV4, có test ghim: mặc định virtual-host của boto3 hỏng ở Supabase và hiện ra dưới dạng lỗi DNS
- [x] `app/content/push_media.py` — đẩy media sinh sẵn lên object store, chạy lại là no-op, `Cache-Control: immutable`. Audio sinh offline là bài toán **triển khai**, không phải bài toán upload (§2.8a)
- [x] `verify()` **xoá** object quá cỡ thay vì chỉ từ chối — presigned PUT không ghim được dung lượng (§2.8b)
- [x] Chạy thật một vòng lên Supabase — Cloudinary đã chạy thật rồi, đường S3 thì chưa
- [ ] Cron ping giữ project Supabase khỏi tự ngủ sau 7 ngày (§2.8 — kiểu hỏng là *chỉ audio 404*)
- [x] Lệnh đối chiếu file mồ côi — `app/content/reconcile_media.py` (§10.4 giờ tốn tiền hàng tháng)

---

## 5. Sprint 5 — TOEIC Practice

**Mục tiêu:** luyện theo part và làm đề đầy đủ, có điểm quy đổi.

### Schema đã sửa cho khớp thiết kế (2026-08-10) — migration `011_mock_test`

Đối chiếu `planning/capture-screen/*.png` với `ADR-001` cho ra **một chặn cứng và năm chỗ thiếu**.

**Chặn cứng: `ck_attempt_mode_fields` cấm đúng thứ giao diện cho phép.** Ràng buộc cũ buộc chọn giữa "cả một đề" (`test_id`, `part` NULL) và "một part rời không thuộc đề nào" (`part`, `test_id` NULL). Màn chọn phần muốn làm sinh ra tổ hợp thứ ba — **một đề, một TẬP part** — và tổ hợp đó bị database từ chối. Không sửa thì tính năng không lưu được.

- [x] `attempt.test_id` thành **NOT NULL** — luyện theo part giờ là "đề này, những part ấy", nên vẫn giữ liên kết tới đề, thứ mô hình cũ đánh mất
- [x] Bỏ `mode`/`part`; thêm `scope` ('full'/'partial') + bảng `attempt_part`. `scope='full'` thì bảng part **rỗng**, không phải chứa đủ bảy hàng — liệt kê đủ bảy sẽ làm một đề rút gọn sau này trông giống hệt một lượt làm cả đề
- [x] `review_mode` ('exam'/'practice') là **trục thứ hai**: phạm vi trả lời "làm phần nào", cái này trả lời "có được xem đáp án khi đang làm không"
- [x] `status` + `elapsed_seconds` + `resumed_at` cho tạm dừng. Thời gian **cộng dồn**, không tính bằng `now() - started_at`: lượt làm tạm dừng được, nên đồng hồ treo tường sẽ ăn mất thời gian người học không ngồi trước màn hình
- [x] CHECK `(status IN ('submitted','expired')) = (submitted_at IS NOT NULL)` — hai cột nói cùng một chuyện thì không được nói khác nhau
- [x] `attempt_item.flagged` cho nút "Đánh dấu"
- [x] Bảng `test_collection` cho "bộ đề" (màn hình 1–2), `practice_test.collection_id` **nullable** để đề lẻ vẫn tồn tại được

**Phần khớp sẵn, không phải sửa gì:** Part 1 (ảnh + 4 đáp án, không chữ), Part 2 (audio từng câu, 3 đáp án), Part 3/4 (một audio cho cụm), Part 6/7 (`passage`/`passage_2`/`passage_3`), đánh số 1–200 qua `practice_test_question.position`.

**Một chỗ cố ý KHÔNG sao chép:** trang tham khảo hiển thị đoạn văn Part 6/7 bằng **ảnh scan**. Giữ nguyên `ADR-005` — ngữ liệu là **văn bản**. Ảnh chữ thì trình đọc màn hình không đọc được, không phóng to trên điện thoại, không tìm kiếm được, và AI Coach ở Sprint 7 không trích dẫn lại được. Trang kia dùng ảnh vì họ scan đề gốc — mà đề gốc thuộc bản quyền ETS, đúng thứ `question.source` sinh ra để chặn.

### ⛔ Chặn phải gỡ trước, không phải sau

**~~Đường ống audio không sinh được clip nhiều giọng~~ — ĐÃ GỠ 2026-08-10** (`MEDIA-PIPELINE` §10.2). Spec có thêm dạng `{"turns": [...], "gap_ms": N}`, `conversation_source_hash` băm cả danh sách lượt, `app/content/audio_join.py` ghép bằng ffmpeg. Đã sinh thật 3 câu Part 2 và 2 hội thoại Part 3.

| Part | Cần | Hiện tại |
|---|---|---|
| 1 | 1 giọng đọc 4 câu | ✅ |
| 4 | 1 giọng độc thoại | ✅ |
| 2 | câu hỏi 1 giọng + 3 đáp giọng khác | ❌ |
| 3 | hội thoại 2–3 giọng | ❌ |

Part 3 là part đông câu nhất (39 câu). Gỡ được thì cần một bước ghép audio, mà repo **cố ý** không có `ffmpeg`. Đây là quyết định cần ra **trước** khi bắt đầu Sprint 5, không phải khi phát hiện Part 2 không sinh nổi audio.

**Việc nhập câu hỏi còn nợ từ Sprint 3** (parser + màn dán + trường `source` không pre-select) làm cùng sprint này — không có nó thì không có đề để test bằng gì ngoài fixture.

### Soạn đề — lượt 1: Part 5, 6, 7 (ADR-007) · ✅ backend xong 2026-08-10
- [x] Migration `012` — `practice_test_question.number`, tách khỏi `position`. `attempt.py` đọc cột này thay cho `enumerate(start=1)`, nên luyện riêng Part 5 hiện **101–130** chứ không phải 1–30
- [x] `suggest_numbers` + `PART_NUMBER_RANGES` — gợi ý theo khoảng chuẩn, **ném lỗi** khi tràn part thay vì đè sang part sau
- [x] `parse_reading_part` — định dạng khối `[NGỮ LIỆU]` / `[CÂU]`; nhiều `[NGỮ LIỆU]` liền nhau là bài đọc đôi/ba của **một** cụm, không phải nhiều cụm
- [x] `source` không có mặc định ở bất kỳ tầng nào; trình dán từ chối cả lô nếu thiếu (ADR-007 §2.5)
- [x] 8 endpoint quản trị: tạo đề, dán/xem trước, ghi, liệt kê câu, xuất bản câu, xuất bản đề — tất cả đã có mặt trong bảng `ADMIN_CALLS` khẳng định learner nhận 403
- [x] **Cổng chặn hai tầng**: câu không publish được khi `validate_question` còn báo lỗi; đề không publish được khi còn câu nháp, và lời từ chối **nêu đúng số câu**
- [x] Đã chạy thật: tạo đề → dán Part 7 → ghi (số 147, 148) → publish bị từ chối 409 → publish từng câu → publish đề 200. Đề nháp trả 404 cho người học
- [x] **Màn quản trị `/admin/tests`** — danh sách + tạo đề, và `/admin/tests/[slug]` với thanh part, ô dán, xem trước theo cụm, ghi, xuất bản từng câu và xuất bản đề
- [x] Part 1–4 **hiện ra nhưng khoá**, kèm `title` nói vì sao — giấu đi thì người soạn tưởng đề chỉ có ba phần và đó là thiết kế
- [x] Placeholder của ô dán là một ví dụ đúng định dạng cho từng part: định dạng khối chỉ dạy được bằng cách cho xem
- [x] Đã chạy thật trong trình duyệt: tạo đề → dán (một câu thiếu `nguồn:`) → xem trước bắt lỗi và **giấu nút Ghi** → sửa → ghi (số 101, 102) → xuất bản từng câu → xuất bản đề

- [x] **Tầng bộ đề** — `GET/POST /admin/test-collections`, `POST /{slug}/publish`, và `PATCH /admin/tests/{slug}` để chuyển đề vào bộ hoặc gỡ ra. Thiếu tầng này thì đề tạo ra là đề mồ côi, và người học không có đường nào tới nó
- [x] Cổng chặn thành **ba bậc**: câu → đề → bộ đề. Bộ đề không xuất bản được khi chưa có đề nào đã xuất bản
- [x] Màn quản trị dựng theo **cây** thay vì danh sách phẳng; đề chưa thuộc bộ nào hiện riêng kèm cảnh báo người học không thấy
- [x] Nút **Chép mẫu** định dạng cho từng part, dùng chính chuỗi đang làm placeholder nên hai bản không thể lệch nhau

- [x] **Ảnh cho ngữ liệu Part 7** — migration `013`, một ảnh cho *mỗi* ô để giữ thứ tự (ADR-007 §2.3c). `alt_text` bắt buộc: ảnh làm ngữ liệu mà thiếu chữ thay ảnh là câu hỏi người dùng máy đọc màn hình không trả lời được
- [x] **Form sửa từng câu** — nửa sau của §2.3: đổi đáp án đúng, sửa lựa chọn, viết giải thích. Sửa một câu đã xuất bản thì nó **quay về nháp**, và giao diện nói trước khi bấm
- [x] Tải ảnh ngữ liệu lên ngay tại ô, kèm dòng nhắc rằng bảng giá và lịch trình nên viết thành văn bản

**Lượt 1 (Part 5, 6, 7) xong.**

### Lượt 2 — Part 1–4 + tải audio lên · 🟢 xong (còn nội dung thật)
- [x] Migration `014` — `audio_script` (JSON lượt nói), `audio_attached_at` và `audio_script_hash` trên cả `question` lẫn `question_set`. Part 1 và 2 không in gì, nên thứ người soạn gõ vào là **lời thoại** và trước đó nó không có chỗ nào để ở
- [x] `parse_listening_part` — `voice:` là công tắc, một ngữ pháp cho cả bốn part. Part 1/2 để lời thoại trên **câu**, Part 3/4 để trên **cụm** (`[SCRIPT]`)
- [x] Tải audio từ trình duyệt qua luồng vé/xác minh (ADR-006 §2.3). **Presigned PUT chạy đúng ngay lần đầu** với Supabase — khác lần Cloudinary, không phải sửa gì
- [x] Ba đường gắn media: audio→câu (Part 1, 2), audio→cụm (Part 3, 4), ảnh→câu (Part 1); mỗi đường từ chối sai part kèm lý do
- [x] Màn quản trị mở khoá Part 1–4, hiện lời thoại cạnh trình phát, chọn accent, chọn ảnh Part 1
- [x] Đã chạy thật: dán Part 3 → ghi → publish **409 "part 3 needs audio on its question_set"** → tải bản thu → gắn → publish 200
- [x] **Sửa được lời thoại.** `PATCH /admin/question-sets/{id}` (Part 3/4) và `audio_script` trên `QuestionEdit` (Part 1/2), kèm ô sửa ngay cạnh trình phát. Sửa lời thoại hạ **cả cụm lẫn các câu của nó** về nháp — cổng xuất bản soát từng câu, nên hạ mỗi cụm sẽ để các câu ở lại trong đề đã phát hành
- [x] **Cảnh báo lệch đổi sang so vân tay** (`audio_script_hash`), không so cặp mốc thời gian. Cách cũ phụ thuộc đồng hồ Python khớp đồng hồ database, và trên SQLite — độ phân giải một giây — sửa ngay sau khi gắn thì im lặng; đã thấy nó fail thật trước khi đổi. Vân tay còn chính xác hơn: sửa dấu phẩy trong phần giải thích không báo oan nữa, và sửa lời thoại **về đúng như cũ** thì cảnh báo tự tắt — đã kiểm trên trình duyệt
- [x] `GET /admin/voices` — danh sách giọng đi qua API thay vì chép sang frontend. Hai bản sao sẽ trôi khỏi nhau và người soạn chọn được một giọng rồi ăn 400 từ chính server vừa gửi dropdown
- [x] Lời từ chối in **ngay dưới nút Lưu**, không chỉ ở băng lỗi đầu trang — cách form cả màn hình thì bấm Lưu rồi thấy không có gì xảy ra. Lưu thất bại **giữ nguyên** bản nháp đang gõ
- [x] Sửa một câu Part 1–4 khi **chưa** gắn bản thu: trước đó `edit_question` soát đủ `validate_question` nên mọi câu Part 1–4 đều "thiếu audio" và không sửa nổi lỗi chính tả cho tới khi đã thu xong — tức là phải thu lại. Nay dùng chung bộ lọc với lúc ghi
- [ ] Nội dung Part 1–4 thật (mới có mẫu demo)
- [x] `app/content/import_media.py` — gắn hàng loạt audio/ảnh có sẵn vào một đề đã dán. Khớp theo số trong tên file, `--dry-run` in bảng khớp, file thừa hoặc ô trống thì **dừng** chứ không nhập một nửa. Ghi `source="uploaded"` nên worker TTS không bao giờ đè lên

### Phân trang · 🟢 xong 2026-08-11
- [x] **Thứ tự toàn phần.** `ORDER BY headword` và `ORDER BY started_at DESC` đều KHÔNG duy nhất, nên với LIMIT/OFFSET một hàng hiện ở hai trang còn hàng khác biến mất — im lặng. Thêm `id` làm khoá phụ. Dictation vốn đã đúng
- [x] `app/schemas/common.py` — `Page[T]`, `count_rows`, `page_of`, và **quy tắc ba nhóm**: có trần trong miền → mảng trần; phình theo nội dung hoặc theo sử dụng → `Page[T]`
- [x] `/attempts` trả `Page[AttemptSummary]`, thêm `offset` (trước đó chỉ có `limit`, tức chỉ cắt cụt chứ không phân trang được)
- [x] 🐞 `total` bị vòng lặp bên dưới gán đè thành số câu của lượt cuối — trả về 1 cho 5 hàng. Đổi tên biến trong vòng lặp thành `asked`
- [x] Nhóm B: `/admin/vocabulary`, `/admin/dictation`, `/admin/dictation/stories`, `/admin/tests` trả `Page[T]`, đều thêm `id` làm khoá phụ. `/admin/dictation` là chỗ thiếu khoá phụ đau nhất — nó sắp theo `difficulty` (số nguyên 1–5) nên gần như mọi hàng đều trùng khoá
- [x] `/learning/vocabulary` và `/learning/dictation` đổi sang `Page[T]`
- [x] `Pager` dùng chung ở `components/ui.tsx` — luôn hiện **vị trí tuyệt đối** ("51–100 trên 342"), tự ẩn khi chỉ có một trang
- [x] 8 nơi gọi ở frontend đã đọc `.items`. **TSC không bắt được thay đổi này**: `apiFetch<T>` nhận kiểu từ nơi gọi chứ không suy ra từ route, nên hợp đồng đổi mà trình biên dịch im lặng — phải đi tìm bằng tay
- [x] Nối `Pager` vào các màn danh sách phẳng: `/admin/vocabulary`, `/admin/dictation`, `/learn/vocabulary`, `/learn/dictation/standalone`
- [x] `/learn/vocabulary` giữ `offset` **trong URL**, cùng chỗ với `topic`. Link chủ đề không mang `offset` nên đổi chủ đề tự về trang đầu — giữ ở state thì đang ở trang 3 của một chủ đề rồi bấm sang chủ đề chỉ có 5 từ sẽ ra danh sách rỗng, trông y như chủ đề đó không có từ nào. Back và F5 cũng đúng theo
- [x] 🐞 `/learn/dictation` đếm câu lẻ bằng `items.length` — con số đó đứng yên ở 50 khi vượt một trang. Đổi sang `total` của máy chủ, và chỉ xin `limit=1` vì trang đó chỉ cần con số
- [x] `/admin/dictation/sections` — ban đầu tôi xếp nhầm vào nhóm "có trần" vì nó trông như một bảng phân loại. Nó không: số phần là chủ đề **nhân** số phần mỗi chủ đề, nên phình theo nội dung. Nay `Page[T]`, kèm `id` làm khoá phụ (`position` và `name` đều không duy nhất)
- [x] **Hai màn dạng cây KHÔNG phân trang**: `/admin/tests` (bộ đề → đề) và cây dictation (chủ đề → phần → bài). Cắt trang một danh sách phẳng rồi gom thành cây sẽ hiện một bộ với 3 trong 8 đề và không nói gì. Chúng xin `limit=200` và **hiện cảnh báo** nếu vẫn không đủ, thay vì lặng lẽ dựng cây khuyết

### Màn kết quả, xem lại bài, lịch sử làm bài · 🟢 xong 2026-08-11
- [x] "Chọn tất cả" ở màn chọn part, đứng cạnh "Bỏ chọn"
- [x] Modal xác nhận nộp bài mang **bốn** con số: đã trả lời, chưa trả lời, đã đánh dấu, thời gian còn. Câu cũ "còn N câu chưa trả lời" giấu mất chuyện người ta đã đánh dấu vài câu để quay lại mà chưa quay lại
- [x] Màn kết quả thay hẳn danh sách câu: đúng/tổng, độ chính xác, bỏ trống, đánh dấu, thời gian đã dùng, và đúng/tổng **theo từng part** — tính từ chính danh sách câu, không cần endpoint thống kê. Điểm quy đổi chỉ hiện khi máy chủ thật sự gửi
- [x] Xem lại từng câu, có bộ lọc **tất cả / câu sai / bỏ trống / đã đánh dấu**, lọc trong part đang mở
- [x] `GET /attempts/{id}/result` — `POST /submit` trả kết quả đúng một lần, nên không có đường đọc lại thì một lần F5 làm điểm biến mất. Dùng chung một hàm dựng với submit
- [x] **`GET /attempts`** + màn `/learn/attempts`. Dev DB có **26 lượt `in_progress`** so với 17 đã nộp — mỗi lượt là một bài đồng hồ vẫn chạy ở máy chủ mà người học không có đường quay lại. Khối "đang làm dở" đặt ở `/learn` vì thế; `/profile` chỉ một dòng link
- [x] Danh sách **không** tự chốt bài quá giờ: `GET /{id}` có làm, nhưng làm thế trong danh sách là một lần mở trang ghi hàng chục hàng vào database
- [x] `correct_count` là NULL khi bài chưa nộp — với bài đang dở, "đúng mấy câu" chính là đáp án
- [x] **Bật lại hiển thị ghi công ảnh.** Hai khối `attribution` đang bị comment trong `HEAD`; CC-BY cho dùng *với điều kiện* ghi công, và ADR-004 §4.2 nói rõ lưu mà không hiện vẫn là vi phạm

### Đóng lỗ đã biết · 🟢 xong 2026-08-11
- [x] **Lọc `question_set.status` phía người học.** `POST /attempts` chỉ lọc câu, nên câu đã xuất bản dưới cụm nháp mang cả ngữ liệu lẫn bản thu của cụm ra ngoài. Dùng `outerjoin` — `set_id` là NULL ở Part 1, 2, 5 nên `join` thường sẽ loại sạch ba part đó khỏi mọi lượt làm bài, hỏng nặng hơn lỗ nó vá. `tests/test_attempts.py` khoá cả hai chiều (file này trước đó **không tồn tại** — API lượt làm bài chưa có test nào)
- [x] **`app/content/reconcile_media.py`** — tìm asset không còn ai trỏ tới. Chỉ báo cáo; `--delete-rows` xoá hàng database, **không** đụng object trên nhà cung cấp. Chạy thật trên dev DB: 39 bản thu + 1 ảnh mồ côi từ các đề probe đã xoá và một lần tải ảnh hỏng
- [ ] Xoá object trên nhà cung cấp — cần liệt kê bucket (S3 làm được, Cloudinary phải qua Admin API riêng), và là thao tác không hoàn tác nên chưa tự động hoá

### Xoá / lưu trữ nội dung đề · 🟢 xong 2026-08-11
- [x] Ba cấp, ba luật khác nhau vì ràng buộc khoá ngoại khác nhau. **Bộ đề là cấp nguy hiểm nhất**: `collection_id` là SET NULL nên xoá không lỗi, không mất dữ liệu, chỉ lặng lẽ cắt đường người học tới từng đề bên trong — chặn khi bộ còn đề. Đề và câu thì database chặn thật (RESTRICT), nên kiểm trước rồi trả 409 chỉ sang `archived`
- [x] Xoá đề phải xoá câu và cụm **bằng tay**: `practice_test_question.test_id` là CASCADE nên hàng liên kết tự mất, còn `question` sống sót và không hiện ở màn quản trị nào nữa. Chỉ xoá câu mà đề này là đề duy nhất dùng nó
- [x] Số câu để lại **chỗ trống**, không dồn — `commit_part` chọn "số chưa dùng trong khoảng", nên ô vừa xoá được lấy lại ở lần dán sau (ADR-007 §2.6)
- [x] Nút Lưu trữ nằm ngay cạnh nút Xoá ở cả ba cấp, và lời từ chối 409 in **trong hộp thoại** kèm nút lưu trữ — băng lỗi chung nằm sau lớp phủ `<dialog>` nên vô hình đúng lúc cần đọc

### 🐞 `done?.(await work())` — báo thành công cho việc chưa xảy ra
- [x] **Optional call ngắt mạch cả đối số.** Khi `done` là `undefined`, `done?.(await work())` bỏ qua luôn việc tính đối số nên `work()` **không bao giờ chạy**, hàm rơi xuống `return null`, và bên gọi được báo thành công. Sửa: `const value = await work(); done?.(value);`
- [x] Chỉ cắn ở lời gọi không truyền `done` — 18/19 chỗ trong màn soạn đề có `done` nên vẫn chạy đúng, đúng một chỗ không: nút **Xoá đề**. Nó báo "đã xoá", chuyển trang, để lại đề nguyên trong database, và **không có request nào trong log server lẫn tab Network**
- [x] `run` sinh đôi ở `admin/tests/page.tsx` viết `await work()` thành câu lệnh riêng — đó là lý do xoá *bộ đề* chạy được còn xoá *đề* thì không. Sự bất đối xứng ấy mới là manh mối
- [x] Đã quét toàn bộ `apps/web` và `packages/shared`: không còn chỗ nào khác dùng mẫu này

### Lượt 3 — sinh audio bằng TTS · 🟢 xong
- [x] `backfill_questions` — lời thoại trên CÂU (Part 1, 2) và trên CỤM (Part 3, 4), băm qua `conversation_source_hash`, ghép bằng ffmpeg. Một lượt nói thì bỏ qua ffmpeg luôn
- [x] **`AudioState.EXTERNAL`** — bản thu tải lên không bao giờ bị ghi đè. Phép kiểm cũ `is not CURRENT` khiến clip tải lên (hash băm id ngẫu nhiên) rơi vào nhánh sinh lại; đã có test và đã xác nhận nó đỏ khi gỡ lá chắn. Lỗi này có thật cho cả vocabulary lẫn dictation, không riêng câu hỏi
- [x] Chuông Redis `POST /admin/media/audio/requests` → **202**, không phải 200: API không sinh audio được. Redis chết vẫn 202, chỉ khác `queued` — vòng quét định kỳ vẫn bắt được việc
- [x] `app/content/tts_worker.py` — chuông ở luồng riêng, vòng quét 300s là cái đảm bảo, một lượt hỏng chỉ thành một dòng log. SIGTERM để `docker stop` không cắt ngang lúc đang ghi manifest
- [x] `docker/worker.Dockerfile` — ảnh RIÊNG có ffmpeg 7.1.5 + extra `content`. Không gộp với ảnh API, để ranh giới A4.1 có hình dạng vật lý thay vì chỉ là quy ước
- [x] Nút "Sinh audio còn thiếu" trong màn soạn đề
- [x] **Đã chạy thật**: dán cụm Part 3 ba lượt nói → bấm chuông → worker thức dậy trong 0s → một clip 15,3s ba giọng → `audio_may_be_stale=False`. Hai cụm có bản thu tải lên: worker không đụng vào
- [x] ~~Chưa lọc `question_set.status`~~ **đã vá 2026-08-11**, xem mục *Đóng lỗ đã biết*. Nguyên văn: `POST /attempts` lọc `Question.status == published` nhưng không lọc trạng thái của cụm, nên một câu đã xuất bản dưới cụm nháp sẽ mang cả ngữ liệu lẫn bản thu của cụm đó ra ngoài. Hôm nay **không với tới được qua API** — `publish_question` kéo cụm lên cùng, `edit_set` hạ cả hai xuống cùng — nhưng đó đúng là cách lỗ rò của cây dictation bắt đầu, và không có gì báo khi nó mở ra

### Backend
- [ ] `GET /api/v1/practice/parts/{part}` — bốc câu hỏi, tôn trọng `question_set` với part 3, 4, 6, 7
- [x] `POST /api/v1/attempts` — mở lượt làm, sinh `attempt_item` cho **toàn bộ** câu được phục vụ. Câu bỏ trống được tạo hàng ngay và chấm là **sai**, không phải bỏ qua: ô trống ở cuối Part 7 là dữ kiện (hết giờ), không phải dữ liệu thiếu
- [x] `PATCH /api/v1/attempts/{id}/questions/{question_id}` — lưu lựa chọn và cờ đánh dấu (khoá theo `question_id`, thứ frontend đã cầm sẵn, không phải `item_id` nội bộ)
- [x] `POST /api/v1/attempts/{id}/submit` — chốt, gọi `score_attempt()`. Hết giờ thì tự chốt ở **request kế tiếp**, không cần tiến trình nền (A2.5 cố ý tránh job queue)
- [x] `GET /api/v1/attempts/{id}` — trạng thái lượt làm. **Không kèm `correct_option_id` khi đang thi** — ngược với dictation, và có lý do: bài thi có điểm, mà điểm nằm lại trong lịch sử người học. Lượt làm của người khác trả **404 chứ không 403**
- [x] `GET /api/v1/test-collections` + `/practice-tests/{slug}` — bộ đề và cấu trúc đề
- [ ] *(Trình nhập nội dung đã chuyển sang Sprint 3 — [`ADR-005`](ADR-005-CONTENT-TOOLING.md). Ba ràng buộc ở `ADR-001` §B4 có hiệu lực từ đó.)*

### Frontend
- [x] **Màn làm bài** (`/learn/attempts/[attemptId]`) — thanh part có badge tiến độ, lưới câu ở thanh bên chia theo part kèm khoảng số, đồng hồ đếm ngược, nút Đánh dấu, nộp bài có xác nhận, và bảng kết quả tại chỗ với đáp án đúng hiện ra sau khi nộp
- [x] Nút "Bắt đầu làm bài" gọi `POST /attempts` rồi chuyển sang màn làm bài
- [x] Đã chạy thật trong trình duyệt: mở đề → chọn đáp án → đánh dấu → đổi part → nộp → xem đáp án
- [x] **Ảnh Part 1** — đã sửa bằng `CloudinaryDriver.upload_file` + `push_media`; ảnh do `images.py` lấy về giờ có đường lên Cloudinary, giữ nguyên `storage_key` nên hàng asset và liên kết câu hỏi không phải đụng tới (ADR-006 §2.8c)
- [x] **Ghi công ảnh hiện ra dưới ảnh** (`ADR-004` §4.2) — `QuestionPublic` trả kèm `image_attribution`/`image_license`. Lưu mà không hiện vẫn là vi phạm CC-BY, và trước hôm nay schema thậm chí không gửi hai trường đó xuống
- [x] Chặn chiều cao ảnh: ảnh dọc đẩy trình phát audio xuống dưới màn hình, ở một phần thi tính bằng giây
- [x] Part 1 hiển thị ảnh + **ghi công** (`ADR-004` §4.2 — lưu attribution mà không hiện ra vẫn là vi phạm CC-BY)
- [x] Part 2 chỉ hiện A/B/C, không hiện chữ
- [x] Part 3, 4, 6, 7 hiện kích thích dùng chung cho cả nhóm câu
- [x] Trang kết quả: điểm từng section, điểm tổng, giải thích từng câu

### Nội dung
- [ ] ≥ 1 đề đầy đủ 200 câu, hoặc ≥ 40 câu mỗi part cho chế độ luyện tập
- [ ] Ảnh Part 1 — chọn thủ công, ghi giấy phép (`ADR-004` §2.1)
- [ ] `question.source` phải điền đúng: **không** sao chép đề ETS thật

### Định nghĩa hoàn thành
Học viên làm hết một đề trong thời gian quy định, nộp bài, nhận điểm quy đổi và xem giải thích từng câu.

---

## 6. Sprint 6 — Hardening & bảo mật

**Phải xong trước Sprint 7.** Đây không phải sprint "dọn dẹp": nó chứa các điều kiện tiên quyết cứng của AI layer.

- [x] **P1-8 Rate limiting** — `/login`, `/register`, `/password`. Bộ cũ khoá theo `user.id` nên không che được `/login`: endpoint đó tồn tại vì chưa có người dùng nào. Thêm `rate_limit_anonymous` khoá theo IP
- [x] `client_ip` đọc hop **cuối** của `X-Forwarded-For`, và `trust_forwarded_for` mặc định **tắt** — tin header khi không có proxy nghĩa là ai cũng tự khai khoá của mình
- [x] Hạn mức nới rộng sau khi e2e phơi ra vấn đề thật: 5 lượt đăng ký/10 phút chặn một lớp học đăng ký cùng lúc trước khi chặn được máy dò (CGNAT). Nay 20 đăng ký, 60 đăng nhập
- [ ] Đếm theo **tài khoản** cho `/login` — chặn được botnet xoay IP, nhưng mở đường khoá tài khoản người khác. Chưa làm, có chủ ý
- [x] **P1-7a** `POST /auth/logout` + `jti` + danh sách thu hồi trên Redis — **xong**
- [ ] **P1-7b** Token sang httpOnly cookie + refresh token — **hoãn có chủ đích, không phải bỏ quên**

  P1-7 ban đầu gộp ba việc vào một, với lý do "token nằm trong `localStorage`".
  Đo lại thì lý do đó không đứng vững, còn *một phần* của nó thì đứng vững —
  nên nó tách làm hai.

  **Vì sao hoãn phần cookie.** Cookie `httpOnly` tồn tại để sống sót qua XSS, và
  bề mặt XSS đo được là gần bằng không: không script bên thứ ba, không CDN,
  không analytics, một chỗ `dangerouslySetInnerHTML` duy nhất render một hằng
  số. Đổi lại, cookie **mang vào CSRF** vì nó tự động gửi kèm. Đó là đổi một rủi
  ro gần bằng không lấy một rủi ro trước đó bằng không, cộng chi phí viết lại
  `apiFetch`, `session.tsx`, mọi nơi gọi và cả e2e.

  **Điều kiện để mở lại:** (1) `SameSite`/`Domain` phụ thuộc vào chuyện API sẽ ở
  cùng site với web hay khác — quyết định bây giờ là quyết định khi chưa có đầu
  vào; (2) refresh token chỉ có nghĩa nếu token chính được rút ngắn, mà rút ngắn
  từ 7 ngày xuống vài giờ là một quyết định về trải nghiệm chứ không phải về bảo
  mật. Việc nào tới trước thì mở lại mục này.

  **Xuất hiện script bên thứ ba nào — analytics, CDN, widget nhúng — thì lập
  luận trên hết hiệu lực ngay**, vì nó dựng lại đúng cái vector đang không có.
- [x] **P1-3** Playwright e2e — 4 spec: đăng ký→khu học, đăng nhập sai, một vòng làm bài (mở đề→trả lời→nộp→kết quả→xem lại + bộ lọc), và lượt đang dở hiện ở `/learn` lẫn `/learn/attempts`. Chạy trên ngăn xếp docker thật, có job CI riêng
- [x] Mỗi spec đã được kiểm **đỏ** trước khi tin: tái hiện lỗi `Page[T]` làm test lượt-đang-dở đỏ, khôi phục thì xanh
- [ ] Test component/unit cho frontend — chưa làm, và có chủ ý: bốn lỗi giao diện của sprint này đều ở CHỖ NỐI, không lỗi nào nằm trong một component đơn lẻ
- [ ] **Bật branch protection** — treo từ Sprint 0, cần quyền admin repo. 13 gate không bắt buộc thì chỉ là gợi ý
- [x] **P2-6** Ảnh API hai tầng, chạy uid 10001, bỏ `gcc` + `libpq-dev`. Hai gói đó chưa bao giờ cần: dependency là `psycopg[binary]`, wheel đã đóng gói sẵn libpq. **510MB → 321MB**. Đã kiểm khởi động thật, nối được Postgres và Redis, alembic chạy được bằng user thường, và luồng `--reload` của compose dev vẫn nguyên
- [x] Ảnh worker cũng bỏ `gcc`/`libpq-dev` (chỉ giữ ffmpeg). Vẫn chạy root **có chủ ý**: nó ghi vào `media/` và `content/` qua bind mount của host, đổi sang user thường là mất quyền ghi vào đúng hai thư mục nó tồn tại để ghi
- [x] **P2-7** Bỏ `|| pnpm install` ở `web.Dockerfile`. Nhánh dự phòng biến một lỗi ồn ào — lockfile lệch `package.json` — thành một lần build im lặng thành công với cây phụ thuộc do máy build tự đoán. `web-entrypoint.sh` đã đúng luật này từ trước; đây là chỗ sót
- [x] Bảng `ai_interaction` (token, chi phí, latency, `request_id`) — migration `015`, dựng **trước** request LLM đầu tiên đúng như §7d. `cached_tokens` tách riêng vì prompt caching tính giá khác và gộp vào thì không đo được nó có hiệu quả không. `cost_usd` là `Numeric(12,6)` chứ không phải float — tiền cộng dồn qua hàng trăm nghìn hàng thì sai số nhị phân tích lại thành con số không khớp hoá đơn. **Không có bảng `ai_usage`**: hạn mức đọc trong request nên thuộc về Redis, báo cáo thì suy ra từ sổ cái này

---

## 7. Sprint 7 — AI Layer

**ADR-003 đã viết** (`planning/ADR-003-AI-LAYER.md`, 2026-08-12). Ba quyết định định hình sprint này:
hai nhà cung cấp định tuyến theo chi phí · embedding mã nguồn mở chạy offline, **`vector(1024)`** ·
**lát cắt mỏng không RAG trước**.

Điều quan trọng nhất trong ADR đó là một sự thật đo được, không phải một lựa chọn: dự án có
**17 câu hỏi có explanation**. Retrieval trên ngần đó không truy hồi được gì, và §7e đòi eval đi
cùng tính năng — nên RAG bị chặn bởi **ngữ liệu**, không phải bởi kỹ thuật. Ngưỡng mở khoá được
ghi thành số ở ADR-003 §3.3: ≥150 câu có explanation, hoặc corpus ngữ pháp riêng ≥200 mục.

- [x] **ADR-003** — hai nhà cung cấp + định tuyến theo chi phí, ngân sách token, chính sách gửi dữ liệu
- [x] Chốt embedding model → **`vector(1024)`** (`bge-m3` / `multilingual-e5-large`, chạy offline trong `app/content/` y như edge-tts). `knowledge_chunk`/`learning_memory` hết bị chặn
- [ ] **Lát cắt mỏng — làm TRƯỚC:** Coach giải thích một câu học viên vừa làm sai, dùng ngữ cảnh có cấu trúc từ database. Mục tiêu không phải ship mà là xác nhận kiến trúc và **đo chi phí thật**
- [ ] Bộ đếm ngân sách token trên Redis, **fail closed** (ngược với bộ giới hạn đăng nhập: ở đây Redis là thứ duy nhất đứng giữa một tài khoản và hoá đơn)
- [ ] Eval harness — **cùng lúc** với endpoint Coach đầu tiên, không phải sau
- [ ] Migration cho `knowledge_chunk`/`learning_memory` — hoãn tới khi làm RAG, vì chưa có gì ghi vào chúng
- [ ] RAG: nguồn corpus, chunking, đánh giá retrieval — **chặn bởi ngữ liệu**, ngưỡng ở ADR-003 §3.3
- [ ] Structured output cho study plan và kết quả chấm
- [ ] AI Coach: giải thích ngữ pháp/từ vựng, phân tích điểm mạnh yếu
- [ ] AI Study Planner
- [ ] Eval harness + tracing — **cùng lúc** với tính năng, không phải sau (§7e)
- [ ] Prompt caching (đòn bẩy chi phí lớn nhất — system prompt và context RAG là phần cố định)

---

## 8. Sprint 8 — Analytics & Production

- [ ] Dashboard tiến độ, Learning Memory
- [ ] `user_progress` (nên là view suy ra từ `attempt`, không phải bảng ghi song song)
- [ ] ~~Cloudflare R2~~ → đã thay bằng driver `s3` ở mục 4d; nhà cung cấp giờ là một biến môi trường (ADR-006 §2.8)
- [ ] Chính sách PII: bài làm của học viên sẽ được gửi sang LLM provider (§7h)
- [ ] Monitoring, deployment

---

## 9. Đã xong

### Sprint 0 — Cầm máu · 2026-08-08
6/6 P0. ESLint crash, `.dockerignore`, đường dẫn `.env`, validator `SECRET_KEY`, parse UUID, race khi register. Chi tiết: `REVIEW-OPUS.md` §3.

### Sprint 1 — Nền móng chất lượng · 2026-08-08
7/10 P1. bcrypt trực tiếp, codegen contract + gate chống drift, `/ready` thật, migration tự chạy, structured logging, mypy strict. Test 1 → 62, gate CI 4 → 13. Chi tiết: `REVIEW-OPUS.md` §4.

### Sprint 2 — Thiết kế dữ liệu · 2026-08-09
Sprint dài nhất và là sprint gỡ toàn bộ chặn của Phase 2.

| Hạng mục | Kết quả |
|---|---|
| Hạ tầng audio | `PHASE2-AUDIO.md` Phần B — `audio_asset`, pipeline offline, manifest, mount `/media`, 16 clip thật đủ 4 accent |
| Data model | `ADR-001-DATA-MODEL.md` + migration `003` — 13 bảng, có SRS |
| Ảnh Part 1 | `ADR-004-IMAGES.md` + `image_asset` — pipeline tải/chuẩn hoá, 3 ảnh CC thật |
| Quy đổi điểm | `score_scale`/`score_conversion` + `app/services/scoring.py` |
| Test | 62 → **191** |

**Bốn lỗi được phát hiện nhờ chạy thật, không phải nhờ đọc code:**

1. `en-AU-WilliamNeural` đã bị Microsoft đổi tên — test `external` bắt được. Vì hash tính trên **tên logic**, sửa một dòng là xong (`PHASE2-AUDIO.md` §A4.3).
2. `alembic/script.py.mako` thiếu trong repo — lệnh `alembic revision --autogenerate` mà `CLAUDE.md` ghi trong mục Commands **chưa bao giờ tạo được file**.
3. **Validator bắt Part 1 phải có `prompt_text`, nhưng Part 1 không in gì ngoài ảnh.** ETS ghi rõ bốn câu mô tả không được in ra. Lỗi này sống sót được **vì** Part 1 chưa dựng nổi — không ai chạm vào phần mình không build được.
4. Wikimedia trả 429 giữa lượt tải 3 ảnh. Lộ ra là một ảnh hỏng làm mất trắng tiến độ cả lượt — đã sửa để giữ phần thành công, và lần chạy sau chỉ làm phần còn thiếu.

---

## 10. Nợ kỹ thuật đang mở

| Mục | Ở đâu | Ghi chú |
|---|---|---|
| **Nội dung vẫn quá mỏng** | `ADR-001` §A6.3 | Vẫn là nút thắt lớn nhất, nhưng đã bớt gắt: **43 từ trên 1 chủ đề** (mục tiêu ≥ 300 trên ≥ 6) và **4 câu dictation**. Công cụ đã xong — chỉ còn việc soạn |
| Rate limiting | P1-8 → **Sprint 6** | Chặn cứng endpoint LLM đầu tiên |
| Token trong `localStorage` | P1-7b → **hoãn có điều kiện** | Bề mặt XSS đo được gần bằng không; cookie mang CSRF vào đổi lại. Phần có thật — đăng xuất không thu hồi — đã xong ở P1-7a |
| Không có test frontend/e2e | P1-3 → **Sprint 6** | 0% coverage phía web. Backend thì 294 test. Revamp giao diện vừa rồi **không có lưới an toàn nào** ngoài typecheck và lint |
| Đổi chính sách giọng không sửa audio cũ | `backfill_audio.voice_for_dictation` | `media_state` cố ý chỉ hỏi "clip có khớp text không". Story thu trước bản sửa vẫn giữ giọng lẫn lộn cho tới khi gỡ liên kết và backfill lại |
| Chưa chọn được giọng cho từng story | `backfill_audio.py` | Giọng suy ra từ `story_id`, nhất quán nhưng admin không chọn được "bài này giọng Anh" |
| Chưa kiểm giao diện ở viewport hẹp | `DESIGN-SYSTEM` §13.3 | Breakpoint đúng trong code, chưa quan sát được ở 360px |
| Branch protection chưa bật | Sprint 0 → **Sprint 6** | Cần quyền admin repo. 13 gate xanh mà không ai bắt buộc thì chỉ là gợi ý |
| `draft` chưa có lối ra cho `question` | `ADR-001` §A4.8 | Từ vựng và dictation **đã có** cổng publish. `question` thì chưa có endpoint nào — Sprint 5 |
| Bản quyền đề ETS | `ADR-005` §2 | `question.source` phải điền đúng ở **từng hàng**. `original` = soạn mới theo cấu trúc; `licensed` = đã thật sự xin phép |
| ~~Audio nhiều giọng bất khả thi~~ ✅ gỡ 2026-08-10 | `MEDIA-PIPELINE` §10.2 | Dạng spec `turns` + ghép bằng ffmpeg ngoài luồng. Part 2 và Part 3 đã có đường ra audio |
| Ảnh không tái tạo được | `MEDIA-PIPELINE` §10.3 | Đầu vào là URL của người khác; `media/` bị gitignore ⇒ với ảnh, thư mục media là **bản sao duy nhất** |
| `attribution` chưa được render ở đâu | `ADR-004` §4.2 · `MEDIA-PIPELINE` §10.10 | Lưu ghi công mà không hiện ra vẫn là vi phạm CC-BY. Chưa có endpoint ảnh nào nên chưa vi phạm — sẽ vi phạm ngay khi Part 1 lên |
| `question_set` không có chỗ chứa ảnh | `MEDIA-PIPELINE` §10.7 | Part 7 đôi khi có biểu đồ/biểu mẫu |
| Không có gì kiểm chứng media còn phục vụ được | `MEDIA-PIPELINE` §10.8 | `/ready` không kiểm media. Sai `AUDIO_PUBLIC_BASE_URL` ⇒ mọi media 404 mà container vẫn healthy |
| `seed` không bao giờ xoá | `MEDIA-PIPELINE` §10.4 | Xoá dòng khỏi manifest ⇒ hàng DB ở lại vĩnh viễn, trỏ tới file không bao giờ được tạo lại |
| Không có đường upload media | `MEDIA-PIPELINE` §10.5 | `AUDIO_SOURCES`/`IMAGE_SOURCES` đã có giá trị `uploaded` — schema hỗ trợ, đường đi chưa xây |
| Bảng quy đổi là **xấp xỉ** | `score_scale.source_note` | Không phải bảng chính thức của ETS. Cần scale riêng cho từng đề trước khi trình bày như điểm ước lượng chính thức |
| Chưa có acceptance criteria cho từng Epic | `REVIEW-OPUS.md` §7c | Mục 3–5 ở trên là bước đầu |

### Đã đóng kể từ lần cập nhật trước

| Mục | Đóng bằng gì |
|---|---|
| ~~Chưa có vai trò người dùng~~ | `users.role` + CHECK, migration `005`, dependency `require_role` |
| ~~Chưa có audit trail cho nội dung~~ | `PublishableMixin` (`created_by`, `published_by`, `published_at`) trên mọi bảng nội dung |
| ~~Audio lệch khỏi text mà không có gì phát hiện~~ | `app/services/media_state.py` + cổng publish. `MEDIA-PIPELINE` §10.1 |
| ~~Volume `node_modules` của `web` không tự cập nhật~~ | `docker/web-entrypoint.sh` chạy `pnpm install --frozen-lockfile` trước dev server, theo đúng khuôn `api-entrypoint.sh`. Đã kiểm bằng cách xoá gói khỏi volume rồi khởi động lại |
| ~~`PLAN.md` §9–§10 là nhật ký lẫn trong spec~~ | Đã chuyển hết vào file này; `PLAN.md` §9 giờ chỉ trỏ sang đây |

---

## 11. Cách cập nhật file này

1. Tick task **ngay khi xong**, đừng để dồn cuối sprint.
2. Sprint kết thúc → gom xuống mục 9 kèm số liệu thật (số test, số migration), không phải mô tả chung chung.
3. **Lỗi phát hiện nhờ chạy thật thì ghi lại** — mục 9 quý ở chỗ đó, không phải ở danh sách tính năng.
4. Quyết định kiến trúc thì viết ADR, **đừng** viết vào đây; ở đây chỉ để link tới.
5. Đổi số liệu ở mục 1 mỗi lần thêm migration hoặc thêm nhóm test.
