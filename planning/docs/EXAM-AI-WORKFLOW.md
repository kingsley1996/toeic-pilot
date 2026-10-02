# Quy trình tạo đề thi từ AI (end-to-end)

Tài liệu này mô tả toàn bộ đường đi từ "chưa có gì" tới "đề thi nằm trên
production", gồm vai trò của AI ở mỗi bước, lệnh chạy, cổng kiểm tra và ngưỡng
số. Chi tiết từng khâu nằm ở các spec riêng (mục 12); đây là bản đồ toàn cảnh.

Quy ước: mọi lệnh chạy từ `apps/api` bằng `uv run`. API runtime không bao giờ
import `app.content` — code sinh đề là công cụ offline, không phải một phần
server.

## 1. Đề thi gồm gì

Một đề full = **103 ô (slot) / 200 câu**:

| Part | Ô | Câu | Ghi chú |
|------|-----|------|---------|
| 1 | 6 | 6 | tranh, lời đọc treo ở từng câu, không in chữ |
| 2 | 25 | 25 | hỏi–đáp, chỉ 3 lựa chọn A–C, 8/25 câu trả lời gián tiếp |
| 3 | 13 | 39 | hội thoại, 3 câu/cụm; cụm có hình thì câu hình nằm ở vị trí thứ 3 |
| 4 | 10 | 30 | độc thoại, 3 câu/cụm; câu hình ở vị trí thứ 2 |
| 5 | 30 | 30 | câu lẻ, đánh số 101–130 |
| 6 | 4 | 16 | 4 đoạn văn × 4 câu, câu điền câu chỉ ở blank 3 hoặc 4 |
| 7 | 15 | 54 | 10 cụm đơn + 2 đôi + 3 ba, 2–5 câu/cụm |

Số câu in trên đề (`number`) đi liền mạch 1–200: P2 từ 7, P3 từ 32 (cách 3),
P4 từ 71 (cách 3), P5 từ 101, P6 từ 131 (cách 4), P7 cộng dồn 147–200.

## 2. Hai pipeline viết nội dung

| | `exam_cli` cổ điển | `exam_agents/upgraded` (bản chính cho đề mới) |
|---|---|---|
| Đơn vị làm việc | cả lượt `--limit`, hỏng 1 ô không dừng | từng slot, tối đa 3 revision |
| Vòng sửa lỗi | `_fix_pass`: checker miễn phí viết lại 1 lần | vòng critic: findings có cấu trúc + evaluator LLM lập kế hoạch sửa (giữ gì/sửa gì) |
| Check tốn tiền | tách hẳn (`check --verify` chạy sau cùng) | nhúng trong vòng, chỉ chạy khi check miễn phí đã sạch |
| Ô hỏng dai | nằm lại `paste/`, chờ `prune` tay | `escalated`, giao người kèm log |
| Trạng thái | file trên đĩa là sự thật | + checkpoint LangGraph |

`upgraded/` dừng ở text. Các khâu `plan`, `photo`, `graphic`, `load`, `label`,
`media`, `compare`, `balance` chỉ có ở `exam_cli` — đề mới đi graph tới khi text
sạch rồi quay lại CLI cho artwork + nạp DB. Vá lẻ, debug prompt, kiểm tra nhanh
dùng CLI (`write --part --limit`, `prompt`, `check`, `prune --slot`).

Skill `exam-model` là cách vận hành chuẩn cho đề mới: model viết plan/context
→ chạy graph qua `FakeGateway` → retry tới 0 escalated → `balance` → `check`.
Vật liệu trung gian nằm ở `/tmp` (`run_<slug>.py`, `drafts_<part>.json`,
`plan*.txt`, `spec*.txt`).

## 3. Giai đoạn 1 — Plan: khóa cấu trúc trước khi gọi model

Lệnh: `uv run python -m app.content.generate_exam plan --slug tp-form-XX --part N [--model ...]`
(`exam_cli/plan.py` → `exam/blueprint.py`). Có thể chạy từng part; `merge()` cộng
dồn, không ghi đè part khác.

Output: `content/generated/<slug>/blueprint.json` — `Blueprint{slug, title, seed,
parts[]}`, mỗi part là danh sách `QuestionSlot`. Các trường slot quan trọng:

- Chung: `id` (= tên file dán, vd `p5-17`), `number` (số câu thật), `context`
  (bối cảnh — KHÔNG phải nội dung câu hỏi).
- Ô một câu (P1/2/5): `question_type` (số ít), `grammar` (P5: 11 mã, P6: 6 mã —
  dùng chéo part là lỗi).
- Ô cụm (P3/4/6/7): `question_types[]` (+ `grammars[]` song song, chỉ P6).
- Nghe: `voice`/`voices[]` (P2 đúng 2 giọng khác giới, P3 2–3, P4 đúng 1; cấm 3 ô
  liền cùng dàn giọng; accent chia ~25% mỗi loại). P1 thêm `people: one|several|none`
  (đủ cả 3 dạng mỗi đề) và 6 scene `TYPE|people|scene` chống trùng 8 đề gần nhất.
- P2: `indirect` + `indirect_kind` (0–3), `how_variant` (0–5).
- P3/4: `topic`, `graphic: "kind: mô tả"` (P3: 3 cụm cuối, P4: 2 cụm cuối; có nhãn
  `GRAPH_OR_TABLE` ⇔ phải có hình và ngược lại), **`hard=1` ép cứng mọi ô**,
  `implication_kind` 0–3 quay vòng (≤1 câu hàm ý/cụm).
- P6: `topic` = dạng văn bản, 4 câu/văn bản.
- P7: `topic`, `structure` (khớp số `passages`), `passages[]` (`""` = đoạn chữ,
  `"kind: mô tả"` = đoạn hình vẽ, 1–3 phần tử), `hard=1` nếu nhiều đoạn hoặc ≥3 câu.

Vai trò AI ở plan: chỉ sinh **nội dung** (context, brief hình) — cấu trúc (số câu,
dạng câu, vị trí hình, dàn giọng) lấy từ bảng `PART*_MIX` tĩnh, hỏng thì fallback
bảng. Người khóa blueprint bằng `check --slug` (validate cấu trúc).

`seed` suy tự động từ `sha256(slug)` (không dùng `hash()`), lái đích balance đáp
án + xáo trộn P5.

## 4. Giai đoạn 2 — Write: viết từng ô, check hai tầng

Lệnh: graph `run_pending` (đề mới) hoặc `write --slug [--part] [--limit]` (vá lẻ).
Hàng đợi = "ô nào chưa có file `paste/<slot>.txt`"; ghi đĩa ngay sau mỗi ô nên
lúc nào cũng tiếp tục được.

Vòng đời một ô: `write → check → sạch thì accept | hỏng thì critic → còn vòng thì
write lại / hết 3 vòng thì escalate giao người`. File dán của ô escalate được giữ
lại; muốn viết lại phải xóa file hoặc `prune`.

Lúc viết, khối text được tách ngay: `[PHOTO]` → `photos/`, `[GRAPHIC]` →
`graphics/`, còn lại → `paste/`. Ô nhiều hình: `graphics/p7-15-1.txt, -2.txt`.

**Check tầng 1 (miễn phí, parser thật + luật code) luôn chạy.** Những cổng chính:

- Cấu trúc (block): mọi `[QUESTION]` phải có `Answer:` + `Explanation:` + `Source:
  original`; số câu/cụm đúng (`QUESTIONS_PER_SET`: P3/P4 = 3, P6 = 4, P7 = 2–5);
  P2 đúng 3 đáp án; `[PASSAGE]` blank `------- (N)`; `voice` đúng giọng blueprint;
  `[GRAPHIC]` dòng 1 là `kind: table|schedule|chart|map|survey|form`, dòng 2 là tiêu
  đề riêng; P1/P2 `prompt=None`.
- Nhiễu nhại thoại P3/4 (block): tỉ lệ từ nội dung đáp án xuất hiện trong thoại
  (`echo`), mỗi câu tối đa **1 nhiễu < 0.2** (`UNRELATED`). Câu hỏi hình được miễn.
- Cân paraphrase P3/4 (block): tối đa 1 câu đáp đúng giống thoại nhất, tối đa 1 câu
  ít giống nhất (trừ câu implication/topic/speaker/location).
- Ghép 2 chỗ / `hard` (block nếu ô hard, cờ nếu không): ô `hard=1` cần ≥1 đáp đúng
  chạm ≥2 câu/văn bản. Im lặng nếu bất kỳ câu nào span 0 (đáp số, marker, NOT/EXCEPT).
- Bắc cầu P7 nhiều tài liệu (block): phải có 1 Explanation trích nguyên văn (mỗi
  mảnh ≥12 ký tự) từ 2 tài liệu khác nhau.
- Hình (block): đúng 1 câu `Look at the graphic`, ở P3-câu-3 / P4-câu-2; 4 đáp án
  bám đúng trục kind (table = tên hàng 3–6 hàng, schedule = tên cột 2–4, chart = nhãn,
  map = đúng 4 ô); thoại nêu tối đa 1/4 mục, không nêu mục thắng; nhìn hình một mình
  không đủ trả lời.
- Rò rỉ chéo (block): không lựa chọn nào chứa ≥2 từ riêng của đáp đúng câu khác
  cùng cụm (kiểm 2 chiều).
- VIC P7 (block): từ hỏi xuất hiện đúng 1 lần toàn cụm, band B2+.
- Tested vocab cấp đề (block): đáp đúng P5 có từ ngoài `frequent_words.txt` (10k từ),
  hoặc target VIC ngoài list — cần **≥5 câu** (đếm câu, không đếm từ).
- Thể tích (cờ): P3/P4 ≥30, P6 ≥80, P7 ≥max(60, 20×số câu) content-word.

**Cấp đề** (`balance` sửa được): đáp án mỗi chữ **≤40%** toàn đề
(`ANSWER_SKEW_LIMIT`); nhiễu Yes/No ở câu WH P2 **≤30%** (phải sinh lại, cổng gọi
đích danh phần vượt).

**Check tầng 2 (`--verify`, tốn tiền) chỉ chạy cho ô đã sạch tầng 1**, và nên dùng
model **khác** model viết (tránh tự chấm bài mình). Kết quả verify là cờ, không
block (trừ verdict luật hình). Dùng sai chỗ (bật toàn đề P1/2/5/6) chỉ tốn tiền mà
không thêm problem nào.

**Explanation** (bắt buộc 200/200 câu): tiếng Việt 2–4 câu, dạng
`… | (X) "nguyên văn lựa chọn" — phân tích`; mọi đoạn EN trong `""` phải là chuỗi
con của script/đoạn văn/lựa chọn; chữ nêu phải khớp đáp án đúng. Chi tiết:
`SPEC-EXPLANATIONS.md`.

## 5. Giai đoạn 3 — Cân bằng cấp đề

`balance --slug`: hoán vị nội dung options để đưa đáp án đúng về đích, gán vòng
tròn A→B→C→D **trong từng part** (xoay theo seed). Đích ~25% mỗi chữ. **Chạy sau
khi đóng băng nội dung, trước `load`** — vì balance ghi đè file dán.

`spread` = kiểm phân bố đáp án toàn đề (cổng `check_answer_spread`): lệch mà kiểm
từng câu không thấy (vd 29/30 câu đáp án A). Bỏ qua khi đề thiếu ô.

## 6. Giai đoạn 4 — Hình ảnh (người nhìn bằng mắt trước khi chốt)

- `graphic --slug`: render hình ngữ liệu P3/4/7 từ `graphics/*.txt` → PNG +
  `.alt.txt` (vẽ bằng code từ dữ liệu bảng, không gọi model ảnh). Tên P7 mang số
  ô ngữ liệu (`p7-15-s2.png`). Thiếu alt text thì gắn ảnh lỗi 409.
- `photo --slug`: vẽ 6 ảnh P1 từ `photos/*.txt` bằng model ảnh (người tự gen ảnh
  từ prompt cũng được — chỉ cần file PNG đúng tên). **Bắt buộc nhìn ảnh trước
  `--commit`**: brief đặt hàng ≠ ảnh giao (model từng vẽ thừa người).
- `attach-images --slug --part 1 [--commit]`: gắn ảnh đĩa vào DB đã load. Mặc định
  chỉ in bảng khớp; `--commit` mới ghi. Khớp tự động: P1 theo `number`, P3/4 theo
  `index`, P7 theo `passage`.

Git: commit `blueprint.json`, `paste/`, `graphics/`, `graphic-images/`, `photos/`;
ignore `images/`, `media/*.mp3`, `verify/`.

## 7. Giai đoạn 5 — Nạp DB dev + audio + media

Thứ tự chuẩn: `graphic`/`photo` → `load` → `backfill_audio` → `attach-images`
→ `media --push` → `check --verify` → `compare` → publish → sync prod.

- `load --slug --token <editor>`: nạp qua **đúng đường dán của admin**
  (`POST /parts/{part}/parse` → `POST /parts`), validators vẫn chạy, đề ở
  `draft`. `commit_part` **cộng thêm** — nạp lại cả đề không lọc sẽ nhân đôi câu,
  vá lẻ phải `--part`/`--slot`. Nạp trọn đề tự chạy `apply_labels`; nạp lẻ thì bỏ qua.
- `label [--dry-run]`: gán nhãn phân loại **từ blueprint, không đoán bằng LLM**
  (`proposed_code=NULL`, không ghi đè hàng đã có). Cấp câu: `question_type(s)` +
  `grammar(s)`; cấp cụm (khi có `set_id`): `topic` + `structure`. Ánh xạ ô → câu
  qua **số câu trên đề**: câu thứ `index` của ô nằm ở `slot.number + index`.
- `backfill_audio --only questions`: tổng hợp TTS. Hàng đợi là truy vấn "thiếu
  audio hoặc script đổi". Audio 2 tầng: P1/2 treo ở `question`, P3/4 treo ở
  `question_set`; P5/6/7 không cần audio. Sửa script làm audio stale + câu về
  draft. Kiểm tra giọng ngoài trước: `TOEIC_ALLOW_EXTERNAL_TTS=1 pytest -m external`.
- `media --slug` (kiểm) → `media --push` (đẩy): DB đúng mà bytes chưa lên provider
  thì nút play im lặng/ảnh 404 — **luôn push ngay trước khi báo test xong**. Kiểm
  cả 2 tầng (câu P1/2 + cụm P3/4), curl kiểm 200/206.

Lỗi đã gặp 2 lần: hai tiến trình backfill cùng lúc chèn trùng `audio_asset`
(`IntegrityError` ở `storage_key`) — cơ chế là race, không phải dữ liệu sai; chạy
lại `dry-run`/`--only questions` để xác nhận đủ rồi đi tiếp.

## 8. Giai đoạn 6 — Verify, compare, prune (trước publish)

- `check --slug --verify`: xáo đáp án rồi đối chiếu bằng LLM.
- `compare --slug [--against ...]`: so đề mới với họ đề cũ trên `paste/`. Trùng
  khít (trigram-Jaccard sau chuẩn hóa) → exit 1 **chặn publish**; gần-đúng ≥0.8
  chỉ liệt kê (họ đề max-sim 0.35–0.48 là bình thường). Kèm bảng thể tích + band từ
  (neo mẫu ETS: ≤1k 53%, ≤3k 80%, ngoài-10k 7%).
- `prune --ambiguity` (bắt buộc ở P5): không cổng tất định nào bắt được lỗi "2
  phương án cùng đúng", phải chạy riêng; có guard phát hiện người chấm trả lời
  phản xạ (≥70% cùng đáp án → tắt kiểm).
- P1 không có cổng tất định nào kiểm ảnh — kiểm bằng mắt người.

`0 blocked` ≠ sạch: P5 ambiguity và ảnh P1 nằm ngoài luồng cổng chính.

## 9. Giai đoạn 7 — Publish: người quyết, máy chặn

Qua `/admin/tests/<slug>`, tay hoàn toàn, không CLI, không tự động. Cổng publish
(`media_state`) từ chối khi audio thiếu/lệch. Vá giải thích đề cũ dùng
`backfill_explanations --test ... --part N [--dry-run]` (~$0.0007/câu), chạy thật
thì bỏ `--dry-run`.

## 10. Giai đoạn 8 — Sync production

- Đề mới: `./scripts/export-test.sh <slug> /tmp/<slug>.sql` (clone dev DB → giữ
  đúng tập bảng của đề + lọc đúng 1 slug + assets dạng `INSERT … ON CONFLICT DO
  UPDATE`, đầu file có khối reset idempotent) rồi
  `docker run --rm -i postgres:17 psql "$PROD_DATABASE_URL" -v ON_ERROR_STOP=1 -q < file`.
  Kiểm tra count `practice_test` / `practice_test_question` / audio trên prod.
  Diễn tập scratch trước khi ghi production; rotate URL nếu lộ.
- Vá giải thích đề cũ: `export-explanations.sh` (chỉ `UPDATE`, kiểm không có
  DELETE/INSERT). **Không** dùng `export-test.sh` cho việc này — nó thay cả đề +
  xóa attempt (mất lịch sử học viên của đề đã publish).
- Placement: `export-placement.sh` (chỉ `practice_test` + `practice_test_question`).
  Đề placement dùng chung câu với đề gốc — chạy nhầm script sẽ thủng đề gốc.
- Vocab/dictation: `dump_learning_content.py` (toàn `ON CONFLICT DO UPDATE`).

Chi tiết: `SYNC-TEST-TO-PRODUCTION.md`.

## 11. AI làm gì, người làm gì

| Giai đoạn | AI (model) | Người |
|---|---|---|
| Plan | sinh context + brief hình | khóa blueprint, validate, giữ `kind`/số câu/vị trí giọng |
| Write/slotloop | sinh khối, critic chấm (khung SUMMARY/CHANGES/PRESERVE/RISK) | viết lại chỗ hỏng, quyết ô escalate |
| Check | luật code chạy máy; verify dùng model khác model viết | đọc ✗ block trước, ⚠ flag sau; duyệt cờ thin-paraphrase, số học |
| Balance/spread | máy xáo + đo | chạy sau đóng băng nội dung, kiểm lại |
| Graphic/photo | render PNG từ dữ liệu bảng; draft ảnh P1 | **nhìn** ảnh P1 trước commit |
| Load/audio/media | `backfill_audio`, `push_media` (hàng đợi = truy vấn) | cấp token editor, kiểm giọng, push trước khi báo xong |
| Publish/sync | script export idempotent | quyết publish; chọn đúng loại export; kiểm count prod |

## 12. Lỗ hổng đã biết (đừng đọc dashboard sai vì chúng)

1. **Cột `difficulty` trong DB mọi câu đều là 3** — pipeline load không truyền độ
   khó thật. Đếm nó chỉ để lộ ra sự thật đó.
2. **`hard` trong blueprint KHÔNG phải độ khó** — là ràng buộc sinh đề (mỗi ô có
   bấy nhiêu câu ghép chứng cứ 2 nơi), P3/P4 ép cứng mọi ô. Đừng quy ra "câu khó".
3. **P5 ambiguity và ảnh P1 không có cổng tất định** — `0 blocked` chưa có nghĩa là sạch.
4. Ngưỡng thể tích P7 ghi khác nhau giữa 3 tài liệu (25/50/80 theo số văn bản vs
   max(60, 20×câu)) — chưa chốt bản nào là cổng.
5. Hai thước vocab chồng nhau (`frequent_words.txt` 10k trong cổng vs band ETS
   google-10000 trong SPEC-DIFFICULTY) — chưa chốt thước nào.
6. Tốc độ đọc giữ -20% (124 vs 150–160 wpm) là nợ có ý thức: đổi `tts_rate` dời
   `source_hash` → recast cả thư viện.

## 13. Tài liệu chi tiết từng khâu

- `EXAM-GENERATION-RUNBOOK.md` — lệnh từng bước + sự cố đã gặp.
- `EXAM-GRAPH.md` — đồ thị `plan → slotloop → balance → spread` + vòng đời một ô.
- `EXAM-WRITE-GUIDE.md` — luật viết + cổng check chi tiết.
- `SPEC-EXAM-DIFFICULTY.md` — trục khó, band từ, volume.
- `SPEC-EXPLANATIONS.md` — định dạng + coverage giải thích.
- `SPEC-EXAM-VISUALS.md` — quy định hình P3/4/7 + ảnh P1.
- `MEDIA-PIPELINE.md` — audio TTS + push provider.
- `SYNC-TEST-TO-PRODUCTION.md` — export/import prod, phân biệt 3 loại export.
- Skill `exam-model` — cách vận hành chuẩn tạo đề mới (`plan → slotloop → balance`).
