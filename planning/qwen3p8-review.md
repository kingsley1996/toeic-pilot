# Review — qwen3.8-max-free · 2026-08-16

> **Ảnh chụp theo ngày, không cập nhật tiếp.** Review này gắn với commit `564e064`;
> các con số trong nó (dòng code, số file qua gate) là của thời điểm đó. Không còn
> mục nào để mở. Trạng thái hôm nay ở [`ROADMAP.md`](ROADMAP.md).

Review toàn bộ source tại `564e064` (main). Đọc hết backend (routes, services, models, core,
content pipeline), frontend (`apps/web`), e2e, CI, Docker; đối chiếu từng convention trong
CLAUDE.md. Số lượng: ~29k dòng Python, ~14k dòng TS/TSX.

## 0. Trạng thái kiểm chứng lúc review (main @ 564e064)

| Gate | Kết quả |
|---|---|
| ruff check / format | xanh, 134 files |
| mypy strict | xanh, 96 files |
| alembic heads | **một head** `023_option_translation` — lỗi multiple-head đã sửa ở `da2d0bc` |
| pytest backend | **576 pass, 1 FAIL**: `test_part_3_needs_a_shared_script_on_the_set` |
| tsc --noEmit (web) | xanh |
| eslint (web) | xanh |

### 🛑 Chặn ngay: CI `api` job đang đỏ vì chính commit hôm nay

Commit `674cbb2` ("[FIX] upload audio by cmd") đã **comment bỏ kiểm tra `[SCRIPT]` bắt buộc
cho cụm Part 3/4** trong `_check_listening_group` (`app/services/content_import.py:770-771`)
nhưng giữ lại test `test_part_3_needs_a_shared_script_on_the_set` (`tests/test_content_import.py:223`).
Test đang đỏ → bước pytest của job `api` sẽ fail. Đây là guard chặn xuất bản một cụm nghe
không có gì để thu — bỏ nó nghĩa là cụm Part 3/4 thiếu lời thoại đi thẳng qua cổng dán
và chỉ chết ở cổng xuất bản, hoặc tệ hơn, nhập audio gắn tay che lấp chỗ thiếu.

**Chọn một trong hai, không được để cả hai:**
1. Khôi phục kiểm tra và test (nếu guard vẫn đúng), hoặc
2. Nếu cố ý bỏ (vì luồng `import_media` gắn audio sau khi dán), thì xoá/bổ sung test cho
   khớp hành vi mới và ghi rõ vào CLAUDE.md tại sao tác giả-dán không còn bắt buộc `[SCRIPT]`.

---

## 1. Tìm thấy theo mức độ

### HIGH

**H1. `session.tsx` — cờ `rejected` không bao giờ được reset** (`apps/web/src/lib/session.tsx:66,118`)
`/auth/me` hỏng đặt `rejected=true`; đăng nhập lại trong cùng SPA session, token mới và
`user` mới được nạp, nhưng `status` vẫn suy ra thành `"anonymous"` vì `rejected` còn
nguyên — người dùng đã đăng nhập mà app coi như chưa, cho tới khi reload cứng.
Sửa: reset `rejected` ở đầu effect fetch khi `token` đổi (nó mô tả lần fetch *trước*).

**H2. `session.tsx` — mọi lỗi `/auth/me` đều xoá token** (`session.tsx:78-84`)
Catch xoá `accessToken` vô điều kiện: 503, rớt mạng, Redis lỗi — token đang hợp lệ vẫn
bị vứt, người dùng văng ra "anonymous". Chỉ nên xoá khi 401 (token hết hạn/giả mạo).

**H3. PATCH dictation cho phép editor đưa `status: "published"`** (`app/api/routes/admin.py:394-435, 816-942`)
Bốn endpoint PATCH (item/topic/section/story) dùng quyền `can_edit` và schema nhận `status`,
trong khi xuất bản phải đi qua endpoint riêng quyền `can_publish` (admin) kèm cổng kiểm
audio-còn-khớp-transcript (`publish_dictation`, line 446-455). Một **editor** patch
`status:"published"` là vượt cả tách nhiệm editor/admin lẫn cổng audio — đúng cái lỗi
"chấm sai câu chưa từng được nghe" mà cổng xuất bản tồn tại để chặn.
Sửa: bỏ `status` khỏi các schema PATCH này (xuất bản chỉ qua endpoint chuyên dụng).

**H4. `save_answer` không kiểm option thuộc câu đang trả lời** (`app/api/routes/attempt.py:556-564`)
`item.selected_option_id` nhận UUID bất kỳ của bảng `question_option` (FK trỏ bảng, không
trỏ câu). Đáp án trỏ sang option của câu khác được lưu và chấm sai im lặng; ở chế độ
luyện tập còn lộ `content_vi`/`spoken_text` của câu kia qua `_state`.
Sửa: trong `_load` kiểm `selected_option_id ∈ {o.id for o in question.options}`, 400/404 nếu sai.

### MEDIUM

**M1. `enrich_skills.pending_sets` bỏ qua `--limit`** (`app/content/enrich_skills.py:194-204`)
`pending()` cắt `todo[:limit]` nhưng `pending_sets` không cắt — `--limit 5` gán 5 câu
nhưng **toàn bộ** set pending. "Lượt thử nhỏ" ghi trong CLAUDE.md thực tế phát lệnh LLM
và commit nhãn cho hàng trăm set. Sửa: `return [...] [:limit]`.

**M2. `run_backfill` phớt lờ `settings.manifest_path`** (`app/content/backfill_audio.py:452,477`)
`generate.py` tôn trọng `MANIFEST_PATH` (dòng 302), backfill thì hard-code
`DEFAULT_MANIFEST_PATH`. Nếu env đó được đặt, hai lệnh duy trì **hai manifest khác nhau**
— backfill sinh lại clip đã có trong manifest kia, manifest commit lệch DB.
Sửa: dùng `settings.manifest_path` cả hai đầu.

**M3. Manifest bị đọc-sửa-ghi xuyên process không có khoá** (`app/content/manifest.py:90-104`)
Atomic từng lần ghi (tmp+rename) nhưng hai process chạy chồng (worker dài hạn + một
`backfill_audio` tay) thì process sau ghi đè cả file, **mất im lặng** entry của process
trước; bytes còn trên đĩa nhưng `seed` ở máy mới không tạo row. Sửa: file lock quanh
đọc→ghi, hoặc append-then-dedupe.

**M4. `validate_question` không kiểm option của các part in chữ** (`app/models/validators.py:46-56`)
Cổng xuất bản kiểm `prompt_text` in-chữ phải khác None nhưng **không** kiểm
`option.content` cho part 3-7. `edit_question` cho phép ghi `content=""` → xuất bản một
câu có đáp án rỗng. Đây chính là biên None-vs-`""` CLAUDE.md dựng lên.
Sửa: trong nhánh in-chữ, kiểm mọi option có `content` không rỗng.

**M5. Đầu vào dictation/recall không giới hạn độ dài** (`app/schemas/learning.py:115-125,168-169`)
`RecallSubmit.typed` và `DictationSubmit.submitted_text` không `max_length`; diff
`SequenceMatcher` là O(n·m) — một submit vài MB ghim worker. Sửa: đặt `max_length` rộng
rãi hơn mọi transcript thật, quá cỡ thì 422.

**M6. OpenRouter trả `{"choices": []}` lọt guard thành `IndexError`** (`app/services/llm/openrouter.py:100-105`)
Guard `"choices" not in body` pass với mảng rỗng, `body["choices"][0]` ném IndexError → 500
mờ mịt, không ghi sổ ledger. Sửa: `if not body.get("choices"):` → `LLMError`.

**M7. Trang chi-tiết đề thi vi phạm ba-trạng-thái auth** (`apps/web/src/app/learn/tests/[slug]/[testSlug]/page.tsx:325-340`)
`status === "authenticated" ? <nút thi> : <mời đăng nhập>` — nhánh else chạy cả khi
`loading`, người đã đăng nhập thoáng thấy "Đăng nhập để làm bài". Đây đúng regession
CLAUDE.md mô tả. Sửa: CTA đăng nhập chỉ khi `status === "anonymous"`.

**M8. Lịch sử attempt và dropdown bài nghe bị cắt trang im lặng**
- `learn/attempts/page.tsx:42-48` — fetch không `limit`, chỉ đọc `items`, bỏ `total`;
  quá 50 lượt là danh sách lẫn bộ đếm "đang làm dở" sai; `.catch(() => [])` đánh đồng lỗi mạng
  với "chưa làm đề nào".
- `admin/dictation/page.tsx:76-78` — dropdown "Thuộc bài" mất đuôi quá ~50 story, editor
  không gắn được câu vào bài có sẵn. Sửa theo mẫu trang cây: `limit=200` + thông báo
  nếu `total` vượt.

### LOW

**L1. Lỗi `uuid.UUID(...)` trên chuỗi body → 500 thay vì 422** (`admin.py:181,325,329,407,416,976; admin_tests.py:862,1267; attempt.py:561`). Typed schema thành `uuid.UUID` là hết cả chùm.

**L2. `rate_explanation` không có rate limit** (`coach.py:166-193`) — endpoint ghi duy nhất trong 3 endpoint coach không có `rate_limit`; PK chặn dữ liệu phình nhưng Postgres hứng đủ một vòng lặp client.

**L3. Trần 20 thẻ-mới tính theo 24h UTC lăn, không theo "hôm nay" múi giờ người học** (`learning.py:384-394`) — mâu thuẫn quy ước streak theo timezone profile; học tối ở Hà Nội reset lúc 17:00.

**L4. `ai_budget.charge`: `EXPIRE` sau `INCRBY` không atomic** (`core/ai_budget.py:69-84`) — nếu expire ném lỗi, key sống vĩnh viễn → khoá ngân sách vĩnh viễn cho một user. Sửa dùng pipeline.

**L5. Gateway: `cost_usd`/provider lookup ngoài khối ghi lỗi** (`llm/gateway.py:110-131`) — model cấu hình sai ném `UnknownModel`/`KeyError` → 500 không có dòng ledger.

**L6. Backfill: manifest chỉ ghi cuối lượt** (`backfill_audio.py:469-477`) — SIGKILL/disk lỗi cuối lượt mất cả sweep; `enrich_skills` commit từng nhãn chính vì lý do này. Thêm commit+flush định kỳ.

**L7. `images.py` không giới hạn kích thước tải về** (`images.py:85-89`) — URL độc trong spec đọc cả body vào RAM; spec cũng bị parse lười giữa vòng lặp (manifest chưa ghi nếu dòng JSON hỏng ở dòng N → N-1 ảnh tải rồi mất sổ).

**L8. Import ảnh tin extension, không tin bytes** (`import_media.py:462-472`) — audio đã được ffprobe theo container thật từ commit `674cbb2` (tốt), nhưng ảnh vẫn đoán MIME/ext từ `path.suffix`; `.png` là JPEG vẫn nhận key `.png` + `image/png`; `.JPG` hoa qua được check suffix thường. Sửa theo audio: PIL `format`.

**L9. `--alt-text` được chấp nhận im lặng cho Part 1** (`import_media.py:541-544,563-568`) — ADR-004 nói ảnh Part 1 *không được* có alt text vì ảnh chính là đề. Sửa: từ chối `--alt-text` khi `--part 1`.

**L10. Coach phục vụ cả explanation `draft`** (`services/coach.py:280-287`, `models/coach.py:22-26`) — cache lấy `status != "rejected"`, không có path nào chuyển `published`. Nếu quy trình "người duyệt trước" là ý định thì đang không được thực thi; nếu assertions là cổng duy nhất thì `published`/`reviewed_by` là cột chết. Cần chốt thiết kế.

**L11. `local_upload` đọc cả body vào RAM trước khi kiểm size** (`media.py:222-227`) — dev-only nhưng vẫn nên stream theo chunk và cắt ở `MAX_IMAGE_BYTES`.

**L12. Ký tự `\n` in ra thành `\`+`n`** (`import_media.py:616,665`) — `f"\\n…"` escape hai lần trên đường báo lỗi. Vặt vãnh nhưng ở chỗ người dùng phải đọc.

### NIT

- `media.py` confirm chỉ kiểm key tồn tại trên driver, không phải key vé đã phát — phòng thủ nhiều lớp thôi.
- `admin_tests.edit_question` commit trước khi kiểm câu thuộc đề → mutate xong rồi 409 (admin_tests.py:755-762).
- Backfill audio upload ghi `engine="uploaded"`/`"-"`, đường browser ghi `"upload"`/`"1"` — hai chính tả một khái niệm.
- `_gateway_for` gọi `get_redis()` thẳng (`coach.py:230`) thay `Depends` — lệch convention test-override.
- `seed_demo_test` vẫn dùng `LIKE 'prefix%'` trên `source_text` — CLAUDE.md đã ghi là mẫu lỗi thời, bẫy nếu copy sang Part 2/3.
- `submit_attempt` không gọi `_expire_if_out_of_time` — hết giờ nộp tay lưu `submitted` chứ không `expired` (attempt.py:607-618).
- `e2e/auth.spec.ts:82` hard-code URL + path — dùng `API_ROUTES` + base env thì trọn quy ước "không hard-code".
- Local type `Message`/`Turn` ở `coach-chat.tsx:10-11` và `Envelope<T>` ở `admin/ai/skill-tags:30` sao chép contract sinh tự động — re-export alias từ `packages/shared` thì hết drift.

---

## 2. Những quy ước đã kiểm và **đúng**

- **Tách ly `app.content`**: không import nào từ `app/main.py` chạm `app/content`; test isolation pass.
- **`require_role` là dependency, không kiểm trong thân**: cả 70 route đăng ký ở 4 router admin — không chỗ nào kiểm vai trò trong handler.
- **Join đề thi**: `start_attempt` lọc `published` cả câu lẫn set bằng **outer join** (không rớt part 1/2/5).
- **Sắp xếp phân trang**: mọi truy vấn phân trang offset đều kết bằng tiebreaker `id`.
- **Mô hình đăng ký đủ**: `app/models/__init__.py` re-export toàn bộ; không bảng nào thiếu.
- **Hash input, không hash output**: `source_hash`, `conversation_source_hash` (kèm thứ tự turn + gap), `script_fingerprint`, `upload_source_hash` — đúng thiết kế `\x1f` separator.
- **`EXTERNAL` không bị ghi đè**: `_REGENERATE=(MISSING, STALE)` áp ở cả ba chỗ; clip upload không bao giờ bị TTS worker sinh lại.
- **Sweep-là-truy-vấn**: không bảng queue; cửa chuông Redis 202; chạy lại chỉ thấy ít việc hơn.
- **push/reconcile không xoá bytes trên provider**; reconcile đủ cả 4 cột FK mỗi loại asset, avatar miễn kiểm đúng.
- **import_media từ chối nửa-vời**, có dry-run bảng mapping, bóc nhãn `part N` trước khi đọc số đầu, `source="uploaded"`.
- **Định tuyến `srs.py`/`scoring.py`/`dictation.py` thuần, không LLM**; scoring thiếu thang điểm ném `ScaleNotFoundError` chứ không nội suy; `is_complete` đòi mọi token diff là `match`.
- **bcrypt 72 bytes** bắt tường minh, không truncate; `pwc` so bằng microsecond; `jti` denylist TTL bằng thời hạn token.
- **Rate limit**: anonymous khoá IP cuối XFF (đúng), fail-open; quota user fail-closed (đúng lý do hoá đơn); `trust_forwarded_for` mặc định off.
- **`/health` không chạm DB**, `/ready` có.
- **XSS**: `dangerouslySetInnerHTML` duy nhất là script init theme hằng số.
- **`dictation.ts` port đúng**: thứ tự lowercase-rồi-strip, `\p{L}\p{N}_` + flag `u`, `SequenceMatcher` khớp Python.
- **Design system**: sạch ngoại trừ một `shadow-[…]` ở sticky header `learn/attempts/[attemptId]/page.tsx:294`.

---

## 3. Đề xuất thứ tự sửa

1. **(H0/chặn CI)** Quyết định chuyện `[SCRIPT]` Part 3/4 — khôi phục hoặc xoá test cho khớp; commit hôm nay đang làm job `api` đỏ.
2. **H3** bỏ `status` khỏi 4 schema PATCH dictation — lỗ vượt quyền xuất bản.
3. **H1/H2** `session.tsx`: reset `rejected` + chỉ xoá token khi 401.
4. **H4** `save_answer` kiểm option thuộc câu.
5. **M4** validate_question chặn option rỗng cho part in chữ.
6. **M1/M2/M3** bộ ba content-pipeline: `--limit` cho sets, `settings.manifest_path`, khoá file cho manifest.
7. **M7/M8** auth ba-trạng-thái trang đề thi + hai danh sách bị cắt trang.
8. **M5/M6** giới hạn đầu vào + guard `choices` rỗng.
9. Phần LOW/NIT làm dần; L1 (typed UUID) nên gộp một PR nhỏ vì là chùm cùng loại.
