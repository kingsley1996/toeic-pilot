# Triển khai — bản đồ cho agent

Điểm nạp (on-ramp) cho mọi thứ liên quan chạy stack ở đâu và bằng ảnh nào. Tài liệu
này **không quyết định gì mới** — nó gom đường đi của một thay đổi từ `docker/**` đến
production, rồi trỏ tới nơi có thẩm quyền cho từng chi tiết:

| Nơi | Cái gì |
|---|---|
| `docker/docker-compose.yml` | Stack dev — chú thích trong file là giải thích có thẩm quyền cho từng dòng |
| `.claude/rules/docker.md` | Luật vùng mã `docker/**`, `Dockerfile*`, `.dockerignore` (tự nạp) |
| `CLAUDE.md` §Toàn stack + §Bẫy chung | Bẫy dev vận hành hằng ngày |
| `adr/ADR-014-DEPLOY-FREE.md` | **Vì sao** mỗi thành phần production nằm ở nhà cung cấp đó; đo hạn mức ngày 2026-08-28, có hạn sử dụng |
| `.github/workflows/ci.yml`, job `docker` | Dựng ảnh, khởi động thử, đẩy GHCR, gọi deploy hook |
| `docs/SYNC-TEST-TO-PRODUCTION.md` | Runbook đem **dữ liệu** lên production — chọn script ở đây, đừng đoán |

Trạng thái: production **đã chạy** (Render + Vercel + Supabase + Upstash; các lần sync
nội dung ghi ngày trong ROADMAP từ 2026-09). ADR-014 dòng "chưa dựng" là trạng thái của
bản khảo sát 2026-08-28, không phải của hôm nay.

---

## 1. Tổ chức code quanh docker

```
docker/
  docker-compose.yml   7 service, context = GỐC repo
  api.Dockerfile       MỘT ảnh, hai vai: production + dev (dev ghi đè CMD)
  worker.Dockerfile    CHỈ dev — tts / skilltag / eval worker, không lên prod
  web.Dockerfile       CHỈ dev — NODE_ENV=development, CMD pnpm dev
  api-entrypoint.sh    alembic upgrade head + sync_kb TRƯỚC khi uvicorn nghe cổng
  web-entrypoint.sh    pnpm install --frozen-lockfile + build shared TRƯỚC khi dev lên
```

Bốn luật định hình everything else:

- **Context build là gốc repo** (`context: ..` trong compose). Vì thế `.dockerignore`
  *là chịu lực*: thiếu `**/.venv`, `**/node_modules`, `**/dist`, một `COPY apps/api ./`
  sẽ đắp virtualenv macOS của host lên venv Linux của ảnh. `apps/api/media/` bị loại
  có chủ ý — ảnh prod không mang media, worker nhận nó qua bind mount lúc chạy.
- **Ảnh APIprod ≠ ảnh worker, và đó là ranh giới kiến trúc có hình dạng vật lý.**
  `worker.Dockerfile` có ffmpeg + extra `content`; `api.Dockerfile` dựng `--no-dev`
  không có cả hai, và `tests/test_content_isolation.py` bắt mọi vi phạm import
  `app.content` từ `app/main.py` dưới một giây. Gộp ảnh không hỏng hôm gộp — nó hỏng
  vào ngày ai đó "import cho tiện vì nó đã ở ngay đó".
- **Entrypoint = "không phục vụ khi state chưa reconciliation".** API chạy Alembic
  (và `sync_kb`) trước khi bind port; web chạy `pnpm install --frozen-lockfile` và
  build `packages/shared` trước khi `pnpm dev`. Alembic **chỉ** chạy ở `api-entrypoint.sh`
  — worker không migrate, không mở cổng, CI không migrate ở chỗ khác.
  Ngoại lệ có chủ đích: `RUN_MIGRATIONS=0` cho smoke test của job `docker`.
- **Một Dockerfile, hai nhân cách.** `api.Dockerfile` là ảnh production *và* ảnh dev;
  service `api` trong compose ghi đè `command:` bằng `uv run uvicorn --reload`. Đó là
  lý do `uv` cố ý ở lại tầng runtime và worker ảnh chạy root (ghi vào bind mount của
  host) còn ảnh API chạy uid 10001.

## 2. Dev — `docker compose up --build`

7 service: `postgres` (pgvector pg17, `log_statement=mod` — **mọi lệnh ghi trên DB dev
đều để lại vết trong `docker logs`**), `redis`, `api`, `worker` (tts), `skilltag-worker`,
`eval-worker`, `web`.

Ba điều chỉ đúng khi đọc từ trong container ra:

1. **`environment:` ĐÈ LÊN `env_file:`.** `DATABASE_URL`, `REDIS_URL`, `OLLAMA_BASE_URL`
   đặt trong compose trỏ vào network của Compose và ghi đè `.env` một cách im lặng.
   Muốn lật sang DB từ xa phải sửa ở **cả ba** service. Ngược lại, biến nào phải đọc từ
   `.env` (`AUDIO_PUBLIC_BASE_URL`,…) thì **tuyệt đối không** đặt vào `environment:`,
   kể cả dạng `${VAR:-default}`.
2. **`localhost` trong container là chính container đó.** Ollama trên host phải gọi qua
   `host.docker.internal:11434` — triệu chứng của quên nó là một câu 503 lịch sự không
   nhắc gì tới Docker.
3. **Nửa sau của stack dev là bind mount, không phải ảnh.** `apps/api/app`, `alembic/`,
   `llm_providers.json`, `media/`, `content/` — sửa file là có hiệu lực, không rebuild.
   Nhưng **không bao giờ mount `../apps/api`** mà chỉ `../apps/api/app`: mount cả thư
   mục sẽ đắp `.venv` macOS lên `.venv` Linux, và `uv run` trong container dựng lại
   venv Linux **đè lên máy host**.

Vòng lặp hay vấp, ghi ngắn (chi tiết trong chú thích compose và CLAUDE.md):

- `docker compose restart` **không** đọc lại `.env` — `env_file` chỉ áp lúc *tạo*
  container. Dùng `up -d`.
- Thêm dependency JS thì phải `up -d --build`: `node_modules` là named volume và Docker
  chỉ seed nó từ ảnh khi volume **rỗng**; ảnh mới + volume cũ = "Module not found" cho
  package rõ ràng có trong package.json.
- `api` dev reload chạy `create_all` ⇒ schema dev trôi dần so với Alembic. `stop api`
  trước khi làm việc với migration.
- Chạy e2e: `pnpm --filter @toeic-pilot/web test:e2e` cần stack đang bật; `pnpm build`
  trên host khi container `web` đang chạy sẽ trộn `.next` (treo mọi request, không log
  gì).

## 3. Prod — hai nửa không đối xứng, và đó là bắt buộc

| Thành phần | Chạy ở | Cách lên prod |
|---|---|---|
| API (ảnh `api.Dockerfile`) | **Render** web service, *Existing Image* | CI build → boot thử → push **GHCR** (`:main` + `:<sha>`) → gọi **deploy hook** |
| Web (Next.js) | **Vercel** — không Docker, không có ngoại lệ | Vercel dựng thẳng từ nguồn, **tự deploy mỗi push** `apps/web`/packages nó phụ thuộc |
| Postgres + pgvector | Supabase | schema do `alembic upgrade head` ở entrypoint dựng; dữ liệu nạp theo §4 |
| Audio | Supabase Storage (driver `s3`) | `push_media` từ máy dev — prod không chạy worker |
| Ảnh | Cloudinary | cùng luồng ticket→confirm, provider là config |
| Redis | Upstash (`rediss://`) | — |
| `worker`, `skilltag-worker`, `eval-worker`, `web.Dockerfile` | **không tồn tại ở prod** | công cụ của máy soạn nội dung (ADR-014 §9) |

Hai điều khiến agent hay dựng sai:

- **Render kiểu ảnh KHÔNG tự deploy khi tag `main` đổi.** Đường duy nhất là
  `RENDER_DEPLOY_HOOK` (secret của repo, bước cuối job `docker`). Hook hỏng im lặng:
  prod chạy bản cũ, CI vẫn xanh. Vercel thì ngược lại — đi dựng một hook cho nó là
  thừa. (Hai nửa ngược chiều nhau; dễ nhớ nhầm cả hai hướng.)
- **Thứ chạy ở prod phải là thứ CI đã khởi động thử.** Đừng trỏ Render vào
  `docker/api.Dockerfile` để "Render tự build cho gọn" — P0-2 từng là một ảnh build
  sạch mà boot thì chết, và job `docker` sinh ra vì chuyện đó.

`/ready` (không phải `/health`) là endpoint sống còn: nó `SELECT 1` lên Postgres và
`ping` Redis, nên một pinger 5 phút/lần đánh thức cả Render (ngủ sau 15 phút), Supabase
(ngủ sau 7 ngày) và Upstash. Ngân sách Render free gần như không dư (ADR-014 §3.3) —
đừng thêm service free thứ hai "chỉ để thử".

Biến môi trường prod: điền theo ADR-014 §6, không đổi mã. Hai chốt: Khoá **ghi** S3 chỉ
thuộc về máy dev (`push_media`), không vào Render; region Supabase phải khớp region
Render (quyết định thực tế: Render Singapore — Supabase Tokyo, cái giá ~70 ms/truy vấn
đã được cân rồi chấp nhận).

## 4. Đưa dữ liệu lên production

Schema **không** bao giờ đi bằng dump — prod có schema do Alembic dựng (schema dev có
`create_all` làm trôi, mang lên là mang theo drift). Dữ liệu đi bằng script, và chọn
script là chọn sai một cái là mất dữ liệu người dùng thật:

| Việc | Dùng | Không dùng |
|---|---|---|
| Dựng lại prod từ đầu | `export-content.sh` → `import-content.sql` → `content.sql` | — |
| Một đề mới | `scripts/export-test.sh` | `export-content.sh` (đụng PK, dừng nửa chừng) |
| Từ vựng/dictation (thêm + sửa tại chỗ) | `dump_learning_content.py` (mọi hàng `ON CONFLICT DO UPDATE`) | export-test (một đề chỉ nạp một lần) |
| Sửa `explanation` của đề đã publish | `scripts/export-explanations.sh` (chỉ `UPDATE`) | export-test — **khối reset của nó `DELETE FROM attempt`: xoá lịch sử làm bài của học viên** |
| Đề placement | `scripts/export-placement.sh` | export-test — **phá `tp-test-09`**: đề placement mượn câu của đề khác |
| Thú cưng mới | thứ tự API → web → `export-pet-species.sh` | — (nạp hàng trước web deploy = con thú là ô trống, không lỗi nào) |

Luật chung của mọi đường sync: `push_media` **trước** (hàng trỏ khoá chưa đẩy → 404 mà
DB trông hoàn hảo), `ON_ERROR_STOP=1`, idempotent, và **diễn tập trên scratch DB trước**
— đây là ghi vào production. Chi tiết từng bug đã gặp: `SYNC-TEST-TO-PRODUCTION.md` §4.

## 5. Sửa gì thì phải đối chiếu chỗ nào

| Thay đổi | Kèm theo |
|---|---|
| `pyproject.toml` / `uv.lock` | rebuild ảnh API (`up --build` ở dev; CI build lại ảnh prod). Ảnh dựng `--frozen` — lockfile lệch là build đỏ, không phải tự đoán |
| migration mới | prod nhận nó qua `alembic upgrade head` trong entrypoint **khi ảnh deploy**; nếu dữ liệu phụ cột mới (seed, hàng `pet_species`) thì thứ tự API → dữ liệu là bắt buộc |
| `package.json` (web) | `pnpm install` trên host cho ra lockfile mới + commit, rồi `up -d --build`; Vercel tự dựng lại |
| `content/kb/*.md` | `sync_kb` chạy ở entrypoint API (bảng PG của prod); vector trên Pinecone do bước `embed_kb` của CI lo khi push `main` |
| env mới | `.env.example` + ô cấu hình Render/Vercel (chúng không có git repo cho env — dashboard là chỗ duy nhất); biến container-network **không** đặt vào `environment:` nếu `.env` còn phục vụ nó |

## 6. Bảng hỏng im lặng (chỉ docker/deploy)

| Cái hỏng | Triệu chứng | neo |
|---|---|---|
| `environment:` đè `env_file:` | sửa `.env`, restart, không gì đổi | compose §api |
| Mount `../apps/api` (cả thư mục) | host `uv run` chết với "broken symbolic link", không nhắc Docker | rules/docker.md |
| Named volume `node_modules` cũ | `Module not found` cho package có trong lockfile | web-entrypoint.sh |
| Render không có deploy hook / hook bị từ chối | prod chạy bản cũ, CI xanh, không ai báo | ci.yml job docker |
| Quên `host.docker.internal` | Coach 503 "lịch sự" | compose §api |
| `api-entrypoint` thiếu (dựng prod bằng ảnh khác) | serve trên schema chưa migrate | api-entrypoint.sh |
| `.dockerignore` thiếu `apps/api/media/` | lỗi quyền uid 10001 chỉ nổ ở checkout sạch = CI | api.Dockerfile |
| Supabase ngủ / region lệch | chỉ audio 404; hoặc mọi trang chậm ~15 vòng × 100 ms | ADR-014 §3.2 §3.4 |

## 7. Không làm

Trích nguyên văn tinh thần ADR-014 §9, áp cho agent:

- Không chạy worker nào trên production; không phục vụ media qua FastAPI ở prod.
- Không transaction pooler (cổng 6543) — prepared statement của psycopg sẽ đổ ở lần
  gọi thứ sáu, tức là sau khi deploy "thành công".
- Không cho Render tự build ảnh; không đưa web vào Docker "cho đồng bộ".
- Không tự động hoá dựng hạ tầng (script một lần là nợ bảo trì cho 0 lần chạy lại).
- Không commit `$SUPABASE_URL`, dump dữ liệu, hay `.env` — và nếu connection string
  từng lộ trong chat/lỗi, rotate password trên Supabase sau khi xong việc.
