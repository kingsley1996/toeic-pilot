# SPEC — Personalized TOEIC Study Planner

**Status:** V1 ĐÃ DỰNG một phần đáng kể — pipeline tất định §5–§13, §16–§23,
§26–§27, §34–§35 sống trong `app/services/study_planner.py`; calendar
`STUDY-PLAN-CALENDAR.md` là mô tả hành vi HIỆN TẠI (tệp này chỉ là phạm vi
mong muốn). Chưa có: weekly evaluation (§31), UI plan versions (§29),
auto-replan (§32), LLM responsibilities (§24 — planner V2 tồn tại nhưng sau
flag). Trạng thái công việc: `ROADMAP.md`.  
**Scope:** TOEIC Pilot MVP  
**Goal:** Generate an adaptive study plan from `target score + exam date + available study time + 84-question diagnostic result`.

---

## 1. Objective

Build a Study Planner that answers:

> Based on what the user currently knows, their target score, exam date, and available study time, what should they study next?

The planner must use the **existing taxonomy labels attached to diagnostic questions**.

Core flow:

```text
Goal + 84Q Diagnostic
        ↓
Skill Profile
        ↓
TOEIC / CEFR Estimate
        ↓
Gap Analysis
        ↓
Priority Engine
        ↓
Roadmap
        ↓
Weekly Plan
        ↓
Daily Tasks
        ↓
Validation
        ↓
Study Plan
        ↓
Learning Events
        ↓
Re-plan
```

---

## 2. Inputs

Required:

```json
{
  "target_score": 700,
  "exam_date": "2026-12-20",
  "daily_minutes": 90,
  "study_days_per_week": 6,
  "diagnostic_id": "diag_001"
}
```

Constraints:

- `target_score` must be a valid TOEIC target.
- `exam_date` must be in the future.
- `daily_minutes > 0`.
- `study_days_per_week` must be between 1 and 7.
- `diagnostic_id` must belong to the user.
- Diagnostic must be completed.

---

## 3. Existing Diagnostic Contract

Diagnostic contains 84 questions covering all 7 TOEIC Parts.

Each question already has taxonomy metadata.

Example:

```json
{
  "question_id": "p7-071",
  "part": 7,
  "taxonomy_id": "p7_inference",
  "difficulty": "medium",
  "correct": false,
  "response_time_ms": 92000
}
```

The Planner MUST NOT re-classify questions.

Taxonomy is the source of truth for skill analysis.

---

## 4. Diagnostic Snapshot

Never overwrite a completed diagnostic.

Store a snapshot:

```text
diagnostic_attempt
├── user_id
├── test_type
├── completed_at
├── total_questions
├── correct
├── estimated_listening
├── estimated_reading
├── estimated_total
├── score_range
└── cefr
```

Question results remain associated with the diagnostic attempt.

---

## 5. Skill Profile

Aggregate diagnostic performance by `taxonomy_id`.

For each taxonomy:

```json
{
  "taxonomy_id": "p7_inference",
  "attempts": 6,
  "correct": 2,
  "accuracy": 0.33,
  "avg_response_time_ms": 92000,
  "confidence": "medium",
  "status": "weak"
}
```

Minimum metrics:

- attempts
- correct
- accuracy
- confidence
- status

Optional:

- response time
- difficulty distribution
- recent performance

---

## 6. Skill Status

Use:

```text
STRONG
STABLE
DEVELOPING
WEAK
INSUFFICIENT_DATA
```

Do not mark a skill as strongly weak when evidence is insufficient.

Suggested evidence thresholds:

```text
1–2 attempts → very low confidence
3–4 attempts → low confidence
5–7 attempts → medium confidence
8+ attempts  → high confidence
```

Thresholds must be configurable.

---

## 7. Score Estimation

Score estimation is deterministic or handled by a dedicated scoring service.

Input:

```text
84-question diagnostic result
```

Output:

```json
{
  "listening": 285,
  "reading": 240,
  "total": 525,
  "range": {
    "min": 490,
    "max": 560
  },
  "confidence": "medium"
}
```

Rules:

- LLM MUST NOT calculate TOEIC score.
- Estimated score is not an official TOEIC score.
- Preserve score range and confidence when available.

---

## 8. CEFR Estimation

Use the estimated TOEIC result and available diagnostic evidence.

Output:

```json
{
  "level": "B1",
  "confidence": "medium"
}
```

The UI must label this as an estimate.

LLM MUST NOT invent CEFR mappings.

---

## 9. Target Gap

Calculate:

```text
score_gap = target_score - estimated_total
days_remaining = exam_date - today
weeks_remaining = ceil(days_remaining / 7)
weekly_capacity = daily_minutes × study_days_per_week
```

Example:

```text
Current: 525
Target: 700
Gap: +175
Study time: 90 min/day
6 days/week
Capacity: 540 min/week
```

---

## 10. Feasibility

Classify the plan:

```text
FEASIBLE
CHALLENGING
HIGH_RISK
```

Consider:

- score gap
- weeks remaining
- weekly study capacity
- diagnostic performance

Never guarantee that the user will reach the target.

The planner may state that a target is ambitious or high-risk.

---

## 11. Priority Engine

Calculate a priority score for every taxonomy skill with sufficient evidence.

Concept:

```text
priority =
    weakness
  × evidence_confidence
  × toeic_relevance
  × target_relevance
  × improvement_potential
  × time_sensitivity
```

The exact formula must be deterministic and configurable.

LLM must not freely invent priority values.

---

## 12. Priority Inputs

### Weakness

Derived from performance:

```text
weakness = 1 - accuracy
```

Use smoothing when sample size is small.

### Evidence confidence

Based on attempts.

### TOEIC relevance

Configured in taxonomy metadata.

Example:

```json
{
  "taxonomy_id": "p7_inference",
  "toeic_relevance": 0.9
}
```

### Target relevance

How relevant the skill is to the user's current score gap and target.

### Improvement potential

Prefer skills with meaningful room for improvement.

### Time sensitivity

Increase priority when the exam date is close.

---

## 13. Priority Limits

Do not expose 10+ weaknesses as equal priorities.

Each phase should have:

```text
Top 3–5 priority skills
```

Strong skills receive maintenance practice rather than intensive allocation.

---

## 14. Learning Objectives

Convert taxonomy IDs into user-readable objectives.

Example:

```text
p7_inference
→ Identify implied information in Part 7 passages.

p2_indirect_response
→ Recognize indirect responses to Part 2 questions.

p5_preposition
→ Select prepositions based on grammar and collocation.
```

Objectives should come from taxonomy metadata/templates when possible.

LLM may improve wording but must preserve the underlying taxonomy.

---

## 15. Roadmap

Study plan has:

```text
Plan
 └── Phases
      └── Weeks
           └── Days
                └── Tasks
```

Recommended phase structure:

```text
Foundation
→ Weakness Development
→ Integrated Practice
→ Mock Tests & Remediation
→ Final Preparation
```

Phases are dynamic based on `weeks_remaining`.

Do not force all five phases when the available time is short.

---

## 16. Phase Strategy

### Foundation

Focus on:

- foundational grammar
- core vocabulary
- basic TOEIC strategies
- high-confidence weaknesses

### Weakness Development

Focus on:

- top taxonomy priorities
- targeted practice
- vocabulary / grammar remediation
- dictation where relevant

### Integrated Practice

Focus on:

- mixed Parts
- mixed taxonomy skills
- timed practice
- realistic TOEIC context

### Mock Tests & Remediation

Focus on:

- mini tests
- full tests
- error analysis
- targeted remediation

### Final Preparation

Focus on:

- exam simulation
- time management
- high-value review
- maintenance

Avoid introducing large amounts of new content immediately before the exam.

---

## 17. Task Types

Planner may only generate supported task types.

Example:

```text
VOCABULARY
COLLOCATION
GRAMMAR
DICTATION
PART_PRACTICE
MIXED_PRACTICE
MINI_TEST
FULL_TEST
ERROR_REVIEW
AI_EXPLANATION
```

Task types must be configured by the application.

LLM cannot create arbitrary task types.

---

## 18. Task Contract

Every task must contain:

```json
{
  "type": "PART_PRACTICE",
  "part": 7,
  "taxonomy_ids": ["p7_inference"],
  "duration_minutes": 25,
  "question_count": 5,
  "objective": "Identify implied information...",
  "reason": "High-priority weakness"
}
```

Required:

- task type
- duration
- objective
- target taxonomy or learning area
- valid module/action reference

---

## 19. Existing Learning Modules

Tasks must map to existing TOEIC Pilot modules.

Examples:

```text
VOCABULARY
→ Vocabulary module

COLLOCATION
→ Collocation module

DICTATION
→ Dictation module

PART_PRACTICE
→ TOEIC Practice module

ERROR_REVIEW
→ Review / analysis module
```

Do not create duplicate learning systems inside Planner.

Planner orchestrates existing modules.

---

## 20. Daily Allocation

Daily tasks must fit the user's available time.

Example:

```text
90 minutes

Vocabulary       15m
Grammar          20m
Part 2           20m
Part 7           25m
Error Review     10m
--------------------
Total             90m
```

Hard rule:

```text
sum(task.duration) <= daily_minutes
```

---

## 21. Weekly Allocation

Hard rule:

```text
sum(weekly task duration)
<= daily_minutes × study_days_per_week
```

Reserve some capacity for review/buffer when possible.

Example:

```text
540 min capacity
450–500 min planned
40–90 min buffer/review
```

---

## 22. Avoid Equal Part Distribution

Do NOT automatically distribute time equally across Part 1–7.

Example:

```text
P1  → maintenance
P2  → high priority
P3  → medium
P4  → medium
P5  → high
P6  → medium
P7  → very high
```

Allocation must follow the priority engine.

---

## 23. Strength Maintenance

If a taxonomy is already strong:

```text
STRONG
→ low-frequency maintenance
```

Do not spend a large portion of the user's limited study time optimizing an already strong skill.

---

## 24. LLM Responsibilities

LLM MAY:

- compose roadmap explanations
- create readable learning objectives
- explain why priorities were selected
- compose weekly summaries
- suggest task sequencing within hard constraints
- summarize progress
- generate adaptive recommendations

LLM MUST NOT:

- calculate TOEIC score
- calculate CEFR mapping
- calculate dates
- exceed time budget
- invent taxonomy IDs
- invent task types
- ignore completed tasks
- override hard constraints

---

## 25. LLM Structured Output

LLM output must follow a strict schema.

Example:

```json
{
  "phase_summary": "Focus on high-impact Reading weaknesses.",
  "weekly_focus": [
    {
      "taxonomy_id": "p7_inference",
      "objective": "Identify implied information...",
      "reason": "Low diagnostic accuracy and high priority."
    }
  ]
}
```

Validate using Pydantic on the API side.

If validation fails:

```text
LLM output
   ↓
Schema validation
   ↓
Repair / regenerate
```

---

## 26. Planner Workflow

```text
1. Load user goal
2. Load latest diagnostic
3. Load taxonomy metadata
4. Aggregate taxonomy performance
5. Estimate TOEIC
6. Estimate CEFR
7. Calculate score gap
8. Calculate time budget
9. Evaluate feasibility
10. Calculate taxonomy priorities
11. Select top priorities
12. Build phases
13. Allocate weekly capacity
14. Generate objectives
15. Generate tasks
16. Validate plan
17. Persist plan version
18. Return plan
```

---

## 27. Validation

Validate:

```text
✓ target score is valid
✓ exam date is valid
✓ diagnostic belongs to user
✓ diagnostic is completed
✓ taxonomy IDs exist
✓ task types exist
✓ modules exist
✓ daily time <= daily budget
✓ weekly time <= weekly capacity
✓ phase dates are valid
✓ tasks do not target invalid taxonomy
✓ mock tests occur before exam
✓ plan contains review
```

No invalid plan may be persisted as active.

---

## 28. Plan Persistence

Recommended entities:

```text
study_plans
study_plan_versions
study_plan_phases
study_plan_weeks
study_plan_days
study_plan_tasks
```

Relationships:

```text
study_plan
  ↓
version
  ↓
phase
  ↓
week
  ↓
day
  ↓
task
```

Store the diagnostic ID used to create each plan version.

---

## 29. Plan Versioning

Never overwrite the original plan.

Example:

```text
v1 → initial diagnostic
v2 → week 2 evaluation
v3 → mock test #1
v4 → target changed
```

Each version stores:

```text
version
reason
created_at
diagnostic_id / evaluation_id
```

---

## 30. Learning Events

Every completed learning activity should produce an event.

Example:

```json
{
  "user_id": "user_001",
  "task_id": "task_123",
  "taxonomy_ids": ["p7_inference"],
  "questions": 10,
  "correct": 6,
  "accuracy": 0.60,
  "duration_seconds": 720,
  "completed_at": "..."
}
```

Learning events become the input for adaptive planning.

---

## 31. Weekly Evaluation

At the end of a week calculate:

```text
task completion
study minutes
taxonomy accuracy
question volume
response time
mock performance
missed tasks
```

Compare against previous performance.

Example:

```text
P7 inference
Diagnostic: 35%
Week 2:    48%
Week 4:    61%
```

---

## 32. Re-planning

Re-plan when:

```text
new diagnostic
new mock test
weekly evaluation
major performance change
target score changed
exam date changed
available study time changed
```

Do not regenerate the entire history.

Process:

```text
Current plan
   ↓
Current progress
   ↓
Recalculate priorities
   ↓
Preserve completed work
   ↓
Adjust future tasks
   ↓
Create new plan version
```

---

## 33. Adaptive Example

Initial:

```text
P7 inference = 35%
Priority = HIGH
```

After training:

```text
P7 inference = 65%
```

Planner should reduce its priority and potentially increase another weakness:

```text
P7 inference → MEDIUM / maintenance
P5 preposition → HIGH
```

The system must adapt based on evidence, not keep the original allocation forever.

---

## 34. User-facing Result

The plan should show:

```text
TOEIC Study Plan

Current estimate: 525
CEFR: B1
Target: 700
Gap: +175
Exam: 20 Dec 2026

Plan status:
Challenging

Top focus:
1. Part 7 — Inference
2. Part 2 — Indirect responses
3. Part 5 — Prepositions
```

Then:

```text
This week
5h 30m

Monday
Vocabulary + Part 5

Tuesday
Part 7 inference

Wednesday
Part 2 + Dictation

...
```

---

## 35. "Why This Plan?"

Generate an explanation from structured facts.

Example:

```text
Bạn đang ở khoảng 525 TOEIC và đặt mục tiêu 700.

Diagnostic cho thấy Reading đang yếu hơn Listening.
Part 7 inference có accuracy thấp và là skill có priority cao.
Part 2 indirect responses cũng cần cải thiện.

Vì vậy giai đoạn đầu ưu tiên các skill này,
trong khi những skill đã mạnh chỉ được duy trì.
```

The explanation must be grounded in actual stored metrics.

---

## 36. API

### Create

```http
POST /api/study-plans
```

Request:

```json
{
  "target_score": 700,
  "exam_date": "2026-12-20",
  "daily_minutes": 90,
  "study_days_per_week": 6,
  "diagnostic_id": "diag_001"
}
```

### Current Plan

```http
GET /api/study-plans/current
```

### Week

```http
GET /api/study-plans/current/weeks/{week_number}
```

### Complete Task

```http
POST /api/study-plans/tasks/{task_id}/complete
```

### Evaluate

```http
POST /api/study-plans/current/evaluate
```

### Re-plan

```http
POST /api/study-plans/current/replan
```

---

## 37. Suggested Backend Structure

```text
app/
├── diagnostic/
│   ├── scoring.py
│   ├── skill_analysis.py
│   └── service.py
│
├── taxonomy/
│   ├── repository.py
│   └── service.py
│
├── planning/
│   ├── priority.py
│   ├── feasibility.py
│   ├── roadmap.py
│   ├── task_allocator.py
│   ├── validator.py
│   ├── planner.py
│   └── replan.py
│
├── learning/
│   ├── events.py
│   ├── progress.py
│   └── evaluation.py
│
└── ai/
    ├── planner_agent.py
    ├── schemas/
    └── prompts/
```

---

## 38. MVP Implementation

### V1 — Initial Plan

Implement:

```text
Diagnostic
→ Taxonomy aggregation
→ Score / CEFR
→ Target gap
→ Priority engine
→ Feasibility
→ Roadmap
→ Daily tasks
→ Validation
→ Persistence
```

### V2 — Progress

Add:

```text
Task completion
→ Learning events
→ Weekly evaluation
→ Progress dashboard
```

### V3 — Adaptive Planner

Add:

```text
Performance
→ Re-rank priorities
→ Reallocate time
→ Adjust future tasks
→ New plan version
```

Do not build a complex autonomous agent before V1/V2 works reliably.

---

## 39. Evaluation

Planner quality should be measurable.

### Constraint validity

```text
% plans satisfying all hard constraints
Target: >99%
```

### Taxonomy alignment

Generated task must match its target taxonomy.

### Workload validity

```text
planned_minutes <= available_minutes
```

### Personalization

Two users with different weaknesses should receive materially different priorities/tasks.

### Adaptation

When a skill improves, its priority should change appropriately.

### Plan stability

Minor performance changes should not cause unnecessary full-plan rewrites.

---

## 40. Definition of Done

- [ ] User can submit target score
- [ ] User can submit exam date
- [ ] User can submit available study time
- [ ] Latest 84Q diagnostic can be loaded
- [ ] Existing taxonomy is consumed
- [ ] Taxonomy performance is aggregated
- [ ] Skill confidence is calculated
- [ ] TOEIC estimate is returned
- [ ] CEFR estimate is returned
- [ ] Target gap is calculated
- [ ] Feasibility is calculated
- [ ] Priorities are ranked
- [ ] Roadmap is generated
- [ ] Weekly plan is generated
- [ ] Daily tasks are generated
- [ ] Tasks map to existing modules
- [ ] Time constraints are enforced
- [ ] LLM output is schema validated
- [ ] Plan is persisted
- [ ] Plan versions are supported
- [ ] Learning events are recorded
- [ ] Weekly evaluation works
- [ ] Re-planning preserves completed work
- [ ] Planner can adapt future tasks
- [ ] Automated planner evaluation exists

---

## 41. Core Principle

The Planner is not a generic:

```text
"Create a TOEIC study plan."
```

It is an evidence-based pipeline:

```text
84Q answers
   ↓
Existing taxonomy
   ↓
Skill profile
   ↓
Current score / CEFR
   ↓
Target gap
   ↓
Priority
   ↓
Available time
   ↓
Study roadmap
   ↓
Concrete learning tasks
   ↓
Performance events
   ↓
Adaptive re-planning
```

The system should answer one concrete question every day:

> **Given what this user currently knows, their target, their deadline, and their available time, what is the highest-value TOEIC activity they should do next?**
