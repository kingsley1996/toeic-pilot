# ADR-012 — Chạm mặt ở Petland: NPC giao việc, và những đợt xâm nhập

Trạng thái: **đề xuất**, chưa dựng dòng nào. Viết 2026-08-27.

Tiếp sau khi ADR-010 xong cả chín lát và ADR-011 xong cả sáu. Đây là thứ đầu
tiên ở góc thú cưng **kéo người ta về phía bài tập** thay vì về phía con thú.

---

## 0. Câu phải trả lời trước mọi câu khác

CLAUDE.md ghi một luật cho góc này, và ADR-010 §11 lẫn ADR-011 §3 đều nhắc lại:

> *một chỉ số cạn sau vài giờ biến nó thành việc phải làm, và việc phải làm thứ
> hai bên cạnh việc học là thứ khiến người ta đóng hẳn bảng này lại.*

Một NPC **xuất hiện rồi biến mất sau mấy phút** là, đúng theo định nghĩa, một cơ
chế **áp lực thời gian** — nó nói "vào ngay không thì mất". ADR-011 §9 đã từ chối
đúng thứ đó khi quyết định ruby không hết hạn.

Nên tính năng này chỉ được phép tồn tại nếu trả lời được: *vì sao lần này áp lực
thời gian là đúng?*

**Trả lời: vì phần thưởng ở đây là THÊM, không bao giờ là MẤT — và vì việc phải
làm để nhận nó chính là việc học.** Bỏ lỡ một NPC không lấy đi của người dùng thứ
gì họ đang có; nó chỉ là một lời mời không được nhận. Và lời mời ấy nói: *làm ba
lượt ôn từ đi*. Đây là chỗ **đảo chiều** so với mọi thứ khác trong góc này: cho
ăn, chọc, đi dạo, mở trứng đều là chơi **cạnh** việc học; chạm mặt là lần đầu
tiên cái góc chơi **đẩy người ta vào** việc học.

Nhưng câu trả lời đó chỉ đúng nếu một điều kiện được giữ, và nó là ràng buộc
nặng nhất tài liệu này:

## 1. **NPC chỉ xuất hiện khi người học ĐANG Ở ĐÓ**

Không có đồng hồ nào chạy khi người dùng vắng mặt. Không thông báo đẩy. Không
chấm đỏ nào tích lại trong lúc họ không mở app.

Cách làm: **sinh ra lúc ĐỌC**, đúng khuôn `daily_tasks.grant_rewards` và
`gacha.settings_row` — mở bảng thú cưng ra thì máy chủ mới quyết định có ai xuất
hiện không. Hệ quả trực tiếp:

- **Không thể bỏ lỡ thứ chưa từng có.** Một NPC không sinh ra trong lúc bạn ngủ
  rồi hết hạn trước khi bạn dậy. Nếu bạn không mở app hôm nay thì hôm nay không
  có NPC nào cả — và đó không phải mất mát, đó là không có chuyện gì xảy ra.
- **Không có FOMO để nuôi.** Thứ duy nhất khiến người ta mở app liên tục là nỗi
  sợ bỏ lỡ; không có gì diễn ra khi vắng mặt thì không có gì để sợ.
- Đổi lại, **cái đồng hồ hết hạn vẫn còn nguyên ý nghĩa trong một phiên**: mở
  bảng ra, thấy NPC, và có mười phút để làm. Áp lực nhỏ ấy là thứ biến một lời
  mời thành một khoảnh khắc.

Nếu về sau có ai muốn thêm thông báo đẩy hay "NPC đã chờ bạn 3 tiếng", **đó là
lúc lập luận ở §0 hết hiệu lực** và cả tính năng phải xem lại.

---

## 2. Quyết định trung tâm: **nhiệm vụ KHÔNG dựng thêm một bộ chấm nào**

Dự án này đã có ba bộ chấm, mỗi bộ là nguồn sự thật của miền nó:

| Miền | Nguồn sự thật | Ghi lại ở |
|---|---|---|
| Từ vựng | `srs.review` (SM-2) | `vocabulary_review_state` + `_log` |
| Chép chính tả | `dictation.grade` | `dictation_attempt` |
| Câu trắc nghiệm | `question_option.is_correct` | `attempt_item` |

Một nhiệm vụ **mượn** đúng ba đường đó. Nó sở hữu *khung cảnh* — ai giao, thưởng
gì, hết hạn lúc nào — và không sở hữu *phép chấm*.

Đây không phải chuyện gọn gàng. Bộ chấm dictation đã có hai bản (máy chủ và
trình duyệt) và `lib/dictation.ts` phải mang một cảnh báo dài về việc hai bản
trôi khỏi nhau. Bản thứ ba, nằm trong một tính năng phụ, sẽ là bản không ai nhớ
cập nhật — và hậu quả là **một câu được chấm đúng ở màn học và chấm sai ở màn
nhiệm vụ**, thứ người dùng đọc ra là hệ thống hỏng chứ không phải là hai bộ chấm.

Hệ quả cụ thể, và đây là chỗ dễ làm sai nhất:

- **Trả lời một nhiệm vụ từ vựng PHẢI đi qua `POST /vocabulary/{id}/review`**,
  tức nó ghi vào SM-2 thật. Nếu không, người học vừa "làm bài" xong mà lịch ôn
  không đổi — họ đã học, và hệ thống giả vờ như chưa.
- **Câu trắc nghiệm không được lộ đáp án.** `QuestionPublic` cố ý không có
  `is_correct`; nhiệm vụ phải dùng đúng schema đó, không được tự dựng một schema
  "gọn hơn" rồi kèm đáp án cho tiện chấm ở client.
- Phép so đáp án hiện nằm trong `attempt.py::_correct_option_ids`. Nó phải **dời
  ra một service dùng chung** trước khi nhiệm vụ gọi tới — chép lại là dựng bộ
  chấm thứ tư.

---

## 3. Nhiệm vụ diễn ra Ở ĐÂU

Hai lối, và chúng cho hai sản phẩm khác nhau:

| Lối | Được | Mất |
|---|---|---|
| **Ngay trong bảng thú cưng** | Một khoảnh khắc liền mạch: thấy NPC → làm → nhận thưởng, không rời trang | Phải dựng một màn bài tập nhỏ trong bảng |
| Đẩy sang màn học thật | Không dựng gì thêm | Một cú chuyển trang cho một xung động kéo dài hai mươi giây — và xung động đó sẽ chết giữa đường |

**Đề xuất: ngay trong bảng.** Nhưng "trong bảng" chỉ nói về *chỗ hiển thị*; câu
trả lời vẫn đi ra đúng endpoint thật ở §2. Cái dựng thêm là một khung hiển thị,
không phải một bộ chấm.

Ba dạng nhiệm vụ ở lát đầu, mỗi dạng một endpoint đã có:

1. **Từ vựng** — hiện một từ đang đến hạn, người học tự chấm năm mức như thẻ
   lật. Gửi `POST /vocabulary/{id}/review`.
2. **Trắc nghiệm** — một câu Part 5 đã xuất bản, bốn lựa chọn, không kèm đáp án.
3. **Chép chính tả** — một câu ngắn, gõ lại. Gửi `POST /dictation/{id}/attempts`.

---

## 4. Kẻ xâm nhập: **cùng bộ máy, khác khung cảnh — và KHÔNG có hình phạt**

"Kẻ xâm nhập" kéo theo một trực giác rất mạnh: nếu không diệt thì phải mất gì
đó. Đây là chỗ tài liệu này nói **không**, và nói to.

ADR-010 §11 đã quyết: *không để thú chết* — "một app học phạt người dùng vì nghỉ
ba ngày là một app người ta không quay lại". Một con quái ăn mất ruby, hay làm
tụt chỉ số con thú, là đúng cái hình phạt ấy mặc áo khác. Tệ hơn: nó biến việc
mở app thành **phòng thủ**, và phòng thủ là việc phải làm.

Nên kẻ xâm nhập là **một cuộc chạm mặt khó hơn với phần thưởng lớn hơn**, không
phải một mối đe doạ:

- Không diệt được thì nó **biến mất và không có gì xảy ra**.
- Khác NPC ở ba chỗ: **nhiều bước** (ba câu liên tiếp thay vì một), **thưởng
  lớn hơn**, và **hiếm hơn**.
- Dấu cảnh báo trên đầu là *khung cảnh*, không phải lời đe doạ. Nó nói "ở đây có
  thứ đáng làm", giống hệt dấu chấm than vàng, chỉ khác màu.

Nếu một ngày ai đó muốn thêm hậu quả, hãy đọc lại đoạn này trước.

---

## 5. Hình dạng dữ liệu

```
encounter
  id            uuid PK
  user_id       uuid FK users ON DELETE CASCADE
  kind          varchar(16)     -- 'npc' | 'intruder'
  actor_tile    smallint        -- ô trong creatures.png, lấy từ petland-bestiary
  tile_x, tile_y smallint       -- chỗ nó đứng trên bản đồ
  task_kind     varchar(24)     -- 'vocabulary' | 'quiz' | 'dictation'
  target_id     uuid NULL       -- từ / câu hỏi / câu chép chính tả
  steps_total   smallint        -- 1 với NPC, 3 với kẻ xâm nhập
  steps_done    smallint
  reward_ruby   smallint        -- CHỐT LÚC SINH RA, không tra lại lúc trả thưởng
  state         varchar(16)     -- 'waiting' | 'done' | 'expired'
  expires_at    timestamptz
  created_at    timestamptz
```

Bốn tính chất:

**`reward_ruby` chốt lúc sinh ra.** Cùng luật đã khiến sổ cái XP và sổ ruby an
toàn để admin sửa: đổi mức thưởng giữa lúc một NPC đang đứng chờ không được đổi
lời hứa đã nói ra trên màn hình.

**`target_id` không phải khoá ngoại.** Nó trỏ vào ba bảng khác nhau, và một khoá
ngoại sẽ chặn việc xoá nội dung chỉ vì có một cuộc chạm mặt cũ trỏ vào — đúng
cái bẫy `dictation_attempt` RESTRICT đã dựng ra ở chỗ khác. Nội dung biến mất thì
cuộc chạm mặt hết hạn, thế thôi.

**Hết hạn suy ra lúc đọc, không cần job nền.** `expires_at` là mốc; `state` chỉ
đổi khi có ai đó nhìn tới. Cùng khuôn `pet_owned.sleep_until`, và vì cùng một lý
do: một trạng thái cần người khác dọn hộ là một trạng thái sẽ có lúc không được
dọn.

**Trả thưởng đi qua `ruby.earn` với `source_id = encounter.id`**, nên khoá duy
nhất `(user, source_type, source_id)` tự lo chuyện trả hai lần. Không có đoạn
`if` nào phải nhớ viết.

---

## 6. Vì sao thưởng bằng ruby lại KHÔNG phá luật của ADR-011

ADR-011 §1 đặt một luật gắt: *không nguồn nào trả theo lượt nhỏ; có nó thì ruby
thành XP thứ hai*. Một nhiệm vụ "ôn ba từ được 4 ruby" nghe đúng là thứ bị cấm.

Khác biệt nằm ở **cái gì giới hạn tốc độ**. Các nguồn của §2 tự giới hạn bằng
nội dung (một bài dictation chỉ xong được một lần). Một cuộc chạm mặt tự giới hạn
bằng **nhịp xuất hiện**: dù học mười tiếng liền, số NPC gặp được vẫn chỉ là số
lần bảng cho phép sinh ra. Không có đường nào cày nó.

Nên luật thật của ADR-011 — *không thể cày ruby bằng cách lặp lại việc nhỏ* —
vẫn nguyên vẹn. Điều kiện: **trần là nhịp sinh, và nhịp sinh phải là hàng cấu
hình**, không phải một hằng số nằm rải trong mã.

`source_type` mới: `encounter`. Không nằm trong `ruby_rule` (mức thưởng chốt trên
từng cuộc chạm mặt), cùng lý do `egg_refund` không nằm ở đó.

---

## 7. Các lát

| # | Lát | Xong nghĩa là |
|---|---|---|
| 1 | Bảng `encounter` + luật sinh/hết hạn + `GET /pet/encounters` | Mở bảng nhiều lần không sinh ra hai NPC; quá hạn thì tự tắt |
| 2 | Dấu hiệu trên bản đồ + bấm vào mở thẻ nhiệm vụ | Chấm than vàng đứng trên đầu đúng ô, bấm ra thẻ |
| 3 | Nhiệm vụ TỪ VỰNG, đi qua `/vocabulary/{id}/review` | Làm xong thì SM-2 đổi thật, và ruby vào ví |
| 4 | Nhiệm vụ CHÉP CHÍNH TẢ | Dùng đúng bộ chấm đã có |
| 5 | Nhiệm vụ TRẮC NGHIỆM + tách phép so đáp án ra service chung. **CHỜ NỘI DUNG** — xem §8.3 | Đáp án không rời máy chủ trước khi trả lời |
| 6 | Kẻ xâm nhập: nhiều bước, thưởng lớn hơn, dấu cảnh báo | Bỏ qua thì không mất gì |
| 7 | `encounter_setting` + `/admin` | Đổi nhịp sinh, thời gian sống, mức thưởng không cần deploy |

Lát 1 đứng trước mọi thứ vì luật sinh là chỗ duy nhất trong tài liệu này có thể
phá luật §1 — và một lỗi ở đó không nhìn thấy được từ giao diện.

**Sửa §1 ngày 2026-08-28: nhiều cuộc cùng lúc, tối đa HAI mỗi loại.** Bản đầu
cho đúng một cuộc mỗi lúc, với lập luận "hai lời mời cạnh tranh nhau thì người
ta làm cái dễ rồi bỏ cái kia". Lập luận ấy đúng ở số lớn và sai ở số hai: cái
thật sự xảy ra là một cuộc bị bỏ dở **chặn đứng cả làn** — mở thẻ, thấy câu khó,
để đó, và mười phút sau vẫn đúng câu ấy. Trần đếm **riêng từng loại**, vì một
trần chung sẽ để NPC lấp kín bản đồ và kẻ xâm nhập không bao giờ có chỗ.

Ràng buộc mới đi kèm, và nó nặng hơn cái trần: **một cuộc mới không bao giờ đẩy
một cuộc đang diễn ra đi.** Người đang gõ dở câu trả lời không được phép thấy đề
bài đổi dưới tay mình.

Hết hạn vì thế **không hẹn lại giờ nữa**: nhịp giờ do phép *sinh* giữ (mỗi lần
sinh tự hẹn lần sau), nên hẹn lại lúc hết hạn chỉ còn là phạt người ta vì đã lờ
một lời mời — §4 từ chối.

**Sửa §3 ngày 2026-08-27: nhiệm vụ từ vựng KHÔNG dùng thẻ lật.** Bản đầu mượn
nguyên màn thẻ lật — hiện nghĩa rồi để người học tự chấm năm mức — và điểm tự
chấm ấy chính là thứ quyết định có trả ruby hay không. Đó là một cái nút in tiền
gửi từ trình duyệt, và nó cũng không đo được gì, vì người bấm là người được
thưởng. Hai dạng thay thế đều **máy chấm**: gõ lại từ, và chọn nghĩa trong bốn ô.
Máy chủ nhận *câu trả lời* rồi tự quy ra điểm SM-2 qua `recall.judge` /
`recall.grade_for` — vẫn không có bộ chấm thứ hai nào, đúng §2.

Kéo theo một luật nhỏ mà cả hai dạng vi phạm theo hai kiểu khác nhau: **đề bài
không được chứa đáp án**. Dạng gõ lại không gửi `headword`; dạng chọn nghĩa không
gửi `entry_id` và mã của mỗi ô là băm theo `(cuộc chạm mặt, mục từ)` chứ không
phải id thật.

**Trạng thái 2026-08-27: lát 1, 2, 3, 4, 6 và 7 đã xong.** Chỉ lát 5 còn lại, và
nó chờ **nội dung** chứ không chờ code — xem §8.3. Trạng thái thật vẫn nằm ở
`ROADMAP.md` §4ab; dòng này chỉ để người đọc tài liệu này không tưởng cả bảng
còn nguyên.

---

## 8. Ba quyết định đã chốt (2026-08-27)

1. **Nhịp sinh: 20 phút một lần, sống 10 phút.** Một buổi học 30–40 phút gặp một
   tới hai NPC — đủ hiếm để mỗi lần gặp là một sự kiện, đủ dài để không phải bỏ
   dở việc đang làm. Kẻ xâm nhập hiếm hơn hẳn: khoảng một giờ một lần. Nhắc lại
   §1: hai con số này chỉ đếm **thời gian người dùng có mặt**, không phải thời
   gian trên đồng hồ.
2. **Thưởng: NPC 5 ruby, kẻ xâm nhập 20.** Ngang một bài dictation cho một việc
   nhỏ hơn nhiều, bù lại bằng chuyện nó hiếm — với nhịp 20 phút thì khoảng 15
   ruby một buổi, không lấn át các nguồn "làm xong" của ADR-011 §2. Đây cũng là
   con số khiến lập luận ở §6 đứng được: chạm mặt là gia vị, không phải nguồn thu.
3. **Làm theo độ dày của kho: từ vựng trước, rồi chép chính tả, trắc nghiệm sau
   cùng.** Kho đang rất lệch — **303 từ vựng**, **35 câu chép chính tả**, nhưng
   chỉ **55 câu trắc nghiệm** trong cả hai đề. Với 55 câu, một người chăm sẽ gặp
   lại câu cũ trong vài ngày, và lúc đó nhiệm vụ dạy **thuộc lòng đáp án** chứ
   không dạy tiếng Anh. Ngưỡng để mở dạng trắc nghiệm là **kho đủ lớn để một
   người học chăm không gặp lại câu cũ trong một tuần** — cùng tinh thần với
   ngưỡng mà ADR-003 §3.3 viết ra để mở khoá RAG. Lát 4 vì thế **chờ nội dung**,
   không chờ code.

---

## 9. Cố ý KHÔNG làm

- **Không thông báo đẩy, không chấm đỏ tích luỹ.** Xem §1; đây là điều kiện tồn
  tại của cả tính năng.
- **Không phạt vì bỏ lỡ.** Không mất ruby, không tụt chỉ số, không "kẻ xâm nhập
  phá chuồng". Xem §4.
- **Không có bảng xếp hạng, không so với người khác.** Nó biến việc học thành
  một cuộc đua, và người thua cuộc đua đó sẽ thôi học.
- **Không đếm nhiệm vụ vào chuỗi ngày hay việc hôm nay.** Ba hệ đo cùng một hành
  động là ba chỗ để lệch; nhiệm vụ trả ruby, và lượt học bên trong nó đã tự chảy
  vào chuỗi ngày qua đường thật rồi.
