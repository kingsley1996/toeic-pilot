# Guide: đóng vai model viết đề (chặng `write` bằng tay)

> Đúc từ lần viết tay toàn bộ tp-form-14 (200 câu, 103 ô): `check` sạch tuyệt
> đối (0 chặn, 0 cờ) ngay trước `balance`. Dành cho agent sau này nhận việc
> "đóng vai model" — tức sinh nội dung câu hỏi mà không gọi provider ngoài.
>
> Vị trí của việc này trong pipeline: đọc `EXAM-GENERATION-RUNBOOK.md` §2 trước.
> Guide này chỉ nói chặng `write` (và kiểm đi kèm), không nói `photo`/`load`/`publish`.

## 0. Nguyên tắc nền

1. **Cấu trúc là của pipeline, nội dung là của model.** Không bao giờ tự bịa số
   câu, dạng câu, vị trí hình, số văn bản. Mọi thứ đó nằm trong `blueprint.json`
   đã validate. Model chỉ điền: bối cảnh đã có → lời thoại/văn bản/câu hỏi/đáp
   án/giải thích/dữ liệu bảng.
2. **Đĩa là sự thật.** Trước khi sửa file nào, đọc bản trên đĩa. Sau mỗi loạt
   sửa, chạy `check` lại. Không tin trí nhớ, không tin bản mình "đã viết".
3. **Viết → kiểm → sửa theo metric, không theo cảm tính.** Cổng `check` là đặc
   tả thi hành được của "đề hay". Mọi luật dưới đây đều có mã nguồn tương ứng
   trong `apps/api/app/content/exam/check.py` — khi guide và code lệch nhau,
   tin code.
4. **Không đụng word-form.** Mọi phép đo của checker so chuỗi thô, **không
   stemming**: `guests`≠`guest`, `moves`≠`move`, `spaces`≠`space`,
   `evening`≠`evenings`, `reviewer`≠`review`. Muốn đáp án "chạm" ngữ liệu thì
   viết đúng dạng từ sẽ xuất hiện ở cả hai nơi. Chữ số vô hình với mọi metric
   (`[a-z]+` only): đáp án số ("Two hundred", "450,000 dong") có span/echo = 0.

## 1. Chuẩn bị: spec sheet + format mẫu

```bash
cd apps/api
# 1. In toàn bộ khung (dạng câu, topic, graphic, hard, số văn bản) của từng ô:
uv run python -c "
from pathlib import Path
from app.content.exam import blueprint as bp
plan = bp.load(Path('content/generated/<slug>/blueprint.json'))
for p in plan.parts:
    print('--- PART', p.part, '---')
    for s in p.slots:
        print(s.id, '| QT=', s.question_types, '| TOPIC=', s.topic,
              '| HARD=', getattr(s, 'hard', 0), '| GRAPHIC=', bool(s.graphic),
              '| PASS=', getattr(s, 'passages', None),
              '| IMPL=', getattr(s, 'implication_kind', None))
"
# 2. Đọc 1 file mẫu mỗi loại từ đề gần nhất (paste/ + graphics/):
#    p1-01, p2-01, p3-01, p3-11 (có hình), p4-09 (có hình), p5-01, p6-01,
#    p7-13 (đa văn bản + hình), graphics/p3-11.txt, photos/p1-01.txt
```

Định dạng dán (parser đọc đúng từng dòng, sai một dấu là chặn):

| Part | Khối | Ghi chú |
|---|---|---|
| 1 | `[QUESTION]` + `voice:` (lấy đúng voice của ô trong blueprint) + 4 lựa chọn + `Answer:` + `Explanation:` + `Source: original` | Không in đề bài. Đáp án đúng mô tả đúng 1 sự thật; mỗi nhiễu sai đúng 1 sự thật (sai vật/sai vị trí/sai hành động/sai số lượng). |
| 2 | `[QUESTION]` + `voice:` người hỏi + câu hỏi + `voice:` người đáp + **3** lựa chọn + ... | Hai giọng khác giới (nam↔nữ). Nhiễu dùng lại từ của câu hỏi rồi bẻ nghĩa. |
| 3/4 thường | `[SCRIPT]` (mỗi lượt một dòng `voice:`) + 3×`[QUESTION]` | Duo: 1 nữ + 1 nam luân phiên. Trio: 3 giọng khác nhau. |
| 3/4 có hình | như trên + file `graphics/<slot>.txt`, câu hỏi về hình ở vị trí cố định (mục 4) | Thoại cho "tọa độ", hình tra ra đáp án. Thoại KHÔNG được đọc tên đáp án. |
| 5 | `[QUESTION]` + câu có `-------` + 4 lựa chọn cùng họ từ | Mỗi câu đúng điểm ngữ pháp của host trong blueprint. |
| 6 | `[PASSAGE]` (tiêu đề + 4 đoạn, chỗ trống `------- (N)`) + 4×`[QUESTION]` dạng `Blank (N)` | Câu chèn câu: đáp án là câu hoàn chỉnh, phải nối được với câu sau chỗ trống. |
| 7 | N×`[PASSAGE]` (N = số `False` trong `slot.passages`) + các `[QUESTION]` | Văn bản có hình KHÔNG viết khối `[PASSAGE]` — dữ liệu hình nằm ở `graphics/<slot>.txt`. |
| photos/ | `photos/p1-NN.txt`: lệnh đặt ảnh tiếng Anh, chi tiết, **ghi cả thứ KHÔNG có** để khóa nhiễu (vd "No cloth is visible near his hands") | Cần cho chặng `photo` và backfill giải thích Part 1 sau này. |

`Source: original` và `Answer:` bắt buộc mọi question block, không có default.

## 2. Vòng lặp làm việc (làm đúng thứ tự này)

```
viết 1 part (paste/ + graphics/ + photos nếu có)
  → check --slug <slug> --part N
  → sửa hết ✗ (chặn nạp), rồi đến ⚠ (cần người nhìn)
  → check lại part đó cho sạch
hết 7 part → check toàn đề → balance → check lại toàn đề → graphic
trước publish → compare --slug <slug> (mục 7: 0 trùng khít mới được lên)
```

Lệnh:

```bash
uv run python -m app.content.generate_exam check --slug tp-form-14 --part 3
uv run python -m app.content.generate_exam check --slug tp-form-14   # toàn đề
uv run python -m app.content.generate_exam balance --slug tp-form-14 # cân A/B/C/D
uv run python -m app.content.generate_exam graphic --slug tp-form-14 # render PNG
```

`balance` xáo vị trí đáp án toàn đề (đích ~25% mỗi chữ). Chạy sau khi nội dung
đóng băng, rồi `check` lại một lần nữa.

## 3. Probe: đo bằng đúng hàm của checker

Đừng đoán echo bằng mắt. Viết script nhỏ import thẳng hàm của checker
(`check.echo`, `check.evidence_sentences`, `check.check_implication`,
`check.check_leakage`, `parse_group`) rồi in bảng echo từng lựa chọn + span
từng đáp án đúng của mỗi ô. Mọi con số trong mục 4 đều đo bằng cách này.

```python
from app.content.exam import check as C
questions, script, _ = C.parse_group(block, part, len(slot.question_types), None)
for q in questions:
    for o in q.options:
        print(o.label, C.echo(C.option_text(o), script))  # < 0.2 = "không nhắc tới"
    gold = [C.option_text(o) for o in q.options if o.is_correct]
    print("span:", C.evidence_sentences(gold[0], script))  # số câu ngữ liệu chạm tới
```

Lưu ý: với ô có hình Part 3/4, `script` mà checker dùng = lời thoại + chữ thay
ảnh (alt text). Tên người/vật trong bảng vì thế cũng "có mặt trong ngữ liệu".

## 4. Luật kiểm — bản cô đọng để viết đúng ngay lần đầu

### 4.1. Nhiễu phải nhại lời thoại (Part 3/4, chặn)

`echo(lựa chọn, ngữ liệu)` = tỉ lệ từ nội dung (dài >2, trừ stopword) của lựa
chọn có mặt trong ngữ liệu. Ngưỡng `UNRELATED = 0.2`. Mỗi câu hỏi: **nhiều
nhất MỘT nhiễu được dưới ngưỡng**, còn lại phải nhại từ đã nói rồi bẻ nghĩa.
Câu hỏi về hình được miễn (lựa chọn của nó bắt buộc là nhãn trục).

Thực hành: khi viết nhiễu, bê nguyên 1–2 từ nội dung từ thoại vào rồi đổi nghĩa
(vd thoại "overnight shift" → nhiễu "overnight bus"). Đếm từ chung với probe,
không áng chừng — số nhiều/số ít là hai từ khác nhau (mục 0).

### 4.2. Rò rỉ chéo (mọi part có cụm, chặn)

Không lựa chọn nào được chứa **≥2 từ RIÊNG của đáp án đúng câu khác** trong
cùng cụm ("từ riêng" = từ không có mặt ở nhiễu của câu kia). Kiểm cả hai chiều.
Đây là lỗi dễ mắc nhất khi viết nhanh: đáp án Q1 là "the downtown branch" thì
mọi lựa chọn Q2/Q3 chỉ được chạm tối đa 1 trong các từ đó.

Thực hành: sau khi chốt đáp án đúng mỗi câu, liệt kê từ riêng của chúng rồi rà
toàn bộ lựa chọn còn lại. Paraphrase là bạn: "downtown branch" ở đáp án thì chỗ
khác viết "city center".

### 4.3. Độ phủ gom hai chỗ (ô `hard`, chặn; ô thường: cờ)

Ô hard (toàn bộ Part 3/4; Part 7 theo cờ từng ô) cần ≥1 đáp án đúng chạm **≥2
câu/văn bản** của ngữ liệu. Cách viết: câu hỏi mà đáp án phải ghép hai chi tiết
rời ("ngày ở lượt trước, giờ ở lượt sau"; "điều kiện ở email + giá ở bảng").

Ngoại lệ thiết kế (không phải lỗ hổng để lợi dụng, nhưng phải biết để khỏi sửa
oan): đáp án không đo được (số thuần túy, marker `[2]`) cho span 0, và **một
span 0 làm cả phép kiểm tắt** — vì kết luận "không câu nào ghép hai chỗ" đòi đo
được mọi câu. Cụm có câu chèn `[N]` vì thế luôn qua cổng này; độ khó của nó nằm
ở chính dạng câu chèn.

### 4.4. Hàm ý đúng biến thể (Part 3/4, chặn theo kind)

- kind 0 (quote-a-line): đề bài phải trích `"..."` sau says/writes, và lời trích
  phải có NGUYÊN VĂN trong thoại. Mẫu: `What does X mean when she says "..."?`
- kind 1 (suy từ hai chi tiết rời): đáp án đúng chạm ≥2 câu thoại (đo như 4.3).
- kind 2/3: không có dấu vết tất định — viết đúng tinh thần biến thể, `--verify`
  giữ phần còn lại.
- Part 7 có 2 câu hàm ý kind 0 (theo `implication_kind` của ô): cũng phải trích
  nguyên văn (`writes` cho chat/email).

### 4.5. Hình ngữ liệu (chặn)

- Vị trí: Part 3 câu thứ BA, Part 4 câu thứ HAI là `Look at the graphic`,
  đúng một câu mỗi cụm. Part 7 không cần cụm từ này (dùng "According to the
  chart/schedule/...").
- Bốn lựa chọn của câu hỏi hình **phải bằng đúng trục đáp án** (không kể thứ
  tự): table = tên hàng; schedule = TIÊU ĐỀ CỘT (khung giờ), cột đầu là tên
  người; chart = nhãn cột; map = tên ô (phần trước dấu `:`); survey vẽ như
  schedule nên trục là tiêu đề cột; form vẽ như table.
- schedule: mọi tên ở cột đầu phải xuất hiện trong thoại (chuẩn hoá, đúng dạng
  từ). Thiết kế dữ liệu sao cho đáp án là duy nhất (vd đúng một cột cả ba cùng
  trống).
- Thoại/bài đọc không được chứa nguyên văn mục đáp án đúng (cờ). Kỹ thuật chuẩn
  theo mẫu đề thật: thoại cho GIÁ TRỊ ("thirty thousand"), hình ánh xạ giá trị
  → nhãn ("Search Ads = 30"); thoại cho QUAN HỆ VỊ TRÍ ("lower left corner"),
  hình tra ra ô.
- Ngữ pháp file `graphics/<slot>.txt`: dòng 1 `kind: <table|schedule|chart|map|
  survey|form>`, dòng 2 tiêu đề (không chứa `|`), rồi hàng tiêu đề cột (chỉ
  table/schedule/survey; chart/map/form KHÔNG có), rồi các hàng `|`-phân cách.
  **Giữ dấu `|` cuối hàng schedule** — ô trống cuối hàng chính là dữ liệu (khung
  giờ rảnh). Giới hạn hàng Part 3/4: table 3–6, schedule 2–4, chart 3–6, map
  đúng 4 ô. Part 7 nới hơn (table 3–12...). Không chép ví dụ trong prompt.

### 4.6. Dạng câu Part 7 (chặn)

- Chèn câu: ngữ liệu phải có đủ dấu `[1]`–`[4]`, bốn lựa chọn phải đúng là
  `[1]` `[2]` `[3]` `[4]`.
- Từ vựng ngữ cảnh: từ hỏi (`\bword\b`, không phân biệt hoa thường) xuất hiện
  **đúng một lần trong toàn cụm** — kể cả dòng Subject. Muốn hỏi "cancelled"
  thì trong bài chỉ được có đúng một "cancelled" (và đừng để "Cancelled" ở
  subject tính ké).
- Trích dẫn trong `Explanation:` phải có nguyên văn trong ngữ liệu đối chiếu
  (= khối dán trừ dòng giải thích + nội dung thô file graphics của Part 7).
  **Không trích diễn đạt tiếng Việt của mình** ("một nửa có mái" mà bài không
  có thì thành cờ). Chỉ trích tiếng Anh có thật.
- Cụm NHIỀU văn bản (hard): phải có một lời giải trích dẫn (mỗi trích ≥12 ký
  tự) từ **hai tài liệu khác nhau** — đó là "câu bắc cầu" chứng minh cụm đáng
  tồn tại. Thiết kế trước cặp trích dẫn khi viết câu hỏi loại này.
- Part 7 KHÔNG chịu luật nhiễu-nhại (4.1), nhưng vẫn chịu rò rỉ (4.2), phủ
  (4.3, nếu hard), và đếm số file hình (`graphics/<slot>.txt` phải đủ đúng số
  passage hình của ô).

### 4.7. Giải thích + độ dài (cờ, nhưng viết sạch từ đầu đỡ tốn lượt)
- `Explanation:` tiếng Việt, mở đầu bằng luận cứ cho đáp án đúng rồi mổ từng
  lựa chọn theo mẫu `| (X) "nguyên văn lựa chọn" — phân tích`. Nguyên văn trong
  ngoặc kép phải khớp lựa chọn (checker đối chiếu).
- Giữ 4 lựa chọn dài tương đương nhau. Đáp án số dễ bị cờ "dài bất thường":
  đệm đơn vị vào đáp án ngắn (`"Ten seats"` thay vì `"Ten"`) và san đều đáp án
  dài, thay vì rút ngắn đáp án đúng.
- Không bao giờ in tên giọng (`uk_female_1`...) vào lựa chọn — đó là chỉ dẫn thu
  âm, in ra là chặn.

### 4.8. Giọng đọc

- Part 1: lấy đúng `voice` của ô trong blueprint.
- Part 2: người hỏi + người đáp khác giới. Part 3 đôi: nữ nói trước, nam nói
  sau, luân phiên cặp quốc tịch; ba người: 3 giọng phân biệt. Part 4: một giọng
  suốt bài. Giọng chỉ nằm ở dòng `voice:`, không bao giờ nằm trong nội dung.

### 4.9. Quota từ hiếm bị kiểm tra (cấp đề, chặn)

`check_tested_vocabulary` đếm CÂU (không đếm từ): đáp án đúng P5 có BẤT KỲ từ
nội dung nào ngoài `frequent_words.txt` (10k từ vendored), hoặc từ hỏi nghĩa
của câu VIC ngoài danh sách đó. Đề cần **≥5 câu** (băng đo được: 07 có 4 và là
đề yếu nhất họ; 08/09/11/12/14 có 5–9). Dưới ngưỡng là block cả đề.

Đáp án ngữ pháp ("worked", "was calculated") toàn từ phổ thông nên tự rớt khỏi
phép đếm — không cần phân biệt câu vocab/grammar bằng nhãn. Đề viết dở (thiếu
tệp) thì cổng im lặng, để cổng từng-ô báo thiếu.

Khi cổng đỏ: nâng từ đúng P5-vocab và target VIC lên band B2+ (prompt part5/
part7 đã dặn sẵn band này — xem mục 0 của prompt). Cặp nâng đã kiểm chứng:
evaluation→(viết lại câu)postpone, celebrate→commemorate,
accommodate→(viết lại câu)inconvenienced, launch→rollout. Verify từng từ mới
với wordlist trước khi thay (appraisal tưởng hiếm mà hóa phổ thông!). VIC target
mới phải xuất hiện đúng 1 lần trong cụm (kể cả dòng Subject).

### 4.10. Cờ thể tích văn bản (cờ)

Tripwire dưới min toàn họ (content-word của thoại/văn bản): P3/P4 ≥30, P6 ≥80,
P7 ≥25/50/80 theo số văn bản chữ. Im lặng với mọi đề đã chấp nhận — chỉ nổ khi
ngữ liệu ngắn hơn bất cứ thứ gì từng đạt (vd 3 văn bản P6 của tp-form-14 chỉ
44–65 từ). Nổ thì NỞ VĂN BẢN, đừng hạ sàn.

Kỹ thuật nở metric-neutral: thêm câu bằng từ vựng MỚI (không xuất hiện ở bất
kỳ lựa chọn/đáp án nào). Mọi phép đo ngữ nghĩa (echo, span, leak) đều là phép
giao — từ mới không giao với đáp án nên không nhúc nhích số nào, chỉ tăng thể
tích. Cấm thêm câu chứa từ đã có trong đáp án đúng câu khác (vỡ leak), cấm thêm
tình tiết làm đáp án khác thành đúng.

Riêng Part 6 hầu như không có cổng ngữ nghĩa (miễn echo, balance, spread, leak —
chỉ còn form, trích dẫn, thể tích), nên nở P6 là an toàn nhất. Part 3/4 thì mỗi
từ thêm vào đều có thể lật balance — nở xong chạy lại `check --part`.

### 4.11. Cân paraphrase (cấp cụm Part 3/4, chặn)

Trong các câu "đo được" (detail/request/future/graph — trừ implication, topic,
speaker, location): nhiều nhất 1 câu có đáp án đúng GIỐNG thoại nhất, nhiều
nhất 1 câu ÍT GIỐNG nhất. Thực hành: đừng để ≥2 đáp án đúng cùng là "bê nguyên
cụm từ" trong khi nhiễu toàn diễn đạt lại (hoặc ngược lại). Probe hiện số này;
sửa bằng cách nâng echo của nhiễu (nhại thêm từ thoại) hoặc hạ echo của đáp án
đúng (diễn đạt lại sâu hơn) — miễn là span hai chỗ (4.3) còn nguyên.

## 5. Bẫy đã gặp (đọc trước khi viết để khỏi trả giá lại)

1. **Nháp đầu viết nhiễu "sạch"** (tự bịa, không dùng từ thoại) → 24 chặn ở
   Part 3. Bài học: nhiễu HAY = nhại từ thoại + bẻ nghĩa, không phải bịa chuyện
   lạ. Sửa bằng cách nhét 1–2 từ thoại vào mỗi nhiễu.
2. **Hiểu sai vị trí câu hỏi hình**: tưởng Part 4 cũng câu cuối — sai, Part 4 là
   câu thứ HAI (đề mẫu ETS). Câu hỏi hình được miễn echo + miễn cờ độ dài, nên
   đừng "sửa" lựa chọn của nó cho ngắn/nhại.
3. **Trục schedule lấy nhầm**: viết brief "cột Thời gian và Hoạt động" là ra
   `table` chứ không phải `schedule`. Schedule là lưới người × khung giờ, đáp án
   là tiêu đề cột, ô trống là dữ liệu.
4. **Quote kind 0 sai một dấu** (thiếu dấu chấm, sai hoa/thường không sao vì
   chuẩn hoá — nhưng thiếu/t Thừa từ là chết). Copy-paste nguyên văn từ thoại,
   đừng gõ lại.
5. **Rò rỉ chỉ kiểm một chiều.** Sửa Q2 xong lòi leak Q1↔Q3. Mỗi lần đổi một
   lựa chọn, rà lại cả hai chiều với đáp án đúng mọi câu còn lại.
6. **Đếm câu toàn đề để biết câu nào là câu nào.** Báo lỗi ghi số câu toàn đề
   (Part 3 bắt đầu 32, Part 4 từ 71, Part 7 từ 147...). Đối chiếu blueprint để
   biết slot nào trước khi sửa.
7. **Đừng nhầm brief với dữ liệu.** Brief hình trong blueprint là văn xuôi mô
   tả; file `graphics/*.txt` mới là thứ checker đọc. Hai thứ phải khớp nhau về
   nội dung (tên, số lượng mục), nhưng định dạng thì theo ngữ pháp mục 4.5.
8. **File bị thay dưới tay.** Nếu lỗi đã sửa sạch bỗng quay lại hoặc nội dung
   file khác điều mình vừa ghi: dừng, đọc lại đĩa, hỏi người chạy song song
   (có thể ai đó đang chạy `write`/`full` cùng slug). Không sửa mù trên trí nhớ.
9. **Motif mới lọt lưới → bổ sung bảng + test ghim.** `PART1_MOTIF_KEYWORDS`
   (mixes.py) chỉ bắt được motif có từ khóa trong bảng — tiệm cắt tóc và trạm
   xăng từng lọt vì bảng không có chúng. Gặp cảnh mới lọt: thêm một mục từ khóa
   (viết theo cách bối cảnh vẫn được viết, để substring bắt được) + một test
   theo mẫu `test_part1_avoid_catches_barber_and_gas_station`.

## 6. Khối lượng và nhịp thực tế (để ước lượng)

- Part 1: 6 câu + 6 lệnh ảnh. Part 5: 30 câu đơn (nhanh nhất). Part 2: 25 cặp.
  Part 6: 4 văn bản × 4 câu. Part 4: 10 bài (mỗi bài 3 câu). Part 3: 13 thoại
  (đắt nhất vì 4.1 + 4.2 + 4.4 cùng đánh). Part 7: 15 cụm, 54 câu (đắt nhì vì
  4.6 + trích dẫn chéo).
- Thứ tự khuyên dùng: 1 → 5 → 2 → 6 → 4 → 3 → 7 (dễ trước, khó sau; luật học
  được ở part dễ áp thẳng vào part khó).
- Mỗi part: viết xong → `check --part` → sửa đến 0 ✗ 0 ⚠ → sang part kế. Không
  dồn sửa cuối: lỗi leak/spread chỉ lòi khi đọc cả cụm, càng để lâu càng khó
  lần.

## 7. Lệnh `compare` (chạy trước publish)

```bash
uv run python -m app.content.generate_exam compare --slug <đề-mới> [--against form-07,form-08]
```

Không `--against` thì so với mọi thư mục còn lại. Ba phần ra:

1. **Trùng lặp câu hỏi** (stem + lựa chọn, trigram-Jaccard): trùng KHÍT thì
   exit 1 — đề bị lộ, chặn publish. Gần-đúng (≥0.8) chỉ liệt kê để người duyệt
   (câu cùng khuôn TOEIC giống nhau một nửa là bình thường; họ đề đo được
   max-sim 0.35–0.48).
2. **Thể tích + band từ** đặt cạnh họ đề (tham khảo): tổng content-word, dài TB,
   % ngoài-10k. Đề mới hụt thể tích (tp-form-14 chỉ bằng ~72% họ) lòi ngay ở bảng
   này trước khi ai phải đọc từng văn bản.
3. Thể tích chỉ đếm chữ người học thấy (đề, lựa chọn, thoại/văn bản) — dòng
   `Explanation:` tiếng Việt lẫn vào là vỡ phép đo, code đã trừ sẵn.
