# TOEIC Pilot — Tiến độ & Lộ trình

> **Đây là file theo dõi duy nhất của dự án.** Sprint, task, trạng thái thật của code — tất cả ở đây.
> Cập nhật **ngay khi** hoàn thành một task, không để dồn.
>
> Các tài liệu khác có vai trò khác và **không** chứa trạng thái sprint:
> `PLAN.md` = spec sản phẩm · `ARCHITECTURE.md` = kiến trúc hiện trạng · `ADR-001` / `PHASE2-AUDIO` (= ADR-002) / `ADR-004` / `ADR-005` = quyết định + lý do · `MEDIA-PIPELINE.md` = media hoạt động thế nào + điểm yếu · `DESIGN-SYSTEM.md` = hệ thống thiết kế giao diện (đã viết, **chưa triển khai**) · `SPEC-LEARNING-HUB.md` = bộ mặc định tạm thời của Learning Hub, dựng để sửa · `REVIEW-OPUS.md` = review kỹ thuật (ảnh chụp 2026-08-08, không cập nhật tiếp)

**Cập nhật lần cuối:** 2026-08-09

---

## 1. Đang ở đâu

| | |
|---|---|
| **Phase hiện tại** | Sprint 3 + 4 đã chạy được đầu-cuối cho **từ vựng và dictation** |
| **Chặn Phase 2** | **Không còn gì.** Cả hai blocker đã gỡ (audio, data model) |
| **Sprint kế tiếp** | Sprint 5 — TOEIC Practice (kèm phần question của Sprint 3 còn nợ) |
| **Test** | 271 thu thập — **269 chạy** + 2 `external` deselect mặc định |
| **Gate CI** | 13, tất cả xanh |
| **Migration** | `001` → `002_audio_assets` → `003_domain_schema` → `004_images_and_scoring` → `005_roles_and_audit` → `006_dictation_audio_optional` |
| **Bảng** | 20 |
| **Endpoint** | **25** — auth (3), health (2), Learning Hub (8), Content admin (12) |
| **Media** | 38 clip audio, 3 ảnh |
| **Nội dung thật** | **3 từ vựng, 4 câu dictation** ← nút thắt |
| **Giao diện** | Design system đã triển khai toàn bộ ([`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md)) · 12/12 route dựng tĩnh |

**Kiểm chứng lại toàn bộ ngày 2026-08-09:** `pytest` 269 passed / 2 deselected — **gồm cả 3 test `integration` chạy trên PostgreSQL thật** (`tests/test_concurrency.py`, dùng `TEST_DATABASE_URL` trỏ vào một database riêng để không làm bẩn dev DB) · `ruff check` sạch · `ruff format --check` 66 file đúng · `mypy` strict 46 file không lỗi · `pnpm lint` sạch · `pnpm gen:api-types` sinh lại **không drift**.

### Điều quan trọng nhất cần biết

**Vòng đời nội dung đã khép kín và chạy thật.** Admin dán từ → lưu ở `draft` → worker sinh audio 4 accent → publish (bị chặn nếu audio thiếu hoặc lệch) → học viên ôn tập bằng flashcard SM-2 và làm dictation có chấm theo từng từ. Đã chạy đầu-cuối qua stack Docker, không phải chỉ qua test.

**Thiếu là nội dung, không phải tính năng.** Hiện có **3 từ và 4 câu dictation** — đủ để chứng minh đường đi, không đủ để dạy ai.

**Nút thắt thật là nội dung, không phải code.** Viết endpoint từ vựng mất vài ngày; soạn 500 từ có nghĩa, ví dụ và audio 4 giọng thì lâu hơn nhiều. Đó là lý do Sprint 3 là **công cụ nhập nội dung** chứ không phải Learning Hub: không có công cụ thì không có dữ liệu để test endpoint bằng gì ngoài fixture, và việc soạn nội dung không chạy song song được với việc code.

**`draft` đã có lối ra — nhưng chỉ cho hai loại nội dung.** `vocabulary_entry` và `dictation_item` publish được qua `POST /admin/{loại}/{id}/publish`, và cổng publish **từ chối** khi audio thiếu hoặc lệch khỏi text. `question.status` thì vẫn là trạng thái không ai thoát ra được, vì chưa có endpoint nào chạm tới `question` — đóng ở Sprint 5.

---

## 2. Thứ tự sprint

Đã sắp lại theo yêu cầu: **Learning Hub và TOEIC Practice trước, AI layer sau cùng.**

```
Sprint 3  Content Tooling       🟡 từ vựng + dictation XONG · phần question còn nợ
Sprint 4  Learning Hub          🟡 backend + frontend XONG · thiếu nội dung
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
- [x] **Sửa một lỗi accessibility có thật** — viền ô nhập cũ chỉ đạt 1.48 tương phản (WCAG 1.4.11 đòi 3.0), tức gần như vô hình với người thị lực kém. Token `rule-strong` mới đạt 3.09–3.64

### Nội dung — **việc duy nhất còn lại của sprint này**
- [ ] Soạn ≥ 300 từ vựng cho ≥ 6 chủ đề — hiện có **3**
- [ ] Sinh audio 4 accent × {headword, example} cho toàn bộ — hiện có **38 clip**
- [ ] Soạn ≥ 50 câu dictation — hiện có **4**

Công cụ để làm việc này đã xong và đã chạy thật: dán ở `/admin`, `backfill_audio` sinh audio ngoài luồng, publish chặn nếu audio chưa khớp. Không còn code nào chặn phần này.

### Hợp đồng & chất lượng
- [x] `pnpm gen:api-types` — đã chạy, sinh lại cho ra file y hệt
- [x] `API_ROUTES` đã có đủ 17 lối vào mới
- [x] Test `draft` không lọt ra, cho mọi endpoint đọc

### Định nghĩa hoàn thành
Học viên tạo tài khoản, học một chủ đề, ôn lại hôm sau và thấy đúng những từ đến hạn, làm dictation và nhận điểm chính xác.

---

## 5. Sprint 5 — TOEIC Practice

**Mục tiêu:** luyện theo part và làm đề đầy đủ, có điểm quy đổi.

### ⛔ Chặn phải gỡ trước, không phải sau

**Đường ống audio hiện không sinh được clip nhiều giọng** (`MEDIA-PIPELINE` §10.2). `SpecItem` là `(text, voice)` — một text, một giọng, một file; `voices: [...]` chỉ nhân bản **cùng một text** ra nhiều accent, không diễn đạt được "lượt 1 giọng nam, lượt 2 giọng nữ".

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
- [ ] `POST /api/v1/attempts` — mở lượt làm, sinh `attempt_item` cho **toàn bộ** câu được phục vụ
- [ ] `PATCH /api/v1/attempts/{id}/items/{item_id}` — lưu lựa chọn
- [ ] `POST /api/v1/attempts/{id}/submit` — chốt, gọi `score_attempt()`
- [ ] `GET /api/v1/attempts/{id}` — kết quả kèm giải thích
- [ ] `GET /api/v1/tests` — danh sách đề
- [ ] *(Trình nhập nội dung đã chuyển sang Sprint 3 — [`ADR-005`](ADR-005-CONTENT-TOOLING.md). Ba ràng buộc ở `ADR-001` §B4 có hiệu lực từ đó.)*

### Frontend
- [ ] Giao diện làm bài: đồng hồ đếm ngược, điều hướng câu, đánh dấu xem lại
- [ ] Part 1 hiển thị ảnh + **ghi công** (`ADR-004` §4.2 — lưu attribution mà không hiện ra vẫn là vi phạm CC-BY)
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
- [ ] Cloudflare R2 (`PHASE2-AUDIO.md` §A5) — chặn bởi việc phải có domain trên DNS Cloudflare
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
| **Chưa có nội dung thật** | `ADR-001` §A6.3 | Nút thắt lớn nhất của dự án. 3 từ, 4 câu dictation. Công cụ đã xong — chỉ còn việc soạn |
| Rate limiting | P1-8 → **Sprint 6** | Chặn cứng endpoint LLM đầu tiên |
| Token trong `localStorage` | P1-7 → **Sprint 6** | Cũng là chỗ đầu tiên Redis thật sự được dùng (refresh token + denylist) |
| Không có test frontend/e2e | P1-3 → **Sprint 6** | 0% coverage phía web. Backend thì 269 test. Revamp giao diện vừa rồi **không có lưới an toàn nào** ngoài typecheck và lint |
| Chưa kiểm giao diện ở viewport hẹp | `DESIGN-SYSTEM` §13.3 | Breakpoint đúng trong code, chưa quan sát được ở 360px |
| Branch protection chưa bật | Sprint 0 → **Sprint 6** | Cần quyền admin repo. 13 gate xanh mà không ai bắt buộc thì chỉ là gợi ý |
| `draft` chưa có lối ra cho `question` | `ADR-001` §A4.8 | Từ vựng và dictation **đã có** cổng publish. `question` thì chưa có endpoint nào — Sprint 5 |
| Bản quyền đề ETS | `ADR-005` §2 | `question.source` phải điền đúng ở **từng hàng**. `original` = soạn mới theo cấu trúc; `licensed` = đã thật sự xin phép |
| Audio nhiều giọng bất khả thi | `MEDIA-PIPELINE` §10.2 | `SpecItem` là `(text, voice)` — không diễn đạt được hội thoại. **Chặn Part 2 và Part 3**, tức chặn phần lớn Sprint 5 |
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
