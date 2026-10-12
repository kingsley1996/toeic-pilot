# Production-Grade Agent Upgrade Plan

## 1. Mục tiêu

Graph hiện tại đã có nền tảng của một agent workflow production-oriented:

```text
State
  ↓
Write
  ↓
Structural Check
  ↓
Content Check
  ↓
Verdict
  ├── Accept
  ├── Evaluator → Revision Plan → Write ↺
  └── Escalate
```

Phần cần nâng cấp tiếp theo không phải là thêm nhiều node hơn, mà là xây các lớp production xung quanh graph:

```text
                    Production AI System
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
      Graph              Evals          Observability
        │                  │                  │
        ▼                  ▼                  ▼
   State/Nodes         Dataset          Tracing/Metrics
   Edges/Loops         Regression       Cost/Latency
        │                  │                  │
        ├────────────┬─────┴────────────┬─────┤
        ▼            ▼                  ▼     ▼
   Persistence   Human Review       Reliability Security
        │            │                  │       │
        └────────────┴──────────────────┴───────┘
                           │
                           ▼
                       Production
```

---

## 2. P0 — Structured Output cho Evaluator

### Vấn đề hiện tại

Evaluator đang trả về text có format kiểu:

```text
SUMMARY:
...

CHANGES:
- ...

PRESERVE:
- ...

RISK:
...
```

Sau đó code parse text thành `RevisionPlan`.

Cách này hoạt động được nhưng phụ thuộc vào format mà LLM có thể phá vỡ.

### Cải thiện

Dùng structured output + Pydantic schema:

```python
class RevisionPlan(BaseModel):
    summary: str
    changes: list[str]
    preserve: list[str]
    risk: Literal["low", "medium", "high"]
    should_regenerate: bool
```

Flow:

```text
Evaluator LLM
     ↓
Structured Output
     ↓
Pydantic validation
     ↓
RevisionPlan
     ↓
SlotState
```

### Nguyên tắc

- Không để graph phụ thuộc vào parsing text nếu schema có thể mô hình hóa được.
- Invalid structured output phải được xử lý như một failure có phân loại.
- Không cho evaluator tự sửa draft; evaluator chỉ tạo `RevisionPlan`.

---

## 3. P0 — Production Observability / Tracing

`RunMetrics` hiện đã có nền tảng tốt. Cần nâng cấp thành trace có thể quan sát từng node và từng revision.

### Trace context

Mỗi run nên có:

```python
class RunContext(TypedDict):
    run_id: str
    trace_id: str
    slot_id: str
    graph_version: str
    prompt_version: str
```

Mỗi node nên ghi:

```text
run_id
trace_id
slot_id
node_name
revision
model
provider
start_time
latency_ms
input_tokens
output_tokens
estimated_cost
status
error_type
```

### Ví dụ trace

```text
run_8f21 / P5-Q23
│
├── write[r1]
│   ├── model=...
│   ├── latency=3.2s
│   └── tokens=1240
│
├── structural_check[r1]
│   └── latency=0.8ms
│
├── content_check[r1]
│   └── findings=3
│
├── evaluator[r1]
│   ├── latency=4.1s
│   └── revision_plan=created
│
├── write[r2]
│   └── ...
│
└── verdict
    └── accepted
```

### Metrics tối thiểu

```text
first_pass_acceptance_rate
final_acceptance_rate
revision_rate
escalation_rate
regression_rate
persistent_error_rate
llm_error_rate
structured_output_error_rate
p50_latency
p95_latency
p99_latency
tokens_in
tokens_out
estimated_cost
```

---

## 4. P0 — Evaluation Dataset + Regression Suite

Agent production không chỉ cần chạy được; cần chứng minh rằng thay đổi graph/model/prompt không làm chất lượng giảm.

### Xây golden dataset

Tạo dataset gồm các slot đã được reviewer xác nhận:

```text
fixtures/evals/
├── part1.jsonl
├── part2.jsonl
├── part3.jsonl
├── part4.jsonl
├── part5.jsonl
├── part6.jsonl
└── part7.jsonl
```

Mỗi case nên chứa:

```json
{
  "slot_id": "P5-Q23",
  "input": "...",
  "expected_properties": [
    "single_correct_answer",
    "natural_english",
    "valid_distractors",
    "toeic_style"
  ],
  "severity_rules": {},
  "human_label": "accepted"
}
```

### Metrics cần theo dõi

```text
First-pass acceptance
Final acceptance
Revision count distribution
Escalation rate
Regression rate
False-positive checker rate
False-negative checker rate
```

Và breakdown theo:

```text
Part
Question type
Finding category
Difficulty
Model
Prompt version
Graph version
```

### Regression gate

Không cho deploy graph mới nếu benchmark quan trọng bị giảm vượt threshold đã định nghĩa.

```text
PR / Release
    ↓
Run eval suite
    ↓
Compare baseline
    ↓
┌───────────────┐
│ Within limits │──→ Deploy
└───────────────┘
        │
        └──→ Block release
```

---

## 5. P0 — Persistent Checkpoint + Resume

Graph đã có abstraction cho checkpointer. Production cần một implementation persistent thực sự thay vì chỉ dựa vào in-memory state.

### Yêu cầu

Một run cần có khả năng:

```text
start
  ↓
checkpoint
  ↓
process crash
  ↓
resume
  ↓
continue from checkpoint
```

### Checkpoint identity

```text
run_id
slot_id
revision
node
state_version
created_at
```

### Không được overwrite lịch sử

```text
checkpoint r1
checkpoint r2
checkpoint r3
```

nên có thể inspect/replay khi debug.

---

## 6. P0 — Idempotency + Concurrency Safety

Production worker có thể chạy lại cùng một slot do retry, timeout hoặc process restart.

### Rủi ro

```text
Worker A ──→ P5-Q23
Worker B ──→ P5-Q23
```

hoặc:

```text
write[r2]
   ↓ timeout
client retry
   ↓
write[r2] again
```

### Cần có idempotency key

```text
idempotency_key = run_id + slot_id + revision + node
```

Ví dụ:

```text
exam_2026_001:P5-Q23:r2:write
```

Persistence layer cần đảm bảo duplicate execution không tạo duplicate artifact/publish event.

### Concurrency rules

Một slot chỉ nên có một active revision writer tại một thời điểm.

```text
slot P5-Q23
     │
     └── lock / lease
             │
             └── one active writer
```

---

## 7. P1 — Human-in-the-Loop cho ESCALATE

`ESCALATE` hiện là terminal state. Production content pipeline nên biến nó thành review workflow.

```text
                 ESCALATE
                    │
                    ▼
              Review Queue
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       approve     edit      reject
          │         │         │
          ▼         ▼         ▼
       publish   new artifact  discard
```

Reviewer action nên được lưu:

```python
class ReviewDecision(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    reviewer_id: str
    reason: str | None
    edited_content: str | None
    created_at: datetime
```

### Feedback loop

Human corrections nên trở thành dữ liệu cho eval:

```text
Escalated case
      ↓
Human correction
      ↓
Golden dataset
      ↓
Regression test
      ↓
Future graph/model changes
```

Đây là cách biến production traffic thành quality improvement loop.

---

## 8. P1 — Error Taxonomy và Retry Policy rõ ràng

Không nên có một loại `error` chung.

### Nên phân loại

```text
LLM
├── timeout
├── rate_limit
├── provider_error
├── invalid_structured_output
└── context_limit

CONTENT
├── invalid_question
├── bad_distractor
├── ambiguity
├── grammar
└── logic

SYSTEM
├── database_error
├── checkpoint_error
├── filesystem_error
└── configuration_error
```

### Retry rule

```text
rate_limit
    → retry with backoff

provider timeout
    → bounded retry

invalid structured output
    → bounded repair/retry

content finding
    → revision loop

persistent content error
    → escalate

database/checkpoint failure
    → infrastructure failure path
```

Không dùng cùng một retry policy cho tất cả failure.

---

## 9. P1 — Versioning cho Graph, Prompt và Model

Kết quả AI cần reproducibility.

Mỗi run nên biết chính xác:

```text
model_version
prompt_version
graph_version
checker_version
schema_version
```

Ví dụ:

```text
run_8f21
├── graph=v3.4.0
├── writer_prompt=p5.v12
├── evaluator_prompt=evaluator.v7
├── checker=v2.8.1
├── model=...
└── schema=revision-plan.v2
```

Nếu chất lượng giảm sau deploy, phải trả lời được:

> Run này được tạo bởi phiên bản nào?

---

## 10. P1 — Publish Gate tách khỏi Generation Graph

Không nên coi:

```text
accepted
```

đồng nghĩa trực tiếp với:

```text
published
```

Nên có boundary:

```text
Generation Graph
      ↓
   ACCEPTED
      ↓
Publish Gate
      ↓
  ┌───┴────┐
  │        │
PASS     BLOCK
  │        │
  ▼        ▼
Publish   Review
```

Publish Gate có thể kiểm tra:

```text
required fields
schema validity
audio availability
answer uniqueness
source metadata
copyright/source policy
quality thresholds
human approval requirements
```

---

## 11. P1 — Security và Input Boundary

Graph production cần coi mọi input bên ngoài là untrusted.

### Cần validate

```text
slot input
blueprint
model output
reviewer input
artifact path
metadata
```

Đặc biệt không cho LLM output trực tiếp quyết định:

```text
filesystem path
shell command
SQL
arbitrary tool arguments
publish target
```

Nếu sau này graph có tool calling, nên giữ nguyên nguyên tắc:

```text
LLM proposes
     ↓
Schema validation
     ↓
Policy validation
     ↓
Tool execution
```

---

## 12. P1 — SLO và Operational Alerts

Sau khi có metrics cần định nghĩa operational expectations.

Ví dụ:

```text
p95 generation latency
maximum cost / slot
maximum revision count
maximum escalation rate
LLM error rate
checkpoint failure rate
```

Alert khi:

```text
escalation_rate ↑ significantly
regression_rate ↑
provider_error_rate ↑
p95_latency ↑
cost / slot ↑
```

Mục tiêu không phải chỉ biết Agent chạy hay không, mà biết:

> Agent đang chạy ổn định và chất lượng có đang thay đổi không?

---

# 13. Target Architecture sau khi nâng cấp

```text
                           ┌──────────────────────┐
                           │      API / Job       │
                           └──────────┬───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │   Run / Trace ID     │
                           └──────────┬───────────┘
                                      │
                                      ▼
                    ┌────────────────────────────────┐
                    │         LangGraph Agent         │
                    │                                │
                    │  ┌──────┐                      │
                    │  │WRITE │                      │
                    │  └──┬───┘                      │
                    │     ▼                          │
                    │  STRUCTURAL_CHECK              │
                    │     │                          │
                    │     ▼                          │
                    │  CONTENT_CHECK                 │
                    │     │                          │
                    │     ▼                          │
                    │  VERDICT                       │
                    │   /   |    \                   │
                    │  /    |     \                  │
                    │accept eval  escalate           │
                    │       │                        │
                    │       ▼                        │
                    │ revision_plan                  │
                    │       │                        │
                    │       └──────→ WRITE            │
                    └───────────────┬────────────────┘
                                    │
                 ┌──────────────────┼───────────────────┐
                 │                  │                   │
                 ▼                  ▼                   ▼
          Checkpoint Store      Trace/Telemetry      Artifact Store
                 │                  │                   │
                 ▼                  ▼                   ▼
              Resume             Metrics             Versions
                 │                  │                   │
                 └──────────────────┼───────────────────┘
                                    │
                                    ▼
                             ┌──────────────┐
                             │  Publish Gate│
                             └──────┬───────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                     Publish              Human Review
                                               │
                                               ▼
                                         Eval Dataset
                                               │
                                               ▼
                                        Regression Suite
```

---

# 14. Implementation Order

Không nên làm tất cả cùng lúc. Thứ tự đề xuất:

### Phase 1 — Reliability foundation

```text
1. Structured RevisionPlan output
2. Persistent checkpointer
3. Idempotency key
4. Explicit error taxonomy
5. Retry/backoff policy
```

### Phase 2 — Observability

```text
6. Run ID / Trace ID
7. Per-node metrics
8. Token/cost tracking
9. Latency tracking
10. Error/outcome tracking
```

### Phase 3 — Quality system

```text
11. Golden dataset
12. Automated eval runner
13. Regression suite
14. Quality dashboards
15. Release quality gates
```

### Phase 4 — Human feedback

```text
16. Escalation queue
17. Reviewer decision schema
18. Human correction storage
19. Feed corrections into eval dataset
```

### Phase 5 — Operational production

```text
20. Publish gate
21. SLOs
22. Alerts
23. Concurrency controls
24. Security/policy boundaries
```

---

# 15. Production Readiness Definition

Không gọi graph là production-ready chỉ vì:

```text
✓ LangGraph compile được
✓ Node chạy được
✓ Conditional edge chạy được
✓ LLM tạo output được
```

Definition nên là:

```text
Production-ready Agent
│
├── Deterministic orchestration
├── Explicit state
├── Bounded loops
├── Structured LLM outputs
├── Persistent checkpoints
├── Idempotent execution
├── Failure classification
├── Observability
├── Automated evaluation
├── Regression protection
├── Human escalation path
├── Versioned artifacts
├── Publish gate
└── Operational monitoring
```

Graph hiện tại đã có phần lớn **Agent Core**. Phần cần xây tiếp chủ yếu nằm ở các lớp **Reliability + Evaluation + Observability + Human Feedback + Operations**.

---

# 16. Nguyên tắc kiến trúc cần giữ

### 1. LLM không sở hữu control flow

```text
LLM → reasoning
Code → routing/policy
```

### 2. Node làm một nhiệm vụ rõ ràng

```text
Writer      → generate
Checker     → validate
Evaluator   → judge
Verdict     → classify
Router      → choose next step
```

### 3. State là source of truth của execution

```text
State → Node → State update → Edge → Node
```

### 4. Mọi loop phải bounded

```text
retry_limit
revision_limit
timeout
budget
```

### 5. Accepted không có nghĩa là Published

Luôn có publish gate riêng.

### 6. Production feedback phải quay về Eval

```text
Production
   ↓
Escalation / Human Review
   ↓
Golden Dataset
   ↓
Regression Test
   ↓
Graph / Prompt / Model update
```

Đây là feedback loop quan trọng nhất để biến Agent từ một workflow chạy được thành một **production-grade AI system có khả năng đo lường và cải thiện liên tục**.
