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

## 4. Việc này KHÔNG sửa được gì cho đề đang có

Mix và prompt chỉ ảnh hưởng đề **sinh mới**. 855 câu trong kho không đổi.

Với đề đã có, chỗ hỏng nằm ở **bộ chọn** chứ không ở nội dung: `make_placement.py`
lấy các cụm ĐẦU của mỗi part, mà đề TOEIC xếp từ dễ đến khó trong từng part. Đo
trên `tp-test-09`: câu biểu đồ Part 3 nằm ở 64–70 còn bộ chọn lấy 32–43; Part 4
là 85–99 và bộ chọn lấy 71–82. **Không giao nhau chút nào.** Kết quả:
`tp-placement-01` có 0 câu biểu đồ (kho có 15), 0 câu hàm ý Part 4 (kho có 7), 0
câu điền câu Part 7 (kho có 6). Kho đã có sẵn câu khó; đề chỉ không lấy chúng.

Đó là một việc riêng, rẻ hơn, và có tác dụng ngay trên kho hiện tại.
