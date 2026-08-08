# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TOEIC Pilot — an AI-powered TOEIC learning platform. Polyglot monorepo: FastAPI backend (`apps/api`), Next.js frontend (`apps/web`), shared TS contract (`packages/shared`), Postgres + pgvector, Redis.

**`planning/PLAN.md` is the product spec and the source of truth for scope.** Work proceeds phase by phase; do not implement a later phase's features while an earlier one is open unless asked.

Two companion documents carry the engineering state, and both are worth reading before planning work:

- **`planning/REVIEW-OPUS.md`** — running engineering review: open issue list (P0/P1/P2) and the sprint roadmap.
- **`planning/PHASE2-AUDIO.md`** — audio architecture decisions (Part A, durable) and the implementation checklist (Part B, expires on completion).

### Current state (2026-08-08)

Phase 1 (scaffolding + auth) is done and hardened. Two remediation passes have landed: all six P0 issues and seven of ten P1 issues from `planning/REVIEW-OPUS.md`.

Product features are **not** built yet. `apps/api/app/ai/` is an empty placeholder for the Phase 4 AI layer. There is no domain model beyond `User` — no questions, tests, attempts, vocabulary, or progress tables.

**Phase 2 is blocked on one decision, not on code: there is no data model** for Learning Hub / TOEIC Practice (`REVIEW-OPUS.md` §7a). Design it before writing any Phase 2 endpoint.

Audio was the second blocker and is now **decided but not built** — `planning/PHASE2-AUDIO.md`. Keep those two apart: the decisions are recorded, while the repo still has no object storage, no `audio_asset` table, no TTS dependency, and no media handling of any kind. Read Part A before touching audio; §A4 records four invariants that are easy to violate and whose consequences do not surface immediately.

One of those decisions constrains §7a directly: TOEIC needs four accents, so a single FK column will not do — vocabulary will need a join table (`PHASE2-AUDIO.md` §A6).

Still open from P1: frontend/e2e tests (P1-3), token in `localStorage` (P1-7), rate limiting (P1-8) — the last is a hard prerequisite for Phase 4, since an unmetered LLM endpoint is an unmetered bill.

## Commands

### Python API (`apps/api`) — always `uv`, never `pip` or bare `python`

```bash
cd apps/api
uv sync --extra dev

uv run uvicorn app.main:app --reload --port 8000
uv run pytest                              # 62 tests
uv run pytest -m "not integration"         # skip the ones needing PostgreSQL
uv run pytest tests/test_auth.py::test_x -v
uv run ruff check app tests
uv run ruff format app tests
uv run mypy                                # strict; config in pyproject.toml
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "..."
```

Tests default to SQLite in-memory (`tests/conftest.py` sets `DATABASE_URL` before the app imports). Tests marked `integration` need real PostgreSQL and **skip automatically** when it is unreachable; point them elsewhere with `TEST_DATABASE_URL`. CI runs them for real against a Postgres service.

### Monorepo — pnpm + Turborepo

```bash
pnpm install
pnpm dev                                   # turbo dev
pnpm --filter @toeic-pilot/web dev
pnpm build                                 # shared builds before web
pnpm --filter @toeic-pilot/web lint
pnpm format / pnpm format:check            # prettier; markdown is excluded on purpose
pnpm gen:api-types                         # regenerate the shared contract — see below
```

### Full stack

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
docker compose -f docker/docker-compose.yml up postgres redis -d   # infra only
```

`api` runs `alembic upgrade head` via `docker/api-entrypoint.sh` before uvicorn binds (`RUN_MIGRATIONS=0` skips it). `web` waits for `api` to report healthy, and `api`'s healthcheck hits `/ready`, so nothing starts until Postgres is genuinely reachable. Source is bind-mounted for hot reload; only dependency-manifest changes need a rebuild.

## Architecture

**Request flow.** Next.js pages (`apps/web/src/app/**`) → `apiFetch()` (`apps/web/src/lib/api.ts`) → FastAPI routes (`apps/api/app/api/routes/*.py`), using paths and types from `@toeic-pilot/shared`. The frontend never hardcodes an API path or response shape.

**The shared contract is generated, not written.** `packages/shared/src/api-types.ts` and `packages/shared/openapi.json` are produced by `pnpm gen:api-types` from FastAPI's own OpenAPI schema. `src/index.ts` only re-exports friendly aliases (`UserPublic`, `TokenResponse`, …) plus the hand-maintained `API_ROUTES` map.

- **Never hand-edit `api-types.ts` or `openapi.json`.** Change the Pydantic schema, then regenerate and commit both files. The `contract` CI job regenerates and fails on any diff.
- `apps/web` imports the package's **compiled `dist/`**, not `src/`. A stale `dist` can satisfy imports and hide drift, which is why `prebuild` wipes it.

**Config.** `app/core/config.py` holds one `settings` singleton (`pydantic-settings`); add env-driven config there rather than reading `os.environ` around the codebase. `env_file` uses **absolute** paths (repo root, then `apps/api`) because a relative `.env` silently resolves against the CWD — which broke the documented dev flow. Real env vars still outrank both, which is how Compose injects values. `ENVIRONMENT=production` refuses to boot on the default `SECRET_KEY`.

**Auth.** JWT bearer tokens (`python-jose`); passwords hashed with the `bcrypt` library directly. `app/api/deps.py::get_current_user` resolves the token to a user; it parses `sub` as a UUID first, because comparing arbitrary text to a UUID column makes Postgres raise and surface as a 500.

**bcrypt's 72-byte limit is enforced explicitly.** `app/core/security.py` raises `PasswordTooLongError` and `app/schemas/auth.py` turns it into a 422. The limit is measured in **bytes, not characters** — a 40-character Vietnamese password is 120 bytes. Do not "fix" this by truncating: older pins truncated silently, which meant only a prefix of the password ever authenticated. Existing `$2b$` hashes from the previous passlib stack still verify; `tests/test_security.py` pins a real one as a golden value.

**Database.** `app/core/database.py` exposes `engine` / `SessionLocal` / `Base` (SQLAlchemy 2.0 `Mapped[...]` style — follow `app/models/user.py`). Routes take a session via the `get_db` dependency. **Alembic owns the schema**; `metadata.create_all` runs only when `environment == "development"`. New models must be imported somewhere reachable from `app/main.py` so their tables register on `Base.metadata`.

**Health vs readiness.** `/health` is liveness and deliberately checks nothing — a database outage must not get the container restarted. `/ready` queries Postgres and pings Redis, returning 503 when Postgres is down. Redis is a soft dependency everywhere: startup logs a warning and `/ready` reports `degraded` rather than failing.

**Logging.** `app/core/logging.py` provides a JSON formatter, a text formatter for local reading (`LOG_FORMAT`), and `RequestContextMiddleware`, which assigns or accepts an `X-Request-ID`, exposes it through a `ContextVar`, echoes it on the response, and logs one line per request. This exists now specifically so Phase 4's LLM calls are traceable from day one.

**Vector store.** pgvector is enabled by the initial migration but unused so far; it is there for Phase 4 RAG.

**Monorepo wiring.** pnpm workspaces + Turborepo for JS/TS. `apps/api` is a separate `uv` project outside the turbo graph, so cross-cutting scripts (`scripts/generate-api-types.sh`) drive both toolchains.

## Testing conventions

- Backend tests live in `apps/api/tests/`. `conftest.py` provides `db_session` (SQLite via `StaticPool` — required, or each connection gets a private empty database) and `client` (overrides `get_db`).
- Tests needing PostgreSQL are marked `integration` and skip cleanly without it.
- **A concurrency test that just fires N threads does not test concurrency here.** The first writer commits before the others reach the advisory pre-check, so the `IntegrityError` branch is never entered and the test passes even with the fix removed. `tests/test_concurrency.py` uses a `threading.Barrier` between the pre-check and the commit to force a genuine race.
- **When fixing a bug, verify the new test fails without the fix** — `git stash push -- <file>` or `git show HEAD~1:<file>`, run, confirm red, restore. Editing the file by string replacement to "revert" it is easy to get silently wrong.

## CI (`.github/workflows/ci.yml`)

Four jobs, all required:

| Job | Checks |
|---|---|
| `api` | ruff lint, ruff format, mypy strict, `alembic upgrade head`, pytest (with Postgres + Redis services, so integration tests run) |
| `web` | prettier, build shared, eslint, build web |
| `contract` | regenerates the API types and fails if the committed ones differ |
| `docker` | builds both images **and boots the API image** — a broken image once built fine and only failed at runtime |

Branch protection is **not yet enabled**; a green CI that nothing enforces is only a suggestion.

## Gotchas worth knowing

- **`.dockerignore` is load-bearing.** Without it, `COPY apps/api ./` overwrote the image's Linux virtualenv with the host's macOS one and the container could not start at all. Never remove `**/.venv`, `**/node_modules`, or `**/dist` from it.
- **`eslint.config.mjs` must not use `FlatCompat`.** `eslint-config-next@16` ships native flat configs; wrapping them in `FlatCompat` throws `Converting circular structure to JSON` and takes CI down.
- Empty directories survive a `git` revert. An `apps/web/src/app/learning/**` skeleton outlived a reverted Phase 2 attempt for exactly this reason and went unnoticed for two sprints (it has since been deleted). Next.js only routes a directory that contains a `page.tsx`, so such leftovers are inert — and therefore invisible until someone looks.
- Prettier deliberately ignores `*.md` and `planning/**` so prose edits stay out of code diffs.
