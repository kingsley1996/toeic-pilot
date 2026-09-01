---
paths:
  - "apps/api/tests/**"
  - "apps/web/e2e/**"
---

# Quy ước kiểm thử

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

## End-to-end tests

`apps/web/e2e/` runs Playwright **against the running docker stack** — it does not start its own server. Playwright's `webServer` can only bring up `next dev`, while a learning flow also needs the API, Postgres and Redis; standing up half the stack is the fastest way to a red suite that says nothing about the code. `docker compose up` first, then `pnpm --filter @toeic-pilot/web test:e2e`.

**E2E rather than component tests, deliberately.** Every frontend bug this project has produced lived at a *seam*, and none of them would fail a render test: a delete button whose handler silently never ran, attached media rendering as "chưa có" because a lookup map was never passed, six endpoints changing shape while `tsc` stayed green, `""` where the database required NULL. Backend tests were green through all of it.

The specs cover the flows the ROADMAP asks for — register→learn; open a test→answer→submit→results→review; and learn a vocabulary topic→self-grade→reload and resume — plus the unfinished-attempt surfaces. Each test registers its own account with a timestamped email, because `users.email` is UNIQUE and a shared fixture account makes the second run fail for a reason that has nothing to do with the code. The exam flow uses the seeded demo test rather than building content: creating one needs an admin, and `register` deliberately cannot grant a role, so seeding an admin inside the test would be more scaffolding than the thing under test.

**Skip on a condition asked at run time, not on a hard `true`.** `vocabulary.spec.ts` is disabled with `test.skip(true, …)` because CI runs a blank database, and the cost of that is that it never runs again — not even once CI can seed. `vocabulary-learn.spec.ts` asks the API instead whether a topic with enough words exists, so it runs for real on the dev stack and skips with a message naming what is missing everywhere else. Same shape as the `integration` marker on the API side.

**A green e2e proves nothing until you have seen it go red.** Each spec here was checked by reintroducing the bug it exists to catch — the `Page[T]` envelope regression turns the unfinished-attempt test red, and restoring the fix turns it green.

**Expect some of those red checks to stay green, and fix the test rather than the story.** Of four bugs reintroduced against the vocabulary-learning spec, two never turned it red. Giving the component a per-tab `key` (remount on every tab switch) stayed green because the board lives on the server, so the remount reads the right place back — the test pins the *behaviour* "you do not lose your place", and the docstring now says so instead of claiming it catches remounts. Removing the meaning-based distractor filter also stayed green across three runs: three distractors drawn from forty-odd words make the chance of both halves of a duplicate pair landing on one question a few in a thousand. That assertion was deleted. An assertion that cannot realistically fail is cost without return, and leaving it in while believing it protects you is worse than not having it.

**Re-running the suite hits the auth rate limiter, and the failure names the wrong thing.** `rate_limit_anonymous` keys on the client IP, and every spec registers a fresh account, so a few consecutive runs start failing at `POST /auth/register` with 429. What you see is `expect(page).toHaveURL(/\/learn$/)` failing in *every* test including ones unrelated to your change. Clear it with `docker compose exec redis redis-cli DEL ratelimit:register:<ip>` (`--scan --pattern 'ratelimit:*'` finds the key).

