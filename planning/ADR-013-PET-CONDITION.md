# ADR-013 — Ba chỉ số nói lên điều gì, và độ hiếm khác nhau ở đâu

Tiếp sau ADR-010 (góc thú cưng), ADR-011 (ruby) và ADR-012 (chạm mặt). Đây là
tài liệu đầu tiên không thêm tính năng nào: nó đi sửa một thứ đã dựng xong nhưng
không có nghĩa.

---

## 0. Câu phải trả lời trước mọi câu khác

**Bỏ qua ba chỉ số ấy thì mất gì?** Hôm nay: không mất gì cả.

Đó không phải suy đoán. `PetView` — thứ duy nhất tầng vẽ nhận được — **không có
trường nhu cầu nào**, nên con thú đang đói và con thú vừa ăn no được vẽ giống hệt
nhau. Và ba chỉ số chỉ ảnh hưởng tới đúng ba cái nút đổi chính chúng:

| Chỉ số | Ảnh hưởng duy nhất hôm nay |
|---|---|
| No | Dưới 0,95 thì cho ăn được; dưới 0,2 thì không đi dạo được; dưới 0,25 thì vui tụt nhanh hơn và chọc kém vui hơn |
| Sức | Dưới 0,15 thì không đi dạo được; trên 0,9 thì không ngủ được |
| Vui | **Không ảnh hưởng tới bất cứ thứ gì** |

Một vòng khép kín: ba cái nút đổi ba chỉ số, và ba chỉ số quyết định ba cái nút.
Không chạm tới XP, ruby, chạm mặt, hay việc học. Cột "Vui" đặc biệt tệ — nó chỉ
là một thanh chạy lên chạy xuống.

Độ hiếm cũng vậy: nó quyết định **khó kiếm tới đâu** (`drop_weight`) và **vòng
sáng màu gì** (`tier` → token màu). Một con huyền thoại và một con thường hành xử
y hệt nhau.

---

## 1. Hai quyết định chốt trước, vì chúng định hình mọi thứ còn lại

**Ba chỉ số KHÔNG chạm ra ngoài bảng thú cưng.** Không cộng ruby, không cộng XP,
không đổi nhịp sinh của chạm mặt. Lý do là luật đã có: gamification không được
đổi thứ đã thật sự học được, và một chỉ số chăm sóc mà quyết định giá trị của
việc học là đúng thứ ấy — chỉ khoác một cái áo dễ chịu hơn.

**Độ hiếm khác nhau ở HÀNH VI, không ở sức mạnh.** Con hiếm không giúp học nhanh
hơn. Nó *sống động* hơn: nhiều dáng đứng hơn, nhiều việc tự làm hơn, phản ứng với
nhiều thứ hơn. Cộng thêm sức mạnh theo bậc sẽ biến gacha thành đường tăng lực
trong một ứng dụng học — và lúc đó câu hỏi "mở trứng có đáng không" trở thành một
câu hỏi về điểm số, không phải về việc thích con nào.

**Hệ quả phải nhìn thẳng: phần thưởng duy nhất còn lại LÀ CON THÚ.** Không có con
số nào đi kèm để bù. Nên tầng biểu cảm không phải phần trang trí của tài liệu này
— nó là toàn bộ tài liệu này. Làm lấy lệ thì ba chỉ số vẫn vô nghĩa, chỉ là vô
nghĩa một cách đẹp hơn.

---

## 2. Mỗi chỉ số nói MỘT câu, và câu ấy nhìn thấy được

Ràng buộc thiết kế: đọc ra được **mà không cần đọc chú thích nào**. Người dùng
nhìn con thú và biết nó đang thiếu gì, rồi mới liếc sang thanh chỉ số để xác nhận
— không phải ngược lại.

### No → nó có ĐI KHÔNG

- No: đi lại thoải mái, tự lang thang khắp bản đồ.
- Đói (< 0,25): quanh quẩn một chỗ, bước chậm hơn, dừng nhiều.

Đọc ra ngay: một con vật đói thì không đi rong. Nó cũng giải thích sẵn luật đã có
— "đói thì không đi dạo được" thôi là một lời từ chối bất ngờ và trở thành thứ
người dùng đã đoán trước.

### Sức → nó có ĐỨNG KHÔNG

- Còn sức: đứng, thở, nhún khi đi.
- Kiệt (< 0,15): **ngồi bệt xuống**, không tự đi đâu nữa.

Đây là chỉ số dễ nhìn nhất nếu diễn tả đúng, và hôm nay nó hoàn toàn vô hình.

### Vui → nó có CHƠI KHÔNG

- Vui: nhảy tại chỗ, quay đầu nhìn theo con trỏ, lại gần sinh vật hậu cảnh, tự đi
  về phía khách trên bản đồ.
- Buồn: đứng yên, không tự làm gì.

Cột "Vui" hôm nay không ảnh hưởng tới gì cả, nên nó là chỗ có nhiều đất nhất và
cũng là chỗ đáng làm trước.

### Và một dòng CHỮ, không chỉ ba cái thanh

Thanh chỉ số cố ý không in phần trăm — đúng, và giữ nguyên. Nhưng nó nên nói một
từ về tình trạng: *đang đói · mệt · vui vẻ · bình thường*. Ba cái thanh không
nhãn buộc người dùng tự dịch, còn một từ thì không.

---

## 3. Bóng nói: thứ rẻ nhất biến chỉ số thành nghĩa

Một bong bóng nhỏ trên đầu con thú, thỉnh thoảng hiện: biểu tượng thức ăn khi
đói, trái tim khi vui, Zzz khi buồn ngủ.

**Thỉnh thoảng, không thường trực.** Một biểu tượng dính mãi trên đầu là một lời
nhắc nợ, và cái góc này không được phép có nợ (ADR-010 §11). Nó chỉ nói *"tôi
đang thế này"* rồi biến đi.

Hạ tầng đã có sẵn: bong bóng thoại của ADR-012 và `PixelIcon` của mấy mẩu bay
lên. Đây là chỗ tốn ít công nhất mà đổi được nhiều nhất.

---

## 4. Con thú phải TỰ LÀM GÌ ĐÓ

Hôm nay nó chỉ đi khi được bảo đi. Một con vật đứng bất động cho tới khi bị bấm
là thứ không ai mở ra xem lần thứ hai — và đây có lẽ mới là nguyên nhân thật của
"chưa hấp dẫn", hơn cả chuyện chỉ số vô nghĩa.

Nên nó tự đi lang thang, và **tình trạng quyết định nó lang thang thế nào**: no và
vui thì đi xa, đói thì quanh quẩn, kiệt sức thì ngồi. Đó cũng chính là chỗ ba chỉ
số trở nên nhìn thấy được — không cần thêm cơ chế nào khác.

Ràng buộc: đi lang thang **không tốn nhu cầu**. Tốn thì con thú tự làm cạn chính
nó trong lúc người dùng không có mặt, và một cái bảng mở ra đã thấy mọi thanh
chạm đáy là một lời trách móc.

---

## 5. Độ hiếm: một VỐN TIẾT MỤC, không phải một hệ số

Mỗi bậc mở thêm việc con thú biết làm. Bậc cao có tất cả những gì bậc dưới có.

| Bậc | Thêm vào |
|---|---|
| common | Đi, thở, ba hành động đã có |
| uncommon | Nhảy tại chỗ lúc rảnh |
| rare | Vệt sáng mờ theo chân khi đi |
| epic | Quay đầu nhìn theo con trỏ; lại gần sinh vật hậu cảnh |
| legendary | Tự đi về phía khách trên bản đồ; ngẩng nhìn trời lúc đêm |

Vì sao là *vốn tiết mục* chứ không phải một con số nhân: nhìn hai con cạnh nhau
là biết ngay con nào hiếm hơn, mà không con nào "mạnh" hơn. Và nó cộng dồn được —
thêm một bậc sau này chỉ là thêm một dòng, không phải cân lại cả bảng.

Cái giá phải nói ra: **tiết mục là nội dung, không phải mã.** Mỗi việc con thú
biết làm là một hoạt ảnh phải nghĩ ra và chỉnh bằng mắt, và bộ sprite chỉ có MỘT
khung cho mỗi loài (ADR-010 §14.5) nên mọi thứ phải diễn tả bằng vị trí, tỉ lệ và
một chút xoay. Đó là lý do bảng trên dừng ở năm bậc và mỗi bậc đúng một tiết mục.

---

## 6. Các lát

| # | Lát | Xong nghĩa là |
|---|---|---|
| 1 | `PetView.needs` + tư thế theo tình trạng (ngồi khi kiệt, ủ rũ khi đói) | Nhìn con thú là biết nó thiếu gì, không cần nhìn thanh |
| 2 | Một dòng chữ tình trạng trong HUD | Ba cái thanh thôi bắt người dùng tự dịch |
| 3 | Bong bóng cảm xúc, thỉnh thoảng | Chỉ số tự nói ra, và không thành lời nhắc nợ |
| 4 | Tự đi lang thang, phạm vi theo tình trạng | Mở bảng ra thấy nó đang sống, không đứng chờ |
| 5 | Vốn tiết mục theo bậc hiếm | Hai con cạnh nhau nhìn là biết con nào hiếm |

Lát 1 đứng trước vì nó là đường ống: chừng nào nhu cầu chưa tới được tầng vẽ thì
không lát nào sau đó làm được.

Lát 4 đáng làm sớm hơn thứ tự này gợi ý nếu phải chọn — nó là thứ đổi cảm giác
nhiều nhất cho một lượng công vừa phải.

---

## 7. Cố ý KHÔNG làm

- **Không để chỉ số chạm vào ruby, XP hay nhịp chạm mặt.** Xem §1.
- **Không cho độ hiếm bất kỳ lợi thế số học nào.** Xem §1.
- **Không phạt.** Không có trạng thái nào khoá một nút mà hôm nay đang mở, và
  không có chỉ số nào tụt vì người dùng nghỉ mấy hôm nhanh hơn hôm nay.
- **Không thêm chỉ số thứ tư.** Ba cái đã không ai đọc; cái thứ tư không sửa được
  chuyện đó.
- **Không nhắc nhở ngoài bảng.** Không chấm đỏ ở thanh điều hướng, không thông
  báo. Con thú đói là chuyện của con thú, không phải một việc phải làm.
