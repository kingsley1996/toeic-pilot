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
- **`planning/ADR-007-TEST-AUTHORING.md`** — how a TOEIC test gets into the system: the audio script lives on the question, not in a spec file beside it (which is what kills the `LIKE 'prefix%'` lookup `seed_demo_test.py` still uses), paste-then-form authoring, canonical question numbers stored rather than derived, and audio generation reached by a Redis doorbell over a query-shaped work queue.
- **`planning/ADR-005-CONTENT-TOOLING.md`** — the admin UI for importing past papers: why a custom admin rather than a headless CMS, why paste-and-parse, and why parse never writes to the database.
- **`planning/REVIEW-OPUS.md`** — an engineering review dated 2026-08-08. A snapshot, not a tracker; its §8 roadmap is superseded by `ROADMAP.md`.

Two descriptions of *current behaviour* rather than of decisions:

- **`planning/ARCHITECTURE.md`** — what the system is made of right now: components, routers, services, file map, and the last verification run. Read it for orientation; `ROADMAP.md` still owns status.
- **`planning/MEDIA-PIPELINE.md`** — how audio and images actually work end to end today, plus an honest strengths/weaknesses list. Read §10 before extending either pipeline: **§10.3 (images are not reproducible) is a real defect**, not a known limitation. §10.1 and §10.2 were too and are now fixed — §10.1 by `app/services/media_state.py`, §10.2 by `app/content/audio_join.py`.

- **`planning/DESIGN-SYSTEM.md`** — the UI design system, **implemented across all of `apps/web`**: contrast-verified colour tokens for light and dark, the three-state theme switch, type (Archivo / Be Vietnam Pro / IBM Plex Mono, all with the `vietnamese` subset), the four-accent categorical scale, Lucide icon rules, component specs. Three rules there are load-bearing and fail quietly: **no `box-shadow`**, **one 4px radius** (the Tailwind scale is replaced, so `rounded-lg` emits nothing), and **`rule-strong` for component boundaries** — `rule` is decorative and does not meet the 3:1 that WCAG 1.4.11 requires of an input border.

And one provisional spec:

- **`planning/SPEC-LEARNING-HUB.md`** — the defaults the Learning Hub was built to (SM-2 grades, session limits, dictation grading). Explicitly built to be changed after real use; its §5 lists what will probably need to move.

### Current state (2026-08-09)

Phase 1 (scaffolding + auth) is done and hardened: all six P0 issues and seven of ten P1 issues from `planning/REVIEW-OPUS.md` are closed.

**The media pipelines are built** — `PHASE2-AUDIO.md` (audio, offline TTS in four accents) and `ADR-004-IMAGES.md` (Part 1 photographs, fetched and normalised, licence and attribution required). Both sit behind the optional `content` extra and neither may be imported by the API. `planning/MEDIA-PIPELINE.md` describes how they actually behave, including two real defects still open in §10.

**The domain schema is designed and migrated** — `ADR-001-DATA-MODEL.md`, migrations `003`–`008`. Twenty-three tables cover vocabulary (with SM-2 spaced repetition), dictation and its four-level tree, questions/options/sets, practice tests, attempts, media assets, roles and score conversion. Phase 4–5 tables (`study_plan`, `learning_memory`, `knowledge_chunk`, `ai_interaction`) exist on paper only, because their vector dimensions depend on an embedding model ADR-003 has not chosen.

**Vocabulary and dictation work end to end.** An editor pastes rows, they land as `draft`, `app/content/backfill_audio.py` synthesises the audio out of band, publishing is refused until every clip matches its text, and a learner reviews with SM-2 flashcards and works through dictation. Verified through the running Docker stack, not just in tests.

**Dictation has its own four-level tree and grades in the browser.** `dictation_topic → dictation_section → dictation_story → dictation_item`, with `item.position` ordering the sentences inside a story and progress tracked per story. The whole of `apps/web/src/lib/dictation.ts` is a step-for-step port of `app/services/dictation.py`; the server still re-grades every submission and its number is the one stored. The UI shows no percentage at all — only "đúng rồi / chưa đúng" and "3/6 câu đã xong".

Three things to know before extending it:

- **`app/services/`** holds the logic that is not HTTP: `srs.py` (SM-2, pure arithmetic), `dictation.py` (normalise + `SequenceMatcher` diff), `media_state.py` (is this clip still the right one?), `content_import.py` (paste parsers), `scoring.py` (raw → scaled). All pure enough to test without a session.
- **`require_role` is a dependency, never an in-body check** — a check in the handler is the one someone forgets to copy into the next route, and the failure mode is an admin endpoint open to every learner. Every admin endpoint has a test asserting a learner gets 403.
- **The API cannot generate audio.** It cannot even import the TTS pipeline (A4.1), and synchronous synthesis would drag in a job queue that A2.5 deliberately avoided. `backfill_audio` runs out of band and its work queue is a *query* — "content whose audio is missing or no longer matches its text" — so there is no queue table, no retry state, and re-running simply finds less to do.

**What is missing is content, not features.** `content/sources/` holds three words and four dictation sentences; the committed manifest carries 67 audio clips and 3 images. Enough to prove the path, nowhere near enough to teach anyone. Authoring several hundred entries is the real remaining work, and it is why the admin tooling came first.

**TOEIC Practice is partly built** — attempts run end to end (start, save an answer, flag, submit, score); the exam runner UI is not written. The old blocker is gone: the pipeline **can** now produce a multi-voice clip (`MEDIA-PIPELINE.md` §10.2, `app/content/audio_join.py`), so Part 2 (question in one voice, three responses in another) and Part 3 (a two-to-three-speaker conversation, the largest part at 39 questions) have a way to get audio. Two things about it fail quietly and are written up in §10.2: **`gap_ms` is silence *added* to the ~1.1s edge-tts pads each turn boundary with**, and **turns that mix accents must declare `"accent"`** rather than have one picked for them. Real TOEIC papers are ETS copyright, and ETS licenses electronic use per year through its general counsel — `question.source` is NOT NULL precisely so provenance is answered per row: `original` means written to the format (formats are not copyrightable, specific text is), `licensed` means permission actually obtained. **Do not default that field anywhere in code or UI.**

**The frontend has a design system, not per-page styling.** `src/components/ui.tsx` holds the primitives, colours come from CSS variables in `globals.css` (so light and dark are one definition rather than a `dark:` twin on every element), and `src/lib/session.tsx` resolves who is signed in *once* for the whole app. Three things follow from that and are easy to undo by accident:

- **Auth has three states, not two.** `loading` is distinct from `anonymous`, because localStorage does not exist during the server render. Collapsing them is what made the old header offer "Log in" to people who were already signed in, and a `? :` on `status === "authenticated"` reintroduces it — the else branch fires while still loading.
- **`useRequireSession({ canEdit: true })` redirects rather than showing a 403.** Someone who never had access should not be told they were refused. The server still enforces every boundary through `require_role`; this only decides what is worth rendering.
- **`status` in the session is derived, not stored.** Writing it from an effect cascades renders and lets it drift out of step with the token it describes. The `react-hooks/set-state-in-effect` lint rule enforces this and will reject the shortcut.

Still open from P1: frontend/e2e tests (P1-3), token in `localStorage` (P1-7), rate limiting (P1-8) — the last is a hard prerequisite for the AI layer, since an unmetered LLM endpoint is an unmetered bill.

## Commands

### Python API (`apps/api`) — always `uv`, never `pip` or bare `python`

```bash
cd apps/api
uv sync --extra dev

uv run uvicorn app.main:app --reload --port 8000
uv sync --extra dev --extra content         # add the offline content pipeline

uv run pytest                              # 296 collected: 294 run + 2 `external` deselected
uv run pytest -m "not integration"         # skip the ones needing PostgreSQL

# The three `integration` tests default to the DEV database, and they run
# `create_all` on it — which is what makes `alembic revision --autogenerate`
# emit an empty migration afterwards. Point them at a scratch database instead:
docker compose -f ../../docker/docker-compose.yml exec -T postgres \
  psql -U toeic -d postgres -c 'CREATE DATABASE toeic_test;'
TEST_DATABASE_URL="postgresql+psycopg://toeic:toeic@localhost:5432/toeic_test" uv run pytest
uv run pytest tests/test_auth.py::test_x -v
uv run ruff check app tests
uv run ruff format app tests
uv run mypy                                # strict; config in pyproject.toml
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "..."

# Offline content pipeline — needs --extra content, never runs at request time
uv run python -m app.content.generate --input content/sources/<spec>.jsonl --dry-run
uv run python -m app.content.generate --input content/sources/<spec>.jsonl
# Multi-voice clips (Parts 2 and 3) need ffmpeg on the authoring machine — the
# same class of prerequisite as network access for edge-tts. The production
# image has neither and needs neither.
uv run python -m app.content.images --input content/sources/images/<spec>.jsonl
uv run python -m app.content.seed          # manifests -> audio_asset / image_asset rows
uv run python -m app.content.seed_scores   # default raw -> scaled score curve
uv run python -m app.content.backfill_audio [--dry-run] [--only questions]  # audio the DB is missing
uv run python -m app.content.tts_worker --once            # one sweep, then exit
uv run python -m app.content.tts_worker                   # long-running: Redis doorbell + 300s sweep
uv run python -m app.content.push_media [--dry-run]       # local media -> its provider (images: Cloudinary, audio: S3)
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

**`docker/web-entrypoint.sh` runs `pnpm install` before the dev server**, for the same reason `api-entrypoint.sh` runs Alembic before uvicorn: a container must not serve against a state it has not reconciled. Adding a JS dependency therefore needs nothing special — `up -d` is enough, and the install costs ~2s on a warm volume.

It exists because `web` mounts `node_modules` as **named volumes**, and Docker seeds a named volume from the image only when the volume is *empty*. Without the entrypoint, `up --build` installs the new package into the fresh image and then mounts yesterday's volume straight over it, and the container fails with `Module not found` for a package that is plainly in `package.json` — which sends you looking at the package, the import and the bundler, none of which are wrong.

Two consequences worth knowing:

- The install is `--frozen-lockfile`, so if `package.json` and `pnpm-lock.yaml` disagree the container **refuses to start** with a message telling you to run `pnpm install` on the host. That is deliberate: booting with a guessed dependency tree is how the original bug hid for a whole session.
- The entrypoint also rebuilds `@toeic-pilot/shared`. The bind mount hides the `dist/` the image built, and `apps/web` imports the compiled output — so on a fresh clone with no host build there would be no `dist` at all.

**Do not run `pnpm dev` — or `pnpm build` — on the host while the `web` container is up.** `apps/web` is bind-mounted, so both write the same `apps/web/.next`, and a cache written by one confuses the other. `build` is the nastier of the two, and stopping the container first does **not** save you: the production artefacts it leaves behind (`BUILD_ID`, `prerender-manifest.json`, `required-server-files.json`) stay in `.next`, the dev server started afterwards reads the mixed cache, prints `✓ Ready in 292ms` exactly as it always does, and then hangs on every request without logging a single error — so the one output you would check to diagnose it looks entirely healthy. The fix is `rm -rf apps/web/.next`, then restart the container.

That matters most when reproducing the `web` CI job locally, because its last step *is* `pnpm --filter @toeic-pilot/web build`. Run that step inside a container, or delete `.next` immediately afterwards.

**`docker compose restart` does not re-read `.env`.** `env_file` is applied when a container is *created*, so `restart` brings the old environment back with it — the setting you just changed appears to have no effect, `docker compose config` shows the new value, and the container disagrees with it. Use `up -d` to recreate. Same shape as the `environment:`-overrides-`env_file` trap above, and it cost a debugging detour on the audio driver.

`api` runs `alembic upgrade head` via `docker/api-entrypoint.sh` before uvicorn binds (`RUN_MIGRATIONS=0` skips it). `web` waits for `api` to report healthy, and `api`'s healthcheck hits `/ready`, so nothing starts until Postgres is genuinely reachable. Source is bind-mounted for hot reload; only dependency-manifest changes need a rebuild.

## Architecture

**Request flow.** Next.js pages (`apps/web/src/app/**`) → `apiFetch()` (`apps/web/src/lib/api.ts`) → FastAPI routes (`apps/api/app/api/routes/*.py`), using paths and types from `@toeic-pilot/shared`. The frontend never hardcodes an API path or response shape.

**The shared contract is generated, not written.** `packages/shared/src/api-types.ts` and `packages/shared/openapi.json` are produced by `pnpm gen:api-types` from FastAPI's own OpenAPI schema. `src/index.ts` only re-exports friendly aliases (`UserPublic`, `TokenResponse`, …) plus the hand-maintained `API_ROUTES` map.

- **Never hand-edit `api-types.ts` or `openapi.json`.** Change the Pydantic schema, then regenerate and commit both files. The `contract` CI job regenerates and fails on any diff.
- `apps/web` imports the package's **compiled `dist/`**, not `src/`. A stale `dist` can satisfy imports and hide drift, which is why `prebuild` wipes it.

**Config.** `app/core/config.py` holds one `settings` singleton (`pydantic-settings`); add env-driven config there rather than reading `os.environ` around the codebase. `env_file` uses **absolute** paths (repo root, then `apps/api`) because a relative `.env` silently resolves against the CWD — which broke the documented dev flow. Real env vars still outrank both, which is how Compose injects values. `ENVIRONMENT=production` refuses to boot on the default `SECRET_KEY`.

**Auth.** JWT bearer tokens (`python-jose`); passwords hashed with the `bcrypt` library directly. `app/api/deps.py::get_current_user` resolves the token to a user; it parses `sub` as a UUID first, because comparing arbitrary text to a UUID column makes Postgres raise and surface as a 500.

**Changing a password ends the other sessions, and the mechanism is equality rather than recency.** Tokens carry a private `pwc` claim — the *generation* of the password, taken from `users.password_changed_at` — and `get_current_user` refuses any token whose generation is not the current one. The obvious design, "reject tokens issued before the change", cannot be made correct: `iat` has one-second resolution, so a token minted in the same second as the change is indistinguishable from one minted just before it, and an ordering test must either let that token through or reject the replacement token the change itself just issued. For the same reason the generation is measured in **microseconds**, not seconds — two changes inside one second would otherwise share a generation and leave the first one's token valid. No claim at all reads as generation zero, which is what lets this ship without signing out every existing session.

`POST /auth/password` therefore returns a **new token**, not a 204: it has just invalidated the one the caller used to make the request, and without a replacement the user is signed out at the moment they successfully changed their password. A wrong current password is **403, not 401** — the token is fine, the action is refused, and 401 would make the frontend treat it as an expired session and redirect to /login.

**bcrypt's 72-byte limit is enforced explicitly.** `app/core/security.py` raises `PasswordTooLongError` and `app/schemas/auth.py` turns it into a 422. The limit is measured in **bytes, not characters** — a 40-character Vietnamese password is 120 bytes. Do not "fix" this by truncating: older pins truncated silently, which meant only a prefix of the password ever authenticated. Existing `$2b$` hashes from the previous passlib stack still verify; `tests/test_security.py` pins a real one as a golden value.

**Database.** `app/core/database.py` exposes `engine` / `SessionLocal` / `Base` (SQLAlchemy 2.0 `Mapped[...]` style — follow `app/models/user.py`). Routes take a session via the `get_db` dependency. **Alembic owns the schema**; `metadata.create_all` runs only when `environment == "development"`. New models must be re-exported from `app/models/__init__.py` — that one package import is what `app/main.py`, `alembic/env.py` and `tests/conftest.py` all rely on to register tables on `Base.metadata`. A model missing from it produces "no such table" in tests and an empty autogenerate diff.

**`user_profile` is 1:1 with `users` and its row is created during registration, never lazily.** The primary key *is* the foreign key, which is what enforces the 1:1 rather than a convention someone has to remember. It is a separate table because `users` is loaded by `get_current_user` on every authenticated request and answers one question — who is this and what may they do — while display preferences and study goals change far more often and would put a migration on the authentication table every time the product grows a setting. Creating the row eagerly matters more than it looks: a 1:1 table whose row might be absent means a null check at every read site, and the one someone forgets is a 500 on a page that worked yesterday. `daily_new_limit` is NULL for "use the system default" rather than a copy of today's 20, because `SPEC-LEARNING-HUB.md` §5 says outright that number will move — copying it in would pin every existing learner to the old value on the day it changes, silently.

**`PATCH /profile` distinguishes an absent key from a null one**, via `model_dump(exclude_unset=True)`. Absent means leave it alone; null means clear it. A `value or existing` merge cannot tell them apart, and the failure is quiet: clearing an exam date returns 200 and changes nothing, so nobody finds out until they reload.

**The activity calendar is sent sparse, with the server's idea of "today".** `LearningStats.calendar` carries only days that had activity; the browser builds the 365-day grid from `today` and `window_days`. `today` comes from the server because it is *the learner's* today — computed in their profile timezone, the same one the streak uses. Letting the browser call `new Date()` instead puts the grid one column out of step with the streak whenever the browser's timezone differs from the profile's, and nothing reports it.

**Profile statistics are derived on every read** (`app/services/profile_stats.py`) — same rule as `StoryProgress` and `VocabularyProgress`. The streak is computed in the learner's own `timezone`, which is why that column exists and is NOT NULL: a day ends at 17:00 UTC in Hanoi, so counting in UTC breaks the streak of everyone who studies in the evening. `compute_streaks` is pure so the calendar arithmetic can be tested without a database.

**Domain model.** Designed in `planning/ADR-001-DATA-MODEL.md` and created by migration `003`; there are no endpoints over it yet. Shared column vocabulary (`PublishableMixin`, status/difficulty CHECK helpers) lives in `app/models/mixins.py`. Two shapes look wrong until you check the exam (ADR-001 §A2):

- `question.set_id` is **nullable** — only parts 3, 4, 6 and 7 group questions under a shared stimulus. A CHECK requires it for exactly those parts.
- `question.prompt_text` and `question_option.content` are **nullable** — part 2 prints nothing at all and has three options rather than four. Null is the correct value there, not missing data.

Audio hangs off two levels for the same reason: parts 1–2 on `question`, parts 3–4 on `question_set`.

`app/models/validators.py` holds the content rules no declarative constraint can express (ADR-001 §B4): at *least* one correct option, the per-part option count, `question.part` matching its set's part, and the printing rules. The partial unique index only rules out *more* than one correct answer — a question with none inserts cleanly and can never be answered correctly.

**Parts 1 and 2 print nothing.** ETS states it outright for both: the statements and responses are spoken only, never printed. Part 1's test book shows the photograph alone; part 2's shows nothing. So `prompt_text` and `question_option.content` are NULL for both — part 1 just also has an image and four options rather than three.

**Images (ADR-004).** `image_asset` mirrors `audio_asset` but is a separate table on purpose: merged, more than half the columns would always be NULL. `license`, `attribution` and `source_url` are NOT NULL because most openly-licensed photographs are CC-BY — usable only *with* credit — and storing the credit is not enough: any endpoint serving a Part 1 image must return it and the UI must render it. `app/content/images.py` fetches from a hand-curated spec file rather than a search API, because a photograph still needs a human to decide whether four statements can be written about it.

**Scoring (`app/services/scoring.py`).** The raw-to-scaled curve lives in `score_scale` / `score_conversion` rather than in code: TOEIC curves differ per form, and a scoring bug should be fixable by editing a row. Lookups **refuse to guess** — a missing conversion raises rather than interpolating, because a silently wrong score is stored permanently on the attempt and the learner cannot tell it is wrong. The seeded default is an approximation and says so in `source_note`; ETS publishes no official table.

**Dictation is graded twice, and the two graders must agree.** `apps/web/src/lib/dictation.ts` is a step-for-step port of `apps/api/app/services/dictation.py` — the client grades so feedback is instant, the server re-grades every submitted attempt, and the server's row is the one stored. Drift is worse than it looks: the client decides whether to say "đúng rồi" while the server decides whether the sentence counts as done, so the two can disagree about whether a learner just finished something. Nobody reports that; they assume they misread. Three things make the port non-obvious: Python's `\w` is Unicode and JavaScript's is ASCII (hence `\p{L}\p{N}_` with the `u` flag), the order is lowercase-then-strip, and the diff is `difflib.SequenceMatcher` — **not** an ordinary LCS, so a hand-rolled diff highlights different words. Change one file, change the other, and re-run the parity check.

**Dictation content is a four-level tree, and every level filters `published` independently.** `dictation_topic` → `dictation_section` → `dictation_story` → `dictation_item`, with `item.position` carrying the order inside a story. A draft story under a published section leaks if only the section is filtered, and nothing complains — the content looks entirely normal. `tests/test_dictation_tree.py` pins one case per level, including the non-obvious one: a *published* story under a *draft* topic must still 404.

**The tree lives on hyphenated paths (`/api/v1/dictation-topics`), not nested under `/dictation/`.** `GET /dictation/{item_id}` declares `item_id: uuid.UUID`, so `/dictation/topics` is captured by it and 422s trying to parse "topics" as a UUID. Declaring static routes before dynamic ones also works, but then declaration order becomes load-bearing and invisible. Same reasoning as the existing `/vocabulary-review/session`.

**Deleting a story needs its sentences detached first, and the reason is a schema contradiction.** The FK says `ON DELETE SET NULL`, but the database only nulls `story_id` and leaves `position` — which violates `ck_dictation_item_story_position`. The two fight, so without `_detach_items` **no story can be deleted at all**. The ORM side needs care too: `sections`/`stories` carry `cascade="all, delete-orphan"` because SQLAlchemy otherwise tries to null a NOT NULL parent FK, and `items` carries `passive_deletes=True` so the ORM keeps its hands off sentences that must survive.

**A sentence with attempts cannot be deleted, by design.** `dictation_attempt.item_id` is RESTRICT; the endpoint checks first and returns 409 pointing at `status='archived'` — the state `CONTENT_STATUSES` was built for. Deleting would orphan a learner's history.

An error that names a way out has to have that way out **reachable from where the user is standing**. This one shipped without it: the 409 said "set its status to archived" while the admin UI had no archive control anywhere, so every attempted sentence was a dead end — and with 32 of 35 sentences attempted, that was almost all of them. The Archive / Bỏ lưu trữ buttons now sit directly beside Delete, and the frontend translates this specific 409 rather than surfacing the raw English. Worth remembering when adding the next gate: a refusal is only finished when the alternative it names is one click away.

**Dictation voice is chosen per story, not per sentence** (`voice_for_dictation`). It keys off `story_id` when there is one, falling back to the item id for standalone sentences. Keying off the item id alone — which it did originally — narrates one continuous passage in four alternating accents. Note that changing this does **not** re-cast existing audio: `media_state` asks "was this clip made from this text", not "was it made under the current policy", so a story recorded before the fix keeps its mixed voices until its items are unlinked and backfilled again.

**Dictation progress counts completions, not scores, and `is_complete` is not `accuracy == 100`.** `accuracy` is `matched / expected`, so typing the whole sentence *and then more* still reads 100 — as does typing it twice. `is_complete` requires every diff token to be `match`: nothing missing, nothing extra. Progress counts that column; using accuracy would mark plainly-wrong submissions as done. The percentage is still computed and stored (history stays re-gradeable) but no longer appears in the UI: "89%" does not tell a learner whether to move on or listen again, and "đúng rồi" does.

**Story progress is derived, never stored.** It comes from `dictation_attempt` — `DISTINCT item_id WHERE is_complete`. A progress table written alongside would drift from the attempt history the first time an attempt is deleted, with nothing to detect it. Once complete, always complete: a later worse attempt does not un-finish a sentence, because having heard it is something that already happened.

**Every check is recorded now.** The old rule — only the first check counted — existed because progress was an average and re-typing a revealed answer would inflate it. With completion there is nothing to inflate, so the rule went, and with it the "Lần kiểm tra đầu tiên sẽ được ghi nhận" label that made learners hesitate before pressing a button they should press freely.

**`dictation_item.story_id` is nullable and `topic_id` still works.** Sentences that predate the tree keep functioning; they surface under `?standalone=true` and a "Câu lẻ" entry that disappears once everything is filed. Without that, upgrading would have silently made existing content unreachable.

**Words the learner has not reached are masked, and the boundary is not where you would first look for it.** `maskUnreached` hides trailing `missing` words as `*`, because otherwise checking after four of ten words prints the whole answer. The boundary is the **count of typed words** mapped onto positions in the transcript — *not* a position in the diff. The obvious rule ("hide everything after the learner's last contribution") is wrong: `SequenceMatcher` folds the whole tail into one `replace` block with every `missing` before the `extra`, so it hides nothing in the most common case of all, a partial answer whose last word is misspelled. Masking is display-only; `accuracy` still covers the whole sentence, which is what keeps the client's number equal to the server's.

**The transcript is sent to the browser on purpose.** `GET /api/v1/dictation/{id}` returns the answer key, because client-side grading needs it; the rationale and its limit are written on `DictationDetail.transcript` and pinned by a test that used to assert the opposite. Acceptable for self-study, **not** for anything scored competitively.

**Health vs readiness.** `/health` is liveness and deliberately checks nothing — a database outage must not get the container restarted. `/ready` queries Postgres and pings Redis, returning 503 when Postgres is down. Redis is a soft dependency everywhere: startup logs a warning and `/ready` reports `degraded` rather than failing.

**Logging.** `app/core/logging.py` provides a JSON formatter, a text formatter for local reading (`LOG_FORMAT`), and `RequestContextMiddleware`, which assigns or accepts an `X-Request-ID`, exposes it through a `ContextVar`, echoes it on the response, and logs one line per request. This exists now specifically so Phase 4's LLM calls are traceable from day one.

**Vector store.** pgvector is enabled by the initial migration but unused so far; it is there for Phase 4 RAG.

**Audio and the content pipeline.** Decisions live in `planning/PHASE2-AUDIO.md` Part A; read §A4 before changing anything here, because all four invariants fail silently. The shape:

- `app/core/media.py` — content-addressed naming, pure stdlib, imported by *both* sides. `source_hash` fingerprints the synthesis **input** (text | logical voice | engine | engine version), never the mp3 bytes: TTS is not byte-deterministic, so hashing output would break idempotency. `voice` is a **logical** name (`us_female_1`), never a provider id (`en-US-JennyNeural`) — that indirection is what kept the library intact when `en-AU-WilliamNeural` was renamed upstream.
- `app/models/audio.py` — `audio_asset`, deliberately independent of the domain schema. The dependency runs domain → asset. `source_text` is **not** the grading answer key; dictation grades against `dictation_item.transcript`.
- **A spec line has two shapes, and only one of them can express a conversation.** `{"text", "voice"}` (or `"voices"` to fan one text across accents) renders one clip; `{"turns": [{text, voice}, …], "gap_ms": N}` renders several turns joined into one file, which is what Parts 2 and 3 require. The hash for the second is `conversation_source_hash`, which fingerprints **the whole turn list in order** plus the gap — drop the order or the gap from it and a re-run silently "skips, already present" while the content has changed. Two behaviours surprise people, both measured and written up in `MEDIA-PIPELINE` §10.2: `gap_ms` is silence *added* to the ~1.1s edge-tts already pads each boundary with, and a clip whose turns mix accents must **declare** `"accent"` because the column holds exactly one value.
- `app/content/**` — the offline pipeline, behind the optional `content` extra. `generate` synthesises and writes `content/manifest/audio_assets.jsonl`; `seed` reads that manifest and upserts rows by `source_hash`. Generation happens **offline**, so an edge-tts outage blocks new content rather than breaking what already exists.
- The manifest is committed; the mp3s under `apps/api/media/` are gitignored. `generate` therefore skips only when the manifest entry *and* the file both exist — otherwise a fresh clone would never re-render them.
- Serving is a string join: `{audio_public_base_url}/{storage_key}`. The API never calls the object store at request time, and audio must **never** be proxied through FastAPI — that loses range requests and burns the API's bandwidth. `/media` is mounted only when `environment == "development"`.

  Read that rule as narrowly as it was meant (ADR-006 §2.9): it bans an endpoint that *re-serves bytes fetched from the object store*. It does **not** ban the `/media` static mount — Starlette's `FileResponse` sets `accept-ranges`, parses `Range`, and returns 206/416, so a static mount loses nothing. What is left is a bandwidth argument, which is about scale rather than correctness. Do not let the rule talk you out of a legitimate option.

- **The provider is a config value, not a code branch** (ADR-006 §2.8). One `s3` driver covers Supabase, B2, R2, DO Spaces, Wasabi and MinIO; `S3_ENDPOINT_URL` decides which. Two settings are load-bearing and fail misleadingly: boto3 defaults to **virtual-host addressing**, which turns the bucket into a subdomain and surfaces as a *DNS* failure rather than a config one, and Supabase requires **SigV4**. `tests/test_storage.py` pins the addressing style for exactly that reason.
- **Generated media never touches the upload path.** `app/content/push_media.py` syncs it — a deploy problem — routing each kind to its own provider (images to Cloudinary, audio to S3). The ticket/verify flow of §2.3 exists for bytes arriving from a machine we do not control (§2.8a).
- **Images live only on Cloudinary, including the ones `images.py` fetches** (ADR-006 §2.8c). Fetching to local disk and seeding a row was only half a path: `public_url` then built a Cloudinary URL for a file never uploaded there, and Part 1 images 404'd silently for sprints because nothing rendered them yet. `CloudinaryDriver.upload_file` closes it, and — like `LocalDiskDriver.write` — stays **off** the `StorageDriver` protocol so a request handler cannot reach it. Both upload paths share `_signed_params`, so the browser and the offline tool cannot drift into producing differently-transformed objects.

**A recording corresponds to its *script*, and staleness is a fingerprint comparison — never a pair of timestamps.** `question.audio_script_hash` / `question_set.audio_script_hash` record `script_fingerprint(...)` at the moment audio is attached; `_may_be_stale` recomputes it and compares. The obvious design — is `updated_at` later than `audio_attached_at`? — cannot be made correct, and both reasons only surface when you run it: `audio_attached_at` is written by Python's clock while `updated_at` comes from the database's `func.now()`, so the comparison depends on two clocks agreeing; and SQLite's `CURRENT_TIMESTAMP` has one-second resolution, so an edit in the same second as the attach is silent. Same shape as the `pwc` claim's `iat` problem. The fingerprint is also *more* accurate: it fires only when the thing the recording corresponds to actually changed, so fixing a comma in an explanation no longer cries wolf — and restoring the script to exactly what it was turns the warning back off, which no timestamp pair can do.

**Editing a set's script sends the set *and every question under it* back to draft.** The publish gate inspects questions one at a time, so demoting only the set leaves its questions published inside a released test, playing a recording of the old script. `PATCH /admin/question-sets/{id}` exists because without it Parts 3 and 4 had no way to change a script at all — one wrong word meant deleting the group and re-pasting — which also meant the stale warning had nothing that could ever trigger it. Part 1/2 scripts live on the question and go through `QuestionEdit`; sending `audio_script` to a Part 3/4 question is refused with a pointer to the set.

**Authoring-time validation is not publish-time validation.** `_authoring_problems` drops the "missing audio"/"missing photograph" complaints, and both `commit_part` and `edit_question` use it. Running the full `validate_question` on edit means every Part 1–4 question is invalid until its recording exists, so a typo in a script cannot be fixed until after it has been recorded — i.e. it has to be recorded twice. The real gate is still publish.

**The TTS worker is a separate image, and that separation is the point.** `docker/worker.Dockerfile` carries ffmpeg and the `content` extra; `api.Dockerfile` carries neither. Merging them would not break anything on the day it happened — it would break on the day someone noticed `app.content` was already installed and imported it into a request handler "since it's right there", putting edge-tts, ffmpeg and a network call on the serving path. A separate image gives A4.1 a physical shape instead of a convention someone has to remember.

**The generate-audio button rings a doorbell; it does not generate audio.** `POST /admin/media/audio/requests` publishes to a Redis channel and returns **202**, never 200 — the API cannot synthesise (A4.1). Nothing is written to any table: the queue is still the *question* "what content is missing audio or no longer matches its script", so pressing the button ten times does not create ten jobs. Redis being down still returns 202 with `queued: false`, because the worker's 300-second sweep finds exactly the same work — reporting failure would make an editor retry something that was already going to run. Pub/sub is deliberate: a message published while the worker is down is lost, and that is fine, because it carries no information.

**`AudioState.EXTERNAL` is what stops the worker overwriting a human recording.** An uploaded clip's `source_hash` fingerprints a random id, so it can never match the text — under the older `is not CURRENT` test it fell straight into the regenerate branch and a human voice was silently replaced by TTS, discoverable only by pressing play. `_REGENERATE` is `(MISSING, STALE)` and nothing else. This applied to vocabulary and dictation too, not just questions.

**`AudioFactory` takes `duration_probe` and `joiner`**, the same two seams `generate()` already had, for the same reason: mutagen needs a real mp3 and `join_turns` needs ffmpeg, while what is worth testing is the skip/generate decision and the row that follows it. Without them no branch of that class could run outside a fully-provisioned machine.

**Nothing reachable from `app/main.py` may import `app.content`.** The production image is built `--no-dev` without the `content` extra, so a leak breaks container startup rather than the build. `tests/test_content_isolation.py` catches it in a subprocess in under a second; the `docker` CI job catches it the slow way. Shared code belongs in `app/core/`.

**Monorepo wiring.** pnpm workspaces + Turborepo for JS/TS. `apps/api` is a separate `uv` project outside the turbo graph, so cross-cutting scripts (`scripts/generate-api-types.sh`) drive both toolchains.

## Testing conventions

**Test the flows that matter, and stop.** The bar for a new test is that a plausible future change would break it *and* that breakage would matter. Tests that exist to raise a count, restate a type signature, or pin a detail nobody would ever change are cost with no return: they slow the suite, they have to be updated by hand every time the code moves, and a wall of green from tests that assert nothing is worse than a smaller suite you trust.

**Do not build elaborate scaffolding to make a test possible.** Hand-rolled fakes of third-party services, fixtures that mutate global settings, generated binary fixtures, multi-step orchestration to reach one assertion — when a test needs that much machinery, the machinery becomes the thing being maintained, and it drifts from the real system it is imitating without anything reporting it. Prefer the version of the test that fits in one screen. If a flow can only be checked with real credentials against a real service, **run it once by hand and write down what you learned** — a note in the ADR outlives a fragile test that nobody dares run.

A short checklist before adding one:

- Would this fail for a *real* defect, or only for a rewrite that changes nothing?
- Is the setup longer than the assertion? That is usually a design smell in the code, not a reason for a bigger fixture.
- Is a nearby test already covering this path? Extend it instead of adding a sibling.


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
- **`<dialog>`'s `cancel` event does not bubble, so React's `onCancel` prop never fires.** React attaches most handlers at the root container and dispatches by bubbling; `cancel` (and `close`) do not bubble, so `onCancel={...}` type-checks, compiles, and silently does nothing. The failure is nasty rather than loud: Escape closes the dialog at the browser level while React state still believes it is open, so the next click on Edit opens nothing at all. `components/modal.tsx` attaches both listeners with `addEventListener` in an effect instead. Do the same for any other non-bubbling event.
- **A `Field` whose hint runs to a different number of lines than its neighbour's misaligns the whole grid row.** Block layout puts each control directly under its own hint, so a one-line hint beside a two-line hint leaves the two inputs at different heights — and the offset changes with viewport width, which makes it read as a random glitch. `Field` is a flex column with `mt-auto` on the control so grid rows line up at the bottom; in a single column there is no spare height and it does nothing.
- Empty directories survive a `git` revert. An `apps/web/src/app/learning/**` skeleton outlived a reverted Phase 2 attempt for exactly this reason and went unnoticed for two sprints (it has since been deleted). Next.js only routes a directory that contains a `page.tsx`, so such leftovers are inert — and therefore invisible until someone looks.
- Prettier deliberately ignores `*.md` and `planning/**` so prose edits stay out of code diffs.
- **`alembic/` is not linted or type-checked.** CI runs `ruff check app tests` and mypy over `app` only, so migrations follow `001`'s existing style (`typing.Union`, `typing.Sequence`) rather than the modern syntax ruff would demand elsewhere. `alembic/script.py.mako` was missing until Sprint 2, which meant the documented `alembic revision --autogenerate` had never actually been able to write a file.
- **`tests/test_concurrency.py` runs `create_all` against the real dev Postgres.** After a test run with Postgres up, the dev database holds every table in `Base.metadata` — so `alembic revision --autogenerate` compares against a schema that already matches and emits an *empty* migration. Reset before generating: `psql -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'` then `alembic upgrade head`.
- **Editing text silently invalidates its audio, and the publish gate is what catches it.** `vocabulary_audio` records no link to the *version* of the text a clip was made from, so renaming a headword leaves a recording of the old word in place. `app/services/media_state.py` detects it by recomputing the hash from the current text and comparing against `audio_asset.source_hash` — no extra column, purely a dividend of hashing the input (A4.2). For dictation it matters more: the transcript is the answer key, so a stale clip grades learners on a sentence they were never played.
- **The dev `api` container recreates the schema on every reload.** It runs uvicorn with `--reload` and `environment=development`, so editing anything under `app/` restarts it and runs `create_all` against the dev Postgres — which will rebuild the tables you just dropped to generate a migration. `docker compose stop api` before doing migration work. This bites hardest when a migration adds **both** a table and a column: `create_all` creates the new table but cannot add a column to an existing one, so `alembic upgrade` then dies on `relation "x" already exists` while the new column is still missing — a half-applied schema that neither tool will finish. Drop the table it created, then let Alembic run. The same stale-schema problem hits a scratch test database that has been used before: recreate `toeic_test` rather than debugging it, since CI gets a fresh Postgres every run and will not reproduce it.
- **Public archives rate-limit and require a User-Agent.** Wikimedia returns 403 to httpx's default UA and 429 partway through a bulk run. `app/content/images.py` sends an identifying UA and paces itself; a failed image is reported and skipped rather than aborting the run, so the successes survive and the next run picks up only what is missing.
- **edge-tts voice ids drift.** They are provider ids, not ours, and Microsoft retires them without notice. `tests/test_tts_external.py` checks every `LOGICAL_VOICES` entry against the live catalogue — run it (`TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external`) before any bulk generation, because a stale id otherwise fails one clip at a time in the middle of a long run.
