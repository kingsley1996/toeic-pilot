# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TOEIC Pilot — an AI-powered TOEIC learning platform. Polyglot monorepo: FastAPI backend (`apps/api`), Next.js frontend (`apps/web`), shared TS contract (`packages/shared`), Postgres + pgvector, Redis.

**`planning/PLAN.md` is the product spec and the source of truth for scope.** Work proceeds phase by phase; do not implement a later phase's features while an earlier one is open unless asked.

**`planning/ROADMAP.md` is the single tracker** — sprints, tasks, real status, and what each finished sprint actually cost. Read it first; update it when you finish something. Nothing else in `planning/` carries status.

The rest carry decisions and their reasoning:

- **`planning/ADR-001-DATA-MODEL.md`** — the domain schema and why it has the shape it has.
- **`planning/PHASE2-AUDIO.md`** — audio architecture (this is ADR-002); Part A is the durable record, Part B the implementation log.
- **`planning/ADR-004-IMAGES.md`** — photographs for Part 1, licensing, and the fetch pipeline.
- **`planning/REVIEW-OPUS.md`** — an engineering review dated 2026-08-08. A snapshot, not a tracker; its §8 roadmap is superseded by `ROADMAP.md`.

### Current state (2026-08-09)

Phase 1 (scaffolding + auth) is done and hardened. Two remediation passes have landed: all six P0 issues and seven of ten P1 issues from `planning/REVIEW-OPUS.md`.

Sprint 2 is in progress. **Audio infrastructure is built** — `planning/PHASE2-AUDIO.md` Part B is complete: `audio_asset` (migration `002`), the content-addressed naming in `app/core/media.py`, the offline `app/content/` pipeline behind the `content` extra, a committed manifest, and a development-only `/media` mount. Part A remains the durable record of *why*; read §A4 before changing any of it.

Product features are still **not** built. `apps/api/app/ai/` is an empty placeholder for the Phase 4 AI layer.

**The data model is designed and migrated** — `planning/ADR-001-DATA-MODEL.md`, migrations `003` and `004`. That closes `REVIEW-OPUS.md` §7a, the last thing blocking Phase 2. Twenty tables cover vocabulary (with SM-2 spaced repetition), dictation, questions/options/sets, practice tests, attempts, media assets and score conversion. Phase 4–5 tables (`study_plan`, `learning_memory`, `knowledge_chunk`, `ai_interaction`) are designed on paper only in Part C, because their vector dimensions depend on an embedding model ADR-003 has not chosen.

Nothing is built *on top of* the schema yet: **no product endpoints at all** (the five that exist are auth and health), and `packages/shared` is therefore unchanged — the contract is generated from endpoints, and there are none. The sample content — 16 audio clips, 3 photographs — exists to prove the pipelines run, not to teach anyone.

**The real bottleneck for the next two sprints is content, not code.** Writing the vocabulary endpoints takes days; authoring 500 words with examples and four-accent audio takes much longer.

Still open from P1: frontend/e2e tests (P1-3), token in `localStorage` (P1-7), rate limiting (P1-8) — the last is a hard prerequisite for Phase 4, since an unmetered LLM endpoint is an unmetered bill.

## Commands

### Python API (`apps/api`) — always `uv`, never `pip` or bare `python`

```bash
cd apps/api
uv sync --extra dev

uv run uvicorn app.main:app --reload --port 8000
uv sync --extra dev --extra content         # add the offline content pipeline

uv run pytest                              # 191 tests
uv run pytest -m "not integration"         # skip the ones needing PostgreSQL
uv run pytest tests/test_auth.py::test_x -v
uv run ruff check app tests
uv run ruff format app tests
uv run mypy                                # strict; config in pyproject.toml
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "..."

# Offline content pipeline — needs --extra content, never runs at request time
uv run python -m app.content.generate --input content/sources/<spec>.jsonl --dry-run
uv run python -m app.content.generate --input content/sources/<spec>.jsonl
uv run python -m app.content.images --input content/sources/images/<spec>.jsonl
uv run python -m app.content.seed          # manifests -> audio_asset / image_asset rows
uv run python -m app.content.seed_scores   # default raw -> scaled score curve
TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external   # calls edge-tts for real
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

**Database.** `app/core/database.py` exposes `engine` / `SessionLocal` / `Base` (SQLAlchemy 2.0 `Mapped[...]` style — follow `app/models/user.py`). Routes take a session via the `get_db` dependency. **Alembic owns the schema**; `metadata.create_all` runs only when `environment == "development"`. New models must be re-exported from `app/models/__init__.py` — that one package import is what `app/main.py`, `alembic/env.py` and `tests/conftest.py` all rely on to register tables on `Base.metadata`. A model missing from it produces "no such table" in tests and an empty autogenerate diff.

**Domain model.** Designed in `planning/ADR-001-DATA-MODEL.md` and created by migration `003`; there are no endpoints over it yet. Shared column vocabulary (`PublishableMixin`, status/difficulty CHECK helpers) lives in `app/models/mixins.py`. Two shapes look wrong until you check the exam (ADR-001 §A2):

- `question.set_id` is **nullable** — only parts 3, 4, 6 and 7 group questions under a shared stimulus. A CHECK requires it for exactly those parts.
- `question.prompt_text` and `question_option.content` are **nullable** — part 2 prints nothing at all and has three options rather than four. Null is the correct value there, not missing data.

Audio hangs off two levels for the same reason: parts 1–2 on `question`, parts 3–4 on `question_set`.

`app/models/validators.py` holds the content rules no declarative constraint can express (ADR-001 §B4): at *least* one correct option, the per-part option count, `question.part` matching its set's part, and the printing rules. The partial unique index only rules out *more* than one correct answer — a question with none inserts cleanly and can never be answered correctly.

**Parts 1 and 2 print nothing.** ETS states it outright for both: the statements and responses are spoken only, never printed. Part 1's test book shows the photograph alone; part 2's shows nothing. So `prompt_text` and `question_option.content` are NULL for both — part 1 just also has an image and four options rather than three.

**Images (ADR-004).** `image_asset` mirrors `audio_asset` but is a separate table on purpose: merged, more than half the columns would always be NULL. `license`, `attribution` and `source_url` are NOT NULL because most openly-licensed photographs are CC-BY — usable only *with* credit — and storing the credit is not enough: any endpoint serving a Part 1 image must return it and the UI must render it. `app/content/images.py` fetches from a hand-curated spec file rather than a search API, because a photograph still needs a human to decide whether four statements can be written about it.

**Scoring (`app/services/scoring.py`).** The raw-to-scaled curve lives in `score_scale` / `score_conversion` rather than in code: TOEIC curves differ per form, and a scoring bug should be fixable by editing a row. Lookups **refuse to guess** — a missing conversion raises rather than interpolating, because a silently wrong score is stored permanently on the attempt and the learner cannot tell it is wrong. The seeded default is an approximation and says so in `source_note`; ETS publishes no official table.

**Health vs readiness.** `/health` is liveness and deliberately checks nothing — a database outage must not get the container restarted. `/ready` queries Postgres and pings Redis, returning 503 when Postgres is down. Redis is a soft dependency everywhere: startup logs a warning and `/ready` reports `degraded` rather than failing.

**Logging.** `app/core/logging.py` provides a JSON formatter, a text formatter for local reading (`LOG_FORMAT`), and `RequestContextMiddleware`, which assigns or accepts an `X-Request-ID`, exposes it through a `ContextVar`, echoes it on the response, and logs one line per request. This exists now specifically so Phase 4's LLM calls are traceable from day one.

**Vector store.** pgvector is enabled by the initial migration but unused so far; it is there for Phase 4 RAG.

**Audio and the content pipeline.** Decisions live in `planning/PHASE2-AUDIO.md` Part A; read §A4 before changing anything here, because all four invariants fail silently. The shape:

- `app/core/media.py` — content-addressed naming, pure stdlib, imported by *both* sides. `source_hash` fingerprints the synthesis **input** (text | logical voice | engine | engine version), never the mp3 bytes: TTS is not byte-deterministic, so hashing output would break idempotency. `voice` is a **logical** name (`us_female_1`), never a provider id (`en-US-JennyNeural`) — that indirection is what kept the library intact when `en-AU-WilliamNeural` was renamed upstream.
- `app/models/audio.py` — `audio_asset`, deliberately independent of the domain schema. The dependency runs domain → asset. `source_text` is **not** the grading answer key; dictation grades against `dictation_item.transcript`.
- `app/content/**` — the offline pipeline, behind the optional `content` extra. `generate` synthesises and writes `content/manifest/audio_assets.jsonl`; `seed` reads that manifest and upserts rows by `source_hash`. Generation happens **offline**, so an edge-tts outage blocks new content rather than breaking what already exists.
- The manifest is committed; the mp3s under `apps/api/media/` are gitignored. `generate` therefore skips only when the manifest entry *and* the file both exist — otherwise a fresh clone would never re-render them.
- Serving is a string join: `{audio_public_base_url}/{storage_key}`. The API never calls the object store at request time, and audio must **never** be proxied through FastAPI — that loses range requests and burns the API's bandwidth. `/media` is mounted only when `environment == "development"`.

**Nothing reachable from `app/main.py` may import `app.content`.** The production image is built `--no-dev` without the `content` extra, so a leak breaks container startup rather than the build. `tests/test_content_isolation.py` catches it in a subprocess in under a second; the `docker` CI job catches it the slow way. Shared code belongs in `app/core/`.

**Monorepo wiring.** pnpm workspaces + Turborepo for JS/TS. `apps/api` is a separate `uv` project outside the turbo graph, so cross-cutting scripts (`scripts/generate-api-types.sh`) drive both toolchains.

## Testing conventions

- Backend tests live in `apps/api/tests/`. `conftest.py` provides `db_session` (SQLite via `StaticPool` — required, or each connection gets a private empty database) and `client` (overrides `get_db`).
- Tests needing PostgreSQL are marked `integration` and skip cleanly without it.
- Tests calling a third-party service are marked `external` and are deselected by `addopts`. **CI must never run them.** Because an explicit `-m` on the command line replaces `addopts` entirely — including the documented `pytest -m "not integration"` — they also self-guard on `TOEIC_ALLOW_EXTERNAL_TTS=1`.
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
- **`alembic/` is not linted or type-checked.** CI runs `ruff check app tests` and mypy over `app` only, so migrations follow `001`'s existing style (`typing.Union`, `typing.Sequence`) rather than the modern syntax ruff would demand elsewhere. `alembic/script.py.mako` was missing until Sprint 2, which meant the documented `alembic revision --autogenerate` had never actually been able to write a file.
- **`tests/test_concurrency.py` runs `create_all` against the real dev Postgres.** After a test run with Postgres up, the dev database holds every table in `Base.metadata` — so `alembic revision --autogenerate` compares against a schema that already matches and emits an *empty* migration. Reset before generating: `psql -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'` then `alembic upgrade head`.
- **The dev `api` container recreates the schema on every reload.** It runs uvicorn with `--reload` and `environment=development`, so editing anything under `app/` restarts it and runs `create_all` against the dev Postgres — which will rebuild the tables you just dropped to generate a migration. `docker compose stop api` before doing migration work.
- **Public archives rate-limit and require a User-Agent.** Wikimedia returns 403 to httpx's default UA and 429 partway through a bulk run. `app/content/images.py` sends an identifying UA and paces itself; a failed image is reported and skipped rather than aborting the run, so the successes survive and the next run picks up only what is missing.
- **edge-tts voice ids drift.** They are provider ids, not ours, and Microsoft retires them without notice. `tests/test_tts_external.py` checks every `LOGICAL_VOICES` entry against the live catalogue — run it (`TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external`) before any bulk generation, because a stale id otherwise fails one clip at a time in the middle of a long run.
