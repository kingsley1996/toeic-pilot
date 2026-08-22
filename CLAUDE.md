# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TOEIC Pilot — an AI-powered TOEIC learning platform. Polyglot monorepo: FastAPI backend (`apps/api`), Next.js frontend (`apps/web`), shared TS contract (`packages/shared`), Postgres + pgvector, Redis.

**`planning/PLAN.md` is the product spec and the source of truth for scope.** Work proceeds phase by phase; do not implement a later phase's features while an earlier one is open unless asked.

**`planning/ROADMAP.md` is the single tracker** — sprints, tasks, real status, and what each finished sprint actually cost. Read it first; update it when you finish something. Nothing else in `planning/` carries status.

The rest carry decisions and their reasoning:

- **`planning/ADR-001-DATA-MODEL.md`** — the domain schema and why it has the shape it has.
- **`planning/PHASE2-AUDIO.md`** — audio architecture (this is ADR-002); Part A is the durable record, Part B the implementation log.
- **`planning/ADR-003-AI-LAYER.md`** — the AI layer's three one-way decisions: two providers routed by cost, an **offline open-source embedding model at `vector(1024)`**, and a **thin non-RAG slice first**. The last one is driven by a measured fact rather than a preference — the project has **34 questions with an explanation** out of 55, so retrieval still has almost nothing to retrieve and §7e's "eval alongside the feature" cannot conclude anything. RAG is blocked by *content*, not by engineering, and §3.3 writes the unblocking threshold as a number. Read §3.4 before adding any LLM call: the token budget **fails closed**, opposite to the auth rate limiter, because there Redis is the only thing between an account and your bill.
- **`planning/toeic_question_label_taxonomy.md`** — the question label taxonomy, **hand-maintained and the source of truth**. `app/services/labels.py` is *generated* from it, and `tests/test_labels.py` re-parses the document to compare code, Vietnamese label and part list one by one. Without that test a label added to the document but not regenerated is simultaneously "decided" and "rejected by the system".
- **`planning/AI-ENGINEERING-PLAN.md`** — how the AI layer earns `PLAN.md`'s claim of "production AI engineering rather than an LLM chatbot". Its load-bearing section is §3: **an explanation of a question is the same for every learner**, so the common path is *precomputed offline* through the existing `app/content/` shape and costs nothing per request — 600 explanations generated once, not 600 per learner. §2 is the other half and matters more than it looks: scoring, SM-2, score conversion and dictation diffing must **never** touch an LLM, because they are exact today and would become approximate. Read §0 before planning any AI feature — `target_score` is filled on **3 of 53** profiles, so the planner still has no input. Its §9b KPI thresholds were written for a provisional 8-tag set and **no longer match the code**: the real taxonomy has 72 codes, so "smallest tag ≥5%" would flag everything. Accuracy is now measured per facet.
- **`planning/ADR-004-IMAGES.md`** — photographs for Part 1, licensing, and the fetch pipeline.
- **`planning/ADR-006-MEDIA-UPLOAD.md`** — how bytes get to a provider: the ticket → direct POST → confirm flow, why one `s3` driver covers six vendors, and why nothing reachable from a request handler may upload.
- **`planning/SPEC-AI-COACH.md`** — the coach's provisional defaults, in the same "built to be changed" spirit as `SPEC-LEARNING-HUB.md`.
- **`planning/ADR-007-TEST-AUTHORING.md`** — how a TOEIC test gets into the system: the audio script lives on the question, not in a spec file beside it (which is what kills the `LIKE 'prefix%'` lookup `seed_demo_test.py` still uses), paste-then-form authoring, canonical question numbers stored rather than derived, and audio generation reached by a Redis doorbell over a query-shaped work queue.
- **`planning/ADR-005-CONTENT-TOOLING.md`** — the admin UI for importing past papers: why a custom admin rather than a headless CMS, why paste-and-parse, and why parse never writes to the database.
- **`planning/REVIEW-OPUS.md`** and **`planning/qwen3p8-review.md`** — two engineering reviews, dated 2026-08-08 and 2026-08-16. Snapshots, not trackers: they are pinned to the commit they were written against and are not updated. `REVIEW-OPUS` still has open items; `qwen3p8-review` has none. Both are superseded as a plan by `ROADMAP.md`.

Two descriptions of *current behaviour* rather than of decisions:

- **`planning/ARCHITECTURE.md`** — what the system is made of right now: components, routers, services, file map, and the last verification run. Read it for orientation; `ROADMAP.md` still owns status.
- **`planning/MEDIA-PIPELINE.md`** — how audio and images actually work end to end today, plus an honest strengths/weaknesses list. Read §10 before extending either pipeline: **§10.3 (images are not reproducible) is a real defect**, not a known limitation. §10.1 and §10.2 were too and are now fixed — §10.1 by `app/services/media_state.py`, §10.2 by `app/content/audio_join.py`.

- **`planning/DESIGN-SYSTEM.md`** — the UI design system, **implemented across all of `apps/web`**: contrast-verified colour tokens for light and dark, the three-state theme switch, type (Archivo / Be Vietnam Pro / IBM Plex Mono, all with the `vietnamese` subset), the four-accent categorical scale, Lucide icon rules, component specs. Three rules there are load-bearing and fail quietly: **no `box-shadow`**, **one 4px radius** (the Tailwind scale is replaced, so `rounded-lg` emits nothing), and **`rule-strong` for component boundaries** — `rule` is decorative and does not meet the 3:1 that WCAG 1.4.11 requires of an input border.

One plan that is half built:

- **`planning/USER-ROAD.md`** — level, badges, avatar frames, XP and daily tasks. **Slices 1 to 3 are built** (ledger, level, daily tasks, and badges), and every number in them is now **admin-editable configuration** rather than a constant (ROADMAP §4w). The avatar-frame *rendering* is not built; neither is `streak_bonus`. ROADMAP §4v carries the status. Read §2.1 before touching it: XP is an append-only `xp_event` ledger rather than a counter on `user_profile`, specifically so that it stays *history* under the rule `profile_stats.py` states, and so that retuning the XP formula later cannot cost anyone a level they already have.

One runbook rather than a decision record:

- **`planning/import_media.md`** — how to get audio and images you already have onto a pasted test: directory layout, what the number in a filename means under each `--match` mode, the per-part counts, and the exact commands. Read §2 before renaming anything; the naming rules exist because two plausible readings of a filename both match *successfully* and put the media on the wrong question.

And one provisional spec:

- **`planning/SPEC-LEARNING-HUB.md`** — the defaults the Learning Hub was built to (SM-2 grades, session limits, dictation grading). Explicitly built to be changed after real use; its §5 lists what will probably need to move.

### Current state (2026-08-21)

Auth and the scaffolding under it are done and hardened. Every P0 and every P1 from `planning/REVIEW-OPUS.md` is now closed except **branch protection**, which needs repo-admin rights — see the status note at the top of that file. The one deliberate exception is P1-7b (httpOnly cookies), deferred with a written reason rather than pending.

**The media pipelines are built** — `PHASE2-AUDIO.md` (audio, offline TTS in four accents) and `ADR-004-IMAGES.md` (Part 1 photographs, fetched and normalised, licence and attribution required). Both sit behind the optional `content` extra and neither may be imported by the API. `planning/MEDIA-PIPELINE.md` describes how they actually behave, including two real defects still open in §10.

**The domain schema is designed and migrated** — `ADR-001-DATA-MODEL.md`, starting at migration `003`. **38 tables** as of `029` (measured off `Base.metadata`, 2026-08-21) cover vocabulary (with SM-2 spaced repetition and per-topic learning sessions), dictation and its four-level tree, questions/options/sets and their label taxonomy, practice tests, attempts, media assets, roles, score conversion, and the AI coach. `study_plan`, `learning_memory` and `knowledge_chunk` still exist on paper only, because their vector dimensions depend on an embedding model ADR-003 has not chosen.

**Vocabulary and dictation work end to end.** An editor pastes rows, they land as `draft`, `app/content/backfill_audio.py` synthesises the audio out of band, publishing is refused until every clip matches its text, and a learner reviews with SM-2 flashcards and works through dictation. Verified through the running Docker stack, not just in tests.

**Dictation has its own four-level tree and grades in the browser.** `dictation_topic → dictation_section → dictation_story → dictation_item`, with `item.position` ordering the sentences inside a story and progress tracked per story. The whole of `apps/web/src/lib/dictation.ts` is a step-for-step port of `app/services/dictation.py`; the server still re-grades every submission and its number is the one stored. The UI shows no percentage at all — only "đúng rồi / chưa đúng" and "3/6 câu đã xong".

**Vocabulary is learned topic by topic, and the learner's place in a topic lives on the server** (`vocabulary_topic_session`, migration `026`; ROADMAP §4e). Three modules — typing, flashcard, quiz — share one board and one self-grading step; see "Learning vocabulary by topic" below for the four invariants that fail quietly.

Three things to know before extending it:

- **`app/services/`** holds the logic that is not HTTP: `srs.py` (SM-2, pure arithmetic), `dictation.py` (normalise + `SequenceMatcher` diff), `media_state.py` (is this clip still the right one?), `content_import.py` (paste parsers), `scoring.py` (raw → scaled). All pure enough to test without a session.
- **`require_role` is a dependency, never an in-body check** — a check in the handler is the one someone forgets to copy into the next route, and the failure mode is an admin endpoint open to every learner. Every admin endpoint has a test asserting a learner gets 403.
- **The API cannot generate audio.** It cannot even import the TTS pipeline (A4.1), and synchronous synthesis would drag in a job queue that A2.5 deliberately avoided. `backfill_audio` runs out of band and its work queue is a *query* — "content whose audio is missing or no longer matches its text" — so there is no queue table, no retry state, and re-running simply finds less to do.

**Content has caught up in two areas and not in the third.** Vocabulary and dictation now run on real material — **303 words across 7 topics** and 15 dictation sentences, with **2 506 audio clips** in `audio_asset` and a committed manifest of 2 470 lines. Practice tests have not: **55 questions across 2 papers, 34 of them with an explanation**, which is why `ADR-003` still refuses to build RAG. Authoring papers is the real remaining work, and it is why the admin tooling came first.

**TOEIC Practice is partly built** — attempts run end to end (start, save an answer, flag, submit, score); the exam runner UI is not written. The old blocker is gone: the pipeline **can** now produce a multi-voice clip (`MEDIA-PIPELINE.md` §10.2, `app/content/audio_join.py`), so Part 2 (question in one voice, three responses in another) and Part 3 (a two-to-three-speaker conversation, the largest part at 39 questions) have a way to get audio. Two things about it fail quietly and are written up in §10.2: **`gap_ms` is silence *added* to the ~1.1s edge-tts pads each turn boundary with**, and **turns that mix accents must declare `"accent"`** rather than have one picked for them. Real TOEIC papers are ETS copyright, and ETS licenses electronic use per year through its general counsel — `question.source` is NOT NULL precisely so provenance is answered per row: `original` means written to the format (formats are not copyrightable, specific text is), `licensed` means permission actually obtained. **Do not default that field anywhere in code or UI.**

**The frontend has a design system, not per-page styling.** `src/components/ui.tsx` holds the primitives, colours come from CSS variables in `globals.css` (so light and dark are one definition rather than a `dark:` twin on every element), and `src/lib/session.tsx` resolves who is signed in *once* for the whole app. Three things follow from that and are easy to undo by accident:

- **Auth has three states, not two.** `loading` is distinct from `anonymous`, because localStorage does not exist during the server render. Collapsing them is what made the old header offer "Log in" to people who were already signed in, and a `? :` on `status === "authenticated"` reintroduces it — the else branch fires while still loading.
- **`useRequireSession({ canEdit: true })` redirects rather than showing a 403.** Someone who never had access should not be told they were refused. The server still enforces every boundary through `require_role`; this only decides what is worth rendering.
- **`status` in the session is derived, not stored.** Writing it from an effect cascades renders and lets it drift out of step with the token it describes. The `react-hooks/set-state-in-effect` lint rule enforces this and will reject the shortcut.

**The learner's home is `/dashboard`; everything they study is under `/learn/**`.** Login, registration and `useRequireSession`'s refusal path all land on `/dashboard`, and `/learn` is a server redirect kept because it was the destination for many sprints and is in people's history and bookmarks. Only the hub moved — `/learn/vocabulary`, `/learn/dictation`, `/learn/tests`, `/learn/review`, `/learn/typing` and `/learn/attempts` keep their paths, because a dashboard and a place to study are different things and `/dashboard/vocabulary` would name the second one wrongly.

**One shell, two sets of links.** `src/components/shell.tsx` holds both layouts and both areas use them: `TopBarShell` for the three pages *outside* the app (`/`, `/login`, `/register`) and `SidebarShell` for everything else, `/admin/**` included. Which one renders is decided by **pathname, never by session status** — status only resolves after JS runs, so choosing on it builds one layout and then swaps to the other in front of the user, the layout-shaped version of the three-state trap. The *links* stay separate per area, because merging a learner's nav with an editor's erases the line between studying and editing what others will study. Below `lg` the sidebar becomes a drawer built from the same `SidebarContent`; a hand-written mobile menu is always the one that gets forgotten when a link is added.

Identity and logout live at the **bottom of the sidebar**, not behind a dropdown — a sidebar has the height for two visible rows and a 4rem header does not, which is why the old design had to hide them behind a click. `SessionControls`/`UserMenu` survive for the three top-bar pages only; delete them and a signed-in visitor on the landing page has no way to reach their profile or sign out without first re-entering the app.

Three consequences, one of which is silent:

- **The logo always points at `/`, even when signed in.** It used to point at the hub; that was reverted deliberately (ROADMAP §4f), so do not "fix" it back. The way home is the first nav item, which is always visible to a signed-in user.
- **`activeHref` matches on path prefixes, so a nav item whose siblings live elsewhere needs `NavItem.covers`.** `/learn/review`, `/learn/typing` and `/learn/attempts` are modes opened *from* the hub but no longer sit under its path, so prefix matching cannot reach them; without `covers` the whole nav bar goes dark on those pages while the page itself is perfectly correct — nobody calls that a bug, they just lose their place. `covers` participates in matching only; `activeHref` still returns the item's `href`.
- **A `display_name` is usually NULL, so `name ?? email` printed above `email` renders the same string twice.** The old dropdown hid this because it only opened on a click; a sidebar shows it permanently, where it reads as broken data rather than as an identity block. The second line renders only when there is a distinct display name.

**The dashboard reads its numbers off `/vocabulary-progress` and `/profile/stats`, and two of its display rules exist because real numbers broke the naive version.** Its vocabulary block was rebuilt from a reference design in `planning/improve-ui/`; ROADMAP §4h records which parts of that design were deliberately not built and why — an accuracy figure needs a correct/incorrect tally no endpoint returns, and inventing one would show a number that looks measured and is not. The "continue learning" entry was the other gap and is now filled by `GET /vocabulary-topic-sessions`, which lists a learner's saved boards newest-first without their `entry_ids` — that array is as long as the topic and only the study screen needs it. It renders only when an unfinished board exists; falling back to "the first collection" would point at somewhere the learner has never opened.

- **A proportional bar rounds small non-zero shares down to nothing, and then contradicts the figure printed beside it.** Two mastered words out of 303 is 0.66% — zero pixels — so the status bar said "nothing mastered" while the number under it said 2. Non-zero segments carry a 3px floor: three pixels cannot convey a ratio, but they get right the thing that matters more, whether there is any at all.
- **Never colour a zero.** Colour is a signal, so a green `0` under "Đã thuộc" reads as something completed. Tones apply only when the count is non-zero.

**XP is a ledger, and the daily cap is enforced on write.** `xp_event` is append-only, unique on `(user_id, source_type, source_id)`, and `level` is `level_from_xp(SUM(amount))` — there is no `level` column and no running total, so retuning the formula later cannot take a level away from someone who already has it. Four things about it fail quietly:

- **The cap trims the last award instead of dropping it.** Three points left and an activity worth five awards three. And **exceeding the cap never touches the activity itself** — SM-2, dictation progress and attempts are recorded exactly as before, they just stop producing `xp_event` rows. A gamification rule must never be able to change what was learned.
- **The cap is enforced when writing, never when reading.** Enforced at read time it becomes a formula, and changing the cap would rewrite the past — losing the one property the ledger exists for.
- **`GET /api/v1/daily-tasks` writes.** It grants the reward for a task finished since the last read, which is a deliberate exception to "GET does not change state": the alternative is recomputing three slots on every hot write path, or a "claim reward" button that adds a step to a feature that exists to remove steps. It is safe because `source_id` is a *deterministic* uuid built from (user, local day, slot), so the unique index refuses the second grant however many times it is called.
- **A daily task's target is a fixed number clamped by what exists, never the condition itself.** "Review everything that is due" reads correctly and breaks silently: the due count falls as you review, so the bar advances and then retreats, and under some SM-2 schedules the task can never close. The moving number is the *clamp*, not the goal.

The dashboard block (`components/daily-tasks.tsx`) reads daily-tasks **before** progression, not in parallel: the first call is what grants the XP, so reading them together can print the total from before the grant — the task closes and the number does not move, and it looks correct again after a reload. That ordering is correct by construction rather than covered by a test; `e2e/daily-tasks.spec.ts` was measured against the parallel version and stayed green, and its docstring says so.

**Frames and badges can carry their own artwork, stored as a raw key under `progression/` — no `image_asset` row.** That table's `license`, `attribution` and `source_url` are NOT NULL because borrowed photographs are mostly CC-BY; frame and badge art is the product's own, exactly like an avatar, which is why avatars store a raw key too. The separate prefix is what keeps a content-image cleanup from reaching them (ADR-006 §2.1).

There is no separate confirm step — the row's own `PATCH` is the confirm, and it checks two things. Without the prefix check it is a write-any-string endpoint: point a frame at a content image and the orphan sweep later deletes something in use. Without asking the provider, the UI shows a broken image until somebody notices, and nobody notices a frame. `image_storage_key: null` clears the art while an absent key leaves it alone (`exclude_unset`, same rule as `PATCH /profile`).

**An `admin` account wears the highest frame tier automatically** — chosen by the largest `min_level`, not by a hardcoded `"challenger"`, because the tier table is editable and a hardcoded code becomes a silent `None` the day someone renames it. The perk touches the frame and nothing else: level, XP and badges stay the account's real numbers, since inflating the level would also inflate the `level_*` badges that read it.

**Frame art is positioned with explicit `top/left: -25%` and `width/height: 150%`, never with utility classes.** Two attempts failed there, both compiling and linting clean: `-inset-[25%]` emits no CSS at all (a leading minus on an arbitrary value is not valid syntax), and setting all four offsets while leaving `width:auto` does not help either, because for a replaced element `auto` resolves to the image's intrinsic size rather than stretching to the offsets. Both produced a 512px image spilling across the page. `/admin/progression/preview` exists to catch exactly this: it renders every tier through the real `Avatar` at three sizes on three surfaces, because no terminal check can see a frame sitting wrong.

Art wins over the token or the icon, but the token still travels: `tone` renders instantly while the image is still loading. An **unearned** badge shows the same art greyed out rather than falling back to its Lucide icon — swapping the picture at the moment of earning it means the learner does not recognise what they just got as the thing they had been looking at.

**Every number in the progression system is a row, not a constant** (`progression_setting`, `daily_task_slot`, `level_tier`, `frame_tier`, `badge_rule`), edited at `/admin/progression` behind `require_role("admin")` — *not* `editor`, because setting the scale for every account is an operational power rather than an editorial one. Three properties of the underlying design are what make handing it over safe, and each fails silently if a later change gives it up:

- **The ledger makes XP rates safe to edit.** Each `xp_event` stores the amount granted at the time, so lowering a rate today never claws back what someone earned. This was an argument in USER-ROAD §2.1; it is now the precondition for the feature.
- **Level never drops.** `user_profile.level_reached` is a high-water mark and the displayed level is `max(computed from today's table, mark)`. Raising the curve slows new learners without taking a level from anyone who reached it. That column is not a counter running beside history — it records something that happened, like `xp_event`.
- **A daily-task slot is a row with a durable uuid**, and that uuid feeds `xp_event.source_id`. Renaming a slot, moving its target or changing its reward cannot turn a paid day into an unpaid one. Deleting and recreating "the same" slot can — a new row is a new uuid — so the UI offers *disable* and a test pins the property.

Four sets stay closed, and they are the real boundary between data and code: a slot's `kind` and a badge's `metric` (each is a real query), a badge's `icon` (the frontend must know how to draw it), and a frame's `tone` (design-system tokens only — a free hex field is the shortest path to a frame that is invisible in dark mode, where nobody checks before saving). `BadgeCode` used to be a closed union so `tsc` caught a badge with no label; `code` is data now, which trades that check for adding a badge without a deploy. `icon` stays a union for exactly that reason.

**Defaults are seeded lazily on first read, never in the migration.** One source of truth in `app/models/progression.py`, same shape as `backdrop_setting`. It follows that **an empty table means "never configured", not "deliberately empty"** — delete every slot and the next read seeds the three defaults back. Disable instead.

**The level table is validated as a block** (`PUT /admin/progression/levels`): level 1 at 0 XP, no gaps, strictly climbing. A table that dips makes the lookup stop at the wrong level, and since `level_reached` only rises, a wrong mark written in that window is permanent. Changing the curve parameters deliberately does **not** regenerate the table — the rows are the truth and may have been hand-edited; regeneration is a separate button that says it overwrites.

**Badges are derived from learning history, not from the XP ledger — which is why old accounts need no backfill.** `user_badge` does not decide who has what; it stores the two things history cannot state on its own: when the system *first saw* the badge, and whether the learner has seen the notice. Four consequences:

- **The three `level_*` badges are the deliberate exception**, because they read XP. Someone who has already learned 300 words sees the "300 words" badge immediately **while still at level 1** — XP measures activity since launch, badges record lifetime achievement. The badges page says this out loud; without the sentence it reads as a bug.
- **Streak badges use `longest_streak`, never `current_streak`.** A badge that disappears because you skipped today punishes a day off and teaches people the system takes back what it gave.
- **The red dot clears when the badges page is opened, not when the dashboard notice scrolls past**, and `POST /progression/badges/seen` fires *after* the page has captured which ones were new — reversing that order sends the learner to a page with nothing new on it.
- **`mark_seen` flushes explicitly**, because sessions run `autoflush=False`: a second read inside the same transaction otherwise still sees `seen_at IS NULL` and marks them again. The rows end up correct after the commit, so the bug shows up only in a count.

**A negative Playwright assertion needs an anchor, or it passes on an unloaded page.** `toHaveCount(0)` is satisfied instantly before any data arrives, so `e2e/badges.spec.ts` stayed green with the "mark as seen" call deleted entirely. Wait for something that *is* present first — rendered from the same fetch — and only then assert the absence.

**Logging out revokes the token, and the mechanism is per-session rather than per-account.**
Tokens carry a `jti`; `POST /auth/logout` writes it to a Redis denylist with a TTL equal
to the token's own remaining life, and `get_current_user` refuses anything on the list.
This is the half of P1-7 that was real: before it, "Đăng xuất" only cleared
`localStorage`, so the token stayed valid for its full seven days — a shared computer or
a restored browser session walked straight back in while the UI said otherwise. `pwc`
could not cover this, because it is a per-account *generation* and can only express
"revoke everything", which is the wrong tool for leaving one machine.

Three parts of it fail quietly if changed:

- **The denylist fails open.** A Redis outage means revoked tokens work again; failing
  closed would mean *nobody* works, turning a soft dependency hard on the hottest path
  there is. Same trade as `rate_limit_anonymous`, opposite to `rate_limit` — there Redis
  is the only thing between an account and a bill.
- **A token with no `jti` is allowed through**, exactly as a missing `pwc` reads as
  generation zero. That is what let this ship without signing out every live session.
- **`/auth/logout` always returns 204**, including when Redis is down. A 503 would leave
  the browser holding a token and the UI holding a signed-in user — the state they just
  asked to leave. The client clears its own token unconditionally; the denylist is the
  second layer, for copies of the token this browser cannot reach.

The other half — httpOnly cookies and refresh tokens — is **deferred with a written
reason** rather than pending: `ROADMAP.md` P1-7b. Short version: cookies exist to survive
XSS, this app has no third-party script and one `dangerouslySetInnerHTML` rendering a
constant, and cookies would introduce CSRF in exchange. **Add any third-party script and
that reasoning expires.**

Still open: branch protection on `main` (needs repo-admin rights), and the token in `localStorage` (P1-7b, deferred above with its reasoning).

**Petland is a self-contained corner, and its layers are enforced by a script rather than by convention.** `apps/web/scripts/check-petland-layers.mjs` fails the build if the wrong file learns the wrong thing, because a single stray import is enough to make "change the mascot" or "change the scene" turn into a search:

- **`petland-sprite.ts` is the only file that knows a `/mascots/` path**, and `petland.tsx` the only one that knows the landscape path.
- **`petland-ui.tsx` may not import the sprite, the scene, or the fx layer.** The interactive controls must survive both a new mascot and a new scene; anything they need comes in as props, which is what the `leading` slot is for.
- **`petland-pet.ts` may not import React.** Needs and actions are arithmetic.

Three numbers on a mascot — `cell`, `footY`, `anchorX` — are **measured by `scripts/pack-pet.mjs` and printed for you to copy**, never chosen by eye. `check-petland-fit.mjs` compares them exactly (`y1 === FOOT_Y - 1`) and walks every frame of every mascot along 241 samples of the path, both facings, at the top of the jump. A few pixels out and the pet floats or sinks, uniformly enough to look like a layout choice rather than a bug.

**The mascot list lives in the API** (`app/schemas/profile.py::PetId`), even though the art lives in the front end. Declared there it travels through OpenAPI into a TypeScript union, so `Record<MascotId, Mascot>` missing a mascot is a `tsc` error rather than a runtime `undefined`. Add a mascot API-side first, regenerate the contract, then add the registry row — the other order does not compile.

**Inside the panel the mascot is read through a ref, not a closure.** The `requestAnimationFrame` loop has its own dependency list and does not rebuild when the mascot changes, so a closure holds the old one forever and the picker looks inert. Putting `mascot` in the deps also works, at the cost of tearing the loop down mid-run — `frameAcc` resets and the pet jumps at the moment the user clicks.

## Commands

### Python API (`apps/api`) — always `uv`, never `pip` or bare `python`

```bash
cd apps/api
uv sync --extra dev

uv run uvicorn app.main:app --reload --port 8000
uv sync --extra dev --extra content         # add the offline content pipeline

uv run pytest                              # 639 collected: 637 run + 2 `external` deselected
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
uv run python -m app.content.enrich_skills --dry-run       # gán nhãn: in ra, không ghi
uv run python -m app.content.enrich_skills --limit 5       # một lượt thử nhỏ (áp cho cả set lẫn câu)
uv run python -m app.content.skilltag_worker --once        # worker gắn nhãn: một lượt rồi thoát
uv run python -m app.content.push_media [--dry-run]       # local media -> its provider (images: Cloudinary, audio: S3)
uv run python -m app.content.reconcile_media [--delete-rows]  # media nothing points at any more
# Bulk-attach audio/images you already have to a pasted test. Dry-run first.
uv run python -m app.content.import_media audio --test <slug> --dir <dir> --accent en-US --dry-run
uv run python -m app.content.import_media image --test <slug> --dir <dir> \
    --source-url ... --license ... --attribution ...
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
pnpm --filter @toeic-pilot/web exec tsc --noEmit   # eslint does NOT typecheck — see below
pnpm format / pnpm format:check            # prettier; markdown is excluded on purpose
pnpm gen:api-types                         # regenerate the shared contract — see below
pnpm --filter @toeic-pilot/web test:e2e    # Playwright — needs the docker stack up
pnpm --filter @toeic-pilot/web test:e2e:ui # same, with the inspector
```

### Full stack

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
docker compose -f docker/docker-compose.yml up postgres redis -d   # infra only
```

**`docker/web-entrypoint.sh` runs `pnpm install` before the dev server**, for the same reason `api-entrypoint.sh` runs Alembic before uvicorn: a container must not serve against a state it has not reconciled. Adding a JS dependency needs `up -d --build`, **not** `up -d`. The reason is a
detail of the mounts: compose bind-mounts `apps/web` and `packages/shared` from the
host but **not the repo root**, so `/app/pnpm-lock.yaml` is whatever the image was
built with while `apps/web/package.json` is live from the host. The entrypoint's
frozen-lockfile check therefore compares two files from *different* sources, and a
new dependency makes them disagree until the image is rebuilt. Once rebuilt, the
install costs ~2s on a warm volume.

That check fires late and looks like something else. A container running from before
the dependency was added never re-runs it, so the stack keeps working; the refusal
only appears at the next `restart`, pointing at a lockfile the host has had correct
all along. `@playwright/test` sat in exactly that state for a sprint.

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

**"Prints nothing" is spelled `None`, never `""`, and every layer must agree.** `validate_question` asks `is not None`, so an empty string reads as "printed, zero characters long" and is refused. The paste parser emitted `""` for a whole sprint — with a comment beside it claiming it emitted `None` — because `QuestionDraft.prompt_text` and `QuestionOptionDraft.content` were typed `str`, so the preview contract could not express the distinction at all. Every other layer (`QuestionPublic`, `QuestionAdmin`, `QuestionEdit`, `OptionPublic`) already had `str | None`; the draft was the one shape that lost it, and Part 1 and 2 could therefore never be committed.

Two things kept that alive. The parser had a test asserting `== ""` and the validator had a test asserting `is not None`; **each half was green against its own test and no test crossed the boundary**. And the admin editor sent `prompt_text: ""` on every save, so even a hand-fixed row could not be edited afterwards — for unprinted parts it now omits the key entirely, which is what `exclude_unset` needs to tell "leave alone" from "clear". `tests/test_content_import.py::test_a_pasted_part_1_question_passes_the_gate_it_will_meet_at_commit` is the crossing test; it reproduces the original error message exactly when the fix is removed.

A NULL prompt is also **not** missing data in the UI. Rendering "thiếu đề bài" for a Part 1 question flags a perfectly correct row as broken, in the one view built for spotting broken rows.

**Lời thoại của Part 1 và 2 mang cả nhãn đáp án.** `spoken_option()` in `(A) …` vào từng lượt nói, vì người thi không đọc gì cả: một bản thu chỉ đọc bốn câu liền nhau không cho biết câu vừa nghe là (A) hay (C), và cả câu hỏi trở thành không trả lời được. Không phép kiểm nào trong hệ thống thấy điều đó — hàng dữ liệu đúng, `validate_question` trả OK, chỉ người bấm play mới biết. `option.spoken_text` vẫn giữ câu **trần**, không nhãn: nó trả lời "đáp án A nói gì", còn giao diện in nhãn ở chỗ khác. Đo được với edge-tts: `(A) ` thêm 0,41 giây, tức là chữ cái thật sự được đọc; giữ dấu ngoặc chứ không viết `A.` vì một chữ "A" đứng riêng trước câu tiếng Anh có thể bị đọc thành mạo từ *a*.

**Parts 1 and 2 print nothing.** ETS states it outright for both: the statements and responses are spoken only, never printed. Part 1's test book shows the photograph alone; part 2's shows nothing. So `prompt_text` and `question_option.content` are NULL for both — part 1 just also has an image and four options rather than three.

**Images (ADR-004).** `image_asset` mirrors `audio_asset` but is a separate table on purpose: merged, more than half the columns would always be NULL. `license`, `attribution` and `source_url` are NOT NULL because most openly-licensed photographs are CC-BY — usable only *with* credit — and storing the credit is not enough: any endpoint serving a Part 1 image must return it and the UI must render it. `app/content/images.py` fetches from a hand-curated spec file rather than a search API, because a photograph still needs a human to decide whether four statements can be written about it.

**Scoring (`app/services/scoring.py`).** The raw-to-scaled curve lives in `score_scale` / `score_conversion` rather than in code: TOEIC curves differ per form, and a scoring bug should be fixable by editing a row. Lookups **refuse to guess** — a missing conversion raises rather than interpolating, because a silently wrong score is stored permanently on the attempt and the learner cannot tell it is wrong. The seeded default is an approximation and says so in `source_note`; ETS publishes no official table.

### Learning vocabulary by topic

**The learner's place in a topic is server state, not browser state.** `vocabulary_topic_session` is keyed `(user_id, topic_id)` and holds `entry_ids` — the *order* of the round — plus `position`, the number of words already graded. It is not `localStorage` because "how far I got" is user data: it must follow the account, be visible in the database, and survive a cleared cache. It cannot be derived from `vocabulary_review_state` either — state knows which words have been graded, not what order the remaining ones are queued in.

**`entry_ids` is deliberately not a foreign key.** It is an ordering, not a relationship, and an FK into `vocabulary_entry` would block removing a word from a topic just because someone is mid-round on it. The cost is orphaned ids, so the read path reconciles the saved board against the current pool and **reshuffles a fresh one if they disagree** — a new round beats resuming a board that points at the wrong words. `done` is derived (`position >= len(entry_ids)`), never stored, for the same reason as `StoryProgress`.

**Grade 6 is the one grade that measures a decision rather than a memory.** `GRADE_MASTERED` is an extension beyond SM-2's 0–5: the learner asserts "I own this word" and the engine honours it by setting `interval_days` **hard** to `MASTERED_INTERVAL_DAYS` instead of multiplying the old one. Ease still goes through the normal formula (computed as `GRADE_EASY`), and it still counts as a passing repetition. Migration `025` widened the CHECK to `0..6`; its downgrade will fail if any grade-6 row exists, which is correct — that data is genuinely invalid under the old scale.

**`/recall-check` exists so a word is not scored twice in one turn.** The typing module asks the machine to do the part it is good at — did I spell it right — and returns the real answer; the learner then self-grades on the five buttons, and *that* is what `/review` records. Scoring inside `recall-check` would count the word twice. It takes no auth on purpose: it writes nothing, and a published word is already public at `GET /vocabulary/{id}`. Note this is a different endpoint from `/recall`, which does record.

**The board belongs to the topic, not to the tab.** Typing, flashcard and quiz are three ways of meeting the same word in the same round; switching modules must not restart anything. Because the board is on the server this holds even when the component remounts — which also means a test that only switches tabs cannot catch a remount bug. What breaks the invariant for real is resetting `index` on a `mode` change.

**Writes to the board must be serialised.** Every `PUT` overwrites the whole `position`, and grading quickly on keys 1–5 fires two requests tens of milliseconds apart. If `position=4` lands after `position=5` the stored board goes *backwards* one word — the last write is still valid, just wrong, and nothing reports it. `persistBoard` chains its writes through one promise for that reason; it stays fire-and-forget toward the caller, because a failed save should cost a place marker, not stall the round.

**Quiz distractors are filtered by meaning, not just by id.** Two different words translate to the same Vietnamese ("quảng cáo", "thường xuyên" each belong to two entries today), so filtering only on `entry.id` can put two identical strings on screen with just one of them scored correct — plus a duplicate React `key`. `buildOptions` dedupes on the text and is shared by both quiz surfaces. When the pool cannot supply three distinct meanings the question simply has fewer options, on purpose.

**A 3D-flipped face is hidden from eyes, not from screen readers.** `backface-visibility` leaves the back of a flashcard in the accessibility tree, so a screen-reader user hears the meaning before being asked whether they remember it — the exercise is gone. The face turned away carries `inert`, which removes it from the a11y tree, blocks interaction **and** moves focus out. `aria-hidden` does neither of the last two, and putting it on the button the user just clicked is itself an ARIA violation.

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

**Signing in with Google or Apple goes through a server-side code flow, never a vendor SDK** (`planning/ADR-008-AUTH-PROVIDERS.md`). That is a constraint this repo imposes on itself: P1-7b (token in `localStorage` rather than an httpOnly cookie) is deferred *with a written reason* — no third-party script on any page. Embedding `accounts.google.com/gsi` expires that reasoning, and P1-7b would have to be paid first. Four things about the implementation fail quietly:

- **Identities are keyed on the provider's `sub`, never on email** (`user_identity`, unique on `(provider, subject)`). Email changes, and Apple's may be a private relay address; keying on it means changing your Google email makes you a new person here, with no learning history.
- **Linking to an existing account by email requires `email_verified` *and* a non-private address.** Linking blindly is a real account-takeover path. Note that **Apple sends `email_verified` as the string `"true"` while Google sends a boolean** — an `is True` check silently treats every Apple account as unverified and turns the rule off.
- **`state`/`nonce` live in Redis and this path fails CLOSED**, opposite to `rate_limit_anonymous`: there Redis being down must not lock everyone out, here Redis is the only thing proving the callback belongs to a real click. Reading the state deletes it, so a captured callback URL cannot be replayed.
- **`users.hashed_password` is nullable now**, which is why `/auth/login` and `/auth/password` both have an explicit `None` branch. They answer differently on purpose: login returns the *generic* wrong-credentials message (saying "this account uses Google" is a free account-existence oracle), while the password endpoint says so plainly because identity is already proven there.

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

**Paginate what grows; leave what has a ceiling.** `app/schemas/common.py` defines `Page[T]` and the rule for which bucket an endpoint falls in: (A) bounded by the domain — eight logical voices, a TOEIC form's 200 questions, seven parts — returns a **bare array**; (B) grows with content and (C) grows with usage return `Page[T]`. Wrapping bucket A "for consistency" makes the frontend handle a case that cannot occur, and converting all eighteen list endpoints would be a breaking contract change everywhere in exchange for nothing on fifteen of them. Consistency *within* the paginated set is the goal.

`limit`/`offset`, not cursors: no list here is a high-churn feed — an admin browses their own content, a history belongs to one learner — and three endpoints already used offsets. The condition for revisiting is written in the module: when a list becomes something many writers append to concurrently.

**A screen that renders a tree must not paginate the flat list behind it.** `/admin/tests` groups tests under collections and the dictation tree nests topic → section → story; slicing the flat list at 50 shows a collection holding three of its eight tests with nothing saying the rest exist. Both request `limit=200` and render a visible notice when `total` exceeds what came back — a truncated tree that admits it beats a paginated one that lies. Paginate the *grouping* level if either ever outgrows one page.

**When a screen only needs the count, read `total`, never `items.length`.** `/learn/dictation` labelled its standalone-sentence link from the array length, which pins at 50 the moment there are more — "50 câu" over 130. It now asks for `limit=1` and shows `total`.

**`pnpm lint` is eslint alone and does not typecheck. Running it is not "the frontend is checked".**
`API_ROUTES` is a **flat** map, so `API_ROUTES.auth.logout` is a `TypeError` on an
`undefined` — and because it threw on the callback's first line, the logout button
cleared nothing, signed nobody out, and did not even reach `router.push`. Clicking it
simply did nothing, which reads as a dead button rather than as a crash. `tsc` reports it
as `TS2339: Property 'auth' does not exist`; eslint exits 0. CI's `web` job builds, so it
would have caught it — one push later than the person who wrote it. Run `tsc --noEmit`
before claiming a frontend change is verified, and prefer an e2e over both when the
change lives at a seam: `e2e/auth.spec.ts` now clicks the real button.

**`apiFetch<T>` takes its type from the caller, so changing a response shape is invisible to `tsc`.** Turning six list endpoints into `Page[T]` broke eight frontend call sites and the compiler reported nothing — the generic is supplied at the call, never inferred from the route, so `apiFetch<Thing[]>` happily mislabels an envelope. A green typecheck after a contract change on a list endpoint is a false negative; grep for the route constants and fix each caller by hand.

**Offset pagination requires a *total* order, or rows silently duplicate and vanish.** `ORDER BY headword` looks deterministic and is not: `vocabulary_entry` is unique on *(headword, part_of_speech)*, so two rows can tie, their relative order is undefined between queries, and with `LIMIT/OFFSET` one row then appears on two pages while another appears on none — with no error anywhere. Every paginated query ends with `id` as a tiebreaker. `tests/test_attempts.py` walks three pages and asserts the union covers each row exactly once.

**Never reuse a name like `total` for a per-row tally in the same function.** `list_attempts` computed the page total, then a loop below unpacked `total, answered, correct = ...` per attempt, so `page_of(...)` reported the *last attempt's question count* as the collection size. It returned 1 for five rows — a plausible number, wrong, and invisible on a skim. The per-row name is `asked`.

**Learner-facing queries filter `published` at *both* levels — the question and the set it belongs to.** `POST /attempts` filtered only the question, so a published question under a draft set carried that set's passage *and* recording out to a learner (`_passages` reads straight off `question_set`). Exactly the dictation-tree leak, which is why that tree filters at all four levels. The join must be an **outer** join: `question.set_id` is NULL for parts 1, 2 and 5, and an inner join silently drops those three parts from every attempt — a worse failure than the leak it fixes, and just as quiet. `tests/test_attempts.py` pins both directions in one test.

**Detaching media never deletes it, and `reconcile_media` is how the debris gets found.** Garbage accumulates from two silent sources: a confirm step that rejects *after* the bytes are already on the provider (ADR-006 uploads first, writes the row second), and the detach buttons, which drop the link on purpose — assets are content-addressed, so two questions sharing one photograph is normal and deleting on detach would eventually strip a different question's image. The command reports only; `--delete-rows` touches the database alone, never the provider, because remote deletion is irreversible and is a per-case human decision. Its reference list must name every FK into `audio_asset`/`image_asset` — including `passage_2_image_id` and `passage_3_image_id`, whose omission reports every multi-passage reading image as junk. Avatars are exempt: `user_profile.avatar_storage_key` holds a raw key with no asset row at all.

**Never put `await work()` inside an optional call's argument list.** `done?.(await work())` looks like "run the work, then hand the result to `done` if there is one". It is not: optional call short-circuits the *whole* call expression when the callee is nullish, arguments included — so with no `done`, **`work()` never runs**, the function falls through to `return null`, and the caller is told the operation succeeded. Write it as two statements: `const value = await work(); done?.(value);`.

This cost a long hunt in `apps/web/src/app/admin/tests/[slug]/page.tsx`. Only calls that omit `done` are affected, so almost every button on the page worked and the bug looked impossible: the Delete-test button reported "đã xoá", redirected to the list, left the row in the database, and produced **no request in the API log or the browser Network tab**. Everything else pointed away from the truth — the modal, the dev-server cache, hydration, CORS. The twin `run` in `admin/tests/page.tsx` writes `await work()` on its own line, which is why deleting a *collection* worked while deleting a *test* did not; that asymmetry was the clue.

Two habits fall out of it. A destructive action should prove success from something the server actually said — `apiSend` returns the raw `Response` and the delete path requires a literal `204` — rather than infer it from the absence of an exception. And when the client claims success while the server log is empty, suspect the client's own control flow before the network.

**`_question_admin` takes its asset map as a required argument, and that is load-bearing.** It was optional (`assets = None`) for a sprint and *no* call site passed it, so `lookup` was always empty and every question came back with `audio_url: null` and `image_url: null` — attached media rendering as "chưa có bản thu" everywhere, while the database was correct. Nothing caught it because the response stayed perfectly valid, just wrong. An optional parameter whose absence still produces a plausible answer is the shape to avoid; making it required turns the omission into a mypy error. The set-level twin (`_set_admin`) always took its map positionally and was never affected, which is why Part 3/4 audio appeared to work while Part 1/2 did not.

**Images are uploaded at the slot they belong to; there is no image library.** `/admin/media` existed and was deleted: a "pick from library" dropdown degrades with volume, and past a couple of hundred images the only label distinguishing two entries is the tail of the `storage_key` — so picking the wrong photograph *succeeds*, silently, and shows a learner a picture nobody wrote questions about. The upload path is unchanged (ADR-006 §2.3 ticket → direct POST → confirm); only the point of use moved. The three provenance fields are declared once per page for the batch, because a paper's images usually share a source; `alt_text` stays per-image because it describes that one picture. Bulk import is `import_media`.

**Parts 3 and 4 carry a graphic on the *set*, not on the question.** The last few conversations in Part 3 and talks in Part 4 print a chart, schedule or floor plan once beside all three questions, and one question says "Look at the graphic". That is the same shape as a Part 7 passage, so it reuses `question_set.passage_image_id` — `assign_passage_image` accepts parts 3, 4 and 7, with **slot 1 only** outside part 7 (three slots there would invite content the exam does not have). Part 1's photograph stays on the question, because there every question has its own. The learner-facing path needed no change: `_passages` already keeps a slot that has an image but no text.

**Alt text is required for a Part 3/4 graphic and deliberately absent for a Part 1 photograph.** The two look like the same rule and are opposites. A Part 1 photo *is* the question, so describing it hands over the answer. A Part 3/4 graphic is data you must read *and* combine with the audio, so a description gives nothing away — and without it the question is unanswerable with a screen reader.

**`--match index` looks up by position, never by zip.** The filename's number is the item's position within its part (`part2/10_….mp3` is the 10th Part 2 question, i.e. question 16). Zipping files onto slots only works when every slot has a file, which is false for Part 3/4 graphics where only the last few sets have one — zip would put set 11's floor plan on set 1, match cleanly, and report success. Empty slots are therefore expected (and tolerated) for `image --part 3|4`, and an error everywhere else.

**`import_media` refuses to do half the job.** Bulk-attaching files to a pasted test matches on the number in the filename, and any leftover file or unfilled slot stops the run rather than importing what matched. A half-import leaves a test missing a couple of recordings, and the gap surfaces only when a learner reaches that exact question. `--dry-run` prints the full mapping table; `--match order` zips sorted files onto slots when the names carry no usable number.

**A `part N` label in a filename is stripped before the question number is read.** `part3_32.mp3` parsed naively gives `3` — and `3` is not a harmless miss, because Part 1 spans questions 1–6, so it matches successfully and staples a Part 3 conversation onto a Part 1 photo question. Silent *wrong* matches are worse than loud misses, which is why `_PART_LABEL` runs first and why the number taken afterwards is the **first** one (`32-34.mp3` is the set that opens at 32; the last number matches no set at all).

**Imported audio must be written with `source="uploaded"`.** That is what puts it in `AudioState.EXTERNAL` and stops the TTS worker regenerating over it on its next sweep. Recording it as `tts` would hand a human voice to edge-tts, discoverable only by pressing play.

**The TTS worker is a separate image, and that separation is the point.** `docker/worker.Dockerfile` carries ffmpeg and the `content` extra; `api.Dockerfile` carries neither. Merging them would not break anything on the day it happened — it would break on the day someone noticed `app.content` was already installed and imported it into a request handler "since it's right there", putting edge-tts, ffmpeg and a network call on the serving path. A separate image gives A4.1 a physical shape instead of a convention someone has to remember.

**The generate-audio button rings a doorbell; it does not generate audio.** `POST /admin/media/audio/requests` publishes to a Redis channel and returns **202**, never 200 — the API cannot synthesise (A4.1). Nothing is written to any table: the queue is still the *question* "what content is missing audio or no longer matches its script", so pressing the button ten times does not create ten jobs. Redis being down still returns 202 with `queued: false`, because the worker's 300-second sweep finds exactly the same work — reporting failure would make an editor retry something that was already going to run. Pub/sub is deliberate: a message published while the worker is down is lost, and that is fine, because it carries no information.

**`AudioState.EXTERNAL` is what stops the worker overwriting a human recording.** An uploaded clip's `source_hash` fingerprints a random id, so it can never match the text — under the older `is not CURRENT` test it fell straight into the regenerate branch and a human voice was silently replaced by TTS, discoverable only by pressing play. `_REGENERATE` is `(MISSING, STALE)` and nothing else. This applied to vocabulary and dictation too, not just questions.

**`AudioFactory` takes `duration_probe` and `joiner`**, the same two seams `generate()` already had, for the same reason: mutagen needs a real mp3 and `join_turns` needs ffmpeg, while what is worth testing is the skip/generate decision and the row that follows it. Without them no branch of that class could run outside a fully-provisioned machine.

**Nothing reachable from `app/main.py` may import `app.content`.** The production image is built `--no-dev` without the `content` extra, so a leak breaks container startup rather than the build. `tests/test_content_isolation.py` catches it in a subprocess in under a second; the `docker` CI job catches it the slow way. Shared code belongs in `app/core/`.

**Monorepo wiring.** pnpm workspaces + Turborepo for JS/TS. `apps/api` is a separate `uv` project outside the turbo graph, so cross-cutting scripts (`scripts/generate-api-types.sh`) drive both toolchains.

**The production API image needs no compiler.** `gcc` and `libpq-dev` sat in `api.Dockerfile` to build psycopg — but the dependency is `psycopg[binary]`, whose wheel already bundles libpq, so nothing was ever compiled. Dropping them plus splitting builder/runtime took the image from 510MB to 321MB and removed a C toolchain from the process that serves HTTP. The image runs as uid 10001; `uv` stays in the runtime stage on purpose, because the dev compose service overrides CMD with `uv run uvicorn --reload` and removing it would save megabytes at the cost of the development loop. `UV_FROZEN=1` plus `--no-sync` keeps startup from ever resolving dependencies over the network.

The worker image drops the same two packages but **stays root**, deliberately: it writes to `media/` and `content/` through host bind mounts, and a non-root user loses write access to the two directories it exists to write to — the quick fix for that is `chmod 777`, which is worse. It also serves no requests.

**Question labels are multi-dimensional, and one scalar column cannot hold them.** The
taxonomy (`planning/toeic_question_label_taxonomy.md`) has **72 codes across 6 facets**, and a
single Part 6 question carries three at once — question type, passage form, grammar. The old
`question.skill_tag` column is gone; labels live in `question_label` and `question_set_label`
(migration `019`). Four things about that shape are load-bearing:

- **The primary key is `(owner_id, facet)`**, and that is where "exactly one label per facet" is
  *enforced* rather than remembered. It also means a code written under the wrong facet **overwrites**
  the label of another facet instead of creating a row — silently losing the old one.
- **Four facets live on `question_set`, not on `question`**: topic (Part 3), speech type (Part 4),
  passage type (Parts 6–7), passage structure (Part 7). Three questions of one Part 3 conversation
  always share a topic because it is a property of the conversation. Hanging them on the question
  lets the schema *permit* three different topics for one conversation, and per-topic statistics
  would count one conversation three times. Same reasoning as ADR-001 §A4.3 for Part 3/4 audio.
- **`proposed_code` is never touched when a human edits `code`.** It is the only column that
  separates "somebody looked at it" from "somebody had to *fix* it", which is the accuracy KPI.
- **A code can be real, on the right facet, and still wrong for the part.** `GRAMMAR_NOUN` exists
  for Part 5 and not for Part 6 — Part 6 tests five grammar points, Part 5 tests eleven. Every
  write path checks all three (exists, right facet, valid for this part) because all three failures
  are silent.

**The confirm button is not a convenience — without it the accuracy KPI is structurally 0%.**
A `<select>`'s `onChange` fires only when the value *changes*, so if reviewing were only possible
by editing, every recorded review would be a correction, `code` would never equal `proposed_code`,
and "machine correct" would read 0% forever — the one number the screen exists to measure. The most
common review action is confirming the machine was right; it has to be a click.

**Enrichment labels one facet per call, and the queue is still a query.** `app/content/enrich_skills.py`
asks "which questions and sets are missing at least one applicable facet", so re-running finds less
to do and there is no job table. One call per facet rather than one call for all six: merging them
is cheaper in calls but makes all six wrong when the model slips once, forces a full retry instead
of retrying the failed facet, and loses the per-facet menu narrowing that keeps the model from
offering `GRAMMAR_NOUN` for a Part 3 question. It commits **per label**, not at the end of the run —
a 200-question run is tens of minutes, and batching means one interrupt discards all of it.

**Two kinds of HTTP 429, and merging them is expensive.** `LLMQuotaExhausted` is separate from
transient overload: a daily cap does not clear in thirty seconds, so backing off against it grinds
through every remaining item, fails identically each time, and buries the one line naming the cause.
OpenRouter's free tier is **50 calls per day**, which is not enough for a single 40-question run —
that is why Ollama runs locally. In `classify`, `except LLMQuotaExhausted` must come **before**
`except LLMError`; it is a subclass, and reversing the order swallows it.

**`ollama_base_url` differs between host and container, and both values are correct.** The CLI on
the host needs `localhost:11434`; inside a container `localhost` is the container itself, so the
worker needs `host.docker.internal:11434`. `.env` carries the host value and compose's `environment:`
block overrides it for the worker — the same precedence trap documented for `env_file` above.

**Never bind-mount `../apps/api` into a container — mount `../apps/api/app`.** The whole directory
includes `.venv`, and `uv run` inside the container finds a macOS virtualenv, deletes it, and builds
a Linux one **over the host's**. Every later `uv run` on the host then fails with
`broken symbolic link to /usr/local/bin/python3.12`, a message that never mentions Docker. The TTS
worker has always mounted only `app/`; that is why.

**Auth endpoints are rate limited by IP, and the quotas are sized around who gets blocked *wrongly*.** The pre-existing `rate_limit` keys on `user.id`, which cannot cover `/login` — that endpoint exists precisely because there is no user yet — so `rate_limit_anonymous` keys on the client address. Vietnamese mobile networks run CGNAT and thousands of subscribers share one public address, as do schools and internet cafés; a tight limit blocks a class signing up together long before it blocks an attacker, and blocked real users never file a report, they just leave. Be honest about the ceiling: this cuts a dictionary attack from thousands a minute to six and stops naive scripts, but a botnet rotating addresses walks straight through. Real brute-force defence needs per-account counting, which opens an account-lockout vector instead — that trade is written up in the docstring, not overlooked.

Two details are load-bearing. `client_ip` reads the **last** `X-Forwarded-For` hop, not the first: a client can prepend as many entries as it likes, and the final one is what your own proxy wrote. And `trust_forwarded_for` defaults to **off** — trusting the header with no proxy in front lets every caller declare its own key, which is worse than no limit because it looks protected. Unlike the upload limiter, the auth one **fails open** when Redis is down: there, Redis is all that stands between an account and your bill, so failing closed is right; here, failing closed means nobody can sign in at all — a soft dependency taking down the product.

## End-to-end tests

`apps/web/e2e/` runs Playwright **against the running docker stack** — it does not start its own server. Playwright's `webServer` can only bring up `next dev`, while a learning flow also needs the API, Postgres and Redis; standing up half the stack is the fastest way to a red suite that says nothing about the code. `docker compose up` first, then `pnpm --filter @toeic-pilot/web test:e2e`.

**E2E rather than component tests, deliberately.** Every frontend bug this project has produced lived at a *seam*, and none of them would fail a render test: a delete button whose handler silently never ran, attached media rendering as "chưa có" because a lookup map was never passed, six endpoints changing shape while `tsc` stayed green, `""` where the database required NULL. Backend tests were green through all of it.

The specs cover the flows the ROADMAP asks for — register→learn; open a test→answer→submit→results→review; and learn a vocabulary topic→self-grade→reload and resume — plus the unfinished-attempt surfaces. Each test registers its own account with a timestamped email, because `users.email` is UNIQUE and a shared fixture account makes the second run fail for a reason that has nothing to do with the code. The exam flow uses the seeded demo test rather than building content: creating one needs an admin, and `register` deliberately cannot grant a role, so seeding an admin inside the test would be more scaffolding than the thing under test.

**Skip on a condition asked at run time, not on a hard `true`.** `vocabulary.spec.ts` is disabled with `test.skip(true, …)` because CI runs a blank database, and the cost of that is that it never runs again — not even once CI can seed. `vocabulary-learn.spec.ts` asks the API instead whether a topic with enough words exists, so it runs for real on the dev stack and skips with a message naming what is missing everywhere else. Same shape as the `integration` marker on the API side.

**A green e2e proves nothing until you have seen it go red.** Each spec here was checked by reintroducing the bug it exists to catch — the `Page[T]` envelope regression turns the unfinished-attempt test red, and restoring the fix turns it green.

**Expect some of those red checks to stay green, and fix the test rather than the story.** Of four bugs reintroduced against the vocabulary-learning spec, two never turned it red. Giving the component a per-tab `key` (remount on every tab switch) stayed green because the board lives on the server, so the remount reads the right place back — the test pins the *behaviour* "you do not lose your place", and the docstring now says so instead of claiming it catches remounts. Removing the meaning-based distractor filter also stayed green across three runs: three distractors drawn from forty-odd words make the chance of both halves of a duplicate pair landing on one question a few in a thousand. That assertion was deleted. An assertion that cannot realistically fail is cost without return, and leaving it in while believing it protects you is worse than not having it.

**Re-running the suite hits the auth rate limiter, and the failure names the wrong thing.** `rate_limit_anonymous` keys on the client IP, and every spec registers a fresh account, so a few consecutive runs start failing at `POST /auth/register` with 429. What you see is `expect(page).toHaveURL(/\/learn$/)` failing in *every* test including ones unrelated to your change. Clear it with `docker compose exec redis redis-cli DEL ratelimit:register:<ip>` (`--scan --pattern 'ratelimit:*'` finds the key).

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
