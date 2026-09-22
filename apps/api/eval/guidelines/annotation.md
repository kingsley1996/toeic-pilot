# Chấm eval AI — cái gì đúng, cái gì sai

Áp cho mọi case trong `datasets/`. Mục đích duy nhất: hai người chấm cùng một
case phải ra cùng một kết quả, và máy chấm thay người cũng vậy.

## 0. Nguyên tắc

- Case **đạt** khi không còn lỗi nào trong danh sách của suite đó, không phải khi
  "đọc thấy ổn". Cảm tính không phải metric.
- Case **rớt** phải chỉ được LỖI Ở ĐÂU (tên assert + đoạn trích), để người sửa
  prompt biết sửa chỗ nào thay vì viết lại mù.
- Sửa dataset để hệ thống đang sai thành đạt là gian lận. Dataset chỉ đổi khi câu
  hỏi/ngữ liệu thật đổi, hoặc khi chính luật chấm đổi (và lúc đó ghi lý do vào PR).
- Mọi case rớt mang một **kind**: `dataset` (case/cấu hình viết sai — không phải
  lỗi sản phẩm), `system` (sản phẩm hành xử sai), `judge` (giám khảo chấm sai),
  `infrastructure` (gọi hỏng: timeout, 503, quota, key). Sập provider không được
  đọc thành regression chất lượng.
- Kèm `code` máy đọc được để group-by về sau. Coach: `wrong_correct_answer`,
  `missing_distractor_ref`, `wrong_language`, `wrong_grammar_point`,
  `missing_field`, `invalid_output`, `bad_length`, `expectation_mismatch`.
  Shape: `segment_count`, `letter_in_evidence`, `wrong_segment_order`,
  `line_break`, `empty_output`. Retrieval: `missing_refs`, `too_many_refs`,
  `invalid_dataset`. Planner: `wrong_selection`, `dangling_reference`,
  `unexpected_none`, `unexpected_items`, `unexpected_call`. Judge:
  `judge_disagree`, `judge_unparseable`, `provider_error`.

## 5. Hồi quy — `--report` và `--baseline`

Luồng đúng khi đổi prompt/model/retrieval:

```bash
uv run python -m app.content.eval_ai --suite all --report eval/reports/base.json
# ... đổi code ...
uv run python -m app.content.eval_ai --suite all --baseline eval/reports/base.json
```

Đổi đường retrieval thì đo cả hai mode (mặc định `lexical` offline cho CI;
`--retrieval-mode vector` đo đường production thật, cần keys — probe hỏng là
dừng TO chứ không lặng lẽ đo lexical rồi báo là vector):

```bash
uv run python -m app.content.eval_ai --suite retrieval --retrieval-mode vector
```

- Case **MỚI RỚT** so với baseline là chặn (exit 1), kể cả khi ngưỡng tuyệt đối
  vẫn qua — ngưỡng bắt "đang tệ", baseline bắt "vừa tệ đi".
- Case **đã hết rớt** chỉ là tin tốt để đọc, không phải lý do merge.
- Delta metric (recall/MRR) là số so sánh; chặn tuyệt đối do `--fail-under` quyết.
- Report JSON mang đủ để tái hiện: run id, giờ UTC, git SHA, hash từng dataset,
  prompt version, ngưỡng, args. Đọc report là biết đã chấm cái gì mà không cần
  hỏi người chạy.

## 6. Judge — schema strict, bất đồng là hiệu chuẩn

- Schema gọi judge khai đủ kiểu từng trường + cấm field lạ; parser JSON giữ làm
  lớp phòng thủ thứ hai cho provider không tôn trọng schema.
- Judge phải khác model sinh — trùng thì runner từ chối trước khi tốn một xu.
- Bất đồng với cổng tất định là tín hiệu HIỆU CHUẨN (judge sai hay case sai),
  không phải tín hiệu bỏ qua. Lỗi gọi (timeout/503/quota) là hạ tầng, kind riêng.
- Tóm tắt judge đọc ma trận TP/FP/FN/TN (judge so với kỳ vọng curated) +
  precision/recall/F1 + số lượt thử lại. Chất lượng ổn mà thử lại tăng là tín
  hiệu vận hành, không phải tín hiệu chất lượng — hai số tách nhau ngay ở tóm tắt.

## 7. Manifest dataset

`datasets/manifest.json` ghim hash từng tệp dataset. Sửa/thêm case xong thì chạy
`--write-manifest`; report nào lệch manifest thì in cảnh báo (không chặn — dataset
đang sửa dở mà chặn CI thì không ai dám thêm case).

## 1. Suite `coach` — lời giải thích câu làm sai

Chạy `parse_output` rồi `check_output` (năm khẳng định, `services/coach.py`).
Case gồm câu hỏi inline + phương án đã chọn + nhãn + MỘT reply ghi sẵn.

- **Nêu sai chữ cái đáp án (critical):** `vi_sao_dap_an_dung` không nhắc đúng chữ
  cái đáp án đúng. Một lời giải trôi chảy mà dạy sai đáp án là lỗi tệ nhất — case
  loại này không bao giờ được hạ thành "chấp nhận được".
- **Không nhắc phương án đã chọn:** `vi_sao_ban_chon_sai` thiếu chữ cái đã chọn.
  Không áp dụng khi học viên bỏ trống (`chosen: null`).
- **Không phải tiếng Việt:** văn bản trôi chảy nhưng là tiếng Anh. Đếm ký tự có
  dấu, không chấm bằng mắt.
- **Độ dài:** mỗi trường 20–900 ký tự. Quá ngắn là rỗng nghĩa, quá dài là lan man.
- **Giảng sai điểm ngữ pháp:** nhắc tên một nhãn `GRAMMAR_*` nhiều chữ mà không
  phải nhãn của câu. Chỉ bắt nhóm tên dài ("mệnh đề quan hệ", "cấu trúc so sánh");
  tên một hai chữ ("thì", "thể") bỏ qua có chủ ý vì đối chiếu chúng báo động giả.
- **Dạng:** không phải JSON / thiếu trường là rớt ở cổng parse, trước cả năm
  khẳng định trên. Reply trong dataset để dạng object cho case đạt, dạng chuỗi
  thô cho case kiểm cổng parse.
- Biến thể diễn đạt khác nhau mà cùng đúng thì cùng đạt. Đừng chấm hay/dở văn.

## 2. Suite `shape` — dòng giải thích backfill

Chạy `check_shape` (`content/backfill_explanations.py`). Một dòng duy nhất:
đoạn căn cứ + mỗi phương án một đoạn, ngăn bằng ` | `.

- Đoạn căn cứ **không mang chữ cái nào** (phương án bị xáo sau khi lời giải viết).
- Mỗi đoạn mở đầu đúng `(X)` của chính nó; đổi chỗ hai đoạn là rớt dù văn xuôi.
- Thiếu/thừa đoạn, xuống dòng, trả về rỗng: đều rớt. Đếm, không tranh luận.

## 3. Suite `retrieval` — tìm tài liệu

Mỗi case: một câu hỏi ngắn + `relevant_refs` (1–2 ref, theo thứ tự quan trọng).
Chạy lexical trên chính `content/kb/*.md` trong SQLite memory — không mạng,
không khoá, deterministic.

- Case đạt khi **mọi ref trong `relevant_refs` nằm trong top-4**.
- `relevant_refs` dài hơn top-4 là case viết hỏng (kind `dataset`), không phải
  retriever hỏng — đòi 5 ref trong top-4 thì không bao giờ đạt được.
- Query viết như người học gõ thật (ngắn, thiếu dấu cũng được), không nhồi từ
  khóa trong title vào query để "giúp" retriever.
- Query tự nhiên mà rớt là tín hiệu thật (thiếu từ khóa, thiếu mục tài liệu) —
  sửa tài liệu hoặc từ khóa, không sửa query cho dễ.
- Metrics: Recall@4 là cổng (mọi ref phải trong top-4); MRR trung bình in kèm để
  so cấu hình retrieval với nhau, không chặn. Không có quan sát nào thì in `n/a`
  — không có số liệu KHÁC đạt tuyệt đối.
- Quy lỗi production (§5.3): mỗi lượt assistant ghi log `kb_retrieval` theo
  `request_id` (refs + scores + ms). Ghép với hàng `ai_interaction` cùng id:
  ref đúng mà trả lời sai là LLM bỏ evidence; ref sai ngay từ đầu là retriever hỏng.

## 4. Suite `planner` — model chọn từ danh sách ứng viên

Đo lớp CHỌN (`planner_llm.llm_select`) với FakeProvider — không đo model, không
đo `weak_items` (lớp đo đã có test riêng ở `test_study_plan.py`). Mỗi case gieo
chủ đề + bài published vào SQLite memory rồi chạy chọn thật.

- **Không ref treo:** mọi `grammar_lesson` phải có `ref_id`; chủ đề `draft` hoặc
  thiếu bài thì ứng viên đó không được tồn tại, chứ không phải tồn tại rồi lọc sau.
- **ID lạ bị lọc:** model trả id ngoài danh sách thì bỏ mục đó, giữ mục đúng —
  không rớt cả lượt vì một id bịa.
- **Trần budget:** vượt `budget` (và `MAX_PICKS`) thì cắt, giữ đúng thứ tự model xếp.
- **Ít ứng viên:** dưới `MIN_PICKS` thì trả `None` (nơi gọi rơi về planner rule)
  và **không gọi model** — gọi rồi bỏ là đốt tiền.
- JSON hỏng cũng là `None`, không phải exception trồi lên request.
