# PR checklist

## Mọi PR

- [ ] Lệnh CI chạy xanh ở local trước khi đẩy (xem `CLAUDE.md` mục CI)
- [ ] Không commit secrets, không sửa file ngoài phạm vi

## Chỉ khi chạm đường AI (`**/prompts/**`, `**/exam_agents/**`, `**/retrieval*`, `**/knowledge*`, `**/planner*`, `**/coach*`, `**/assistant*`)

- [ ] Logic tất định tách khỏi logic LLM
- [ ] Prompt đã versioned (frontmatter chỉ đổi metadata thì version không đổi)
- [ ] Structured output có validation + đường hỏng rõ ràng
- [ ] `uv run python -m app.content.eval_ai --suite <liên quan>` xanh, dán tóm tắt metrics:
  - suite/kết quả:
  - có đổi prompt không, bản nào → bản nào:
- [ ] Đổi prompt sinh (coach/enrich): đã chạy judge hoặc ghi lý do chưa chạy
- [ ] Tokens/cost/latency quan sát được (sổ `ai_interaction` hoặc transcript)
- [ ] Failure paths có test; prompt injection đã nghĩ tới; không gửi PII thừa
