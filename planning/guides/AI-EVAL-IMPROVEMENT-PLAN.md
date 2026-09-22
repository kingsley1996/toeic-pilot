# AI Evaluation Harness — Improvement Plan

> Scope: improvements to `app/content/eval_ai.py` based on the current implementation.
>
> Goal: evolve the current offline L1/L2 + optional L3 judge harness into a production-grade evaluation system for TOEIC Pilot.

---

## 1. Priority overview

| Priority | Area | Current state | Target |
|---|---|---|---|
| P0 | Eval correctness | Good foundation, a few edge cases | No misleading PASS/metric |
| P0 | Strict judge schema | Partial | Fully validated structured output |
| P0 | Regression comparison | `--against` is only metadata | Real baseline vs current diff |
| P0 | Eval metadata | Prompt version only | Reproducible run metadata |
| P1 | Case-level observability | Basic failures only | Failure taxonomy + latency/tokens/cost |
| P1 | Judge calibration | Basic agreement rate | Confusion matrix + calibration metrics |
| P1 | Dataset versioning | JSONL files | Versioned datasets / reproducible snapshots |
| P1 | Retrieval evaluation | Lexical Recall/MRR | Lexical + vector + fallback evaluation |
| P1 | Failure analysis | Free-form detail | Structured failure categories |
| P2 | Production feedback loop | Not present | Production traces → curated eval cases |
| P2 | Experiment tracking | JSON report | Historical runs + trend comparison |
| P2 | Adversarial eval | Not explicit | Robustness / boundary-case suite |

---

# 2. P0 — Fix evaluation correctness first

## 2.1 Validate retrieval `relevant_refs` against `limit`

Current retrieval evaluation uses:

```python
search_knowledge(..., limit=4)
```

while every `relevant_refs` item is required to appear in the top-4.

Add dataset validation:

```python
if len(want) > limit:
    raise EvalError(
        f"{cid}: relevant_refs ({len(want)}) exceeds retrieval limit ({limit})"
    )
```

Why:

- A case requiring 5 relevant documents cannot pass a top-4 retrieval test.
- This is a broken eval case, not a retrieval failure.
- Dataset/configuration errors should be separated from system failures.

---

## 2.2 Do not treat “no metric data” as 100%

Current:

```python
def _mean(xs):
    return sum(xs) / len(xs) if xs else 1.0
```

This can report:

```text
recall 1.00
MRR 1.00
```

when there were actually no metric observations.

Prefer:

```python
def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None
```

Then render:

```text
recall n/a · MRR n/a
```

or fail the suite when the dataset unexpectedly produces zero measurable cases.

Principle:

```text
No data != perfect score
```

---

## 2.3 Separate dataset/config errors from system failures

Current `SuiteReport.failures` contains both:

```text
case invalid
system failed
judge failed
```

Introduce a category:

```python
FailureKind = Literal[
    "dataset",
    "system",
    "judge",
    "infrastructure",
]
```

Example:

```python
@dataclass(slots=True)
class CaseFailure:
    id: str
    kind: str
    detail: str
```

This prevents a malformed test case from looking like a model regression.

---

# 3. P0 — Make LLM judge output strictly structured

Current judge schema only declares required fields:

```python
schema = {
    "type": "object",
    "required": ["dat", "ly_do"],
}
```

Define properties explicitly:

```python
schema = {
    "type": "object",
    "properties": {
        "dat": {"type": "boolean"},
        "ly_do": {"type": "string"},
    },
    "required": ["dat", "ly_do"],
    "additionalProperties": False,
}
```

Also keep the local parser as a defensive validation layer.

Expected contract:

```json
{
  "dat": true,
  "ly_do": "..."
}
```

Avoid accepting silently malformed judge output.

---

# 4. P0 — Turn `--against` into real regression comparison

Current `--against` records a label but does not actually compare two evaluation runs.

The intended flow should become:

```text
baseline run
     │
     ▼
baseline.json
     │
     ├──────────────┐
                    │
current run         │
     │              │
     ▼              ▼
current.json ──→ compare
                    │
                    ▼
             regression report
```

Example:

```text
coach
baseline: 96/100 = 96%
current:  93/100 = 93%
delta:    -3pp

retrieval
baseline Recall: 0.91
current Recall:  0.88
delta:           -0.03
```

Comparison should work at two levels:

### Suite level

- pass rate delta
- metric delta
- threshold status

### Case level

- newly failing cases
- newly passing cases
- unchanged failures
- unchanged passes

Most important regression category:

```text
NEW FAILURE
```

because an existing known failure should not be treated the same as a newly introduced regression.

---

# 5. P0 — Make evaluation runs reproducible

The report currently stores suite name/version/pass/failure information.

Add run metadata:

```json
{
  "run_id": "...",
  "timestamp": "...",
  "git_sha": "...",
  "dataset_version": "...",
  "prompt_versions": {},
  "models": {},
  "config": {},
  "suites": []
}
```

At minimum track:

- `run_id`
- UTC timestamp
- git commit SHA
- dataset version/hash
- prompt version
- model/provider
- suite
- CLI arguments
- threshold configuration

Goal:

> Given an evaluation report, another developer should be able to understand exactly what was evaluated.

---

# 6. P1 — Add case-level observability

Current report mainly stores:

```text
passed
total
failures
```

For each case, eventually capture:

```json
{
  "case_id": "coach-001",
  "passed": false,
  "failure_kind": "system",
  "failure_code": "wrong_explanation",
  "latency_ms": 812,
  "input_tokens": 500,
  "output_tokens": 220,
  "cost": 0.0012
}
```

This makes evaluation useful for both quality and operations.

Track where available:

- latency
- input tokens
- output tokens
- total tokens
- estimated cost
- provider
- model
- retry count
- error type

Do not require all fields for offline suites; use nullable fields.

---

# 7. P1 — Introduce a structured failure taxonomy

Avoid relying only on free-form strings such as:

```text
"chọn sai: được ..., muốn ..."
```

Keep human-readable `detail`, but add machine-readable fields.

Example:

```python
failure_code = "wrong_selection"
failure_kind = "system"
```

Suggested codes:

### Coach

```text
invalid_output
wrong_correct_answer
missing_explanation
wrong_reasoning
wrong_distractor
unsupported_claim
```

### Retrieval

```text
missing_relevant_ref
poor_rank
empty_result
retrieval_error
```

### Planner

```text
wrong_selection
unexpected_llm_call
unexpected_none
dangling_reference
invalid_candidate
```

### Judge

```text
invalid_json
missing_field
judge_disagreement
provider_error
timeout
rate_limit
```

This enables aggregate analysis later.

---

# 8. P1 — Improve LLM judge calibration

Current judge evaluation mainly asks:

```text
Did the judge agree with the deterministic expected result?
```

Add a confusion matrix:

```text
                    Ground Truth
                  PASS       FAIL
Judge PASS         TP         FP
Judge FAIL         FN         TN
```

Then report:

- accuracy
- precision
- recall
- F1
- false-positive rate
- false-negative rate

Keep the deterministic suite as the current reference for curated cases.

Important distinction:

```text
Judge evaluation
!=
Application quality evaluation
```

The first measures whether the judge behaves consistently with curated expectations.

---

# 9. P1 — Evaluate retrieval as separate components

Current retrieval evaluation deliberately forces lexical fallback:

```text
embedding unavailable
        ↓
lexical retrieval
```

Keep this test, but add separate suites/configurations:

```text
retrieval-lexical
retrieval-vector
retrieval-fallback
```

Suggested metrics:

### Retrieval quality

- Recall@K
- MRR
- optionally nDCG@K later

### Reliability

- embedding unavailable → lexical fallback works
- empty query
- malformed query
- KB unavailable
- duplicate chunks
- stale KB

The key is to avoid mixing:

```text
retrieval quality
```

with:

```text
fallback reliability
```

---

# 10. P1 — Remove global monkey-patching when architecture allows

Current retrieval eval temporarily replaces:

```python
embeddings.embed_query = _offline_embed
```

and restores it in `finally`.

This is safe for the current sequential runner, but fragile if evaluation becomes:

- parallel
- async
- multi-threaded

Prefer dependency injection eventually:

```python
search_knowledge(
    session,
    query,
    limit=4,
    embed_query=offline_embed,
)
```

or:

```python
KnowledgeRetriever(
    embedder=OfflineEmbedder()
)
```

Keep the current implementation until the surrounding service API can support this cleanly.

---

# 11. P1 — Make offline dependencies explicit

Planner currently constructs:

```python
redis.Redis()
```

while the suite is intended to be offline and the budget path does not actually need Redis.

Prefer an explicit fake/no-op dependency:

```python
FakeRedis()
```

or dependency injection that allows:

```python
redis_client=None
```

when Redis is not required.

The goal is that:

```text
offline eval
```

does not accidentally imply:

```text
real infrastructure dependency
```

---

# 12. P1 — Separate infrastructure failures from quality failures

For LLM judge and future live-model evaluation, distinguish:

```text
QUALITY FAILURE
```

from:

```text
INFRASTRUCTURE FAILURE
```

Examples:

```text
quality:
  judge says PASS but expected FAIL

infrastructure:
  timeout
  503
  rate limit
  authentication failure
  malformed provider response
```

A provider outage should not be interpreted as a model-quality regression.

The report should make this explicit.

---

# 13. P1 — Track retry behavior

The judge already uses backoff:

```python
_with_backoff(...)
```

Capture:

```text
attempts
successful_attempt
retry_reason
```

Example:

```json
{
  "case_id": "coach-42",
  "passed": true,
  "attempts": 2,
  "retry_reason": "503"
}
```

This allows monitoring:

```text
quality stable
but retry rate increasing
```

which is an operational signal rather than a quality signal.

---

# 14. P2 — Dataset versioning

The evaluation depends heavily on JSONL datasets.

Add a dataset identity:

```text
datasets/
  manifest.json
  coach_explain.jsonl
  explanation_shape.jsonl
  retrieval.jsonl
  planner.jsonl
```

Manifest example:

```json
{
  "version": "2026-09-21",
  "coach_explain_sha256": "...",
  "retrieval_sha256": "...",
  "planner_sha256": "..."
}
```

This makes historical reports reproducible even when datasets evolve.

---

# 15. P2 — Production feedback → eval dataset

The eventual loop should be:

```text
Production interaction
        ↓
trace / log
        ↓
bad or uncertain output
        ↓
human review
        ↓
curated eval case
        ↓
JSONL dataset
        ↓
CI
        ↓
new model/prompt release
```

This is especially important for TOEIC Pilot because real failures can reveal cases that hand-written datasets do not cover.

Examples:

```text
User reports explanation is confusing
        ↓
convert to coach negative case
```

```text
User cannot find grammar lesson
        ↓
convert to retrieval case
```

```text
Planner repeatedly selects low-value lessons
        ↓
convert to planner regression case
```

Do not automatically promote every production interaction into the golden dataset. Add a review/curation step.

---

# 16. P2 — Add adversarial and boundary cases

Current suites are primarily curated functional cases.

Add cases around boundaries.

### Coach

- missing chosen answer
- invalid option label
- ambiguous question
- contradictory labels
- empty explanation
- extremely long explanation
- hallucinated grammar rule

### Retrieval

- empty query
- typo
- synonym
- Vietnamese query
- English query
- mixed-language query
- query with no relevant document
- duplicate relevant references

### Planner

- budget = 0
- budget smaller than minimum item cost
- no weak topics
- all topics weak
- duplicate topics
- unpublished topics
- missing lesson references

### Judge

- fenced JSON
- extra fields
- malformed JSON
- empty reason
- boolean encoded as string
- extremely long explanation

---

# 17. P2 — Add trend reporting

Once reports are persisted, show trends:

```text
Run        Coach    Retrieval    Planner
----------------------------------------
#101       94%      0.91         100%
#102       96%      0.92         100%
#103       95%      0.89         98%
#104       97%      0.93         100%
```

Track:

- quality over time
- regressions
- retrieval metrics
- judge agreement
- latency
- token usage
- cost

This can eventually become an internal AI quality dashboard.

---

# 18. Recommended report structure

A future report should look roughly like:

```json
{
  "run": {
    "id": "eval-2026-09-21-001",
    "timestamp": "...",
    "git_sha": "...",
    "dataset_version": "2026-09-21"
  },
  "models": {
    "generator": "provider/model",
    "judge": "provider/model"
  },
  "suites": [
    {
      "name": "coach",
      "prompt_version": "v3",
      "passed": 97,
      "total": 100,
      "rate": 0.97,
      "failures": []
    },
    {
      "name": "retrieval",
      "metrics": {
        "recall_at_4": 0.93,
        "mrr": 0.81
      }
    }
  ],
  "regression": {
    "baseline_run": "...",
    "new_failures": [],
    "fixed_failures": [],
    "metric_deltas": {}
  }
}
```

The exact schema can evolve; the important thing is separating:

```text
run metadata
suite metrics
case results
failures
regression
```

---

# 19. Recommended implementation order

Do not implement everything at once.

## Phase 1 — Correctness

1. Validate `relevant_refs <= limit`
2. Fix empty metric behavior
3. Add failure categories
4. Strengthen judge JSON schema
5. Make infrastructure failures distinct from quality failures

## Phase 2 — Regression

6. Add `run_id`
7. Store git SHA
8. Store dataset hash/version
9. Implement actual baseline comparison
10. Detect new failures

## Phase 3 — Observability

11. Case-level latency
12. Token usage
13. Cost
14. Provider/model
15. Retry count
16. Structured failure codes

## Phase 4 — Judge quality

17. Confusion matrix
18. Precision/recall/F1
19. Judge calibration dataset
20. Judge-vs-ground-truth analysis

## Phase 5 — Retrieval

21. Separate lexical/vector/fallback suites
22. Add Recall@K
23. Add MRR
24. Add robustness cases

## Phase 6 — Production feedback

25. Capture production traces
26. Human review/curation
27. Promote selected failures to eval datasets
28. Run them in CI
29. Track quality trends

---

# 20. Target architecture

The long-term architecture should become:

```text
                         ┌──────────────────────┐
                         │   Eval Datasets      │
                         │ golden + regression  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Eval Runner       │
                         └──────────┬───────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
       Deterministic            System Eval             LLM Judge
       L1 / L2                  retrieval/planner       L3
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Evaluation Result    │
                         │ case + suite metrics │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
              Threshold         Regression       Observability
                  │                 │                 │
                  └─────────────────┼─────────────────┘
                                    ▼
                                  CI/CD
                                    │
                                    ▼
                              Model/Prompt
                                Release
                                    │
                                    ▼
                              Production
                                    │
                                    ▼
                               Feedback
                                    │
                                    └──────→ Eval Dataset
```

## Core principle

The eval system should eventually answer four different questions:

```text
1. Does the output have the correct structure?
   → deterministic/schema checks

2. Does the AI system behave correctly?
   → system-level evals

3. Can an independent model reliably judge quality?
   → judge calibration

4. Did the latest change make the system better or worse?
   → regression evaluation
```

Do not collapse these into one score.

The current `eval_ai.py` already has the right foundation for this separation; the main improvement is to turn the current test runner into a **reproducible, observable, regression-aware evaluation system**.
