# Ảnh Part 1 và ngữ liệu hình Part 7 — đối chiếu với đề thật

**Trạng thái:** 🟡 **TẠM THỜI** · viết 2026-09-03
**Mục đích:** ghi lại kết quả đối chiếu nội dung đã sinh với format TOEIC thật, và
hai việc phải làm — chúng có bản chất khác nhau nên không được gộp

---

## 1. Hai vấn đề, hai bản chất

| | Part 1 | Part 7 |
|---|---|---|
| Triệu chứng | ảnh đơn điệu, gần như chỉ có văn phòng và người | 12 ngữ liệu hình đều là bảng/lịch/khảo sát/biểu mẫu |
| Bản chất | **ràng buộc quá hẹp** trong prompt | **bảng màu của bộ vẽ hình hẹp** — cấu trúc và đa dạng tài liệu đều đã đúng |
| Cách sửa | nới ràng buộc, sửa prompt | thêm `kind` vào `graphics.py` |

---

## 2. Part 1 — ràng buộc quá hẹp

### 2.1 Quan sát

Trong 25 ảnh Part 1 đã sinh: **0 câu mang nhãn `PART_1_OBJECT_OR_SCENE_DESCRIPTION`**
(12 câu có nhãn — 10 `PERSON_DESCRIPTION`, 2 `PERSON_AND_OBJECT_DESCRIPTION`).

Đọc 24 câu đáp án đúng thì gần như câu nào cũng là *người đang làm gì*, và bối
cảnh lặp lại: máy photocopy, máy tính, máy in, bàn làm việc, nhà kho, sảnh, lễ
tân, phòng họp.

### 2.2 Đề thật

Khoảng **2/3 ảnh có người, 1/3 là vật hoặc cảnh không người**. Ba thứ Part 1 hay
hỏi là **hoạt động**, **tình huống chung**, và **quan hệ vị trí** (*next to, near,
across from*). Bối cảnh không giới hạn ở công sở: đường phố, công trường, bến
cảng, cửa hàng, nhà hàng, phương tiện giao thông, ngoài trời.

### 2.3 Ba chỗ hard-code gây ra nó

1. `plan_part1_scenes.md` — *"thuộc môi trường **công sở/dịch vụ**"*: planner
   **bắt buộc** bối cảnh văn phòng.
2. Cùng tệp — *"phần lớn là one hoặc several, **nhiều nhất một dòng none**"*: tối
   đa 1/6 ảnh không có người, tức **17%**, đúng một nửa tỉ lệ thật.
3. `photos.py` → `STYLE` kết thúc bằng **`"ordinary workplace setting."`**, và
   chuỗi này dán vào **mọi** ảnh Part 1 bất kể planner viết gì.

Chỗ thứ ba là chỗ quyết định: sửa hai chỗ trên mà để nguyên nó thì mô hình vẽ
vẫn kéo mọi cảnh về văn phòng, và cái sai đó chỉ lộ ra khi có người nhìn ảnh.

### 2.4 Còn một trục nữa bị thiếu

`part1_system.md` liệt kê bốn loại bẫy: sai hành động, sai vật, vật không có
trong ảnh, sai số ít/số nhiều. **Không có "sai vị trí".** Nên kể cả khi đã có ảnh
tả vật, mô hình cũng không được dạy dựng bẫy theo trục vị trí — trong khi đó lại
là một trong ba thứ Part 1 hay hỏi nhất.

### 2.5 Điều kiện thuận lợi

Ảnh Part 1 là **ảnh sinh ra**, không phải ảnh tìm được từ kho công cộng. Nên nới
bối cảnh chỉ là sửa prompt, không phụ thuộc kho ảnh có sẵn gì.

---

## 3. Part 7 — chỉ bảng màu của bộ vẽ là hẹp

> **Sửa hai lần, 2026-09-03.** Bản đầu viết "0 bộ ba đoạn" và "đặt sai bài toán";
> bản thứ hai vẫn giữ "0 chuỗi tin nhắn" và "4/7 dạng bài". **Cả bốn đều sai**,
> và cùng một nguyên nhân: đo bằng thứ THAY THẾ cho nội dung thay vì đo nội dung.
>
> - "0 bộ ba" — đếm `passage_2`/`passage_3` (cột chữ) mà bỏ `passage_*_image_id`,
>   nên bộ có slot là hình bị tụt xuống thành đơn/đôi.
> - "0 chuỗi tin nhắn" — regex giả định ngoặc tròn `(9:15 A.M.)`, bộ sinh dùng
>   ngoặc vuông `[9:15 A.M.]`.
> - "4/7 dạng bài" — đếm nhãn `passage_type`, mà chỉ 16/47 bộ có nhãn. Đó là số
>   đo **độ phủ nhãn**, không phải độ đa dạng nội dung.
>
> Giữ lại nguyên văn thay vì xoá: ba cái bẫy này đều còn nguyên trong dữ liệu.

### 3.1 Cấu trúc ĐÚNG

| | tp-form-06 / 07 / 08 (mỗi đề) | đề thật |
|---|---|---|
| đoạn đơn | 10 | 10 |
| đoạn đôi | 2 | 2 |
| đoạn ba | 3 | 3 |
| số câu | 54 | 54 |

### 3.2 Đa dạng tài liệu cũng ỔN — đo bằng nội dung

Trên 47 bộ Part 7: **24** có tiêu đề thư/email (`From:`), **7** mang dấu hiệu hoá
đơn/biên lai/xác nhận đơn, **6** là **chuỗi tin nhắn nhiều người**
(`Tên [9:15 A.M.]`), **3** có lịch trình/chuyến bay, **3** có địa chỉ web, **12**
có ngữ liệu hình.

### 3.3 Cái thật sự hẹp: bảng màu của bộ vẽ

Cả 12 bộ có hình đều do `graphics.py` sinh, và nó đang dùng **hết** sáu `kind`
của mình: lịch ×4, khảo sát ×3, biểu mẫu ×2, bảng ×3, biểu đồ ×1, sơ đồ ×2.

Nên giới hạn nằm ở **bảng màu của module**, không phải ở cách dùng — muốn đa dạng
hơn thì phải **thêm `kind`**, chứ dùng khéo hơn không giúp gì. Đề thật còn có
những tài liệu hình mà sáu dạng này không vẽ ra được: phiếu giảm giá, biên lai có
bố cục, ảnh chụp trang web, bản đồ có tuyến đường.

Module KHÔNG bị dùng nhầm chỗ: `assign_passage_image` cố ý nhận cả part 7, và hai
`kind` `survey`/`form` **được miễn** luật "trục đáp án đúng 4 mục" — tức nó đã có
sẵn dạng dành cho phần đọc.

### 3.4 Một lỗ có thật, nhưng là lỗ NHÃN

Chỉ **16/47** bộ Part 7 có nhãn `passage_type` — `enrich_skills` chưa quét hết.
Điều đó không làm nội dung nghèo đi, nhưng nó làm mọi kết luận rút từ nhãn trở
nên vô giá trị, và §3 này đã trả giá đúng một lần vì thế.

### 3.5 Còn lại

**3/9 bộ ba dùng hai hình** (chữ + hình + hình). Bộ ba thật thường là ba *tài
liệu*, nhiều nhất một trong đó là bảng biểu. Đây là điểm duy nhất trong mục này
đo trực tiếp từ cột slot và đứng vững qua cả hai lần sửa.

Part 3/4 dùng `graphics.py` đúng chỗ của nó: 15 câu "Look at the graphic" trên 5
đề.

---

## 4. Việc phải làm

**4.1 Part 1** (làm trước, rẻ và độc lập):

- gỡ `"ordinary workplace setting."` khỏi `STYLE` — nếu không thì hai việc dưới vô hiệu;
- nới bối cảnh trong `plan_part1_scenes.md` ra ngoài công sở;
- nâng tỉ lệ ảnh không người lên khoảng 1/3;
- thêm **"sai vị trí"** vào bảng bẫy của `part1_system.md`.

**4.2 Part 7** — đã làm 2026-09-03:

- [x] **Ngân sách chữ theo số câu hỏi.** `part7_system.md` ghi "90-200 words
      each", và đứng trước một khoảng thì mô hình viết số nhỏ nhất trong đó: đo
      được trung bình 110 từ một tài liệu, tức **53 → 42 → 36 từ mỗi câu hỏi**
      khi số đoạn tăng từ một lên ba. Đề thật đi ngược lại — thêm tài liệu thì
      thêm chữ, vì đáp án phải ghép từ nhiều tài liệu. Luật mới là **60 từ cho
      mỗi câu hỏi**, và `part7.py` **nhân sẵn** con số đó rồi in vào prompt thay
      vì để mô hình tự tính. Trần token không đổi: nội dung thật ~700 trên trần
      10 000, phần vượt vốn là suy luận chứ không phải chữ.
- [x] **Cụm ba đoạn dùng hai hình → ba tài liệu.** `p7-15` từng là thư + bảng
      giá + phiếu đặt vé, tức năm câu hỏi dựa vào đúng một tài liệu có chữ chạy.
      Giữ bảng giá (chỗ tra tự nhiên), trả ô còn lại về email xác nhận. Giờ mọi
      cụm nhiều đoạn có nhiều nhất một ô hình. `build_part7` tự đếm số ô hình từ
      `PART7_SETS` nên không hằng số nào phải sửa theo.
- [x] **Mâu thuẫn giữa dòng "Tình huống" và brief hình.** Dòng tình huống viết
      tay theo `PART7_SETS`, còn ô hình lấy từ `PART7_GRAPHIC_POOL` theo seed —
      hai chỗ có thể gọi tên hai tài liệu khác nhau trong cùng một prompt. Đầu
      ra hiện tại vẫn mạch lạc (mô hình tự hoà giải), nên đây là mâu thuẫn tiềm
      ẩn chứ chưa phải lỗi đã xảy ra; prompt giờ nói thẳng **brief hình thắng**.

Còn lại:

- [ ] thêm `kind` cho `graphics.py`. Mười mẫu trong `PART7_GRAPHIC_POOL` phủ đủ
      sáu `kind`, nhưng **cả sáu cùng một họ thị giác**: dữ liệu xếp hàng cột.
      Thiếu hẳn tài liệu có bố cục — phiếu giảm giá, biên lai có dòng và tổng
      tiền, ảnh chụp trang web, bản đồ có tuyến đường.
- [ ] chạy `enrich_skills` cho `passage_type` — 31/47 bộ chưa có nhãn.

---

## 5. Nguồn

- [ETS Global — Format and questions of the TOEIC Listening and Reading test](https://www.etsglobal.org/fr/en/help-center/test-content/format-questions-toeic-listening-reading)
- [ETS Global — What is changing in the June 2018 updated version](https://www.etsglobal.org/fr/en/help-center/most-frequently-asked-questions/updates-toeic-listening-and-reading)
- [990prep — TOEIC Part 1 Photographs](https://990prep.com/en/guides/listening-part-1-photographs)
- [990prep — TOEIC Test Format Breakdown](https://990prep.com/en/guides/toeic-test-format-breakdown)
- [esl-lounge — TOEIC Reading Part 7](https://www.esl-lounge.com/student/toeic-reading-part-seven.php)
- [ETS Examinee Handbook (PDF)](https://files.eric.ed.gov/fulltext/ED505579.pdf)
