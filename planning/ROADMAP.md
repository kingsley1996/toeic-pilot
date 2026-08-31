# TOEIC Pilot — Tiến độ & Lộ trình

> **Đây là file theo dõi duy nhất của dự án.** Sprint, task, trạng thái thật của code — tất cả ở đây.
> Cập nhật **ngay khi** hoàn thành một task, không để dồn.
>
> Các tài liệu khác có vai trò khác và **không** chứa trạng thái sprint:
> `PLAN.md` = spec sản phẩm · `ARCHITECTURE.md` = kiến trúc hiện trạng · `ADR-001` … `ADR-008` (`PHASE2-AUDIO` = ADR-002) = quyết định + lý do · `MEDIA-PIPELINE.md` = media hoạt động thế nào + điểm yếu · `DESIGN-SYSTEM.md` = hệ thống thiết kế giao diện, **đã triển khai toàn bộ `apps/web`** · `SPEC-LEARNING-HUB.md` và `SPEC-AI-COACH.md` = bộ mặc định tạm thời, dựng để sửa · `toeic_question_label_taxonomy.md` = bảng nhãn câu hỏi, **sửa tay và là nguồn sự thật** · `import_media.md` = runbook gắn media vào đề đã dán · `USER-ROAD.md` = level/badge/XP/daily task — **lát 1 và 2 đã dựng** (mục 4v), badge và khung avatar chưa · `REVIEW-OPUS.md` và `qwen3p8-review.md` = hai bản review kỹ thuật, **ảnh chụp theo ngày, không cập nhật tiếp**

**Cập nhật lần cuối:** 2026-08-21

---

## 1. Đang ở đâu

Số liệu dưới đây **đo trên `main` ngày 2026-08-21**, không phải ước lượng.

| | |
|---|---|
| **Trạng thái** | Từ vựng, dictation và luyện đề chạy đầu-cuối trên nội dung thật. Lớp AI đã gắn nhãn câu hỏi và sinh giải thích. Còn thiếu: **RAG** (chặn bởi nội dung, xem `ADR-003` §3.3) |
| **Test API** | **683 chạy** + 2 `external` deselect mặc định |
| **E2E** | 7 tệp, **18 bài** — 14 chạy, 4 bài `vocabulary.spec.ts` tắt cứng chờ CI seed nội dung |
| **Gate CI** | 4 job (`api`, `web`, `contract`, `docker`), tất cả xanh. Branch protection **chưa bật** |
| **Migration** | **34 bản**, mới nhất `034_user_identity` |
| **Bảng** | **46** (đo từ `Base.metadata`) |
| **Endpoint** | **148 thao tác HTTP trên 120 đường dẫn** — 95 admin, 53 còn lại (đếm từ `packages/shared/openapi.json`) |
| **Trang web** | **38 route** — trang chủ khu học ở `/dashboard`, `/learn` là redirect |
| **Media** | **2 506** clip audio (`audio_asset`), 10 ảnh |
| **Nội dung** | **303 từ vựng / 7 chủ đề**, 15 câu dictation, 55 câu hỏi (34 có giải thích), 2 đề luyện |
| **Người dùng** | **33 tài khoản thật**, 7 trong đó có hoạt động. `users` có 574 hàng nhưng **541 là tài khoản e2e** (email mang dấu thời gian 13 chữ số) — lọc chúng ra trước khi đếm bất cứ thống kê người dùng nào |
| **Giao diện** | Design system triển khai toàn bộ ([`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md)) |

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

## 4m. Petland — góc thú cưng · ✅ XONG (2026-08-18)

- [x] `assets/mascots/dino/` — 48 khung hình rời (5 hoạt ảnh), là bản GỐC, không nằm trong `public/`
- [x] `scripts/png.mjs` — giải mã/mã hoá PNG 8-bit RGBA bằng `zlib` của Node, không thêm phụ thuộc
- [x] `scripts/pack-dino.mjs` — gộp thành 5 dải ngang, ô **165×117**, 6.0MB → **440KB**
- [x] `scripts/check-dino-fit.mjs` — kiểm bằng số rằng mọi khung hình nằm trọn trong sân
- [x] `components/petland.tsx` — mở từ nút góc dưới trái, đi/chạy/nhảy/ngủ, tự đi dạo rồi tự ngủ
- [x] `e2e/petland.spec.ts` — đo chuyển động thật trong trình duyệt thật

**Bộ ảnh này khác hẳn ba tấm sprite sheet trước, và khác ở đúng chỗ quan trọng: nó đã được căn chỉnh sẵn.** Cả 48 khung hình nằm trên cùng canvas 680×472, và đáy của tư thế đứng cố định ở y=422 trong **cả mười** khung hình. Nên cách xử lý đúng là cắt **một** hình chữ nhật chung cho mọi khung hình — giữ nguyên căn chỉnh của hoạ sĩ. Cắt sát hộp bao của *từng* khung hình (thứ bộ sheet trước bắt buộc phải làm, vì nó không có căn chỉnh nào để giữ) là đúng nguyên nhân lỗi "nhảy lên thì pet nhỏ đi".

**Ba con số trong `petland.tsx` do máy đo, không chọn bằng mắt, và cả ba hỏng im lặng:**

- `FOOT_Y = 105` — bàn chân của tư thế đứng nằm ở hàng 105 của ô chứ không ở đáy ô, vì khung cắt chung phải chừa chỗ cho tư thế nằm vốn thấp hơn. Vẽ ô sát mặt đất làm con thú lơ lửng 12px; vì **mọi** hoạt ảnh lệch giống nhau nên nó trông như một lựa chọn bố cục.
- `ANCHOR_X = 47` — ô rộng 165 nhưng tư thế đứng chỉ chiếm x 1..93. Lật quanh tâm *ô* đẩy con thú ngang 70px mỗi lần đổi hướng, nên `transform-origin` phải đặt ở tâm *con thú*.
- `MIN_X = 64` — tư thế chạy và nhảy vươn tới x=111, nên khi quay trái cái đuôi thò ra 64px về bên trái điểm neo. `check-petland-fit.mjs` bắt được: ở `MIN_X = 50` nó báo `run` và `jump` tràn mép trái đúng 14px.

**Một vòng lặp, không phải hai.** Bản trước tách `requestAnimationFrame` cho vị trí và `setInterval` cho khung hình, và đó là nguồn của cảm giác giật: hai đồng hồ trôi khỏi nhau nên chân bước và thân dịch không khớp pha. Giờ cùng một vòng, và mọi chuyển động tính theo **giây** chứ không theo khung hình. Cung nhảy là parabol theo thời gian, không phải tích phân trọng lực — nhờ vậy thời gian bay cố định và khung hình nhảy bám đúng cung thay vì trôi theo tải máy.

**`Dead` được đổi tên thành `sleep`.** Bộ khung hình là con thú ngả xuống rồi nhắm mắt, không có gì chết chóc — và một con thú học tập thì không chết. Nó luôn nằm quay mặt sang phải, vì tư thế này đổ người *về phía trước* và quay trái thì đổ ra ngoài mép sân.

**Petland KHÔNG gọi API.** Chưa có hạt giống, độ đói hay cấp độ nên chưa có bảng nào phía máy chủ; phần nuôi thú gắn với hoạt động học vẫn còn để ngỏ. Nó cũng vắng mặt ở màn làm bài — nhánh `bareLayout` — vì một con thú nhảy nhót cạnh người đang tính giờ làm bài là thứ cạnh tranh trực tiếp với sự tập trung.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch
- [x] `check-petland-fit.mjs`: 48/48 khung hình nằm trong sân ở **cả hai hướng** và ở đỉnh cú nhảy; bàn chân tư thế đứng khớp `FOOT_Y`
- [x] **Thấy nó đỏ trước khi tin nó xanh** — `e2e/petland.spec.ts` đỏ đúng ba lần khi cho hỏng lại ba khuyết điểm: `idle` không đổi khung hình, giữ phím mà không chuyển sang bước đi, và cú nhảy không rời mặt đất. Xanh lại sau khi phục hồi.

**Một phép đo phải bỏ đi vì nó vô hiệu.** Đo qua DevTools trong một tab ở nền cho ra "đứng yên" ở mọi mẫu — nhưng đó là vì `visibilityState === "hidden"` làm trình duyệt **dừng** `requestAnimationFrame`, chứ không phải vì code sai. Cùng loại với hai kỹ thuật đo đã phải loại ở §4k. Kết luận chỉ rút ra được từ Playwright, nơi trang thực sự được vẽ.

---

## 4n. Petland — bối cảnh khu trại · ✅ XONG (2026-08-18)

- [x] `assets/landscape/petland-1.png` — bản GỐC 2.0MB, ngoài `public/`
- [x] `public/landscape/petland-1.jpg` — bản chạy, **348KB**
- [x] `components/petland-scene.ts` — đường đi 11 điểm neo, `pointAt()` nội suy
- [x] `components/petland.tsx` — camera bám con thú, phối cảnh, ánh sáng theo vị trí
- [x] `scripts/check-petland-fit.mjs --debug` — kiểm bằng số **và** vẽ ra để nhìn
- [x] `png.mjs` đọc thêm PNG kiểu RGB (ảnh chụp của Playwright)

**Bức tranh KHÔNG phải pixel art, dù nó vẽ ra pixel art.** Đo được: 178.821 màu, và không cỡ khối nào từ 2 tới 8 px cho tỉ lệ cạnh-nằm-đúng-lưới cao hơn mức ngẫu nhiên — tức không có lưới pixel nào cả. Tỉ lệ bước màu mượt/gắt là 8.4:1. Hai hệ quả ngược chiều nhau: `image-rendering: pixelated` sẽ **phá** nó, và không có hệ số phóng nguyên nào phải tôn trọng; nhưng con khủng long cũng là art tô mượt, nên hai bên **không lệch phong cách** như tưởng ban đầu. Ảnh cũng **đục 100%**, nên JPEG là đúng định dạng: 2.0MB → 348KB mà không mất gì.

**Ống nhòm, không phải cả bức tranh.** Tỉ lệ trong tranh là thật — đống lửa cao ~110px, cửa gỗ ~90px — nên một con thú "thuộc về" cảnh này phải cao 60–80px, đúng cỡ tự nhiên của bộ sprite. Thu nhỏ bức tranh cho vừa khung góc màn hình thì con thú cũng phải nhỏ theo và thành một vệt 40px. Nên khung là **cửa sổ 420×250 trượt theo con thú**, cộng một nút xem toàn cảnh ở đúng 50% (cả bức vừa khít, không phải kẹp camera).

**Mặt đất không phẳng, nên vị trí con thú là MỘT số chứ không phải hai.** Khu trại thấp bên trái, mặt cầu cao hơn 130px và ở xa hơn, bờ phải lại thấp xuống. Cho con thú đi ngang theo một `y` cố định là cho nó lội qua sông ở nửa quãng đường. Đường đi là một chuỗi điểm neo mang `x`, `y` (chỗ **bàn chân** chạm đất) và `scale`; vị trí là quãng đường đã đi dọc đường đó. Nội suy **tuyến tính** chứ không trơn: Catmull-Rom đẹp hơn nhưng vọt ra ngoài điểm neo ở chỗ gấp khúc, tức con thú lượn ra khỏi mặt đất đã đo — đúng thứ đường đi này sinh ra để ngăn.

**Ảnh gỡ lỗi bắt được thứ con số không bắt được.** Bộ kiểm báo xanh — con thú nằm trọn trong khung ở mọi mẫu — trong khi ba điểm neo đặt mặt cầu **thấp hơn thực tế 20px và dốc ngược chiều**, và điểm neo cuối đặt bàn chân **vào trong lòng máng nước**. Một đường đi lọt trong khung vẫn có thể đi thẳng qua giữa lòng sông. Phải phóng 3x kèm lưới đo mới đọc đúng: cây cầu là hình **thang** (dốc lên 481 → phẳng 463 → dốc xuống 483), và ở cỡ thật thì mặt cầu với gầm cầu chỉ cách nhau vài pixel.

**Ánh sáng phải theo vị trí, không thể là một bộ lọc cố định.** Con thú được vẽ dưới ánh sáng ban ngày còn cảnh là đêm, nên không chỉnh gì thì nó nổi lên như hình dán. Nhưng mức đủ tối cho khúc cầu dưới trăng làm con thú cạnh đống lửa trông như trong bóng râm. `lightingAt()` nội suy theo khoảng cách tới đống lửa; `hue-rotate` đổi dấu làm việc nặng nhất — dương đẩy xanh lá về vàng, âm đẩy về xanh lục lam.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch
- [x] `check-petland-fit.mjs`: 48 khung hình × 241 mẫu dọc đường đi, cả hai hướng, cả đỉnh cú nhảy — không khung nào ra khỏi bức tranh
- [x] **Thấy đỏ trước khi tin xanh**: bỏ phối cảnh (ép `scale` cố định) làm bài kiểm mới đỏ đúng chỗ, phục hồi thì xanh lại
- [x] Chụp thật qua Playwright ở ba chỗ: cạnh lửa, bờ bên kia, và toàn cảnh

**Một lỗi tự giấu mình.** Chốt tránh ghi lại `filter` mỗi khung viết là `Math.abs(spot.x - lastLitX) > 6` với `lastLitX` khởi tạo bằng `NaN` — mọi so sánh với `NaN` đều sai, nên lần ghi **đầu tiên** không bao giờ xảy ra, `filter` mãi rỗng, và toàn bộ phần ánh sáng lặng lẽ không chạy mà không ném lỗi nào. Chỉ lộ ra vì phép kiểm đọc giá trị `filter` thật thay vì tin vào code. Nay so **khoá đã làm tròn**, không có đường nào dẫn tới `NaN`.

---

## 4o. Petland — lớp hạt làm khung cảnh sống · ✅ XONG (2026-08-18)

- [x] `components/petland-fx.ts` — sao nhấp nháy, mặt nước lấp lánh, đốm lửa, đom đóm
- [x] `petland-scene.ts` thêm các vùng `SKY`, `WATER`, `GLOW_ZONES`, `FIRE`
- [x] `check-petland-fit.mjs` kiểm **chất liệu** của từng vùng, và vẽ chúng ra với `--debug`
- [x] `png.mjs` đọc thêm PNG kiểu RGB — ảnh chụp của Playwright là kiểu đó
- [x] `e2e/petland.spec.ts` thêm bài kiểm lớp hạt

**Bức tranh là ảnh phẳng, nên thứ chuyển động phải là một lớp PHỦ.** Muốn chính dòng nước tự chảy thì phải cắt nó thành lớp riêng có kênh trong suốt, tức tô mặt nạ bằng tay cho một vùng mép răng cưa — nhiều việc hơn hẳn, và kết quả cuối vẫn là một vòng lặp vẽ. Một canvas hạt cho gần hết hiệu quả mà không đụng vào tài sản gốc.

**Mỗi hiệu ứng bị nhốt trong vùng đo từ bức tranh.** Một vệt sáng lấp lánh trên bãi cỏ lộ ra ngay là đồ dán thêm, nên `SKY`/`WATER`/`GLOW_ZONES` là toạ độ đo thật, y như `PATH`. Canvas chạy trong **cùng** vòng lặp `requestAnimationFrame` với con thú: hai vòng lặp là hai `dt`, và đốm lửa sẽ trôi lệch pha với con thú mỗi khi máy tải nặng — đúng lỗi đã sửa khi gộp vị trí với khung hình.

**"Nước thì xanh" là luật sai ở đúng chỗ nó cần đúng nhất.** Vũng nước trong tranh gần nửa là vệt phản chiếu màu cam của đống lửa, nên một ô nằm trọn trong lòng nước cũng chỉ đạt ~65% theo luật đó, không phân biệt được với ô đè lên cỏ. Định nghĩa ngược lại thì tách sạch: thứ duy nhất tiếp giáp nước là **cỏ**, và cỏ xanh-lá-trội — đo "không phải xanh lá trội" cho cỏ 61–65%, nước 98–99%. Phép kiểm này bắt được ba ô sai ngay lượt đầu. Giới hạn đã biết: nó không phân biệt nước với **gỗ**, nên một ô đè lên cột cầu vẫn lọt — chỗ đó do ảnh gỡ lỗi phát hiện.

**Bản đồ chênh lệch giữa hai khung hình là thứ trả lời được "cái gì đang động".** Nhìn ảnh tĩnh chỉ kết luận được "hình như không có đốm lửa"; trừ hai khung cho nhau thì thấy ngay chúng có tồn tại nhưng chụm thành một cụm bé nằm gọn **bên trong vầng sáng của chính đống lửa** — vì chúng sinh ra ở vành đá dưới chân (y=548) với lực nâng quá nhỏ. Cho sinh ở ngọn lửa (y≈494–518) và nâng mạnh hơn là xong.

`prefers-reduced-motion` tắt hẳn lớp này. Khối `prefers-reduced-motion` sẵn có ở `globals.css` chỉ với tới CSS animation, không với tới canvas — nên đây là phép kiểm thứ hai, không phải phép kiểm thừa.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch · Playwright **10 xanh, 4 bỏ qua**
- [x] `check-petland-fit.mjs`: 5/5 ô nước và 2/2 ô trời đạt ≥90% đúng chất liệu
- [x] **Thấy đỏ trước khi tin xanh**, hai kiểu hỏng riêng: canvas không vẽ gì (`> 0` nhận 0) và canvas vẽ một lần rồi đứng im (`not 170441`). Hai khẳng định trong bài kiểm đều gánh việc, không cái nào thừa.
- [x] Nhịp khung hình đo bằng Playwright: **16.7ms trung vị** cả khi bảng đóng, mở cửa sổ nhỏ và mở toàn cảnh — không đo được chênh lệch nào

**Những lần đỏ chập chờn gặp trong lúc dựng phần này KHÔNG phải lỗi test.** Chúng là bộ giới hạn tốc độ của `/auth/register` — mỗi bài e2e tự đăng ký một tài khoản, và một buổi làm việc dài thì chạm trần. Triệu chứng đã ghi sẵn trong CLAUDE.md và cách gỡ là xoá khoá `ratelimit:*` trong Redis. `waitForPet` thêm vào để phòng một cuộc đua **có thật** — đọc `transform` trước lần ghi đầu của vòng lặp cho `y = 0` và `scale = 1` — chứ không phải bản vá cho những lần đỏ đó.

---

## 4p. Petland — mặt nước đọc ra là dòng chảy · ✅ XONG (2026-08-18)

- [x] Vệt sáng 34 → **108**, dài 10–56px, dày 1–3px, trôi nhanh gấp đôi, một phần năm mang sắc ấm
- [x] Chọn ô nước theo **diện tích** thay vì đều tay
- [x] Thêm **gợn sóng tròn**, dẹt 0.36 theo chiều dọc vì cảnh nhìn xiên
- [x] `check-petland-fit.mjs` chạy thẳng lớp hạt với một `ctx` giả và đọc từng nét vẽ

**Chỉ tăng số hạt thì vũng lớn vẫn không đậm lên, và lý do nằm ở cách CHỌN ô.** `pick()` đều tay chia đúng số vệt cho mỗi ô nước, nên ô suối trên 58×96 nhận bằng ô vũng chính 340×114 — gấp bảy lần diện tích. Chỗ nhỏ thì sáng rực còn mặt vũng lớn nhất, thứ chiếm gần hết khung hình, lại loãng nhất. Chọn theo diện tích mới cho mật độ đều.

Một vệt sáng đơn lẻ là một tia loé; một dòng chảy là **nhiều** vệt cùng đi một hướng, đủ dày để thành kết cấu. Đó là lý do con số phải nhảy từ 34 lên 108 chứ không phải 50. Tốc độ cũ 3–15 px/giây chậm tới mức mắt đọc thành đứng yên. Gợn sóng tròn là thứ duy nhất trong lớp này nói "đây là **mặt nước**" chứ không phải một bề mặt sáng nào đó.

### Nhốt hạt vào vùng chỉ có nghĩa nếu chúng Ở LẠI trong vùng

Tăng tốc độ lên gấp đôi làm vỡ chính cái luật mà các ô sinh ra để giữ: ở tốc độ mới một vệt đi gần 60px trong đời nó, thừa sức ra khỏi ô và nằm lấp lánh **trên bãi cỏ**. Ảnh chụp chỉ để lộ nó sau khi phóng đúng góc — một vạch trắng ở world x≈1025 trong khi ô nước dừng ở 1000.

Chặn ở vòng vẽ vẫn chưa đủ, và nguyên nhân thật nằm chỗ khác: **`newShimmer` chọn vị trí mà không tính chiều dài của chính vệt đó**. `inRect()` cho một điểm bất kỳ trong ô, kể cả sát mép phải, nên một vệt dài 40px đặt ở đó thò ra 36px ngay từ khung hình đầu. Phép kiểm biên chạy TRƯỚC lần vẽ, nên vệt vừa sinh vẫn kịp được vẽ đúng một khung rồi mới bị thay — một khung ở 60fps là quá nhanh để thấy, nhưng có hơn trăm vệt nên lúc nào cũng có vài cái đang ở đúng khoảnh khắc đó. Cái nhìn thấy được là những vạch sáng nhấp nháy trên cỏ. Nay chọn chiều dài trước, rồi mới chọn chỗ đặt.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch · Playwright **10 xanh, 4 bỏ qua**
- [x] `check-petland-fit.mjs` mô phỏng **30 giây** lớp hạt trong Node với một `ctx` giả: **194.400 vệt + 12.600 gợn sóng**, không nét nào ra khỏi mặt nước
- [x] **Đỏ đúng hai lần, cả hai vì lỗi THẬT**: phép kiểm bắt được vệt lọt ra ở `x=1036 w=40` (ô dừng ở 1040) khi mới viết, và đỏ lại khi gỡ phần chặn vệt trôi — nên cả hai nửa đều gánh việc
- [x] Nhịp khung hình vẫn **16.7ms trung vị** ở cả ba trạng thái, với ~207 hạt

**`ctx` giả ở đây nhỏ đúng bằng phần `petland-fx` dùng tới** — nó chỉ ghi lại các nét, không mô phỏng canvas, và nếu module dùng thêm API mới thì nó ném lỗi chứ không âm thầm bỏ qua. Phân biệt vệt nước với vầng sáng đống lửa bằng việc `fillStyle` là chuỗi hay là gradient. Script phải chép `petland-fx.ts` ra một bản tạm đã đổi alias `@/` thành đường dẫn tương đối **kèm đuôi `.ts`**: alias là của bundler, còn Node ESM thì đòi đuôi file.

---

## 4q. Petland — giao diện tương tác, tách khỏi phần sẽ đổi · ✅ XONG (2026-08-18)

- [x] `components/petland-sprite.ts` — **tệp DUY NHẤT phải sửa khi đổi mascot**
- [x] `components/petland-pet.ts` — nhu cầu và hành động, số học thuần, không ảnh không React
- [x] `components/pixel-icon.tsx` — biểu tượng pixel vẽ bằng lưới ký tự, không thêm tệp ảnh
- [x] `components/petland-ui.tsx` — thanh chỉ số + hàng nút, không biết mascot lẫn bối cảnh
- [x] `scripts/check-petland-layers.mjs` — **giữ ranh giới đó bằng máy**
- [x] Cho ăn · Chọc · Đi dạo · Ngủ; e2e cho cả chuỗi cho-ăn

**Cầu nối giữa hai nửa là `PetIntent`, không phải tên tệp ảnh.** Phần điều khiển nói `stand` / `walk` / `run` / `hop` / `sleep`, và một bảng trong `petland-sprite.ts` dịch sang tên clip. Con dino hiện tại không có hoạt ảnh "ăn" hay "vui", nên `hop` gánh luôn vai reo mừng — đó chính là thứ bảng này tồn tại để cho phép: một mascot khác có clip `eat` riêng chỉ cần thêm một dòng, không ai ở nơi khác phải biết.

Ý định cũng được ghi ra DOM (`data-intent`), và e2e đọc **nó** chứ không bóc tên clip ra khỏi `url(/mascots/dino/walk.png)` như bản trước. Một bài kiểm ghim vào tên tệp ảnh sẽ đỏ vào đúng ngày đổi mascot, vì lý do chẳng liên quan gì tới hành vi nó kiểm.

**Cách chia tệp không tự giữ được, nên nó được kiểm.** Thêm một dòng `import` từ `petland-sprite` vào `petland-ui` thì mọi thứ vẫn chạy, mọi bài kiểm vẫn xanh, và cái giá chỉ đến vào ngày đổi mascot — lúc đó người sửa không có cách nào biết tệp nào đã lặng lẽ dính vào. `check-petland-layers.mjs` kiểm hai chiều: các tệp "không đổi" không được nhập các tệp "sẽ đổi", và mỗi đường dẫn tài sản (`/mascots/`, `/landscape/`) chỉ được **đúng một** tệp biết tới. Cùng loại với `tests/test_content_isolation.py` bên API.

**Biểu tượng vẽ bằng lưới ký tự ngay trong mã nguồn, dựng thành SVG.** Một biểu tượng 12×12 là khoảng 40 byte dưới dạng lưới, và sửa nó là sửa một dòng chữ chứ không phải mở trình vẽ rồi nhớ commit tệp mới. SVG chứ không canvas vì canvas không tồn tại lúc dựng ở máy chủ. Ranh giới về phong cách: **đồ hoạ của con thú thì pixel, khung cửa sổ thì không** — nút đóng và nút phóng to là điều khiển cửa sổ và giữ bộ icon chung của ứng dụng.

**Chỉ số cố ý cạn rất chậm** (độ no hết sau ~10 phút MỞ BẢNG liên tục). Đây là góc thú cưng của một ứng dụng học, không phải game nuôi thú: một chỉ số cạn trong hai phút biến nó thành việc phải làm, và việc phải làm thứ hai bên cạnh việc học là thứ khiến người ta đóng hẳn bảng lại. Chúng sống ở `PetLand` chứ không ở trong bảng, nên đóng rồi mở lại không đặt con thú về mặc định — "đóng cửa sổ" không phải một sự kiện trong đời con thú.

**Cho ăn đặt miếng ăn CÁCH một quãng rồi con thú tự đi tới.** Đặt ngay dưới chân thì "cho ăn" chỉ là một con số nhảy lên — cả hành động gói trong một khung hình, không có gì để nhìn. Thanh chỉ số là tám ô rời, làm tròn LÊN cho mọi giá trị khác 0: 1/8 là 12.5%, nên một chỉ số còn 4% làm tròn xuống thành rỗng và nói sai rằng con thú đã kiệt.

### Kiểm
- [x] `tsc`, `eslint`, `prettier` sạch · Playwright **11 xanh, 4 bỏ qua**
- [x] `check-petland-layers.mjs` đỏ đúng cả hai chiều: khi cho `petland-ui` nhập `petland-sprite`, và khi rải đường dẫn bức tranh sang `petland-fx`
- [x] Bài e2e cho-ăn đỏ đúng hai lần: khi đặt miếng ăn ngay dưới chân (`Expected "walk", Received "stand"`) và khi bỏ khoá nút lúc đang ăn
- [x] Chạy thật ở cả chủ đề tối và sáng

**Một lỗi mà đường ống che mất.** Sau khi dời số đo mascot sang `petland-sprite.ts`, `check-petland-fit.mjs` vẫn cào chúng từ `petland.tsx` và **ném lỗi** — nhưng nó được chạy qua `| tail -1`, và mã thoát của đường ống là của `tail`, nên chuỗi `&&` vẫn đi tiếp và mọi thứ nhìn như đã kiểm. Nay script nhập thẳng mô-đun thay vì dùng biểu thức chính quy. Bài học rộng hơn: **đừng nối một bộ kiểm vào `tail` khi còn quan tâm tới mã thoát của nó.**


---

## 4r. Petland — mascot và bối cảnh tự sinh · ✅ XONG (2026-08-19)

Thay bộ dino và bức tranh đi mượn bằng bộ **tự sinh tại máy**, dùng skill `generate2dsprite` / `generate2dmap` với FLUX.2-klein-4B qua mflux.

- [x] `assets/mascots/cat/**` — 26 khung gốc, 5 clip (idle 4, walk 6, run 6, jump 6, sleep 4)
- [x] `public/mascots/cat/**` — 5 dải ngang + `atlas.json`, ô **151×117**
- [x] `scripts/pack-pet.mjs` — kế thừa hai luật của `pack-dino.mjs`, thêm phép đo độ lệch đường chân **giữa các clip**
- [x] `assets/landscape/petland-2.png` (gốc) + `public/landscape/petland-2.jpg` (**220KB**)
- [x] `petland-sprite.ts` — `CELL` 151×117, `FOOT_Y` 115, `ANCHOR_X` 64, số khung và `fps` mới
- [x] `petland-scene.ts` — `WORLD_W` 1376 → **1360**, đo lại 11 điểm neo, 2 ô trời, 4 ô nước, `FIRE`, 5 vùng đom đóm
- [x] `check-petland-fit.mjs` — bỏ đường dẫn cứng `dino`

**Mô hình khuếch tán KHÔNG tuân số ô, và đó là ràng buộc thiết kế chứ không phải lỗi tạm thời.** Sinh tự do một lưới N×M cho sai số ô một cách tin cậy: yêu cầu 2×3 ra 3×3, yêu cầu 2×4 ra 3×2. Kèm theo là tỉ lệ lệch giữa các ô và không có đường chân chung — cả ba đều đánh thẳng vào hợp đồng của `pack-*.mjs`. Cách vòng qua là **anchor sheet**: lặp một khung master đã duyệt vào từng ô ở đúng cỡ và đúng đường chân, rồi bảo mô hình *chỉ đổi tư thế*. Với anchor sheet, số ô đúng, `body_scale_cv` xuống 0.0020–0.0388 và `anchor_x_std` bằng 0.

**Hình dạng ô phải hợp hình dạng con vật, nếu không bố cục có hai cách đọc.** Anchor sheet 2 hàng × 3 cột trên khung vuông cho ô **dọc** 341×512; con mèo nhìn ngang là hình nằm, nên sáu con nhỏ rải trên nền magenta đọc thành "3×3" cũng hợp lý ngang "2×3" — và mô hình chọn cách kia. Đổi sang 3 hàng × 2 cột (ô 512×341, tỉ lệ 1.50, gần tỉ lệ ô đích 1.41) thì cả ba clip sáu khung đều đúng ngay lượt đầu.

**Anchor sheet còn sửa một thứ không nhắm tới: màu nền.** Nền do mô hình tự vẽ trôi xa `#FF00FF` — khung master đo được `#EF359B`, cách 114.3, **vượt ngưỡng 100** của `remove_bg_magenta`, nghĩa là bước tách nền xoá được đúng 0% và sẽ lặng lẽ trả về một ảnh y hệt ảnh vào. Anchor sheet có nền `#FF00FF` thật vì do script tổng hợp, và bản edit kế thừa màu đó: bốn sheet sinh từ anchor đo được 44.7–72.9, lọt ngưỡng mặc định.

**`FOOT_Y` phải đo trên dải ĐÃ đóng gói, không suy từ ảnh nguồn.** Phép thu nhỏ làm tròn, nên con số suy trước khi thu nhỏ lệch một pixel so với thứ thật sự nằm trong tệp — và `check-petland-fit.mjs` so khớp tuyệt đối `y1 === FOOT_Y - 1`. Thông báo lỗi khi đó in `FOOT_Y=114 nhưng bàn chân ở hàng 114`, hai số bằng nhau, nhìn như chính phép kiểm bị hỏng.

**Đo cảnh bằng màu không thay được mắt, nhưng phép kiểm chất liệu thì thay được.** Bộ dò gỗ tự viết để tìm mặt cầu bắt nhầm tay vịn ở cột này, mặt cầu ở cột kia, cột đèn ở cột khác — bỏ. Ngược lại `check-petland-fit.mjs` bắt ô nước [3] sai **hai lần liên tiếp** (73% rồi 87%) trước khi phóng 6× cho thấy mảng nước sạch thật sự chỉ rộng 52×26, kẹp giữa đá bờ trái và cỏ ăn vào từ phải. Không phóng thì cả hai lần đều trông đúng.

### Kiểm
- [x] `check-petland-fit.mjs` **mã thoát 0**: 26 khung × 241 mẫu dọc đường đi, cả hai hướng, cả đỉnh nhảy — không khung nào ra khỏi tranh; 2/2 ô trời và 4/4 ô nước ≥99% đúng chất liệu
- [x] `pack-pet.mjs`: độ lệch đường chân giữa 5 clip **7px** (ngưỡng 12)
- [x] `check-petland-layers.mjs`: ranh giới còn nguyên
- [x] `tsc --noEmit` sạch · `e2e/petland.spec.ts` **4/4 xanh** trên cả sprite mới lẫn bối cảnh mới
- [x] Ảnh chụp thật trong ứng dụng, cả cửa sổ nhỏ lẫn toàn cảnh

**`petland-1.jpg` vẫn còn trong kho**, chưa xoá — bỏ đi là mất đường lùi trong khi chưa có ai dùng thật bức mới. Bộ sprite dino MUA SẴN thì **không** vào kho: nó đi kèm không giấy phép nào, và một khi mỹ thuật bên thứ ba đã nằm trong lịch sử git thì gỡ ra phải viết lại lịch sử. Nó vẫn nằm trong thư mục làm việc cùng `scripts/pack-dino.mjs`; có giấy phép thì thêm vào sau bằng một lệnh.

**Một chướng ngại không liên quan tới việc này, ghi lại vì nó chặn cả stack.** Cơ sở dữ liệu dev bị đóng dấu `029_learner_pet`, một migration chưa từng có trong git, cùng bốn bảng mồ côi `pet`, `learner_pet`, `pet_feed`, `pet_feed_log` — dấu vết của một tính năng dựng tại máy rồi hoàn tác phần code mà không hoàn tác cơ sở dữ liệu. `api` không khởi động được. Đã đóng dấu lại về `028_backdrop_speed` thay vì `down -v`, vì trong đó có 2506 clip audio, 303 từ vựng và 116 lượt làm bài. **Bốn bảng mồ côi vẫn còn**, nên lần `alembic revision --autogenerate` tới sẽ đòi DROP chúng — đọc kỹ trước khi commit migration đó.


---

## 4s. Mascot thứ hai (dino tự sinh) + sửa hai lỗi trong bộ đóng gói · ✅ XONG (2026-08-20)

- [x] `assets/mascots/rex/**` + `public/mascots/rex/**` — 22 khung, 4 clip, ô **125×117**
- [x] `pack-pet.mjs` nhận `--pet <tên>`, và suy danh sách clip từ thư mục có thật
- [x] `pack-pet.mjs` căn đường chân **giữa các clip** lúc đóng gói
- [x] `pack-pet.mjs` đổi đơn vị ngưỡng lệch sang pixel **ô đích**
- [x] `petland-sprite.ts` cập nhật `FOOT_Y` 115 → **117** theo cơ chế mới

**Anchor sheet mạnh ở chuỗi đơn điệu và yếu ở chuỗi tuần hoàn, và giờ có hai con vật làm bằng chứng.** `sleep` (hạ thấp dần) và `run` (sải bước) đạt ngay lượt đầu ở cả bộ mèo lẫn bộ dino. `jump` yếu ở cả hai — mèo `body_scale_cv` 0.0309, dino 0.0822 với 3/6 khung chạm mép. Lý do nằm ở cơ chế: anchor sheet hoạt động bằng cách GIỮ NGUYÊN ảnh tham chiếu, nên nó không có khái niệm "giữ cỡ và danh tính nhưng thả tư thế", và một cú nhảy đúng là thân rời điểm neo rồi quay về. Ba lần thử `walk`/`jump` cho ba trạng thái: khoá bao hình → sáu khung giống hệt nhau; thả tự do → một hai khung hoang dã cộng phần còn lại tĩnh; khoá hướng thân → lại giống hệt nhau. Không có nấc giữa.

**`body_scale_cv` và `anchor_y_std` đo độ NHẤT QUÁN, không đo CHUYỂN ĐỘNG — một sheet bất động ăn điểm cao nhất ở cả hai.** Bản `walk` tĩnh nhất trong ba lần lại cho `body_scale_cv` 0.0022 và `anchor_y_std` 0.0000, tức đẹp nhất. Phải tự đo phần silhouette đổi giữa hai khung liên tiếp (sau khi căn tâm và đáy) mới thấy: 9.7% so với 42.9% của bản có chuyển động thật, và 7.4% của `idle` vốn đúng là phải tĩnh. Con số này chỉ dùng để so các bản của CÙNG một clip — `run` đọc ra là chạy ở 14.5% còn `jump` đứng yên cũng ra 13.2%.

**Ngưỡng lệch đường chân đo sai đơn vị ngay từ đầu.** Bản ở §4r đo bằng pixel NGUỒN, mà nguồn thì mỗi bộ một cỡ: 7px của bộ mèo là 2.7px thật, 18px của bộ dino là 6.3px. Cùng một sai lệch nhìn thấy được lại đạt ở bộ này và trượt ở bộ kia chỉ vì hộp bao khác cỡ. Nay quy về pixel ô đích trước khi so.

**Căn đường chân giữa các clip là việc của bộ đóng gói, không phải của người sinh ảnh.** Điểm thấp nhất của cả bốn clip đều LÀ mặt đất, kể cả tư thế nằm ngủ, nên dịch cửa sổ cắt của từng clip cho trùng nhau là đúng — và đó chỉ là phần mở rộng của thao tác `--align feet` vốn đã làm trong một clip. Nó chỉ sửa vị trí DỌC; sai lệch tỉ lệ không được sửa và vẫn do `body_scale_cv` bắt, nên một clip sinh hỏng không lọt qua im lặng. Hệ quả: bộ mèo đóng gói lại có đáy đồng nhất 715 ở cả năm clip thay vì 715/716/717, và `FOOT_Y` chuyển thành đúng chiều cao ô.

**Bóng đổ sống sót qua chroma-key ở ngưỡng mặc định, và cách chữa đúng không phải nâng `--threshold`.** Dải `run` còn 366 pixel hồng dưới chân; chúng ở khoảng cách 125–170 tới magenta trong khi màu gần magenta nhất TRÊN con dino đúng bằng 170 — biên quá hẹp để nâng ngưỡng chung. Nhưng bóng nối liền với nền, nên nâng `--edge-threshold` lên 200 (chỉ ăn từ mép ảnh lan vào, không đụng pixel giữa thân) xoá sạch mà viền vẫn nguyên.

### Kiểm
- [x] Bộ mèo đóng gói lại bằng packer mới: `check-petland-fit.mjs` **mã thoát 0**, `petland.spec.ts` **4/4 xanh**, `tsc` sạch
- [x] Sót magenta sau khi sửa: run **0 px**, ba clip kia 5–13 px (răng cưa ở viền)
- [x] Chạm mép ảnh ra, kẹp, khung rỗng: **0** trên cả 22 khung

**Bộ rex CHƯA nối vào Petland** — con mèo vẫn đang chạy. `walk` không có clip riêng: theo lối thoát mà `petland-sprite.ts` thiết kế sẵn, ý định `walk` trỏ vào clip `run` ở fps thấp hơn.


---

## 4t. Chọn thú cưng · ✅ XONG (2026-08-21)

- [x] `user_profile.pet` (migration **029**), nullable, không `server_default`
- [x] `PetId` ở `app/schemas/profile.py` — danh sách mascot đi qua OpenAPI ra TypeScript
- [x] `petland-sprite.ts` thành sổ đăng ký `Record<MascotId, Mascot>`
- [x] `MascotPicker` trong thanh tiêu đề bảng Petland
- [x] `check-petland-fit.mjs` duyệt **mọi** mascot thay vì một thư mục cố định
- [x] `e2e/petland.spec.ts` thêm bài kiểm chọn + nạp lại trang

**Danh sách mascot sống ở backend dù mỹ thuật nằm ở frontend.** Khai `PetId` phía API nghĩa là nó đi qua OpenAPI thành một union TypeScript, nên `Record<MascotId, Mascot>` thiếu một con là lỗi `tsc` — không phải một `undefined` lộ ra lúc chạy. Cố ý **không** thêm CHECK trong cơ sở dữ liệu: đó là chỗ thứ hai phải nhớ sửa mỗi lần thêm mascot, và chỗ bị quên luôn là chỗ báo lỗi muộn nhất.

**Cột nullable, không giá trị mặc định ở phía máy chủ.** NULL nghĩa là "chưa chọn" và frontend rơi về con mặc định của nó, nên đổi mặc định là mọi người chưa từng chọn đi theo — cùng cái bẫy `daily_new_limit` tránh, và hỏng lặng lẽ y hệt.

**Petland lần đầu gọi API, đảo lại điều §4m ghi.** Câu "Petland KHÔNG gọi API" đúng ở thời điểm đó vì không có gì trong nó thuộc về tài khoản. Con mascot thì có: "pet của tôi" phải theo tài khoản qua mọi thiết bị và sống sót qua việc xoá cache, nên nó **không** nằm ở `localStorage` như chủ đề sáng/tối — cái đó là sở thích theo *thiết bị*. Lần đọc hồ sơ hỏng thì im lặng rơi về mặc định: một góc thú cưng không mở được vì mạng chập là cái giá quá đắt cho một tuỳ chọn trang trí.

**Mascot đọc qua ref bên trong vòng lặp, không qua closure.** Vòng `requestAnimationFrame` có danh sách phụ thuộc riêng và không dựng lại khi mascot đổi, nên closure sẽ giữ mãi con cũ và nút chọn trông như chết. Thêm `mascot` vào deps cũng chạy, nhưng giá là dựng lại cả vòng lặp giữa chừng: `frameAcc` về 0 và con thú giật đúng lúc người dùng vừa bấm.

**Migration 029 viết tay, không autogenerate.** Cơ sở dữ liệu dev mang bốn bảng mồ côi `pet`, `learner_pet`, `pet_feed`, `pet_feed_log` (§4r), nên autogenerate sẽ sinh thêm bốn lệnh `DROP TABLE` không ai yêu cầu và chúng đi thẳng vào bản phát hành.

### Kiểm
- [x] `check-petland-fit.mjs` **mã thoát 0 cho cả hai mascot**, 241 mẫu dọc đường đi, cả hai hướng, cả đỉnh nhảy
- [x] `e2e/petland.spec.ts` **5/5**, và bài mới **đã thấy đỏ trước**: bỏ lần `PATCH` thì nửa "nạp lại trang" đỏ ngay — đó là nửa chứng minh lựa chọn thật sự tới máy chủ chứ không nằm trong một biến bộ nhớ
- [x] ruff · mypy · **637 test API** · tsc · eslint · prettier · contract sinh lại không lệch

**Bộ sprite dino MUA SẴN không vào kho.** Không kèm giấy phép nào, và mỹ thuật bên thứ ba dễ giữ ngoài lịch sử git hơn nhiều so với gỡ ra khỏi nó. Nó vẫn nằm trong thư mục làm việc cùng `scripts/pack-dino.mjs`.


---

## 4u. Từ vựng — lưới chủ đề, route động và hai minigame · ✅ XONG

Gộp từ `improve-vocabulary.md` ở gốc kho, tệp đó đã xoá: ROADMAP là tracker duy nhất, và một tệp ghi tiến độ thứ hai ở gốc kho là chỗ để lạc thông tin.

- [x] `/learn/vocabulary` — lưới chủ đề dạng card lớn thay cho danh sách phẳng
- [x] `/learn/vocabulary/[slug]` — danh sách từ chuyển sang route động theo slug
- [x] `/learn/vocabulary/quiz/[slug]` và `/learn/vocabulary/match/[slug]` — hai minigame
- [x] Admin sửa và xoá chủ đề

**Segment tĩnh phải đứng trước `[slug]`.** `quiz/` và `match/` khai trước, nếu không `/learn/vocabulary/quiz/business` rơi vào trang danh sách với slug là "quiz" — hỏng theo kiểu vẫn dựng được trang, chỉ là trang rỗng.

**Minigame ghi lượt ôn SM-2, nên tiến độ tự đúng mà không cần bảng nào.** Trạng thái một từ (mới / đang học / đã thuộc) luôn suy ra từ `vocabulary_review_state` qua `mastery()`, không có cột lưu sẵn — cùng luật với `StoryProgress` và `VocabularyProgress`. Hệ quả là chơi game làm tiến độ học nhích lên thật, chứ không phải một điểm số song song.

**Ô đã ghép dùng `invisible`, không dùng `hidden`.** Ô biến mất nhưng lưới 4×4 không co lại; lưới co lại giữa ván làm người chơi mất phương hướng vì các ô còn lại nhảy chỗ.

**Màu trạng thái thắng màu loại chữ, nhưng độ đậm thì giữ.** Khi ô báo sai hoặc đang chọn, `alert`/`action` thay `action-ink` của headword — chữ vẫn đậm để không mất tín hiệu phân biệt loại từ.

## 4v. Sổ cái XP, level, việc hôm nay và huy hiệu · ✅ XONG cả bốn lát (2026-08-22)

Cả bốn lát của [`USER-ROAD.md`](USER-ROAD.md) §8. Chỉ còn `streak_bonus` ở §2.3 là chưa dựng.

- [x] Migration `030_xp_event` — sổ cái nối thêm, `UNIQUE (user_id, source_type, source_id)`
- [x] `app/services/leveling.py` — đường cong thuần, không chạm database
- [x] `app/services/progression.py` — ghi XP dùng chung, cưỡng chế trần lúc GHI
- [x] Gắn ghi XP vào ba đường ghi đã có: ôn từ, nộp câu dictation, nộp đề
- [x] `GET /api/v1/profile/progression`
- [x] `app/services/daily_tasks.py` + `GET /api/v1/daily-tasks`
- [x] Khối "Việc hôm nay" đầu `/dashboard` (`components/daily-tasks.tsx`)
- [x] `e2e/daily-tasks.spec.ts`
- [x] Migration `031_user_badge` — chỉ giữ "thấy lần đầu lúc nào" và "đã xem chưa"
- [x] `app/services/badges.py` — 15 badge suy ra từ lịch sử, không cần backfill
- [x] `GET /api/v1/progression/badges` và `POST /api/v1/progression/badges/seen`
- [x] Trang `/profile/badges`, dòng báo trên `/dashboard`, lối vào ở `/profile`
- [x] `e2e/badges.spec.ts`
- [ ] `streak_bonus` — nguồn XP duy nhất của §2.3 chưa dựng
- [x] `Avatar` nhận `frame` và `level` — viền theo token, vòng ngoài, huy hiệu level ở góc dưới phải (lát 4)
- [x] Level, khung và tiến độ XP hiện trên `/profile`; avatar sidebar mang huy hiệu
- [x] **Tranh riêng cho khung và huy hiệu** — tải lên qua vé, khoá dưới `progression/`, ảnh thắng token/icon

**Bậc tuyến tính của đường cong là 500, không phải 1800.** Bản đầu của kế hoạch ghi 1800 kèm khẳng định nó bằng khoảng cách hai level cuối đoạn cong; bậc 19→20 thật ra là **476**, tức sai gần bốn lần, và cái giá rơi đúng vào người học đã đi xa nhất. `test_level_curve_is_monotonic_and_joins_without_a_step` bắt được ngay lần chạy đầu — đây là loại lỗi chỉ lộ ra khi công thức được cho chạy, đọc lại kế hoạch thêm lần nữa không tìm ra.

**`GET /daily-tasks` là một lần đọc CÓ GHI, và đó là ngoại lệ có chủ ý.** Nó trao XP cho việc vừa xong. Hai phương án còn lại đều tệ hơn: nhét logic ba khe vào cả ba đường ghi nóng (mỗi lượt ôn phải đếm lại tiến độ ba khe), hoặc thêm một nút "nhận thưởng" — thêm đúng một bước rối vào tính năng tồn tại để bớt rối. An toàn vì `source_id` là uuid **tất định** sinh từ (người, ngày, khe), nên `uq_xp_event_source` chặn lần trao thứ hai; gọi lại bao nhiêu lần cũng ra một kết quả, kể cả khi React gọi hai lần lúc dựng.

**Mục tiêu là số CỐ ĐỊNH đã kẹp, không phải chính tình trạng.** "Ôn hết số từ đến hạn" nghe đúng nhưng số đến hạn *giảm dần khi bạn ôn*, nên thanh tiến độ chạy tới rồi lùi lại và với một số lịch SM-2 thì việc không bao giờ đóng được. Con số động là **cái kẹp**, không phải cái đích.

**Xong cả ba việc thì khối thu lại một dòng, không biến mất.** Biến mất đọc như hỏng, và nó lấy mất phần thưởng của việc vừa làm xong.

**Badge KHÔNG đọc sổ cái XP, và vì thế tài khoản cũ không cần backfill.** Điều kiện đọc thẳng lịch sử học, nên chúng đúng ngay lần đọc đầu tiên. `user_badge` không quyết định ai có badge gì — nó chỉ nhớ hai thứ lịch sử không tự nói được: lần đầu hệ thống nhìn thấy, và người dùng đã xem chưa. Thiếu nó thì không có "bạn vừa mở huy hiệu mới", vì mỗi lần đọc cái nào cũng mới.

**Ba badge `level_*` là ngoại lệ có chủ ý và giao diện phải nói ra.** Chúng đọc XP, nên một người đã học 300 từ thấy huy hiệu "300 từ" ngay lập tức **nhưng vẫn ở level 1** — XP đo hoạt động kể từ khi ra mắt, badge ghi nhận thành tựu trọn đời. Không giải thích thì nó đọc thành lỗi; câu giải thích nằm ngay dưới tiêu đề trang huy hiệu.

**Dùng `longest_streak`, không phải `current_streak`.** Một huy hiệu đã trao rồi biến mất vì hôm nay nghỉ là hình phạt cho việc nghỉ một ngày, và nó dạy người dùng rằng hệ thống lấy lại thứ đã cho.

**Chấm đỏ tắt khi MỞ TRANG huy hiệu, không khi lướt qua trang chủ**, và `POST .../seen` gọi SAU khi trang đã giữ lại danh sách "mới" — gọi trước thì người dùng theo thông báo bấm vào và thấy một trang không có gì mới cả.

**`mark_seen` phải `flush` tường minh.** Session của dự án chạy `autoflush=False`, nên lần đọc tiếp theo trong cùng giao dịch vẫn thấy `seen_at IS NULL` và đánh dấu lại lần nữa. Hàng vẫn đúng sau khi commit, nên lỗi chỉ lộ ra ở chỗ đếm — bài test bắt được ngay, đọc code thì không.

### Kiểm

`pytest` **661 passed / 2 deselected** · `ruff check` + `ruff format --check` (146 file) + `mypy` strict (104 file) sạch · `tsc --noEmit`, `eslint`, `prettier --check` sạch · `pnpm gen:api-types` sinh lại **không drift** · gọi thật trên stack đang chạy: tài khoản mới → 3 câu dictation đúng trọn → `xp_total` 25 (3×5 + 10 thưởng khe) và `xp_awarded` của lần đọc thứ hai là **0** · `alembic upgrade head` chạy `031` thật trên database dev · huy hiệu đối chiếu trên hai tài khoản có lịch sử thật (73 và 24 lượt ôn) cho ra `first_steps`, `first_test` và tiến độ 7/50 · Playwright **14 bài chạy, xanh**.

**E2E của huy hiệu cũng đã kiểm bằng cách làm hỏng thật — và lần đầu nó xanh với lỗi vẫn nằm nguyên đó.** Bỏ hẳn lệnh `POST .../seen` mà bài vẫn xanh, vì `toHaveCount(0)` đúng ngay lập tức trên một trang **chưa tải xong**: khẳng định phủ định chạy trước khi dữ liệu về thì nó tự thoả mãn. Đảo thứ tự — chờ một thứ CÓ mặt trước, rồi mới khẳng định thứ kia vắng mặt — thì cả hai lần làm hỏng (bỏ đánh dấu đã xem; ẩn huy hiệu chưa mở) đều đỏ. Đây là cái bẫy đáng nhớ hơn cả tính năng: một khẳng định phủ định trong Playwright mà không có mốc neo là một khẳng định luôn đúng.

**E2E của daily task đã kiểm bằng cách làm hỏng thật, và một trong ba lần không đỏ.** Ẩn dòng việc đã xong → đỏ; bỏ phần trao thưởng ở `GET /daily-tasks` → đỏ. Nhưng **đọc hai endpoint song song thay vì nối tiếp thì vẫn xanh ba lần chạy liền** — thứ tự nối tiếp vẫn là thứ đúng (đọc điểm trước khi thưởng kịp ghi thì việc đóng mà điểm không nhích) nhưng đó là một cuộc đua vài mili giây và bài e2e không canh được nó. Ghi lại đúng như đã đo, thay vì để lại một khẳng định không đúng trong docstring.

---

## 4w. Hệ level thành cấu hình: admin sửa được, thêm được, không cần triển khai lại · 🟢 XONG (2026-08-21)

Mọi con số của mục 4v từng là hằng số trong code. Giờ chúng là hàng trong database, có màn hình quản trị ở `/admin/progression`, và **`admin` mới vào được — `editor` thì không**: soạn nội dung và chỉnh thang điểm của mọi tài khoản là hai loại quyền khác nhau.

- [x] Migration `032_progression_config` — 5 bảng cấu hình + `user_profile.level_reached`
- [x] `progression_setting` (singleton): mức XP mỗi hoạt động, trần ngày, tham số đường cong
- [x] `daily_task_slot` — thêm/sửa/tắt/xoá khe; số khe không còn cố định là ba
- [x] `level_tier` — bảng ngưỡng là hàng, kèm nút sinh lại từ công thức
- [x] `frame_tier` — bậc khung avatar, màu là token của design system
- [x] `badge_rule` — thêm huy hiệu mới, đổi nhãn, đổi ngưỡng, tắt
- [x] `GET/PATCH/PUT/POST/DELETE /api/v1/admin/progression/**` (13 thao tác)
- [x] Trang `/admin/progression` (tiếng Anh, như cả khu quản trị)
- [x] `tests/test_progression_admin.py` — 8 bài

### Ba tính chất khiến việc mở cấu hình này an toàn

**Sổ cái làm cho mức XP an toàn để sửa.** Mỗi hàng `xp_event` giữ số điểm ĐÃ TRAO lúc đó, nên hạ mức hôm nay không rút lại của ai. Đây chính là thứ §2.1 của USER-ROAD mua về, và trước lát này nó chỉ là một lập luận — giờ nó là điều kiện để tính năng tồn tại.

**Level không bao giờ tụt.** `user_profile.level_reached` là mốc nước cao; level hiển thị là `max(tính theo bảng hiện tại, mốc đã đạt)`. Nâng chuẩn thì người mới lên chậm hơn, người cũ giữ nguyên; hạ chuẩn thì mọi người lên. Không có đường nào làm ai mất một level họ đã có vì một quyết định vận hành mà họ không tham gia. Cột này KHÔNG vi phạm luật "không có bộ đếm song song với lịch sử": nó không đếm gì, nó ghi một mốc đã xảy ra.

**Khe daily task là một HÀNG có uuid bền, không phải một mã chuỗi.** uuid đó đi vào `xp_event.source_id`, nên đổi nhãn, đổi mục tiêu, đổi mức thưởng đều không biến ngày đã thưởng thành ngày chưa thưởng. Xoá rồi tạo lại "một khe y hệt" thì có — hàng mới là uuid mới — nên giao diện mời **tắt** thay vì xoá, và bài test ghim đúng tính chất đó.

### Ranh giới giữa dữ liệu và code

Bốn tập hợp vẫn đóng, và chúng là ranh giới thật của tính năng này: `kind` của khe (mỗi loại là một phép đếm), `metric` của badge (cùng lý do), `icon` của badge (frontend phải biết vẽ), `tone` của khung (chỉ token đã có trong design system — một ô nhập mã màu tự do là đường ngắn nhất tới một khung không đọc được ở chế độ tối, nơi không ai kiểm trước khi lưu).

Đánh đổi có chủ ý: `BadgeCode` từng là union đóng nên `tsc` bắt được huy hiệu thiếu nhãn. Giờ `code` là dữ liệu, nên mất kiểm tra đó — đổi lấy việc thêm huy hiệu chỉ là thêm một hàng. `icon` giữ nguyên dạng union chính vì thế.

### Ba chi tiết fail im lặng

**Bộ mặc định seed LƯỜI ở lần đọc đầu, không seed trong migration.** Chèn ở cả hai nơi là hai bộ mặc định phải giữ đồng bộ bằng tay, và chúng lệch nhau ở đúng lần đầu ai đó sửa một con số mà quên nơi kia. Hệ quả: **bảng trống nghĩa là "chưa từng cấu hình", không phải "cố ý không có gì"** — xoá hết khe rồi thì lần đọc sau seed lại ba khe mặc định.

**Bảng level kiểm như một KHỐI.** Level 1 phải là 0 XP, không được thủng, và ngưỡng phải tăng đều. Một bảng dừng sai chỗ làm người học đọc ra một level thấp hơn XP của họ — và vì `level_reached` chỉ đi lên, một mốc sai ghi xuống trong khoảnh khắc đó thì ở lại vĩnh viễn. Vì thế `PUT /levels` ghi đè nguyên bảng chứ không có endpoint sửa-một-bậc.

**Đổi tham số đường cong KHÔNG tự sinh lại bảng.** Bảng là sự thật của phép tra cứu và admin có thể đã sửa tay vài bậc; ghi đè ngầm là xoá chỉnh sửa đó mà không hỏi. Sinh lại là một nút riêng, và trang nói trước rằng nó ghi đè.

**Một lần duy nhất khi triển khai:** mã định danh khe đổi từ chuỗi (`"review"`) sang uuid của hàng, nên `source_id` của daily task đổi theo. Người học đã nhận thưởng một khe trong ngày triển khai có thể nhận lại đúng một lần nữa cho ngày đó. Đo được, một lần, và không lặp lại.

### Quyết định của người vận hành, ghi lại vì nó đi ngược một cảnh báo

**Đổi mục tiêu daily task có hiệu lực NGAY, kể cả giữa ngày** — chọn có cân nhắc thay vì thêm cột `effective_from`. Hệ quả đã biết: nâng mục tiêu lúc 2 giờ chiều làm một việc đã xong mở lại (10/10 → 10/15), đúng cái bẫy §6.2 mô tả. XP đã trao thì không mất. Câu cảnh báo này nằm ngay cạnh ô nhập trong màn quản trị, không nằm trong tài liệu.

### Kiểm

`pytest` **672 passed / 2 deselected** · ruff + `mypy` strict (107 file) sạch · `tsc --noEmit`, eslint, prettier sạch · `gen:api-types` không drift · `alembic upgrade head` chạy `032` thật trên database dev · Playwright **14 bài chạy, xanh** · gọi thật trên stack: thêm một khe mới → học viên thấy ngay 4 việc với mục tiêu và XP riêng; thêm một huy hiệu mới đo bằng `dictation_items` → mở ra đúng theo lịch sử đã có, không cần backfill.

**`react-hooks/set-state-in-effect` bắt được thiết kế sai của bản đầu.** Mỗi hàng trong màn quản trị giữ một bản sao state và đồng bộ lại bằng `useEffect(() => setForm(props))`. Lint từ chối, và nó đúng: sự thật khi đó nằm ở sáu chỗ. Bản sửa cho cả trang MỘT bản nháp, các hàng thành component có kiểm soát — ít code hơn, và không còn chỗ nào để trôi.

---

## 4x. Khung và huy hiệu dùng tranh thật · ✅ XONG (2026-08-22)

Lát 4 vẽ khung bằng viền và token màu; giờ mỗi bậc khung và mỗi huy hiệu **gắn được một tranh riêng**, tải lên ngay tại hàng của nó trong `/admin/progression`.

- [x] Migration `033_progression_art` — `frame_tier.image_storage_key`, `badge_rule.image_storage_key`
- [x] `POST /admin/progression/assets/ticket` — vé upload, khoá dưới `progression/`
- [x] Gắn/gỡ tranh qua chính `PATCH` của hàng; `FramePublic.image_url` và `BadgePublic.image_url`
- [x] `Avatar` vẽ tranh khung đè lên ảnh; `BadgeTile` vẽ tranh huy hiệu
- [x] 2 bài test cho đường tranh

**Khoá thô dưới `progression/`, KHÔNG phải hàng trong `image_asset`.** Ba cột `license`, `attribution`, `source_url` của bảng đó là NOT NULL vì ảnh nội dung phần lớn là CC-BY và phải ghi công; tranh khung/huy hiệu là tài sản của chính sản phẩm. Avatar đã lưu khoá thô vì đúng lý do này, và tiền tố riêng là thứ giữ cho một lệnh dọn ảnh nội dung không chạm nhầm sang đây (ADR-006 §2.1).

**Không có bước `confirm` riêng, nhưng vẫn kiểm hai lớp.** Bước xác nhận chính là lệnh `PATCH` gắn khoá: nó kiểm tiền tố (thiếu lớp này thì đây là đường ghi chuỗi tuỳ ý — trỏ khung vào một ảnh nội dung rồi lệnh dọn ảnh mồ côi xoá mất thứ đang dùng) và hỏi lại nhà cung cấp (thiếu lớp này thì giao diện hiện ảnh vỡ cho tới khi có người để ý, mà không ai để ý một cái khung).

**Ảnh thắng token, nhưng token không biến mất khỏi dữ liệu.** `tone` vẫn gửi kèm vì nó vẽ được ngay trong lúc ảnh còn đang tải. **Huy hiệu chưa mở dùng chính tranh đó, làm xám** chứ không rơi về icon: đổi hẳn hình khi mở được sẽ khiến người ta không nhận ra thứ vừa nhận chính là thứ đã nhìn thấy suốt.

**Tranh khung tràn ra ngoài avatar 25% mỗi phía.** Một khung vẽ tay bao giờ cũng có phần trang trí thò ra khỏi ô vuông, và ép nó vừa khít ô sẽ cắt cụt đúng phần đó. Lớp ảnh mang `pointer-events-none` để không nuốt cú bấm của khối danh tính bên dưới.

**Sửa một hàng mặc định trước lần đọc đầu tiên từng trả 404.** Bộ mặc định seed lười, nên `PATCH /frames/bronze` trước khi ai đó `GET` cấu hình sẽ tra vào một bảng trống — 404 trên một hàng mà màn hình đang hiện. Cả bốn đường sửa/xoá giờ seed trước khi tra. Bài test tranh là thứ phát hiện ra.

**Tài khoản `admin` đeo sẵn bậc khung cao nhất** (hôm nay là `challenger`). Chọn theo `min_level` lớn nhất chứ không cứng mã: bảng bậc là dữ liệu sửa được, nên một mã cứng sẽ thành `None` im lặng vào ngày ai đó đổi tên hoặc xoá bậc đó. Ưu đãi này chạm đúng MỘT thứ — khung, vốn thuần trang trí — và dừng ở đó: level, XP và huy hiệu vẫn là số thật của chính họ. Cho cả level thì con số trên hồ sơ họ thành một lời nói dối, và nó lây sang các huy hiệu `level_*` vốn đo bằng đúng con số ấy. `editor` không có ưu đãi này.

### `/admin/progression/preview` — màn hình thử khung, và hai lỗi nó bắt được

Khung là phần DUY NHẤT của tính năng này **không kiểm được bằng terminal**: API nói hàng có `image_url`, CDN trả 200, mà khung vẫn có thể sai. Trang thử dựng mọi bậc qua chính component `Avatar`, ở ba cỡ và trên ba bề mặt (panel, recess, khối tối), kèm nút đổi số chữ số của huy hiệu level và đổi giữa ảnh thật với ô chữ cái. Nó cố ý bày ra những tổ hợp khó chịu chứ không phải một phòng trưng bày.

Mở lần đầu là nó bắt ngay hai lỗi nối tiếp nhau ở đúng một chỗ, **cả hai đều biên dịch sạch và lint sạch**:

1. **`-inset-[25%]` không sinh ra CSS nào** — dấu trừ đứng trước giá trị tuỳ ý không phải cú pháp hợp lệ. Hậu quả không phải lệch vài pixel: `position:absolute` không có toạ độ thì ảnh giữ nguyên 512px và tràn ra khắp trang. Cùng họ với cái bẫy thang bán kính ở `DESIGN-SYSTEM` §6.2.
2. **Đặt đủ bốn cạnh rồi để `width:auto` cũng không cứu.** Với phần tử THAY THẾ như `<img>`, `auto` giải ra kích thước gốc của ảnh chứ không giãn theo bốn cạnh (CSS 2.1 §10.3.7) — kết quả y hệt lần một, và đó là lý do lần sửa đầu tiên trông như không có tác dụng gì.

Bản đúng viết thẳng `top/left: -25%` và `width/height: 150%`. Bài học đáng nhớ hơn cả hai lỗi: **một tính năng thị giác cần một bề mặt để nhìn nó**, và bề mặt đó phải dựng bằng component thật chứ không phải bằng ảnh chụp màn hình dán vào tài liệu.

### Tranh lấy từ đâu

Bộ skill `agent-sprite-forge` (`~/.claude/skills/`) **dùng được, nhưng chỉ hai mắt xích đầu**: sinh ảnh trên nền `#FF00FF` đặc, rồi tách nền thành PNG trong suốt. Phần còn lại của skill — sheet, frame, animation, anchor, hợp đồng Godot — là chuyện của sprite game và không liên quan gì tới một tấm tĩnh cho giao diện web. Runbook đầy đủ kèm prompt đã dùng nằm ở `apps/api/content/sources/progression-art/README.md`.

**Bản đã xử lý được commit vào kho.** Cùng lý do `MEDIA-PIPELINE` §10.3 nêu: ảnh không tái tạo được. Model sinh ảnh không tất định, `media/` thì gitignore, nên một tấm bị xoá nhầm trên Cloudinary là mất hẳn. Tệp chỉ vài chục KB.

**Provider tự chọn là flux2 chạy tại máy**, ~2,5 phút một tấm, đỉnh 12,37 GB RAM trên máy M2 16 GB. Chạy được, và đó là con số đo chứ không phải suy từ code.

**Prompt phải cấm luôn nét viền hồng/magenta trong chính hình vẽ.** Bước tách nền xoá theo màu, nó không phân biệt được nền với một nét vẽ cùng màu — `frame-gold` còn ~2,7% pixel ám hồng ở rìa vì model tự vẽ một đường viền hồng nhạt. Ở cỡ hiển thị thật thì gần như không thấy; ở lần sinh sau thì viết thêm câu đó.

### Kiểm

`pytest` **674 passed / 2 deselected** · ruff + `mypy` strict (107 file) sạch · `tsc --noEmit`, eslint, prettier sạch · `gen:api-types` không drift · `alembic upgrade head` chạy `033` thật trên database dev · Playwright **14 bài chạy, xanh** · vé upload gọi thật và trả về chữ ký Cloudinary đúng tiền tố `toeic-pilot/progression/`.

**Thang khung là TÁM bậc, mỗi bậc một tranh riêng** (2026-08-22): `bronze` 5 · `silver` 10 · `gold` 15 · `platinum` 20 · `diamond` 25 · `master` 30 · `grandmaster` 40 · `challenger` 50. Bốn bậc giữa là mới; `gold` nhường mốc 20 cho `platinum` và lùi về 15. Thứ tự thao tác quan trọng: `min_level` là UNIQUE, nên tạo `platinum` ở mốc 20 trong lúc `gold` còn đứng đó sẽ bị chặn — dời `gold` trước, rồi mới tạo.

**`tone` của mỗi bậc vẫn đặt dù đã có tranh.** Nó là màu vẽ ngay trong lúc ảnh còn tải, nên bỏ trống nghĩa là khung không tồn tại cho tới khi ảnh về — với kết nối chậm đó là một avatar nhấp nháy đổi hình.

**Đã chạy trọn vòng bằng tranh thật** (2026-08-22): sinh → tách nền → vé → POST lên Cloudinary → `PATCH` gắn khoá → học viên đọc được `image_url` → CDN trả 200. Tám khung (512px) và một huy hiệu `streak_7` (256px) đang nằm trong database dev và phục vụ được từ CDN.

---

## 4y. Đăng nhập bằng Google và Apple · 🟢 Google xong, Apple dựng sẵn (2026-08-22)

Quyết định và lý do ở [`ADR-008-AUTH-PROVIDERS.md`](ADR-008-AUTH-PROVIDERS.md), kèm runbook lấy khoá cho cả hai bên.

- [x] Migration `034_user_identity` — bảng `user_identity`, `users.hashed_password` bỏ NOT NULL
- [x] `app/services/oauth.py` — mô tả hai nhà cung cấp, kho `state`, xác minh `id_token`, luật liên kết
- [x] `GET /auth/providers`, `GET /auth/{provider}/start`, callback cho cả GET (Google) lẫn POST form (Apple)
- [x] Nút "Tiếp tục với…" ở `/login` và `/register`, trang `/auth/callback`
- [x] `tests/test_oauth.py` — 8 bài, không bài nào gọi ra mạng thật
- [ ] **Chạy thật với Google** — cần Client ID/secret của một project Google Cloud
- [ ] **Apple** — cần tài khoản Apple Developer và một domain HTTPS; Apple không nhận `localhost`
- [ ] Gỡ liên kết trong trang hồ sơ, và đặt mật khẩu lần đầu cho tài khoản chỉ có nhà cung cấp

**Không nhúng SDK của Google hay Apple, và đó là ràng buộc từ chính dự án này.** P1-7b (token trong `localStorage` thay vì cookie httpOnly) được hoãn *với lý do viết ra*: app không có script bên thứ ba nào. Nhúng `accounts.google.com/gsi` là làm lý do đó hết hiệu lực, và khi đó P1-7b phải trả trước tính năng này. Nên luồng đi phía máy chủ.

**Tra theo `sub`, không theo email.** Email đổi được, và với Apple còn có thể là địa chỉ chuyển tiếp ẩn. Tra theo email nghĩa là ai đổi email bên Google sẽ thành một người mới ở đây, mất sạch lịch sử học.

**Liên kết theo email chỉ khi đã xác minh và không phải địa chỉ ẩn.** Gắn bừa là một đường chiếm tài khoản có thật. Chi tiết dễ làm hỏng cả luật: **Apple gửi `email_verified` dạng chuỗi `"true"`, Google gửi boolean** — một phép so `is True` sẽ coi mọi tài khoản Apple là chưa xác minh và luật im lặng ngừng chạy.

**`state` fail CLOSED khi Redis hỏng**, ngược với `rate_limit_anonymous`. Ở đó Redis hỏng mà chặn hết là một phụ thuộc mềm làm sập sản phẩm; ở đây Redis là thứ duy nhất chứng minh callback thuộc về một lần bấm có thật.

**mypy bắt đúng hai chỗ mà tài khoản không mật khẩu đi qua.** Đổi `hashed_password` sang nullable làm `verify_password(..., None)` thành lỗi kiểu ở `/auth/login` và `/auth/password` — cả hai đều là đường mà một `None` lọt qua sẽ hỏng lặng lẽ. Hai chỗ đó giờ xử lý khác nhau có chủ ý: `/login` trả thông báo chung (nói "tài khoản này dùng Google" là một máy dò tài khoản), `/password` nói thẳng vì danh tính đã được chứng minh.

### Giao diện đăng nhập / đăng ký: linh vật đổi bên, có trạng thái

`/login` và `/register` chuyển vào **nhóm route `app/(auth)/`** dùng chung một layout. Đó là điều kiện để hiệu ứng tồn tại chứ không phải cách xếp thư mục cho gọn: layout của nhóm route **không bị dựng lại** khi đi giữa hai trang trong nhóm, nên linh vật giữ nguyên phần tử DOM, trượt sang bên kia, và nhịp chớp mắt không bị đặt lại. Gọi component từ trong mỗi trang thì mỗi lần chuyển là một lần tháo ra dựng lại — ảnh biến mất rồi hiện ra ở chỗ mới, không có gì để chuyển động. Ngoặc đơn không thêm đoạn nào vào URL.

**Đổi chỗ bằng `translate-x`, không bằng `order`.** `order` không chuyển động được — trình duyệt chỉ nội suy được thuộc tính có giá trị trung gian, và thứ tự sắp xếp thì không có. Hai nửa rộng bằng nhau nên dịch 100% chiều rộng của chính mình là hoán vị khít.

**Bốn khung hình sinh trong MỘT sheet 2×2**, không phải bốn lần sinh riêng: model không vẽ lại đúng một nhân vật hai lần, và mỗi khung lệch một chút ở mũ hay khăn thì lúc chớp mắt cả con vật giật một cái. Ba trạng thái đang dùng — idle, chớp mắt, che mắt khi con trỏ ở ô mật khẩu; khung vẫy tay để dành cho lúc có một khoảnh khắc chờ đủ dài để nhìn thấy.

**Trạng thái "che mắt" nghe ở cấp `document`, không truyền prop.** Linh vật sống trong layout còn ô mật khẩu nằm trong từng trang — hai nhánh khác nhau của cây component. Nối bằng prop sẽ phải dựng một context xuyên qua layout chỉ để nói "đang gõ mật khẩu", và mỗi trang thêm sau lại phải nhớ nối vào. `focusin`/`focusout` nổi bọt lên `document`, nên một chỗ nghe phủ mọi ô mật khẩu kể cả của trang chưa viết.

**Chớp mắt dùng hẹn giờ LỒNG NHAU, không `setInterval`:** mỗi lần cách nhau một khoảng khác nhau. Mắt bắt được nhịp đều rất nhanh, và lúc đó nó đọc ra là một vòng lặp chứ không phải một sinh vật. Hai khung kia được tải sẵn trong DOM ở kích thước 0 — không có bước đó thì lần chớp ĐẦU TIÊN là một khoảng trống, vì trình duyệt mới bắt đầu tải ảnh đúng lúc cần hiện.

**`normalise_bg.py` phải viết lại vì nó ăn thủng linh vật.** Bản đầu quy mọi pixel nằm trong bán kính màu quanh nền thành magenta; thân nâu (170, 92, 72) chỉ cách nền hồng (205, 37, 135) **90,7** — vừa đúng ngưỡng 90 — nên 12% pixel thân bị coi là nền và khoét thành lỗ lỗ chỗ. Bản mới **lan từ mép ảnh vào**: nền thật luôn nối liền với mép, còn màu áo nhân vật thì không, nên một vùng bên trong có màu gần giống nền vẫn an toàn dù bán kính có rộng đến đâu. Đo lại: 0 pixel thân bị quy nhầm, chạy 0,87 giây.

**Sinh sheet lần đầu hỏng theo kiểu chỉ phát hiện được khi xem từng khung:** model vẽ cây bút chì ở hai trong bốn ô, và hai ô đó là idle với chớp mắt — mỗi lần chớp là cây bút hiện ra rồi biến mất. Prompt hiện tại cấm hẳn đồ cầm tay, và ghi lý do ngay trong tệp prompt.

### Giao diện đăng nhập / đăng ký dựng lại

Bản trước là một cái thẻ trắng căn giữa với hai ô nhập — đúng hình dạng mà mọi ứng dụng đều có, và nó không nói gì về việc sản phẩm này làm gì.

**Bản trung gian (đã gỡ): thang điểm TOEIC 10–990 dựng như một thước đo thật**, và nó mang thông tin đúng chứ không phải hình trang trí: khoảng điểm thật của kỳ thi, cùng hai ngưỡng năng lực ETS công bố (605 = giao tiếp công việc, 785 = thành thạo). Nó đóng luôn vai đường phân cách của trang, nên không có đường kẻ trang trí nào phải thêm.

Ba chi tiết là hệ quả trực tiếp của DESIGN-SYSTEM chứ không phải sở thích:

- **Ba dải năng lực `rounded-none`**, cùng lý do `Meter` đã ghi: vạch chia của thiết bị đo không bo tròn. Bo 4px ở chiều cao 6px biến chúng thành ba viên thuốc rời, đọc ra là ba cái nhãn chứ không phải một phép đo liên tục.
- **Bốn chấm màu giọng đọc dùng đúng thang `--accent-{us,uk,au,ca}`** — thang đó tồn tại để phân loại giọng đọc, nên đây là chỗ duy nhất trong trang được phép có bốn màu, và nó đang làm đúng việc của mình.
- **`leading` không dưới 1.28 ở tiêu đề 2.6rem**: tiếng Việt chồng hai tầng dấu lên một nguyên âm, và thang display của tiếng Anh (1.0–1.1) sẽ cắt cụt dấu.

Chuyển động: đúng MỘT — ba dải vẽ ra từ trái sang, so le nhau, một lần lúc tải. Thuần CSS keyframes chứ không phải state React (`setState` trong effect bị lint chặn), `scaleX` chứ không phải `width` (chỉ scaleX chạy trên compositor), và `prefers-reduced-motion` tắt hẳn.

**Hai lỗi tự soi ra khi nhìn màn hình thật:** nửa dưới trang trống trơn vì mọi thứ dính lên đỉnh (sửa bằng căn giữa dọc), và khối biểu mẫu bị lưới kéo giãn nên có một khoảng trống dưới đáy, trông như đang thiếu một trường nhập (sửa bằng `self-start`).

### Kiểm

`pytest` **683 passed / 2 deselected** · ruff + `mypy` strict (110 file) sạch · `tsc`, eslint, prettier sạch · `gen:api-types` không drift · `alembic upgrade head` chạy `034` thật trên database dev · Playwright **14 bài chạy, xanh** · gọi thật: chưa cấu hình thì `/auth/providers` trả `[]` và `/auth/google/start` trả **404**, giao diện không hiện nút nào.

**Chưa chạy được đầu-cuối với nhà cung cấp thật** — cần khoá. Đó là lý do phần "chạy thật với Google" ở trên còn để trống thay vì đánh dấu xong.

---

## 4z. Ruby — đơn vị thứ hai, thưởng cho việc LÀM XONG · 🟢 lát 1–6 xong (2026-08-27)

Quyết định và lý do ở [`ADR-011-RUBY.md`](ADR-011-RUBY.md). Dựng ra để mở khoá lát 8 (gacha) của ADR-010: trứng phải mua bằng *một thứ gì đó*, và §6.2 của tài liệu kia đã loại thứ hiển nhiên nhất.

- [x] Lát 1 — migration `038_ruby`, `ruby_event` + `ruby_rule`, `app/services/ruby.py::earn`
- [x] Lát 2 — nối vào ba đường đã có: xong một bài dictation (5), thuộc trọn một chủ đề (15), làm hết một đề (25 / 8)
- [x] Lát 3 — `daily_all` (10), `daily_gift` (3), `streak_week` (20) ở `app/services/ruby_daily.py`, `GET /ruby`, `POST /ruby/gift`
- [x] Lát 4 — `spend()` có khoá tư vấn Postgres + `tests/test_ruby_race.py` có `Barrier`
- [x] Lát 5 — `GET/PATCH /admin/ruby/rules` sau `require_role("admin")`, trang `/admin/ruby`
- [x] Lát 6 — số dư + nút quà ở `/dashboard`, toast riêng cho ruby
- [x] Đường TIÊU thật — gacha (ADR-010 lát 8), mở lẻ và mở 10, cùng khoản hoàn cho con trùng

**Ruby thưởng việc LÀM XONG, XP thưởng KHỐI LƯỢNG — và đó là lý do có hai đơn vị.** Không nguồn nào trả theo lượt nhỏ; có một cái là ruby thành XP thứ hai và cả tài liệu mất nghĩa. Hệ quả cụ thể: `daily_all` trả cho việc xong **cả ba** việc chứ không từng việc, và toast của ruby là một tin RIÊNG chứ không cộng chung dòng với XP.

**Ngưỡng của lượt làm đề đo bằng ĐỘ ĐẦY ĐỦ, không bằng điểm.** Trả theo điểm là phạt người học yếu vì họ yếu; trả cho mọi lượt nộp thì bấm bừa qua 200 câu trong hai phút cũng lấy đủ 25. `RUBY_ANSWERED_RATIO = 0.8` chặn đường thứ hai mà không đụng tới người thứ nhất. `source_id` là **đề**, không phải lượt làm, nên làm lại đề cũ không in thêm ruby.

**Chỗ khó thật nằm ở việc TIÊU, và bài kiểm của nó đã suýt vô dụng.** Số dư là một phép `SUM`, nên hai lần mở trứng đồng thời đều đọc thấy 30, đều thấy đủ cho một quả 25, và đều ghi một hàng −25 — không ràng buộc nào bị vi phạm, không lỗi nào được ném. `pg_advisory_xact_lock` theo `user_id` khép khe đó lại.

Bản đầu của bài kiểm đặt `Barrier` ngay **trước** lúc lấy khoá, và **gỡ khoá đi nó vẫn xanh**: luồng đầu kịp đọc-ghi-commit trọn vẹn trước khi luồng sau xin được kết nối. Hàng rào phải nằm **giữa** lần đọc số dư và lần ghi — chỗ `tests/test_concurrency.py` đã đặt nó cho cuộc đua đăng ký. Nhưng ở giữa thì lại khoá chết khi khoá CÓ mặt (luồng cầm khoá chờ những luồng đang chờ chính nó), nên nó chờ có hạn giờ và coi việc vỡ hàng rào là câu trả lời hợp lệ. Đo lại cả hai chiều: không khoá thì tám luồng cùng mua được, số dư còn −170; có khoá thì đúng một quả.

**Gieo lười cũng là một cuộc đua, và bài kiểm đó tìm ra nó.** Tám luồng cùng hỏi mức thưởng khi `ruby_rule` còn rỗng thì cùng gieo, và người thua vỡ khoá chính — một lượt học hỏng vì một cuộc đua trên bảng cấu hình. `rules()` gieo trong SAVEPOINT và nuốt va chạm, người thua chỉ đọc lại. Cùng hình dạng này đang có ở `pet_species` và `progression_config` và **chưa được xử lý ở đó**.

**Quà hàng ngày mở SAU khi hôm nay đã học gì đó**, không mở sẵn lúc vào app: thưởng cho việc mở app mà không học là dạy đúng cái hành vi không muốn. Nhìn từ phía người dùng nó vẫn là "vào nhận quà mỗi ngày", chỉ khác ở chỗ nút sáng lên sau bài đầu tiên — và nó cho cái nút một câu để nói.

**`streak_week` khoá theo SỐ MỐC, không theo ngày.** Mốc 7 trả đúng một lần trong đời tài khoản; đứt chuỗi rồi gây lại tới 7 không trả lần nữa. Trả lại theo ngày sẽ biến nó thành nguồn thu đều đặn cho người cứ bảy ngày nghỉ một lần. Nó cũng đọc `current_streak` — khác huy hiệu chuỗi ngày, vốn phải đọc `longest_streak`.

Một khoản nợ nhỏ đã trả nhân tiện: **`/admin/pet` (lát 7 của ADR-010) chưa từng có lối vào nào trong menu quản trị**. Giờ nó là một mục ở nhóm System, với `/admin/ruby` làm mục con.

**Tài khoản `admin` luôn được bù lên 500 ruby**, để thử được đường tiêu mà không phải học hết một chủ đề từ vựng trước mỗi lần. Ba tính chất của cách làm này là cố ý:

- **Là một HÀNG trong sổ cái (`admin_grant`), không phải một ngoại lệ lúc đọc.** Cho `balance()` trả về con số khác cho admin là để màn hình nói một đằng và sổ cái nói một nẻo — rồi `spend` trừ trên con số thật và số dư tụt xuống âm. Một hàng thật giữ nguyên "số dư là `SUM` của đúng một bảng", và nó trả lời được câu "chỗ ruby này ở đâu ra".
- **Bù cả ở đường TIÊU, không chỉ lúc đọc.** Mở liên tiếp sẽ cạn giữa chừng, và một lời từ chối "cần 25 ruby" giữa phiên thử là đúng chỗ người ta kết luận nhầm rằng tính năng hỏng.
- **Chỉ `admin`, không `editor`** — cùng ranh giới `/admin/ruby/rules` đã vẽ.

Cái giá phải nói ra, và giao diện nói ra: số dư ruby của một admin thật không còn là con số họ kiếm được. Cùng đánh đổi với khung avatar bậc cao nhất — perk chạm đúng một thứ. Khác trường hợp XP ở chỗ ruby không nuôi level hay huy hiệu, nên không có gì bị thổi phồng lây.

**Vòng sáng dưới chân theo hạng hiếm, và nó phải BA lớp.** Bản đầu là một hình bầu dục 22% độ đậm — đọc ra là bóng đổ, vì bóng đổ đúng là như thế. Giờ có quầng rộng (vùng sáng), lõi đặc (điểm chói) và một vòng lan ra rồi tắt; không lớp nào tự nó làm được việc "đang phát ra cái gì đó". Vòng lan **chỉ có ở hạng hiếm và cực hiếm**: nó tốn chú ý nhất, nên cho hạng nào cũng có thì không phân biệt được gì — thứ hiếm phải hiếm cả trong cách nó chiếm mắt người nhìn. Vòng sáng bám ĐẤT chứ không bám con thú (không nhận cái nhún, không nhận tư thế), vì đó là chỗ mắt đọc ra "bóng phát sáng trên mặt đất" thay vì "vòng dính vào bụng".

Màu lấy từ đúng bốn token mà `TIER_TONE` dùng cho chữ trong tủ (`--ink-muted` / `--ok` / `--action` / `--alert`), đọc lúc chạy nên **theo cả chế độ sáng lẫn tối**, và đọc lại khi đổi con hoặc đổi chủ đề — nghe cả `data-theme` lẫn `prefers-color-scheme`, vì chủ đề có ba trạng thái và nghe một đường là đúng cho một nửa số người dùng.

**`petland-bestiary.ts` — 180 ô sinh vật đã được xếp vai**, chuẩn bị cho những tính năng còn ở phía trước (gặp NPC ngẫu nhiên, đánh kẻ xâm nhập bằng cách trả lời câu hỏi tiếng Anh). Phân bố lúc viết: **99 kẻ xâm nhập · 60 hoang dã · 12 thú nuôi · 9 NPC** (đổi thành 96 · 37 · 40 · 7 sau khi mở rộng bộ thú nuôi bên dưới).

Ba điều về bảng này:

- **Phân loại bằng MẮT, một lần.** Tấm ghép không nói ô nào là gì — nó là 180 hình 16×16 xếp cạnh nhau. Kết quả có được bằng cách giải mã PNG bằng zlib thuần rồi phóng to từng khối sáu hàng mà xem, nên nó là dữ liệu người đọc chứ không phải thứ suy ra được. Đã đối chiếu ngược: cả 180 ô đều có hình (không ô nào trống bị xếp vai), và tổng bốn vai đúng 180.
- **Ngoại lệ thắng khoảng, và ngoại lệ được viết thành từng dòng có tên.** `creatures.png` xếp theo chủ đề — sáu hàng đầu gần như toàn sinh vật huyền thoại, sáu hàng cuối gần như toàn thú thật — nhưng có con nằm lẫn: tiên, thiên thần, tiên cá, thần đèn nằm giữa đám quái; mắt bay và cây ăn thịt nằm giữa đám thú. Một ô xếp nhầm vai nghĩa là con thú đi tới bắt chuyện với một con quái, hoặc người chơi bị hỏi câu tiếng Anh vì một con thỏ.
- **Vai mặc định là `wildlife`, không phải `intruder`.** Ô lạ hay ô đánh số nhầm thì không kéo theo hành vi nào; mặc định thù địch sẽ biến một con số sai thành một trận đánh không ai hẹn.

Bảng này **tạm ở frontend**, đúng nghĩa mà `SPECIES_TILE` từng tạm: ngày kẻ xâm nhập có máu, có phần thưởng và có bộ câu hỏi gắn kèm thì nó phải xuống database như `pet_species` đã xuống — vì lúc đó nó là thứ người vận hành cân chỉnh, không phải thứ lập trình viên sửa.

**Bốn mươi loài và hạng thứ năm: `legendary`** (migration `041`). Chọn tay từ `creatures.png` bằng cách giải mã tấm ghép rồi phóng to từng ô mà xem — **không đoán theo tên hàng**, vì ô 170 trông như cá heo ở cỡ 16px và thật ra là con tê giác, ô 103 là con vẹt chứ không phải gà trống, và ô 123 là bình sữa chứ không phải vịt. Đặt nhầm thì hàng dữ liệu vẫn hợp lệ, chỉ người mở trứng ra mới biết.

| Hạng | Loài | Tỉ lệ cả hạng | Màu vòng sáng |
|---|---|---|---|
| thường | 9 | 49,3% | `--ink-muted` |
| ít gặp | 10 | 34,2% | `--ok` |
| hiếm | 8 | 11,0% | `--action` |
| cực hiếm | 7 | 3,8% | `--alert` |
| **huyền thoại** | 6 | **1,6%** | `--warn` (vàng) |

Sáu con huyền thoại — kỳ lân, thiên mã, rồng lửa, rồng băng, tiên, thần đèn — lấy từ khoảng "sinh vật huyền thoại" của tấm ghép, tức là chúng **thôi làm kẻ xâm nhập kể từ ngày thành thú nuôi**: `roleOf` xét bảng thú nuôi trước mọi thứ khác, vì một con rồng vừa nở ra từ trứng thì không được phép quay lại tấn công chủ nó. Bảng vai giờ là **96 kẻ xâm nhập · 40 thú nuôi · 37 hoang dã · 7 NPC**.

0,27% cho mỗi con huyền thoại là cố ý, và **bộ đếm an ủi mới là thứ giữ cho nó không thành vô vọng**: sau mười quả không ra hạng hiếm thì quả sau chắc chắn ra hạng hiếm trở lên, và trong nhóm ấy huyền thoại chiếm 10% — nên `RARE_TIERS` phải kể cả `legendary`, nếu không hạng cao nhất lại là hạng duy nhất bộ đếm không bao giờ ép ra.

**Migration `041` chèn thẳng danh sách loài, và đó là chỗ DUY NHẤT trong dự án một bộ mặc định xuất hiện hai lần.** Lý do: bộ mặc định được gieo LƯỜI, mà gieo lười chỉ chạy khi bảng RỖNG — đúng tính chất khiến "xoá một loài" không bị hoàn tác ở lần đọc sau. Hệ quả là mọi cài đặt đã chạy đang giữ 12 hàng cũ và **sẽ không bao giờ** thấy 28 loài mới, dù mã nguồn đã có. Bản trong migration vì thế không phải bản sao của bảng: nó là **ảnh chụp tại đúng lần sửa này**, đông cứng vĩnh viễn, và không bao giờ cập nhật theo bộ mặc định nữa. `ON CONFLICT DO NOTHING` giữ nguyên mọi hàng admin đã chỉnh. Chiều xuống chỉ xoá hạng huyền thoại (CHECK cũ không nhận chúng) và **không** xoá 28 loài kia — người chơi có thể đã nở ra chúng, và `pet_owned` giữ mã loài chứ không giữ khoá ngoại.

**Petland có đồng hồ riêng, và trời tối sáng theo nó** (`petland-clock.ts`). Ba quyết định:

- **Một ngày ở Petland dài một giờ thật.** Đánh đổi giữa hai cái hỏng ngược nhau: chạy theo giờ thật thì người chỉ học buổi chiều **không bao giờ** thấy đêm — một tính năng phần lớn người dùng không nhìn thấy thì coi như không có; chạy quá nhanh thì bầu trời nhấp nháy trong lúc người ta đang học, và góc thú cưng chuyển từ "có gì đó đang sống ở đây" sang "có gì đó đang nháy ở đây".
- **Suy ra từ `Date.now()` theo UTC, không lưu và không theo múi giờ máy.** Cùng luật với nhu cầu con thú và chuỗi ngày học; và vì Petland là MỘT nơi chốn, người ở Hà Nội với người ở Berlin cùng nhìn vào một buổi hoàng hôn. Lấy theo múi giờ máy thì "đêm ở Petland" thành câu không nói được với ai khác.
- **Trời tối bằng một lớp phủ trên KHUNG NHÌN, không phải trên bản đồ.** Lớp phủ vào `app.stage` chứ không vào `world`: `world` bị camera lia và bị phóng `zoom`, nên một hình chữ nhật nằm trong đó sẽ trôi theo bản đồ và để lộ một góc chưa phủ mỗi khi con thú đi.

Màu trời là một bảng mốc được **nội suy**, không phải bốn trạng thái — nhảy bậc thì đọc ra là lỗi vẽ chứ không phải hoàng hôn. Ba con số trong bảng là thiết kế: giữa trưa `alpha` bằng **0** (phủ một lớp mỏng cho "ấm" làm mọi ô pixel lệch màu suốt cả ngày, mà bảng màu Kenney vốn được chọn để đứng cạnh nhau); đêm dừng ở **0,55** chứ không 0,8 (dưới ngưỡng đó không nhìn ra con thú đang đứng đâu, mà con thú mới là thứ người ta mở bảng này để xem — trời tối là bối cảnh, không phải màn che); bình minh và hoàng hôn ngả **cam**, đêm ngả **xanh tím** (cùng một màu tối cho cả ba thì chỉ còn "sáng dần rồi tối dần", mất hai khoảnh khắc người ta thật sự nhận ra).

Đồng hồ hiện ở thanh tiêu đề kèm mặt trời/mặt trăng, và `title` **nói ra đây là giờ của Petland**: một con số "02:15" cạnh con thú mà không giải thích thì người đọc sẽ so với đồng hồ máy mình rồi kết luận là sai. Phần chữ chạy theo hẹn giờ 2,5 giây (đúng một phút Petland) chứ không theo khung hình — cho nó vào state ở 60 khung/giây là dựng lại cả bảng sáu mươi lần mỗi giây để đổi một chữ số mỗi hai giây rưỡi; còn bầu trời thì vẫn đọc đồng hồ mỗi khung hình vì nó phải đổi mượt.

**Ngủ để hồi sức** (migration `043`). Sức vốn đã tự hồi 1 điểm mỗi 12 giờ mà không cần ai làm gì, nên nếu ngủ chỉ là một dòng chảy thứ hai chạy song song thì nó không phải cơ chế — chỉ là một cái nút làm đúng việc đồng hồ đang làm. Thứ nó thêm vào là một **quyết định**: đánh đổi vài giờ không chơi được với con thú để lấy lại sức đi dạo. Ngủ hồi **gấp bốn** (đầy từ số không trong ba tiếng), **vui không tụt** trong lúc ngủ, và **đói vẫn xuống như thường** — nếu đói cũng dừng thì cho ngủ là cách né cơn đói, và người chơi sẽ tìm ra mẹo ấy rồi dùng mãi.

Bốn tính chất, mỗi cái là một quyết định:

- **`sleep_until` là một MỐC HẾT HẠN, không phải cờ `đang_ngủ`.** Giấc ngủ tự dứt khi tới mốc: không cần ai bấm gì, không cần job nền đi đánh thức, và người đóng tab giữa chừng vẫn thấy con thú đã dậy khi quay lại. Một cái cờ thì phải có ai đó tắt nó, và "ai đó" cuối cùng luôn là người dùng — tức là đúng cái việc-phải-làm mà cả góc thú cưng dựng ra để không có.
- **`decay` chia quãng thời gian làm HAI ĐOẠN, không nhân một hệ số.** Giấc ngủ gần như luôn kết thúc GIỮA hai lần đọc — cho ngủ rồi đóng tab, lần mở sau đã qua cả giấc lẫn một quãng thức. Nhân cả quãng với tốc độ ngủ thì con thú hồi sức trong lúc nó đã dậy từ lâu: con số vẫn hợp lệ, chỉ là sai, và không có gì báo.
- **Ba hành động kia bị TỪ CHỐI trong lúc ngủ, không tự đánh thức.** Một cú bấm nhầm mà xoá mất hai tiếng hồi sức là thứ người dùng không lường trước và cũng không hoàn lại được; nút "Đánh thức" thì họ chủ động bấm, và nó nằm đúng chỗ nút "Ngủ" nên không phải đi tìm.
- **Ngủ và dậy không cho XP.** Chúng không tốn gì và không đòi hỏi gì, nên trả điểm là mở lại đúng cái cửa mà trần ngày đóng. Thứ giấc ngủ trả về là **đi dạo được** — mà đi dạo mới là hành động đáng 5 điểm. Cùng mạch với ràng buộc đói-thì-chưa-đi-dạo-được: ba nút giờ có một thứ tự thật, cho ăn → ngủ → đi dạo.

Đo trên stack: sức 0,95 thì bị từ chối ("Nó chưa buồn ngủ"); ngủ trọn ba tiếng từ 0,12 lên **1,00** với vui giữ nguyên 0,70 và no vẫn tụt 0,62 → 0,49; cùng ba tiếng mà THỨC thì sức chỉ lên 0,37 và vui tụt còn 0,62; hết giấc thì tự dậy, không ai đánh thức.

**Mở 10 quả một lượt** (`POST /pet/eggs/open-ten`). Ba tính chất:

- **Cả lượt là MỘT giao dịch, không phải mười.** Trừ tiền từng quả thì một lỗi ở quả thứ bảy để lại người dùng mất tiền của sáu quả đã mở mà không có gì nói vì sao — và đường tiêu này là đường có khoá tư vấn, nên nửa chừng còn nghĩa là giữ khoá lâu gấp mười lần cần thiết. Sổ ruby ghi **một dòng trừ và một dòng hoàn** cho cả lượt, chứ không hai mươi dòng cho một cú bấm.
- **Không có luật "mở 10 chắc chắn có hàng hiếm".** Bộ đếm an ủi chạy qua từng quả trong lượt, đúng như khi mở lẻ; một luật riêng sẽ là luật thứ hai làm đúng việc mà bộ đếm đang làm, với một con số khác — mà bộ đếm thì admin sửa được, nên hai con số sẽ lệch nhau vào ngày ai đó chỉnh một trong hai. Mở mười quả mà không ra gì thì bộ đếm đã đầy, và quả kế tiếp chắc chắn ra hạng hiếm.
- **Đường dẫn riêng, không phải `?count=10`.** Hai lượt mở trả về hai hình dạng khác nhau (một quả và một danh sách), và một endpoint đổi hình dạng theo tham số là thứ frontend phải đoán.

Bài kiểm bắt được một lỗi **chỉ xuất hiện khi mở nhiều**: `db.get(PetOwned, …)` không thấy hàng vừa `add` trong cùng lượt (session chạy `autoflush=False`, cùng cái bẫy đã ghi cho `mark_seen` và cho `_finalise`), nên mở mười quả ra cùng một loài chèn mười hàng cùng khoá chính và vỡ ở lệnh flush cuối. Mở lẻ không bao giờ lộ ra — mỗi lượt một quả, và giao dịch đóng lại trước quả kế tiếp. Đã thêm `flush` ngay sau khi thêm hàng.

Giao diện: lưới 5×2, con trùng mờ đi và con mới có viền theo màu hạng — mười cái thẻ nối nhau thì không ai đọc hết. **Một thông báo cho cả lượt**, câu chúc lấy theo hạng cao nhất trong lượt: bắn từng con mới sẽ đẩy ra tới mười thẻ chồng nhau, và cái thẻ báo con huyền thoại nằm lẫn giữa chín cái báo con vịt.

Đo trên stack: chưa đủ tiền → *"Cần 250 ruby cho mười quả, hiện có 0"*; bốn lượt liên tiếp cho 7 · 6 · 3 · 4 con mới với tiền hoàn 30 · 40 · 70 · 60, và sổ ruby đúng một cặp dòng cho mỗi lượt.

### Kiểm

`pytest` **824 passed / 2 skipped / 5 deselected** (thêm 27 bài mới) · ruff + `mypy` strict (135 file) sạch · `tsc`, eslint, prettier sạch · `gen:api-types` không drift · `alembic upgrade head` **và** `downgrade` chạy thật trên một database trắng, `alembic check` không thấy lệch · bài kiểm đua chạy thật trên Postgres, đã xem nó ĐỎ khi gỡ khoá rồi XANH khi trả lại.

---

## 4aa. Petland lát 8 — gacha trứng, mua bằng ruby · 🟢 XONG (2026-08-27)

Lát 8 của [`ADR-010-PETLAND-V2.md`](ADR-010-PETLAND-V2.md) §9, mở khoá được nhờ §4z ở trên.

- [x] Migration `039_pet_gacha` — `pet_owned`, `egg_setting`, `pet_species.drop_weight`, `pet_state.rolls_since_rare`
- [x] `app/services/gacha.py` — quay theo trọng số, bộ đếm an ủi, trùng thì hoàn ruby
- [x] `GET /pet/eggs` (giá, số dư, bộ đếm, **bảng tỉ lệ**), `POST /pet/eggs/open`, `GET /pet/collection`
- [x] `GET/PATCH /admin/pet/eggs` + ô trọng số cho từng loài ở `/admin/pet`
- [x] Màn trứng trong bảng thú cưng (`components/petland-eggs.tsx`), có bảng tỉ lệ mở ra được
- [x] `tests/test_gacha.py` (10 bài) + một bài e2e, đã xem nó đỏ khi gỡ điều kiện `can_open`
- [x] Lát 9 — bộ sưu tập, đổi con đang nuôi (`PATCH /pet`), và khoảnh khắc nở trứng

**Mỗi con có chỉ số RIÊNG** (migration `040`): đói, sức, vui, XP, level và cả chỗ đứng dời từ `pet_state` sang `pet_owned`. Bản đầu của lát này làm ngược lại — một bộ chỉ số dùng chung cho cả góc, "đổi con giữ nguyên vị trí và nhu cầu", đúng chữ §9 của ADR-010. Đọc lại thì chữ ấy sai: nó nói rằng mọi con là **cùng một con mang hình khác nhau**, nên đổi con là con mới thừa hưởng độ no của con cũ trong khi con cũ mất sạch quá trình được chăm — và cả bộ sưu tập mất nghĩa. Giờ đổi qua đổi lại không mất gì và cũng không mượn được gì: con vừa chọn ra đúng như lúc nó được cất đi, con vừa cất tiếp tục đói theo đồng hồ thật. **Chỗ này thay cho câu ở ADR-010 §9.**

**Hai thứ Ở LẠI `pet_state` vì chúng thuộc về NGƯỜI CHƠI**: đang nuôi con nào, và bộ đếm an ủi của gacha (nó đo mấy quả trứng vừa mở, không đo con vật nào).

**Cặp `xp_today`/`xp_day` từng ở lại đó, và đó là một lỗi — migration `042` sửa.** Lý do viết ra lúc `040` nghe hợp lý: "trần XP ngày phải là trần của NGƯỜI, cho mỗi con một bộ đếm riêng thì ai có năm con là có năm lần trần". Cái sai lộ ra ngay khi dùng thật: **một con vừa nở ra không nhận nổi một điểm XP nào cho tới hôm sau**. Người ta mở trứng SAU khi đã chơi với con cũ, nên trần gần như luôn cạn đúng lúc con mới xuất hiện — chọc ba mươi cái mà `xp` vẫn 0, `level` vẫn 1, không có gì nói vì sao. Đo được trước khi sửa: chọc mèo 30 lần cho kịch trần, đổi sang con cua vừa nở, chọc mười lần nữa — `xp=0 lv=1` nguyên vẹn.

Chỗ lập luận trượt: **level là của TỪNG CON**, nên thứ trần ngày phải bảo vệ là "một con không lên max level trong một buổi", chứ không phải "một người không được chơi quá lâu". Trần theo từng con giữ nguyên tính chất ấy — mỗi con vẫn tối đa 30 XP một ngày — và điều nó cho phép thêm chỉ là một người có nhiều thú thì dành nhiều thời gian hơn cho cả bộ sưu tập. Đó là một trò sưu tầm đang hoạt động đúng: level của một con nói "con này được chăm bao nhiêu ngày", không nói "chủ nó rảnh bao nhiêu". `tests/test_pet_state.py::test_a_freshly_hatched_pet_can_still_earn_today` ghim lại.

Loài chưa sở hữu trả **404 chứ không 403**: nói "không có quyền" với một con vật là sai nghĩa, và 404 cũng không tiết lộ bảng loài cho người chưa mở được nó.

**Bộ sưu tập KHÔNG in "×2".** Mở trúng con đã có thì được hoàn ruby, nên bản thứ hai không phải một thứ người chơi đang giữ: in ×2 bên cạnh tên là nói rằng có hai con — trong khi chỉ có một — và ngụ ý con số ấy dùng được vào việc gì đó. Cột `copies` giữ lại làm LỊCH SỬ ("đã nở mấy lần"), thứ mà sổ ruby không kể được sau khi mức hoàn thay đổi, và nó nằm trong `title` cho ai tò mò.

**Con đầu tiên không đến từ quả trứng nào**, nên không có gì ghi nó vào `pet_owned` — tủ rỗng trong khi trên bản đồ đang có một con mèo, và đổi đi rồi là mất luôn con mèo vì "không sở hữu". `ensure_pet` ghi ở đường ĐỌC chứ không chỉ lúc tạo, nên nó tự đúng cho cả tài khoản cũ (đã có `pet_state` từ trước lát 8) lẫn tài khoản mới — rẻ hơn hẳn một migration đi vá dữ liệu cũ, và không ai phải nhớ chạy nó.

**Trứng RUNG trước khi nở**, và có một khoảng chờ tối thiểu 900ms. Trên máy nội bộ máy chủ trả lời trong vài chục mili giây, nên không có khoảng chờ ấy thì quả trứng chớp một cái rồi biến mất — mà thứ duy nhất một hệ gacha bán là đúng khoảnh khắc chưa biết mình được gì. Chờ THÊM chứ không bao giờ chờ lâu hơn: mạng chậm hơn nhịp rung thì không đợi thêm giây nào.

Kiểm thật trên stack: tủ của tài khoản mới có sẵn con mèo; mở 5 quả ra 4 loài; đổi sang loài chưa có trả 404. Và sau `040`: chăm con mèo tới no 0,970 / vui 1,000 / xp 6 rồi dời nó sang ô (11,5), đổi sang con hươu — hươu ra với 0,620 / 0,700 / xp 0 / ô (3,8) — chọc hươu một cái rồi quay lại mèo, mèo vẫn nguyên 0,970 / 1,000 / xp 6 / (11,5), trong khi `xp_today` chạy chung 6 → 7 → 7. Migration chạy thật trên database dev đang có dữ liệu: con đang nuôi giữ nguyên chỉ số, chín con còn lại trong tủ nhận mặc định.

**Hai chỗ lệch khỏi bản kế hoạch, cả hai đều là quyết định đã chốt với Samuel:**

**Không có `egg_token`.** ADR-010 §6.2 đề xuất một bộ đếm riêng kiếm từ nhiệm vụ ngày. ADR-011 thay nó bằng ruby, và lý do chính là lý do §6.2 đã dùng để loại XP: một bộ đếm không trả lời được câu "điểm này từ đâu ra, tiêu vào đâu". Đường tiêu đi qua `ruby.spend`, tức là qua khoá tư vấn — đó là điều kiện §5 của ADR-011 đặt ra trước khi mở bất kỳ đường tiêu nào.

**Trùng thì HOÀN RUBY, không đổi thành mảnh.** §6.3 viết "trùng thì đổi thành mảnh", và lập luận của nó đúng: mở quả thứ mười, nhận đúng con đã có, không được gì cả là trải nghiệm dạy người ta ngừng mở. Nhưng mảnh chỉ có nghĩa khi có chỗ tiêu, mà chỗ tiêu thuộc lát 9 — ship một con số người chơi không làm gì được với nó là đúng kiểu nửa vời dự án này vẫn tránh. Hoàn 10 trên 25 giữ nguyên ý định và tiêu được ngay. Ràng buộc **hoàn < giá** nằm ở cả database lẫn màn quản trị: hoàn bằng hoặc hơn giá là một cỗ máy in ruby.

**Một hạng trứng, không phải bảng `egg_tier`.** Với 12 loài, ba hạng trứng là chia một cái bể nhỏ thành ba ngăn rỗng. `egg_setting` là một hàng theo khuôn `progression_setting`; ngày cần nhiều hạng thì nó lên thành nhiều hàng.

**Trọng số, không phải phần trăm** (`pet_species.drop_weight`). Phần trăm phải cộng lại đúng 100, nên tắt hay thêm một loài biến cả bảng thành sai và ai đó phải chỉnh tay từng hàng. Trọng số tự chuẩn hoá, và **tỉ lệ in ra màn hình được tính từ chính bảng mà phép quay dùng** — hai phép tính là hai cơ hội để màn hình nói một đằng và máy làm một nẻo (§6.4). Migration đặt trọng số cho hàng cũ **theo hạng của chính nó**, không để nguyên mặc định: để nguyên thì mười hai loài rơi đều nhau và hạng hiếm hết hiếm — một thay đổi về tỉ lệ mà không ai ra lệnh.

**Một lỗi tự lộ ra khi viết màn này: nút thu gọn của góc thú cưng cắt sai ô.** Nó lấy số cột từ `SHEET_COLS.town` (12 — số cột của tấm NỀN) trong khi `creatures.png` có 10 cột, nên nó vẽ ra một mảnh của con khác — đủ giống một con thú để không ai nhận ra là sai. Hình học của tấm ghép giờ là `CREATURE_COLS`/`CREATURE_ROWS` trong `petland-sprite.ts`, tệp vốn đã là chỗ duy nhất biết "một loài trông ra sao".

**Và một cái bẫy của Tailwind bị chặn trước khi kịp xảy ra:** cỡ ô sinh vật đặt bằng `style` chứ không bằng `h-${size}`. Tailwind quét mã nguồn bằng văn bản, nên một tên lớp chỉ tồn tại lúc chạy **không sinh ra CSS nào** — cùng lớp lỗi với `-inset-[25%]` của khung avatar, và cũng im lặng y như thế.

### Kiểm

`pytest` **834 passed / 2 skipped / 5 deselected** · ruff + `mypy` strict (136 file) sạch · `tsc`, eslint, prettier sạch · `gen:api-types` không drift · `alembic upgrade` **và** `downgrade` chạy thật trên database trắng, `alembic check` không thấy lệch · Playwright petland **6 bài xanh**, bài mới đã xem ĐỎ khi gỡ điều kiện `can_open` · chạy thật trên stack: mở 12 quả liên tiếp, bộ đếm an ủi về 0 đúng lúc ra hạng hiếm, trùng hoàn đúng 10 ruby, và `GET /pet/collection` khớp với những gì đã nở.

**Chú ý khi kéo nhánh này về:** database dev đã có `ruby_event`, `ruby_rule`, `pet_owned`, `egg_setting` do `create_all` của container `api` tạo, nên `alembic upgrade head` sẽ chết với `relation already exists` — trong khi hai cột MỚI trên bảng cũ (`drop_weight`, `rolls_since_rare`) thì vẫn thiếu, vì `create_all` không sửa bảng đã có. Đúng cái bẫy CLAUDE.md đã ghi. Cách ra: `docker compose stop api`, `DROP TABLE ruby_event, ruby_rule, pet_owned, egg_setting CASCADE`, rồi `alembic upgrade head`.

---

## 4aj. Chọn giọng theo dàn narrator của đề thật · 🟡 mã xong, CHƯA sinh lại audio (2026-09-01)

Đề tự sinh đang dùng cả **tám** giọng logic và rải chúng bằng `pool[(index + seed) % len(pool)]`. Hai chỗ sai, và không phép kiểm nào thấy được:

- **Bốn trong tám giọng không tồn tại trong đề thật.** Đề thật có bốn narrator với cặp quốc tịch–giới tính cố định: Mỹ nữ, Canada nam, Anh nữ, Úc nam. Mỹ nam, Canada nữ, Anh nam, Úc nữ thì không có. `PART1_VOICES` cũ lệch hai trên bốn, và `VOICE_FOR_ACCENT` của từ vựng cũng vậy.
- **`PART3_CASTS` ép CÙNG accent trong một cuộc hội thoại — ngược hẳn đề thật.** Vì giới tính gắn cứng vào quốc tịch, một hội thoại hai người (một nam một nữ) luôn là hai quốc tịch khác nhau. Comment cũ biện minh bằng ràng buộc `audio_asset.accent` một giá trị, vốn đã được `backfill_audio._accent_of` gỡ từ trước.
- **Xoay vòng không phải ngẫu nhiên, nó là đếm.** 25 câu Part 2 trên tám cặp lặp lại đúng thứ tự ấy ba lần; `seed` chỉ dịch điểm bắt đầu.

`TOEIC_NARRATORS` vào `app/core/media.py` (sự thật về miền, cả ba khu vực dùng chung — xem PHASE2-AUDIO §A4.6); `_deal` chia đều theo seed và `_spread` đẩy hai ô liền nhau ra xa; `_casting_problems` đặt luật ở tầng part: mỗi accent 15–35% số lượt nói, không ba ô liền nhau chung dàn giọng. Từ vựng và dictation chuyển sang cùng dàn — người học gặp bốn giọng ấy trong phòng thi.

**Chất lượng: hai nguyên nhân tách biệt.** Thư viện đang có **hai tốc độ đọc** — 2 571 clip ở `engine_version` 1 (+0%, ~188 wpm) và 1 529 ở version 2 (−20%, ~151 wpm), nên một đề trộn cả hai. `media_state` cố ý không coi version cũ là STALE, nên chuyện này không tự khỏi. Và giọng Mỹ chuyển sang thế hệ HD của edge-tts (Ava/Andrew thay Jenny/Guy); `en-GB`, `en-AU`, `en-CA` **không có** lựa chọn tương đương, nên chênh lệch chất lượng theo accent là giới hạn đã biết chứ không phải thứ bỏ sót. `tts_engine_version` lên **3** — bắt buộc, vì đổi `_EDGE_IDS` mà giữ version là hai người đọc chung một tên giọng và `media_state` báo CURRENT cho cả hai.

Ô chọn giọng ở `/admin/tests/[slug]` xếp bốn narrator lên đầu và đánh dấu ★ (`VoiceOption.narrator`, contract đã sinh lại) — trước đó mặc định của một lượt mới rơi vào `au_female_1`, một cặp đề thi không có.

### Kiểm

ruff + mypy strict sạch, `tsc --noEmit` sạch, contract đã regenerate. Quét 60 seed qua cả bốn part nghe: tỉ lệ accent nằm trong dải **24–27%**, **0/60 seed** bị `validate` từ chối. **Chưa chạy pytest** và **chưa sinh lại audio.**

### Bug tìm được khi trả lời "đề cũ có được cập nhật không"

**`--force` chưa bao giờ với tới audio của đề.** `backfill_questions` không nhận `policy` cả — nó so thẳng `script_state(...) not in _REGENERATE`, nên cờ `--force` bị bỏ qua im lặng ở đúng chỗ nó cần nhất. Và nó cần nhất ở đây: `script_state` hỏi "clip này có đọc đúng lời thoại này không", nên đổi tốc độ đọc hay đổi ánh xạ `_EDGE_IDS` đều để nó trả `CURRENT` — audio của đề sẽ **không bao giờ** được thu lại. Sửa: `backfill_questions(factory, limit, policy)`. Hai test mới trong `tests/test_backfill_questions.py`, đã kiểm ĐỎ khi bỏ fix (`--force` sinh lại được clip còn khớp lời thoại; `--force` vẫn KHÔNG ghi đè bản thu người tải lên, vì `EXTERNAL` chặn trước cả `force`).

### Đổi dàn giọng cho đề đã dán: `recast_voices.py`

Giọng nằm trong `audio_script` — dữ liệu — nên `TOEIC_NARRATORS` không với tới đề cũ. `app/content/recast_voices.py --test <slug>` ánh xạ từng giọng ngoài dàn sang narrator **cùng giới**, tránh trùng giọng trong một ô, và chọn accent đang ít lượt nhất nên cả đề tự tiến về 25% mỗi accent. Giữ giới tính là ràng buộc load-bearing: Part 3/4 hỏi thẳng "What does the **man** say?", nên lật giới tính một lượt là làm câu hỏi sai đáp án và không phép kiểm nào thấy. Ô có nhiều người cùng giới hơn số narrator (dàn chỉ có hai nữ, hai nam) thì **báo ra, không đoán** — đoán nghĩa là hai người nói chung một giọng.

Sau khi đổi, lời thoại khác đi nên `script_state` trả `STALE` cho đúng những ô ấy: một sweep thường thu lại chúng, không cần `--force`.

`backfill_audio` thêm `--test <slug>`: ép thu lại tốn hàng giờ và không hoàn tác được, nên phải thử được trên một đề trước khi áp cho cả kho (162 ô).

### Chạy thật trên tp-form-07 (2026-09-01)

Trạng thái trước: 54 ô có lời thoại, **10/13 hội thoại Part 3 cùng một accent** (4 cuộc toàn Úc, 3 toàn Canada, 2 toàn Anh, 1 toàn Mỹ), và 105/211 lượt nói dùng bốn giọng đề thật không có — `au_female_1` nhiều nhất với 33 lượt. Sau recast: 40/54 ô đổi, 0 ô phải sửa tay, còn đúng bốn giọng với tỉ lệ 24–26% mỗi accent. Bốn bất biến được kiểm bằng mô phỏng trước khi ghi (giới tính từng lượt giữ nguyên, mọi giọng trong dàn, số người nói không đổi, Part 2/3 nhiều người thì khác accent) — không vi phạm nào.

**Tệp dán và `blueprint.json` cũng phải theo, nếu không chúng thành lời khai sai.** `commit_part` CỘNG THÊM câu chứ không ghi đè, nên tệp cũ không âm thầm hoàn tác được database — nhưng chúng vẫn ghi dàn giọng cũ, và một ô sinh bổ sung về sau sẽ lấy dàn cũ từ blueprint, cho ra một đề trộn hai dàn. `--files-only` lấy **database làm nguồn sự thật** rồi viết ngược ra tệp, chứ không chạy lại bộ lập ánh xạ — chạy lại là hai lượt lập độc lập và chúng có thể ra hai kết quả khác nhau, đúng thứ việc này sinh ra để dọn. Nối tệp với hàng bằng NỘI DUNG lời thoại chứ không bằng tên tệp, vì tên tệp là id ô của blueprint và không có gì bảo đảm ô `p3-01` là hàng nào. Kết quả trên tp-form-07: 40 tệp dán + 40 ô blueprint, 0 tệp không nối được, và `git diff` xác nhận **không dòng nào ngoài `voice:` thay đổi**.

**Bài học vận hành: phải `docker compose stop worker` trước khi chạy backfill bằng tay.** Lần chạy đầu chết vì `DeadlockDetected` — `tts_worker` trong container đang quét cùng lúc và hai bên khoá chéo nhau trên `question`. Tệ hơn nữa là nó im lặng: lệnh chạy qua `| tail` nên exit code báo về là của `tail`, và stdout bị đệm khối khi qua pipe nên traceback (stderr) in ra TRƯỚC các dòng "synthesised", làm bản log đọc như một lượt chạy trót lọt. Và container worker chạy mã đã import lúc khởi động, nên kể cả khi nó thắng cuộc đua thì nó thu bằng `_EDGE_IDS` cũ.

### Còn phải làm

`uv run python -m app.content.backfill_audio --force` để cả thư viện về một tốc độ (~4 100 clip), rồi `push_media` và `reconcile_media --delete-rows` dọn hàng cũ không còn ai trỏ tới.

**Đề đã dán từ trước chỉ đổi tốc độ, không đổi dàn giọng.** Tên giọng nằm trong `question.audio_script` / `question_set.audio_script` — dữ liệu, không phải mã — và backfill đọc thẳng `turn["voice"]` từ đó. Giọng Mỹ thì có đổi (script ghi `us_female_1`, và tên ấy giờ trỏ sang Ava). Từ vựng và dictation ngược lại: giọng được TRA lúc sinh, nên `--force` đổi luôn cả dàn. Muốn đề cũ theo dàn mới thì cần một script viết lại `audio_script`, chưa có.

---

## 4ai. Trợ lý biết dùng tài liệu và biết tự tra số · ✅ XONG (2026-08-29)

Hai lát nối tiếp 4ah: Trợ lý trả lời dựa trên **knowledge base về chính trang** thay vì một khối SITE_GUIDE cứng, và tự **GỌI CÔNG CỤ** lấy số cá nhân thay vì nhận cả đống số sẵn trong ngữ cảnh.

**Knowledge base là FILE trong git, bảng chỉ là bản tính sẵn.** `content/kb/*.md` — frontmatter `ref`/`title`/`keywords` cộng thân bài — đồng bộ vào bảng `knowledge_chunk` (migration `051`) bằng `app/content/sync_kb.py`; file mất khỏi thư mục là hàng bị xoá, và `embed_kb` dọn luôn vector mất gốc trên Pinecone (`list_ids` + `delete`) — không dọn thì "xoá tài liệu" chỉ xoá được một nửa. Nội dung đi qua review như mã. Lỗi thật ngày đầu: `DEFAULT_DIR` trỏ nhầm `app/content/kb` (rỗng) và sync XOÁ SẠCH 16 hàng — đã sửa đường dẫn và ghi vết trong comment, kèm một test chặn parse file hỏng.

**Truy hồi lai: vector là chính, lexical là đường lui.** Embeddings qua cổng tương thích OpenAI của Google (`gemini-embedding-001`, 3072 chiều, khoá `GEMINI_API_KEY` tái dùng) — b.AI TỪ CHỐI embeddings ("HTTP node only allows..."), quyết định đó là do thử thật. Vector nằm ở **Pinecone** (lựa chọn của người vận hành; pgvector đã bật nhưng giữ nguyên) — adapter httpx thẳng không SDK, đúng khuôn `openrouter.py`; index serverless tự tạo bằng `embed_kb --create-index`, chiều lấy từ vector thật chứ không từ hằng số. `search_knowledge` thử vector trước, MỌI hỏng (mất khoá, sập, index chưa có) thì log warning và rơi về tra lexical trong Python — Pinecone là phụ thuộc mềm, cùng hạng Redis ở `rate_limit_anonymous`. Suite chặn đường vector ra mạng bằng cách để trống hai khoá trong `conftest.py` — một lượt gọi mạng trong test là một test phải biết mình đang test gì.

**Bốn công cụ tra dữ liệu CỦA CHÍNH NGƯỜI HỌC:** `trang_thai_hoc_tap`, `luot_thi_gan_day`, `vi_ruby`, `huy_hieu` — schema đúng giao thức OpenAI, thực thi bằng `profile_stats`/`progression`/`ruby`/`user_badge`. Tool KHÔNG nhận `user_id`: nó đọc user của request, nên không tồn tại đường đọc dữ liệu người khác. `LLMRequest` thêm `messages` (vòng tool) và `tools`; cả bốn adapter đều passthrough + parse `tool_calls` (ollama trả arguments là DICT, phải serialize lại). Vòng tool chặn 3 lượt gọi model — hết 3 vẫn xin tool thì hỏng TOÀN LƯỢT, vì câu trả lời thiếu số là câu bịa. JSON hỏng từ model là DỮ LIỆU trả về cho model (nó tự sửa), không phải exception. Số cá nhân rời khỏi ngữ cảnh tĩnh: câu không liên quan tiết kiệm cả đống token, câu có liên quan nhận số THẬT lúc hỏi.

**Đếm chi phí vòng tool đi qua `Gateway` như mọi lượt gọi** — mỗi vòng một hàng `ai_interaction`, `ai_budget` chặn trên tổng.

**Gộp lại bản review d9c1e92 bị ghi đè:** lượt viết tool loop đã đè mất `_find`/`_open` (get-or-create chống đua) — đã gộp lại: tìm cuộc trước, gọi model, mở cuộc SAU khi gọi (model hỏng không để lại cuộc rỗng), `IntegrityError` đọc lại. Test chống đua với `Barrier` trong `test_concurrency.py` xanh lại.

### Kiểm

`pytest` **913 passed / 2 deselected**, trong đó 23 test mới (6 registry provider, 10 knowledge, 7 vòng tool); ruff + mypy strict sạch. Chạy THẬT đầu-cuối trên dev stack với `bai/glm-5.3-flash`: câu quy tắc → chunk đúng + trích dẫn `[dictation]`; câu cá nhân → tool trả số thật (19 XP, 4 từ đến hạn). Lỗi được bắt nhờ chạy thật: Google trả `data` KHÔNG có `index` (giữ thứ tự phản hồi khi thiếu), và `max_tokens` 900 bị model ăn hết vào thinking rồi CẮT GIỮA CÂU (`finish_reason=length`, đo thật) — trần lên 3000; cap cao không tốn thêm vì tiền tính theo token thật sinh ra.

### Ba bug review bắt được sau khi lát xong (2026-08-30)

- **Dry-run của `sync_kb` GHI THẬT.** `sync_knowledge` tự `db.commit()` bên trong, mà `Session.commit()` commit giao dịch ngoài cùng và thả savepoint — `rollback()` sau đó là vô dụng; `begin_nested` không cứu được. Chạy thật chứng minh: sau dry-run, hàng vẫn nằm trong bảng. Sửa: sync không commit, caller commit (`sync_kb` đường thật, `embed_kb`); dry-run chỉ còn sync + rollback. Kèm phát hiện `vars(result)` trên dataclass `slots=True` raise TypeError — dry-run chưa từng chạy được trọn.
- **Vector trả ref bảng không còn thì không rơi về lexical.** `search_knowledge` lọc ref mất gốc rồi trả `[]` mà không thử lexical — "xoá file chưa embed lại" biến thành "không có tài liệu". Sửa: mapped rỗng thì rơi xuống lexical.
- **`embed_kb` quảng cáo `[--dry-run]` mà argparse không có cờ** — đã bỏ khỏi docstring.

Hai test mới chặn (mỗi bug một test, đã kiểm ĐỎ khi bỏ fix): `test_SYNC_khong_tu_COMMIT` và `test_TRA_VECTOR_ref_mat_GOC_thi_RO_ve_LEXICAL`. Suite sau sửa: **917 passed / 2 deselected**, ruff + mypy sạch.

### Ba bug nữa từ review 2026-08-30

- **`_tool_recent_attempts` — `int(args.get("limit", 3))` không bọc try → model gửi arg kiểu sai thành 500.** `_execute` chỉ bọc `json.loads` trong try, `impl` nằm ngoài. Sửa: bọc `impl(db, user, args)` trong try/except và trả error về model, nhất quán với thiết kế "JSON hỏng là dữ liệu, không phải exception". Kèm test `test_CONG_CU_LOI_thi_tra_LOI_ve_model_khong_phai_500`.
- **`PineconeVectorStore.list_ids` — `pagination_token` sai tên.** Pinecone Data Plane API dùng `paginationToken` (camelCase), không phải `pagination_token`. Sửa: `pagination_token` → `paginationToken`. Với namespace nhỏ dưới 100 vector thì không sao; với lớn hơn thì không phân trang được.
- **`knowledge_chunk.updated_at` không bao giờ được ghi trên sync.** Model có `server_default=func.now()` nhưng không có `onupdate`. Các model khác trong project dùng `onupdate=func.now()`. Sửa: thêm `onupdate=func.now()` vào cột. Kèm test `test_SYNC_sua_noi_dung_thi_MOI_updated_at` (đã kiểm đỏ khi bỏ fix).

Còn mở: đường vector chưa có ngưỡng cosine (câu lạc đề vẫn nhận đủ 4 chunk khi có khoá — cần đo thật trên `gemini-embedding-001`), và timeout request-path 60s+30s+30s ≈ 120s worst case trước khi rơi lexical.

---

## 4ah. Trợ lý AI trang web · ✅ XONG (2026-08-29)

Tính năng AI thứ hai của lớp học viên, và lần này **không neo vào lượt làm bài**: người học hỏi về chính trang web — tính năng nào ở đâu, một quy tắc hoạt động ra sao — và về tiến độ của chính họ. Bốn mảnh: `services/assistant.py` (ngữ cảnh + gọi model), `routes/assistant.py` (`POST/GET /api/v1/assistant/chat`), migration `050` (`coach_conversation.attempt_id` thành nullable), và màn `/learn/assistant` kèm mục "Trợ lý AI" ở sidebar. Feature key riêng `assistant_chat` — tắt trợ lý không tắt coach, cấu hình ở `/admin/ai` như mọi tính năng AI khác.

**`attempt_id NULL` là dấu hiệu phân loại, không thêm cột `kind`.** Hai nguồn sự thật cho cùng một phân loại sẽ lệch nhau ở lần đầu ai đó đặt `kind` không khớp `attempt_id`, và không gì báo sự lệch đó. `chat.ask` (đường coach) được kiểm chặn cuộc hội thoại `attempt_id NULL` thay vì tin — chạy nó với ngữ cảnh rỗng vẫn thu tiền.

**Không dùng `Retriever`/`Anchor`.** Ngữ cảnh của trợ lý là (1) bản hướng dẫn trang **viết tay trong mã** (`SITE_GUIDE` — nhỏ, tĩnh, đi qua review như code, sửa cùng commit với tính năng nó mô tả) và (2) số liệu thật suy ra từ đúng các service giao diện đang dùng (`profile_stats`, `progression`, đếm lượt nộp). Tự kỳ công một phép tìm kiếm trên văn bản vài nghìn ký tự chỉ tạo ảo giác rằng hệ thống đang RAG. Ngày RAG tới (ADR-003 §3.3), nguồn thứ ba nối vào đúng một chỗ.

**Không cổng "nộp bài mới hỏi".** Cổng đó của coach tồn tại vì ngữ cảnh là chính lượt làm bài — cho hỏi khi chưa nộp là cho xin đáp án. Trợ lý không nhìn thấy lượt nào, không có gì để gian lận. Một người **một** cuộc hội thoại cuốn theo, vì trợ lý nói về cùng một trang web.

**An toàn prompt injection giữ nguyên khuôn coach:** lịch sử đi vào lượt NGƯỜI DÙNG, không nối vào `system` — test khẳng định chữ lượt trước không bao giờ xuất hiện trong `system` của lượt sau. Hạn mức riêng 40 request/giờ, `BudgetExceeded` → 429, tính năng tắt → 503, và cả hai cổng đều fail **closed** vì mỗi tin nhắn là tiền thật.

**`_gateway_for` tách thành `deps.get_gateway`.** Hai router AI cần cùng một bản dựng gateway; bản sao thứ hai sẽ trôi khỏi bản đầu khi thêm nhà cung cấp.

**Và đường phục vụ lần đầu biết nói với Google/Groq/Cerebras.** Pipeline offline đã lâu nay dựng adapter từ bảng `ENDPOINTS` + quy ước `<tên>_api_key`, nhưng `get_gateway` — đường phục vụ — chỉ dựng ollama + openrouter cứng: admin chọn được `google/gemini-…` ở `/admin/ai` (model CÓ GIÁ, hợp lệ), rồi lượt gọi thật chết bằng KeyError 500. Giờ cả hai phía đi qua **một** builder (`llm/providers.py`): đường phục vụ gom tên provider từ routes lẫn mọi hàng `ai_feature_config`, thiếu khoá thì bỏ qua provider đó (`strict=False` — tính năng A trỏ sai không kéo sập tính năng B), và Gateway thiếu adapter giờ ném `LLMError` 503 có ghi sổ thay vì KeyError. 6 test mới ở `test_llm_providers.py`.

**Provider custom là FILE CẤU HÌNH, không phải mã** (`apps/api/llm_providers.json`, đổi đường bằng `LLM_PROVIDERS_FILE`). Ba thứ từng nằm ở ba tệp mã — endpoint (`ENDPOINTS`), khoá (`<tên>_api_key`), giá (`pricing._RATES`) — giờ khai một chỗ: base_url, tên biến môi trường chứa khoá, bảng giá. Thêm Mistral/DeepSeek/Together là sửa file cộng đặt khoá, không deploy mã; `pricing` và `known_models()` (danh sách model của `/admin/ai`) đọc chung nguồn đó. Hai luật không bị phá: **khoá không bao giờ nằm trong file** (file được commit — file chỉ *nhắc tên* biến môi trường, cùng lý do `AiFeatureConfig` không có cột khoá), và **model không có ở đâu cả vẫn bị từ chối** — file là nguồn giá, không phải lối né phép kiểm (N4). File được đọc MỖI lượt cần, không cache, cùng lập luận với `resolver_for`; file sai thì CLI chết ngay còn đường phục vụ log warning và coi như rỗng. Mục ghi đè builtin bị từ chối ở cả hai chế độ — để nó "hiệu lực giả" là kiểu hỏng im lặng tệ nhất. 10 test mới ở `test_llm_registry.py`, trong đó một test chỉ ra vì sao nội dung hỏng phải ghi vào file tmp chứ không vào file mẫu.

### Kiểm

`pytest` **901 passed / 2 deselected**, trong đó 28 test mới (12 trợ lý, 6 builder provider, 10 registry): ngữ cảnh mang số thật, cặp hỏi–đáp ghi đúng thứ tự, lịch sử lượt trước vào lượt user (không vào `system`), một người một cuộc, đường coach từ chối cuộc không neo, 401/422/503/429 ở endpoint, và happy path qua `FakeProvider` cắm ở đúng seam (`get_gateway` bị monkeypatch — router không đổi). ruff + mypy strict sạch; `tsc`, eslint sạch; `gen:api-types` sinh lại không lệch.

---

## 4ag. Ao nước đi vào được, và con thú bơi · ✅ (2026-08-28)

Mười hai ô ao trong `map.json` vốn bị đánh dấu **cản đường** — cái hồ là một bức tường có màu xanh. Giờ mở ra, và khi con thú xuống nước thì nó chìm một phần: khung ảnh bị cắt đúng ở mặt nước, kèm một vòng gợn quanh chân.

**Cắt KHUNG ẢNH, không dùng mặt nạ.** Con thú chỉ có một khung 16×16 (ADR-010 §14.5), nên "một phần chìm" nghĩa là vẽ ít pixel hơn — rẻ hơn hẳn một lượt vẽ mặt nạ, và với `anchor` ở đáy thì mép cắt chính là mặt nước. Texture cắt sẵn được nhớ lại và chỉ đổi khi đổi loài hoặc khi xuống/lên khỏi nước; dựng `Texture` mỗi khung là dựng một đối tượng GPU sáu chục lần mỗi giây cho một tấm ảnh không đổi.

Dưới nước thì **bỏ cái nhún của bước chân** và thay bằng nhịp bập bềnh chậm hơn, lệch pha với nhịp thở: cái nhún là nhịp chân chạm đất, giữ nó dưới nước thì con thú trông như đang chạy trên mặt hồ. Vệt sáng của bậc hiếm cũng tắt dưới nước — vệt là dấu chân, mà gợn nước đã nói việc ấy rồi.

**Hai chỗ chỉ nhìn mới thấy, và cả hai đều đã sửa nhờ chụp ảnh canvas rồi phóng to:**

- **Ô số 1 của tấm ghép `water` là CỎ**, được dùng 99 lần trong bản đồ. Phép thử `sheet === "water"` — thứ ai cũng viết đầu tiên — sẽ biến gần hết bãi cỏ thành ao.
- **Ranh giới nằm ở ĐÁY ô, không phải giữa ô.** Con thú neo ở đáy ô, nên thứ quyết định nó đứng hay bơi là cái nằm dưới chân. Bản đầu tính cả chín ô của bộ ghép 3×3, và ảnh chụp cho thấy con thú bị cắt ngang kèm gợn nước **trong khi đang đứng hẳn trên cỏ** ở hàng dưới. Nước giờ là sáu ô: hàng trên (cỏ ở nửa trên, nước ở dưới) và hàng giữa.

Khách không đứng giữa ao (`spotNear` loại ô nước): con thú thì bơi được, còn một NPC lội tới ngực giữa hồ để giao bài tập thì đọc ra là đặt sai chỗ. Con thú **tự đi lang thang xuống nước được** — đó là chủ ý.

`check-petland-walk.mjs` ghim ba điều: 12 ô ao đi vào được, đúng 6 ô tính là nước, và 99 ô cỏ cùng tấm ghép không bị nhầm. Đã xem đỏ với cả hai lỗi trên.

---

## 4af. Bậc hiếm thứ sáu: "thần" · ✅ (2026-08-28)

**Không phải tải thêm tài nguyên nào.** `creatures.png` (Tiny Creatures — Clint Bellanger, CC0) có 180 ô, trong đó **hơn một trăm sinh vật huyền thoại**, và bốn mươi loài hiện tại mới dùng 40 ô. Năm ô của bậc thần đều nằm sẵn ở đó và chưa loài nào lấy: bốn nguyên tố ở hàng 4 (45–48) và một ô thiên thần có vầng hào quang ở hàng 3 (37).

Chọn bằng MẮT chứ không bằng phỏng đoán: `scripts/png.mjs` không đọc được PNG bảng màu (color type 3), nên phải viết thêm một bộ giải mã bảng màu trong thư mục nháp để dựng bảng ô phóng to rồi nhìn. Đó là cách duy nhất trả lời được "ô nào trông ra dáng thần nhất".

| Loài | Ô | |
|---|---|---|
| Thần Lửa | 45 | nguyên tố lửa |
| Thần Nước | 46 | nguyên tố nước |
| Thần Đá | 47 | nguyên tố đá |
| Thần Bão | 48 | nguyên tố gió |
| Thiên Thần | 37 | vốn nằm trong hồ NPC; lấy ra thì hồ ấy còn 5 ô, và hai thiên thần còn lại (35, 36) ở lại làm khách |

**Màu chủ đạo là tím đen, và nó phải thành một TOKEN MỚI của hệ thiết kế** (`--myth` / `--myth-tint`). Bốn token trạng thái đã dùng kín cho năm bậc; bậc thứ sáu không còn gì để mượn, mà mượn lại một cái là bắt một màu mang hai nghĩa. Đây cũng là ví dụ rõ nhất cho việc vì sao một token có hai giá trị: tím đen đọc rất tốt trên nền sáng (13.06:1) nhưng ở chế độ tối thì tím đen trên nền tím đen là một nhãn vô hình, nên giá trị tối là một sắc tím **sáng** (6.73:1). Cả sáu tổ hợp đều đạt AA — đã đo.

**Thang vòng sáng phải chia lại, không phải nhét thêm một số lớn hơn 1.** Sáu bậc giờ là 0,2 / 0,36 / 0,52 / 0,68 / 0,84 / 1 — khoảng cách vẫn đều, nên vẫn đọc được từ xa mà không cần chú thích.

**Tiết mục thứ năm: `float`** — con thú bậc thần lơ lửng, chân không chạm đất, nhấp nhô chậm hơn nhịp thở nên hai chuyển động không trùng pha. Vòng sáng vẫn bám ĐẤT (nó dùng `footY`, không dùng `pet.y`), và chính khoảng hở giữa chân với vòng sáng mới là thứ đọc ra "đang bay".

**Migration `047` CHÈN năm hàng, khác thói quen của bảng loài** — và đó là một cân nhắc chứ không phải một lần quên. Bảng loài là dữ liệu admin sửa được, gieo lười chỉ chạy khi bảng còn rỗng, mà mọi cài đặt đã chạy đều có bảng khác rỗng. Không chèn nghĩa là năm loài mới không xuất hiện ở đâu cả — một tính năng tồn tại mà không tồn tại, đúng cái lỗi vừa phải sửa cho `/admin/petland`. Lằn ranh là `ON CONFLICT (code) DO NOTHING`: chỉ THÊM mã chưa từng có, không đụng vào nhãn, ô, trọng số hay công tắc mà người vận hành đã chỉnh.

Trọng số 1 (một nửa huyền thoại): **0,10% mỗi loài, 0,5% cho cả bậc** — khoảng một trong hai trăm quả trứng. Con số này là HÀNG dữ liệu, sửa được ở `/admin/pet` mà không cần triển khai lại.

**Một bẫy cũ lại bắt được:** database nháp `toeic_test` còn giữ ràng buộc CHECK năm bậc, nên bài kiểm đua gieo bảng loài đỏ với `0 == 45` — mọi luồng chèn đều vi phạm CHECK, `all_species` nuốt lỗi đúng như thiết kế, và kết quả là một bảng rỗng không kèm lỗi nào. Dựng lại database nháp là xong, đúng như CLAUDE.md đã ghi.

---

## 4ae. Ba chỉ số nói lên điều gì, và độ hiếm khác nhau ở đâu · ✅ XONG cả năm lát (2026-08-28)

Quyết định và lý do ở [`ADR-013-PET-CONDITION.md`](ADR-013-PET-CONDITION.md). Tài liệu đầu tiên của góc thú cưng không thêm tính năng nào: nó sửa một thứ đã dựng xong nhưng không có nghĩa.

**Chẩn đoán, bằng sự kiện chứ không bằng cảm giác:** `PetView` — thứ duy nhất tầng vẽ nhận được — **không có trường nhu cầu nào**, nên con thú đói và con thú no được vẽ giống hệt nhau. Ba chỉ số chỉ ảnh hưởng tới đúng ba cái nút đổi chính chúng, và cột **Vui không ảnh hưởng tới bất cứ thứ gì**. Độ hiếm thì chỉ quyết định khó kiếm tới đâu và vòng sáng màu gì.

Hai quyết định chốt trước vì chúng định hình mọi thứ còn lại, và cả hai là lựa chọn của người dùng:

- **Chỉ số KHÔNG chạm ra ngoài bảng** — không ruby, không XP, không nhịp sinh chạm mặt. Một chỉ số chăm sóc mà quyết định giá trị của việc học là đúng thứ mà luật "gamification không đổi thứ đã học được" cấm, chỉ khoác một cái áo dễ chịu hơn.
- **Độ hiếm khác ở HÀNH VI, không ở sức mạnh.** Cộng lực theo bậc sẽ biến gacha thành đường tăng sức mạnh trong một ứng dụng học.

**Hệ quả phải nhìn thẳng: phần thưởng duy nhất còn lại là chính con thú.** Không có con số nào bù vào. Nên tầng biểu cảm là toàn bộ tài liệu ấy chứ không phải phần trang trí của nó — làm lấy lệ thì ba chỉ số vẫn vô nghĩa, chỉ là vô nghĩa một cách đẹp hơn.

- [x] Lát 1 — `PetView.condition` + tư thế theo tình trạng: ngồi bệt khi kiệt sức, nghiêng người và thở chậm khi đói, thở nhanh và nhảy tại chỗ khi vui
- [x] Lát 2 — một dòng CHỮ tình trạng trong HUD, cạnh ba cái thanh không nhãn
- [x] Lát 3 — bong bóng cảm xúc, **thỉnh thoảng** chứ không thường trực (14 giây một lần, im lặng khi bình thường và khi đang ngủ)
- [x] Lát 4 — tự đi lang thang, phạm vi theo tình trạng (2 / 4 / 6 ô)
- [x] Lát 5 — vốn tiết mục theo bậc hiếm: `bounce` (uncommon) → `trail` (rare) → `watch` (epic) → `greet` (legendary)

**Tầng vẽ nhận MỘT TỪ, không nhận ba con số.** `PetView.condition` là kết quả đã quyết của `conditionOf`, cùng luật với `glow` và `sky`: tầng vẽ vẽ thứ nó được bảo vẽ. Đọc ngưỡng ở cả hai nơi là dựng bộ ngưỡng thứ hai, và nó lệch vào đúng ngày ai đó chỉnh một con số — lúc ấy con thú ngồi bệt trong khi dòng chữ nói nó vui vẻ.

**Chuyến tự đi KHÔNG ghi vị trí lên máy chủ** (`ambient`). Một `PUT` mỗi mươi giây suốt lúc bảng mở là cái giá không ai xin, và chỗ đứng do chính nó chọn thì cũng chẳng ai nhớ để mà tiếc. Người dùng ra lệnh — bấm chuột, bấm phím, bấm "Đi dạo" — thì cờ ấy tắt và vị trí lại được ghi như cũ.

**Bốn luật mới nằm ở tầng thuần và được `check-petland-walk.mjs` đo**, cả bốn đã xem đỏ: kiệt sức thì không tự đi; càng khoẻ càng đi xa; xin giảm chuyển động thì không tự đi; và **vừa đói vừa kiệt sức thì là kiệt sức** — ca cuối là ca quyết định, thiếu nó thì đảo thứ tự ưu tiên không làm bài kiểm đỏ.

**Vốn tiết mục cộng dồn, và không tiết mục nào làm con thú mạnh hơn.** `bounce` là nhảy tại chỗ kể cả lúc chỉ bình thường — con thường chỉ nhảy khi vui; `trail` để lại vệt mờ dưới chân khi đi; `watch` quay mặt theo con trỏ lúc đứng yên; `greet` đi về phía khách thay vì lang thang ngẫu nhiên. Bậc trên có tất cả những gì bậc dưới có, nên nhìn hai con cạnh nhau là biết con nào hiếm — mà không con nào hơn con nào. `check-petland-walk.mjs` ghim tính cộng dồn ấy và ghim cả chuyện bậc lạ rơi về mốc không.

**`greet` KHÔNG mở thẻ nhiệm vụ khi tới nơi.** Húc vào khách chỉ tính khi NGƯỜI DÙNG đang lái (ADR-012), và một cái thẻ tự bật ra vì con thú đi ngang qua là một cửa sổ chen ngang.

**Bài kiểm ảnh chụp KHÔNG ghim được "khung cảnh đứng im", và đó là kết luận sau bốn lần thử.**

| Cách | Kết quả |
|---|---|
| Chụp cách nhau 600ms | Đỏ khoảng **một lượt trong ba** — lớp phủ bầu trời nội suy theo giờ Petland (một ngày = một giờ thật) và thỉnh thoảng vượt một bậc màu ngay giữa hai tấm |
| Nới lên 4,5 giây để ôm trọn một chuyến tự đi | Đỏ **mọi lượt**, cùng lý do |
| `page.clock` đóng băng đồng hồ tường | Đỏ **mọi lượt** — bảng còn nhiều thứ chạy theo bộ hẹn giờ |
| Chụp liền nhau, không chờ | Hết chập chờn, nhưng **thôi bắt được gì**: gỡ hẳn chốt giảm-chuyển-động của nhịp thở mà bài vẫn xanh |

Cửa sổ đủ rộng để thấy chuyển động cũng đủ rộng để bầu trời trôi. **ADR-010 §10 đã viết sẵn kết luận này từ đầu — "phải kiểm bằng mắt chứ không bằng test"** — và tôi mất bốn lượt thử mới tin. Bài e2e giờ chỉ ghim nửa còn lại: giảm chuyển động thì góc thú cưng **vẫn chơi được**. Nửa "đứng im" thuộc về mắt người, còn thứ ghim được bằng máy là luật thuần `wanderRange(condition, reduced)`.

**Một lỗi cũ lộ ra khi làm lát 1: chốt `reduced` cho cái nhún khi đi chưa từng được áp.** Phép thay chuỗi ở lượt trước trượt sang cái nhún của sinh vật hậu cảnh, và bài kiểm ảnh chụp không thấy vì trong bài ấy con thú đứng yên (`t === 0`, nên `hop` vốn đã bằng 0). Đã vá.

Mỗi chỉ số nói **một câu nhìn thấy được**: no là *nó có đi không*, sức là *nó có đứng không*, vui là *nó có chơi không*. Ràng buộc là đọc ra được mà không cần đọc chú thích nào.

**Lát 4 có thể là thứ đổi cảm giác nhiều nhất.** Hôm nay con thú chỉ đi khi được bảo đi, và một con vật đứng bất động cho tới khi bị bấm là thứ không ai mở ra xem lần thứ hai — nguyên nhân thật của "chưa hấp dẫn" có khi nằm ở đó hơn là ở chuyện chỉ số vô nghĩa. Đi lang thang **không được tốn nhu cầu**: tốn thì con thú tự làm cạn chính nó trong lúc người dùng vắng mặt, và mở bảng ra thấy mọi thanh chạm đáy là một lời trách móc.

**Cái giá của "độ hiếm khác ở hành vi": tiết mục là NỘI DUNG, không phải mã.** Bộ sprite chỉ có một khung cho mỗi loài, nên mọi việc con thú biết làm phải diễn tả bằng vị trí, tỉ lệ và một chút xoay — và phải chỉnh bằng mắt. Đó là lý do bảng dừng ở năm bậc, mỗi bậc đúng một tiết mục.

---

## 4ad. Sidebar — trạng thái nhánh con sai, và một trang không có lối vào · ✅ (2026-08-28)

Hai lỗi im lặng: trang vẫn đúng, chỉ thanh bên nói sai chỗ mình đang đứng — mà không ai gọi đó là lỗi, họ chỉ mất dấu.

**Nhánh con hỏi theo QUAN HỆ CHA-CON, không theo tiền tố đường dẫn.** Luật cũ là `active === item.href || active.startsWith(item.href + "/")`, và nó đúng chừng nào mọi mục con còn nằm dưới đường dẫn của cha. `Ruby rates` thì không: `/admin/ruby` là con của `/admin/pet` vì hai trang ấy là **hai nửa của một quyết định vận hành**, không vì đường dẫn. Hệ quả là đứng ở `/admin/ruby` thì cả nhánh Petland biến mất và không mục nào sáng — người dùng đang ở một trang mà thanh bên nói rằng họ không ở đâu cả. Cùng loại lỗi mà `NavItem.covers` sinh ra để vá ở tầng mục gốc, và cùng cách chữa: **đừng suy quan hệ từ chuỗi đường dẫn khi đã có quan hệ thật trong dữ liệu.**

**`/admin/petland` — trình vẽ bản đồ — không có lối vào nào trong menu.** Đúng cùng chỗ hỏng với màn xem trước khung avatar đã phải vá một lần: một trang thật mà cách duy nhất mở ra là gõ tay đường dẫn, nên nó tồn tại mà không tồn tại. Giờ là mục con của Petland, cạnh Ruby rates.

`activeHref` và `isBranchOpen` tách sang `nav-active.ts` (một tệp `.ts`, không phải `.tsx`) để `scripts/check-nav-active.mjs` chạy thẳng được bằng `node --experimental-strip-types`. Nó đo trên **đúng 16 đường dẫn thật của khu quản trị** cộng bảy của khu học, và kiểm hai điều: mục nào sáng, và nhánh nào mở. Quay lại luật tiền tố thì nó đỏ đúng chỗ: `/admin/ruby: nhánh /admin/pet đóng, đáng lẽ mở`.

Vì sao phải là script chứ không phải e2e: khu quản trị đòi vai trò `admin`, mà `register` cố ý không cấp vai trò nào — cùng lý do bài kiểm đề thi phải dùng đề đã gieo sẵn.

---

## 4ac. Petland — trả ba món nợ của ADR-010 §10, và hai cuộc đua tìm được trên đường · ✅ (2026-08-28)

Ba món trong "cái phải đo, và cái chưa biết" của [`ADR-010`](ADR-010-PETLAND-V2.md) §10, làm theo thứ tự rẻ-và-thật trước.

- [x] **Gieo lười `pet_species` có chốt chống đua.** Bảng gieo lười CUỐI CÙNG còn thiếu nó, và nó nằm trên đường đọc nóng nhất của cả góc thú cưng — `ensure_pet` gọi ở mỗi lần mở bảng. Hai request đầu tiên sau một lần triển khai cùng đọc bảng rỗng và cùng gieo; người thua vỡ khoá chính và mất nguyên một lượt học vì một cuộc đua trên bảng *cấu hình*.
- [x] **Vòng vẽ dừng hẳn khi tab bị ẩn.** Đo được: trang chưa mở bảng gọi `requestAnimationFrame` **0 lần** một giây; mở bảng ra là **~135**; ẩn đi còn **~60**. Con số 135 tố cáo **hai** vòng — vòng vẽ của bảng và ticker riêng của Pixi — nên phải tắt cả hai (`app.stop()`); tắt mỗi vòng của mình thì máy vẫn vẽ WebGL sau lưng người dùng. Phần 60 còn lại là ticker nội bộ của Pixi, làm việc dọn dẹp chứ không vẽ, và không tắt được từ đây.
- [x] **`prefers-reduced-motion`**: bỏ nội suy (`progress = 1`, con thú xuất hiện ở ô đích thay vì trượt tới), bỏ thở và nhún, bỏ nhịp phập phồng của vòng sáng, sinh vật hậu cảnh đứng im. **Không tắt cả góc** — nó là một cái game nhỏ, tắt đi thì không còn gì.
- [x] Xoá `SPECIES_TILE` — bảng tra 12 loài đã trôi khỏi bảng 40 loài ở backend. Cách sửa không phải cập nhật cho đủ 40 (thế là hẹn một lần trôi nữa), mà là xoá hẳn: chỗ duy nhất còn gọi luôn truyền `"cat"`, nên nó cần đúng một hằng số `LAUNCHER_TILE`.

**Cuộc đua thứ hai, tìm được TÌNH CỜ và nguy hiểm hơn hẳn: `GET /pet` trả 500 ở lần mở bảng đầu tiên của một tài khoản.** Lần mở đầu bắn hai request gần như cùng lúc — `GET /pet` và `GET /pet/encounters` — và cả hai đi qua `ensure_pet`. Trên một tài khoản chưa có hàng nào thì cả hai cùng thấy `None` và cùng dựng; người thua vỡ `pet_state_pkey`. Không đọc mã mà ra: một lượt chạy e2e đỏ với `SyntaxError: Unexpected token 'I', "Internal S"...`, tức là trình duyệt nhận "Internal Server Error" ở chỗ nó đợi JSON.

Cả hai cuộc đua đều có bài kiểm với `threading.Barrier` đặt **giữa lần đọc và lần ghi**, và cả hai đã được xem đỏ. Bài học của `test_ruby_race` áp nguyên: chặn TRƯỚC khi gọi thì luồng đầu đọc-ghi-commit trọn vẹn xong trước khi luồng sau kịp đọc, nên bài kiểm xanh y hệt cả khi chốt bị gỡ — tôi đã đo đúng như thế trước khi dời hàng rào vào đúng khe.

**Nới hạn mức đăng ký: 20 → 60 lượt mỗi 10 phút** (`REGISTER_QUOTA`, 2026-08-28).

Lý do không phải là bộ e2e. Chú thích ngay trên con số ấy đã hứa "đủ chỗ cho một lớp học đăng ký cùng lúc từ một đường mạng" — và 20 **không giữ được lời hứa của chính nó**: một lớp 40 học sinh cùng bấm "Tạo tài khoản" trong giờ học thì non nửa lớp bị chặn, mà như đoạn ngay trên đó viết, *người dùng thật bị chặn thì không ai báo lại, họ chỉ bỏ đi*. Nó còn chặt hơn cả `LOGIN_QUOTA` (60), trong khi **đăng nhập mới là cửa dò mật khẩu thật**, còn đăng ký chỉ mở đường bơm rác.

60 mỗi 10 phút = 6 lần/phút cho một địa chỉ: đủ cho một lớp cộng vài lần gõ lại, và vẫn là cái phanh cần cho script bơm tài khoản. Nó chưa bao giờ là hàng rào chống botnet xoay IP — đoạn ghi chú trên `LOGIN_QUOTA` đã nói thẳng chuyện đó.

Bộ e2e chỉ là *triệu chứng* đã phơi con số ra: 22 bài, mỗi bài đăng ký một tài khoản, nên bài thứ 21 luôn đỏ ở `toHaveURL(/dashboard$/)` — một chỗ chẳng liên quan gì tới nó. Đo lại sau khi nới: **một lượt sạch chạy trọn 22/22**, đếm được 21 lượt đăng ký. Chạy dồn vẫn có trần: hai lượt liên tiếp là 42, lượt thứ ba vượt 60 và đỏ hàng loạt ngay từ `auth.spec.ts` — đúng như thiết kế. Xoá bộ đếm giữa những lượt chạy nặng: `docker compose exec redis redis-cli DEL ratelimit:register:<ip>` (ip của gateway Docker, ở máy này là `192.168.65.1`).

---

## 4ab. Chạm mặt ở Petland — NPC giao việc và những đợt xâm nhập · ✅ lát 1–4, 6, 7 (2026-08-27)

Quyết định và lý do ở [`ADR-012-ENCOUNTERS.md`](ADR-012-ENCOUNTERS.md). Đây là thứ đầu tiên ở góc thú cưng **kéo người ta về phía bài tập** thay vì về phía con thú.

- [x] Lát 1 — bảng `encounter` + `encounter_setting`, luật sinh/hết hạn (`app/services/encounters.py`), `GET /pet/encounters`
- [x] Lát 2 — khách đứng trên bản đồ với dấu hiệu trên đầu, bấm vào mở thẻ
- [x] Lát 3 — nhiệm vụ TỪ VỰNG, câu trả lời đi thẳng vào SM-2
- [x] Lát 4 — nhiệm vụ chép chính tả, đi qua đúng bộ chấm của màn chép chính tả
- [ ] Lát 5 — nhiệm vụ trắc nghiệm · **chờ nội dung**, xem ADR-012 §8.3
- [x] Lát 6 — kẻ xâm nhập nhiều bước, mỗi bước một câu hỏi khác
- [x] Lát 7 — `/admin/pet` cho nhịp sinh, thời gian sống và mức thưởng
- [x] Bài kiểm tự động cho luật sinh và cho hai chỗ rò đáp án (`tests/test_encounters.py`, 10 bài)

**Ràng buộc nặng nhất: NPC chỉ xuất hiện khi người học ĐANG Ở ĐÓ.** Sinh ra lúc đọc, không đồng hồ nào chạy khi vắng mặt, không thông báo đẩy. Hệ quả là **không thể bỏ lỡ một thứ chưa từng có** — không NPC nào sinh ra lúc ba giờ sáng rồi hết hạn trước khi người ta thức dậy. Bỏ ràng buộc ấy là biến một lời mời thành một cuộc hẹn, và một cuộc hẹn bị lỡ là mất mát — đúng thứ ADR-010 §11 và ADR-011 §9 đều từ chối.

**Giờ hẹn chốt trước, không bốc xúc xắc mỗi lần đọc** (`pet_state.next_npc_at`). Nếu mỗi lần đọc là một lần bốc thì bấm F5 mười lần gọi NPC ra nhanh gấp mười, và cái góc này lập tức dạy người ta bấm lại trang thay vì học. Đo được: đọc lại ba lần liên tiếp trả về đúng một cuộc, bảng chỉ có một hàng.

**Nhiệm vụ không có bộ chấm riêng.** Câu trả lời từ vựng đi thẳng vào `_apply_review` — cùng hàm mà `POST /vocabulary/{id}/review` gọi — nên nó ghi vào SM-2 thật, vào `vocabulary_review_log`, và chảy tiếp vào chuỗi ngày. Bộ chấm dictation đã có hai bản và phải mang một cảnh báo dài về chuyện trôi khỏi nhau; bản thứ ba nằm trong một tính năng phụ sẽ là bản không ai nhớ cập nhật.

Đo tay trên stack: lần đọc đầu **chỉ đặt mốc** (tài khoản mới không bị NPC nhảy vào mặt ở giây thứ nhất) · tới giờ thì sinh một NPC giao một từ đang chờ ôn · chấm **"Quên"** thì bước không tính **nhưng lượt ôn vẫn được ghi** (nó là một lượt học thật đã xảy ra) · chấm **"Dễ"** thì xong, +5 ruby, SM-2 nhích lên `repetitions=1` · trả lời lại lần nữa trả **409**.

**Nhiệm vụ chép chính tả dùng lại đúng thân của `POST /dictation/{id}/attempts`**, tách thành `record_dictation_attempt` chứ không chép mấy dòng "chấm rồi ghi" sang bên này. Bộ chấm dictation đã có hai bản — Python và `lib/dictation.ts` — và phải mang một cảnh báo dài về chuyện trôi khỏi nhau; bản thứ ba nằm trong một tính năng phụ sẽ là bản không ai nhớ cập nhật. Cổng là `is_complete`, **không phải `accuracy`**: gõ đủ câu rồi gõ thêm vẫn ra 100%, nên lấy điểm làm cổng là trả ruby cho một bài sai rõ ràng.

Thẻ nhiệm vụ **che những chữ còn thiếu thành chấm**, cùng lý do `maskUnreached` ở màn chép chính tả — nhưng ở đây gắt hơn: sai rồi thử lại mà được xem đáp án thì lần sau chỉ là chép lại, và cuối lần sau có ruby. Chữ *thừa* thì hiện nguyên, vì đó là chữ của chính người gõ.

**Kẻ xâm nhập bốc mục tiêu MỚI sau mỗi bước đúng.** Ba bước cùng một từ thì bước hai và ba chỉ là gõ lại đáp án vừa nhìn thấy, và cả đợt xâm nhập rút gọn thành một cái nút bấm ba lần — nó vẫn trả thưởng, vẫn chạy trơn, chỉ là không còn là bài học nào.

**`/admin/pet` từ chối `life >= gap`**, và lý do là một cách hỏng im lặng: mỗi lúc chỉ một cuộc được tồn tại, nên một cuộc sống lâu hơn khoảng cách giữa hai lần sinh sẽ chiếm chỗ suốt — giờ hẹn tới rồi trôi qua mà không ai xuất hiện, và không có lỗi nào để mà đọc.

**Nhiệm vụ từ vựng hỏi bằng cách MÁY chấm được, không bằng thẻ lật** (2026-08-27, theo yêu cầu người dùng). Hai dạng, chốt theo id cuộc chạm mặt nên không đổi giữa hai lần đọc: **gõ lại từ** (in nghĩa tiếng Việt, gõ từ tiếng Anh) và **chọn nghĩa** (in từ, chọn một trong bốn nghĩa).

Thẻ lật phải bỏ vì nó là **tự chấm**, và tự chấm không dùng được ở chỗ có phần thưởng: bản đầu nhận thẳng `grade` từ trình duyệt và dùng chính con số ấy để quyết định có trả ruby không — tức là một trường "hãy trả tôi hai mươi ruby" gửi từ client. Giờ máy chủ nhận *câu trả lời*, chấm bằng `recall.judge`, rồi quy ra điểm bằng `recall.grade_for` — vẫn đúng bộ chấm mà màn gõ lại từ đang dùng, nên một lỗi gõ nhẹ vào SM-2 ở mức KHÓ chứ không phải QUÊN.

Hai chỗ rò đáp án đã bịt, và chúng hỏng theo hai kiểu khác nhau: dạng gõ lại **không gửi `headword`** (bê nguyên payload của thẻ lật sang là in đáp án lên đề bài), còn dạng chọn nghĩa **không gửi `entry_id`** và mỗi ô mang một mã băm theo `(cuộc chạm mặt, mục từ)` — gửi id thật thì đáp án đúng là ô trùng `entry_id`, và cả câu hỏi trả lời được từ devtools mà không đọc chữ nào. Mã băm không lưu ở đâu: máy chủ tính lại đúng mã ấy cho `target_id` để đối chiếu.

**Enter gửi bài ở cả ba dạng** — với `<textarea>` của chép chính tả thì Enter gửi, Shift+Enter xuống dòng.

**Khách đứng ở ô ĐỨNG ĐƯỢC và NẰM TRONG KHUNG NHÌN** (`spotNear`, 2026-08-27). Bản đầu bốc chỗ đứng bằng một công thức thuần trên toạ độ bản đồ (`4 + seed % 9`), không hỏi bản đồ và không biết khung nhìn ở đâu — trong khi chú thích ngay bên trên lại nói `nearestWalkable` kéo về ô đi được, một hàm chưa từng được gọi. Đo hết 24 600 tổ hợp (mọi ô con thú đứng được × 200 seed) trên bản đồ 18×13: công thức cũ cho **7 011 lượt rơi vào vật cản** và **13 528 lượt rơi ra ngoài khung nhìn 14×8**; `spotNear` cho 0 và 0. Đó là một lỗi duy nhất sinh ra ba triệu chứng — không thấy dấu hiệu, không bấm được vào NPC, khách đứng trong tường — và cái nút ở thanh tiêu đề vẫn mở được thẻ nên nhìn từ ngoài nó không giống một lỗi vẽ.

Hai chỗ nhỏ đi kèm: phép thử "bấm trúng khách" chạy **trước** chốt "con thú đang ngủ" (giấc ngủ chỉ nên khoá việc dắt con thú đi, không liên quan gì tới việc trả lời một câu hỏi), và vùng bấm cao **hai ô** vì sprite neo ở đáy ô nên đầu và dấu hiệu nhô lên ô trên — người ta bấm vào chỗ nhìn thấy chứ không vào ô mà nó "thuộc về".

**Bấm vào khách thì con thú CHẠY TỚI, và khách nói một câu.** Con thú dừng ở ô **kề bên** (`neighbourOf`, chọn ô kề gần nó nhất nên đi đường ngắn nhất): đi vào đúng ô của khách thì hai sprite chồng khít lên nhau và con nào hiện ra trước là chuyện của thứ tự thêm vào danh sách vẽ, không phải của khung cảnh. Đang ngủ thì bỏ đoạn đi nhưng **vẫn mở thẻ** — trả lời một câu hỏi không dính gì tới việc con thú đang ngủ.

Lời thoại sống ở `petland-speech.ts` cùng chỗ với bảng phân vai sinh vật, và vì cùng lý do: đây là *lời thoại*, không phải dữ liệu miền — đưa nó thành hàng dữ liệu là mời một màn quản trị, một migration và một endpoint vào chỗ chỉ cần hai chục câu văn. Chọn theo id cuộc chạm mặt nên **cùng một vị khách luôn nói cùng một câu**, kể cả sau khi F5; bốc lại mỗi lần dựng thì cái làng đọc ra là một cỗ máy phát chữ. Kẻ xâm nhập nói năng hung hăng nhưng **không doạ mất mát** — ADR-012 §4 nói bỏ qua thì không mất gì, nên một câu doạ mà hệ thống không thực hiện là nói dối người học.

Bong bóng là **phần tử DOM**, không vẽ trên canvas: canvas cố ý không nạp phông chữ nào (cùng lý do dấu chấm than là hai hình chữ nhật), và chữ vẽ trên canvas thì trình đọc màn hình không đọc được. Vị trí ghi thẳng vào `style` mỗi khung qua `stage.guestScreen()` chứ không qua state — một `setState` mỗi khung là dựng lại cả bảng, kèm canvas Pixi bên trong, sáu chục lần một giây — và nó phải bám thật chứ không chốt lúc bấm, vì con thú chạy tới thì máy quay xê dịch theo. Sát mép trên thì bong bóng lật xuống dưới, vì khung bản đồ cắt phần tràn ra.

Đo bằng script: `neighbourOf` trên 492 tổ hợp không lần nào trả ô tường, không kề, hay không phải ô gần nhất; `speechFor` trên 3 000 lượt không lần nào đổi câu giữa hai lần gọi.

**Nhiều cuộc cùng lúc (2026-08-28, theo yêu cầu người dùng).** Bản trước cho đúng **một** cuộc mỗi lúc, và điều đó sai nặng nhất ở chỗ một cuộc bị bỏ dở chặn đứng cả làn: người học mở thẻ, thấy câu khó, để đó, và mười phút sau vẫn đúng câu ấy. Giờ **tối đa hai mỗi loại**, đếm riêng từng loại — một trần chung 4 sẽ để NPC lấp kín bản đồ và kẻ xâm nhập, thứ hiếm hơn hẳn và là chỗ hoạt cảnh chiến đấu sống, không bao giờ có chỗ mà xuất hiện.

**Một cuộc mới không bao giờ đẩy cuộc đang diễn ra đi.** `sync` không xoá gì để lấy chỗ; cái đang chờ chỉ biến mất khi hết hạn hoặc làm xong. Nếu không thì một người đang gõ dở câu trả lời sẽ thấy đề bài đổi dưới tay mình, và công sức của họ biến mất vì một cái đồng hồ ở đâu đó vừa điểm.

Kéo theo ba chỗ:

- **Hết hạn KHÔNG hẹn lại giờ nữa.** Ở bản một-cuộc-một-lúc thì phải hẹn lại để "bỏ lỡ" không thành có lợi; giờ mỗi lần *sinh* đã tự hẹn lần sau, nên nhịp được giữ bởi chính phép sinh — và hẹn lại thêm ở đó chỉ còn là phạt người ta vì đã lờ một lời mời, đúng thứ ADR-012 §4 từ chối. Đầy chỗ thì lùi một nhịp **ngắn**, không lùi cả nhịp đầy: chỗ sẽ trống ngay khi một cuộc hết hạn, mà bắt đợi thêm một nhịp nữa sau đó là phạt cho việc bản đồ vừa đông.
- **`GET /pet/encounters` trả mảng trần.** Số cuộc bị chặn cứng bởi miền (2 × 2), nên đây là nhóm (A) của `app/schemas/common.py` — bọc `Page[T]` là bắt frontend xử lý một trường hợp không thể xảy ra.
- **Thứ tự CHỐT bằng `ORDER BY created_at, id`.** Giao diện chỉ vẽ một dấu hiệu cho mỗi loại và người mang nó là người tới trước; không có `ORDER BY` thì thứ tự đổi giữa hai lần đọc và cái dấu ấy nhảy qua nhảy lại giữa hai vị khách.

**Xong nhiệm vụ thì CON THÚ cũng lên XP** — NPC 6 điểm, đẩy lui kẻ xâm nhập 15, cùng tỉ lệ với ruby vì hai phần thưởng đo cùng một việc. Cao hơn hẳn `walk` (5) có chủ ý: đây là XP duy nhất phải *học* mới có, còn mấy cái nút chăm sóc chỉ trả cho sự chăm chỉ. Đi qua đúng `_award` của mấy cái nút ấy, nên trần ngày, mốc level và múi giờ người học là một bộ — một đường trao XP thứ hai là chỗ trần ngày đếm thiếu mà không ai thấy. `_award` vì thế nhận **số điểm** thay vì tên hành động; tra bảng trong hàm thì cuộc chạm mặt phải bịa ra một "hành động" không có nút nào bấm được.

**Nút gọi khách cho admin** (`POST /admin/pet/encounters/spawn`, biểu tượng tia sáng ở thanh tiêu đề bảng Petland, chỉ admin thấy). Nó tồn tại vì đường thật **cố ý chậm** — hai mươi phút cho một NPC, một giờ cho một kẻ xâm nhập, và lần đọc đầu của một tài khoản mới chỉ đặt mốc chứ không sinh ai; không có nó thì mỗi lần sửa một dòng trong hoạt cảnh chiến đấu là hai mươi phút ngồi đợi.

Ba tính chất giữ cho nó không thành một cửa hậu: **chỉ cho chính người gọi** (không nhận `user_id`, nên không ai gọi kẻ xâm nhập vào bản đồ người khác), **vẫn tôn trọng trần** (đo thật: bấm năm lần vẫn đúng bốn người), và **đi qua đúng `_spawn` của đường thật** — một đường sinh riêng cho việc thử sẽ dựng ra những cuộc mà đường thật không bao giờ tạo được, và lúc đó thử xong cũng không biết mình vừa thử cái gì. Nó cũng dời giờ hẹn của làn như một lần sinh bình thường, nếu không thì ngay sau khi thử xong làn ấy nhả thêm một cuộc nữa vào giây kế tiếp.

Nút nằm trong bảng Petland chứ không ở `/admin/pet`, vì thứ nó tạo ra chỉ nhìn thấy được trên bản đồ ấy — một nút ở trang khác nghĩa là mở tab thứ hai, bấm, rồi quay lại, mỗi vòng thử.

**Lái thú cưng bằng WASD** (và cả bốn phím mũi tên, 2026-08-28). Bốn quyết định trong đó, mỗi cái vá một cách hỏng khác nhau:

- **Nghe phím ở KHUNG BẢN ĐỒ, không ở `window`.** Bảng thú cưng nổi trên mọi trang của khu học, kể cả màn gõ lại từ và ô chép chính tả — nghe ở `window` thì gõ chữ "w" trong một bài tập sẽ lái con thú, và không ai nối được hai chuyện đó với nhau. Lọc theo `event.target` cũng chặn được, nhưng nó là một danh sách thẻ phải nhớ bổ sung mãi mãi. Đổi lại, khung bản đồ giờ nhận focus, có `role="application"`, `aria-label` và viền focus thấy được — trả một phần món nợ "không điều khiển được bằng bàn phím" của ADR-010 §10.
- **Vòng vẽ đọc trạng thái GIỮ, không nạp ô lúc bấm.** Bàn phím tự lặp ~30 lần một giây khi giữ, mà mỗi ô mất 0,3 giây để đi: nạp theo sự kiện sẽ dựng một hàng đợi dài hàng chục ô và con thú đi tiếp cả sau khi đã thả phím.
- **Ghi vị trí khi dừng hẳn, mà "dừng hẳn" giờ gồm cả "không còn phím nào đang giữ".** Thiếu vế sau thì đi mười hai ô bằng bàn phím là mười hai request — đúng thứ mà việc ghi-khi-dừng sinh ra để tránh.
- **Giành quyền lái thì để bước đang đi dở đi cho hết** (`queue.slice(0, 1)`). Bản đầu xoá sạch hàng đợi rồi đặt `progress = 0`, và thế là con thú **dịch tới ô đích ngay lập tức** — `tile` đã là đích còn `from` mới là chỗ xuất phát, nên đổi hướng giữa bước là một cú nhảy nửa ô.

**Bàn phím nghe ở `window` nhưng có CỔNG "đang chơi ở bảng này"** — bản thứ tư, và ba bản trước đều sai theo một kiểu riêng:

1. **Nghe ở `window` trần** — sai: bảng nổi trên mọi trang của khu học, nên gõ chữ "w" trong một ô nhập bài tập sẽ lái con thú.
2. **Nghe ở riêng khung bản đồ, chỉ khi nó giữ focus** — quá hẹp. Bấm bất cứ nút nào là bàn phím chết lặng, không có gì nói vì sao. Đây là lỗi người dùng báo: *"nhiều lúc phím không nhận, ví dụ sau khi chạm npc và tắt"* — bấm cái X đóng thẻ là focus nằm trên chính cái nút vừa bị gỡ khỏi cây, và trình duyệt đẩy nó ra `document.body`.
3. **Nghe ở cả bảng** — vẫn hụt, và chỗ hụt chỉ lộ ra khi ĐO: nút "Cho ăn" tự mờ đi ngay sau khi bấm, mà một phần tử disabled thì mất focus về `body`, tức ra ngoài bảng. Sự kiện phím không còn nổi tới nơi nghe. Tôi đã tưởng bản này đúng và phải viết một bài chẩn đoán in `document.activeElement` mới thấy.

Cổng `engaged` trả lời đúng câu hỏi thật — *bàn phím đang nói với ai?* Chạm vào bảng thì nó nói với bảng, cho tới khi bấm hoặc focus sang chỗ khác; không phụ thuộc focus đang nằm đâu, nên một cái nút tự mờ đi không cắt được đường. Ô nhập chữ vẫn bị bỏ qua (`isTyping`), và đóng cột bên phải thì focus được trả về khung bản đồ cho người dùng bàn phím.

**Thẻ mở do HÚC thì ô nhập không tự lấy focus.** Lấy rồi thì phím W tiếp theo gõ chữ "w" vào ô đó thay vì đi lên — bàn phím trông như chết. Bấm chuột mở thẻ thì ngược lại: tay đã rời bàn phím, tự đặt con trỏ vào ô nhập là đúng việc.

Bài `bấm nút trong bảng xong, bàn phím vẫn lái được` chặn **cả hai phía**, và đã xem đỏ cả hai: quay lại nghe theo focus → đỏ ở "bấm nút xong phím phải vẫn lái được"; bỏ cổng `engaged` → đỏ ở "bấm ra ngoài bảng thì phím phải thôi lái" (con thú vẫn đi từ 3 sang 6).

**Húc vào một vị khách cũng là mở thẻ của họ**, y như bấm chuột (2026-08-28). Ba quyết định trong đó:

- **Chỉ bắt lúc CHUYỂN từ "chưa chạm" sang "đang chạm"** (`bumpRef`). Giữ phím áp vào một NPC là sáu chục khung hình mỗi giây đều thấy đang chạm, và mở thẻ ở mỗi khung là sáu chục lần dựng lại cả bảng — kèm canvas Pixi bên trong.
- **Chỉ tính khi NGƯỜI DÙNG đang lái.** Đi dạo là con thú tự đi, và một cái thẻ nhiệm vụ tự bật ra giữa lúc người ta đang đọc thứ khác là một cửa sổ chen ngang.
- **Ô có người đứng là ô không đi qua được**, cho cả bàn phím lẫn đường bấm chuột (`findPath` nhận thêm một tập `blocked`). Không có nó thì con thú xuyên thẳng qua một NPC và hai sprite chồng khít lên nhau — cùng lý do `neighbourOf` tồn tại. Húc vào tường hay húc vào người đều **vẫn quay mặt** về hướng ấy.

Đo được: `scripts/check-petland-walk.mjs` dựng 112 tuyến đi qua bản đồ thật, chặn đúng ô giữa mỗi tuyến, và không tuyến nào xuyên qua; gỡ phép tránh ra thì cả 112 tuyến đỏ. Bản thân cú húc thì **chưa có phép kiểm tự động** — nó cần một vị khách trên bản đồ, mà sinh khách đòi quyền admin còn `register` thì cố ý không cấp vai trò nào (cùng lý do bài kiểm đề thi phải dùng đề đã gieo sẵn).

**Máy trạng thái đi lại tách sang `petland-pet.ts`, và đó là bài học thật của lát này.** Nó từng nằm trong closure của `requestAnimationFrame`, nơi cách duy nhất để kiểm là bấm thử bằng tay — và nó sinh ra **ba lỗi liên tiếp mà `tsc`, eslint và cả một bài Playwright đều xanh**:

- **Con thú được vẽ ở ô TRƯỚC ô nó thật sự đang đứng.** Một bước là cặp (`from` → `tile`) cộng `progress`; đứng yên nghĩa là `from` trùng `tile`. Bản hỏng đặt `progress = 0` khi hết đường mà không kéo `from` về `tile`, nên hình vẽ tụt lại một ô so với vị trí logic. Bước sau bắt đầu bằng một cú dịch tới ô logic ấy — và nếu cú dịch đó ngược hướng vừa bấm thì người dùng thấy **"bấm sang trái mà nhảy sang phải"**. Một nguyên nhân, ba triệu chứng.
- **Phần dư của `progress` bị vứt ở mỗi ô**, nên cứ mỗi ô con thú khựng mất hơn nửa khung hình — đọc ra là *giật*, không phải *chậm*.
- **`progress` bị chặn bằng `queue.length ? progress : 0` trước khi gửi cho tầng vẽ.** Lái bằng bàn phím thì hàng đợi rỗng gần như suốt (ô kế tiếp do `steer` cấp thẳng), nên tầng vẽ nhận 0 ở mọi khung hình và con thú dịch từng ô thay vì đi.

Thêm một chỗ nữa: **giành quyền lái phải bỏ CẢ tuyến chuột**, không giữ lại `queue[0]` — ô ấy là ô kế tiếp theo hướng cũ.

`scripts/check-petland-walk.mjs` chạy máy trạng thái ấy bằng `node --experimental-strip-types`, với **`dt` rung như khung hình thật**: `1/60` chia đúng 18 khung cho một ô 0,3 giây nên phần dư luôn bằng 0, và bài kiểm chạy ở nhịp tròn ấy sẽ không thấy gì khi ai đó vứt phần dư đi. Cả ba lỗi đều đã được **xem đỏ** ở đó bằng cách gỡ đúng đoạn mã chúng canh.

Bài Playwright `lái bằng bàn phím đi ĐÚNG hướng` vẫn giữ, nhưng nó canh chỗ khác: phím có tới được con thú không, và có đi đúng trục không. Nó **không** bắt được lỗi đổi hướng — vị trí chỉ tới máy chủ khi con thú dừng hẳn, nên khoảnh khắc đổi hướng giữa lúc đang đi là thứ e2e không quan sát được. Đã thử tái tạo lỗi và nó vẫn xanh; đó là lý do phải có bài đo thuần.

**Ô mặc định của thú cưng phải đứng được** (migration `046`). `(3, 8)` nằm trong tường — hàng 8 của `map.json` là `#####....#.#...#.#`. Không ai nhìn thấy, vì lượt nạp đầu gọi `nearestWalkable` kéo con thú ra rồi ghi lại; cái giá là một lần dịch chuyển và một `PUT` mà mọi tài khoản mới đều phải trả để sửa một con số lẽ ra đã đúng. Phát hiện ra vì bài Playwright đỏ ở một chỗ chẳng liên quan: bấm `d` mà `y` đổi từ 8 xuống 6.

**Nút gợi ý cho nhiệm vụ gõ lại từ** (migration `045`, 2026-08-28). Tối đa **hai lần mỗi bước**: lần một mở một phần tư số chữ, lần hai mở một nửa. Không mở một chữ mỗi lần — với một từ mười một chữ thì hai lượt chỉ ra hai chữ, không gỡ được gì và cái nút thành trang trí; không quá một nửa, vì phần còn phải nhớ chính là thứ phân biệt một bài kiểm với một ô điền sẵn. Đo thật trên `recital`: `re·····` rồi `reci···`, lần ba trả 409.

**Trần đếm ở máy chủ (`encounter.hints_used`), và đó là điều kiện để cái nút không phá chính bài kiểm nó đang giúp**: xin đủ nhiều lần thì gợi ý in ra cả từ, và lúc ấy phần thưởng ruby chỉ còn là một cái nút bấm nhiều lần — một bộ đếm trong `useState` thì devtools đặt lại được trong hai giây. `task.hints_left` được gửi kèm để giao diện tự khoá sau khi tải lại trang, thay vì mời bấm một nút chắc chắn trả về lỗi.

Ba chi tiết nhỏ hơn, mỗi cái vá một cách hỏng lặng lẽ: **đổi mục tiêu giữa các bước thì đặt lại `hints_used`** (bước hai và ba của một đợt xâm nhập là từ khác, không nên thừa hưởng cái trần đã dùng hết ở bước một); **gợi ý in riêng một dòng, không đổ vào ô nhập** (đổ vào thì người học mất cái đang gõ dở, và phần máy mở ra trông y hệt phần họ tự nhớ); và **chỗ chưa mở in bằng dấu chấm giữa dòng**, nên độ dài của từ cũng lộ ra — đó là chủ ý, biết từ dài mấy chữ là nửa phần giá trị của một gợi ý.

Chỉ dạng gõ lại từ mới có. Dạng chọn nghĩa đã có sẵn bốn ô để loại trừ, còn "mở vài ký tự" của cả một câu chép chính tả là mở luôn đáp án.

**Ô bên phải là MỘT trạng thái, không phải ba cờ** (`panel`, 2026-08-28). Trước đó là `side` + `questOpen` + `listKind`, và chúng mâu thuẫn được với nhau: mở danh sách khách rồi bấm nút trứng thì `side` đổi thành `"eggs"` trong khi `listKind` vẫn còn, nên màn trứng bị chính điều kiện `!listKind` chặn lại — cái nút trông như hỏng, không có lỗi nào để đọc, chỉ là bấm mà không có gì xảy ra. Một biến thì trạng thái ấy không tồn tại được: mở cái này là đóng cái kia, theo đúng nghĩa đen.

Kèm một cái bẫy liền kề đã bịt luôn: **ô rỗng thì coi như đóng**. Một cuộc chạm mặt có thể hết hạn ngay trong lúc thẻ của nó đang mở — máy chủ bỏ nó khỏi danh sách ở lần đọc kế tiếp — và nếu chỉ nhìn `panel` thì bảng vẫn chừa nguyên chỗ cho một cái thẻ không còn được vẽ, đúng cái khoảng trống bên cạnh bản đồ đã phải sửa một lần rồi. Suy ra (`shown`) chứ không dọn bằng effect: dọn bằng effect là thêm một đường đổi state nữa phải giữ cho đồng bộ.

**Danh sách in ảnh đại diện của đúng con vật đang đứng trên bản đồ.** `tileForGuest(id, role)` sống ở `petland-bestiary.ts` và cả hai nơi cùng gọi nó. Tính riêng hai lần là hai công thức, và chúng lệch nhau vào đúng ngày ai đó thêm một ô vào bảng phân vai — lúc đó danh sách in một con, bản đồ vẽ một con khác, và không có gì báo vì cả hai đều là ô hợp lệ. Đo 6 000 lượt: không lượt nào ra ô sai vai, không lượt nào đổi ô giữa hai lần gọi.

**Mỗi vị khách mang dấu hiệu của riêng mình** (2026-08-28). Có thử gộp còn một dấu mỗi loại cho đỡ ồn, nhưng nó lấy đi đúng thứ dấu hiệu sinh ra để làm: người không mang dấu vẫn bấm được mà **không ai biết là bấm được**. Hình thì vẫn theo loại — chấm than cho việc, tam giác cho nguy hiểm.

**Thanh tiêu đề: một nút mỗi loại, luôn in dấu chấm than, và nó mở một DANH SÁCH** (`petland-quest-list.tsx`) chứ không mở thẳng một thẻ. Bấm thẳng thì cái nút phải tự đoán người dùng muốn ai trong hai người — đoán sai là mở nhầm việc. In số thay vì dấu chấm than cũng đã thử và sai: hàng nút ấy toàn biểu tượng, nên một con số ở giữa đọc ra là một chỉ số chứ không phải một lời mời, mà số lượng thì đã có sẵn ở đầu danh sách.

**Danh sách in thời gian còn lại, và đó là thứ đáng giá nhất trong nó.** Một cuộc chạm mặt sống mười phút rồi biến mất không báo trước; không thấy con số ấy thì người học không có cách nào biết nên làm cái nào trước, và cái họ chọn sai sẽ tan đi giữa chừng. Đồng hồ cũng nằm trên chính thẻ nhiệm vụ, nơi nó còn quan trọng hơn: người ta đang gõ dở một câu trả lời, và không có con số thì cái hạn ấy ập đến như một lỗi — bấm "Kiểm tra" rồi nhận 409 mà không hiểu vì sao. Dưới một phút thì đổi màu, vì đó là lúc con số thôi là thông tin và bắt đầu là một lời khuyên.

Nhịp một giây sống trong chính hai component ấy, không ở bảng ngoài: mỗi giây một `setState` ở bảng là dựng lại cả bảng kèm canvas Pixi bên trong — cùng lý do vị trí bảng và bong bóng thoại đều ghi thẳng vào `style`. `secondsLeft`/`clock` tách sang `petland-countdown.ts` (một tệp `.ts`, không phải `.tsx`) để chạy thẳng được bằng `node --experimental-strip-types`; đo 5 trường hợp gồm cả mốc đã quá hạn (kẹp về `0:00`, không đếm âm).

**Lỗi vừa gây ra và đã sửa: vị khách vẽ dưới cả tấm nền.** Chỗ đứng của họ được chèn bằng `addChildAt(sprite, 0)`, mà mỗi ô cỏ là một sprite thêm vào từ lúc dựng sân khấu — nên chỉ số 0 là *sau* tất cả. Triệu chứng không giống nguyên nhân chút nào: **dấu hiệu vẫn hiện còn nhân vật biến mất hẳn**, vì dấu nổi lên hai ô phía trên và thường rơi vào ô trống, mà ô trống thì không có sprite nào để che. Giờ chèn ngay trước con thú (`world.getChildIndex(pet)`), giữ đúng thứ tự cũ. Không phép kiểm nào ở đây thấy được chuyện đó — `tsc` và eslint đều xanh suốt.

**Kẻ xâm nhập bị con thú đánh cho một trận**, và trận đánh dựng trong tầng vẽ vì đó là chỗ duy nhất biết cả hai thân đứng đâu — `action` chỉ tả một thân, nên nó là một trường riêng (`PetView.fight`) chứ không phải một `kind` nữa. Ba nhịp lao tới (`|sin(3πt)|`, số nhịp **lẻ** có chủ ý: số chẵn kết thúc lúc con thú đang ở giữa đà lao và nó búng về chỗ cũ, đúng lỗi mà nhịp nhai của "cho ăn" đã phải sửa), kẻ kia giật lùi và ửng đỏ **đúng lúc chạm** chứ không đỏ suốt, tia va chạm chớp ở điểm giữa. Đòn kết liễu chiếm 30% cuối: nó phải tới SAU mấy nhịp đánh, nếu không thì đó là "chạm nhẹ rồi ngã".

Ba chỗ trong đó hỏng im lặng nếu làm khác:

- **Con thú phải TỚI NƠI rồi mới đánh.** Trả lời từ nút trên thanh tiêu đề thì nó có thể đang ở nửa bản đồ bên kia, và một cú lao dài nửa ô ở đó chỉ là một cái nhích. Nhưng chờ suông thì treo, và treo hỏng nặng hơn xấu — `fightRef` còn giá trị nghĩa là vị khách bị **giữ lại trên bản đồ** sau khi máy chủ đã báo xong. Nên vắng khách, đang ngủ, hay không có đường đi đều đánh ngay tại chỗ.
- **Vị khách sống thêm qua cú ngã.** Máy chủ trả "xong" ngay khi câu trả lời đúng và `onChange(null)` gỡ khách khỏi bản đồ, nên nếu xoá đúng lúc ấy thì cú ngã không bao giờ được vẽ — kẻ xâm nhập biến mất giữa không trung. Vòng lặp vẽ mới là chỗ xoá, sau khi diễn xong.
- **Chỗ đứng của khách chốt MỘT LẦN theo `id`, không theo object.** `encounter` là object mới sau mỗi câu trả lời, mà chỗ đứng lại đo theo ô con thú đang đứng — và con thú thì vừa chạy tới sát bên. Không khoá lại thì kẻ xâm nhập dịch chuyển tức thời sang chỗ khác giữa hai bước, mà vẫn giữ nguyên hình dạng vì hạt giống lấy từ `id`.

**Dấu hiệu khác HÌNH chứ không chỉ khác màu**: chấm than cho việc, chấm than trong khung tam giác cho nguy hiểm. Cặp vàng/đỏ là đúng cặp khó nhất với người mù màu. Màu vẽ thẳng vào hình chứ không qua `tint` — `tint` nhân lên mọi lớp nên cái nền tối, thứ giữ cho dấu hiệu đọc được trên một bản đồ nhiều màu, cũng ngả vàng theo và biến mất đúng chỗ nó phải làm việc.

**Bài kiểm: `tests/test_encounters.py`, 10 bài**, và ba trong số đó đã được xem đỏ bằng cách gỡ đúng đoạn mã chúng canh: bỏ nhánh "còn cuộc đang chờ thì thôi" (sinh ra mười cuộc cho mười lần đọc), bỏ hẹn lại giờ khi hết hạn (bỏ lỡ thành có lợi), và bỏ việc bốc mục tiêu mới giữa các bước. Luật sinh nhận `now` và `rng` làm tham số chính vì chuyện này — một luật phụ thuộc đồng hồ và may rủi mà không tiêm được thì không bài kiểm nào nói được gì về nó.

---

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
- [ ] Monitoring, deployment — **phương án đã chốt, chưa dựng**: `ADR-014-DEPLOY-FREE.md`.
      Vercel (web) + Render (API) + Supabase (Postgres + audio) + Upstash (Redis) + Cloudinary,
      toàn bộ gói free và không cần thẻ tín dụng. Không phải sửa mã: nhà cung cấp lưu trữ vốn đã
      là biến môi trường (ADR-006 §2.8). Ba chỗ hỏng im lặng nằm ở ADR-014 §3; hạn mức chạm
      trước nhất là **Redis** chứ không phải băng thông (§4). Đường dựng ở §7: API chạy ảnh
      dựng sẵn từ GHCR (CI phải gọi deploy hook), web không Docker hoá được.
      🟢 **Đã lên production 2026-08-29**: Vercel + Render + Supabase (Singapore) + Upstash +
      Cloudinary, toàn bộ gói free, không thẻ. `/admin/system` vẽ sơ đồ này và đo trạng thái
      thật; xem ADR-014 §10 cho việc tách nội dung khỏi lịch sử học khi đem dữ liệu lên.

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
