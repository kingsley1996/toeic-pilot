# Ảnh Part 1 và ngữ liệu hình Part 7 — đối chiếu với đề thật

**Trạng thái:** 🟡 **TẠM THỜI** · viết 2026-09-03
**Mục đích:** ghi lại kết quả đối chiếu nội dung đã sinh với format TOEIC thật, và
hai việc phải làm — chúng có bản chất khác nhau nên không được gộp

---

## 1. Hai vấn đề, hai bản chất

| | Part 1 | Part 7 |
|---|---|---|
| Triệu chứng | ảnh đơn điệu, gần như chỉ có văn phòng và người | hình nào cũng ra bảng/lịch/khảo sát/biểu mẫu |
| Bản chất | **ràng buộc quá hẹp** trong prompt | **đặt sai bài toán** — module được đặc tả cho phần NGHE |
| Cách sửa | nới ràng buộc, sửa prompt | bộ sinh **tài liệu** riêng, không phải thêm dạng vào `graphics.py` |

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

## 3. Part 7 — đặt sai bài toán

### 3.1 Module được đặc tả cho phần NGHE

`graphics.py` tự khai nó dựng theo **câu 64, 67, 70, 96, 99** của đề mẫu ETS.
Đánh số TOEIC: 32–70 là Part 3, 71–100 là Part 4. **Cả năm ví dụ đều là graphic
của phần nghe.** Khái niệm tổ chức của module nói thẳng điều đó:

> Điều thật sự phân biệt bốn dạng không phải cách vẽ, mà là **trục đáp án**: bốn
> lựa chọn của câu **"Look at the graphic"** lấy từ đâu.

### 3.2 Nhưng nó đang sinh ngữ liệu cho phần ĐỌC

**Cả 12 bộ có hình đều thuộc Part 7.** Một module đặc tả cho graphic phần nghe
đang sinh vật liệu phần đọc — và ràng buộc `len(answer_axis()) != 4` là yêu cầu
của câu nghe đang bị áp lên vật liệu đọc. Đó là lý do chúng đồng loạt ra bảng,
lịch, khảo sát, biểu mẫu.

Part 7 thật **không có câu "Look at the graphic"**. Ngữ liệu hình của nó là **văn
bản có định dạng** để đọc — hoá đơn, biên lai, lịch trình, phiếu giảm giá, trang
web, quảng cáo, thông báo, biểu mẫu — với câu hỏi đọc hiểu bình thường, không có
trục đáp án nào.

### 3.3 Hai lỗ nữa cùng chỗ

- **0 bộ ba đoạn.** Part 7 thật có 10 đơn, 2 đôi, **3 bộ ba**. Mình có 37 đơn, 10
  đôi, **0 ba**.
- **0 chuỗi tin nhắn / chat nhiều người.** Đây là dạng bản cập nhật TOEIC tháng
  6/2018 thêm vào Part 7, và mình chưa có khuôn nào cho nó.

### 3.4 Part 3/4 thì đang ĐÚNG

15 câu "Look at the graphic" trên 5 đề, dùng đúng module được đặc tả cho nó. Đừng
sửa `graphics.py` theo hướng Part 7 — nó đang phục vụ đúng chỗ của nó.

---

## 4. Việc phải làm

**4.1 Part 1** (làm trước, rẻ và độc lập):

- gỡ `"ordinary workplace setting."` khỏi `STYLE` — nếu không thì hai việc dưới vô hiệu;
- nới bối cảnh trong `plan_part1_scenes.md` ra ngoài công sở;
- nâng tỉ lệ ảnh không người lên khoảng 1/3;
- thêm **"sai vị trí"** vào bảng bẫy của `part1_system.md`.

**4.2 Part 7** (việc lớn hơn, làm sau):

- một bộ sinh **tài liệu** riêng, không có trục đáp án — hoá đơn, biên lai, lịch
  trình, phiếu giảm giá, trang web, quảng cáo;
- dạng **chuỗi tin nhắn nhiều người**;
- dựng **bộ ba đoạn**.

---

## 5. Nguồn

- [ETS Global — Format and questions of the TOEIC Listening and Reading test](https://www.etsglobal.org/fr/en/help-center/test-content/format-questions-toeic-listening-reading)
- [ETS Global — What is changing in the June 2018 updated version](https://www.etsglobal.org/fr/en/help-center/most-frequently-asked-questions/updates-toeic-listening-and-reading)
- [990prep — TOEIC Part 1 Photographs](https://990prep.com/en/guides/listening-part-1-photographs)
- [990prep — TOEIC Test Format Breakdown](https://990prep.com/en/guides/toeic-test-format-breakdown)
- [esl-lounge — TOEIC Reading Part 7](https://www.esl-lounge.com/student/toeic-reading-part-seven.php)
- [ETS Examinee Handbook (PDF)](https://files.eric.ed.gov/fulltext/ED505579.pdf)
