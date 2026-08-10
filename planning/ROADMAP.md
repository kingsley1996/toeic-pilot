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
- [ ] Parser: `Questions X-Y refer to the following …` mở `question_set`; `NNN.` mở câu; `(A)`–`(D)` là phương án

### Frontend `/admin`
- [x] Màn dán **từ vựng và dictation** — ô text dán hàng loạt, chọn topic, xem trước rồi mới lưu (`/admin/vocabulary`, `/admin/dictation`)
- [ ] Màn dán **câu hỏi**: chọn part, ô text đề, ô text đáp án riêng
- [ ] **Cảnh báo Part 1 và 2 phải dán từ phần audioscript** — phần đề của hai part này trong PDF gần như trống, ai không biết sẽ tưởng parser hỏng
- [x] Lưới review: lỗi hiện ngay tại dòng
- [ ] Editor từng câu **có xem trước** — bắt buộc cho Part 1: không nhìn thấy ảnh thì không viết được bốn câu mô tả
- [x] Bảng nội dung có badge audio (`missing`/`stale`/`current`) + nút publish
- [ ] Trường `source` **không được pre-select** — đây là cột duy nhất mà giá trị sai gây hậu quả pháp lý

### Test
- [x] Parser từ vựng + dictation: dòng đúng, dòng thiếu cột, dòng rỗng (`tests/test_services.py`)
- [ ] Parser câu hỏi: đề đúng chuẩn, đề thiếu đáp án, đánh số nhảy cóc, stimulus thiếu
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
- [ ] Soạn ≥ 300 từ vựng cho ≥ 6 chủ đề — hiện có **43** trên **1** chủ đề (Business, 2026-08-10)
- [x] Sinh audio 4 accent × {headword, example} cho toàn bộ số từ đang có — **387 clip**, 0 lỗi
- [ ] Soạn ≥ 50 câu dictation — hiện có **4**

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
- [x] Trang `/admin/media` — thư viện ảnh, ba trường bản quyền bắt buộc, ghi công **hiện ra** chứ không chỉ được lưu (ADR-004 §4.2)
- [x] `Avatar` nhận `src`; header và trang hồ sơ dùng ảnh thật, thiếu thì rơi về chữ cái đầu
- [x] **Đã chạy thật lên Cloudinary** cả hai luồng (ảnh nội dung + avatar) qua chính các endpoint
- [x] **Driver `s3` (audio)** — một driver cho Supabase / B2 / R2 / DO Spaces / MinIO; nhà cung cấp là `S3_ENDPOINT_URL`, không phải một nhánh `if` trong code (ADR-006 §2.8). Địa chỉ **kiểu đường dẫn** + SigV4, có test ghim: mặc định virtual-host của boto3 hỏng ở Supabase và hiện ra dưới dạng lỗi DNS
- [x] `app/content/push_media.py` — đẩy media sinh sẵn lên object store, chạy lại là no-op, `Cache-Control: immutable`. Audio sinh offline là bài toán **triển khai**, không phải bài toán upload (§2.8a)
- [x] `verify()` **xoá** object quá cỡ thay vì chỉ từ chối — presigned PUT không ghim được dung lượng (§2.8b)
- [ ] Chạy thật một vòng lên Supabase (chờ credential) — Cloudinary đã chạy thật rồi, đường S3 thì chưa
- [ ] Cron ping giữ project Supabase khỏi tự ngủ sau 7 ngày (§2.8 — kiểu hỏng là *chỉ audio 404*)
- [ ] Lệnh đối chiếu file mồ côi (§10.4 giờ tốn tiền hàng tháng)

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
- [ ] Part 2 chỉ hiện A/B/C, không hiện chữ
- [ ] Part 3, 4, 6, 7 hiện kích thích dùng chung cho cả nhóm câu
- [ ] Trang kết quả: điểm từng section, điểm tổng, giải thích từng câu

### Nội dung
- [ ] ≥ 1 đề đầy đủ 200 câu, hoặc ≥ 40 câu mỗi part cho chế độ luyện tập
- [ ] Ảnh Part 1 — chọn thủ công, ghi giấy phép (`ADR-004` §2.1)
- [ ] `question.source` phải điền đúng: **không** sao chép đề ETS thật

### Định nghĩa hoàn thành
Học viên làm hết một đề trong thời gian quy định, nộp bài, nhận điểm quy đổi và xem giải thích từng câu.

---

## 6. Sprint 6 — Hardening & bảo mật

**Phải xong trước Sprint 7.** Đây không phải sprint "dọn dẹp": nó chứa các điều kiện tiên quyết cứng của AI layer.

- [ ] **P1-8 Rate limiting** — bắt buộc trước endpoint LLM đầu tiên
- [ ] **P1-7** Token sang httpOnly cookie + refresh token + denylist trên Redis (Redis hiện chưa dùng vào việc gì)
- [ ] **P1-3** Test frontend + Playwright e2e cho luồng auth và một luồng học
- [ ] **Bật branch protection** — treo từ Sprint 0, cần quyền admin repo. 13 gate không bắt buộc thì chỉ là gợi ý
- [ ] P2-6 Dockerfile production: multi-stage, non-root, bỏ `gcc`/`libpq-dev` thừa
- [ ] P2-7 Bỏ fallback `pnpm install --frozen-lockfile || pnpm install`
- [ ] Bảng `ai_interaction` (token, chi phí, latency, `request_id`) — dựng **trước** khi có request LLM

---

## 7. Sprint 7 — AI Layer

**Chặn bởi:** ADR-003 chưa viết.

- [ ] **ADR-003** — chọn LLM provider, phân tầng routing, ngân sách token/user (`REVIEW-OPUS.md` §7g, §7d)
- [ ] Chốt embedding model → mới tạo được `knowledge_chunk`/`learning_memory` (chiều `vector(n)` là quyết định một chiều: đổi model = tính lại toàn bộ corpus)
- [ ] Migration cho các bảng ở `ADR-001` Phần C
- [ ] RAG: nguồn corpus, chunking, đánh giá retrieval
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
| Token trong `localStorage` | P1-7 → **Sprint 6** | Cũng là chỗ đầu tiên Redis thật sự được dùng (refresh token + denylist) |
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
