---
paths:
  - "apps/api/app/content/exam*/**"
  - "apps/api/content/generated/**"
---

# Đóng vai model sinh đề qua graph (không gọi LLM ngoài)

Chế độ này khác runbook (`planning/docs/EXAM-GENERATION-RUNBOOK.md`): ở đó model
ngoài viết nội dung qua `--model`; ở đây **agent tự viết mọi nội dung model**
(plan scenes + từng khối ô) và chỉ dùng code pipeline để dẫn vòng
write→check→critic (`app/content/exam_agents/graph.py`, `full.py`).
Dùng khi tạo đề `tp-form-NN` mới mà không đốt quota LLM.

Mọi lệnh chạy từ `apps/api/`. `<SLUG>` là đề mới — kiểm tra chưa tồn tại trong
`content/generated/` trước.

## 1. Plan — tự viết bối cảnh, không dùng bảng tĩnh

Bảng tĩnh (cùng `seed`) trùng ~80% context với đề trước (đo được 62/78 với đề
kề trước). Giữ cấu trúc seed, thay toàn bộ nội dung:

- Dump ràng buộc từng ô (id | topic | question_type(s) | grammar(s) | voices |
  people | indirect/how/implication kinds | passages | graphic brief) rồi viết
  theo: 103 context + 6 scene P1 + brief hình **giữ nguyên kind** của structure.
- Mỗi dòng tiếng Việt, duy nhất trong đề (103/103) và overlap 0 với mọi
  `content/generated/*/blueprint.json` — verify bằng script, không bằng mắt.
- P1: 6 dòng `TYPE|people|scene`, 6 nơi khác nhau, ≤1 văn phòng, ≥2 ngoài trời,
  tránh motif 8 đề gần nhất (lấy danh sách từ
  `exam_cli.plan._part1_avoid_and_lean`). Mapping cố định: PERSON/one,
  PERSON_AND_OBJECT/several, OBJECT_OR_SCENE/none.
- P7 nhiều tài liệu: context phải gọi tên ĐỦ từng tài liệu. Brief hình khớp
  context vừa viết (graphic hosts đọc context mới).
- Áp đúng đường của node plan (`exam_agents.full.plan_blueprint`): P1
  `build_part1(slug, title, seed, scenes)`; P2–7 `_override_contexts`;
  P3/4/7 rebuild `build_partN(slug, title, seed, graphics)` rồi override lại.
  `bp.validate` phải sạch mới lưu.

## 2. Slotloop — graph chạy, người trả lời

`run_pending` + FakeGateway đọc bản viết sẵn (harness để ở `/tmp`, không
commit — viết lại mỗi đề):

- `run(request, feature, tier)`: `exam_write` nhận diện slot qua context
  (duy nhất trong đề) rồi trả bản đã viết; `exam_verify` (critic) lưu request
  ra tệp và trả hint đã viết, chưa có thì trả hint máy móc trích đúng problems.
- Drafts là `{slot: text | [v1, v2, …]}` — **chuỗi đơn phải được bọc thành
  list**, nếu không index rơi vào từng ký tự và mọi ô chết với lỗi khối 1 ký tự.
- Chạy `run_pending(..., retry=<ids>)` theo part (`--part N`): không có `only`
  thì retry lôi cả part chưa viết vào. `pending` là truy vấn trên thư mục nên
  retry ghi đè tệp cũ là đúng đường phục hồi của pipeline.

## 3. Hợp đồng khối và luật kiểm (thuộc trước khi viết)

Khung khối: `[PHOTO]` (P1) / `[SCRIPT]` + `voice:` từng lượt (P3/P4) /
`[QUESTION]` + `voice:` (P1/P2) / `[PASSAGE]` với blank `------- (N)` (P6/P7) /
`[GRAPHIC]` + `kind:` + dòng tiêu đề riêng (ô có hình — node write tự tách ra
`graphics/<slot>.txt`, bản viết LUÔN kèm khối gốc). Mỗi `[QUESTION]` kết thúc
`Answer:` (+`Explanation:` nếu cần) + `Source: original`, đúng số câu
(`QUESTIONS_PER_SET` P3/P4:3, P6:4; P7 theo ô; P2 ba đáp án A–C).
`Explanation:` chỉ ở Part 1 + Part 5, và ở câu bắc cầu của cụm P7 nhiều tài
liệu chữ — các part khác không có.

Luật chặn ở lượt kiểm miễn phí:

- **Distractor nhại lời thoại (P3/P4):** mỗi câu tối đa 1 nhiễu có echo < 0.2
  (`check.echo` = tỉ lệ từ nội dung của đáp án có trong thoại). Viết nhiễu
  bằng từ trong thoại rồi bẻ nghĩa.
- **Cân paraphrase (cụm P3/P4):** trong các câu không-abstract (trừ
  PURPOSE/IMPLICATION/IDENTITY/LOCATION), đáp án đúng giống thoại nhất tối đa
  1 câu, ít giống nhất tối đa 1 câu. Paraphrase cả đáp án đúng hoặc cho nhiễu
  hòa/kém hơn đúng một bậc — đo bằng `check.echo` trước khi chạy.
- **Hàm ý:** imp0 trích đúng 4–9 từ có thật sau says/writes; imp1 đáp án chạm
  ≥2 câu thoại; imp2 bản sửa thắng bản cũ trong đáp án.
- **Ô có hình được miễn distractor/balance/spread**, nhưng: đúng 1 câu
  `Look at the graphic` ở câu thứ 3 (Part 3) / thứ 2 (Part 4)
  (`GRAPHIC_POSITION`); 4 đáp án = đúng trục kind (table/tên hàng,
  schedule/khung giờ, chart/nhãn, map/tên ô, survey/tiêu đề cột); thoại nêu
  tối đa 1 trong 4 mục, không bao giờ nêu mục thắng; nhìn hình một mình không
  đủ trả lời. Schedule: cả 4 tên cột đầu đều được nói ra, ô trống là chỗ hỏi.
- **P7 nhiều tài liệu chữ (≥2 khối `[PASSAGE]` văn bản):** phải có 1 câu bắc
  cầu với Explanation trích nguyên văn (`"..."`, mỗi mảnh ≥12 ký tự) từ HAI
  tài liệu — `check_cross_passage` đo đúng cái này, thiếu là blocked.
- **Sàn ngữ liệu (từ nội dung — dưới sàn thì viết dài ra, không dùng):**
  P3/P4 ≥ 30, P6 ≥ 80, P7 ≥ max(60, 20 × số câu). Band chuẩn theo tp-form-15:
  P6 ~95–108, cụm 5 tài liệu ~154–184. Ô hard=1 nên có đáp án span ≥ 2 câu
  (`evidence_sentences`), đừng ỷ vào kẽ hở span-0 của đáp án synonym.
- **P7:** từ VIC xuất hiện ĐÚNG 1 lần toàn cụm, band B2+; sentence-insertion
  cắm marker `[1]–[4]` trong doc, đáp án là marker; implication chuỗi chat
  trích verbatim kèm timestamp.
- **P5:** 4 đáp án dài xấp xỉ, khác trường nghĩa, đúng 1 từ hợp collocation;
  từ đúng vocab thuần band B2+.

## 4. Vòng retry và kết thúc

Đọc `vòng N:` trong log + file critic đã lưu để biết lý do, viết lại CHỈ chỗ
hỏng (giữ script/ngữ liệu đã đúng), thêm bản mới vào drafts, chạy
`--retry … --round K` tới khi hết escalated. Ba flag `lựa chọn dài bất thường`
ở đáp án redirect/moot là lành tính (đề thật cũng vậy).

Xong khi: `balance` (cân đáp án cả đề) → `check_answer_spread` đạt →
`check_blueprint` cả 7 part (gateway=None) **0 blocked, 0 ô dưới sàn**.
Dừng ở đây như `full.py`: artwork (vẽ hình/ảnh) và load (cần token editor)
làm tay sau khi đọc báo cáo.
