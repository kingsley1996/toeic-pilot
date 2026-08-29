# TOEIC Pilot — System Overview

Đọc từ source lần cuối: **2026-08-29** (commit `cc3d97c`).

> Bản đồ toàn hệ thống đọc trực tiếp từ source — mô tả **hiện trạng**, không phải kế hoạch. Phạm vi sản phẩm nằm ở [`PLAN.md`](PLAN.md); trạng thái sprint ở [`ROADMAP.md`](ROADMAP.md); lý do đằng sau từng quyết định nằm ở các ADR — file này chỉ trỏ tới, không nhắc lại.

## Con số đo được (2026-08-29)

| Thứ | Số |
|---|---|
| Bảng Postgres | **56** (50 migrations, `001` → `050`) |
| Router có endpoint | **21**, **184** thao tác HTTP (+1 nhận upload local, chỉ dev) |
| Trang Next.js (`page.tsx`) | **48**; components 54, lib 15 (122 tệp TS/TSX) |
| Contract sinh ra | `api-types.ts` ~12 600 dòng |
| Test backend | **903** collected (901 chạy, 2 `external` bị deselect) trong 55 tệp |
| E2E Playwright | 8 spec, chạy chống docker stack đang sống |
| `app/services/` | 35 module + 9 trong `llm/` |
| `app/content/` | 24 module + 9 trong `exam/` |

## 1. Monorepo

- `apps/api` — FastAPI (Python 3.12, quản bằng `uv`), ngoài graph Turborepo.
- `apps/web` — Next.js 16 App Router (React, Turbopack).
- `packages/shared` — contract **sinh ra** từ OpenAPI của FastAPI (`pnpm gen:api-types`) + `API_ROUTES` viết tay. Web import `dist/` đã build, không phải `src/`.
- `docker/` — ba image: `api` (mỏng, không compiler, không `content` extra), `worker` (có ffmpeg + `content`, chạy root vì ghi qua bind mount), `web`.
- `planning/` — spec, roadmap, ADR.

## 2. Backend — `apps/api`

### 2.1 `main.py` khoá những gì

- Lifespan: `create_all` **chỉ khi** `environment == "development"`; ngoài ra Alembic sở hữu schema.
- Redis ping lúc khởi động chỉ log cảnh báo — Redis là phụ thuộc mềm (trừ hai chỗ, xem §9).
- Middleware: `RequestContextMiddleware` (X-Request-ID, log một dòng/request), CORS từ `settings.cors_origins`.
- Mount `/media` (static) và `media.local_upload_router` **chỉ khi dev** — production media đi thẳng nhà cung cấp, không byte nào qua API.

### 2.2 Bản đồ router (prefix `/api/v1`)

| Nhóm | Router (số endpoint) | Vai trò |
|---|---|---|
| Sống còn | `health` (2) | `/health` liveness không kiểm gì; `/ready` kiểm Postgres + ping Redis, và **ghi `health_sample`** (throttle 1 phút/bản ghi, trong tiến trình) |
| Danh tính | `auth` (5) | register, login, me, đổi mật khẩu (trả token mới, thu hồi generation cũ qua `pwc`), logout (denylist theo `jti`) |
| | `oauth` (4) | Google/Apple, luồng mã phía máy chủ, `state`/`nonce` trong Redis, **fail closed** |
| Hồ sơ & học tập | `profile` (10) | hồ sơ, thống kê suy ra, avatar, việc hôm nay, tiến độ từ vựng |
| | `learning` (22) | Learning Hub: từ vựng, ôn SM-2, dictation — **mỗi tầng tự lọc `published`** |
| | `practice` (3) | đọc bộ đề/đề/cấu trúc — công khai, không đòi đăng nhập |
| | `attempt` (6) | làm bài: bắt đầu, lưu câu, gắn cờ, nộp, xem lại — **đáp án không rời máy chủ khi đang thi** |
| | `coach` (4) | giải thích câu làm sai (chỉ sau khi nộp) + hội hỏi đáp; đọc từ cache bảng |
| | `assistant` (2) | trợ lý trang web: hỏi đáp về chính TOEIC Pilot và tiến độ của người hỏi — ngữ cảnh là bản hướng dẫn viết tay cộng số thật, **không neo vào lượt làm bài** |
| | `appearance` (2) | nền lưới động: một đọc công khai, một ghi admin |
| Góc thú | `pet` (11) | trạng thái thú, hành động, loài, gacha, chạm mặt (ADR-010/012/013) |
| | `petland_map` (2) | đọc/ghi bản đồ — 204 khi chưa ai ghi đè (`petland_map` là override của `public/pet/map.json`) |
| | `ruby` (2) | ví ruby: số dư, lịch sử (ADR-011) |
| Quản trị nội dung | `admin` (41) | dán → xem trước → commit → publish cho từ vựng + dictation + cây của nó; **parse không bao giờ ghi** (ADR-005) |
| | `admin_tests` (28) | soạn đề luyện từng part; script audio nằm trên câu/set (ADR-007) |
| | `admin_ai` (9) | bấm chuông worker, xem thống kê, duyệt nhãn — **không endpoint nào chạy model** |
| Quản trị vận hành | `admin_progression` (14) | XP, khe việc hôm nay, bậc level, khung avatar, luật badge — bảng hệ số là hàng, không phải hằng số |
| | `admin_pet` (8) | bảng loài + hạng hiếm — quyết định vận hành, `require_role("admin")` |
| | `admin_ruby` (2) | mức thưởng ruby — giá cả nền kinh tế, cũng `admin` |
| | `admin_system` (2) | trạng thái production sống (ADR-014); media được probe **từ trình duyệt** vì đó là đường thật |
| Media | `media` (5) | xin vé → xác nhận (ADR-006 §2.3); API chỉ đứng ở bước 1 và 4 |

Mọi endpoint admin đi qua `require_role` **làm dependency**; mỗi endpoint có một test khẳng định `learner` nhận 403.

### 2.3 `app/services/` — logic không phải HTTP

Bốn loại, và ranh giới giữa chúng là thứ giữ hệ thống test được:

**Thuần số học, không session** — `srs.py` (SM-2, grade 0–6 với 6 là "mastered" đặt cứng interval), `dictation.py` (chuẩn hoá + `SequenceMatcher`), `leveling.py` (đường cong level), `pet.py` (nhu cầu trừ theo thời gian, ba hành động), `recall.py` (chấm gõ lại từ — chấm ở **server**, khác dictation), `scoring.py` (raw → scaled, tra bảng và **từ chối đoán** khi thiếu conversion).

**Suy ra, không lưu bảng tổng** — `profile_stats.py` (streak tính theo timezone của hồ sơ), `badges.py` (từ lịch sử học, không phải sổ XP), `daily_tasks.py` (ba khe cố định, target bị clamp), `ai_stats.py` (từ sổ cái AI), `health_history.py` (ghi/tổng hợp `health_sample`), `encounters.py` (sinh lúc ĐỌC — không có đồng hồ chạy khi không ai nhìn).

**Sổ cái, đường ghi duy nhất** — `progression.py` (`xp_event`, chạm cap khi **ghi**, không bao giờ đụng vào hoạt động gốc), `ruby.py` (`ruby_event`), `ruby_daily.py` (chính sách ba nguồn theo ngày, tách khỏi sổ cái), `progression_config.py` + `pet_species.py` (đọc và seed lười khi bảng trống — bảng trống nghĩa là "chưa cấu hình", không phải "cố ý rỗng").

**Còn lại** — `content_import.py` (parser dán, trả lỗi chứ không raise), `media_state.py` (clip có còn khớp text? — so fingerprint, không so timestamp), `labels.py` (**sinh ra** từ taxonomy, không sửa tay), `oauth.py` (mã uỷ quyền phía server, không SDK), `gacha.py` (quay ở **máy chủ**, trả bằng ruby), `chat.py`/`coach.py`/`retrieval.py` (lớp Coach), `ai_features.py` (danh mục tính năng trong mã, cấu hình trong bảng).

### 2.4 `app/models/` — 56 bảng theo nhóm

- **Danh tính:** `users`, `user_profile` (1:1, khoá chính = khoá ngoại, tạo ngay khi register), `user_identity` (theo `sub` của nhà cung cấp, không phải email).
- **Từ vựng:** `vocabulary_entry`, `vocabulary_collection(_item)`, `vocabulary_topic`, `vocabulary_review_state`, `vocabulary_review_log` (grade 0–6), `vocabulary_topic_session` (bảng học nằm trên server), `vocabulary_audio`.
- **Dictation:** cây `dictation_topic → section → story → item` + `dictation_attempt`.
- **Luyện đề:** `test_collection`, `practice_test`, `practice_test_question`, `question`, `question_option`, `question_set`, `attempt(_item/_part)`, `score_scale`, `score_conversion`.
- **Nhãn (migration 019):** `question_label`, `question_set_label` — PK `(owner_id, facet)` ép "một nhãn mỗi facet"; 4 facet thuộc về set chứ không phải câu.
- **AI/Coach:** `ai_interaction`, `ai_feature_config`, `coach_explanation` (cache, khoá có `prompt_version`), `coach_conversation`, `coach_message`, `coach_feedback`.
- **Level & thưởng:** `xp_event`, `daily_task_slot`, `level_tier`, `user_badge`, `badge_rule`, `frame_tier`, `progression_setting`.
- **Góc thú:** `pet_state`, `pet_owned`, `pet_species`, `egg_setting`, `petland_map` (1 hàng, `CHECK id = 1`), `ruby_event`, `ruby_rule`, `encounter`, `encounter_setting`.
- **Media & hệ thống:** `audio_asset`, `image_asset`, `backdrop_setting`, `health_sample`.

Luật chung: `app/models/__init__.py` re-export **mọi** model — đó là cái `alembic/env.py`, `main.py` và `tests/conftest.py` đều dựa vào. `models/validators.py` giữ các luật không viết thành constraint được; `models/mixins.py` giữ cột status/created_at dùng chung.

### 2.5 `app/core/`

`config.py` (một singleton `settings`, `env_file` đường dẫn tuyệt đối, chờ `SECRET_KEY` placeholder ở production), `database.py`, `security.py` (bcrypt thẳng, giới hạn 72 **byte**), `logging.py`, `media.py` (đặt tên theo nội dung, stdlib thuần, cả hai phía cùng import), `storage.py` (driver lưu trữ: local / S3-tương-thông / Cloudinary — nằm ở `core/` vì cả API lẫn pipeline cần đọc, nhưng **ghi** thì không handler nào với tới), `rate_limit.py`, `token_denylist.py`, `redis_client.py`, `ai_budget.py` (trần chi tiêu, **fail closed**), `audio_jobs.py` + `ai_jobs.py` (hai cái chuông Redis — không hơn).

## 3. Lớp AI

Đường đi của một lượt gọi LLM: **`llm/gateway.py`** là chỗ duy nhất mọi call đi qua — kiểm hạn mức → chọn tầng (`router.py`) → gọi → ghi sổ. Adapter được dựng tại **một chỗ duy nhất** (`llm/providers.py`) cho cả đường phục vụ lẫn pipeline, tra theo thứ tự: ollama → openrouter → builtin `ENDPOINTS` → **`apps/api/llm_providers.json`** — file cấu hình provider custom (base_url + tên biến khoá + bảng giá), nơi thêm provider mới **không cần sửa mã**; khoá không bao giờ nằm trong file vì file được commit. Provider thiếu khoá bị bỏ qua lúc dựng (`strict=False` ở đường phục vụ; CLI chết ngay với thông báo rõ), và lượt gọi tới provider thiếu là `LLMError` 503 có ghi sổ chứ không phải KeyError 500. `fake.py` là bản duy nhất test được phép chạm. `pricing.py` tự quy token ra tiền, `retry.py` lùi rồi thử lại với quá tải tạm thời (`LLMQuotaExhausted` là subclass — `except` nó **trước** `LLMError`).

Người tiêu: `coach.py` (giải thích câu sai — cache bảng, `prompt_version` trong khoá), `chat.py` (hỏi đáp, neo ngữ cảnh qua `retrieval.py` — hôm nay là `AnchoredRetriever` lấy từ chính câu hỏi; RAG bị chặn bởi **nội dung**, ngưỡng gỡ chặn ghi bằng số ở [ADR-003](ADR-003-AI-LAYER.md) §3.3), `content/enrich_skills.py` (gắn nhãn, **một facet mỗi call**, commit từng nhãn), `content/generate_exam.py` (sinh đề, §4.3).

## 4. Content pipeline — `app/content/`

Tách khỏi API cả về import lẫn image: **không gì từ `app/main.py` với tới được** (`tests/test_content_isolation.py` chặn trong subprocess; image production build `--no-dev` không có extra `content`). Mọi lệnh chạy bằng `uv run --extra content`, ngoài luồng phục vụ.

### 4.1 TTS & audio

`generate.py` (spec JSONL → mp3 + manifest), `tts.py` (engine seam, edge-tts), `audio_join.py` (ghép nhiều lượt nói — thứ mở khoá Part 2/3), `manifest.py` (bàn giao giữa nửa sinh và nửa ghi DB). Tên file theo **nội dung**: hash của (text | giọng logic | engine | phiên bản), không phải của byte mp3. `seed.py` upsert `audio_asset` theo `source_hash`.

### 4.2 Ảnh

`images.py` (fetch + chuẩn hoá ảnh Part 1 mở phép, UA định danh,pace theo nhịp), đẩy lên **Cloudinary** — cả ảnh fetch cũng vậy. `photos.py` trong sinh đề đi chiều ngược: mô tả → prompt vẽ (ADR-004 giữ licence, TOEIC-PIPELINE §8 ghi chiều phụ thuộc ngược).

### 4.3 Sinh đề — `generate_exam.py`, bốn chặng

`plan` (blueprint: thiết kế đề **trước** khi gọi model — model viết câu giỏi hơn thiết kế đề) → `write` (một ô một lượt call, xuất ra **định dạng dán**) → `check` (ba tầng kiểm, tầng đầu gọi thẳng parser thật) → `load` (đi qua **đúng đường dán** của `admin_tests`, gọi HTTP với token editor). Phụ trợ: `balance.py` (cân vị trí đáp án — model có thiên lệch vị trí rất mạnh), `graphics.py` + `fonts.py` (hình Part 3/4 **vẽ từ dữ liệu**, không dùng model ảnh). Mỗi chặng đọc/ghi tệp dưới `content/generated/<slug>/`, chạy lại chặng sau không trả tiền lại chặng trước.

### 4.4 Workers và lệnh bảo trì

- `tts_worker.py`, `skilltag_worker.py` — tiến trình dài: nghe chuông Redis + quét định kỳ 300s; hàng đợi là một **câu truy vấn** ("cái gì đang thiếu?"), không có bảng job.
- `backfill_audio.py`, `enrich_skills.py` — một lượt rồi thoát, có `--dry-run`.
- `import_media.py` (gắn media có sẵn vào đề đã dán, `--dry-run` bắt buộc trước, từ chối làm nửa vời), `push_media.py` (đẩy local → provider; ảnh sang Cloudinary, audio sang S3), `reconcile_media.py` (tìm rác; `--delete-rows` chỉ đụng DB), `seed_scores.py`, `seed_demo_test.py`, `seed_dictation.py`.

## 5. Frontend — `apps/web`

### 5.1 Shells & session

- **Một shell, hai bộ link** (`components/shell.tsx`): `TopBarShell` cho ba trang ngoài app (`/`, `/login`, `/register`), `SidebarShell` cho mọi thứ còn lại kể cả `/admin/**`. Chọn theo **pathname**, không theo session status.
- **Session ba trạng thái** (`lib/session.tsx`): `loading` ≠ `anonymous` ≠ `authenticated`, vì `localStorage` không tồn tại lúc server render. `status` là derived, không lưu bằng effect.
- `useRequireSession({ canEdit: true })` **redirect**, không渲染 403; ranh giới thật vẫn do `require_role` phía server giữ.
- Design system: primitive trong `components/ui.tsx`, màu từ CSS variable (sáng/tối một định nghĩa), không `box-shadow`, một bán kính 4px, `rule-strong` cho biên thành phần.

### 5.2 Bản đồ trang (47)

- **Ngoài app:** `/` (landing), `/login`, `/register`, `/auth/callback` (OAuth).
- **Học viên:** `/dashboard` (đọc số từ `/vocabulary-progress` + `/profile/stats`, đọc daily-tasks **trước** progression); `/learn/**` — từ vựng (hub, topic, typing, match, quiz, collection), dictation (hub, topic, section, story, standalone, random), luyện đề (danh sách → đề → làm bài), review, typing, attempts (danh sách + chi tiết), assistant (trợ lý AI); `/profile` + `/profile/badges`; `/petlab` (phòng thí nghiệm góc thú).
- **Quản trị (18):** `/admin` + từ vựng (hub + cây), dictation (hub + cây), tests (danh sách + `[slug]`), ai (hub, providers, skill-tags), appearance, pet, petland (trình vẽ bản đồ), progression (+ preview khung avatar), ruby, health, system.
- `preview/attempt-result` — trang xem trước kết quả, không qua đăng nhập thật.

### 5.3 Petland subsystem

`components/petland.tsx` + mười tám tệp `petland-*`: sprite (duy nhất biết đường `/mascots/`), render, map, clock, creature, quest, speech, palette, eggs, bestiary, collection, history, music-toggle… Ranh giới do `scripts/check-petland-layers.mjs` ép lúc build: UI không import được sprite/scene/fx; `petland-pet.ts` không import React. Ba số `cell`/`footY`/`anchorX` do `scripts/pack-pet.mjs` đo và `check-petland-fit.mjs` so exactly — không chọn bằng mắt. Bản đồ công khai là `public/pet/map.json`; `petland_map` trên DB là override, và màn hình vẽ nói ra bản nào đang sống.

### 5.4 `lib/`

`api.ts` (`apiFetch`/`apiSend`, path từ `API_ROUTES` — generic do **caller** cung cấp, nên đổi shape response `tsc` không thấy), `session.tsx`, `dictation.ts` (**port từng bước** của `app/services/dictation.py` — client chấm cho phản hồi tức thì, server chấm lại và số của server là số lưu), `attempt.ts`, `progression.ts`, `audio-upload.ts`/`image-upload.ts`/`upload.ts` (vé → POST thẳng → xác nhận), `game.ts` + `petland-*` (logic góc thú phía client), `sound.ts`/`petland-music.ts` (âm thanh, nhạc nền mặc định **tắt**), `theme.ts`, `toast.tsx`, `auth-storage.ts`, `url-once.ts`.

## 6. Hạ tầng & vận hành

- **Compose:** `postgres` (pgvector, bật từ migration đầu nhưng chưa dùng), `redis`, `api`, `worker`, `web`. `api-entrypoint.sh` chạy `alembic upgrade head` trước khi bind; `web-entrypoint.sh` chạy `pnpm install --frozen-lockfile` + build lại `shared`. Bind mount chỉ `apps/api/app` (không bao giờ cả thư mục — `.venv` macOS sẽ đè `.venv` Linux).
- **CI (4 job, đều required):** `api` (ruff, format, mypy strict, `alembic upgrade head`, pytest với Postgres + Redis service), `web` (prettier, build shared, eslint, build), `contract` (sinh lại types, lệch là fail), `docker` (build cả ba image **và boot image API**).
- **Production (ADR-014):** Vercel + Render + Supabase + Upstash + Cloudinary, không thẻ tín dụng. API chạy **image build sẵn từ GHCR** — image-backed service không redeploy khi tag mới xuất hiện, CI phải gọi deploy hook. Web không thể Dockerise trên Render (1 488/750 giờ free).
- **Redis:** hai hành vi — fail **open** (auth rate limit, token denylist, chuông worker) và fail **closed** (`ai_budget`, `oauth` state). Vị trí của Redis trong luồng quyết định bên nào: nếu nó là thứ duy nhất đứng giữa tài khoản và hoá đơn thì chặn khi hỏng.

## 7. Kiểm thử

- Backend: 903 collected; `integration` cần PostgreSQL thật (tự skip, CI chạy thật); `external` tự deselect và tự khoá bằng `TOEIC_ALLOW_EXTERNAL_TTS=1`. Test mặc định SQLite in-memory qua `StaticPool`.
- Frontend: `pnpm lint` là eslint **thuần** — `tsc --noEmit` phải chạy riêng; đổi shape response trên endpoint danh sách thì grep `API_ROUTES` và sửa từng caller.
- E2E: 8 spec chạy **chống docker stack đang sống**, mỗi spec tự đăng ký tài khoản mới (email UNIQUE), và mỗi spec đã được chứng minh đỏ bằng cách tái tạo đúng con bọ nó canh.

## 8. Luật xuyên suốt — bảng tra nhanh

| Luật | Ghi ở đâu |
|---|---|
| Mọi tầng cây nội dung tự lọc `published` (câu, set, story, section, topic) | `learning.py`, `attempt.py`, `tests/test_dictation_tree.py` |
| `require_role` là dependency, không phải kiểm trong thân | mọi router admin |
| Thống kê **suy ra**, không lưu bảng tổng | `profile_stats.py`, `badges.py`, `daily_tasks.py`, `ai_stats.py` |
| Ghi thưởng chỉ qua sổ cái, cap chạm lúc **ghi** | `progression.py`, `ruby.py` |
| Parse không bao giờ ghi; commit là bước riêng | `content_import.py`, ADR-005 |
| API không import được `app.content`; media không chạy qua API lúc phục vụ | `test_content_isolation.py`, ADR-006 §2.9 |
| Đáp án không rời máy chủ khi đang thi | `attempt.py` |
| Chấm đọc chép hai nơi phải bước từng bước giống nhau | `lib/dictation.ts` ↔ `app/services/dictation.py` |
| Tên audio theo **nội dung**, staleness là so fingerprint, không so timestamp | `core/media.py`, `media_state.py` |
| Số cấu hình là **hàng**, seed lười; bảng trống = chưa cấu hình | `progression_config.py`, `pet_species.py` |
| Mọi danh sách phân trang kết thúc bằng `id` làm tiebreaker | `schemas/common.py`, `test_attempts.py` |
| `prompt_text`/`option.content` "in nothing" là `None`, không phải `""` | `validators.py`, `test_content_import.py` |
