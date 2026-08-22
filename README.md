# TOEIC Pilot

An AI-assisted TOEIC learning platform: vocabulary with spaced repetition,
dictation graded word by word, and full practice tests scored against a
conversion curve — plus the authoring tools that get that content in.

Polyglot monorepo. FastAPI + PostgreSQL/pgvector behind a Next.js front end,
with a shared TypeScript contract generated from the API's own OpenAPI schema.

## Status

Working end to end, on real content, verified through the running stack rather
than in tests alone:

| Area | State |
|---|---|
| Accounts | Registration, JWT auth, per-session logout, password change, profile |
| Vocabulary | Paste-to-import, offline TTS, SM-2 review, per-topic sessions, two minigames |
| Dictation | Four-level topic tree, word-by-word diffing, progress by completion |
| Practice tests | Paste-to-import, media attachment, attempts, scoring, review |
| AI layer | Question labelling across a 72-code taxonomy, coach explanations |
| Petland | An optional pet corner with two mascots the learner picks between |

Measured on `main` (2026-08-21): 38 tables across 29 migrations · 106 API paths
/ 131 operations · 637 backend tests · 36 front-end routes.

What it is **not** yet: there is no RAG layer. That decision is written up in
[`planning/ADR-003-AI-LAYER.md`](planning/ADR-003-AI-LAYER.md) and it is blocked
by content rather than engineering.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js App Router (`apps/web`) |
| Backend | FastAPI, SQLAlchemy 2.0, Alembic (`apps/api`) |
| Database | PostgreSQL + pgvector |
| Cache / limits | Redis |
| Shared contract | `@toeic-pilot/shared`, generated from OpenAPI |
| Monorepo | pnpm workspaces + Turborepo |
| Media | Offline TTS (edge-tts) and image fetch, behind an optional extra |
| Infra | Docker Compose; separate API and worker images |

## Quick start

Docker is the supported path — it is the only one that brings up Postgres,
Redis, the API, the web app and the TTS worker together, and the API container
runs `alembic upgrade head` before it serves.

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

- Web — http://localhost:3000
- API docs — http://localhost:8000/docs

Adding a JavaScript dependency needs `up -d --build`, not `up -d`: `node_modules`
is a named volume and Docker only seeds one from the image when it is empty.

### Running pieces on the host

Infrastructure only, then each service by hand:

```bash
docker compose -f docker/docker-compose.yml up postgres redis -d

pnpm install
pnpm --filter @toeic-pilot/web dev

cd apps/api && uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

Do not run `pnpm dev` or `pnpm build` on the host while the `web` container is
up — both write the same `apps/web/.next`, and a mixed cache makes the dev
server hang on every request while still logging a clean startup.

## Development

```bash
# Backend — always uv, never pip
cd apps/api
uv run pytest                       # 637 tests
uv run pytest -m "not integration"  # skip the ones needing PostgreSQL
uv run ruff check app tests && uv run ruff format app tests
uv run mypy                         # strict
uv run alembic upgrade head

# Frontend
pnpm --filter @toeic-pilot/web lint
pnpm --filter @toeic-pilot/web exec tsc --noEmit   # eslint does NOT typecheck
pnpm --filter @toeic-pilot/web test:e2e            # Playwright, needs the stack up

# Shared contract — generated, never hand-edited
pnpm gen:api-types
```

`pnpm lint` is eslint alone. Run `tsc --noEmit` before calling a front-end
change verified; CI's `web` job builds, so it catches type errors one push
later than the person who wrote them.

## Layout

```
apps/
  api/            FastAPI app, Alembic migrations, offline content pipeline
    app/api/      routers
    app/models/   SQLAlchemy models
    app/services/ logic that is not HTTP (SM-2, diffing, scoring, media state)
    app/content/  offline TTS / image tooling, behind the `content` extra
  web/            Next.js App Router, design-system primitives, Playwright specs
packages/
  shared/         generated API types + the hand-maintained route map
docker/           Compose file and the API / worker images
planning/         product spec, ADRs, architecture and the single tracker
```

## Documentation

`planning/` holds the reasoning. Start with:

| File | What it is |
|---|---|
| [`PLAN.md`](planning/PLAN.md) | Product spec — the source of truth for scope |
| [`ROADMAP.md`](planning/ROADMAP.md) | The single tracker: sprints, real status, what each cost |
| [`ARCHITECTURE.md`](planning/ARCHITECTURE.md) | What the system is made of right now |
| [`DESIGN-SYSTEM.md`](planning/DESIGN-SYSTEM.md) | UI tokens, type, components — implemented across `apps/web` |
| [`MEDIA-PIPELINE.md`](planning/MEDIA-PIPELINE.md) | How audio and images work end to end, and where they are weak |
| [`USER-ROAD.md`](planning/USER-ROAD.md) | Levels, XP, daily tasks, badges and avatar frames — built, configurable at `/admin/progression` |

Decisions and their reasoning live in the ADRs: the domain schema
([ADR-001](planning/ADR-001-DATA-MODEL.md)), audio
([PHASE2-AUDIO](planning/PHASE2-AUDIO.md), which is ADR-002), the AI layer
([ADR-003](planning/ADR-003-AI-LAYER.md)), images
([ADR-004](planning/ADR-004-IMAGES.md)), content tooling
([ADR-005](planning/ADR-005-CONTENT-TOOLING.md)), media upload
([ADR-006](planning/ADR-006-MEDIA-UPLOAD.md)) and test authoring
([ADR-007](planning/ADR-007-TEST-AUTHORING.md)).

`CLAUDE.md` at the repo root is written for coding agents. It repeats a lot of
the above in a denser form, with an emphasis on the failure modes that are
silent.

## CI

`.github/workflows/ci.yml` runs four required jobs:

| Job | Checks |
|---|---|
| `api` | ruff lint + format, mypy strict, `alembic upgrade head`, pytest with Postgres and Redis services |
| `web` | prettier, build shared, eslint, build web |
| `contract` | regenerates the API types and fails on any diff |
| `docker` | builds both images and boots the API image |

Branch protection is not enabled yet, so a green CI is a signal rather than a
gate.

## License

Not yet chosen. Practice-test content carries its own provenance per row —
`question.source` is NOT NULL and distinguishes material written to the format
from material actually licensed. See [ADR-001](planning/ADR-001-DATA-MODEL.md).
