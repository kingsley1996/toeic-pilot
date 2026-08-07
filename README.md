# TOEIC Pilot

AI-powered TOEIC learning platform (Phase 1 scaffolding).

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (`apps/web`) |
| Backend | FastAPI (`apps/api`) |
| Database | PostgreSQL + pgvector |
| Cache | Redis |
| Shared types | `@toeic-pilot/shared` |
| Monorepo | pnpm workspaces + Turborepo |
| Infra | Docker Compose |

## Prerequisites

- Node.js 20+
- pnpm 9+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker (optional, for Postgres/Redis/services)

## Quick start (local)

1. Copy environment file:

   ```bash
   cp .env.example .env
   ```

2. Start Postgres and Redis:

   ```bash
   docker compose -f docker/docker-compose.yml up postgres redis -d
   ```

3. Install dependencies:

   ```bash
   pnpm install
   cd apps/api && uv sync --extra dev
   ```

4. Run database migrations (optional; API also runs `create_all` on startup for dev):

   ```bash
   cd apps/api && uv run alembic upgrade head
   ```

5. Start dev servers (two terminals):

   ```bash
   pnpm --filter @toeic-pilot/web dev
   ```

   ```bash
   cd apps/api && uv run uvicorn app.main:app --reload --port 8000
   ```

- Web: http://localhost:3000  
- API docs: http://localhost:8000/docs  

## Docker (full stack)

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

## Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Turbo dev (web + shared watch when configured) |
| `pnpm build` | Build all packages |
| `pnpm lint` | Lint workspace |
| `cd apps/api && uv run pytest` | API tests |
| `cd apps/api && uv run ruff check app tests` | Python lint |

## Project layout

```
apps/
  api/          FastAPI, auth, Alembic, AI layer placeholders
  web/          Next.js App Router
packages/
  shared/       Shared TypeScript contracts
docker/         Compose + Dockerfiles
planning/       PLAN.md (product spec)
```

## Authentication (MVP scaffold)

- `POST /api/v1/auth/register` — email + password (min 8 chars)
- `POST /api/v1/auth/login` — returns JWT bearer token
- `GET /api/v1/auth/me` — current user (requires `Authorization: Bearer …`)

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs API tests (Postgres + Redis services), Ruff, and Next.js lint/build.

## License

TBD.
