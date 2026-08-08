# TOEIC Pilot — Review tổng thể

**Ngày:** 2026-08-08
**Phạm vi:** toàn bộ repo (`apps/api`, `apps/web`, `packages/shared`, `docker/`, `.github/`) + `planning/ARCHITECTURE.md` + `planning/PLAN.md`
**Người review:** Claude (Opus 5)

---

## 0. Cách review này được thực hiện

Không chỉ đọc code — các kết luận dưới đây đều được **kiểm chứng bằng cách chạy thật**:

| Lệnh | Kết quả thực tế |
|---|---|
| `cd apps/api && uv run pytest -q` | ✅ `1 passed, 2 warnings` |
| `cd apps/api && uv run ruff check app tests` | ✅ `All checks passed!` |
| `pnpm build` (turbo: shared + web) | ✅ `2 successful` — Next.js build + typecheck sạch |
| `pnpm --filter @toeic-pilot/web lint` | ❌ **CRASH** — `TypeError: Converting circular structure to JSON` |

Việc `lint` crash nghĩa là **job `web` trong CI đang đỏ** ở mọi PR. Đây là phát hiện P0 số 1.

---

## 1. Tóm tắt điều hành

Đây là một **scaffold Phase 1 chất lượng khá tốt** so với mặt bằng chung: monorepo được nối dây đúng, Docker Compose chạy được, CI có sẵn, auth hoạt động, shared types tách package riêng, Alembic có migration đầu tiên, ruff sạch, `.env` không bị commit. Nền móng đủ tốt để xây tiếp.

Nhưng có một khoảng cách rất lớn giữa **hạ tầng đã có** và **sản phẩm cần xây**. Cụ thể:

> Toàn bộ `PLAN.md` (Learning Hub, TOEIC Practice, AI Study Planner, AI Coach) **chưa có một dòng thiết kế dữ liệu nào**. Không có ERD, không có schema câu hỏi/đề thi/lượt làm bài/từ vựng/tiến độ. Không có kế hoạch cho **audio** — mà Dictation và Listening Part 1–4 thì không thể tồn tại nếu không có audio storage/CDN. Đây là rủi ro kiến trúc lớn nhất của dự án, lớn hơn tất cả các bug code cộng lại.

Bảng điểm:

| Hạng mục | Điểm | Ghi chú |
|---|---|---|
| Cấu trúc monorepo & tooling | 8/10 | pnpm + turbo + uv tách bạch sạch sẽ |
| Backend code quality | 7/10 | Idiomatic SQLAlchemy 2.0, nhưng thiếu error handling ở vài chỗ |
| Frontend code quality | 7/10 | Gọn, dùng shared types đúng cách; bảo vệ route còn yếu |
| Bảo mật | 4/10 | Token localStorage, không rate limit, SECRET_KEY không validate |
| Test coverage | 2/10 | Đúng **1** test (`/health`). Business logic 0% |
| DevOps / Docker | 4/10 | Thiếu `.dockerignore` → image hỏng; không có prod target |
| CI | 5/10 | Có, nhưng đang đỏ và thiếu nhiều gate |
| Tài liệu (`PLAN.md`/`ARCHITECTURE.md`) | 6/10 | Viết tốt nhưng thiếu data model, thiếu acceptance criteria |
| **Sẵn sàng cho Phase 2** | **Chưa** | Cần Sprint 0 sửa P0 + thiết kế data model trước |

---

## 2. Điểm mạnh (giữ nguyên, đừng đụng vào)

1. **Tách `packages/shared` là quyết định đúng.** Frontend không hardcode API path — `apps/web/src/app/login/page.tsx:27` dùng `API_ROUTES.login`. Đây là thứ nhiều dự án bỏ qua rồi trả giá.
2. **`uv` được áp dụng nhất quán** — `.cursor/rules/python-uv.mdc` có rule rõ, Dockerfile và CI đều dùng `uv sync`/`uv run`. Không lẫn `pip`.
3. **SQLAlchemy 2.0 style đúng chuẩn** — `apps/api/app/models/user.py` dùng `Mapped[...]` + `mapped_column`, `DeclarativeBase`. Không dùng legacy `declarative_base()`.
4. **Config tập trung** — `apps/api/app/core/config.py` dùng `pydantic-settings`, không có `os.environ` rải rác.
5. **Redis là soft dependency** — `apps/api/app/main.py:18-21` bắt `ConnectionError` và chỉ log warning. App không chết vì Redis. Đúng.
6. **Test dùng SQLite in-memory** — `apps/api/tests/conftest.py` cho phép chạy `pytest` local không cần Postgres. DX tốt.
7. **`.env` được gitignore** (đã kiểm chứng: `git ls-files --error-unmatch .env` → không tracked). `.env.example` có sẵn.
8. **Turbo `dependsOn: ["^build"]`** đảm bảo `shared` build trước `web`. Đúng thứ tự.

---

## 3. Vấn đề P0 — chặn, phải sửa ngay

### P0-1. CI đang đỏ: ESLint crash trên `apps/web`

**File:** `apps/web/eslint.config.mjs`

```
TypeError: Converting circular structure to JSON
  --> property 'configs' -> 'flat' -> ... -> 'plugins' -> 'react' closes the circle
  at ConfigValidator.formatErrors (@eslint/eslintrc/lib/shared/config-validator.js:299)
```

**Nguyên nhân:** file dùng `FlatCompat.extends("next/core-web-vitals", "next/typescript")` — cơ chế cầu nối cho eslintrc cũ. Nhưng `eslint-config-next@16.3.0` **đã export flat config native** (đã kiểm chứng qua `package.json` exports: `"./core-web-vitals"`, `"./typescript"`). Đưa một flat-config-native plugin qua `FlatCompat` tạo cấu trúc vòng → `JSON.stringify` nổ.

**Hệ quả:** step `Lint web` trong `.github/workflows/ci.yml` fail → **mọi PR đều đỏ**. Nếu team đang merge, nghĩa là branch protection chưa bật hoặc mọi người đang bỏ qua CI đỏ — cả hai đều là vấn đề quy trình.

**Sửa:**

```js
// apps/web/eslint.config.mjs
import coreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default [
  ...coreWebVitals,
  ...nextTypescript,
];
```

Xóa hoàn toàn `FlatCompat`, `dirname`, `fileURLToPath` và devDependency `@eslint/eslintrc`.

---

### P0-2. Không có `.dockerignore` → image API bị hỏng và phình 118MB

**File:** `docker/api.Dockerfile:16` + không tồn tại `.dockerignore`

```dockerfile
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev      # ← tạo /app/apps/api/.venv (Linux)
COPY apps/api ./                   # ← GHI ĐÈ bằng .venv của host (macOS aarch64!)
```

**Đã kiểm chứng:** `apps/api/.venv/pyvenv.cfg` trỏ tới `/Users/samuel/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin`, dung lượng **118MB**. Không có `.dockerignore` nên `COPY apps/api ./` sẽ copy nguyên venv macOS đè lên venv Linux vừa build.

Tương tự `docker/web.Dockerfile:15` dùng `COPY . .` — copy cả `node_modules/`, `.git/`, `.next/`, và **`.env` (chứa secret)** vào image.

**Sửa — tạo `.dockerignore` ở root:**

```
**/node_modules
**/.venv
**/.next
**/.turbo
**/__pycache__
**/.pytest_cache
**/.ruff_cache
.git
.env
.env.*
*.log
dist
```

---

### P0-3. `.env` KHÔNG được nạp ở luồng dev local mà README hướng dẫn

**File:** `apps/api/app/core/config.py:5`

```python
model_config = SettingsConfigDict(env_file=".env", ...)
```

`env_file=".env"` là **đường dẫn tương đối theo CWD**. README.md:59 hướng dẫn:

```bash
cd apps/api && uv run uvicorn app.main:app --reload --port 8000
```

→ CWD là `apps/api`, nhưng **không có `apps/api/.env`** (đã kiểm chứng). File `.env` nằm ở root repo. Kết quả: app chạy với **toàn bộ giá trị mặc định**, bao gồm:

```python
secret_key: str = "dev-secret-change-in-production"   # config.py:11
```

Trong Docker thì `env_file: ../.env` của compose truyền biến qua environment nên vẫn đúng — vấn đề chỉ xảy ra ở luồng local. Nhưng đây là loại bug im lặng nguy hiểm: **dev tưởng đang dùng .env của mình, thực ra thì không.**

**Sửa:**

```python
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # → repo root

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT / ".env", Path(".env")),  # root trước, local override sau
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

---

### P0-4. `SECRET_KEY` mặc định có thể lọt lên production

Không có bất kỳ validation nào chặn việc chạy production với `secret_key = "dev-secret-change-in-production"`. JWT ký bằng secret ai cũng đoán được = **bất kỳ ai cũng forge được token của bất kỳ user nào**.

**Sửa — thêm vào `config.py`:**

```python
from pydantic import model_validator

class Settings(BaseSettings):
    environment: str = "development"
    secret_key: str = "dev-secret-change-in-production"

    @model_validator(mode="after")
    def _guard_secret(self):
        if self.environment == "production" and "change" in self.secret_key:
            raise ValueError("SECRET_KEY must be set in production")
        return self
```

---

### P0-5. Token `sub` không phải UUID → 500 thay vì 401

**File:** `apps/api/app/api/deps.py:29`

```python
user = db.query(User).filter(User.id == payload["sub"]).first()
```

`payload["sub"]` là string tùy ý từ JWT. Cột `User.id` là `Uuid(as_uuid=True)`. Nếu ai đó gửi token hợp lệ về chữ ký nhưng `sub` là `"admin"` (ví dụ token cũ, hoặc secret bị lộ ở môi trường khác), Postgres sẽ ném `DataError: invalid input syntax for type uuid` → **HTTP 500**, không phải 401. Rò rỉ thông tin qua status code và làm bẩn error log.

**Sửa:**

```python
import uuid

try:
    user_id = uuid.UUID(payload["sub"])
except (ValueError, TypeError):
    raise HTTPException(status_code=401, detail="Invalid token subject",
                        headers={"WWW-Authenticate": "Bearer"})
user = db.query(User).filter(User.id == user_id).first()
```

---

### P0-6. Race condition khi đăng ký → 500 thay vì 409

**File:** `apps/api/app/api/routes/auth.py:23-29`

Pattern check-then-insert cổ điển:

```python
existing = db.query(User).filter(User.email == body.email.lower()).first()
if existing: raise HTTPException(409, ...)
user = User(...)
db.add(user); db.commit()          # ← 2 request đồng thời → IntegrityError chưa bắt → 500
```

Unique index tồn tại (`ix_users_email`) nên DB chặn đúng, nhưng app không bắt exception.

**Sửa:**

```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(user)
    db.commit()
except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="Email already registered")
db.refresh(user)
```

---

## 4. Vấn đề P1 — quan trọng, sửa trong 1–2 sprint tới

### P1-1. `passlib` sẽ vỡ trên Python 3.13

`pyproject.toml` khai báo `requires-python = ">=3.12"` nhưng dùng `passlib>=1.7.4` + pin `bcrypt<4.1`. Khi chạy test đã thấy cảnh báo thật:

```
DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
  from crypt import crypt as _crypt   (passlib/utils/__init__.py:854)
```

Module `crypt` đã **bị xóa khỏi Python 3.13**. `passlib` 1.7.4 phát hành 2020 và gần như không còn bảo trì. Chỉ cần một dev chạy `uv sync` trên Python 3.13 là app không import được. Cái pin `bcrypt<4.1` cũng chính là dấu hiệu của một workaround tương thích đã cũ.

**Sửa:** bỏ `passlib` + `bcrypt<4.1`, dùng thư viện `bcrypt` trực tiếp (hoặc `pwdlib[argon2]`):

```python
import bcrypt

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

Đồng thời pin `requires-python = ">=3.12,<3.14"` để không bị bất ngờ.

### P1-2. Test coverage ~0% cho business logic

Chỉ có `apps/api/tests/test_health.py`. Không có test nào cho register / login / me / 401 / 409 / password sai.

Có một cái bẫy ẩn khiến việc viết test DB sẽ fail ngay lần đầu: `TestClient(app)` ở module scope **không chạy lifespan** (Starlette chỉ chạy lifespan khi dùng `with TestClient(app) as c:`). Nghĩa là `Base.metadata.create_all` trong `main.py:17` **không được gọi** trong test → bảng `users` không tồn tại → mọi test DB sẽ báo `no such table`.

**Cần thêm fixture chuẩn:**

```python
# tests/conftest.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,          # bắt buộc: giữ 1 connection cho in-memory
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        yield s

@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Danh sách test tối thiểu cho Phase 1: register thành công (201) / trùng email (409) / password < 8 ký tự (422) / login đúng (200 + token) / login sai (401) / `/me` không token (401) / `/me` token rác (401) / `/me` hợp lệ (200).

### P1-3. Không có test frontend, không có Playwright

`PREPARE.md` mô tả rõ vai trò "Integration Tester team-member that builds and runs end-to-end Playwright tests" — nhưng repo không có Playwright, không có vitest/jest, `package.json` root **không có script `test`**, và `turbo.json` không định nghĩa task `test`. Ý định trong tài liệu chưa được hiện thực hóa.

### P1-4. Contract drift vô hình giữa Pydantic và TypeScript

Types trong `packages/shared/src/index.ts` được **viết tay**, song song với `apps/api/app/schemas/auth.py`. Không có gì kiểm tra hai bên khớp nhau.

**Bằng chứng cụ thể đã phát hiện:** trước khi tôi chạy `pnpm build`, file `packages/shared/dist/index.d.ts` chứa các type **không hề tồn tại trong `src/`**:

```ts
export type Topic = { name; description; item_count };
export type VocabularyItem = { word; definition; example };
export type DictationExercise = { id; title; prompt; length };
export type DictationResult = { ...; score: number };
export declare const API_ROUTES: {
    readonly learningTopics: "/api/v1/learning/topics";
    readonly learningVocabulary: (topic: string) => string;
    readonly learningDictation: "/api/v1/learning/dictation";
    // ...
};
```

Đây là artifact còn sót từ một phiên bản Phase 2 đã bị revert. Điểm nguy hiểm: **`apps/web` import từ `dist/`, không phải `src/`** (`packages/shared/package.json` khai `"main": "./dist/index.js"`). Nghĩa là web app có thể type-check thành công dựa trên một `dist` đã lỗi thời — drift hoàn toàn vô hình.

Thêm nữa, `tsc` không dọn `outDir`: sau khi build lại, `dist/types.js` và `dist/types.d.ts` (từ một file `src/types.ts` đã bị xóa) **vẫn còn nguyên** — đã kiểm chứng.

**Khuyến nghị (giá trị cao, chi phí thấp):**
1. Sinh types từ OpenAPI thay vì viết tay:
   ```bash
   uv run python -c "import json,app.main;print(json.dumps(app.main.app.openapi()))" > openapi.json
   pnpm dlx openapi-typescript openapi.json -o packages/shared/src/api-types.ts
   ```
   Thêm một job CI: sinh lại rồi `git diff --exit-code` → PR nào làm lệch contract sẽ fail.
2. Thêm `"prebuild": "rm -rf dist"` vào `packages/shared/package.json`.

### P1-5. `create_all` chạy ở mọi môi trường, migration không tự chạy

`apps/api/app/main.py:17` gọi `Base.metadata.create_all(bind=engine)` trong lifespan — tiện cho dev, nhưng ở production nó sẽ tạo schema lệch với Alembic và che giấu migration thiếu. Đồng thời `docker/docker-compose.yml` không chạy `alembic upgrade head` ở entrypoint.

**Sửa:** gate bằng `settings.environment == "development"`, và thêm entrypoint script chạy `uv run alembic upgrade head` trước khi start uvicorn.

### P1-6. `/ready` là readiness giả

`apps/api/app/api/routes/health.py:12-15` luôn trả `{"status": "ready"}`, kể cả khi Postgres chết. Docstring tự thừa nhận là placeholder. Compose cũng không có healthcheck cho service `api`/`web`.

Với load balancer / k8s, endpoint này sẽ nói dối → traffic được route vào instance chưa sẵn sàng.

**Sửa:**

```python
@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1")); checks["db"] = "ok"
    except Exception: checks["db"] = "fail"
    try:
        get_redis().ping(); checks["redis"] = "ok"
    except Exception: checks["redis"] = "degraded"   # soft dependency
    if checks["db"] != "ok":
        raise HTTPException(503, detail=checks)
    return {"status": "ready", **checks}
```

### P1-7. Token trong `localStorage`, không có refresh, không có logout server-side

`apps/web/src/lib/auth-storage.ts` lưu JWT vào `localStorage` → bất kỳ lỗ XSS nào cũng lấy được token. TTL là **7 ngày** (`config.py:12`: `60*24*7`) và không có cách nào thu hồi. Không có refresh token.

**Khuyến nghị cho Phase 2:** chuyển sang httpOnly + Secure + SameSite cookie, access token ngắn hạn (15–30 phút) + refresh token, và denylist `jti` trong Redis khi logout — Redis đã có sẵn trong stack, chỉ chưa dùng vào việc gì.

### P1-8. Không có rate limiting

`POST /api/v1/auth/login` hoàn toàn không giới hạn → brute-force thoải mái. Chưa quan trọng ở Phase 1, nhưng **bắt buộc trước Phase 4**: khi có LLM, một endpoint không giới hạn là một hóa đơn không giới hạn. Dùng `slowapi` hoặc middleware tự viết trên Redis.

### P1-9. Không có observability

Không có structured logging, không request-id, không metrics, không tracing, không error tracking. `PLAN.md` xếp Observability vào Phase 6 — **quá muộn**. Chi tiết ở mục 6.

### P1-10. Không có type-check cho Python

Ruff chỉ bật `["E", "F", "I", "UP"]` — không có bugbear (`B`), không có security (`S`). Không có mypy/pyright. Không dùng `ruff format` và CI không check format. Prettier có trong `package.json` root nhưng **không có file config** và không chạy trong CI.

---

## 5. Vấn đề P2 — nên sửa, không gấp

| # | Vấn đề | File |
|---|---|---|
| P2-1 | `UserPublic.created_at: str` + hàm map thủ công `_user_public()`. Nên dùng `ConfigDict(from_attributes=True)` + `datetime` | `schemas/auth.py:21`, `routes/auth.py:13` |
| P2-2 | `User` thiếu `updated_at`, `is_active`, `full_name`, `locale`, `target_score`, `role` — sẽ phải migration lại ngay ở Phase 2 | `models/user.py` |
| P2-3 | Chuẩn hóa email chỉ ở tầng code (`.lower()`). Nên dùng `CITEXT` hoặc unique index trên `lower(email)` | `routes/auth.py:23` |
| P2-4 | Dashboard khi 401 chỉ hiện text + link, không redirect. Bảo vệ route hoàn toàn client-side → nháy nội dung trước khi redirect | `app/dashboard/page.tsx:25-28` |
| P2-5 | `globals.css` đặt `font-family: Arial` đè lên biến `--font-geist-sans` mà `layout.tsx` vừa tải → tải font Google xong rồi không dùng | `globals.css:20` |
| P2-6 | `api.Dockerfile` cài `gcc`, `libpq-dev` nhưng dùng `psycopg[binary]` (không cần compile); chạy user `root`; không multi-stage; không có target production | `docker/api.Dockerfile:7-9` |
| P2-7 | `pnpm install --frozen-lockfile \|\| pnpm install` — fallback im lặng phá tính tất định của lockfile | `docker/web.Dockerfile:11` |
| P2-8 | `apiFetch` không có timeout / `AbortSignal` / retry; set `Content-Type` cho cả GET | `apps/web/src/lib/api.ts:29-36` |
| P2-9 | `turbo.json` task `dev` không có `dependsOn` → clone mới chạy `pnpm dev` có race giữa `shared` watch và `web` dev | `turbo.json:11-14` |
| P2-10 | Thiếu `LICENSE` (README ghi "TBD"), `.editorconfig`, `CODEOWNERS`, PR template, Dependabot/Renovate | root |
| P2-11 | Không có i18n dù người dùng mục tiêu là người Việt học TOEIC. Toàn bộ UI đang tiếng Anh | `apps/web` |
| P2-12 | Không có ADR (Architecture Decision Records) — các quyết định lớn sắp tới (chọn LLM provider, vector store, storage audio) cần được ghi lại | `planning/` |

---

## 6. Đánh giá `planning/ARCHITECTURE.md`

### Điểm mạnh
- Mô tả đúng hiện trạng, có "File map" các entry point — rất hữu ích cho người mới.
- Có mục "Gaps & recommended next work" — hiếm thấy, đáng khen.
- Nhận diện đúng vấn đề `create_all` ở production (mục 122).

### Sai / lỗi thời (cần sửa)

**Mục "Test & verification performed" (dòng 68, 129-130) khẳng định sai:**

> "Ran `pytest` inside the running `api` container: `1 passed, 2 warnings`"

Điều này **không thể xảy ra** với cấu hình hiện tại:
- `docker/api.Dockerfile:14` chạy `uv sync --frozen --no-dev` → **không có pytest** trong image.
- `docker/docker-compose.yml` chỉ mount `app/`, `pyproject.toml`, `uv.lock` — **không mount thư mục `tests/`**.

Kết quả `1 passed` là chạy ở host, không phải trong container. Cần sửa hoặc xóa khẳng định này — một tài liệu kiến trúc chứa claim không kiểm chứng được sẽ làm mất niềm tin vào toàn bộ phần còn lại.

### Thiếu (theo thứ tự quan trọng)

1. **ERD / data model** — thiếu sót nghiêm trọng nhất. Xem mục 7.
2. **Storage cho audio** — không nhắc một chữ nào, dù Dictation và Listening bắt buộc phải có.
3. **Non-functional requirements** — không có mục tiêu latency (p95), concurrency, chi phí/user/tháng, SLA.
4. **Environment matrix** — dev / staging / prod khác nhau thế nào? Secret quản lý ở đâu?
5. **Threat model** — dữ liệu học viên là PII; bài làm sẽ được gửi sang LLM provider. Cần chính sách rõ ràng.
6. **Backup & DR** — Postgres backup ở đâu, RPO/RTO bao nhiêu?
7. **Sequence diagram** cho các luồng chính (auth, làm bài, AI coach).
8. **Sơ đồ trực quan** — toàn bộ tài liệu là text, không có một diagram nào.

### Vấn đề quy trình

Cuối file ghi *"Prepared by: automated repository audit (assistant)"* và có ngày cứng `2026-08-07`. Tài liệu kiến trúc nên là **tài liệu sống** — cập nhật kèm PR khi kiến trúc đổi, không phải snapshot của một lần audit. Đề xuất: thêm mục "Change log" và yêu cầu PR nào đổi kiến trúc thì phải sửa file này.

---

## 7. Đánh giá `planning/PLAN.md`

### Điểm mạnh
- Vision rõ ràng, phân biệt tốt với đối thủ ("không chỉ là chatbot LLM").
- 4 module MVP được định nghĩa gọn.
- Mục 4 (AI Capabilities) liệt kê đúng các kỹ thuật AI Engineering thực chất — không phải buzzword.
- Mục 6 quy định "PLAN.md là single source of truth" và "không implement ngoài Epic hiện tại" — kỷ luật tốt.

### Thiếu sót nghiêm trọng

#### 7a. Không có data model — rủi ro số 1 của dự án

Phase 2 và 3 yêu cầu: Dictation, Vocabulary by topic, Practice by Part, Full Mock Test. Không có gì trong đó khả thi nếu chưa thiết kế:

- Câu hỏi (question) — thuộc Part nào (1–7), loại gì, đáp án, giải thích, độ khó
- Đề thi (test) và quan hệ với câu hỏi
- Lượt làm bài (attempt) — user, thời gian, điểm từng part, điểm quy đổi
- Câu trả lời của user (answer) — để phân tích điểm yếu
- Từ vựng (vocabulary) — từ, nghĩa, phiên âm, ví dụ, audio, topic
- Tiến độ học (progress) — cần cho AI Study Planner
- Bài dictation — audio, transcript, độ khó

Nếu code trước, thiết kế sau, sẽ phải refactor toàn bộ ở giữa Phase 3.

**Khuyến nghị:** dành 1 sprint riêng cho việc này, output là một ADR + migration Alembic + ERD, trước khi viết bất kỳ endpoint Phase 2 nào.

#### 7b. Không có kế hoạch audio & nội dung — rủi ro số 2

Đây là lỗ hổng kiến trúc mà cả `PLAN.md` lẫn `ARCHITECTURE.md` đều không nhắc:

- **Dictation cần audio.** Listening Part 1–4 cần audio. Nguồn ở đâu?
- **Stack không có object storage.** Không S3, không R2, không CDN. Postgres không phải chỗ để lưu file mp3.
- **Bản quyền.** Đề TOEIC thật thuộc bản quyền ETS. Kế hoạch là mua license, tự sản xuất, hay dùng nguồn mở? Đây là rủi ro pháp lý, không phải rủi ro kỹ thuật — và nó cần được quyết định **trước** khi build content pipeline.
- **Nếu tự sản xuất bằng TTS** — chọn provider nào, chi phí bao nhiêu, chất lượng giọng có đạt chuẩn TOEIC không?

#### 7c. Không có acceptance criteria cho từng Epic

Mục 7 (Development Phases) chỉ liệt kê tên tính năng. Không có user story, không có definition of done, không có tiêu chí đo được. "Phase 2: Learning Hub — Vocabulary, Dictation" không đủ để biết khi nào Phase 2 xong.

Mục 8 (Success Criteria) cũng chỉ định tính: "AI explains grammar and vocabulary with contextual knowledge" — không đo được.

#### 7d. Không có ngân sách / quota LLM

Chi phí LLM trên mỗi user hiện là **không giới hạn**. Một user có thể chat với AI Coach 500 lần/ngày. Cần thiết kế ngay từ Phase 4:
- Token budget theo user/ngày
- Cache câu trả lời cho câu hỏi lặp lại (Redis đã có sẵn — hiện chưa dùng gì)
- LLM routing theo chi phí (đây chính là ý nghĩa thực tế của mục "LLM Routing" ở mục 4)
- Rate limit theo tier user

#### 7e. Evaluation & Observability để tận Phase 6 — quá muộn

Không thể cải thiện chất lượng AI nếu không đo được. Eval dataset và tracing phải có **ngay khi bắt đầu Phase 4**, không phải sau khi đã ship xong. Nếu để đến Phase 6, mọi thay đổi prompt ở Phase 4–5 đều là đoán mò.

#### 7f. Phase tuần tự đẩy rủi ro lớn nhất về cuối

Thứ tự 1→2→3→4→5→6 nghĩa là AI Layer — phần khó nhất, khác biệt nhất, và rủi ro nhất — được làm sau cùng. Nếu đến Phase 4 mới phát hiện RAG không cho kết quả đủ tốt, hoặc chi phí quá cao, thì đã đi được 60% dự án.

**Khuyến nghị:** chèn một **vertical slice mỏng** ngay sau Phase 2 — một tính năng AI Coach nhỏ, đầu-cuối, có RAG + structured output + eval + tracing, chỉ phục vụ 1 use case (ví dụ: "giải thích một câu ngữ pháp"). Mục tiêu không phải ship, mà là **de-risk**: xác nhận kiến trúc AI hoạt động, đo được chi phí thực, có sẵn eval harness trước khi scale ra 4 module.

#### 7g. Chưa chọn LLM provider

`PLAN.md` mục 5 liệt kê "AI Layer: LLM Router, Prompt Engine, RAG Engine, Tool Registry, Memory Service" nhưng không nói dùng model nào. Đây là quyết định kiến trúc cần chốt sớm vì nó ảnh hưởng đến chi phí, latency, và cách viết prompt.

**Khuyến nghị cụ thể — dùng Claude (Anthropic), và đây chính là cách hiện thực hóa "LLM Routing" một cách thực chất:**

| Tầng | Model ID | Giá (input/output, /1M token) | Dùng cho |
|---|---|---|---|
| Rẻ | `claude-haiku-4-5` | $1 / $5 | Phân loại câu hỏi, gợi ý từ vựng, chấm dictation, tag độ khó, routing intent |
| Cân bằng | `claude-sonnet-5` | $3 / $15 | AI Coach hội thoại thông thường, giải thích từ vựng |
| Mạnh | `claude-opus-5` | $5 / $25 | Sinh study plan cá nhân hóa, phân tích điểm mạnh/yếu, giải thích ngữ pháp phức tạp |

Ba kỹ thuật nên đưa vào thiết kế AI Layer ngay từ đầu:

1. **Structured Output** — mục 4 của PLAN.md đã liệt kê đúng. Cách làm hiện tại là `output_config: {format: {type: "json_schema", schema: ...}}` trên `messages.create()`, hoặc `client.messages.parse()` để tự validate. Rất hợp cho study plan (JSON có schema cố định) và kết quả chấm bài. **Lưu ý:** không dùng kỹ thuật "prefill assistant turn" để ép JSON — cách đó trả về lỗi 400 trên các model hiện tại.

2. **Prompt Caching** — đòn bẩy chi phí lớn nhất cho ứng dụng này. System prompt của AI Coach (persona, quy tắc sư phạm, format) và context RAG là phần **cố định, lặp lại ở mọi request**. Cache read chỉ tốn ~0.1× giá input. Với Opus 5, prefix tối thiểu để cache là 512 token — dễ đạt. Nguyên tắc: đặt nội dung ổn định trước, nội dung thay đổi (câu hỏi của user) sau breakpoint cuối. Tuyệt đối không nhét timestamp / user id vào đầu system prompt — sẽ vô hiệu hóa toàn bộ cache.

3. **Adaptive thinking + effort** — dùng `thinking: {type: "adaptive"}` và `output_config: {effort: ...}` để điều chỉnh độ sâu suy luận theo tác vụ: `low` cho gợi ý từ vựng, `high` cho phân tích tiến độ học.

#### 7h. Các thiếu sót khác

- **Không có kế hoạch RAG corpus.** Nguồn kiến thức ngữ pháp/từ vựng lấy từ đâu? Chunking thế nào? Embedding model nào? Đánh giá retrieval ra sao? (`pgvector` đã bật extension trong migration `001_initial` nhưng chưa dùng.)
- **Không có spaced repetition.** Đây là cốt lõi khoa học của việc học từ vựng (SM-2 / FSRS). Một app học từ vựng không có SRS thì chỉ là flashcard tĩnh. `PLAN.md` không nhắc tới.
- **Không có chính sách PII.** Bài làm của học viên sẽ được gửi sang LLM provider. Cần: thông báo cho user, chính sách retention, tùy chọn opt-out, cân nhắc region.
- **Không có mục "Out of scope".** Có "MVP Scope" nhưng không có "những gì KHÔNG làm" → rất dễ scope creep.
- **PLAN.md đang lẫn spec với nhật ký trạng thái.** Mục 9 ("Current status") và mục 10 ("Code progress") là log vận hành, không phải spec sản phẩm. Chúng sẽ lỗi thời liên tục và làm loãng vai trò "single source of truth" mà chính mục 6 đã tuyên bố. **Đề xuất:** tách ra `planning/STATUS.md`, giữ `PLAN.md` thuần spec.

---

## 8. Lộ trình đề xuất

### Sprint 0 — "Cầm máu" (1–2 ngày)
Chỉ sửa P0. Không thêm tính năng.

- [ ] Sửa `eslint.config.mjs` → CI xanh trở lại
- [ ] Thêm `.dockerignore`
- [ ] Sửa đường dẫn `env_file` trong `config.py`
- [ ] Thêm validator `SECRET_KEY` cho production
- [ ] Parse UUID trong `get_current_user` → 401 thay vì 500
- [ ] Bắt `IntegrityError` trong `register` → 409 thay vì 500
- [ ] Bật branch protection: CI phải xanh mới merge được

### Sprint 1 — "Nền móng chất lượng" (1 tuần)
- [ ] Thay `passlib` bằng `bcrypt` trực tiếp
- [ ] Test fixture DB + đủ 8 test auth
- [ ] Sinh types từ OpenAPI + CI gate chống drift
- [ ] `/ready` kiểm tra thật + healthcheck trong compose
- [ ] Entrypoint chạy `alembic upgrade head`; gate `create_all` theo environment
- [ ] Structured logging + request-id middleware
- [ ] Thêm `ruff format --check`, prettier config, mypy vào CI

### Sprint 2 — "Thiết kế dữ liệu" (1 tuần) ← **quan trọng nhất**
- [ ] ADR-001: Data model cho Learning Hub + TOEIC Practice (ERD đầy đủ)
- [ ] ADR-002: Storage cho audio (S3/R2 + CDN) và nguồn nội dung + bản quyền
- [ ] ADR-003: LLM provider, routing tiers, ngân sách token/user
- [ ] Migration Alembic cho toàn bộ schema domain
- [ ] Cập nhật `packages/shared` + `ARCHITECTURE.md` (thêm ERD)

### Sprint 3+ — Phase 2 + vertical slice AI
- [ ] Learning Hub (Vocabulary + Dictation) theo schema đã chốt
- [ ] Song song: một lát cắt AI mỏng đầu-cuối (RAG + structured output + eval harness + tracing) để de-risk Phase 4
- [ ] Playwright e2e cho luồng auth + 1 luồng học

---

## 9. Definition of Done — đề xuất cho mọi Epic từ nay

Mỗi Epic chỉ được coi là xong khi:

1. Có test tự động (API test + ít nhất 1 e2e cho luồng người dùng chính)
2. Migration Alembic đã viết và chạy được cả `upgrade` lẫn `downgrade`
3. Types trong `packages/shared` khớp với backend (CI gate xác nhận)
4. `ARCHITECTURE.md` được cập nhật nếu có thay đổi kiến trúc
5. CI xanh toàn bộ (lint + format + typecheck + test)
6. Với Epic có AI: có eval case và log chi phí token
7. Có acceptance criteria được viết ra **trước** khi bắt đầu code

---

## 10. Kết luận

Scaffold này tốt hơn mức trung bình và các bug P0 đều thuộc loại "sửa trong một buổi chiều". Điểm đáng lo không nằm ở code đã viết, mà ở **những gì chưa được quyết định**: data model, nguồn nội dung + audio, và chiến lược AI.

Nếu chỉ được chọn **ba việc** để làm tiếp:

1. **Sửa CI đỏ** (P0-1) — vì mọi thứ khác đều vô nghĩa khi CI không tin được.
2. **Thiết kế data model + chốt nguồn nội dung/audio** (Sprint 2) — vì đây là thứ sẽ quyết định Phase 2–3 mất 1 tháng hay 3 tháng.
3. **Làm một vertical slice AI sớm** (7f) — vì đó là phần rủi ro nhất, và biết sớm luôn rẻ hơn biết muộn.
