---
paths:
  - "apps/api/app/content/**"
---

# Đường ống nội dung ngoài luồng — audio, ảnh, nhãn, sinh đề

**Audio and the content pipeline.** Decisions live in `planning/docs/PHASE2-AUDIO.md` Part A; read §A4 before changing anything here, because all four invariants fail silently. The shape:

- `app/core/media.py` — content-addressed naming, pure stdlib, imported by *both* sides. `source_hash` fingerprints the synthesis **input** (text | logical voice | engine | engine version), never the mp3 bytes: TTS is not byte-deterministic, so hashing output would break idempotency. `voice` is a **logical** name (`us_female_1`), never a provider id (`en-US-JennyNeural`) — that indirection is what kept the library intact when `en-AU-WilliamNeural` was renamed upstream.
- `app/models/audio.py` — `audio_asset`, deliberately independent of the domain schema. The dependency runs domain → asset. `source_text` is **not** the grading answer key; dictation grades against `dictation_item.transcript`.
- **A spec line has two shapes, and only one of them can express a conversation.** `{"text", "voice"}` (or `"voices"` to fan one text across accents) renders one clip; `{"turns": [{text, voice}, …], "gap_ms": N}` renders several turns joined into one file, which is what Parts 2 and 3 require. The hash for the second is `conversation_source_hash`, which fingerprints **the whole turn list in order** plus the gap — drop the order or the gap from it and a re-run silently "skips, already present" while the content has changed. Two behaviours surprise people, both measured and written up in `MEDIA-PIPELINE` §10.2: `gap_ms` is silence *added* to the ~1.1s edge-tts already pads each boundary with, and a clip whose turns mix accents must **declare** `"accent"` because the column holds exactly one value.
- `app/content/**` — the offline pipeline, behind the optional `content` extra. `generate` synthesises and writes `content/manifest/audio_assets.jsonl`; `seed` reads that manifest and upserts rows by `source_hash`. Generation happens **offline**, so an edge-tts outage blocks new content rather than breaking what already exists.
- The manifest is committed; the mp3s under `apps/api/media/` are gitignored. `generate` therefore skips only when the manifest entry *and* the file both exist — otherwise a fresh clone would never re-render them.
- Serving is a string join: `{audio_public_base_url}/{storage_key}`. The API never calls the object store at request time, and audio must **never** be proxied through FastAPI — that loses range requests and burns the API's bandwidth. `/media` is mounted only when `environment == "development"`.

  Read that rule as narrowly as it was meant (ADR-006 §2.9): it bans an endpoint that *re-serves bytes fetched from the object store*. It does **not** ban the `/media` static mount — Starlette's `FileResponse` sets `accept-ranges`, parses `Range`, and returns 206/416, so a static mount loses nothing. What is left is a bandwidth argument, which is about scale rather than correctness. Do not let the rule talk you out of a legitimate option.

- **The provider is a config value, not a code branch** (ADR-006 §2.8). One `s3` driver covers Supabase, B2, R2, DO Spaces, Wasabi and MinIO; `S3_ENDPOINT_URL` decides which. Two settings are load-bearing and fail misleadingly: boto3 defaults to **virtual-host addressing**, which turns the bucket into a subdomain and surfaces as a *DNS* failure rather than a config one, and Supabase requires **SigV4**. `tests/test_storage.py` pins the addressing style for exactly that reason.
- **Generated media never touches the upload path.** `app/content/push_media.py` syncs it — a deploy problem — routing each kind to its own provider (images to Cloudinary, audio to S3). The ticket/verify flow of §2.3 exists for bytes arriving from a machine we do not control (§2.8a).

- **Synthesising audio is not the last step — `push_media` is, and forgetting it breaks playback while every database check still passes.** `backfill_audio` writes clips to the local store and links the rows; the URL served to the learner points at the provider, so until `uv run python -m app.content.push_media --prefix audio` runs, every one of those rows resolves to a 400. Nothing warns you: the item is `published`, `audio_asset_id` is set, and `media_state` says `current`, because all three describe the row rather than the object.

  **A `--force` recast breaks audio that was already working, for the same reason.** `source_hash` includes `engine_version`, so re-recording moves every clip to a new content-addressed key — and the old key that was pushed months ago is no longer the one anyone asks for. Recasting 2 470 clips in one run therefore took the whole vocabulary and dictation library offline until the push caught up (2026-09-02). Verify a real URL with `curl -o /dev/null -w '%{http_code}'` after any bulk generation; checking `engine_version` in the database proves nothing about whether a learner can hear it.
- **Images live only on Cloudinary, including the ones `images.py` fetches** (ADR-006 §2.8c). Fetching to local disk and seeding a row was only half a path: `public_url` then built a Cloudinary URL for a file never uploaded there, and Part 1 images 404'd silently for sprints because nothing rendered them yet. `CloudinaryDriver.upload_file` closes it, and — like `LocalDiskDriver.write` — stays **off** the `StorageDriver` protocol so a request handler cannot reach it. Both upload paths share `_signed_params`, so the browser and the offline tool cannot drift into producing differently-transformed objects.

**A recording corresponds to its *script*, and staleness is a fingerprint comparison — never a pair of timestamps.** `question.audio_script_hash` / `question_set.audio_script_hash` record `script_fingerprint(...)` at the moment audio is attached; `_may_be_stale` recomputes it and compares. The obvious design — is `updated_at` later than `audio_attached_at`? — cannot be made correct, and both reasons only surface when you run it: `audio_attached_at` is written by Python's clock while `updated_at` comes from the database's `func.now()`, so the comparison depends on two clocks agreeing; and SQLite's `CURRENT_TIMESTAMP` has one-second resolution, so an edit in the same second as the attach is silent. Same shape as the `pwc` claim's `iat` problem. The fingerprint is also *more* accurate: it fires only when the thing the recording corresponds to actually changed, so fixing a comma in an explanation no longer cries wolf — and restoring the script to exactly what it was turns the warning back off, which no timestamp pair can do.

**Editing a set's script sends the set *and every question under it* back to draft.** The publish gate inspects questions one at a time, so demoting only the set leaves its questions published inside a released test, playing a recording of the old script. `PATCH /admin/question-sets/{id}` exists because without it Parts 3 and 4 had no way to change a script at all — one wrong word meant deleting the group and re-pasting — which also meant the stale warning had nothing that could ever trigger it. Part 1/2 scripts live on the question and go through `QuestionEdit`; sending `audio_script` to a Part 3/4 question is refused with a pointer to the set.

**Authoring-time validation is not publish-time validation.** `_authoring_problems` drops the "missing audio"/"missing photograph" complaints, and both `commit_part` and `edit_question` use it. Running the full `validate_question` on edit means every Part 1–4 question is invalid until its recording exists, so a typo in a script cannot be fixed until after it has been recorded — i.e. it has to be recorded twice. The real gate is still publish.

**Paginate what grows; leave what has a ceiling.** `app/schemas/common.py` defines `Page[T]` and the rule for which bucket an endpoint falls in: (A) bounded by the domain — eight logical voices, a TOEIC form's 200 questions, seven parts — returns a **bare array**; (B) grows with content and (C) grows with usage return `Page[T]`. Wrapping bucket A "for consistency" makes the frontend handle a case that cannot occur, and converting all eighteen list endpoints would be a breaking contract change everywhere in exchange for nothing on fifteen of them. Consistency *within* the paginated set is the goal.

`limit`/`offset`, not cursors: no list here is a high-churn feed — an admin browses their own content, a history belongs to one learner — and three endpoints already used offsets. The condition for revisiting is written in the module: when a list becomes something many writers append to concurrently.

**A screen that renders a tree must not paginate the flat list behind it.** `/admin/tests` groups tests under collections and the dictation tree nests topic → section → story; slicing the flat list at 50 shows a collection holding three of its eight tests with nothing saying the rest exist. Both request `limit=200` and render a visible notice when `total` exceeds what came back — a truncated tree that admits it beats a paginated one that lies. Paginate the *grouping* level if either ever outgrows one page.

**When a screen only needs the count, read `total`, never `items.length`.** `/learn/dictation` labelled its standalone-sentence link from the array length, which pins at 50 the moment there are more — "50 câu" over 130. It now asks for `limit=1` and shows `total`.

**Question labels are multi-dimensional, and one scalar column cannot hold them.** The
taxonomy (`planning/docs/toeic_question_label_taxonomy.md`) has **72 codes across 6 facets**, and a
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

