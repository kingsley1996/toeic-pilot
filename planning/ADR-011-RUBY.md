# ADR-011 — Ruby: đơn vị của góc thú cưng, kiếm bằng việc học

Trạng thái: **đề xuất**, chưa dựng dòng nào. Viết 2026-08-27.

Chặn lát 8 (gacha) của ADR-010: trứng phải mua bằng *một thứ gì đó*, và §6.2 đã
loại thứ hiển nhiên nhất.

---

## 0. Vì sao không dùng XP, và vì sao câu đó quan trọng

XP người học nuôi **level**, mà **level không bao giờ tụt** — đó chính là thuộc
tính mà sổ cái `xp_event` được dựng ra để có (USER-ROAD §2.1). Cho tiêu XP là
phá đúng thuộc tính ấy, hoặc buộc phải dựng một khái niệm "XP đã tiêu" chạy song
song với sổ cái, và hai con số đó sẽ lệch nhau.

Nên phải có một đơn vị thứ hai. Câu hỏi thật không phải "có nên" mà là **"nó
khác XP ở chỗ nào"** — vì nếu nó chỉ là XP có thêm đường tiêu thì nó là cùng một
thứ mang hai cái tên, và mọi thứ dựng trên nó chỉ nhân đôi phần bookkeeping.

---

## 1. Câu trả lời: **XP thưởng KHỐI LƯỢNG, ruby thưởng VIỆC LÀM XONG**

Đây là quyết định trung tâm của tài liệu này.

Nhìn vào dữ liệu thật đang có, XP được trao theo từng đơn vị nhỏ và có trần
ngày 120:

| Nguồn | Mức | Đã trao (thật) |
|---|---|---|
| `vocabulary_review` | 2 / lượt ôn | 238 |
| `dictation_complete` | 5 / câu đúng trọn | 895 |
| `attempt_submit` | 30 / lượt nộp | 766 |
| `daily_task` | theo khe | 410 |

Đó là phần thưởng cho **khối lượng**, và nó đúng: nó khiến người ta mở app ra
mỗi ngày và làm thêm một ít.

Nhưng có một hạng hành vi mà hệ hiện tại **gần như không thưởng**: *làm xong một
thứ*. Nghe hết một bài dictation, thuộc trọn một chủ đề từ vựng, làm hết một đề
200 câu. Ba việc đó đắt hơn nhiều lần một lượt ôn, và người học nhận về đúng
tổng của các phần nhỏ — không có gì đánh dấu rằng họ vừa *hoàn thành* cái gì.

**Ruby trả vào đúng chỗ trống đó.** Hệ quả:

- Nó không phải XP đổi tên. Hai đơn vị đo hai thứ khác nhau, nên nhìn cả hai con
  số vẫn học được điều gì đó.
- Nó đẩy người dùng về phía **kết thúc thay vì cày**. Một app học muốn người ta
  học hết một bài hơn là bấm ba trăm lượt ôn lấy điểm.
- Nó **tự giới hạn tốc độ mà không cần trần**: một bài dictation chỉ xong được
  một lần. Xem §4.

---

## 2. Bảng kiếm ruby

Con số là **đề xuất khởi điểm**, và chúng là **hàng trong bảng cấu hình** chứ
không phải hằng số (§6).

| `source_type` | Trao khi | Ruby | Lặp lại |
|---|---|---|---|
| `story_complete` | xong trọn một bài dictation (mọi câu `is_complete`) | 5 | mỗi bài một lần, VĨNH VIỄN |
| `topic_mastered` | mọi từ trong một chủ đề đạt grade 6 | 15 | mỗi chủ đề một lần |
| `attempt_full` | nộp một đề đầy đủ, trả lời ≥ 80% số câu | 25 | mỗi đề một lần |
| `attempt_mini` | nộp một đề rút gọn, trả lời ≥ 80% số câu | 8 | mỗi đề một lần |
| `daily_all` | xong **cả ba** việc trong ngày | 10 | mỗi ngày |
| `daily_gift` | mở quà, sau khi hôm nay đã học gì đó | 3 | mỗi ngày |
| `streak_week` | chuỗi ngày chạm mốc bội số của 7 | 20 | mỗi mốc một lần |

Năm điều về bảng này, mỗi điều là một quyết định:

**`daily_all` thưởng việc xong CẢ BA, không phải từng việc.** XP đã trả cho từng
khe rồi; ruby trả cho việc đóng trọn một ngày. Hai phần thưởng cùng hình dạng
trên cùng một hành động là chỗ người dùng không phân biệt được hai đơn vị.

**Ngưỡng của lượt làm đề là ĐỘ ĐẦY ĐỦ, không phải điểm số.** Trả ruby theo điểm
là phạt người học yếu vì họ yếu — sai hoàn toàn với một sản phẩm dạy học. Nhưng
trả cho mọi lượt nộp bất kể gì thì bấm bừa qua 200 câu trong hai phút cũng được
25 ruby. Ngưỡng "đã trả lời ≥ 80% số câu" chặn đường thứ hai mà không đụng tới
người thứ nhất.

**`streak_week` cuối cùng cũng làm `streak_bonus` có nghĩa.** `XP_SOURCES` khai
sẵn `streak_bonus` từ lâu và chưa bao giờ được dùng (USER-ROAD ghi nó chưa dựng).
Chuỗi ngày là hành vi đã đo được sẵn, nên đây là nguồn rẻ nhất trong bảng.

**Quà hàng ngày phải ĐỔI LẤY một việc đã học, không đổi lấy một lần mở app.**

Bản đầu của tài liệu này liệt "không tặng ruby cho việc đăng nhập" vào mục cố ý
không làm, với lý do: thưởng cho việc mở app mà không học là dạy đúng cái hành vi
không muốn. Samuel đã quyết là có quà hàng ngày, nên luật ấy được viết lại chứ
không bỏ — quà **mở được sau khi ngày hôm đó đã tính vào chuỗi ngày**, tức là đã
có một hoạt động học thật.

Nhìn từ phía người dùng thì nó vẫn là "vào nhận quà mỗi ngày", chỉ khác ở chỗ nút
sáng lên sau bài đầu tiên thay vì sáng sẵn lúc mở app. Và nó cho cái nút một câu
để nói: *"học xong một chút là mở được quà"* — một lời mời, không phải một phần
thưởng cho sự có mặt.

Ba ruby là con số nhỏ có chủ ý. Quà hàng ngày là **nhịp**, không phải nguồn thu:
nếu nó lớn hơn phần thưởng cho việc học xong một bài thì nó dạy người ta rằng ghé
qua đáng giá hơn làm xong.

**Không có nguồn nào trả theo *lượt* nhỏ.** Không có "2 ruby mỗi từ ôn". Có nó
thì ruby thành XP thứ hai, và §1 mất hết ý nghĩa.

---

## 3. Ranh giới không được vượt: **con thú không bao giờ phụ thuộc vào ruby**

CLAUDE.md đã ghi một luật cho góc thú cưng, và nó là luật bảo vệ chính sản phẩm
học: *"một chỉ số cạn sau vài giờ biến nó thành việc phải làm, và việc phải làm
thứ hai bên cạnh việc học là thứ khiến người ta đóng hẳn bảng này lại."*

Ruby nới rộng đúng cái rủi ro đó. Nên:

- **Cho ăn, chọc, đi dạo VĨNH VIỄN miễn phí.** Ba hành động giữ con thú ổn không
  bao giờ được tính tiền.
- **Con thú không chết, không ốm, không bị phạt vì hết ruby.** Đã ghi ở ADR-010
  §11 và nay áp cho cả ruby.
- **Ruby chỉ mua THÊM**: trứng, và sau này là đồ trang trí. Không bao giờ mua
  thứ để tránh một hậu quả xấu.

Ranh giới này là thứ tách "phần thưởng cho việc học" khỏi "một cái máy nhai thời
gian gắn cạnh việc học". Bỏ nó đi thì mọi lập luận còn lại trong tài liệu này
không cứu được gì.

---

## 4. Sổ cái, không phải bộ đếm — và lần này nó bắt buộc

Với XP của con thú (ADR-010 §5) tôi đã chọn một bộ đếm và ghi rõ điều kiện huỷ
đánh đổi: *"đánh đổi ấy hết hạn vào ngày XP con thú mua được thứ gì thật… lúc đó
phải chuyển sang sổ cái TRƯỚC khi thêm chỗ tiêu, vì một bộ đếm không trả lời được
câu 'điểm này từ đâu ra'."*

Ruby có đường tiêu ngay từ ngày đầu, nên điều kiện ấy đã đúng ngay lúc này.

```
ruby_event
  id           uuid PK
  user_id      uuid FK users ON DELETE CASCADE
  amount       int            -- DƯƠNG là kiếm, ÂM là tiêu
  source_type  varchar(32)
  source_id    uuid NULL
  created_at   timestamptz
  UNIQUE (user_id, source_type, source_id)
```

Số dư là `SUM(amount)`. Bốn tính chất đi kèm:

**Khoá duy nhất LÀM LUÔN việc chống cày.** Xong bài dictation số 7 sinh
`source_id = story_id`, nên lần thứ hai chèn bị từ chối bởi database chứ không
bởi một đoạn `if` ai đó phải nhớ viết. Đây là lý do §2 không cần trần ngày:
nội dung tự giới hạn tốc độ.

**Nguồn lặp theo NGÀY dùng `source_id` tất định**, sinh từ (người, ngày địa
phương, khe) — đúng cách `daily_tasks.grant_rewards` đã làm. Gọi lại bao nhiêu
lần cũng chỉ trao một lần.

**Sửa mức thưởng không lấy lại thứ đã trao**, vì mỗi hàng lưu số ruby *tại thời
điểm đó*. Cùng tính chất khiến sổ cái XP an toàn để admin chỉnh.

**Tiêu là một hàng ÂM, không phải một phép trừ.** Lịch sử giữ được câu "đã tiêu
vào đâu", và đó là thứ duy nhất trả lời được khiếu nại "tôi có 40 ruby, giờ còn
10".

---

## 5. Chỗ khó thật: **sổ cái làm việc TIÊU thành một cuộc đua**

Số dư là một phép `SUM`, nên "kiểm đủ tiền rồi trừ" có một khe hở kinh điển: hai
lần mở trứng gửi cùng lúc đều đọc thấy 30 ruby, đều thấy đủ cho một quả 25, và
đều ghi một hàng −25. Số dư thành −20. Không có ràng buộc nào bị vi phạm, không
có lỗi nào, và người dùng nhận hai quả trứng với tiền của một quả.

Dự án này đã gặp đúng lớp lỗi ấy ở đăng ký tài khoản, và `tests/test_concurrency.py`
ghi lại bài học quan trọng nhất: **bắn N luồng không kiểm được chuyện đua** — luồng
đầu commit xong trước khi các luồng sau tới chỗ kiểm, nên nhánh lỗi không bao giờ
chạy và bài kiểm xanh cả khi bản sửa bị gỡ. Phải có `threading.Barrier` giữa bước
kiểm và bước commit.

Ba lối, và tôi đề xuất lối thứ hai:

| Lối | Vì sao không / có |
|---|---|
| Cột `balance` có `CHECK (balance >= 0)` | Hai nguồn sự thật cho một con số, và cái sai là cái không ai đọc |
| **Khoá tư vấn Postgres theo `user_id`** quanh bước kiểm-và-ghi | Nối tiếp hoá đúng một người, không đụng người khác; dự án đã biết pattern này |
| Bảng riêng `ruby_balance` khoá bằng `SELECT … FOR UPDATE` | Chạy được, nhưng lại là cột số dư ở lối thứ nhất |

Khoá tư vấn giữ được sổ cái là nguồn sự thật duy nhất. Cái giá: mọi đường tiêu
**phải** đi qua một hàm chung — và đó là thứ cần một luật, vì đường tiêu thứ hai
viết ở chỗ khác sẽ không có khoá, sẽ chạy đúng trong mọi lần thử tay, và sẽ hỏng
đúng vào ngày có hai người bấm cùng lúc.

---

## 6. Mức thưởng là HÀNG, không phải hằng số

Theo đúng khuôn `progression_setting` / `frame_tier` / `badge_rule` / `pet_species`:
một bảng `ruby_rule` (`source_type` PK, `amount`, `enabled`), sửa ở `/admin`
sau `require_role("admin")` — đặt giá cho cả nền kinh tế là quyền vận hành, không
phải quyền biên tập.

Mặc định **gieo lười ở lần đọc đầu**, một nguồn sự thật trong mã, và **bảng rỗng
nghĩa là "chưa từng cấu hình"** — cùng hệ quả đã ghi cho `pet_species`.

---

## 7. Không có phần thưởng nào là vô hình

Một hệ điểm mà người ta không thấy mình vừa kiếm được thì không kích thích gì cả.
Ba chỗ, và cả ba đều dùng thứ đã có sẵn:

- **Toast ngay lúc kiếm được.** Hệ thông báo đã dựng ở `lib/toast.tsx`, và ràng
  buộc của nó áp luôn: chỉ thông báo đi sau một cú bấm mới xin được tiếng.
- **Số dư nằm cạnh việc hôm nay trên `/dashboard`**, không giấu trong góc thú
  cưng. Người ta phải thấy nó ở chỗ họ *học*, không phải ở chỗ họ *chơi*.
- **Khoảng cách tới quả trứng kế tiếp**, viết thành câu: "còn 5 nữa là mở được
  trứng thường". Đây là đòn bẩy mạnh nhất trong cả tài liệu — một con số trần
  không nói cho ai biết nên làm gì tiếp.

---

## 8. Các lát

| # | Lát | Xong nghĩa là |
|---|---|---|
| 1 | `ruby_event` + hàm `earn` dùng chung | Trao hai lần cùng một nguồn chỉ ghi một hàng |
| 2 | Nối vào ba đường đã có: dictation, từ vựng, lượt làm đề | Học xong một bài thì ruby nhích, và chỉ nhích một lần |
| 3 | `daily_all` + `daily_gift` + `streak_week` | Xong cả ba việc, mở quà, giữ chuỗi — mỗi thứ đúng một lần mỗi ngày |
| 4 | Hàm `spend` có khoá tư vấn + bài kiểm đua có `Barrier` | Hai lần tiêu đồng thời không tạo ra số dư âm |
| 5 | `ruby_rule` + `/admin` | Đổi mức thưởng không cần deploy |
| 6 | Số dư ở dashboard + toast + câu "còn bao nhiêu nữa" | Nhìn thấy được ở chỗ người ta học |

Lát 4 đứng trước gacha của ADR-010, không phải sau: mở trứng là đường tiêu đầu
tiên, và mở nó trước khi có khoá là mở đúng cái khe ở §5.

---

## 9. Cố ý KHÔNG làm

- **Không mua ruby bằng tiền thật.** Đó là một sản phẩm khác với một bộ nghĩa vụ
  pháp lý khác.
- **Không tặng ruby cho việc đăng nhập suông.** Quà hàng ngày có, nhưng nó mở sau
  khi ngày đó đã có hoạt động học — xem §2. Thưởng cho việc mở app mà không học là
  dạy đúng cái hành vi không muốn.
- **Không cho ruby âm.** Không có phạt, không có nợ. Sản phẩm này không phạt
  người học vì bất cứ điều gì.
- **Không hết hạn.** Ruby cũ mất giá trị là một cơ chế gây áp lực thời gian, và
  áp lực thời gian là thứ ADR-010 §11 đã từ chối khi quyết định con thú không
  chết.

---

## 10. Ba quyết định đã chốt (2026-08-27)

1. **Tên gọi: "ruby".** Dùng luôn làm tên bảng (`ruby_event`, `ruby_rule`), theo
   đúng cách `xp_event` mang tên người dùng nhìn thấy chứ không mang một tên kỹ
   thuật trung tính. Một cái tên trong giao diện và một cái tên khác trong
   database là chỗ mọi cuộc trao đổi về sau phải dịch qua lại.
2. **Mức thưởng ở §2 giữ nguyên**, cộng thêm `daily_gift`. Với bảng đó, một người
   học chăm được ~18 ruby/ngày, nên quả trứng thường giá 20–25 rơi vào khoảng
   một tới hai ngày.
3. **Ngưỡng lượt làm đề đo bằng SỐ CÂU ĐÃ TRẢ LỜI**, không bằng thời gian. Thời
   gian đo được nhưng nó thưởng cho việc *ngồi lâu*, và một người làm nhanh vì
   giỏi sẽ bị phạt. Số câu đã trả lời đo đúng thứ định đo: đã thật sự làm bài hay
   chưa.
