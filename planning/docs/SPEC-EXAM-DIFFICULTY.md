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
