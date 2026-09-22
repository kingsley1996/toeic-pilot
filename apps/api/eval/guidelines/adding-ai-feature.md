# Thêm tính năng AI mới — copy gì từ pipeline sinh đề

Sinh đề (`app/content/exam_agents/graph.py` + `exam/check.py`) là reference
implementation cho mọi workflow AI nhiều bước. Tính năng mới không cần giống
hệt, nhưng phải trả lời được từng dòng dưới — chỗ nào không có thì ghi lý do.

## Khung bắt buộc

```text
Viết/Sinh → Kiểm tất định → Phê/Chọn → Kiểm lại → Publish/Ghi
```

- **State explicit**: một `TypedDict`/dataclass mang toàn bộ trạng thái
  (`SlotState`: draft, problems, flags, fix_hint, revision, outcome, log).
  Không đọc history ẩn để biết mình đang ở đâu.
- **Vòng có trần**: `MAX_REVISIONS` — hỏng cùng kiểu 3 lần là lỗi prompt/brief,
  quay tiếp chỉ đốt tiền. Hết vòng thì `escalate` (giao người), không quay mãi.
- **Kiểm rẻ trước, đắt sau**: tầng miễn phí (parser, luật) chạy trước; chỉ cái
  gì sạch mới tới lượt gọi model. Ô đã hỏng không cần hỏi model thêm.
- **Lỗi phân loại**: `blocked` (nội dung hỏng) vs `fatal` (lượt gọi hỏng) vs
  `flags` (người nên nhìn). Ba loại đi ba đường khác nhau, không gộp.

## Prompt và version

- Prompt là file `.md` versioned (hash body, frontmatter chỉ là metadata).
- Viết lại sau phê phải kèm `fix_hint` (lý do), không sinh lại mù.
- Nhiệt độ khác 0 chỉ khi cần đa dạng (sinh đề); chấm/chọn thì 0.0.

## Eval đi cùng, không đi sau

- Golden cases vào `eval/datasets/` + suite offline chạy được ở CI — như
  `exam_slots.jsonl` (paste golden + kỳ vọng đúng/sai từng cổng).
- Viết case XONG mới tin cổng: suite exam bắt được đáp án đúng quá nguyên văn,
  thiếu câu bắc cầu, rò đáp án chéo — toàn lỗi người viết mắc khi dựng dataset.
- Judge/critic (model chấm model) cần hiệu chuẩn với verdict người trước khi
  tin — xem runbook judge ở `eval/baseline.md`.

## Quan sát được

- Mỗi vòng ghi `log` một dòng: ba vòng hỏng CÙNG kiểu hay ba kiểu khác nhau
  quyết định sửa prompt hay đổi model — không log thì không phân biệt được.
- Mọi lượt gọi model qua `Gateway` (budget + sổ cái + `prompt_version`).
  Không gọi adapter trực tiếp "cho nhanh".
- Hàng đợi là một TRUY VẤN (câu nào chưa xong), không phải bảng job — chạy lại
  là tìm thấy ít việc hơn, và đó là toàn bộ cơ chế phục hồi.
