# Agent graph: tự điều phối việc sinh đề bằng LangGraph

> Runbook cho hai đồ thị agent (`app/content/exam_agents/`). Tài liệu kế hoạch
> và lý do thiết kế: [`generate-full-toeic.md`](generate-full-toeic.md). Quy trình
> thủ công từng chặng: [`EXAM-GENERATION-RUNBOOK.md`](EXAM-GENERATION-RUNBOOK.md).

---

## 0. Hai đồ thị, một vòng lặp

| File | Đồ thị | Dùng khi |
|---|---|---|
| `graph.py` | `write → check ─┬→ accept` | blueprint đã có, chỉ sinh các ô còn thiếu |
| | `▲ │ └→ critic → write (≤3 vòng)` | |
| `full.py` | `plan → slotloop` | từ `--slug` trống ra cả đề |

`full.py` tái dùng `graph.py`: node `slotloop` chỉ là vòng gọi `run_pending`
cho tới khi hết ô thiếu. **Vòng lặp cốt lõi nằm trong `graph.py`.**

```
START → write → check ─┬─ pass ──► accept → END
      ▲                └─ fail ──► critic ──► write   (tối đa MAX_REVISIONS = 3 vòng)
```

Vì sao tồn tại: pipeline thủ công `write → check → prune` là một vòng **không
có nhớ** — ô bị loại được sinh lại từ đầu mà không biết vì sao bị loại. Đồ thị
biến nó thành có nhớ: lời phê (`fix_hint`) quay lại lượt viết sau.

## 1. Ba node, cả ba cắm vào thứ đã có

**`write` — tái dùng `writer.write_slot`.** Prompt per-part, `temperature=0.8`,
`with_backoff`, kiểm khối hoàn chỉnh. Ô viết xong được **ghi đĩa ngay** — hàng
đợi vẫn là một truy vấn trên thư mục (`pending()`), chạy lại không trả tiền lại.
`MissingBlock` (đầu ra bị cắt giữa phần suy nghĩ) thành state `blocked` thay vì
exception — ngoại lệ làm đồ thị chết, dữ liệu thì nhánh được.

**`check` — `check_blueprint(gateway=None, only=part)`, KHÔNG gọi model.**
Parser thật (`parse_one`), luật hình, trùng lặp — cùng hàm mà lệnh `check`
chạy. Bản kiểm riêng sẽ trôi khỏi parser, nên nó gọi thẳng. Nguồn DUY NHẤT
được điền `blocked` của nhánh kiểm.

**`critic` — một lượt gọi `exam_verify`** (temperature 0, max_tokens 200).
Model **chấm chứ không viết lại**: đọc lý do bị chặn + bản nháp, trả một gợi ý
sửa ngắn. Gọi feature `exam_verify` vì cùng loại việc với đối chiếu đáp án —
muốn tier riêng thì thêm feature vào bảng giá, không sửa đồ thị.

## 2. Seam mà vòng lặp sống nhờ

`writer.write_slot` nhận thêm **`fix_hint: str | None`**. Khi có, nó ghép vào
user prompt:

```
{prompt gốc}

LƯU Ý SỬA từ lượt trước: {fix_hint}
```

Dùng xong thì node `write` xoá (`fix_hint=None`) — không thì lượt sau đọc lại
hint cũ của lỗi cũ. Đó là toàn bộ khác biệt giữa "sửa theo lý do" và "sinh lại
mù". Test `test_hint_reaches_next_write` pin đúng điều này.

Trần vòng (`MAX_REVISIONS = 3`): một ô hỏng cùng kiểu ba lần thì lỗi nằm ở
prompt/brief, không nằm ở lượt viết — quay tiếp chỉ đốt quota. Quá trần →
`escalate`, giao người.

## 3. Chạy

```bash
cd apps/api

# Đề mới hoàn toàn: plan (7 part) + vòng write→check→critic cho tới khi đủ
uv run python -m app.content.exam_agents.full --slug tp-form-08 \
    --model bai/glm-5.3-flash

# Chỉ một part, thử vài ô
uv run python -m app.content.exam_agents.full --slug tp-form-08 \
    --part 5 --limit 2 --model bai/glm-5.3-flash

# Blueprint đã có, chỉ chạy các ô còn thiếu (graph.py — vòng per-slot)
uv run python -m app.content.exam_agents.graph --slug tp-form-08 \
    --limit 3 --model bai/glm-5.3-flash

# Đổi tier (mặc định cheap)
uv run python -m app.content.exam_agents.full --slug tp-form-08 --tier strong
```

Flag:

| Flag | Ý nghĩa |
|---|---|
| `--slug` | đề; thư mục làm việc `content/generated/<slug>/` |
| `--model` | `provider/model`, ghi đè cả hai tier. Xem `known_models()` |
| `--limit N` | chỉ viết N ô lượt này |
| `--part N` | chỉ sinh part N (`full.py` áp cho cả plan và slotloop) |
| `--seed` | seed blueprint (cùng seed = cùng chủ đề, khác câu chữ) |
| `--tier` | `cheap`/`strong` khi **không** có `--model` |

Hết quota (`LLMQuotaExhausted`) thì `with_backoff` ném ra và ô đó dừng — chạy
lại lệnh là tự nó tiếp, ô đã ghi không mất.

## 4. Node `plan` trong `full.py`

`plan_blueprint()` được **tách từ `cmd_plan`** thành hàm dùng chung — CLI
`generate_exam plan` và node graph gọi **một đường**. Hai bản sao của "cách
dựng blueprint" sẽ trôi khỏi nhau, và cái trôi là cái không ai chạy bằng tay.

- Blueprint đã có trên đĩa → node **bỏ qua** (chạy lại giữa chừng không đốt
  quota plan lần nữa).
- Model sinh bối cảnh per-part + brief hình (part 3/4/7); hỏng → rơi về bảng
  cấu hình/pool theo seed. Cấu trúc (số câu, vị trí hình, giọng) **luôn từ
  bảng**, model chỉ sinh nội dung.
- Sau mỗi part: `bp.merge` + `bp.validate` — sai là ném, không lưu đề hỏng.

## 5. Kiểm

`tests/test_exam_agents_graph.py` — ba test, **không gọi model** (cùng quy tắc
với demo cũ: cái được kiểm là cấu trúc vòng lặp, không phải chất lượng model):

| Test | Pin hành vi |
|---|---|
| `test_pass_first_try` | khối tốt qua kiểm ngay, đúng 1 lượt viết, không tốn critic |
| `test_escalates_after_max_revisions` | khối luôn hỏng → dừng ở trần, **không quay mãi** |
| `test_hint_reaches_next_write` | hint của critic **thực sự tới** prompt lượt viết 2 — pin bằng cách đọc prompt model giả nhận |

Model giả đi qua đúng seam thật: `gateway.run(request, feature=...)` — thay
bản thật là cắm `Gateway`, không sửa node nào.

## 6. Ranh giới không được phá

- **Extra `agents` tách riêng** (`langgraph`), không gộp vào `content` — hai lý
  do cài khác nhau, chỉ ảnh worker cần nó. `test_content_isolation.py` canh cả
  hai: API không được import `app.content`, càng không được import `langgraph`.
- **Kiểm là code, không phải model.** `check` node phải là hàm điều kiện; chỉ
  `write` và `critic` tốn token. Thêm tầng kiểm = thêm code trong
  `check_blueprint`, không thêm lượt gọi.
- **Mỗi ô một thread** (`thread_id = slot.id`) với `InMemorySaver` — checkpoint
  per-slot, một ô hỏng không ảnh hưởng ô khác. Muốn checkpoint bền (đồ thị tiếp
  sau khi máy ngủ) thì đổi sang saver trên đĩa/Redis — seam đã sẵn.

## 7. Sau khi graph xong

Graph chỉ sinh **tệp dán**. Các chặng sau giữ nguyên pipeline thủ công — vì mỗi
chặng có một loại quyết định của người:

```bash
uv run python -m app.content.generate_exam graphic --slug tp-form-08   # vẽ hình (người xem)
uv run python -m app.content.generate_exam photo --slug tp-form-08     # vẽ ảnh P1 (người xem)
uv run python -m app.content.generate_exam load --slug tp-form-08 --token <token>
uv run python -m app.content.backfill_audio --only questions
uv run python -m app.content.generate_exam attach-images --slug tp-form-08 --commit
uv run python -m app.content.generate_exam media --slug tp-form-08 --push
uv run python -m app.content.generate_exam check --slug tp-form-08 --verify
```

Chi tiết từng chặng: [`EXAM-GENERATION-RUNBOOK.md`](EXAM-GENERATION-RUNBOOK.md).
