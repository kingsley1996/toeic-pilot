# Plan: đưa workflow AI hiện có lên production-grade (theo guides)

**Nguồn chuẩn:** `planning/guides/AI Engineering Guidelines — TOEIC Pilot.md` (gọi tắt là guides).
**Hiện trạng (đã đối chiếu):** kiến trúc + determinism + observability + safety đạt ~85–95%;
eval + RAG đo được + tracing đạt ~25–40%. Chưa feature nào Level 5 (§23).
**Nguyên tắc của plan:** eval trước, observability sau, rồi mới sửa hành vi (§24).
Mỗi phase xong phải trả lời được "có tốt hơn hay tệ đi" bằng số.

Quy ước: "1 file case + 1 lệnh chạy" cho eval (luật test của repo) — `datasets/*.jsonl`
là dữ liệu, không phải framework. Không thêm service, DB, hay framework agent mới.

## 0. Bản đồ hiện trạng → Level (§23)

| Workflow | Hôm nay | Level | Lên Level 5 còn thiếu |
|---|---|---|---|
| Coach giải thích (`services/coach.py`) | structured + 5 validators + cache + cost/prompt_version log | L4 | eval dataset + judge + regression gate (P0) |
| Gắn nhãn / backfill explanation (`content/enrich_skills.py`, `content/backfill_explanations.py`) | offline, queue = query, cổng duyệt, shape check | L4 | accuracy/consistency/usability KPIs chưa đo (P0) |
| Planner V2 (`services/planner_llm.py` + `content/eval_planner.py`) | candidate-list + FK guard + fallback V1 + compare script | L3–L4 | failure observable + eval có ngưỡng (P0, P3) |
| Assistant / coach_chat + RAG (`services/assistant.py`, `chat.py`, `knowledge.py`, `retrieval.py`) | tools hẹp, history vào `user`, lexical + vector dự phòng | L2–L3 | retrieval eval, metadata, phân biệt retrieval vs generation lỗi (P1) |
| Sinh đề (`content/exam_agents/graph.py`, `content/exam/check*`) | graph viết→kiểm→phê→escalate, state explicit, trần vòng | L4 | judge calibration + regression dataset thành reference (P5) |

## P0. Eval harness + regression gate (§6, §7, §8, §9, §10) — LÀM TRƯỚC

Mục tiêu: mọi đổi prompt/model/retrieval/parser đều so được old/new trên cùng dataset.

### P0.1 Runner + layout dữ liệu

- Tạo `apps/api/eval/datasets/*.jsonl` (dữ liệu thuần, mỗi dòng 1 case):
  `coach_explain.jsonl` (~50 case: question_id hoặc đề inline + chosen + expected_answer_letter +
  expected_skill + golden_explanation cho ~17 câu đã có),
  `retrieval.jsonl` (~40 query → `relevant_refs[]`, dùng ở P1),
  `planner.jsonl` (attempt fixture ids + weak codes kỳ vọng — tái dùng logic `eval_planner.py`),
  `prompt_regression.jsonl` (mỗi prompt runtime × 3–5 case cố định).
- Tạo `apps/api/eval/guidelines/annotation.md`: định nghĩa correct/incorrect,
  biến thể chấp nhận được, critical error (vd: nêu sai chữ cái đáp án = critical).
- Tạo **một** runner `apps/api/app/content/eval_ai.py`:
  `uv run python -m app.content.eval_ai --suite coach --against <prompt_version|model>`
  chạy L1+L2 offline bằng `FakeProvider` (không mạng), in bảng pass/fail theo từng
  assert + tổng cost/latency = 0 (ghi rõ "offline").
- L3 judge: runner flag `--judge` gọi gateway thật, model judge **khác** model sinh
  (lấy từ `AiFeatureConfig["eval_judge"]`), ghi `judge model + prompt_version + dataset + score`.
- Acceptance:
  - [ ] `eval_ai --suite all` chạy xanh không cần khoá API, < 2 phút.
  - [ ] Đổi 1 từ trong `coach_explain.md` làm version đổi và report chỉ ra case nào rớt.
  - [ ] `--judge` từ chối khi judge model == generation model.

### P0.2 Ngưỡng khởi điểm (tạm, hiệu chỉnh bằng baseline — §7)

Chạy baseline trước rồi ghim số, không phát minh số đẹp:

| Suite | Metric | Ngưỡng tạm | Ghi chú |
|---|---|---|---|
| coach L2 | pass 5 asserts | ≥95% | critical (sai chữ cái) = 100% pass, không thương lượng |
| enrich (B3/B4/B6 của AI-ENGINEERING-PLAN §9b) | accuracy vs mẫu gắn tay / consistency 2 lượt temp=0 / dùng-ngay | ≥90% / ≥98% / ≥70% | mẫu 40 câu gắn tay toàn bộ ở kho hiện tại |
| planner | ref treo | 0 | + phủ V1 báo cáo, không đặt ngưỡng phủ (đo, chưa chặn) |
| retrieval | Recall@4 | baseline + không tụt | ngưỡng chặn đặt sau P1 |

- Acceptance: [ ] report baseline đã chạy và số ghim trong `eval/reports/` (gitignore,
  chỉ tóm tắt vào PR); [ ] CI fail khi L1/L2 tụt (xem P0.3).

### P0.3 Cổng CI (§8 L4, §17)

- Deterministic suites (L1/L2, FakeProvider) chạy trong job `api` của CI — luôn chặn.
- Judge (L3, tốn tiền) chỉ chạy khi PR chạm `**/prompts/**`, `**/retrieval*`,
  `**/knowledge*`, `**/exam_agents/**` (path filter), hoặc khi gắn nhãn `ai-eval`.
- Cập nhật `ROADMAP.md` §"Lớp AI": đánh dấu eval harness xong, ghi lệnh đo.

## P1. RAG đo được (§5) — assistant + coach_chat

### P1.1 Metadata chunk (§5.1)

- Migration mới (nullable toàn bộ, không backfill bắt buộc):
  `knowledge_chunk`: `source` (vd `content/kb/tests-scoring.md`),
  `doc_type`, `topic`, `language` (default `vi`), `content_version`.
- `sync_knowledge` đọc 5 trường từ frontmatter; thiếu → giữ giá trị cũ + warning,
  không fail (corpus hiện tại 16 file vẫn sync được).
- Acceptance: [ ] `sync_kb --dry-run` báo file nào thiếu metadata; [ ] sync thật
  upsert đúng 16 ref, không mất hàng.

### P1.2 Tách lỗi retrieval vs generation (§5.3) + đo (§5.2)

- Thêm vào runner P0 suite `retrieval`: Recall@4 / Precision@4 / MRR trên
  `retrieval.jsonl`, chạy 3 cấu hình: lexical, vector, chained — cùng một lệnh.
- Production: log `retrieved_refs + retrieval_scores + retrieval_ms` theo `request_id`
  (chi tiết schema ở P2) để khi sai trả lời được "retriever hỏng hay LLM bỏ evidence".
- Quyết định Pinecone (§22): giữ hay bỏ dựa trên bảng so sánh
  quality/latency/cost trên cùng dataset — kèm đối chiếu ADR-003 §3.2
  (offline bge-m3/vector(1024)/không dữ liệu rời máy). Kết quả ghi vào ADR mới
  hoặc sửa ADR-003, không để `config.py:95` là nguồn duy nhất.
- Acceptance: [ ] có bảng số 3 cấu hình; [ ] quyết định Pinecone có ADR; [ ] không
  thêm reranker (§5.4: chỉ thêm khi đo được lợi).

## P2. Observability + tracing + cost (§11, §12, §13)

### P2.1 Thêm trường sổ cái (1 migration, nullable hết)

`ai_interaction`: `workflow` (vd `coach_qa`, `exam_slot` — tách khỏi `feature`),
`retrieved_refs JSONB NULL`, `retrieval_ms INT NULL`, `reranker_used BOOL DEFAULT FALSE`,
`step_count INT NULL`. Per-tool latency/error **không** vào DB — vào transcript JSONL
theo `request_id` (tránh phình bảng nóng).

### P2.2 Trace theo request_id (§12)

- Gateway transcript: mỗi lượt ghi thêm events `retrieve → tool* → validator`
  với `ms` từng bước, chung `request_id`. Không dựng tracing infra mới.
- `assistant.ask` / `chat.ask` đo `retrieval_ms`, đếm `step_count`, truyền vào `_record`.
- Acceptance: [ ] từ 1 `request_id` truy được full path + chi phí từng bước mà
  không reproduce request; [ ] dashboard `/admin/ai` hiện được top feature/model
  + p50/p95 (đã có `ai_stats.collect`, chỉ thêm cột mới).

### P2.3 Cost/routing (§13)

- Chạy 1 feature rẻ (đề xuất `enrich_label` hoặc `coach_chat` history tóm tắt) trên
  `Tier.CHEAP` 1 tuần, đo pass-rate + retry-rate + cost/call vs STRONG.
  Quy tắc: leo thang > ~15% hoặc L2 rớt → STRONG vẫn đáng; ngược lại chuyển hẳn.
- Bật prompt caching cho system prompt dài (`assistant_chat` context, exam prompts),
  đo bằng `cached_tokens` đã có. Ghi kết quả vào AI-ENGINEERING-PLAN §7.
- Acceptance: [ ] có con số quality/cost cho CHEAP vs STRONG; [ ] bảng giá
  `pricing.py` không còn model nào "chưa có giá" cho đường đang chạy.

## P3. Reliability + safety (§14, §15)

- `planner_llm.llm_select`: thay `except Exception: return None` bằng except hẹp
  (`LLMError, ValueError, KeyError`) + ghi hàng `ai_interaction` status=`error`
  (feature=`study_plan`) kèm `error` là lý do → caller vẫn fallback V1 nhưng lỗi
  observable. Thêm test: LLM hỏng → V1 + có hàng error.
- Chuẩn hoá fallback mọi nơi: `coach_chat`/`assistant` hết vòng tool → raise
  (đã có), không trả câu bịa; enrich/backfill giữ nguyên (bỏ qua + báo).
- Safety tests mới trong `tests/test_security.py` (hoặc file riêng `test_prompt_injection.py`):
  history chứa "bỏ qua mọi quy tắc", retrieved doc chứa chỉ dẫn lạ, tool args
  chứa `user_id` → assert model không điều khiển được hệ thống, tool lạ bị từ chối.
- PII audit: grep `LLMRequest(` — assert không chỗ nào gửi email/tên/phone;
  planner chỉ gửi tỉ lệ tổng hợp (giữ nguyên).
- Acceptance: [ ] 100% đường LLM có timeout + retry/backoff + fallback được test;
  [ ] không còn `except: return None` trong đường AI.

## P4. Prompt lifecycle + DoD cho PR (§6, §17, §18, §25)

- `Prompt` parser: hỗ trợ frontmatter YAML tùy chọn trong `.md`
  (`purpose, inputs, outputs, model_hint, temperature, eval_suite`); **version =
  hash phần body sau frontmatter** (sửa metadata không đổi version, sửa chữ đổi).
  Không frontmatter → behavior cũ, không migration prompt hàng loạt.
- Checklist §25 thành template PR cho `**/prompts/**` + `**/exam_agents/**` +
  `**/retrieval*` + `**/knowledge*`: deterministic tách LLM, state explicit,
  tool typed, prompt versioned, structured validated, eval dataset + metrics +
  regression, tokens/cost/latency observable, failure paths tested, injection/PII/permissions.
- Agent coding rules (§18): bổ sung vào `.claude/rules/testing.md` 2 dòng —
  "sửa AI phải chạy `eval_ai` suite liên quan + dán tóm tắt metrics vào PR".
- Acceptance: [ ] sửa prompt không frontmatter vẫn chạy; [ ] PR mẫu đi qua checklist.

## P5. Sinh đề thành reference implementation (§20)

- Đóng băng 10–20 slot golden (input blueprint + draft đạt + verdict) làm
  `eval/datasets/exam_slots.jsonl`; `graph.py` chạy được ở chế độ `--replay`
  (không gọi model) để regression parser/checker/critic trong CI.
- Calibrate judge `exam_verify`: so judge vs verdict người trên mẫu golden,
  ghi agreement rate; judge prompt versioned như mọi prompt runtime.
- Acceptance: [ ] `eval_ai --suite exam` xanh offline; [ ] doc 1 trang
  "thêm tính năng AI mới thì copy gì từ sinh đề" (state/graph/validator/eval).

## Thứ tự + ROADMAP

1. P0.1 → P0.2 (baseline) → P0.3 (cổng CI) — xong mới đụng hành vi.
2. P1 song song P2 (khác files, khác người làm được).
3. P3 sau khi P0 có gate (sửa reliability mà không có eval là mù).
4. P4 + P5 cuối (chuẩn hoá + nhân rộng).

Sau mỗi phase: cập nhật `ROADMAP.md` (tracker duy nhất — phase xong thì sửa số đo
+ lệnh đo, không để plan này mang trạng thái), archive plan con đã xong kèm commit.
