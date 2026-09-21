# Baseline eval AI

Số ghim ngày **2026-09-21**, lệnh đo duy nhất:

```bash
uv run python -m app.content.eval_ai --suite all --fail-under
```

| Suite | Kết quả | Ngưỡng (`thresholds.json`) | Vì sao ngưỡng này |
|---|---|---|---|
| coach (10 case) | 10/10 | ≥95% | Critical (sai chữ cái) không thương lượng; 95% chừa chỗ cho case biên mới thêm vào |
| shape (7) | 7/7 | 100% | Đếm dạng — không có lý do trượt |
| retrieval (16 query) | 16/16, Recall@4 = 1.0 | 100% | Tập curated nhỏ; tụt 1 query là fail (hồi quy) |
| planner (6) | 6/6, ref treo 0 | 100% | Ảo giác ghi vào DB là lỗi tệ nhất của planner |

Đổi prompt/model/retrieval mà tụt dưới ngưỡng thì không merge. Đổi dataset
(thêm case) thì chạy lại baseline ở đây trước để lấy số mới — số trong bảng này
là trần đã đo, không phải mục tiêu phấn đấu.

Luồng hồi quy khi đổi code (case MỚI RỚT là chặn, kể cả ngưỡng vẫn qua):

```bash
uv run python -m app.content.eval_ai --suite all --report eval/reports/base.json
# ... đổi prompt/model/retrieval ...
uv run python -m app.content.eval_ai --suite all --baseline eval/reports/base.json
```

Chi phí lượt chạy offline: 0 (FakeProvider + SQLite memory, không gọi model).

## So sánh lexical vs vector (ADR-016, đo 2026-09-21)

16 query curated, corpus 16 mục, top-4:

| | Recall@4 | MRR | Trễ/query | Giá |
|---|---|---|---|---|
| Lexical | 1.00 | 1.00 | 2ms | 0 |
| Vector (Gemini + Pinecone) | 1.00 | 0.94 | ~3s | >0 |

Kết luận: giữ thứ tự hiện tại (vector trước, lexical fallback) vì tập eval
thiên vị keyword; xem lại khi có 30 ngày log `kb_retrieval`, corpus >200 chunk,
hoặc đo trên query thật thấy lexical thua ≥5 điểm MRR. Chi tiết ở ADR-016.

## Giám khảo (L3, chạy tay khi đổi prompt sinh)

```bash
uv run python -m app.content.eval_ai --judge <provider/model> --gen-model <provider/model>
```

- Judge phải khác model sinh — trùng thì runner từ chối ngay.
- Chuẩn đồng ý hiện tại: 10/10 case coach (đo lần đầu khi chạy live).
- Hàng `ai_interaction` feature=`eval_judge` ghi model/prompt thật đã chấm
  (lấy từ kết quả trả về, không phải từ flag) — đó là nguồn đối chiếu khi
  judge và cổng tất định bất đồng.

## Runbook KPI làm giàu (B3/B4/B6, đo tay — cần người duyệt)

Ba chỉ số này không vào CI vì chúng cần mắt người và lượt gọi live.

**B3 — độ đúng nhãn (≥90%, mẫu 40 gắn tay):**

```bash
uv run python -m app.content.enrich_skills --limit 40
```

So `proposed_code` (máy) với `code` (người duyệt sửa) trên đúng 40 câu:

```sql
SELECT count(*) FILTER (WHERE code = proposed_code) * 1.0 / count(*)
FROM question_label WHERE reviewed_at IS NOT NULL;
```

Mẫu chấp nhận TẬP nhãn đúng cho câu đa điểm (TOEIC một câu kiểm hai điểm là
thường) — so bằng mắt, không phải `=` máy.

**B4 — nhất quán (≥98%, hai lượt `temperature=0`):**

Chạy enrich trên cùng mẫu hai lần (prompt temperature đã là 0.0 mặc định),
so `proposed_code` lượt 1 vs lượt 2. Lệch nghĩa là nhãn có phần là nhiễu và mọi
`GROUP BY` về sau thừa hưởng nó.

**B6 — dùng được ngay (≥70% publish không sửa hoặc sửa vặt):**

Đếm trên hàng đã duyệt: `code = proposed_code` (không sửa) + sửa vặt do người
duyệt đánh dấu tay. Dưới ngưỡng thì sửa prompt, không hạ chuẩn.
