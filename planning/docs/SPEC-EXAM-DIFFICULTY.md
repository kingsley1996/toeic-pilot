# Độ khó của đề tự sinh — SPEC

Vì sao đề sinh ra dễ hơn đề thật, và trục nào trong `mixes.py` sửa được điều đó.

Ngày khảo sát: **2026-09-07**. Đo trên `tp-test-09`, `tp-placement-01` và 855 câu
published trong kho dev.

---

## 0. Cột `difficulty` không mang thông tin, và đừng để mô hình điền nó

Cả **855/855** câu published đều `difficulty = 3`. Thang là 1–5, mặc định 3, và
**không dòng mã nào đọc nó** — chỉ dictation dùng độ khó thật.

Con số ấy không phải phán đoán của ai. Chữ `difficulty` xuất hiện **0 lần** trong
toàn bộ `app/content/exam/`; định dạng dán không mang nó; nó rơi vào
`Field(default=3, ge=1, le=5)` ở `app/schemas/admin.py` vì không ai điền.

**Không vá bằng cách bảo mô hình tự chấm câu nó vừa viết.** Đó là chấm bài của
chính mình: con số trông như đo được nhưng không đo gì. ETS pre-test câu hỏi trên
người thi thật trước khi dùng chúng để tính điểm — với TOEIC, độ khó là thứ *đo*,
không phải thứ *khai*. Một cột `difficulty` do LLM điền tệ hơn cột hằng số, vì nó
tạo ra niềm tin sai.

Đường đúng cho cột ấy là `attempt_item`: tỉ lệ đúng thật của từng câu. Ngày
2026-09-07 kho mới có 1 839 lượt trả lời trên 532 câu, **trung vị 5 lượt/câu** —
quá mỏng để dùng (p-value cần ~30, IRT cần ~200, xem `SPEC-PLACEMENT` §2). Nhưng
nó tích luỹ, và nó là thứ **duy nhất kiểm được** những thay đổi ở §2.

## 1. Cơ chế: mix quyết định *dạng câu*, mô hình quyết định *độ khó trong dạng*

`blueprint.py` mở đầu bằng đúng lập luận này, ở một tầng trên:

> Bảo nó "sinh 30 câu Part 5" thì phần lớn sẽ rơi vào cùng vài điểm ngữ pháp dễ
> nhất, vì đó là vùng xác suất cao nhất — và không có gì trong đầu ra nói cho ta
> biết điều đó đã xảy ra.

Cơ chế ấy lặp lại **một tầng sâu hơn**. Mix giao mã nhãn; nhưng trong một mã, mô
hình tự do vẫn rơi vào thể hiện dễ nhất của dạng đó — vẫn là vùng xác suất cao
nhất, và vẫn không có gì báo. Nên mỗi trục độ khó phải được **ghi thành dữ liệu**
trong `mixes.py`, và phải có một cổng ở `check.py` cưỡng chế nó. Không có cổng
thì mix chỉ là gợi ý: một ô viết sai dạng vẫn là một câu hỏi hợp lệ.

## 2. Bốn thay đổi (2026-09-07)

### 2.1 Part 2 — đáp án đúng trực tiếp hay gián tiếp

`PART2_MIX` mang thêm cột thứ ba: số câu mà **đáp án đúng trả lời gián tiếp**.
8/25 câu, đúng tỉ lệ đề thật.

Đây là trục độ khó lớn nhất của Part 2 và trước đó không có ô nào cho nó. Một câu
WHERE có đáp đúng "It's on Rachel's desk" thì người nghe chỉ cần bắt được từ để
hỏi; cũng câu ấy mà đáp đúng là "I just got back from lunch" thì phải hiểu cả câu
rồi suy ra rằng người kia đang nói mình không biết.

Prompt cũ chỉ nói về **đáp án nhiễu** ("Do NOT make a wrong response absurd") và
chưa từng nói gì về đáp án đúng, nên cả 25 câu đều đáp thẳng. Nay
`part2_system.md` mô tả bốn kiểu đáp gián tiếp, và `part2.py` nói ô này thuộc
loại nào — ở prompt của **từng ô**, vì system prompt tả cả hai loại còn ô thì
phải là một.

Câu đuôi và câu lựa chọn để 0: chúng đã khó sẵn ở chỗ khác, và đáp gián tiếp cho
một câu lựa chọn thường ra câu nghe không tự nhiên.

### 2.2 Part 3 — mã `PART_3_IMPLICATION` chưa từng tồn tại

`PART_4_IMPLICATION` và `PART_7_IMPLICATION` đều có mã; **Part 3 thì không** —
không trong `labels.py`, không trong `toeic_question_label_taxonomy.md`. Mà đề
thật Part 3 luôn có câu "What does the woman mean when she says…?". Kho có 0 câu
dạng đó, và cả part chỉ còn chủ đề, chi tiết và hành động tiếp theo.

Mã đã được thêm (taxonomy trước, `labels.py` sinh theo), và `PART3_MIX` xếp 3 câu
— thay vào chỗ câu chi tiết, dạng đang thừa nhất (10/39). Part 4 nâng từ 1 lên 3.

Một cụm ba câu không mang hai câu hàm ý: đề thật không làm thế, và hai lời trích
trong một hội thoại ngắn thì lời sau không còn hàm ý gì.

### 2.3 Part 3/4 — prompt chưa bao giờ tả câu hàm ý là gì

`PART_4_IMPLICATION` đã nằm trong mix từ trước, nhưng `part4_system.md` **không
nhắc tới nó một chữ nào**. Prompt theo ô chỉ in nhãn tiếng Việt năm chữ —
"Câu hỏi về hàm ý câu nói" — rồi để mô hình đoán. Đó là lý do kho chỉ có 7 câu
loại này và không có gì bảo đảm chúng đúng dạng.

Cả hai system prompt nay có một mục tả hình dạng cố định của nó: lời trích ngắn
4–9 chữ có **thật trong lời thoại**, đáp án là nghĩa **hàm ý** chứ không phải
diễn lại lời trích, và ba đáp án sai là các cách đọc theo nghĩa đen.

### 2.4 Part 7 — nửa số câu là hai dạng dễ nhất

| | Trước | Sau |
|---|---|---|
| Tìm thông tin | 17 | 13 |
| Chủ đề, mục đích | 10 | 7 |
| **Hai dạng trên cộng lại** | **27/54 (50%)** | **20/54 (37%)** |
| Suy luận | 14 | 18 |
| Thông tin sai (NOT/EXCEPT) | 5 | 6 |
| Từ vựng trong ngữ cảnh | 4 | 6 |
| Điền câu | 2 | 2 |
| Hàm ý | 2 | 2 |

Điền câu và hàm ý **giữ nguyên**: đề thật có đúng hai câu mỗi loại, và hàm ý chỉ
sống trong cụm tin nhắn — mà đề có đúng hai cụm như thế.

## 3. Cổng ở `check.py`

`check_implication` chạy cho mọi ô mà blueprint giao mã `*_IMPLICATION`, và nó là
`problems` chứ không phải `flags` — ô bị xoá và sinh lại, thay vì đi tiếp vào đề.
Hai thứ nó bắt, cả hai đều tất định:

- **Không trích lời nào.** Bỏ lời trích đi thì còn lại một câu hỏi chi tiết hoàn
  toàn hợp lệ, phủ đủ mọi phép kiểm khác, và không có gì nói ô này đã viết sai
  thứ được giao.
- **Trích một câu không có trong lời thoại.** Tệ hơn: người nghe không bao giờ
  nghe thấy nó, nên câu hỏi không trả lời được.

Cả hai vế được `_normalise` trước khi so — so một vế thô với một vế đã chuẩn hoá
thì mọi lời trích có dấu phẩy hay dấu nháy đều bị báo là bịa.

Phân bố ở §2 được ghim bằng test trong `tests/test_exam_generation.py`: mix trôi
bằng một dòng sửa mà không ai thấy.

## 4. Bộ chọn đề placement — sửa riêng, và có tác dụng ngay

Mix và prompt ở §2 chỉ ảnh hưởng đề **sinh mới**; 855 câu trong kho không đổi.
Với đề đã có, chỗ hỏng nằm ở **bộ chọn** chứ không ở nội dung.

`make_placement.py` lấy các cụm ĐẦU của mỗi part, mà đề TOEIC xếp từ dễ đến khó
trong từng part. Đo trên `tp-test-09`:

| Part | Part trải từ câu | Câu dạng khó nằm ở | Bộ chọn lấy |
|---|---|---|---|
| 3 | 32–70 | **64–70** | 32–43 |
| 4 | 71–100 | **85–99** | 71–82 |

Không giao nhau chút nào. Kết quả: `tp-placement-01` có **0** câu biểu đồ (kho
có 15), **0** câu hàm ý Part 4 (kho có 7), **0** câu điền câu Part 7 (kho có 6),
**0** câu từ vựng trong ngữ cảnh (kho có 22), và Part 5 chỉ 2/20 câu từ vựng
trong khi chính đề nguồn có tỉ lệ 7/30. Kho đã có sẵn câu khó; đề chỉ không lấy.

### 4.1 Chọn theo dạng câu, không theo vị trí

Vị trí **không** phải thứ để sửa theo. Đề nguồn do chính pipeline này sinh ra, và
blueprint xáo Part 2 và Part 5 theo seed — ở đó vị trí không mang tín hiệu độ khó
nào. Thứ mang tín hiệu là dạng câu, và nó có nhãn.

- `PLACEMENT_MIX` — định mức từng dạng cho Part 2 và Part 5 (chọn được từng câu).
  Part 5 nay là 8 ngữ pháp / 6 từ loại / **6 từ vựng**.
- `PRIORITY` — dạng khó mà đề PHẢI có ít nhất một câu. Đúng những dạng bộ chọn cũ
  lấy trọn 0.
- `EASY` — hai dạng dễ nhất của mỗi part nghe/đọc dài; cụm đặc chúng lấy sau cùng.
  Đây là thứ thay cho "lấy cụm đầu tiên".

Với part chọn theo cụm, hai chặng và **thứ tự giữa chúng là toàn bộ điểm**: mỗi
mã `PRIORITY` lấy một cụm chứa nó (cụm nhỏ nhất, để còn chỗ), rồi phần còn lại
xếp theo tỉ lệ câu dễ tăng dần. Đảo lại thì chặng hai ăn hết định mức và cụm có
biểu đồ không bao giờ tới lượt — đúng cái đã xảy ra, chỉ khác lý do.

### 4.2 Lấp cho ĐÚNG định mức, không "gần đủ"

Cụm Part 7 dài 2 tới 5 câu, nên "lấy tiếp nếu còn vừa" dừng ở 13/14 rồi tắc:
không có cụm một câu nào để bù. `_fill_exactly` là quy hoạch động trên số câu —
mười lăm cụm và `need ≤ 14` nên nó tức thời. Phép kiểm 84 câu vẫn đứng nguyên;
thứ được sửa là phép chọn, không phải phép kiểm.

### 4.3 Đủ 12 mã ngữ pháp, bằng luật chứ không bằng may

§0.4 của spec placement chọn 20 câu Part 5 chính vì "mỗi nhãn `grammar` hiện diện
ít nhất một câu". Định mức mới xếp theo `question_type`, nên một mã ngữ pháp hiếm
có thể rơi ra ngoài — và điều đó không vô hại: planner đọc kỹ năng yếu theo mã
`GRAMMAR_*`, nên một mã vắng mặt nghĩa là người yếu điểm ấy không bao giờ bị phát
hiện.

Hai lần vá, cả hai đều **đổi chỗ chứ không thêm câu**, nên định mức không đổi:
trong Part 5 đổi câu cùng `question_type`; ở Part 6 (lấy 2 trong 4 cụm) đổi cả
cụm cùng kích thước. Bộ chọn cũ phủ đủ 12 mã, nhưng do may — nó lấy hai cụm đầu.

### 4.4 Kết quả đo được

`--preview` in phân bố mà không ghi gì. Trên kho ngày 2026-09-07:

| | Cũ | Mới |
|---|---|---|
| Câu biểu đồ (P3+P4) | 0 | 2 |
| Câu hàm ý (P4) | 0 | 1 |
| Điền câu (P7) | 0 | 1 |
| Từ vựng trong ngữ cảnh (P7) | 0 | 1 |
| Từ vựng Part 5 | 2/20 | 6/20 |
| Hai dạng dễ nhất của P7 | 9/14 (64%) | 6/14 (43%) |
| Mã ngữ pháp phủ được | 12 (do may) | 12 (do luật) |

`PART_3_IMPLICATION` vẫn thiếu và `describe()` nói ra điều đó: mã ấy mới thêm ở
§2.2, đề nguồn cũ không có câu nào. Nó sẽ có ở đề sinh sau.

## 5. Đổi đề placement thì đổi thế nào

`build()` từ chối dựng lại một đề đã published — đổi đề dưới chân người học. Nên
đề mới là **slug mới** (`--slug`), và `--publish` chuyển đề cũ sang `archived`,
không xoá: lượt làm cũ vẫn trỏ vào nó và màn xem lại vẫn phải đọc được.

Lưu trữ đề cũ là bắt buộc chứ không phải dọn dẹp. `_placement_test()` chọn bằng
`db.scalar` trên `(is_placement, published)`; hai đề cùng thoả thì nó lấy một cái
tuỳ ý, và hai người học làm hai đề khác nhau mà kết quả vẫn được đem so với nhau.

Kết quả cũ không bị ảnh hưởng: `placement_result` là snapshot gắn lượt làm
(SPEC-PLACEMENT §4), nên người đã đo trình độ giữ nguyên phán quyết của đề cũ.


## 6. Trùng khung giữa các đề (đo 2026-09-07)

Kiểm năm blueprint đã sinh. Kết luận có hai nửa ngược nhau.

**Nội dung KHÔNG trùng.** Trên bốn đề thật (06, 07, 08, test-09): 120/120 câu
Part 5 khác nhau, 16/16 bài Part 6, 60/60 bài Part 7. Độ trùng từ vựng giữa các
cụm khác đề đo bằng Jaccard: trung vị **0,03–0,07**, cao nhất **0,26**, **không
cặp nào** vượt 0,35.

Hai phép đo đầu tôi làm hỏng, ghi lại để không lặp: lọc `slug LIKE 'tp-%'` bắt cả
hai đề placement, mà chúng **dùng lại chính câu của `tp-test-09`** — "40 câu Part
5 trùng" là ảo. Và "Part 6 trùng 95%" cũng ảo: `prompt_text` của Part 6 chỉ là
nhãn `Blank (1)…(4)`.

Đề bài lặp nhiều nhất ở Part 3/4/7 — *"Why is the woman calling?"*, *"Who is the
speaker?"* — là thứ **đúng ra phải lặp**; đề thật cũng dùng chúng ở mọi form.

**Khung thì trùng gần như hoàn toàn.** `--seed` từng có mặc định ghi cứng
`20260822`, và cả năm đề đều mang số đó. Đo trên mã lúc ấy:

| | Ô giống hệt |
|---|---|
| Cùng seed mặc định | **99/99 (100%)** |
| Đổi seed | 18/99 (18%) |

Tức hai đề sinh bằng lệnh mặc định có **cùng một hình dạng đề**: câu 32 luôn hỏi
chủ đề, câu 34 luôn hỏi hành động tiếp theo. Và 18% còn lại trùng dù đổi seed, vì
`PART3_MIX`/`PART4_MIX`/`PART7_SETS` là tuple cố định **duyệt theo thứ tự** — seed
chỉ xáo Part 1 và Part 2.

Thứ đang cứu tình hình là bước `plan` cho model viết lại lời tả cảnh; đó là lý do
form-07 trở đi có cảnh riêng, và cũng là lý do `tp-form-06` lạc loài — nó giữ
nguyên chuỗi thô của mix (*"lịch họp và lịch công tác"*). Nghĩa là **biến thiên
phụ thuộc hoàn toàn vào một lượt gọi model**, không vào blueprint.

### Đã sửa

**Seed suy từ slug**, không còn mặc định ghi cứng. Hai đề khác tên tự khắc khác
khung; dựng lại cùng slug vẫn ra đúng đề cũ. Dùng `sha256`, **không** dùng
`hash()` của Python — nó ngẫu nhiên hoá theo tiến trình, nên dựng lại ở lần chạy
sau sẽ ra đề khác, đúng thứ tính tái lập tồn tại để ngăn.

**Xáo `PART3_MIX`, `PART4_MIX`, `PART7_SETS` theo seed**, nhưng xáo **trong từng
nhóm**, vì hai bất biến của đề thật hỏng im lặng nếu xáo cả bảng:

- **Câu hỏi hình nằm ở cuối part.** `build_part3` gán brief cho ô 10–12 và
  `build_part4` cho ô 8–9 theo VỊ TRÍ, nên một hàng vốn có hình trôi lên đầu sẽ
  đẻ ra câu hỏi hình giữa Part 3 — hợp lệ từng câu, sai với mọi đề thật.
- **Part 7 xếp cụm một đoạn trước, rồi hai, rồi ba.** `number` cộng dồn theo số
  câu của ô trước, nên trộn cụm 5 câu vào giữa đám cụm 2 câu vẫn đánh số liền
  mạch tới 200 — không có gì báo.

Kích thước nhóm của Part 7 đọc từ chính bảng (`groupby` trên số đoạn), không viết
cứng: thêm một cụm mà quên sửa con số là đúng loại sai lệch không ai thấy.

### Đo lại sau khi sửa

| | Ô giống hệt |
|---|---|
| Hai slug khác nhau | **10/103 (10%)** |
| Dựng lại cùng slug | 103/103 — tái lập nguyên vẹn |

Bốn bài test ghim lại: hai đề khác slug phải khác khung, cùng slug phải dựng lại
được, ô có hình vẫn ở 10–12 và 8–9 với mọi seed, và Part 7 vẫn một-hai-ba đoạn,
kết thúc đúng câu 200.


## 7. Đáp án nhiễu phải nhại lời thoại (2026-09-07)

### Tra đề thật trước, vì suy đoán ở đây sai theo cả hai hướng

Nhận xét ban đầu: "đáp án trích nguyên văn nên dễ chọn". Đo đúng. Nhưng cách sửa
hiển nhiên — cấm đáp án đúng dùng lại chữ của lời thoại — **sai**, vì đề thật CÓ
những câu trả lời được bằng cách khớp cụm từ, và bỏ chúng đi làm đề khó hơn đề
thật.

Hai nguồn luyện thi độc lập mô tả cùng một cơ chế, và nó là điều quyết định:

> *"Keyword trap: an answer repeats a word from the talk but changes the
> meaning."* — mytoeiccoach, Part 4
>
> *"Incorrect answers often containing words/phrases heard in the
> conversation."* — prepedu, Part 3

Tức trong đề thật, **đáp án SAI mới là chỗ nhại lời thoại**. Người nghe được một
từ quen rồi chọn đại phải sai phần lớn số lần.

### Đề tự sinh làm ngược

Đo trên 276 câu Part 3/4 của bốn đề đầu — độ phủ là tỉ lệ từ nội dung của một
lựa chọn có sẵn trong lời thoại:

| Độ phủ | Đáp án ĐÚNG | Đáp án NHIỄU |
|---|---|---|
| 0–20% (không nhắc tới) | 11% | **37%** |
| 80–100% (nhại gần hết) | **58%** | 17% |

Hệ quả đo được: chọn lựa chọn "nghe quen nhất" đúng **46%** ở Part 3 và **49%**
ở Part 4, so với 25% nếu chọn bừa. Part 7 thì sạch — 21%, dưới cả may rủi.

Và **35% số câu có từ hai đáp án nhiễu "không nhắc tới"**, 17% có cả ba. Ở nhóm
17% ấy, đáp án đúng là lựa chọn DUY NHẤT chứa từ nào của lời thoại.

Nguyên nhân nằm trong prompt: cả sáu prompt đều tả kỹ đáp án *sai* phải sai thế
nào, và **không prompt nào nói gì về đáp án đúng**. Danh sách bốn kiểu nhiễu của
Part 3/4 xếp "something never mentioned" ngang hàng ba kiểu kia, nên model dùng
nó nhiều nhất — nó dễ viết nhất. Cùng hình dạng lỗ hổng với Part 2 ở §2.1.

### Đã sửa

**Prompt Part 3/4**: ít nhất HAI trong ba đáp án nhiễu phải dùng lại chữ người
nói đã nói rồi bẻ nghĩa, theo bốn khuôn (kế hoạch đã đổi, sai người nói, ý đã bị
bác, đúng chữ sai quan hệ). Nhiều nhất MỘT được là chuyện không nhắc tới. Và nói
thẳng rằng **đáp án đúng KHÔNG buộc phải tránh chữ của lời thoại** — thứ phải
tránh là để độ phủ *đoán được* đáp án.

**Cổng `check_distractors`** ở `check.py`, tất định: quá một đáp án nhiễu "không
nhắc tới" thì chặn. Chạy trên kho hiện tại nó bắt **97/276 câu (35%)**, khớp
đúng con số đo bằng script rời.

**Câu hỏi về HÌNH được miễn**, và không phải vì tiện: lựa chọn của nó là tên hàng
trong bảng, còn lời thoại **cố ý không đọc tên ấy** — đó là toàn bộ cơ chế của
dạng câu này. Bắt nó nhại lời thoại là bắt nó thôi làm câu hỏi về hình. Chỗ này
lộ ra vì hai bài test cũ đỏ, không phải vì tôi nghĩ ra trước.

Bốn fixture test phải viết lại: chúng dùng nhiễu "không nhắc tới" cho cả ba lựa
chọn, tức chuẩn cũ. Đó là dấu hiệu cổng chạy đúng, không phải hồi quy.

## 8. Ảnh Part 1 và dải chủ đề

**Ảnh quá đơn giản.** Ràng buộc nơi chốn đã có sẵn trong `plan_part1_scenes.md`
và các đề mới đang tuân thủ (đề 09: 0 văn phòng / 3 ngoài trời; đề 10: 0/5; đề
07–08 sinh trước khi siết nên 4/0 và 2/0). Vấn đề còn lại nằm ở một câu trong
`part1_system.md`: *"describe the photograph that makes exactly one of them
true… must fix every detail the four statements depend on."* Câu ấy đòi bức ảnh
**tối thiểu**, và ảnh tối thiểu là một người làm một việc — mọi đáp án sai đều bị
bác bởi đúng một sự thật.

Nay prompt đòi trong ảnh **nhiều hơn** bốn câu cần: ảnh có người phải có ít nhất
hai nhóm chủ thể làm hai việc khác nhau; ảnh không người phải có ít nhất ba nhóm
vật ở ba quan hệ vị trí. Và nói rõ vì sao: phần thừa ấy để một câu sai *có thể*
đã được viết về nó, nên người nghe phải soi ảnh thay vì dừng ở thứ đầu tiên nhìn
thấy.

**Chủ đề lặp.** `BUSINESS_CONTEXTS` chỉ có **mười** mục và toàn đời sống văn
phòng; nó là hạt giống cho mọi bối cảnh model viết. Đếm từ khoá trên bốn đề:
"hàng" 146 lần, "quản/giám" 90, "lịch" 42, "email" 31. Nay **30 mục**, thêm đi
lại, ăn uống, y tế, nhà cửa, ngân hàng, thư viện, bảo tàng, thời tiết, công
trình, nông sản — vẫn là đời sống công việc và nơi công cộng, không phải chuyện
riêng tư.


## 9. Sinh thử và đo lại (2026-09-08)

Dựng `tp-form-11` bằng `bai/glm-5.3-flash` (blueprint) rồi viết 5 cụm Part 3
bằng cả hai model để tách biến.

### Khung và ảnh: đạt

Khung trùng **16–17%** với từng đề cũ, so với **100%** giữa hai đề cũ bất kỳ.
Seed suy từ slug và phép xáo theo nhóm chạy đúng; `validate` sạch, 103 ô.

Ảnh Part 1 đổi hẳn: **6/6 ô có từ hai việc diễn ra** (mọi đề cũ: 0/6), mô tả dài
36 từ thay vì 12–18. Và nó có tác dụng đúng chỗ mong đợi — đáp án sai giờ gọi tên
vật **có thật trong ảnh**: giàn giáo có nhưng không ai leo, cát và máy trộn đều có
nhưng người thợ đang đổ từ xô, túi xi măng có nhưng xếp sẵn trên pallet.

### Luật một phía làm mọi thứ TỆ HƠN

Bản đầu của luật hai chỉ chặn một cực: *"nhiều nhất một câu có đáp án đúng giống
lời thoại nhất"*. Model làm đúng lời rồi lật hẳn sang cực kia.

| Chiến thuật đoán bừa | May rủi | Kho cũ (276 câu) | Luật một phía |
|---|---|---|---|
| Chọn cái **giống** lời thoại nhất | 25% | **47%** | 0% |
| Chọn cái **ít giống** nhất | 25% | 3% | **67%** |

Thiên lệch 47% bị thay bằng thiên lệch 67% ngược chiều — **tệ hơn chỗ xuất phát**.
Một cổng chặn một phía không làm tín hiệu biến mất, nó chỉ đổi dấu. Đó là lý do
`check_paraphrase_balance` chặn **cả hai cực**, và lý do ấy nằm ngay trong
docstring của nó.

### Luật đối xứng: đạt, và LUẬT làm việc chứ không phải model

| | n | giống nhất | ít giống nhất | phủ đúng | phủ nhiễu | qua cổng nhiễu |
|---|---|---|---|---|---|---|
| may rủi | | 25% | 25% | | | |
| kho cũ | 276 | **47%** | 3% | 0,72 | 0,38 | 65% |
| glm-5.3-flash | 12 | 33% | 33% | 0,42 | 0,46 | **100%** |
| qwen3.8-flash | 15 | **7%** | 20% | 0,62 | 0,77 | **100%** |

Cả hai model đều diệt được thiên lệch 47% và đều qua cổng nhiễu 100%. Nên con số
0%/67% ở lượt trước là của **luật**, không phải của model — điều chỉ biết được sau
khi chạy lại cùng luật trên cả hai.

**qwen3.8-flash hợp hơn.** glm cân đối (33%/33%) nhưng phủ thấp cả hai bên
(0,42 / 0,46): nó diễn đạt lại *mọi thứ*, tức trôi về phía **khó hơn đề thật** —
đúng cái phải tránh. qwen giữ phủ cao ở cả hai (0,62 / 0,77) mà vẫn không đoán
được, tức đáp án nhiễu thật sự nhại lời thoại đúng kiểu bẫy keyword. glm còn hỏng
1/5 ô (`bị cắt giữa phần suy luận`) và chậm hơn.

Với n = 12 và 15, chênh lệch 33% so với 25% nằm trong sai số; khoảng cách 0,42 với
0,62 ở độ phủ thì không.

### Hai bài học về cách ĐO, không về mã

**Đừng xoá hiện vật trước khi kiểm tên model.** Gõ `bai/qwen-3.8-flash` (tên đúng
không có gạch) trả 404 năm lần, và năm cụm glm đã sinh thì đã bị xoá — mất luôn
khả năng so hai model trên cùng luật ở lượt ấy.

**Đừng đổi hai biến cùng lúc.** Lượt đầu đổi cả luật lẫn model, nên 0%/67% không
quy được cho cái nào. Phải chạy thêm một lượt mới tách ra.
