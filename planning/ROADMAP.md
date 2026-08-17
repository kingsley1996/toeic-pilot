# TOEIC Pilot — Tiến độ & Lộ trình

> **Đây là file theo dõi duy nhất của dự án.** Sprint, task, trạng thái thật của code — tất cả ở đây.
> Cập nhật **ngay khi** hoàn thành một task, không để dồn.
>
> Các tài liệu khác có vai trò khác và **không** chứa trạng thái sprint:
> `PLAN.md` = spec sản phẩm · `ARCHITECTURE.md` = kiến trúc hiện trạng · `ADR-001` / `PHASE2-AUDIO` (= ADR-002) / `ADR-004` / `ADR-005` = quyết định + lý do · `MEDIA-PIPELINE.md` = media hoạt động thế nào + điểm yếu · `DESIGN-SYSTEM.md` = hệ thống thiết kế giao diện (đã viết, **chưa triển khai**) · `SPEC-LEARNING-HUB.md` = bộ mặc định tạm thời của Learning Hub, dựng để sửa · `REVIEW-OPUS.md` = review kỹ thuật (ảnh chụp 2026-08-08, không cập nhật tiếp)

**Cập nhật lần cuối:** 2026-08-17

---

## 1. Đang ở đâu

| | |
|---|---|
| **Phase hiện tại** | Sprint 3 + 4 chạy đầu-cuối cho **từ vựng và dictation**; dictation đã có cây phân cấp 4 tầng; đang làm **4e — học từ vựng theo chủ đề** |
| **Chặn Phase 2** | **Không còn gì.** Cả hai blocker đã gỡ (audio, data model) |
| **Sprint kế tiếp** | Sprint 5 — TOEIC Practice (kèm phần question của Sprint 3 còn nợ) |
| **Test** | **630 chạy** + 2 `external` deselect mặc định (đo 2026-08-17) |
| **E2E** | 4 file, 11 bài — **7 chạy**, 4 bài trong `vocabulary.spec.ts` tắt cứng chờ CI seed nội dung |
| **Gate CI** | 13, tất cả xanh |
| **Migration** | **26 bản**, mới nhất `026_vocabulary_topic_session`. `alembic check` trên database trắng: không lệch model |
| **Bảng** | 37 |
| **Endpoint** | **128** — 81 admin, 47 còn lại (đếm từ `packages/shared/openapi.json`) |
| **Trang web** | 35 route — trang chủ khu học ở `/dashboard`, `/learn` là redirect |
| **Media** | **2 506** clip audio (hàng `audio_asset`), 10 ảnh |
| **Nội dung trong repo** | **303 từ vựng / 7 chủ đề** (tất cả published), 15 câu dictation |
| **Giao diện** | Design system đã triển khai toàn bộ ([`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md)); 3 route dictation dùng tham số động, còn lại dựng tĩnh |

**Kiểm chứng lại ngày 2026-08-17** (phần từ vựng, xem mục 4e): `pytest` **630 passed / 2 deselected** · `ruff check` + `ruff format --check` (135 file) + `mypy` strict (96 file) sạch · `tsc --noEmit`, `eslint`, `prettier --check` sạch · `pnpm gen:api-types` sinh lại **không drift** · `alembic upgrade head` chạy hết `026` trên database trắng và `alembic check` báo **không lệch model** · Playwright **7 bài chạy, xanh** (4 bài `vocabulary.spec.ts` skip) · gọi thật `vocabulary-topic-sessions`, `recall-check` và `review` grade 6 trên stack đang chạy.

**Kiểm chứng lại toàn bộ ngày 2026-08-09:** `pytest` **294 passed / 2 deselected** — gồm cả 3 test `integration` chạy trên PostgreSQL thật (`tests/test_concurrency.py`, dùng `TEST_DATABASE_URL` trỏ vào database riêng để không làm bẩn dev DB) · `ruff check` sạch · `ruff format --check` 67 file đúng · `mypy` strict 46 file không lỗi · `pnpm lint` sạch · `pnpm build` xanh · `pnpm gen:api-types` sinh lại **không drift** · `alembic upgrade → downgrade → upgrade` sạch tới `008`.

### Điều quan trọng nhất cần biết

**Vòng đời nội dung đã khép kín và chạy thật.** Admin dán từ → lưu ở `draft` → worker sinh audio 4 accent → publish (bị chặn nếu audio thiếu hoặc lệch) → học viên ôn tập bằng flashcard SM-2 và làm dictation. Đã chạy đầu-cuối qua stack Docker, không phải chỉ qua test.

**Dictation có cây phân cấp riêng và chấm ở client.** `dictation_topic → section → story → item`, câu có thứ tự trong bài, tiến độ theo bài. Chấm chạy trong trình duyệt (`apps/web/src/lib/dictation.ts`, bản port từng bước của bộ chấm Python — 20/20 ca kiểm khớp tuyệt đối), server vẫn chấm lại và điểm của server mới là bản được lưu. Giao diện **không hiện phần trăm**: chỉ "đúng rồi / chưa đúng" và "3/6 câu đã xong".

**Đủ nội dung từ vựng để dạy.** Hiện có **303 từ vựng đã xuất bản / 7 chủ đề** (mỗi chủ đề ≥ 40 từ, trộn đủ 5 loại từ), 2 420 hàng `vocabulary_audio` và audio đã đẩy lên object store — bấm nghe là kêu. Phần thiếu còn lại là **50 câu dictation** (đang có 15).

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
Sprint 4e Học từ vựng theo chủ đề 🟡 ĐANG LÀM, chưa commit (mục 4e)
Sprint 4f Trang chủ -> /dashboard  ✅ XONG (mục 4f)
Sprint 4g Sidebar thay nav ngang   ✅ XONG (mục 4g)
Sprint 4h Dashboard khối từ vựng   ✅ XONG (mục 4h)
Sprint 4i Trang giới thiệu         ✅ XONG (mục 4i)
Sprint 4j Chỉnh nền từ admin       ✅ XONG (mục 4j)
Sprint 4k Sửa tia sáng bị giật     ✅ XONG (mục 4k)
Sprint 4l Sao băng + chỉnh tốc độ  ✅ XONG (mục 4l)
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
- [x] **Gộp hai trang hub, sửa lại điều hướng (2026-08-10)** — `/dashboard` và `/learn` cũ làm cùng một việc mà không trang nào bao trùm trang kia: số "cần ôn hôm nay" chỉ có ở `/dashboard`, lối vào "Gõ lại từ" chỉ có ở `/learn`, và `/dashboard` **không nằm trong nav** nên rời khỏi nó một lần là không quay lại được — con số đáng lẽ điều khiển hành vi mỗi ngày lại nằm ở chỗ khó tới nhất. Giờ `/learn` là nhà duy nhất ("Hôm nay"), `/dashboard` chuyển hướng ở server (giữ route vì nó nằm trong bookmark và lịch sử của người đang dùng). Nav đổi từ `Learning Hub · Ôn tập · Dictation` — một lỗi phân loại, vì hai mục sau nằm BÊN TRONG mục đầu — sang ba mục ngang hàng `Hôm nay · Từ vựng · Dictation`. `Ôn tập`/`Gõ lại từ` rời khỏi nav vì chúng là hai **chế độ** của cùng một hàng đợi SM-2: mở cái nào trước thì cái đó tiêu hết hàng đợi của ngày, và cái còn lại hiện "không còn từ nào đến hạn". Logo khi đã đăng nhập trỏ `/learn` thay vì trang giới thiệu — **hai chi tiết cuối đã đảo ngược ngày 2026-08-17, xem mục 4f**; phần gộp hai trang hub và bộ ba mục nav thì giữ nguyên
- [x] **Nội dung Business đầu tiên có thật (2026-08-10)** — 40 từ soạn mới, rải đủ 5 loại từ (noun 13 · verb 11 · adj 8 · adv 4 · phrase 4) vì trắc nghiệm cần ≥ 4 từ **cùng `part_of_speech`** mới sinh nổi distractor. Nhập qua chính API admin (parse 40/40, commit 40 draft), `backfill_audio` sinh **320 clip · 0 lỗi**, rồi publish 40/40. Kiểm danh mục giọng edge-tts **trước** khi chạy hàng loạt, đúng như `CLAUDE.md` dặn — một voice id lỗi thời sẽ hỏng từng clip một giữa chừng
- [x] **Từ vựng có trạng thái thuộc/chưa thuộc + lối vào (2026-08-10)** — `GET /vocabulary-progress` (có auth) và `srs.mastery()`; ba mức `new`/`learning`/`mastered` **suy ra từ `interval_days ≥ 21`**, không phải từ `repetitions` — số lần ôn chỉ tăng nên một từ đã quên vẫn mãi khoe là đã thuộc, còn interval bị lapse kéo về 1 ngày nên tự hạ cấp. Endpoint **riêng** chứ không thêm cột vào `/vocabulary` công khai: với khách chưa đăng nhập thì mọi từ hoá ra `new`, đó là nói dối chứ không phải thiếu dữ liệu. Trang từ vựng thôi là một cuốn từ điển — có thanh "Đã thuộc 0/42", badge từng dòng và nút vào ôn tập
- [x] **Sửa một lỗi accessibility có thật** — viền ô nhập cũ chỉ đạt 1.48 tương phản (WCAG 1.4.11 đòi 3.0), tức gần như vô hình với người thị lực kém. Token `rule-strong` mới đạt 3.09–3.64

### Nội dung — **việc duy nhất còn lại của sprint này**
- [x] Soạn ≥ 300 từ vựng cho ≥ 6 chủ đề — hiện có **303** trên **7** chủ đề (2026-08-16): Business 42 · Office 50 · Marketing 45 · Travel 42 · Finance 42 · Music 41 · Housing 40. File dán lưu trong `apps/api/content/sources/vocabulary_{office,marketing,travel,finance,housing,music}.paste.txt`
- [x] Sinh audio 4 accent × {headword, example} cho toàn bộ số từ đang có — **2 420** hàng `vocabulary_audio` (lượt 2026-08-16 sinh 2 072 clip mới, 8 clip tái sử dụng, 0 lỗi)
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

## 4e. Học từ vựng theo chủ đề · 🟡 ĐANG LÀM (chưa commit tính tới 2026-08-17)

**Mục tiêu:** biến trang từ vựng từ *một cuốn từ điển có nút phát* thành *một chỗ để học*, đi qua từng từ theo chủ đề.

Trước đó chỉ có hai lối vào rời rạc — thẻ lật `/learn/review` (hàng đợi SM-2 toàn cục) và hai minigame ghép/trắc nghiệm. Không lối nào trả lời được câu hỏi thường gặp nhất: *hôm nay học chủ đề Business, học tới từ nào rồi?*

### Schema
- [x] Migration `025_review_log_grade_mastered` — nới `ck_vocabulary_review_log_grade` từ `0..5` lên `0..6`
- [x] Migration `026_vocabulary_topic_session` — bảng `vocabulary_topic_session`, khoá chính `(user_id, topic_id)`, `entry_ids` JSON/JSONB + `position`

**`entry_ids` cố ý KHÔNG phải khoá ngoại.** Nó là *thứ tự học* của một ván, không phải quan hệ. Khoá ngoại vào `vocabulary_entry` sẽ chặn việc gỡ một từ khỏi chủ đề chỉ vì có ai đó đang học dở nó. Đổi lại, id thành mồ côi được — nên phía đọc đối chiếu với hồ từ hiện tại và **xáo lại bàn mới nếu lệch**, thà xáo lại còn hơn nối tiếp một bàn cờ sai.

**`done` suy ra, không lưu.** Nó là `position >= len(entry_ids)`. Một cột lưu song song sẽ lệch khỏi cặp `(entry_ids, position)` ngay lần ghi đầu tiên quên cập nhật cả hai — cùng lý do đã ghi cho `StoryProgress` và `VocabularyProgress`.

### Backend
- [x] `GET` / `PUT /api/v1/vocabulary-topic-sessions/{topic_id}` — upsert bàn cờ theo `(user, topic)`, lọc `published`, 404 khi chưa từng lưu
- [x] `POST /api/v1/vocabulary/{id}/recall-check` — máy chấm chính tả, **không ghi lượt ôn nào**
- [x] `srs.GRADE_MASTERED = 6` — bậc "Thành thạo", đặt `interval_days` **cứng** ở `MASTERED_INTERVAL_DAYS`

**Bàn cờ nằm trên máy chủ chứ không phải `localStorage`.** "Học tới đâu" là dữ liệu của người dùng: phải đi theo tài khoản, thấy được trong database, và không bốc hơi khi đổi trình duyệt hay xoá cache. Không suy ra được từ `vocabulary_review_state` — state chỉ biết từ nào *đã* chấm, không biết các từ còn lại xếp hàng theo thứ tự nào.

**Grade 6 là lần duy nhất điểm không đo TRÍ NHỚ mà đo một QUYẾT ĐỊNH.** Học viên khẳng định "thuộc rồi", và engine tôn trọng bằng cách nhảy thẳng lên mốc đã-thuộc thay vì bắt chờ ba tuần — nên interval đặt cứng ở ngưỡng chứ không nhân với hệ số cũ. Ease vẫn đi công thức chuẩn (tính như `GRADE_EASY`), và vẫn tính là một lượt pass.

**`recall-check` tách khỏi `recall` vì nếu không thì một từ bị tính điểm hai lần trong một lượt.** Máy chỉ làm phần nó giỏi — kiểm tra gõ đúng không — rồi trả đáp án thật; mức độ nhớ do học viên tự chấm ở năm nút, ghi qua `/review`. Endpoint này **không đòi đăng nhập** vì nó không ghi gì, và từ đã xuất bản vốn công khai ở `GET /vocabulary/{id}`.

### Frontend
- [x] `_games.tsx` — gom `MatchGame`/`QuizGame` từ hai trang minigame về một chỗ, thêm `TopicSession`
- [x] Trang cuốn sách hai cột: danh sách chủ đề bên trái, ba module (Gõ từ · Thẻ lật · Trắc nghiệm) qua tabs bên phải, kèm thanh tiến độ đọc lại từ máy chủ sau mỗi lượt chấm
- [x] Thẻ lật xoay 3D quanh trục Y, nghĩa nằm trên mặt sau — không mọc thêm nội dung bên dưới

**Ba module dùng CHUNG một bàn cờ, và bàn cờ thuộc về chủ đề chứ không thuộc về tab.** Chuyển gõ từ → thẻ lật là đổi *cách tương tác* với cùng một từ, không phải bắt đầu lại. Vì bàn cờ nằm trên máy chủ, chuyện này đúng cả khi component bị dựng lại.

### Ba lỗi tiềm ẩn đã sửa (2026-08-17)
- [x] **Lượt ghi bàn cờ bắn song song có thể lưu lùi một từ.** Mỗi `PUT` ghi đè toàn bộ `position`; chấm nhanh bằng phím 1–5 là hai request cách nhau vài chục mili-giây, và nếu cái `position=4` về sau cái `position=5` thì bản ghi cuối *vẫn hợp lệ, chỉ là sai*, không có gì báo. Các lượt ghi giờ nối đuôi nhau qua một hàng đợi promise
- [x] **Nhiễu trắc nghiệm trùng nghĩa.** Hai từ khác nhau vẫn dịch ra cùng một tiếng Việt (trong kho: "quảng cáo", "thường xuyên"), nên lọc nhiễu theo id mà không lọc theo nghĩa sinh ra hai ô chữ y hệt — chỉ một ô được tô đúng, kèm cảnh báo `key` trùng của React. Gộp về `buildOptions` dùng chung cho cả hai màn trắc nghiệm
- [x] **Thẻ lật đọc lộ đáp án cho trình đọc màn hình.** `backface-visibility` chỉ giấu khỏi *mắt*; mặt sau vẫn nằm trong cây accessibility nên người dùng screen reader nghe thấy nghĩa **trước khi** được hỏi có nhớ nghĩa không — mất luôn bài tập. Dùng `inert` trên mặt đang quay đi: che khỏi cây a11y, khoá tương tác, **và** tự đẩy focus ra. `aria-hidden` không làm hai việc sau, và đặt nó lên chính cái nút vừa bấm còn là vi phạm ARIA

### Test
- [x] 6 test backend mới (`test_learning_api.py`, `test_services.py`) — round-trip bàn cờ, tách theo học viên, từ chối topic nháp và `position` vượt mảng, đòi đăng nhập, grade 6 lên thẳng đã-thuộc, `recall-check` không ghi gì
- [x] `e2e/vocabulary-learn.spec.ts` — 2 bài, **đếm request thật** thay vì tin con số trên màn hình

**Bài e2e tự bỏ qua theo điều kiện lúc chạy**, chứ không tắt cứng như `vocabulary.spec.ts`: nó hỏi API xem có chủ đề nào ≥ 4 từ không, có thì chạy thật, không thì bỏ qua kèm lý do nói rõ thiếu gì. Một bài bị tắt cứng thì không bao giờ chạy lại, kể cả sau khi CI đã seed được dữ liệu.

### Đã gây lại lỗi để xem test có đỏ không — và hai lần nó không đỏ
Gây lại 4 lỗi, chỉ 2 làm test đỏ. Hai lần còn lại đã sửa **bài test** thay vì tự khen:

- **Cho `key` của component kèm theo tab** (tức dựng lại mỗi lần đổi tab) — **vẫn xanh**, vì bàn cờ nằm trên máy chủ nên lần dựng lại đọc về đúng chỗ cũ. Bài test kiểm *hành vi* "không mất chỗ", không kiểm cơ chế nào tạo ra nó; cái làm nó đỏ thật là đặt lại `index` khi `mode` đổi. Đã ghi lại đúng như vậy trong docstring của file.
- **Bỏ lọc nhiễu theo nghĩa, chạy 3 lượt** — **xanh cả ba**. Nhiễu bốc 3 trong hơn 40 từ, nên dù hồ từ có cặp trùng nghĩa thì xác suất cả cặp rơi vào một câu chỉ vài phần nghìn. Đã **xoá** khẳng định "các đáp án phải khác nhau": một dòng gần như không bao giờ đỏ là chi phí không đổi lấy gì. Quy tắc đó sống bằng lập luận viết tại `buildOptions`

### Còn lại
- [ ] Chạy `alembic upgrade head` trên môi trường thật (mới chỉ chạy trên database trắng và trên stack dev)
- [ ] Bàn cờ ghép từ (`MatchGame`) hiện không có lối vào từ trang chủ đề — vẫn tới được qua `/learn/vocabulary/match/{slug}`. Nó ghép **nhiều từ cùng lúc** nên không nhét vào luồng năm nút được; muốn bày lại thì cho nó một tab riêng, đừng ép qua `TopicSession`
- [ ] Hồ từ tải với `limit=200`. Chủ đề lớn nhất hiện có 50 từ nên chưa chạm trần, nhưng vượt 200 thì ván chỉ gồm 200 từ đầu và **không có gì nói ra điều đó** — đúng loại lỗi mà luật "màn hình dựng cây thì hiện thông báo khi `total` vượt số trả về" đã viết cho chỗ khác

---

## 4f. Trang chủ về `/dashboard`, logo về landing · ✅ XONG (2026-08-17)

**Đảo ngược hai chi tiết** của quyết định 2026-08-10 ở mục 4 (theo yêu cầu). Phần gộp hai trang hub và bộ ba mục nav ngang hàng **không** đổi.

- [x] Trang chủ khu học chuyển từ `/learn` sang **`/dashboard`**; `/learn` giữ lại làm redirect ở server
- [x] Logo **luôn** trỏ `/`, kể cả khi đã đăng nhập
- [x] `NavItem.covers` — mục nav nhận thêm những đường dẫn thuộc về nó mà không nằm dưới `href`

**Chỉ trang hub đổi; các trang con giữ nguyên `/learn/**`.** `/learn/vocabulary`, `/learn/dictation`, `/learn/tests`, `/learn/review`, `/learn/typing`, `/learn/attempts` không đụng tới. Lý do là hai cái tên mô tả hai thứ khác nhau: trang hub là một *bảng điều khiển* nên `dashboard` gọi đúng nó, còn các trang con thật sự là *nơi học* nên `/learn/...` mới đúng. Đổi cả cây sẽ phải sửa hơn 30 file và làm hỏng mọi URL người dùng đã bookmark, để đổi lấy một cái tên tệ hơn (`/dashboard/vocabulary`).

**`/learn` là redirect chứ không phải 404** — đúng cái lý do `/dashboard` từng được giữ lại hồi tháng 8: đó là địa chỉ đăng nhập đẩy tới suốt nhiều sprint nên nó nằm trong lịch sử và bookmark. Lần này mũi tên chỉ quay đầu.

### Một thứ suýt hỏng im lặng
`activeHref` khớp theo **tiền tố của `href`**. Khi trang chủ còn ở `/learn`, ba trang `/learn/review`, `/learn/typing`, `/learn/attempts` tự động làm sáng mục "Hôm nay" vì chúng nằm dưới `/learn/`. Chuyển sang `/dashboard` là quy tắc tiền tố **không còn với tới chúng**: mở "Ôn tập" thì cả thanh nav tắt đèn, người dùng mất dấu mình đang ở đâu — và trang thì vẫn đúng nên không ai gọi đó là lỗi. `NavItem.covers` bắc cầu chỗ đó; `covers` chỉ để so khớp, `activeHref` vẫn trả về `href`.

### Kiểm
- [x] Hai khẳng định mới trong `e2e/auth.spec.ts`: logo có `href="/"`, và "Hôm nay" giữ `aria-current="page"` cả trên `/dashboard` lẫn `/learn/review`
- [x] **Đã gây lại cả hai lỗi và cả hai đều đỏ** — trả logo về `/dashboard` khi đã đăng nhập → đỏ ở khẳng định logo; bỏ `covers` → đỏ ở `aria-current` (`Expected: "page" · Received: ""`)
- [x] `curl` trên stack đang chạy: `/dashboard` → 200, `/learn` → **307 → `/dashboard`**, `/learn/vocabulary` → 200
- [x] Playwright 7 bài xanh · `tsc`, `eslint`, `prettier` sạch

---

## 4g. Sidebar thay cho thanh nav ngang · ✅ XONG (2026-08-17)

- [x] `components/shell.tsx` — `SidebarShell` + `TopBarShell`, dùng chung cho **cả** khu học lẫn khu quản trị
- [x] Mọi trang trong ứng dụng đổi sang sidebar trái cố định: bộ mục + danh tính + đăng xuất
- [x] Ba trang **ngoài** ứng dụng (`/`, `/login`, `/register`) giữ thanh trên như cũ, kể cả menu tài khoản
- [x] `admin-shell.tsx` bỏ layout riêng, chuyển sang dùng `SidebarShell` với bộ mục của nó

**Chọn khung theo ĐƯỜNG DẪN, không theo trạng thái phiên.** Phiên chỉ phân giải được sau khi JS chạy, nên chọn theo nó sẽ dựng một khung rồi đổi sang khung kia ngay trước mắt người dùng — biến thể layout của cái bẫy ba-trạng-thái. Ba trang dùng thanh trên là ba trang đứng ngoài ứng dụng: trang giới thiệu nói chuyện với người chưa có tài khoản, còn `/login` và `/register` là cánh cửa vào.

**Hai khung gộp làm một, hai BỘ MỤC thì không.** `links` là tham số. Trộn bộ mục của học viên với của biên tập viên sẽ xoá mất ranh giới giữa *đang học* và *đang sửa nội dung người khác sẽ học*. Đây cũng là chỗ `DESIGN-SYSTEM.md` §9.7 phải viết lại: trước đây "có sidebar hay không" chính là tín hiệu phân biệt hai khu, giờ tín hiệu chuyển sang **nội dung** của sidebar.

**Danh tính và đăng xuất rời khỏi menu xổ.** Sidebar có sẵn chiều cao cho hai dòng nhìn thấy được; header cao 4rem thì không, và đó mới là lý do bản cũ phải giấu chúng sau một cú bấm. `SessionControls`/`UserMenu` vẫn còn — nhưng chỉ cho ba trang thanh trên: bỏ hẳn thì người đã đăng nhập đứng ở trang giới thiệu không còn lối nào xem hồ sơ hay đăng xuất.

### Hai lỗi chỉ lộ ra khi nhìn ảnh chụp
Test xanh hết, còn cả hai lỗi dưới đây thì không test nào bắt được — chúng được tìm ra bằng cách chụp màn hình thật ở 1280px và 390px rồi nhìn:

- **Tên và email in trùng nhau.** `display_name` là nullable và phần lớn tài khoản chưa đặt, nên `name ?? email` rồi in thêm dòng `email` cho ra **cùng một chuỗi hai lần**. Menu xổ cũ giấu được chuyện này vì nó chỉ mở khi được bấm; sidebar thì hiện thường trực, và ở đó nó trông như lỗi dữ liệu. Dòng email giờ chỉ hiện khi có tên hiển thị riêng.
- **Khối tài khoản thiếu `shrink-0`.** Trong flex column nó có thể bị co lại khi bộ mục dài; giờ vùng mục là phần `flex-1` tự cuộn, còn khối tài khoản khoá cứng ở đáy.

Cộng thêm một chi tiết thừa: trong `/admin/**`, sidebar vẫn hiện "Quản trị nội dung" trỏ về chính nơi đang đứng — đã ẩn khi đang ở trong khu đó.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch · Playwright **7 bài xanh**
- [x] Ảnh chụp thật ở 1280×860 và 390×780: `/dashboard`, `/learn/vocabulary`, `/` (thanh trên, không đổi), `/admin/ai/skill-tags` (mục con lồng vẫn đúng), và ngăn kéo mobile đóng/mở
- [x] `e2e/auth.spec.ts` sửa theo: đăng xuất giờ là nút ở đáy sidebar, không còn là mục trong menu xổ

---

## 4h. Dashboard — khối từ vựng dựng lại · ✅ XONG (2026-08-17)

Dựng theo ảnh mẫu ở [`improve-ui/`](improve-ui/): hai cột — trái là **Thống kê học tập** (lưới 2×2 số liệu + lối vào ôn tập), phải là **Trạng thái từ vựng** (thanh xếp chồng ba mức + số từng mức + tổng). Thay cho ô "Cần ôn hôm nay" một-con-số-to và ô "Từ vựng" nhỏ trước đây.

### Ba phần của ảnh mẫu KHÔNG dựng, ba lý do khác nhau
- **Đấu trường từ vựng** — tính năng chưa tồn tại. Không phải chuyện giao diện, nên không có gì để dựng.
- **Độ chính xác (93%)** — **dữ liệu không có**. `vocabulary_review_log` có ghi `grade` nên tỉ lệ nhớ được là *tính được*, nhưng không endpoint nào trả nó về. Dựng ô đó bằng một con số suy từ thứ khác sẽ cho một tỉ lệ trông như đo được mà không đo gì cả. Ô thứ tư dùng **chuỗi ngày** — số liệu thật, đã có sẵn trong `LearningStats`. Mở khoá bằng cách thêm `reviews_correct` vào `gather_stats`.

### "Tiếp tục học" — dựng sau, cùng endpoint của nó
Ban đầu bỏ qua vì thiếu dữ liệu, rồi làm nốt: thêm **`GET /api/v1/vocabulary-topic-sessions`** liệt kê ván học của chính học viên, mới động vào trước.

- Mảng trần chứ không `Page[T]`: số ván của MỘT học viên bị chặn trên bởi số chủ đề đã xuất bản, vì khoá chính là `(user, topic)` — nhóm (A) của `schemas/common.py`.
- **Không trả `entry_ids`.** Danh sách đó dài bằng cả chủ đề (40–50 id) và chỉ có ích cho màn đang học; nhét vào để hiện một dòng "3/41 từ" là gửi vài nghìn ký tự cho một con số.
- **Lọc `published` ở chủ đề**, và **outer join** sang cuốn sách: `topic.collection_item_id` nullable nên chủ đề chưa xếp vẫn có ván hợp lệ, và inner join sẽ nuốt mất chúng.
- Trang cuốn sách nhận thêm **`?topic=<slug>`**. Không có nó thì "Học tiếp" dẫn về cuốn sách rồi mở chủ đề ĐẦU TIÊN — ném học viên ra khỏi đúng chỗ họ vừa rời đi. Slug lạc (chủ đề đã chuyển sách, link cũ) rơi về chủ đề đầu tiên chứ không để trang trống.
- Khối này **chỉ hiện khi thật sự có ván dở**; không có thì biến mất hẳn, chứ không rơi về "tuyển tập đầu tiên".

Đã chạy thật đầu-cuối trên stack dev: học dở 3 từ của chủ đề **thứ hai** trong cuốn sách → dashboard hiện "600 từ vựng thiết yếu cho TOEIC · Music · 3/41 từ" → bấm Học tiếp → về đúng chủ đề Music, đúng từ 4/41 (không phải Business, chủ đề đầu danh sách).

### Hai chỗ lệch khỏi ảnh mẫu, có chủ đích
- **Huy hiệu icon VUÔNG bo 4px**, không tròn. Bán kính 4px là ngôn ngữ của cả hệ và thang Tailwind đã bị thay, nên một `rounded-full` ở đây sẽ là ngoại lệ duy nhất trong toàn bộ giao diện.
- **Không dùng gradient.** Ảnh mẫu tô gradient tím–hồng cho nút đấu trường; hệ này không có gradient nào và §6.3 nói độ nổi đến từ cấu trúc chứ không từ trang trí.

### Hai lỗi chỉ lộ ra khi nhìn số thật
Cả hai đều không có test nào bắt được — tìm ra bằng cách chụp màn hình một tài khoản mới và một tài khoản đã chấm vài từ:

- **Thanh xếp chồng nuốt mất phần nhỏ.** Với kho 303 từ, 2 từ đã thuộc là 0.66% — làm tròn xuống thành **không pixel nào**, nên thanh nói "chưa thuộc gì cả" trong khi con số ngay dưới nó nói 2. Phần khác 0 giờ có `minWidth: 3px`: ba pixel không đọc được tỉ lệ, nhưng đúng ở chỗ quan trọng hơn — có hay không có.
- **Số 0 vẫn bị tô màu.** Một "0" màu xanh lá dưới nhãn "Đã thuộc" đọc như thể có gì đó đã xong. Màu chỉ đặt khi số khác 0.

### Kiểm
- [x] `pytest` **631 passed** (1 test mới cho endpoint liệt kê) · `tsc`, `eslint`, `prettier` sạch · `gen:api-types` không drift · Playwright **7 bài xanh**
- [x] Ảnh chụp thật ở 1280×900 và 390px, cho **hai** trạng thái: tài khoản mới tinh (mọi số bằng 0) và tài khoản đã chấm 6 từ (303 tổng · 297/4/2 · chuỗi 1 ngày)

---

## 4i. Trang giới thiệu dựng lại · ✅ XONG (2026-08-17)

- [x] Nền lưới kỹ thuật — ban đầu chỉ sau hero, sau đó **mở ra toàn khung** kèm tia sáng chạy dọc cạnh lưới (`.grid-backdrop` + `.grid-spark`), xem [`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md) §9.7b
- [x] Nội dung sắp lại theo **ba khu học có thật**: Từ vựng · Dictation · Luyện đề, đúng ba mục của thanh điều hướng
- [x] Thêm mục **lịch ôn năm bậc**, bày đúng dãy nút học viên thật sự bấm
- [x] Số từ và số chủ đề **đọc từ máy chủ**, không viết cứng

**Trang giới thiệu mô tả một cấu trúc khác với cấu trúc thật là dạy sai người dùng ngay trước khi họ bước vào.** Bản cũ chỉ nói về dictation — hero, bốn giọng, và một vòng ba bước toàn là nghe-gõ — trong khi phần có nhiều nội dung nhất giờ là từ vựng (303 từ / 7 chủ đề) và luồng làm đề đã chạy đầu-cuối.

**Số liệu đọc từ `total`, không phải tổng `entry_count`.** `vocabulary_topic` là quan hệ nhiều-nhiều, nên cộng `entry_count` của các chủ đề là đếm *lượt thuộc chủ đề*: một từ xếp vào hai chủ đề sẽ được cộng hai lần và trang khoe nhiều từ hơn số thật. Bản đầu tiên của tôi mắc đúng lỗi này (302 thay vì 303, và chỉ trùng khớp vì tình cờ có một từ chưa xếp chủ đề). Viết cứng con số thì tệ hơn nữa — nó đúng đúng một lần rồi sai mãi mà không gì báo, y như bảng số liệu ở mục 1 từng lệch cả chục migration.

**Một khẳng định sai đã bị bắt trước khi lên trang.** Bản nháp viết "Từ vựng và dictation cùng chạy trên một bộ lịch ôn, nên học bên nào cũng làm bên kia vơi đi". Sai: chỉ **từ vựng** chạy SM-2; dictation đếm câu đã hoàn thành và **không có ngày đến hạn**. Câu đúng cho hai chế độ *thẻ lật* và *gõ lại* — chúng dùng chung một hàng đợi — chứ không cho hai khu. Gộp cho gọn ở đây là hứa một cơ chế không tồn tại.

**Dòng hiện trạng cập nhật.** Câu cũ nói "phần luyện đề TOEIC đầy đủ chưa mở"; nay luồng làm bài chạy đủ (mở đề → trả lời → nộp → chấm → xem lại từng câu), nên thứ còn thiếu là **nội dung** chứ không phải tính năng — hiện 2 đề / 55 câu, và 6 câu dictation đã xuất bản.

**Lưới mở ra toàn khung, và điều đó lật ngược lập luận tôi vừa viết.** Bản đầu giới hạn lưới ở riêng trang giới thiệu vì "một lưới sau bảng điểm là nhiễu thị giác trên đúng thứ người dùng đang cố đọc". Chủ dự án quyết định ngược lại. Lập luận cũ không bị vứt đi mà đổi thành **ràng buộc về cường độ**: alpha hạ xuống 0.5, và mọi tham số của tia (chu kỳ lẻ nhau, lệch pha, đặt theo số ô) tồn tại để giữ nền dưới ngưỡng cạnh tranh với chữ. §9.7b ghi lại cả quyết định lẫn cái giá của nó thay vì để tài liệu mâu thuẫn với code.

**Hai nơi cố ý không có nền này:** màn làm bài (dùng `bareLayout`, và một vệt sáng chuyển động sau lưng người đang tính giờ là thứ duy nhất cạnh tranh trực tiếp với sự tập trung), và người bật `prefers-reduced-motion` — tia bị **tắt hẳn** chứ không rút thời lượng về 0.01ms, vì với `iteration-count: 1` nó sẽ đứng lại ở cuối đường thành một vệt sáng bất động giữa màn hình.

**Lưới riêng của trang giới thiệu đã gỡ.** Giữ cả hai sẽ chồng hai bộ đường kẻ lệch pha lên nhau — trông như lỗi render chứ không như một lưới đậm hơn.

**Chỉnh theo phản hồi, ba lượt.** (1) Ô lưới **32px** thay vì 64px, alpha hạ 0.5 → 0.4 để lưới dày hơn mà không nặng hơn. (2) Còn hai tia, cả hai đều dọc. (3) Tia đổi hẳn thành **chạy vòng theo cạnh lưới** — phải, xuống, trái, lên — bằng `offset-path`, cộng thêm **đốm sáng thỉnh thoảng loé** ở giao điểm lưới.

**Số tia, số đốm và màu sửa được từ `/admin/appearance`** (mục 4j).

### Hai lỗi thời gian, cả hai chỉ lộ ra khi ĐO chứ không khi đọc code
- **Tia đứng yên trong suốt `animation-delay`.** Chưa chạy thì phần tử giữ style thường của nó (nằm ở gốc, chưa vào đường dẫn), nên tia có `delay: 8s` **đứng bất động tám giây** rồi mới chạy — trông đúng như một vạch sáng bị kẹt. `animation-fill-mode: backwards` bắt nó nhận khung hình đầu tiên ngay từ đầu. Lộ ra vì hai ảnh chụp liên tiếp thấy một vạch bất động ở **cùng một chỗ**, mà một tia đang chạy thì không thể như vậy.
- **Hai trong năm đốm chưa hề sáng sau 20 giây.** Đỉnh sáng ban đầu đặt ở 94% chu kỳ, nên lần loé ĐẦU TIÊN của mỗi đốm bị lùi gần trọn một chu kỳ. Dời đỉnh về 6% cho cùng một kết quả nhìn thấy nhưng đốm sống ngay sau `delay`. Không bắt được bằng ảnh chụp — phải lấy mẫu `opacity` của từng đốm trong 20 giây rồi so đỉnh; sau khi sửa cả năm đều đạt 0.85.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch · Playwright **7 bài xanh**
- [x] `CSS.supports("offset-path", …)` hỏi thẳng trình duyệt thay vì đoán; hộp bao của tia đo được đúng `y = 96px` = hàng 3 × 32px, tức nó nằm trên đường kẻ chứ không cạnh đường kẻ
- [x] Ảnh chụp bốn mốc thời gian: tia đi hết cạnh trên, xuống cạnh phải, rồi ngược lại cạnh dưới — vòng khép kín

---

## 4j. Chỉnh nền lưới từ khu quản trị · ✅ XONG (2026-08-17)

- [x] Migration `027_backdrop_setting` — bảng một hàng, `CHECK (id = 1)`
- [x] `GET /api/v1/backdrop` (**công khai**) và `PUT /api/v1/admin/backdrop` (`require_role`)
- [x] Trang `/admin/appearance`: số tia, số đốm, màu, và công tắc tắt chuyển động
- [x] 4 test mới (`tests/test_appearance.py`)

**Một hàng duy nhất, do DATABASE bảo đảm.** `CHECK (id = 1)` chứ không phải quy ước "nhớ đừng chèn hàng thứ hai" — hàng thứ hai sẽ xuất hiện vào đúng ngày ai đó viết một script seed, và từ đó `LIMIT 1` trả về cái nào là chuyện của thứ tự vật lý. Không lỗi, chỉ sai.

**Đường đọc KHÔNG đòi đăng nhập.** Bắt xác thực ở đây làm khách chưa đăng nhập rơi về nền mặc định, tức cấu hình vừa đặt không áp cho đúng nhóm nhìn thấy trang nhiều nhất. Cấu hình này không phải bí mật — nó mô tả thứ ai cũng nhìn thấy.

**Không lưu toạ độ, chỉ lưu SỐ LƯỢNG.** Vị trí sinh từ một bảng cố định trong `shell.tsx`; một toạ độ lưu sẵn phải hợp lệ với mọi kích thước màn hình, mà lúc lưu thì không có màn hình nào để kiểm.

**Màu là TÊN TOKEN, không phải mã hex.** Mỗi token có sẵn giá trị cho nền sáng và nền tối, nên đổi màu vẫn giữ nguyên lời hứa tương phản. Một ô nhập hex hỏng đúng ở chỗ không ai thử: người chỉnh ở chế độ sáng chọn một màu đẹp, cùng màu đó chìm nghỉm hoặc chói gắt trên nền tối, và không gì báo vì nó vẫn là một màu hợp lệ.

**Ba thứ cố ý KHÔNG cho chỉnh:** cỡ ô, alpha và mask. Chúng được canh theo cỡ chữ và khoảng cách panel (§9.7b), nên một thanh trượt lên chúng là thanh trượt lên khả năng đọc của mọi trang phía sau.

**Hai bộ mặc định phải khớp nhau.** `BACKDROP_DEFAULTS` phía máy chủ và `BACKDROP_FALLBACK` phía giao diện: lệch nhau thì trang nhấp nháy đổi hình một lần ngay sau khi tải xong, và không có gì báo. Migration chèn sẵn hàng id=1 nên đường đọc công khai (không có quyền ghi) không bao giờ phải rơi về giá trị cứng.

### Kiểm
- [x] `pytest` **635 passed** · `ruff`, `mypy` sạch · `alembic upgrade head` + `alembic check` trên database trắng: không lệch model
- [x] `tsc`, `eslint`, `prettier` sạch · `gen:api-types` không drift · Playwright **7 bài xanh**
- [x] **Chạy thật qua chính UI**: đăng nhập admin → đổi 5 tia / 10 đốm / màu `accent-au` → bấm Save → `GET /backdrop` trả đúng giá trị mới → mở `/dashboard` và đếm DOM: **5 `.grid-spark`, 10 `.grid-twinkle`, `--spark-color` = `49 185 166`** (đúng giá trị tối của `accent-au`)

---

## 4k. Tia sáng bị giật — nguyên nhân và cách sửa · ✅ XONG (2026-08-17)

Phản hồi: *"các tia sáng chuyển động không mượt, bị giật và có khi đứng"*. Hai nguyên nhân độc lập, và **cả hai chỉ tìm ra bằng cách đo**.

### 1. Animation chạy sai luồng
`offset-path` + `offset-distance` là cách gọn nhất để cho một phần tử chạy vòng theo đường, và nó **không hợp thành được**. Chrome chỉ hợp thành `transform`, `opacity`, `filter`; `offsetDistance` chạy ở main thread, nên tia khựng theo đúng mọi việc JS đang làm — chính là triệu chứng "có khi đứng". Kiểm bằng `getAnimations()[0].effect.getKeyframes()`: trước là `offsetDistance`, sau là `transform`.

Bốn cạnh giờ nằm trong một bộ keyframes `translate() rotate()`, góc bẻ bằng hai keyframe cách nhau 0.2%. Kéo theo một ràng buộc mới: đường đi phải là **hình vuông**, vì phần trăm trong keyframes là hằng số nên bốn cạnh chia đều thời gian.

### 2. Tia đi chậm hơn một pixel mỗi khung hình
Đây mới là phần bất ngờ. Sau khi chuyển sang `transform`, đo được **60fps, không rơi khung nào** — mà vẫn không mượt. Con số giải thích: **0.538 px/khung**. Một vệt dày 1px nhích nửa pixel mỗi khung thì khử răng cưa phân bổ lại độ sáng giữa hai hàng pixel ở mỗi khung, và mắt đọc ra là rung. Chu kỳ rút lại để tốc độ quanh **1 px/khung** — đo lại: 0.975 và 1.012.

Luật rút ra, đã ghi vào §9.7b: **muốn tia chậm hơn thì phải làm nó dày hơn, không phải kéo dài chu kỳ.**

### Hai phép đo SAI, ghi lại để không lặp
Cả hai đều "chạy được" và đều cho kết luận vô nghĩa:
- **`getBoundingClientRect()` trước/sau khi chặn main thread.** Trong một tác vụ đồng bộ không có lần tính lại style nào, nên hai lần đọc luôn bằng nhau — bất kể animation chạy ở đâu. Nó trả `false` cho *cả* bản cũ lẫn bản mới.
- **Chụp màn hình trong lúc chặn main thread.** `Page.captureScreenshot` cũng phải qua main thread, nên hai ảnh chỉ được chụp *sau* khi hết chặn, ở hai thời điểm khác nhau → luôn khác nhau. Cũng cho `true` cho cả hai bản.

Thứ kiểm được thật là **tên thuộc tính đang được animate** (một sự thật đọc trực tiếp từ API) và **số px mỗi khung hình** (một đại lượng nói đúng cái mắt nhìn thấy).

---

## 4l. Sao băng + chỉnh tốc độ · ✅ XONG (2026-08-17)

- [x] Tia chạy vòng theo cạnh lưới → **sao băng** lao chéo qua khung rồi tắt
- [x] Migration `028_backdrop_speed` — `speed_percent`, hệ số 25–300%
- [x] `/admin/appearance` thêm ô **Speed**; hệ số áp cho cả sao băng lẫn đốm sáng

**Tốc độ là HỆ SỐ phần trăm, không phải số giây.** Mỗi vệt có chu kỳ gốc riêng, cố ý lẻ nhau để chúng không rơi vào một nhịp đều đặn — thứ mắt bắt được và bắt đầu theo dõi. Một ô nhập "số giây" sẽ san phẳng đúng đặc tính đó. Hệ số giữ nguyên tỉ lệ giữa chúng. Số càng lớn càng **nhanh** (chu kỳ bị chia), nên cột tên là `speed` chứ không phải `duration`.

**Sàn 25% không tuỳ tiện:** dưới nữa thì vệt đi chậm tới mức rung thay vì trôi (§9.7b, luật px-mỗi-khung). Chỉnh chậm quá không cho ra hiệu ứng êm hơn mà cho ra hiệu ứng hỏng — nên nó bị chặn ở tầng schema chứ không để người dùng tự phát hiện.

**Sao băng dùng hai lớp lồng nhau:** lớp ngoài chỉ xoay (đặt hướng rơi), lớp trong chỉ trượt. Gộp vào một `transform` cũng chạy, nhưng khi đó mỗi keyframe phải lặp lại góc xoay, và cái bị quên khi đổi góc là keyframe cuối — vệt sẽ xoay từ từ trong lúc rơi. Quãng đường tính bằng `vmax` chứ không phải pixel: số pixel đủ dài trên laptop sẽ hụt trên màn rộng, vệt tắt giữa trời.

### Một lần vấp đúng cái bẫy đã ghi sẵn trong CLAUDE.md
Thêm cột `speed_percent` xong thì `/backdrop` trả **500**: `column backdrop_setting.speed_percent does not exist`. Dev DB ở revision `026` trong khi `create_all` (chạy mỗi lần container `--reload`) đã dựng sẵn bảng `backdrop_setting` **thiếu cột mới** — `create_all` tạo được bảng mới nhưng không thêm được cột vào bảng đã có. Chạy `alembic upgrade` thẳng sẽ chết ở "relation already exists". Cách đúng đã có sẵn trong tài liệu: **dừng `api`, drop bảng do `create_all` dựng, rồi để Alembic chạy**, xong mới bật lại.

### Kiểm
- [x] `pytest` **635 passed** · `ruff`, `mypy` sạch · `alembic upgrade head` + `alembic check` trên database trắng: không lệch model
- [x] `tsc`, `eslint`, `prettier` sạch · `gen:api-types` không drift · Playwright **7 bài xanh**
- [x] **Chạy thật qua chính UI**: đổi 4 sao băng + tốc độ 2x → `--meteor-duration` đo được **5.50s** (đúng một nửa của 11s gốc), DOM dựng đúng 4 vệt, thuộc tính animate là `["transform","opacity"]`, và tốc độ khi bay là **17–32 px/khung** — trên ngưỡng rung rất xa
- [x] Chụp được đúng khoảnh khắc **hai vệt đang bay**: đầu sáng, đuôi mờ, hướng chéo xuống phải

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
- [x] **Lát A — bộ khung** (`app/services/llm/`, `app/core/ai_budget.py`, migration `016`). Không SDK của nhà cung cấp nào: `httpx` đã có sẵn, và ADR-003 §3.1 chốt bộ định tuyến là một hàm chọn tầng chứ không phải tầng trừu tượng hoá SDK — dùng httpx thẳng là cách giữ đúng lời đó mà không thêm gì vào ảnh production
  - sổ cái ghi bằng **phiên làm việc riêng**: tiền đã tiêu là sự thật đã xảy ra, ghi chung phiên thì một lỗi ở bước sau cuốn luôn bản ghi chi phí đi — hoá đơn vẫn tới nhưng sổ không có dòng nào. Có test đỏ khi đổi sang dùng chung phiên
  - hạn mức **fail closed**, kiểm đỏ bằng cách cho nó fail open
  - `refused` và `error` đều được ghi thành hàng: chỉ ghi lượt thành công thì tỉ lệ hỏng của nhà cung cấp bằng 0 trong mọi báo cáo, và không biết hạn mức đang cắn ai
  - model lạ thì `cost_usd` **ném lỗi** chứ không ghi 0 (N4, giống `scoring.py`)
  - prompt là tệp có phiên bản, phiên bản là **hash nội dung** chứ không phải số tự tăng — số tự tăng thì có ngày ai đó sửa mà quên tăng
- [x] **Lát B — bộ nhãn câu hỏi** (`app/services/labels.py`, `app/models/labels.py`, migration `019`, `/admin/ai/skill-tags`)
  - phân loại thật ở `planning/toeic_question_label_taxonomy.md`: **72 mã, 6 mặt**. Một câu Part 6 mang ba nhãn cùng lúc, nên cột vô hướng `question.skill_tag` không chứa nổi — đã bỏ hẳn. Thêm nữa `PART_1_PERSON_AND_OBJECT_DESCRIPTION` dài 36 ký tự, tràn `String(32)`
  - module nhãn **sinh từ tài liệu**, và `tests/test_labels.py` đọc lại tài liệu để so từng mã. Thiếu nó thì một nhãn thêm vào tài liệu mà quên sinh lại vừa "đã được quyết" vừa "bị hệ thống từ chối"
  - khoá chính `(chủ_thể, facet)` **thi hành** luật đúng-một-nhãn-mỗi-mặt; bốn mặt ngữ liệu chung nằm ở `question_set_label` vì ba câu của một hội thoại Part 3 luôn cùng chủ đề
  - ba phép kiểm ở mọi đường ghi, vì ba kiểu sai đều im lặng: mã bịa, mã sai mặt (ghi đè nhãn khác qua khoá chính), mã sai part (`GRAMMAR_NOUN` có ở Part 5, không có ở Part 6)
  - **nút "Xác nhận đúng" là bắt buộc**: `onChange` chỉ nổ khi giá trị đổi, nên không có nó thì mọi lượt kiểm đều là lượt sửa và KPI độ đúng vĩnh viễn 0% — chính thứ màn hình đó sinh ra để đo
  - **Ollama chạy tại máy** thay OpenRouter free: tier miễn phí cho 50 lượt/ngày, không đủ cho một lượt 40 câu. `LLMQuotaExhausted` tách khỏi 429 quá tải tạm thời
- [ ] **Chạy đủ nhãn cho toàn bộ ngữ liệu** — mới 2 câu và 8 nhóm có nhãn từ lượt kiểm thử
- [ ] **Viết lại `AI-ENGINEERING-PLAN` §9b** — các ngưỡng ở đó (nhãn nhỏ nhất ≥5%, lớn nhất ≤30%, `khac` <5%) hiệu chỉnh cho bộ 8 nhãn tạm và **không còn khớp mã**: với 72 mã thì mọi mã dưới 5%. Mã đã chuyển sang đo độ đúng **theo từng mặt**; tài liệu thì chưa
- [ ] **Lát C — Coach:** Coach giải thích một câu học viên vừa làm sai, dùng ngữ cảnh có cấu trúc từ database. Mục tiêu không phải ship mà là xác nhận kiến trúc và **đo chi phí thật**
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
