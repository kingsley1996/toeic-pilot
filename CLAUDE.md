# CLAUDE.md

TOEIC Pilot — nền tảng học TOEIC có AI. Monorepo đa ngôn ngữ: FastAPI (`apps/api`),
Next.js (`apps/web`), hợp đồng TS dùng chung (`packages/shared`), Postgres + pgvector, Redis.

<!-- Giữ tệp này DƯỚI 200 dòng. Nó nạp vào MỌI phiên và ăn context thật; luật chỉ
     đúng cho một vùng mã thì thuộc về `.claude/rules/` với `paths:` frontmatter,
     vì chỉ path-scoped rule mới thật sự giảm context — `@import` thì không. -->

## Luật nằm ở đâu

Tệp này chỉ giữ thứ đúng ở **mọi** phiên. Luật theo vùng mã nằm ở `.claude/rules/`
và tự nạp khi đọc tệp khớp `paths:`:

| Rule | Nạp khi đụng vào |
|---|---|
| `api-backend.md` | `apps/api/app/**/*.py` — cấu hình, auth, database, luật miền, phân trang |
| `frontend.md` | `apps/web/**` — design system, ba trạng thái session, shell, bẫy `tsc` |
| `learning-domain.md` | services + route học — bất biến từ vựng và dictation |
| `content-pipeline.md` | `apps/api/app/content/**` — audio, ảnh, nhãn, sinh đề, và lệnh của chúng |
| `testing.md` | `apps/api/tests/**`, `apps/web/e2e/**` |
| `docker.md` | `docker/**`, `Dockerfile*`, `.dockerignore` |

## Tài liệu

**`planning/docs/ROADMAP.md` là tracker duy nhất** — sprint, việc, trạng thái thật, chi phí.
Đọc trước; cập nhật khi xong việc. Không tệp nào khác trong `planning/` mang trạng thái.

**`planning/docs/PLAN.md` là spec sản phẩm** và là nguồn sự thật về phạm vi. Làm theo pha;
không làm tính năng của pha sau khi pha trước còn mở, trừ khi được bảo.

`planning/` chia ba: **`docs/`** hành vi hiện tại, spec và runbook · **`adr/`** quyết định ·
**`archive/`** kế hoạch của việc đã xong, ghim theo commit và **không cập nhật**.

Đường dẫn dưới đây tính từ `planning/`:

| Tệp | Về cái gì |
|---|---|
| `adr/ADR-001-DATA-MODEL.md` | Schema miền và vì sao nó có hình dạng đó |
| `docs/PHASE2-AUDIO.md` (ADR-002) | Kiến trúc audio. §A4 có bốn bất biến, cả bốn hỏng im lặng |
| `adr/ADR-003-AI-LAYER.md` | Hai nhà cung cấp, embedding offline, RAG bị chặn bởi **nội dung** chứ không phải kỹ thuật. §3.4: ngân sách token **fail closed** |
| `adr/ADR-004-IMAGES.md` · `adr/ADR-006-MEDIA-UPLOAD.md` | Ảnh Part 1, giấy phép · ticket → POST → confirm, provider là **config** |
| `adr/ADR-005-CONTENT-TOOLING.md` · `adr/ADR-007-TEST-AUTHORING.md` | Admin nhập đề · lời thoại nằm trên câu, không nằm cạnh tệp spec |
| `adr/ADR-008-AUTH-PROVIDERS.md` | Google/Apple qua **code flow phía máy chủ**, không SDK. Thêm script bên thứ ba là hết hiệu lực lý do hoãn P1-7b |
| `adr/` — ADR-010, 011, 012, 013 | Petland, ruby, chạm mặt, chỉ số thú cưng |
| `adr/ADR-015-TURNSTILE.md` | Ô kiểm chống bot. §0: nửa còn lại của Cloudflare cần **tên miền**. §3 hỏng thì mở, chối thì đóng. §6 nó tiêu món nợ P1-7b |
| `adr/ADR-014-DEPLOY-FREE.md` | Production trên free tier. §0 đọc trước; ba thứ hỏng im lặng ở §7 |
| `docs/AI-ENGINEERING-PLAN.md` | §3: giải thích một câu **giống nhau với mọi người học** nên tính sẵn offline. §2: chấm điểm, SM-2, quy đổi điểm **không bao giờ** chạm LLM |
| `docs/PROMPT-SYSTEM.md` | Kiểm kê prompt. §0: hai sổ đăng ký, và ranh giới giữa chúng là ranh giới kiến trúc |
| `docs/DESIGN-SYSTEM.md` | Ba luật hỏng im lặng: **không `box-shadow`**, **một bán kính 4px**, **`rule-strong`** cho viền |
| `docs/toeic_question_label_taxonomy.md` | Bảng nhãn, **duy trì bằng tay** và là nguồn sự thật; `labels.py` được *sinh ra* từ nó |
| `docs/SYSTEM-OVERVIEW.md` · `docs/MEDIA-PIPELINE.md` · `docs/EXAM-GRAPH.md` | Mô tả **hành vi hiện tại**, không phải quyết định |
| `docs/REFACTOR-LONG-FILES.md` | Tách tệp quá dài. §0: dài không tự nó là lỗi |
| `docs/USER-ROAD.md` · `docs/SPEC-*.md` | Level/badge/XP · các mặc định dựng để sửa |
| `docs/BRAND-ASSETS.md` | Prompt sinh logo/favicon/ảnh OG. §0: favicon vẫn là bản mặc định của Next.js. §2: ba thứ model làm không được |
| `docs/import_media.md` · `docs/EXAM-GENERATION-RUNBOOK.md` · `docs/SYNC-TEST-TO-PRODUCTION.md` | Runbook thao tác |
| `docs/REVIEW-OPUS.md` · `docs/qwen3p8-review.md` | Hai bản review, ghim theo commit, **không cập nhật** |
| `archive/**` | Kế hoạch của việc đã làm xong, và ROADMAP cũ. Ghim theo commit, **không cập nhật** — đọc để biết *vì sao*, không phải để biết *đang thế nào* |

## Lệnh

### API (`apps/api`) — luôn `uv`, không `pip`, không `python` trần

```bash
cd apps/api
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                       # 949 collected
uv run pytest -m "not integration"  # bỏ những bài cần PostgreSQL
uv run ruff check app tests && uv run ruff format app tests
uv run mypy                         # strict, chỉ soi `app/`
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "..."
```

**Test `integration` mặc định trỏ vào database DEV và chạy `create_all` trên đó** — đó là
lý do `alembic revision --autogenerate` sau đấy sinh ra migration rỗng. Trỏ sang database
nháp:

```bash
docker compose -f ../../docker/docker-compose.yml exec -T postgres \
  psql -U toeic -d postgres -c 'CREATE DATABASE toeic_test;'
TEST_DATABASE_URL="postgresql+psycopg://toeic:toeic@localhost:5432/toeic_test" uv run pytest
```

`test_concurrency.py` và `test_ruby_race.py` **từ chối chạy khi thiếu `TEST_DATABASE_URL`**.
Không có chốt đó, một lần `pytest` trần đã xoá sạch bộ sưu tập thú cưng của dev (2026-08-30).

### Monorepo — pnpm + Turborepo

```bash
pnpm install
pnpm dev                                          # turbo dev
pnpm build                                        # shared build trước web
pnpm --filter @toeic-pilot/web lint               # eslint — KHÔNG typecheck
pnpm --filter @toeic-pilot/web exec tsc --noEmit   # cái này mới typecheck
pnpm format / pnpm format:check                   # prettier; markdown bị bỏ qua cố ý
pnpm gen:api-types                                # sinh lại hợp đồng dùng chung
pnpm --filter @toeic-pilot/web test:e2e           # Playwright — cần docker stack đang chạy
```

**Hợp đồng dùng chung được SINH RA, không viết tay.** Sửa schema Pydantic rồi
`pnpm gen:api-types`, commit cả `api-types.ts` lẫn `openapi.json`. Job `contract` của CI
sinh lại và fail nếu khác. `apps/web` import **`dist/`** đã build, nên một `dist` cũ vẫn
thoả mãn import và che mất sai lệch.

### Toàn stack

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
docker compose -f docker/docker-compose.yml up postgres redis -d   # chỉ hạ tầng
```

**Thêm một dependency JS thì phải `up -d --build`, không phải `up -d`.** Compose bind-mount
`apps/web` từ host nhưng **không** mount gốc repo, nên `/app/pnpm-lock.yaml` là của image
còn `apps/web/package.json` là của host — entrypoint so hai tệp từ hai nguồn và từ chối
khởi động cho tới khi image được build lại. Lời từ chối ấy nổ **muộn**: container đang
chạy không kiểm lại, nên nó chỉ hiện ra ở lần `restart` kế tiếp.

**Đừng chạy `pnpm dev` hay `pnpm build` trên host khi container `web` đang chạy.** Cả hai
ghi cùng `apps/web/.next`. `build` là cái tệ hơn, và dừng container trước **không cứu
được**: hiện vật production nó để lại làm dev server đọc phải cache lẫn lộn, in
`✓ Ready` như thường, rồi treo ở mọi request **mà không log một dòng lỗi nào**. Sửa bằng
`rm -rf apps/web/.next` rồi khởi động lại container.

**`docker compose restart` không đọc lại `.env`.** `env_file` chỉ áp lúc *tạo* container.
Dùng `up -d` để tạo lại.

## Quy ước comment

**Comment ngắn.** Một hai câu là cỡ bình thường. Chỉ comment ở chỗ mã không tự nói được:
một bất biến hỏng im lặng, một thứ tự không hiển nhiên, một quyết định mà lựa chọn hiển
nhiên là sai. Đừng nhắc lại điều mã đã nói, đừng kể lịch sử những lần thử.

Repo này coi trọng *vì sao* hơn *cái gì* — nhiều lỗi ở đây hỏng im lặng. Nhưng đó là lý
do để đặt lý do ở **vài chỗ**, không phải mọi chỗ. Comment dài quá vài dòng là dấu hiệu:
hoặc mã nên rõ hơn, hoặc lời giải thích thuộc về `planning/`.

## CI (`.github/workflows/ci.yml`)

Bốn job, tất cả bắt buộc:

| Job | Kiểm |
|---|---|
| `api` | ruff lint + format, mypy strict, `alembic upgrade head`, pytest (có Postgres + Redis) |
| `web` | prettier, build shared, eslint, build web |
| `contract` | sinh lại API types, fail nếu bản đã commit khác |
| `docker` | build cả hai image **và boot image API** — một image hỏng từng build sạch rồi chết lúc chạy |

Branch protection **chưa bật**; CI xanh mà không ai bắt buộc thì chỉ là gợi ý.

## Bẫy chung

- **`.dockerignore` là chịu lực.** Thiếu nó, `COPY apps/api ./` ghi đè virtualenv Linux của
  image bằng virtualenv macOS của host và container không khởi động nổi. Không bao giờ bỏ
  `**/.venv`, `**/node_modules`, `**/dist` khỏi nó.
- **Container `api` của dev dựng lại schema ở mỗi lần reload** (`--reload` +
  `environment=development` ⇒ `create_all`). `docker compose stop api` trước khi làm việc
  với migration. Nặng nhất khi một migration thêm **cả** bảng lẫn cột: `create_all` tạo bảng
  mới nhưng không thêm được cột, rồi `alembic upgrade` chết vì `relation already exists`.
- **Thư mục rỗng sống sót qua `git revert`.** Next.js chỉ route thư mục có `page.tsx`, nên
  tàn dư như thế trơ và do đó vô hình cho tới khi có người nhìn.
- **`alembic/` không bị lint hay typecheck.** CI chạy `ruff check app tests` và mypy chỉ trên
  `app`, nên migration theo style của `001` chứ không theo style ruff đòi ở nơi khác.
- **id giọng của edge-tts trôi.** Chúng là id của nhà cung cấp và Microsoft rút không báo.
  Chạy `TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external` trước mỗi đợt sinh lớn.
- **Mọi lượt ghi trên Postgres dev đều được log** (`log_statement=mod`). Đừng cho rằng một
  lệnh `psql` trực tiếp là vô hình.
