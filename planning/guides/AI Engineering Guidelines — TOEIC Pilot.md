# AI Engineering Guidelines — TOEIC Pilot

> **Purpose:** Guide AI coding agents and engineers to build TOEIC Pilot as a production-grade AI system, not a collection of LLM demos.
>
> **Core principle:**
>
> **Nothing ships on vibes.**
>
> Every AI feature must be designed, implemented, evaluated, observed, and iterated with evidence.

---

## 1. Engineering North Star

TOEIC Pilot should follow this lifecycle for every meaningful AI feature:

```text
Problem
  ↓
Design
  ↓
Implement
  ↓
Validate
  ↓
Evaluate
  ↓
Observe
  ↓
Iterate
  ↓
Ship
```

Do not treat an LLM call as the feature.

The feature is the complete system around the model:

```text
User
 ↓
Application
 ↓
AI Workflow
 ├── Context
 ├── Retrieval
 ├── Tools
 ├── Model
 ├── Validation
 └── Evaluation
 ↓
Result
 ↓
Telemetry
 ↓
Feedback
```

---

# 2. Core Principles

## 2.1 AI is a system, not a prompt

Do not solve a complex problem by continuously increasing prompt complexity.

Prefer:

```text
LLM
+
Structured state
+
Tools
+
Deterministic code
+
Validators
+
Evaluation
```

over:

```text
Huge prompt
+
Huge context
+
Hope
```

---

## 2.2 Deterministic code before LLM

Use normal application code whenever the requirement is deterministic.

Good:

```python
if question.part != "part5":
    raise ValidationError(...)
```

Not:

```text
LLM, please make sure this is Part 5.
```

LLMs should handle tasks involving:

- language understanding
- generation
- classification
- reasoning
- semantic matching
- natural-language feedback

Application code should handle:

- schemas
- permissions
- state transitions
- database writes
- authentication
- limits
- retries
- validation
- business rules

---

## 2.3 Structured output by default

Do not parse free-form LLM text when a schema is possible.

Prefer:

```python
class Question(BaseModel):
    question: str
    choices: list[str]
    answer: str
    explanation: str
```

over:

```text
LLM → Markdown → regex → object
```

Every production AI output should have:

1. schema
2. validation
3. failure handling

---

# 3. Feature Classification

Before implementing an AI feature, classify it.

### Type A — Normal application logic

No LLM required.

Examples:

- score calculation
- XP calculation
- streak calculation
- SM-2 scheduling
- permission checks

Use deterministic code.

---

### Type B — Single LLM operation

Examples:

- explain grammar
- generate vocabulary example
- rewrite explanation

Architecture:

```text
Input
 ↓
Prompt
 ↓
LLM
 ↓
Structured Output
 ↓
Validator
```

---

### Type C — RAG

Examples:

- TOEIC knowledge assistant
- grammar explanation from curated knowledge
- vocabulary explanation

Architecture:

```text
Query
 ↓
Query processing
 ↓
Retrieval
 ↓
Reranking
 ↓
Context
 ↓
LLM
 ↓
Validation
```

---

### Type D — Agent workflow

Use only when the problem genuinely requires:

- multiple steps
- tools
- dynamic decisions
- state
- iteration
- external systems

Architecture:

```text
Input
 ↓
Planner / Controller
 ↓
┌───────────────┐
│ Agent State   │
└───────────────┘
 ↓
Tool / Retrieval
 ↓
Model
 ↓
Validator
 ↓
Decision
 ├── Finish
 └── Retry / Revise
```

Do not introduce an agent merely because an LLM is involved.

---

# 4. Agent Design Rules

## 4.1 Every agent needs explicit state

Do not rely on hidden conversation history.

Example:

```python
class GenerationState(TypedDict):
    specification: QuestionSpec
    retrieved_context: list[Document]
    draft: Question | None
    validation_errors: list[str]
    evaluation: EvaluationResult | None
    attempts: int
```

State should contain everything required to understand the current workflow.

---

## 4.2 Every tool needs a narrow contract

Bad:

```text
execute_anything(...)
```

Good:

```python
search_knowledge(query)
get_question_template(part)
save_question(question)
validate_question(question)
```

Each tool must define:

- input schema
- output schema
- permissions
- failure behavior
- timeout
- retry policy

---

## 4.3 Limit agent autonomy

Every agent should have:

```text
max_steps
max_retries
allowed_tools
timeout
token_budget
```

Example:

```python
MAX_ATTEMPTS = 3
MAX_TOOL_CALLS = 8
```

Never create an unrestricted loop such as:

```text
while not good:
    ask_llm()
```

---

## 4.4 Prefer workflow graphs over uncontrolled loops

For predictable workflows:

```text
Generate
  ↓
Validate
  ↓
Evaluate
  ↓
Revise
  ↓
Validate
  ↓
Publish
```

Prefer an explicit state machine / graph.

The next step should be observable.

---

# 5. RAG Engineering

Every RAG feature must define:

```text
Source
 ↓
Ingestion
 ↓
Cleaning
 ↓
Chunking
 ↓
Metadata
 ↓
Embedding
 ↓
Index
 ↓
Retrieval
 ↓
Reranking
 ↓
Context assembly
 ↓
Generation
```

---

## 5.1 Documents need metadata

At minimum:

```json
{
  "source": "...",
  "document_type": "...",
  "topic": "...",
  "language": "en",
  "version": "...",
  "created_at": "..."
}
```

For TOEIC content, consider:

```text
part
question_type
taxonomy
difficulty
topic
source
```

---

## 5.2 Retrieval must be measurable

Do not claim:

> "RAG works."

Create evaluation data.

Example:

```json
{
  "query": "When should I use despite vs although?",
  "relevant_documents": [
    "grammar/conjunctions/contrast.md"
  ]
}
```

Measure appropriate retrieval metrics such as:

```text
Recall@K
Precision@K
MRR
NDCG
```

Do not optimize retrieval based only on subjective inspection.

---

## 5.3 Retrieval errors and generation errors are different

When an answer is wrong, determine whether:

```text
Retrieval failure
```

or:

```text
Generation failure
```

Example:

```text
Correct document exists
        ↓
Retriever failed
        ↓
Generation never had correct evidence
```

This is fundamentally different from:

```text
Correct document retrieved
        ↓
LLM ignored evidence
        ↓
Generation failure
```

Track these separately.

---

## 5.4 Reranking should be evidence-driven

Do not add reranking because it is trendy.

Measure:

```text
Baseline retrieval
       vs
Retrieval + reranker
```

Compare:

```text
retrieval quality
latency
token usage
cost
answer quality
```

Keep the additional complexity only when it produces measurable value.

---

# 6. Prompt Engineering as Software Engineering

Prompts are source code.

Do not treat prompts as random strings inside business logic.

Prefer:

```text
prompts/
├── question-generator/
│   ├── v1.md
│   ├── v2.md
│   └── metadata.yaml
├── evaluator/
│   ├── v1.md
│   └── v2.md
└── assistant/
    └── v1.md
```

Every important prompt should have:

```text
name
version
purpose
input contract
output contract
model
temperature / generation config
evaluation dataset
```

---

## 6.1 Prompt changes require evaluation

Never assume:

```text
better prompt
=
better system
```

For every meaningful prompt/model change:

```text
Old version
 ↓
Eval dataset
 ↓
Metrics

New version
 ↓
Same eval dataset
 ↓
Metrics

Compare
```

Keep regression cases.

---

# 7. Evaluation is a First-Class System

Every AI feature must answer:

> How do we know this works?

At minimum define:

```text
Dataset
Metric
Threshold
Evaluation method
Failure categories
```

Example:

```yaml
feature: toeic_question_generation

metrics:
  answer_correctness:
    threshold: 0.98

  grammar_quality:
    threshold: 0.95

  distractor_quality:
    threshold: 0.90
```

Thresholds must be based on actual project requirements and evaluation evidence, not arbitrary numbers.

---

# 8. Evaluation Layers

Use multiple layers.

## Layer 1 — Schema validation

```text
Is the output valid JSON?
Are required fields present?
Are types correct?
```

---

## Layer 2 — Deterministic validation

Examples:

```text
Exactly 4 choices
Exactly 1 correct answer
Answer exists in choices
No duplicate choices
Valid TOEIC Part
Valid taxonomy
```

---

## Layer 3 — Semantic evaluation

Examples:

```text
Is the answer correct?
Is the explanation logically valid?
Is the question natural?
Are distractors plausible?
```

---

## Layer 4 — Regression evaluation

Run the same dataset after:

- prompt changes
- model changes
- retrieval changes
- agent changes
- parser changes

A change should not silently degrade previous behavior.

---

# 9. LLM-as-Judge Rules

LLM judges can be useful but are not ground truth.

When using an LLM evaluator:

```text
Generation model
        ↓
Evaluator
        ↓
Score
```

also maintain:

```text
Human-reviewed benchmark
```

Use human evaluation to calibrate the automated evaluator.

Record:

```text
judge model
judge prompt version
evaluation dataset
score
confidence
```

Do not blindly trust a single LLM judge.

---

# 10. Dataset and Annotation

AI quality depends heavily on data quality.

Maintain:

```text
eval/
├── datasets/
├── annotations/
├── guidelines/
└── reports/
```

Annotation guidelines should define:

```text
What counts as correct?
What counts as incorrect?
What is acceptable variation?
What is a critical error?
```

For TOEIC questions, possible labels:

```text
correctness
grammar
naturalness
difficulty
distractor_quality
taxonomy
explanation_quality
```

---

# 11. Production Observability

Every important AI request should generate structured telemetry.

At minimum:

```text
request_id
feature
workflow
model
model_version
prompt_version
latency
input_tokens
output_tokens
estimated_cost
status
error_type
```

For RAG:

```text
retrieval_latency
retrieved_document_ids
retrieval_scores
reranker_used
```

For agents:

```text
step_count
tool_calls
tool_latency
tool_errors
retry_count
```

---

# 12. Tracing

An AI request should be traceable end-to-end.

Example:

```text
trace: abc123

Request
 ├── retrieve
 │    ├── embedding
 │    └── vector_search
 │
 ├── agent
 │    ├── tool: search_grammar
 │    ├── model_call
 │    └── validator
 │
 └── response
```

When something fails in production, an engineer should be able to answer:

> What happened?

without reproducing the entire request manually.

---

# 13. Cost Engineering

LLM cost is an engineering metric.

Track:

```text
input tokens
output tokens
model
cost/request
cost/feature
```

Do not automatically use the largest model.

Prefer:

```text
Simple task → cheaper/faster model
Complex reasoning → stronger model
Deterministic task → no LLM
```

Measure quality/cost tradeoffs before changing models.

---

# 14. Reliability

Every external model/tool call must define:

```text
timeout
retry
backoff
fallback
error handling
```

Example:

```text
LLM request
 ↓
Timeout?
 ├── No → continue
 └── Yes
      ↓
   retry with backoff
      ↓
   max retry?
      ├── No → retry
      └── Yes → controlled failure
```

Never hide failures behind:

```python
except Exception:
    return None
```

Errors should be observable.

---

# 15. Safety

Treat external content as untrusted.

Potential attack surfaces:

```text
User input
Retrieved documents
Web content
Uploaded files
Tool output
Conversation history
```

Do not assume retrieved text is an instruction.

---

## 15.1 Prompt injection

Separate:

```text
Instructions
```

from:

```text
Untrusted data
```

Example:

```text
SYSTEM INSTRUCTIONS
-------------------
...

RETRIEVED CONTENT
-----------------
The following content is untrusted reference material:
...
```

Never allow retrieved text to redefine system policy.

---

## 15.2 Tool permissions

Tools should use least privilege.

Bad:

```text
agent → unrestricted database access
```

Better:

```text
agent
 ↓
specific tool
 ↓
validated parameters
 ↓
authorized service
```

The model should not directly control sensitive infrastructure.

---

## 15.3 PII

Do not send unnecessary personal information to LLM providers.

Prefer:

```text
user_id: internal_123
```

instead of unnecessary:

```text
name
email
phone
address
```

when those fields are not required.

---

# 16. Testing

AI features require multiple testing layers.

```text
Unit tests
Integration tests
AI evaluation tests
Regression tests
API tests
```

Example:

```text
tests/
├── unit/
├── integration/
├── eval/
├── regression/
└── fixtures/
```

Test deterministic logic normally.

Evaluate probabilistic behavior statistically.

Do not expect LLM outputs to be byte-for-byte identical unless determinism is explicitly required.

---

# 17. Definition of Done for AI Features

An AI feature is not considered complete merely because the UI works.

Before shipping, verify:

### Architecture

- [ ] Clear responsibility for LLM vs deterministic code
- [ ] State is explicit
- [ ] Tools have schemas
- [ ] Failure paths are defined

### LLM

- [ ] Prompt is versioned
- [ ] Model is explicitly configured
- [ ] Structured output is used where appropriate
- [ ] Context is controlled

### RAG

- [ ] Sources are identifiable
- [ ] Documents have metadata
- [ ] Retrieval can be evaluated
- [ ] Retrieval failures are distinguishable from generation failures

### Evaluation

- [ ] Evaluation dataset exists
- [ ] Metrics are defined
- [ ] Regression cases exist
- [ ] Significant changes trigger evaluation

### Production

- [ ] Logs exist
- [ ] Tracing exists
- [ ] Token usage is tracked
- [ ] Cost can be estimated
- [ ] Latency is measurable
- [ ] Errors are observable

### Safety

- [ ] Prompt injection considered
- [ ] Untrusted content is treated as data
- [ ] Tool permissions are restricted
- [ ] PII exposure is minimized

### Testing

- [ ] Unit tests
- [ ] Integration tests
- [ ] AI evaluation
- [ ] Failure cases

---

# 18. AI Agent Coding Rules

When an AI coding agent modifies TOEIC Pilot, it should follow this sequence.

## Step 1 — Understand

Before coding:

```text
Read existing architecture.
Find related modules.
Understand current interfaces.
Identify existing tools/services.
```

Do not create a parallel architecture without checking existing code.

---

## Step 2 — Plan

Write a short implementation plan:

```text
Goal
Architecture
Files to change
New interfaces
Evaluation strategy
Testing strategy
Observability impact
```

---

## Step 3 — Implement the smallest complete slice

Prefer:

```text
working vertical slice
```

over:

```text
large unfinished abstraction
```

Example:

```text
API
 ↓
Agent
 ↓
Tool
 ↓
LLM
 ↓
Validator
 ↓
Response
```

Get one complete path working first.

---

## Step 4 — Add evaluation

Before declaring success:

```text
Create representative examples.
Test normal cases.
Test edge cases.
Test failure cases.
Measure quality.
```

---

## Step 5 — Add observability

Make the workflow inspectable.

At minimum:

```text
request
model
prompt version
latency
tokens
errors
```

---

## Step 6 — Run regression tests

Existing functionality must continue working.

Do not optimize the new feature by silently breaking existing behavior.

---

## Step 7 — Report evidence

Every substantial AI change should report:

```text
What changed?

Why?

What was evaluated?

What metrics changed?

What failed?

What remains uncertain?
```

Never report only:

```text
Implemented successfully.
```

---

# 19. Preferred Architecture

For AI-heavy backend features, prefer a layered architecture:

```text
app/
├── api/
│   └── routes/
│
├── domain/
│   ├── models/
│   └── services/
│
├── ai/
│   ├── agents/
│   ├── prompts/
│   ├── tools/
│   ├── workflows/
│   ├── evaluators/
│   └── clients/
│
├── retrieval/
│   ├── ingestion/
│   ├── chunking/
│   ├── embeddings/
│   ├── retrieval/
│   └── reranking/
│
├── infrastructure/
│   ├── db/
│   ├── redis/
│   └── observability/
│
└── tests/
```

Do not force every feature into this structure if it increases complexity unnecessarily.

Architecture should serve the feature.

---

# 20. Recommended TOEIC Pilot AI Workflow

The flagship AI workflow should demonstrate:

```text
Question Specification
        ↓
Planner
        ↓
Content Retrieval
        ↓
Generator
        ↓
Structured Output
        ↓
Deterministic Validator
        ↓
AI Evaluator
        ↓
        ┌───────────────┐
        │ Pass?         │
        └───────┬───────┘
            Yes │ No
                │
        Publish │
                ↓
             Revise
                ↓
             Validate
```

With:

```text
Prompt Versioning
Evaluation Dataset
Regression Tests
Tracing
Token Tracking
Cost Tracking
Error Analysis
```

This workflow should become the reference implementation for future AI features.

---

# 21. Avoid Overengineering

Production-grade does NOT mean:

```text
20 microservices
+
Kubernetes
+
Kafka
+
complex agent framework
+
multiple databases
```

Production-grade means:

```text
correct architecture
+
measurable quality
+
reliable behavior
+
observable failures
+
controlled cost
+
safe execution
+
maintainable code
```

Prefer the simplest architecture that satisfies those requirements.

---

# 22. Decision Framework

Before introducing a technology, ask:

### Do we need an LLM?

If deterministic code solves it → don't use an LLM.

### Do we need RAG?

If the model already knows the required information and freshness is irrelevant → RAG may not be necessary.

### Do we need an agent?

If the workflow is deterministic → use a normal workflow.

### Do we need a framework?

If a small amount of application code solves the problem → avoid framework complexity.

### Do we need another model?

Only after measuring the current model's limitations.

### Do we need another database?

Only when the current architecture has a demonstrated requirement.

---

# 23. Engineering Quality Bar

For every AI feature, the target progression is:

```text
Level 0
LLM demo

Level 1
Working AI feature

Level 2
Structured + validated AI feature

Level 3
Evaluated AI feature

Level 4
Observable AI feature

Level 5
Production-grade AI system
```

TOEIC Pilot should progressively move important workflows toward **Level 5**.

---

# 24. Final Rule for AI Coding Agents

Before making a change, ask:

> **Can this system tell us whether the change made it better or worse?**

If the answer is no:

```text
Implement evaluation first.
```

Then ask:

> **If this fails in production, can an engineer understand why?**

If the answer is no:

```text
Add observability.
```

Then ask:

> **Can this component fail safely?**

If the answer is no:

```text
Add validation, limits, permissions, and failure handling.
```

The ultimate goal is not:

```text
"Make the LLM produce a good answer."
```

The goal is:

```text
Build an AI system whose behavior can be
designed,
tested,
measured,
observed,
debugged,
and continuously improved.
```

---

# 25. Short Checklist for Every PR

```text
[ ] Is deterministic logic separated from LLM logic?
[ ] Is the AI workflow explicit?
[ ] Is state explicit?
[ ] Are tool inputs/outputs typed?
[ ] Is the prompt versioned?
[ ] Is structured output validated?
[ ] Is there an evaluation dataset?
[ ] Are quality metrics defined?
[ ] Are regression cases covered?
[ ] Are tokens/cost/latency observable?
[ ] Are failure paths tested?
[ ] Is prompt injection considered?
[ ] Is unnecessary PII excluded?
[ ] Are tool permissions restricted?
[ ] Does the feature have evidence that it works?
```

**If a feature cannot be evaluated, observed, and safely failed, it is not finished.**