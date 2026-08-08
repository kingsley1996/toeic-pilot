# TOEIC Pilot — Tiến độ & Lộ trình

> **Đây là file theo dõi duy nhất của dự án.** Sprint, task, trạng thái thật của code — tất cả ở đây.
> Cập nhật **ngay khi** hoàn thành một task, không để dồn.
>
> Các tài liệu khác có vai trò khác và **không** chứa trạng thái:
> `PLAN.md` = spec sản phẩm · `ARCHITECTURE.md` = kiến trúc · `ADR-*.md` / `PHASE2-AUDIO.md` = quyết định + lý do · `REVIEW-OPUS.md` = review kỹ thuật (ảnh chụp 2026-08-08, không cập nhật tiếp)

**Cập nhật lần cuối:** 2026-08-09

---

## 1. Đang ở đâu

| | |
|---|---|
| **Phase hiện tại** | Sprint 3 sắp bắt đầu — Learning Hub |
| **Chặn Phase 2** | **Không còn gì.** Cả hai blocker đã gỡ (audio, data model) |
| **Test** | 191 (189 chạy + 2 `external` deselect mặc định) |
| **Gate CI** | 13, tất cả xanh |
| **Migration** | `001_initial` → `002_audio_assets` → `003_domain_schema` → `004_images_and_scoring` |
| **Bảng** | 20 (users + 19 bảng domain/media/scoring) |
| **Endpoint** | 5 — chỉ auth và health. **Chưa có endpoint sản phẩm nào** |

### Điều quan trọng nhất cần biết

**Hạ tầng đã xong; sản phẩm thì chưa bắt đầu.** Schema đầy đủ, đường ống audio và ảnh chạy được, bảng quy đổi điểm đã có. Nhưng chưa có một endpoint sản phẩm nào và **chưa có nội dung thật** — 16 clip audio và 3 ảnh hiện tại chỉ để chứng minh đường ống hoạt động.

**Nút thắt thật của Sprint 3–4 là nội dung, không phải code.** Viết endpoint từ vựng mất vài ngày; soạn 500 từ có nghĩa, ví dụ, và audio 4 giọng thì lâu hơn nhiều. Lên kế hoạch theo đó.

---

## 2. Thứ tự sprint

Đã sắp lại theo yêu cầu: **Learning Hub và TOEIC Practice trước, AI layer sau cùng.**

```
Sprint 3  Learning Hub          ← tiếp theo
Sprint 4  TOEIC Practice
Sprint 5  Hardening & bảo mật   ← bắt buộc trước AI
Sprint 6  AI Layer
Sprint 7  Analytics & Production
```

### ⚠️ Rủi ro đã biết của thứ tự này

`REVIEW-OPUS.md` §7f khuyến nghị chèn một **lát cắt AI mỏng sớm** để giảm rủi ro. Đẩy toàn bộ AI về Sprint 6 nghĩa là phần **khó nhất, khác biệt nhất và rủi ro nhất** của sản phẩm chưa được kiểm chứng cho tới khi dự án đã đi được ~70%. Nếu tới lúc đó mới phát hiện RAG không đủ tốt hoặc chi phí quá cao thì đã muộn.

Đây là lựa chọn có ý thức, không phải sơ suất. Hai thứ giảm thiểu, đã đưa vào Sprint 5:

1. **Rate limiting** (P1-8) phải xong **trước** endpoint LLM đầu tiên. Endpoint LLM không đo đếm là hoá đơn không giới hạn.
2. **`ai_interaction`** (đếm token + chi phí) phải tồn tại từ request LLM đầu tiên, không phải sau. Không đo được thì không cải thiện được; không đếm được thì không giới hạn được.

Nếu muốn giảm rủi ro sớm hơn: chèn một lát cắt AI mỏng **một** use case (ví dụ "giải thích một câu ngữ pháp") vào cuối Sprint 4. Mục tiêu không phải ship mà là xác nhận kiến trúc và đo chi phí thật.

---

## 3. Sprint 3 — Learning Hub

**Mục tiêu:** học viên đăng nhập được, học từ vựng theo chủ đề có phát âm 4 giọng, làm bài dictation và được chấm.

Schema đã sẵn sàng (`ADR-001` §B2). Việc còn lại là endpoint, UI và nội dung.

### Backend
- [ ] `GET /api/v1/topics` — chỉ trả `status='published'`
- [ ] `GET /api/v1/vocabulary` — lọc theo topic, phân trang
- [ ] `GET /api/v1/vocabulary/{id}` — kèm 4 accent audio và câu ví dụ
- [ ] `GET /api/v1/vocabulary/review` — các từ đến hạn ôn (index `ix_vocabulary_review_state_due`)
- [ ] `POST /api/v1/vocabulary/{id}/review` — chấm SM-2, ghi `state` **và** `log`
- [ ] `GET /api/v1/dictation` + `GET /api/v1/dictation/{id}`
- [ ] `POST /api/v1/dictation/{id}/attempt` — chấm theo `dictation_item.transcript`, **không** theo `audio_asset.source_text`
- [ ] Thuật toán SM-2 trong `app/services/` + test cho từng nhánh (đúng/sai/quên lại)
- [ ] Thuật toán chấm dictation: chuẩn hoá, so khớp từng từ, sinh `word_diff`

### Frontend
- [ ] Trang danh sách chủ đề
- [ ] Trang học từ vựng — chọn accent, phát audio bằng thẻ `<audio>` native
- [ ] Phiên ôn tập SRS
- [ ] Trang dictation — phát audio, nhập, xem kết quả tô màu

### Nội dung
- [ ] Soạn ≥ 300 từ vựng cho ≥ 6 chủ đề (nút thắt thật)
- [ ] Sinh audio 4 accent × {headword, example} cho toàn bộ
- [ ] Soạn ≥ 50 câu dictation

### Hợp đồng & chất lượng
- [ ] `pnpm gen:api-types` — **lần đầu tiên thật sự cần chạy**, vì đây là endpoint sản phẩm đầu tiên
- [ ] Thêm entry vào `API_ROUTES` trong `packages/shared/src/index.ts`
- [ ] Test cho mỗi endpoint đọc: nội dung `draft` **không** lọt ra (`ADR-001` §A5.3)

### Định nghĩa hoàn thành
Học viên tạo tài khoản, học một chủ đề, ôn lại hôm sau và thấy đúng những từ đến hạn, làm dictation và nhận điểm chính xác.

---

## 4. Sprint 4 — TOEIC Practice

**Mục tiêu:** luyện theo part và làm đề đầy đủ, có điểm quy đổi.

### Backend
- [ ] `GET /api/v1/practice/parts/{part}` — bốc câu hỏi, tôn trọng `question_set` với part 3, 4, 6, 7
- [ ] `POST /api/v1/attempts` — mở lượt làm, sinh `attempt_item` cho **toàn bộ** câu được phục vụ
- [ ] `PATCH /api/v1/attempts/{id}/items/{item_id}` — lưu lựa chọn
- [ ] `POST /api/v1/attempts/{id}/submit` — chốt, gọi `score_attempt()`
- [ ] `GET /api/v1/attempts/{id}` — kết quả kèm giải thích
- [ ] `GET /api/v1/tests` — danh sách đề
- [ ] Trình nhập nội dung dùng `validators.validate_question()` — ba ràng buộc ở `ADR-001` §B4 chỉ có hiệu lực nếu có thứ gọi tới nó

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

## 5. Sprint 5 — Hardening & bảo mật

**Phải xong trước Sprint 6.** Đây không phải sprint "dọn dẹp": nó chứa các điều kiện tiên quyết cứng của AI layer.

- [ ] **P1-8 Rate limiting** — bắt buộc trước endpoint LLM đầu tiên
- [ ] **P1-7** Token sang httpOnly cookie + refresh token + denylist trên Redis (Redis hiện chưa dùng vào việc gì)
- [ ] **P1-3** Test frontend + Playwright e2e cho luồng auth và một luồng học
- [ ] **Bật branch protection** — treo từ Sprint 0, cần quyền admin repo. 13 gate không bắt buộc thì chỉ là gợi ý
- [ ] P2-6 Dockerfile production: multi-stage, non-root, bỏ `gcc`/`libpq-dev` thừa
- [ ] P2-7 Bỏ fallback `pnpm install --frozen-lockfile || pnpm install`
- [ ] Bảng `ai_interaction` (token, chi phí, latency, `request_id`) — dựng **trước** khi có request LLM

---

## 6. Sprint 6 — AI Layer

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

## 7. Sprint 7 — Analytics & Production

- [ ] Dashboard tiến độ, Learning Memory
- [ ] `user_progress` (nên là view suy ra từ `attempt`, không phải bảng ghi song song)
- [ ] Cloudflare R2 (`PHASE2-AUDIO.md` §A5) — chặn bởi việc phải có domain trên DNS Cloudflare
- [ ] Chính sách PII: bài làm của học viên sẽ được gửi sang LLM provider (§7h)
- [ ] Monitoring, deployment

---

## 8. Đã xong

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

## 9. Nợ kỹ thuật đang mở

| Mục | Ở đâu | Ghi chú |
|---|---|---|
| Chưa có nội dung thật | `ADR-001` §A6.3 | Nút thắt lớn nhất của Sprint 3–4 |
| Rate limiting | P1-8 → Sprint 5 | Chặn cứng Sprint 6 |
| Token trong `localStorage` | P1-7 → Sprint 5 | |
| Không có test frontend/e2e | P1-3 → Sprint 5 | 0% coverage phía web |
| Branch protection chưa bật | Sprint 0 → Sprint 5 | Cần quyền admin repo |
| Bảng quy đổi là **xấp xỉ** | `score_scale.source_note` | Không phải bảng chính thức của ETS. Cần scale riêng cho từng đề trước khi trình bày như điểm ước lượng chính thức |
| `PLAN.md` §9–§10 là nhật ký lẫn trong spec | `REVIEW-OPUS.md` §7h | Đã chuyển vào file này; xoá khỏi `PLAN.md` |
| Chưa có acceptance criteria cho từng Epic | `REVIEW-OPUS.md` §7c | Mục 3 và 4 ở trên là bước đầu |
| Chưa có ảnh cho Part 7 | `ADR-004` §5 | Đề thật đôi khi có biểu đồ/bảng biểu |

---

## 10. Cách cập nhật file này

1. Tick task **ngay khi xong**, đừng để dồn cuối sprint.
2. Sprint kết thúc → gom xuống mục 8 kèm số liệu thật (số test, số migration), không phải mô tả chung chung.
3. **Lỗi phát hiện nhờ chạy thật thì ghi lại** — mục 8 quý ở chỗ đó, không phải ở danh sách tính năng.
4. Quyết định kiến trúc thì viết ADR, **đừng** viết vào đây; ở đây chỉ để link tới.
5. Đổi số liệu ở mục 1 mỗi lần thêm migration hoặc thêm nhóm test.
