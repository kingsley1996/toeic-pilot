# PLAN — Personalized TOEIC Study Plan Engine

> Trạng thái: PROPOSED  
> Product: TOEIC Pilot  
> Mục tiêu: Từ `target score + exam date + thời gian học + kết quả diagnostic 84 câu`, tạo một kế hoạch học TOEIC cá nhân hóa, có thể giải thích, validate và tự điều chỉnh theo tiến độ.

---

## 1. Mục tiêu

Xây dựng một **Personalized Learning Planner** sử dụng kết quả bài diagnostic TOEIC rút gọn 84 câu làm baseline.

Input chính:

- Target TOEIC score
- Exam date
- Available study time/day
- Study days/week
- Kết quả 84 câu diagnostic
- Taxonomy label đã được gắn cho từng câu hỏi

Output:

1. Estimated TOEIC score
2. Estimated CEFR
3. Confidence / estimation range
4. Learner skill profile
5. Strengths
6. Weaknesses
7. Priority learning areas
8. Multi-week roadmap
9. Weekly plans
10. Daily learning tasks
11. Rationale giải thích tại sao task được chọn
12. Progress milestones
13. Cơ chế re-plan khi user có dữ liệu mới

Nguyên tắc cốt lõi:

> Không lập kế hoạch từ tổng điểm בלבד. Lập kế hoạch từ `taxonomy → skill profile → target gap → priority → learning tasks`.

---

# 2. Problem Definition

Một user có thể có cùng TOEIC score nhưng cần kế hoạch hoàn toàn khác nhau.

Ví dụ:

```text
User A
TOEIC estimated: 550
Listening: strong
Reading: weak
Main weakness: Part 7 inference
```

và:

```text
User B
TOEIC estimated: 550
Listening: weak
Reading: medium
Main weakness: Part 2 indirect response
```

Không thể dùng cùng một study plan.

Planner phải trả lời được:

```text
1. User đang ở đâu?
2. User muốn đến đâu?
3. Khoảng cách là bao nhiêu?
4. Skill nào đang cản trở target?
5. Skill nào có khả năng cải thiện tốt nhất?
6. Có bao nhiêu thời gian?
7. Nên học gì trước?
8. Mỗi tuần học gì?
9. Mỗi ngày làm task nào?
10. Khi performance thay đổi thì plan thay đổi ra sao?
```

---

# 3. Existing Diagnostic Data

Diagnostic test gồm 84 câu và đã có taxonomy label cho từng question.

Planner **không cần tự suy luận taxonomy từ câu hỏi**.

Đây là một lợi thế lớn.

Mỗi question nên có tối thiểu:

```json
{
  "question_id": "p5-034",
  "part": 5,
  "taxonomy": {
    "category": "grammar",
    "skill": "word_form",
    "subskill": "noun_vs_adjective"
  },
  "difficulty": "medium",
  "correct": false,
  "response_time_ms": 18300
}
```

Nếu hệ thống hiện tại có taxonomy sâu hơn thì giữ nguyên taxonomy hiện có.

Planner chỉ cần consume taxonomy như một **skill ontology**.

---

# 4. Không Hard-code Taxonomy vào Planner

Planner không nên chứa logic kiểu:

```python
if part == 5:
    ...
```

ở mọi nơi.

Thay vào đó tạo abstraction:

```text
Taxonomy
   ↓
Skill
   ↓
Question
   ↓
Performance
```

Ví dụ:

```text
Part 5
 ├── Grammar
 │    ├── Verb tense
 │    ├── Subject-verb agreement
 │    ├── Word form
 │    ├── Preposition
 │    └── Relative clause
 │
 └── Vocabulary
      ├── Collocation
      └── Word meaning
```

Taxonomy phải là source of truth cho diagnosis.

---

# 5. Diagnostic Result Model

Sau khi user hoàn thành 84 câu, tạo immutable diagnostic snapshot.

```json
{
  "diagnostic_id": "diag_001",
  "user_id": "user_001",
  "test_type": "toeic_short_84",
  "completed_at": "...",
  "total_questions": 84,
  "correct": 48,
  "estimated_score": {
    "total": 525,
    "listening": 285,
    "reading": 240,
    "range": [490, 560],
    "confidence": "medium"
  },
  "cefr": {
    "level": "B1",
    "confidence": "medium"
  }
}
```

Không overwrite diagnostic cũ.

Mỗi lần test mới tạo một snapshot mới.

---

# 6. Skill Performance Aggregation

Từ question-level results tạo skill-level performance.

Ví dụ:

```text
P7 / inference

attempts = 6
correct = 2
accuracy = 0.33
```

Nhưng không chỉ lưu accuracy.

Nên có:

```text
attempts
correct
accuracy
weighted_accuracy
avg_response_time
difficulty_distribution
recent_accuracy
confidence
```

Ví dụ:

```json
{
  "taxonomy_id": "p7_inference",
  "attempts": 6,
  "correct": 2,
  "accuracy": 0.33,
  "avg_response_time_ms": 92000,
  "difficulty": {
    "easy": 1,
    "medium": 3,
    "hard": 2
  }
}
```

---

# 7. Sample Size Problem

Không được kết luận:

```text
1/1 correct → strong
```

hoặc:

```text
0/1 → severe weakness
```

Mỗi skill cần confidence dựa trên số lượng câu.

Đề xuất:

```text
1–2 attempts  → very low confidence
3–4 attempts  → low confidence
5–7 attempts  → medium confidence
8+ attempts   → higher confidence
```

Ngưỡng có thể điều chỉnh sau khi có dữ liệu thật.

UI nên phân biệt:

```text
Weak — high confidence
Weak — medium confidence
Potential weakness — low confidence
```

---

# 8. Skill Status

Mỗi taxonomy skill được phân loại:

```text
STRONG
STABLE
DEVELOPING
WEAK
INSUFFICIENT_DATA
```

Ví dụ:

```text
P5 word_form
accuracy = 83%
→ STRONG

P7 inference
accuracy = 33%
→ WEAK

P4 future_action
accuracy = 50%
attempts = 2
→ INSUFFICIENT_DATA / DEVELOPING
```

Không nên gọi skill là weak nếu evidence chưa đủ.

---

# 9. Estimated TOEIC Score

Score estimator là module deterministic/separate.

```text
Diagnostic answers
       ↓
Listening raw performance
Reading raw performance
       ↓
Score estimation model
       ↓
Estimated L/R
       ↓
Estimated total
       ↓
Confidence range
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

Không để LLM tự tính score.

LLM chỉ giải thích kết quả.

---

# 10. CEFR Estimation

CEFR estimate cũng là một module riêng.

```text
Estimated TOEIC
+
Diagnostic evidence
       ↓
CEFR mapping
```

Output:

```json
{
  "level": "B1",
  "confidence": "medium"
}
```

UI wording:

> Estimated CEFR: B1

Không trình bày diagnostic CEFR như một chứng chỉ chính thức.

---

# 11. Target Analysis

Input:

```text
current_estimated_score = 525
target_score = 700
exam_date = 2026-12-20
```

Tính:

```text
score_gap = 175
days_remaining = ...
weeks_remaining = ...
```

Ví dụ:

```text
Current: 525
Target: 700
Gap: +175
Time: 14 weeks
```

---

# 12. Feasibility Analysis

Planner phải đánh giá target có khả thi tương đối hay không.

Input:

```text
score gap
weeks remaining
minutes/day
days/week
current performance
```

Output:

```text
FEASIBLE
CHALLENGING
HIGH_RISK
INSUFFICIENT_TIME
```

Không được hứa:

> Bạn chắc chắn đạt 700.

Nên dùng:

> Mục tiêu 700 là challenging nhưng có thể theo đuổi với 90 phút/ngày trong 14 tuần.

---

# 13. Available Study Capacity

Tính:

```text
daily_minutes
×
study_days_per_week
=
weekly_minutes
```

Ví dụ:

```text
90 × 6 = 540 minutes/week
```

Planner phải đảm bảo:

```text
sum(task.duration)
<= weekly_minutes
```

Có thể reserve một phần cho review / buffer.

Ví dụ:

```text
540 min
├── 450 min planned learning
└── 90 min buffer/review
```

---

# 14. Priority Engine

Đây là core của Planner.

Mỗi taxonomy skill nhận priority score.

Conceptual formula:

```text
priority =
    weakness
  × evidence_confidence
  × TOEIC_relevance
  × target_relevance
  × improvement_potential
  × time_sensitivity
```

Không cần expose công thức này cho user.

---

# 15. Weakness Score

Ví dụ:

```python
weakness = 1 - accuracy
```

Accuracy:

```text
90% → 0.10
70% → 0.30
50% → 0.50
30% → 0.70
```

Có thể dùng smoothing khi sample size nhỏ.

---

# 16. Evidence Confidence

Ví dụ:

```text
attempts = 1 → 0.2
attempts = 3 → 0.5
attempts = 5 → 0.7
attempts = 8 → 0.9
```

Mục tiêu là tránh overreact với một câu hỏi.

---

# 17. TOEIC Relevance

Một số taxonomy xuất hiện nhiều hơn hoặc có impact lớn hơn.

Có thể định nghĩa metadata:

```json
{
  "taxonomy_id": "p7_inference",
  "toeic_relevance": 0.9
}
```

Không hard-code trong prompt.

Đưa vào taxonomy configuration.

---

# 18. Target Relevance

Ví dụ user target 700.

Planner có thể ưu tiên skills thuộc vùng cần thiết để vượt ngưỡng target.

```text
525 → 700
```

khác:

```text
650 → 700
```

Người 650 không cần roadmap giống người 525.

---

# 19. Improvement Potential

Nếu user:

```text
P1 = 95%
```

thì thêm 5 điểm phần trăm có thể không đáng đầu tư.

Nếu:

```text
P7 inference = 35%
```

có room for improvement lớn hơn.

Concept:

```text
improvement_potential = 1 - normalized_performance
```

Sau này có thể thay bằng model dựa trên historical learner data.

---

# 20. Time Sensitivity

Skill có thể được ưu tiên hơn khi:

```text
exam date gần
AND
skill có impact cao
```

Ví dụ:

```text
14 weeks:
Foundation + skill building

4 weeks:
Exam strategy + timed practice

1 week:
Simulation + maintenance
```

---

# 21. Priority Output

Ví dụ:

```json
{
  "priorities": [
    {
      "taxonomy": "p7_inference",
      "score": 0.91,
      "status": "weak",
      "reason_codes": [
        "low_accuracy",
        "high_relevance",
        "large_improvement_room"
      ]
    },
    {
      "taxonomy": "p2_indirect_response",
      "score": 0.84,
      "status": "weak"
    },
    {
      "taxonomy": "p5_preposition",
      "score": 0.78,
      "status": "weak"
    }
  ]
}
```

---

# 22. Learning Objective Generation

Không đưa raw taxonomy trực tiếp cho user.

Chuyển:

```text
p7_inference
```

thành:

```text
Identify implied information in TOEIC Part 7 passages.
```

Chuyển:

```text
p2_indirect_response
```

thành:

```text
Recognize answers that respond indirectly to WH and yes/no questions.
```

LLM có thể giúp tạo explanation, nhưng objective nên có template / metadata ổn định.

---

# 23. Roadmap Architecture

Study plan có 4 tầng:

```text
Plan
 ├── Phases
 │    ├── Weeks
 │    │    ├── Days
 │    │    │    └── Tasks
```

Ví dụ:

```text
14-week plan

Phase 1 — Foundation
Week 1–2

Phase 2 — Weakness Development
Week 3–6

Phase 3 — Integrated TOEIC Practice
Week 7–10

Phase 4 — Mock Tests & Remediation
Week 11–13

Phase 5 — Final Preparation
Week 14
```

Số phase/week phải dynamic theo exam date.

---

# 24. Phase Rules

## Foundation

Mục tiêu:

```text
repair foundational weaknesses
build core vocabulary/grammar
introduce strategies
```

Không dành toàn bộ thời gian cho full tests.

---

## Weakness Development

Mục tiêu:

```text
high-priority taxonomy skills
```

Tập trung vào top weaknesses.

---

## Integrated Practice

Kết hợp:

```text
multiple parts
multiple taxonomy skills
timed practice
```

---

## Mock Test

Tăng:

```text
full/section tests
timed practice
error analysis
```

---

## Final Preparation

Không nhồi kiến thức mới.

Tập trung:

```text
simulation
high-value review
time management
confidence
```

---

# 25. Task Types

Planner chỉ được sử dụng task type đã được hệ thống hỗ trợ.

Ví dụ:

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

Không để LLM tạo task type tùy ý.

---

# 26. Task → Existing Product Module

Mỗi task phải map tới module thật trong TOEIC Pilot.

Ví dụ:

```json
{
  "task_type": "practice",
  "part": 7,
  "taxonomy": ["p7_inference"],
  "question_count": 5,
  "duration_minutes": 25
}
```

Vocabulary:

```json
{
  "task_type": "vocabulary",
  "topic": "business",
  "taxonomy": ["business_collocation"],
  "duration_minutes": 15
}
```

Dictation:

```json
{
  "task_type": "dictation",
  "part": 3,
  "taxonomy": ["p3_detail"],
  "duration_minutes": 15
}
```

---

# 27. Daily Plan Generator

Ví dụ user có 90 phút.

```text
DAY 17 — 90 minutes

Vocabulary
15m

Grammar
20m

Part 2
20m

Part 7
25m

Error review
10m
```

Mỗi task phải có:

```text
id
type
duration
part
taxonomy
objective
question_count
mode
```

---

# 28. Task Allocation

Không chia thời gian đều cho 7 Part.

Ví dụ:

```text
P1      5%
P2     15%
P3     10%
P4     10%
P5     15%
P6     10%
P7     30%
Review 15%
```

Chỉ là ví dụ.

Allocation thực tế phải dựa trên priority engine.

---

# 29. Strength Maintenance

Skill mạnh không biến mất khỏi plan hoàn toàn.

Ví dụ:

```text
P1 accuracy = 90%
```

Không cần intensive training.

Có thể:

```text
maintenance = 5–10% effort
```

Mục tiêu:

> maintain, không optimize.

---

# 30. Weakness Concentration

Một user không nên có 10 priorities cùng lúc.

Đề xuất:

```text
Top 3–5 priority skills
```

mỗi phase.

Ví dụ:

```text
Phase 1
1. P7 inference
2. P2 indirect response
3. P5 preposition
```

Khi skill được cải thiện, priority engine re-rank.

---

# 31. LLM Role

LLM KHÔNG làm:

```text
score calculation
days calculation
duration validation
taxonomy classification
hard constraints
```

LLM làm:

```text
interpret learner profile
generate study rationale
compose learning objectives
generate natural-language plan explanation
suggest task sequencing within constraints
summarize weekly progress
```

---

# 32. Structured Output

LLM phải trả JSON theo schema.

Ví dụ:

```json
{
  "phase_summary": "...",
  "weekly_focus": [
    {
      "taxonomy_id": "p7_inference",
      "objective": "...",
      "reason": "..."
    }
  ]
}
```

Dùng Pydantic/Zod để validate.

---

# 33. Planner Pipeline

```text
1. Load user goal
2. Load latest diagnostic
3. Load taxonomy metadata
4. Aggregate performance
5. Estimate score
6. Estimate CEFR
7. Calculate time budget
8. Calculate target gap
9. Calculate skill priorities
10. Build phases
11. Allocate weekly capacity
12. Generate learning objectives
13. Select valid task types
14. Generate daily tasks
15. Validate constraints
16. Generate explanation
17. Persist plan version
```

---

# 34. Deterministic vs AI Boundary

## Deterministic

```text
score
accuracy
sample size
confidence
days
weeks
available minutes
priority baseline
task duration
capacity
schedule constraints
validation
```

## AI-assisted

```text
rationale
objective wording
study advice
weekly explanation
progress summary
adaptive recommendation
```

Điều này giúp hệ thống predictable và dễ debug.

---

# 35. Plan Validator

Validator phải kiểm tra:

```text
✓ target > current score
✓ exam date > today
✓ no task exceeds daily budget
✓ weekly minutes <= capacity
✓ all taxonomy IDs exist
✓ all task types exist
✓ all referenced modules exist
✓ all required fields exist
✓ no duplicate impossible tasks
✓ phase dates are valid
✓ mock tests occur before exam
✓ enough review time exists
```

Nếu invalid:

```text
LLM output
   ↓
Validator
   ↓
INVALID
   ↓
Repair / regenerate
```

---

# 36. Plan Versioning

Database:

```text
study_plans
study_plan_versions
study_plan_weeks
study_plan_tasks
```

Example:

```text
Plan v1
created after diagnostic

Plan v2
created after week 2 review

Plan v3
created after mock test #1
```

Không overwrite lịch sử.

---

# 37. Re-planning Trigger

Re-plan khi:

```text
new diagnostic test
new full mock test
weekly assessment
large performance change
missed study sessions
target score changed
exam date changed
available study time changed
```

Không cần regenerate toàn bộ plan sau mỗi task.

---

# 38. Re-plan Strategy

Không reset toàn bộ.

```text
Existing plan
     ↓
Current progress
     ↓
Recalculate priorities
     ↓
Preserve completed work
     ↓
Adjust future tasks
```

Ví dụ:

```text
Original:
P7 inference = high priority

After 3 weeks:
accuracy 35% → 65%

New:
P7 inference = medium
P7 paraphrase = high
```

---

# 39. Progress Metrics

Theo dõi:

```text
skill accuracy
question volume
study minutes
task completion
streak
mock score
estimated score
time/question
error rate
```

Đặc biệt:

```text
taxonomy performance over time
```

Ví dụ:

```text
P7 inference

Diagnostic: 35%
Week 2:    48%
Week 4:    61%
Week 6:    68%
```

Đây là evidence để Planner adapt.

---

# 40. Learning Event

Mỗi activity tạo event:

```json
{
  "user_id": "...",
  "task_id": "...",
  "taxonomy_id": "p7_inference",
  "questions": 10,
  "correct": 6,
  "accuracy": 0.6,
  "duration_seconds": 720,
  "completed_at": "..."
}
```

Event là input cho future planning.

---

# 41. Weekly Evaluation

Cuối mỗi tuần:

```text
Completed tasks
+
taxonomy performance
+
time spent
+
missed tasks
+
new mistakes
```

→ tạo weekly report.

Ví dụ:

```text
Week 4

Completed: 87%

P7 inference:
35% → 58% ↑

P2 indirect:
40% → 63% ↑

P5 preposition:
42% → 45% →

Recommendation:
Continue P5
Reduce P2
Increase P7 mixed practice
```

---

# 42. Adaptive Allocation

Ví dụ weekly budget:

```text
540 minutes
```

Sau evaluation:

```text
P7 inference improved strongly
P5 still weak
```

Week tiếp:

```text
P7: 25%
P5: 30%
P2: 10%
P3/P4: 20%
Review: 15%
```

Không giữ allocation cố định.

---

# 43. Plan Explanation

UI cần có:

> Why this plan?

Ví dụ:

```text
Bạn đang ở khoảng 525 TOEIC và đặt mục tiêu 700.

Kết quả diagnostic cho thấy:
- Reading đang yếu hơn Listening.
- Part 7 inference là một trong những taxonomy có accuracy thấp nhất.
- Part 2 indirect response cũng cần cải thiện.
- Một số grammar skills đã tương đối tốt nên plan không dành quá nhiều thời gian cho chúng.

Vì vậy 4 tuần đầu ưu tiên Part 7, Part 2 và các grammar/vocabulary skill có impact cao.
```

Explanation phải được sinh từ structured facts, không hallucinate.

---

# 44. User-facing Plan

Dashboard:

```text
Your TOEIC Plan

525 → 700
14 weeks

Current level
B1

Focus
Part 7 · Part 2 · Part 5

This week
5h 30m

Progress
████████░░ 78%
```

---

# 45. Weekly View

```text
WEEK 3

Main goals
────────────────────
1. Improve P7 inference
2. Improve P5 prepositions
3. Maintain P2

Monday
Vocabulary + P5

Tuesday
P7 inference

Wednesday
P2 + Dictation

Thursday
P5 + P7

Friday
Mixed practice

Saturday
Mini test + Review

Sunday
Rest
```

---

# 46. Daily View

```text
TODAY — 90 min

15m  Vocabulary
20m  P5 Prepositions
25m  P7 Inference
20m  Part 2
10m  Error Review

[ Start today's plan ]
```

---

# 47. Milestones

Không chỉ milestone theo thời gian.

Có cả skill milestone:

```text
P7 inference
35% → 50%
```

và score milestone:

```text
525
 ↓
575
 ↓
625
 ↓
650
 ↓
700
```

Nhưng đây là **estimated milestones**, không guarantee.

---

# 48. Exam Countdown

Khi gần exam:

```text
90 days
→ learning-heavy

45 days
→ mixed practice

21 days
→ mock-heavy

7 days
→ simulation + review
```

Exam date ảnh hưởng trực tiếp đến planner.

---

# 49. Edge Cases

## Target thấp hơn current

Ví dụ:

```text
Current 650
Target 600
```

Không tạo improvement plan.

→ hỏi/cho phép user chọn:

```text
Maintain 650+
```

hoặc:

```text
Change target
```

---

## Không có exam date

Cho phép:

```text
open-ended plan
```

Nhưng nếu feature yêu cầu exam date thì validation bắt buộc.

---

## Quá ít thời gian

Ví dụ:

```text
700 target
14 weeks
20 min/day
```

Plan phải đánh dấu:

```text
HIGH_RISK
```

không tự tăng workload vượt input.

---

## Diagnostic thiếu dữ liệu

Không đủ evidence cho taxonomy:

```text
INSUFFICIENT_DATA
```

→ đưa skill đó vào low-confidence exploration, không kết luận weakness.

---

# 50. MVP Scope

## Phase 1

Implement:

```text
Diagnostic snapshot
↓
Taxonomy aggregation
↓
Estimated TOEIC
↓
Estimated CEFR
↓
Target gap
↓
Priority engine
↓
LLM roadmap
↓
Validator
↓
Persist plan
```

Chưa cần adaptive learning phức tạp.

---

# 51. MVP Phase 2

Implement:

```text
Weekly plan
↓
Daily tasks
↓
Task completion
↓
Learning events
↓
Weekly evaluation
```

---

# 52. MVP Phase 3

Implement:

```text
Adaptive planner
↓
Re-rank taxonomy
↓
Reallocate study time
↓
Regenerate future tasks
↓
Plan versioning
```

Đây mới là phần tạo giá trị lớn.

---

# 53. Suggested Backend Modules

```text
app/
├── diagnostic/
│   ├── models.py
│   ├── scoring.py
│   ├── skill_analysis.py
│   └── service.py
│
├── taxonomy/
│   ├── models.py
│   ├── repository.py
│   └── service.py
│
├── planning/
│   ├── models.py
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
    ├── prompts/
    ├── schemas/
    └── planner_agent.py
```

Tên module có thể điều chỉnh theo architecture hiện tại.

---

# 54. Suggested API

## Create plan

```http
POST /api/study-plans
```

```json
{
  "target_score": 700,
  "exam_date": "2026-12-20",
  "daily_minutes": 90,
  "study_days_per_week": 6,
  "diagnostic_id": "diag_001"
}
```

---

## Get current plan

```http
GET /api/study-plans/current
```

---

## Get week

```http
GET /api/study-plans/current/weeks/3
```

---

## Complete task

```http
POST /api/study-plans/tasks/{task_id}/complete
```

---

## Evaluate week

```http
POST /api/study-plans/current/evaluate
```

---

## Re-plan

```http
POST /api/study-plans/current/replan
```

---

# 55. Database Concept

```text
diagnostic_attempts
       │
       └── diagnostic_answers
                    │
                    └── taxonomy_id

study_plans
       │
       └── study_plan_versions
                    │
                    └── study_plan_weeks
                              │
                              └── study_plan_tasks
                                         │
                                         └── learning_events
```

Có thể giữ `taxonomy_id` trực tiếp trên performance/task để query nhanh.

---

# 56. Agent Architecture

Nếu muốn biến feature này thành AI Agent portfolio:

```text
Planner Agent
│
├── Diagnostic Tool
├── Taxonomy Tool
├── Progress Tool
├── Content Tool
├── Schedule Tool
├── Score Tool
└── Validation Tool
```

Agent state:

```text
Goal
Diagnostic
Skill Profile
Priorities
Roadmap
Current Week
Progress
Constraints
```

Agent loop:

```text
OBSERVE
   ↓
DIAGNOSE
   ↓
PLAN
   ↓
VALIDATE
   ↓
EXECUTE
   ↓
EVALUATE
   ↓
ADAPT
```

---

# 57. Không cần Agent ngay từ đầu

V1 nên dùng workflow deterministic:

```text
Service
  ↓
Priority Engine
  ↓
Planner
  ↓
LLM
  ↓
Validator
```

Khi đã có:

```text
learning events
progress history
plan versions
```

mới chuyển sang agentic architecture.

Điều này giảm complexity và giúp đánh giá chất lượng dễ hơn.

---

# 58. Evaluation

Planner phải được đánh giá như một AI system.

## Constraint accuracy

```text
% plans satisfying all hard constraints
```

Target:

```text
> 99%
```

---

## Taxonomy alignment

Kiểm tra:

> Task generated có thực sự target weakness không?

Ví dụ:

```text
priority = p7_inference

generated task = p7_vocabulary

→ bad alignment
```

---

## Workload validity

```text
planned_minutes <= available_minutes
```

---

## Personalization

So sánh 2 users:

```text
same target
different weakness
```

Plan phải khác nhau.

---

## Adaptation

Sau khi skill cải thiện:

```text
priority ranking
```

phải thay đổi hợp lý.

---

# 59. Important Design Principle

Không để AI quyết định:

> "User cần học Part 7 vì Part 7 khó."

Phải có evidence:

```text
P7 inference
accuracy = 33%
attempts = 6
confidence = medium
priority = 0.91
```

LLM chỉ biến evidence thành:

> Part 7 inference là ưu tiên cao vì đây là một trong những skill có accuracy thấp nhất và có ảnh hưởng đáng kể tới mục tiêu Reading của bạn.

---

# 60. Final Architecture

```text
                  USER GOAL
                     │
          ┌──────────┴──────────┐
          │                     │
    Target Score            Exam Date
          │                     │
          └──────────┬──────────┘
                     ↓
              TIME CONSTRAINTS
                     │
                     ↓
          ┌─────────────────────┐
          │ 84Q DIAGNOSTIC      │
          └──────────┬──────────┘
                     ↓
             QUESTION RESULTS
                     │
                     ↓
              TAXONOMY LABELS
                     │
                     ↓
             SKILL AGGREGATION
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
    TOEIC ESTIMATE          CEFR ESTIMATE
          │                     │
          └──────────┬──────────┘
                     ↓
               GAP ANALYSIS
                     ↓
              PRIORITY ENGINE
                     ↓
             FEASIBILITY CHECK
                     ↓
              ROADMAP BUILDER
                     ↓
              LLM PLAN COMPOSER
                     ↓
                VALIDATOR
                     ↓
              STUDY PLAN V1
                     │
                     ↓
              DAILY ACTIVITIES
                     │
                     ↓
             LEARNING EVENTS
                     │
                     ↓
              WEEKLY EVALUATION
                     │
                     ↓
              RE-PRIORITIZATION
                     │
                     ↓
                RE-PLANNER
                     │
                     └──────────────→ V2 → V3 → V4
```

---

# 61. Definition of Done

Feature được coi là hoàn thành khi:

- [ ] User nhập target score
- [ ] User nhập exam date
- [ ] User nhập daily study time
- [ ] System load latest 84Q diagnostic
- [ ] System sử dụng taxonomy có sẵn
- [ ] System aggregate performance theo taxonomy
- [ ] System tính confidence theo sample size
- [ ] System tạo estimated TOEIC
- [ ] System tạo estimated CEFR
- [ ] System tính target gap
- [ ] System kiểm tra feasibility
- [ ] System ranking weakness
- [ ] System tạo top priorities
- [ ] System tạo multi-week roadmap
- [ ] System tạo weekly plans
- [ ] System tạo daily tasks
- [ ] Task map được tới learning modules thật
- [ ] Daily/weekly workload không vượt budget
- [ ] LLM output được schema validation
- [ ] Plan có explanation
- [ ] Plan được versioning
- [ ] Learning events được lưu
- [ ] Weekly progress được tính
- [ ] Có thể re-plan
- [ ] Completed tasks không bị mất khi re-plan
- [ ] Planner có automated evaluation

---

# 62. Recommended Implementation Order

```text
Step 1
Freeze existing taxonomy contract

Step 2
Build diagnostic aggregation

Step 3
Build score + CEFR estimator interface

Step 4
Build skill profile

Step 5
Build priority engine

Step 6
Build feasibility engine

Step 7
Build roadmap generator

Step 8
Build task allocator

Step 9
Add LLM plan composer

Step 10
Add Pydantic/Zod validation

Step 11
Persist plan/version

Step 12
Expose API

Step 13
Build UI

Step 14
Track learning events

Step 15
Build weekly evaluation

Step 16
Build adaptive re-planning

Step 17
Evaluate planner quality
```

---

# 63. Core Philosophy

TOEIC Pilot không nên trả lời:

> "Bạn nên học TOEIC như thế nào?"

Mà nên trả lời:

> "Dựa trên chính những gì bạn đã làm sai, mục tiêu 700, thời gian còn lại và thời gian bạn có thể học mỗi ngày, **hôm nay bạn nên học gì và tại sao?**"

Diagnostic 84 câu là baseline.

Taxonomy là skill map.

Priority Engine quyết định **học gì trước**.

Planner quyết định **học khi nào**.

Learning modules quyết định **học bằng cách nào**.

Learning events cho biết **user đang tiến bộ ra sao**.

Re-planner quyết định **bước tiếp theo nên thay đổi thế nào**.

Đó là nền tảng để biến TOEIC Pilot thành một **adaptive AI learning system**, thay vì chỉ là một TOEIC practice app có thêm LLM.
