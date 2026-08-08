# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TOEIC Pilot — an AI-powered TOEIC learning platform. Polyglot monorepo: FastAPI backend (`apps/api`), Next.js frontend (`apps/web`), shared TS types (`packages/shared`), Postgres+pgvector, Redis. Currently at **Phase 1 (scaffolding)**: monorepo, Docker, CI, and basic email/password auth only. Learning Hub, TOEIC Practice, AI Study Planner, and AI Coach (the actual product) are not yet built — `apps/api/app/ai` is an empty placeholder package for the future AI layer (LLM router, prompt engine, RAG engine, memory service, tool registry).

`planning/PLAN.md` is the product spec and single source of truth for scope. Development proceeds by Epic/Phase (see PLAN.md §7) — do not implement features from a later phase while an earlier one is in progress unless explicitly asked.

## Commands

### Python API (`apps/api`) — always use `uv`, never `pip`/bare `python`

```bash
cd apps/api
uv sync --extra dev                          # install deps (commit uv.lock after dependency changes)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                                # all tests
uv run pytest tests/test_health.py           # single file
uv run pytest tests/test_health.py::test_x -v  # single test
uv run ruff check app tests                  # lint (rules: E, F, I, UP; line-length 100)
uv run alembic upgrade head                  # apply migrations
uv run alembic revision --autogenerate -m "..."  # new migration
```

Tests run against SQLite in-memory by default (`tests/conftest.py` sets `DATABASE_URL` before app import if not already set) — no Postgres needed for local `pytest`. CI runs against real Postgres/Redis service containers.

### Web / monorepo root — pnpm + Turborepo

```bash
pnpm install
pnpm dev                                     # turbo dev, all workspace packages
pnpm --filter @toeic-pilot/web dev           # web only (Turbopack)
pnpm --filter @toeic-pilot/web lint
pnpm build                                   # turbo build (shared must build before web)
pnpm --filter @toeic-pilot/shared build      # rebuild shared types after editing packages/shared/src
```

### Full stack via Docker

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build      # postgres, redis, api, web
docker compose -f docker/docker-compose.yml up postgres redis -d  # infra only, for local dev servers
```

The `api` and `web` services bind-mount source (`apps/api/app`, `apps/web`, `packages/shared`) so container dev servers hot-reload; only `pyproject.toml`/`uv.lock`/`package.json` changes require a rebuild.

## Architecture

**Request flow**: Next.js pages (`apps/web/src/app/**`) → `apiFetch()` wrapper (`apps/web/src/lib/api.ts`) → FastAPI routes (`apps/api/app/api/routes/*.py`) using paths/types from `@toeic-pilot/shared` (`packages/shared/src/index.ts`, exports `API_ROUTES` and request/response TS types — **the frontend never hardcodes API paths or shapes**; add new endpoints there first). Any change to a backend request/response contract should be mirrored in `packages/shared/src/index.ts` and rebuilt (`pnpm --filter @toeic-pilot/shared build`) so the web app picks up the new types.

**Auth**: JWT bearer tokens (`python-jose`), password hashing via `passlib`/bcrypt. `app/core/security.py` creates/decodes tokens; `app/api/deps.py::get_current_user` is the FastAPI dependency that resolves the bearer token → DB user for protected routes. Frontend stores the token via `apps/web/src/lib/auth-storage.ts` and attaches it through `apiFetch`'s `token` option.

**Config**: `app/core/config.py` (`pydantic-settings`) loads `.env` into a single `settings` singleton — add new env-driven config there, not via `os.environ` reads scattered in code.

**DB**: `app/core/database.py` defines `engine`/`SessionLocal`/`Base` (SQLAlchemy 2.0 `DeclarativeBase`, `Mapped[...]` style — follow `app/models/user.py` as the pattern for new models). Routes get a session via the `get_db` dependency. `app/main.py`'s lifespan calls `Base.metadata.create_all` on startup for dev convenience — Alembic (`apps/api/alembic/`) is the source of truth for schema and must be used for anything beyond local scratch work. New models must be imported in `app/main.py` (or an equivalent import point) so their tables register with `Base.metadata` before `create_all`/autogenerate runs.

**Redis**: `app/core/redis_client.py::get_redis()` — connection is a soft dependency; app startup logs a warning and continues if Redis is unreachable rather than failing.

**Vector store**: Postgres via `pgvector` extension (image `pgvector/pgvector:pg16`), enabled in the initial Alembic migration. Intended for future embeddings/RAG work (Phase 4), not yet used by any route.

**Monorepo wiring**: pnpm workspaces (`apps/*`, `packages/*`) + Turborepo (`turbo.json`) for JS/TS; the Python API is a separate `uv`-managed project under `apps/api` and is not part of the pnpm/turbo graph. `pnpm build` builds `packages/shared` before `apps/web` (turbo `dependsOn: ["^build"]`) since web imports shared's compiled output (`dist/`), not its source.

## CI (`.github/workflows/ci.yml`)

Two independent jobs on push/PR to `main`/`master`:
- **api**: Postgres (pgvector) + Redis service containers → `uv sync --extra dev` → `ruff check app tests` → `pytest`.
- **web**: pnpm install → build `@toeic-pilot/shared` → lint `@toeic-pilot/web` → build `@toeic-pilot/web`.

Both must pass; there is no combined/integration CI job yet.
