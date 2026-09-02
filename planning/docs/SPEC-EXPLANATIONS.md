# Giải thích đáp án — đặc tả tạm thời

**Trạng thái:** 🟡 **TẠM THỜI** · viết 2026-09-02
**Mục đích:** chốt *hình dạng* của một lời giải thích trước khi viết sáu prompt, không phải để chốt trên giấy

> Tài liệu này tồn tại để **bị sửa sau đợt thí điểm** (§9). Bằng chứng ở §2 cho
> thấy một lời dặn nghe rất hợp lý vẫn đẻ ra câu vòng tròn, nên mọi luật dưới đây
> là giả thuyết cho tới khi nhìn kết quả sinh thật.

---

## 1. Vì sao có tài liệu này

Trong bảy tệp prompt sinh đề, **chỉ `part5_system.md` yêu cầu mô hình viết dòng
`Explanation:`** — sáu tệp còn lại không nhắc chữ đó lấy một lần. Khối đầu ra
được `writer.py` tách theo mốc `[QUESTION]` chung cho mọi part, nên đường ống vốn
đã tải được dòng giải thích; chỉ là sáu prompt kia chưa bao giờ đòi.

Nên đây không phải một quyết định đã cân nhắc rồi bỏ qua. Đây là một chỗ sót, và
độ phủ hiện tại là hệ quả trực tiếp:

| Part | Câu | Có giải thích | |
|---|---|---|---|
| 1 | 25 | 6 | 24% |
| 2 | 100 | 25 | 25% |
| 3 | 118 | 1 | 1% |
| 4 | 94 | 1 | 1% |
| 5 | 95 | 91 | **96%** |
| 6 | 52 | 0 | 0% |
| 7 | 167 | 0 | 0% |
| | **655** | **124** | 19% |

Nó cũng đang **chặn** thứ khác: `ROADMAP.md` đặt ngưỡng 300/655 câu có giải thích
để mở khoá RAG (`adr/ADR-003-AI-LAYER.md` §3.3). Còn thiếu 176 câu.

---

## 2. Bằng chứng đã có trong kho

Hai part đã làm, và chúng cho ra hai kết quả rất khác nhau. Chỗ khác nhau đó là
toàn bộ nội dung của tài liệu này.

### 2.1 Part 1 hỏng một nửa

Ba trong sáu câu lấy mẫu kết thúc bằng đúng một dạng câu:

> Các câu (A), (B) và (D) không đúng vì mô tả những hành động hoặc đồ vật không
> phù hợp với hình ảnh.

Đó là một câu vòng tròn — *"các câu sai thì sai vì chúng sai"*. Nó **thoả mãn**
yêu cầu "nói vì sao từng câu sai" mà không dạy được gì, và không câu nào tả đủ
trong ảnh thật sự có gì để người học nhìn lại mà thấy.

Đáng chú ý: `part5_system.md` đã dặn *"The explanation names the reason EACH wrong
option is wrong, not just why the right one is right"*. Lời dặn ấy vẫn bị lách
được bằng một câu gộp cả ba. **Luật đúng nhưng chưa đủ chặt là luật sẽ bị lách.**

### 2.2 Part 2 thì tốt

> Câu hỏi hỏi ai quan tâm đến việc bắt đầu một chương trình đi chung xe. Lựa chọn
> (B) "Clara's already organizing one." trả lời trực tiếp bằng cách nêu tên Clara
> và cho biết cô ấy đang tổ chức một chương trình. Lựa chọn (A) không liên quan
> và dùng từ "pool" trong "carpool" để tạo yếu tố gây nhiễu liên quan đến bơi
> lội. Lựa chọn (C) chuyển sang chủ đề về một bài viết.

Nó làm ba việc theo đúng thứ tự: **thuật lại** câu hỏi đã nghe → **trích** đáp án
đúng bằng tiếng Anh → nêu **cụ thể** từng câu sai sai ở đâu, kể cả gọi tên bẫy.

---

## 3. Nguyên tắc tổ chức

> **Giải thích chỉ có ích khi người học đối chiếu được với một thứ gì đó. Việc
> đầu tiên của nó là dựng lại thứ người học không còn nhìn thấy — rồi mới lập
> luận.**

Tỉ lệ "dựng lại" so với "lập luận" đảo ngược hoàn toàn giữa các part, và đó là lý
do một khuôn duy nhất cho cả bảy part sẽ sai ở hai đầu.

| Part | Lúc đọc giải thích còn thấy gì | Phải mở đầu bằng |
|---|---|---|
| 5 | cả câu | không cần dựng lại — vào thẳng quy tắc |
| 6 | cả đoạn văn | **câu nào** quyết định chỗ trống (thường không phải câu chứa nó) |
| 7 | cả đoạn văn | định vị dòng làm bằng chứng |
| 1 | bức ảnh | tả trong ảnh thật sự có gì |
| 3, 4 | không gì cả (audio đã tắt) — nhưng lời thoại nằm trong `question_set.audio_script` | trích đúng dòng đó |
| 2 | **không gì hết** | thuật lại câu hỏi *và* cả ba lựa chọn |

Part 2 là ca cực đoan và đáng ghi riêng: đề không in ra chữ nào, nên giải thích
của nó là **bản ghi duy nhất** của thứ đã được nói. Ở đó nó vừa là giải thích vừa
là nội dung.

Part 6 là ca dễ làm sai nhất theo hướng ngược lại: nó *trông* giống Part 5 nên dễ
bị viết như Part 5, nhưng bẫy kinh điển của Part 6 là thì hoặc liên từ do **câu
bên cạnh** quyết định. Một giải thích chỉ đọc câu chứa chỗ trống sẽ đúng về hình
thức và sai về nội dung.

---

## 4. Làm sao mô hình thấy đúng ngữ liệu

§3 đòi giải thích phải dựng lại thứ người học không còn thấy. Nhưng người *viết*
giải thích cũng không thấy — nó không nghe được audio, không nhìn được ảnh. Nên
câu hỏi thật là: ngữ liệu chính xác đến tay nó bằng đường nào.

### 4.1 Ở mọi part, ngữ liệu chính xác đã tồn tại — vấn đề là nó có sống sót không

| Part | Ngữ liệu chính xác | Có trong DB? |
|---|---|---|
| 3, 4 | `question_set.audio_script` | ✅ nguyên văn |
| 6, 7 (chữ) | đoạn văn của `question_set` | ✅ |
| 7 (hình) | `image_asset.alt_text` | ✅ 15/15 |
| 1 | mô tả ảnh trong khối `[PHOTO]` | ❌ chỉ ở `workdir/photos/*.txt` |

**Hình ngữ liệu Part 7 là ca đã giải xong, và cách giải đáng chép lại.** Hình đó
được *vẽ từ dữ liệu*, nên `Graphic.alt_text()` sinh chữ từ **chính dữ liệu vừa
vẽ** — không ai nhìn ảnh cả. `graphics.py` ghi lý do: *"mô tả tay trôi khỏi hình
ngay lần sửa đầu tiên"*. Và `assign_passage_image` trả 409 nếu hình ngữ liệu
thiếu `alt_text`, tức là một cổng chứ không phải một lời dặn.

Nguyên tắc rút ra: **đừng bảo mô hình nhìn ảnh — hãy lấy chữ từ thứ đã tạo ra
ảnh.** Nó đúng ở mọi chỗ hình được *sinh ra*, và chỉ hỏng ở chỗ hình được *tìm
thấy*.

### 4.2 Part 1 hỏng vì không có mô tả nào cả

24 trên 25 ảnh Part 1 **không có `alt_text`**. Đó mới là nguyên nhân thật của
những câu vòng tròn ở §2.1: mô hình được bảo giải thích một bức ảnh nó không thấy
và chưa ai tả. Nó làm đúng thứ duy nhất làm được.

### 4.3 Cách sửa hiển nhiên là một lỗ rò đáp án

`alt_text` đi thẳng tới người học qua `image_alt` **trong lúc đang làm bài**. Và
`admin_questions.py` ghi rõ vì sao Part 1 khác Part 6/7:

> Ở Part 1 nội dung ảnh chính là thứ không được mô tả quá kỹ — **mô tả kỹ là lộ
> đáp án**.

Nên sinh mô tả chi tiết rồi đổ vào `alt_text` là rò đáp án qua đúng đường trợ
năng — lỗ mà người kiểm bằng mắt không bao giờ thấy, vì nó chỉ hiện với trình đọc
màn hình.

**Hai trường, yêu cầu ngược nhau, và không được gộp:**

| | `alt_text` | mô tả cho người viết giải thích |
|---|---|---|
| ai đọc | người học, **trong lúc làm bài** | chỉ đường soạn nội dung |
| yêu cầu | vừa đủ để làm được bài, **cố ý mơ hồ** | cặn kẽ từng chi tiết |
| lộ ra lúc nào | ngay | chỉ sau cổng `reveal` |

### 4.4 Mô tả cặn kẽ ấy đã được viết ra rồi

`part1_system.md` bắt mô hình:

> Write the four statements FIRST, then describe the photograph that makes exactly
> one of them true. The description **must fix every detail the four statements
> depend on**.

Đó chính là ground truth **theo định nghĩa** — đáp án đúng được xác định *bằng*
nó. Nó tốt hơn việc bảo một vision model đọc lại tấm ảnh, vì tấm ảnh chỉ là thứ
tìm được để *xấp xỉ* mô tả đó; hai bên lệch nhau thì mô tả mới là thứ câu hỏi
được viết dựa vào. `graph.py` ghi nó ra `workdir/photos/<slot>.txt` rồi thôi —
nó chết theo workdir.

### 4.5 Kết luận

1. **Đừng với tới vision model** cho đề sinh mới. Mô tả định nghĩa đáp án đã có.
2. **Giữ nó lại** — viết giải thích ngay trong lượt đó (§7.1), vì đó cũng là
   *khoảnh khắc duy nhất* ngữ liệu chắc chắn còn đủ, hoặc lưu ở phía soạn thảo.
3. **Không bao giờ đổ vào `alt_text`.** Khác người nhận, ngược yêu cầu.
4. Chỉ **25 câu Part 1 cũ** đã mất workdir mới cần một lượt vision — và đầu ra đi
   vào *giải thích*, thứ vốn đã nằm sau cổng `reveal`, không vào `alt_text`.

---

## 5. Hai kiểu hỏng im lặng, chặn bằng máy

Cả hai đều đọc rất trôi chảy, nên không có cách nào phát hiện bằng mắt ở quy mô
vài trăm câu.

**5.1 Mô hình biện hộ cho đáp án sai cũng trôi chảy y như biện hộ cho đáp án
đúng.** Chặn: chữ cái nêu trong giải thích phải khớp `question.correct_option_id`.
Một phép so chuỗi.

**5.2 Mô hình bịa ra dòng trích dẫn không có trong lời thoại.** Đây là kiểu tệ
nhất — người học đi tìm một câu không tồn tại rồi kết luận tai mình có vấn đề.
Chặn: mọi đoạn tiếng Anh đặt trong ngoặc kép phải là **chuỗi con** của
`audio_script` / đoạn văn / nội dung lựa chọn. Rẻ, và bắt đúng thứ nguy hiểm nhất
ở Part 3, 4 và 7.

Đây là hai *cổng*, không phải hai lời dặn. Lời dặn thì §2.1 đã cho thấy kết cục.

---

## 6. Cách viết luật để câu vòng tròn không hợp lệ

Hai thứ, dùng cùng nhau:

**6.1 Mỗi câu sai một mệnh đề riêng, và mệnh đề đó phải nhắc lại câu ấy nói gì.**
Đủ để một câu gộp ba lựa chọn không còn là câu trả lời hợp lệ về mặt hình thức.

**6.2 Một danh sách đóng các loại bẫy theo từng part**, để mô hình *gọi tên* bẫy
thay vì tả chung chung:

| Part | Loại bẫy |
|---|---|
| 1 | hành động không diễn ra · sai vật · người không có trong ảnh · đúng vật nhưng sai hành động |
| 2 | trả lời sai loại câu hỏi (hỏi *when* đáp *where*) · từ gần âm · lặp lại từ vừa nghe |
| 3, 4 | lặp từ đã nghe nhưng sai ngữ cảnh · đúng thông tin nhưng sai người nói · đúng nhưng không trả lời câu hỏi |
| 5 | sai từ loại · sai kết hợp từ · sai thì/thể/số · từ có thật nhưng khác trường nghĩa |
| 6 | quyết định bởi câu trước hoặc câu sau · sai quan hệ logic của liên từ · sai thì so với mốc thời gian trong đoạn |
| 7 | đúng nhưng không trả lời câu hỏi · có nhắc nhưng sai chi tiết · trái với đoạn văn · suy diễn quá xa |

Danh sách đóng chứ không mở: một trường tự do sẽ quay về đúng câu "không phù hợp
với hình ảnh".

---

## 7. Hai chỗ sinh, không phải một

**7.1 Câu mới — viết giải thích trong CÙNG lượt gọi đã viết câu hỏi.** Lúc đó mô
hình còn biết nó dựng mỗi đáp án nhiễu để bẫy cái gì, và ý định ấy mất hẳn khi
câu được lưu. Đây là điều Part 5 đang làm, và là lý do giải thích của Part 5 nêu
được lý do từng lựa chọn sai.

**7.2 Câu cũ — một lượt riêng.** 531 câu đã có không còn lượt gọi nào để bám vào.
Đầu vào: câu hỏi + đáp án đúng + `audio_script`/đoạn văn. Đây là công việc lớn
hơn hẳn và nên chạy theo từng part.

Làm 7.1 trước, vì nếu không thì mỗi đề sinh thêm lại đào sâu thêm hố cần bù.

---

## 8. Ngôn ngữ và độ dài

- **Văn tiếng Việt** — khu học viên là tiếng Việt (`part5_system.md` đã chọn thế).
- **Trích dẫn giữ nguyên tiếng Anh.** Đó là thứ người học đã nghe hoặc đã đọc;
  dịch nó ra là cắt mất đường đối chiếu, tức là bỏ đi chính việc ở §3.
- Hai đến bốn câu. Không có trần thì Part 7 sẽ ra một đoạn văn.

---

## 9. Bước tiếp theo: thí điểm một part, đừng viết sáu prompt

§2.1 là lý do. Một lời dặn nghe hợp lý vẫn đẻ ra câu vòng tròn, nên nhân luật ra
sáu part dựa trên lý thuyết là nhân cả lỗi ra sáu chỗ.

**Chọn Part 3 làm thí điểm**, vì nó có `audio_script` sẵn nên kiểm được **cả hai**
cổng ở §5 ngay trong đợt đầu. Viết luật → sinh chừng năm câu → đọc kết quả thật →
rồi mới quyết định khuôn chung.

Thứ tự làm sau khi khuôn đã chốt, xếp theo giá trị cho người học chứ không theo
độ dễ:

1. **Part 2** (75 câu còn lại) — chỗ khó tự chẩn đoán nhất trong cả đề, vì không
   in ra chữ nào. Sai rồi thì không có gì để đọc lại.
2. **Part 3 + 4** (210) — vừa mới rẻ đi vì lời thoại đã nằm trong database.
3. **Part 6** (52).
4. **Part 1** (19 câu còn lại) — nhưng trước đó phải giải xong §4: 25 câu Part 1 hiện
   có đều đã mất mô tả ảnh, nên chúng cần một lượt vision riêng, không dùng chung
   khuôn với các part khác.
5. **Part 7** (167) — khối lượng lớn nhất nhưng người học đọc lại đoạn văn được,
   nên tự phục vụ được nhiều nhất.

Riêng Part 2 và Part 3+4 đã đủ vượt ngưỡng RAG ở §1.

Ghi chú về thứ tự: Part 5 đang 96% và **không nằm trong danh sách ưu tiên** — đó
đúng là part mà người học ít cần giải thích nhất, vì cả câu nằm ngay trước mắt.
Việc nó được làm trước là do tình cờ của §1, không phải do nó đáng làm trước.
