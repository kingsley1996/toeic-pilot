# Trang phân tích kết quả bài thi — cần gì để dựng thật

> **LƯU TRỮ.** Tệp này được ghim theo commit nó được viết và **không cập nhật**.
> Giữ lại vì lý do đằng sau vẫn đọc được, không phải vì nội dung còn đúng.
> Trạng thái thật: `planning/docs/ROADMAP.md`. Hành vi hiện tại: xem chỉ mục ở `CLAUDE.md`.

> Bản KẾ HOẠCH cho màn kết quả, nay đã dựng.

**Trạng thái:** 📋 KẾ HOẠCH, chưa code · lập 2026-08-23
**Phạm vi:** biến `/preview/attempt-result` từ một trang xem trước thành màn kết quả thật của một lượt làm bài.
**Đối chiếu:** bản preview đã được nạp **số đo thật** của lượt `f21ba732` (đề `tp-form-06`, 200 câu, 730 điểm), nên mọi khoảng trống nêu dưới đây là thứ đã thử dựng và không dựng được, chứ không phải phỏng đoán.

> Tài liệu này là **kế hoạch**. Khi code xong, trạng thái đi về [`ROADMAP.md`](../docs/ROADMAP.md); phần lý do ở lại đây.

---

## 0. Bốn con số đo được, trước khi bàn tới thiết kế

Đo trên database dev ngày 2026-08-23. Mỗi con số đều đổi một quyết định thiết kế, nên chúng đứng trước.

| Đo | Giá trị | Hệ quả |
|---|---|---|
| Lượt đã nộp trên toàn hệ | **12** | Mọi khối "so với lần trước" gần như không có dữ liệu để vẽ. |
| Tài khoản đã nộp ít nhất một lượt | **7**, trong đó **5** chỉ có đúng một lượt | Lớp nét đứt của lục giác là ngoại lệ, không phải mặc định. |
| Hồ sơ có `target_score` | **5 / 821** | Cột "Mục tiêu" và vạch mục tiêu trên đồng hồ trống với 99,4% tài khoản. |
| Hàng `coach_explanation` đã sinh | **0** | Khối "Trợ giảng nhận xét" là tính năng mới, không phải tái dùng thứ đang chạy. |

Đọc bảng này theo đúng cách `ADR-003` §0 đọc `target_score`: **cái gì chưa có dữ liệu thì chưa dựng được, dù thiết kế đã vẽ ra rồi.** Thứ tự làm ở §4 đi thẳng từ đây — dựng trước những khối chỉ cần **một** lượt và **không** cần mục tiêu.

---

## 1. Thứ đã có sẵn — đừng dựng lại

Đây là phần dễ bị đánh giá nhầm nhất: nhìn bản preview thì tưởng cần một API thống kê mới, nhưng phần lớn số liệu **đã nằm trong phản hồi hiện tại**.

`GET /api/v1/attempts/{id}` sau khi nộp trả về `AttemptState`, và mỗi câu trong đó mang đủ:

- `number` — số thứ tự trong đề, nên **bản đồ 200 ô dựng được ngay**, đúng thứ tự câu.
- `selected_option_id` và `correct_option_id` — `correct_option_id` chỉ lộ ở chế độ Luyện tập hoặc **sau khi nộp**, và đã kiểm: cả 200/200 câu đều có. Suy ra được đúng / sai / bỏ trống cho từng câu.
- `part` — nên bảng từng phần dựng được, và `ResultScreen` hiện tại **đã** tính đúng/tổng theo part kiểu này rồi.
- `set_id` + `passages` — `passages` là một mảng, đếm độ dài là ra số văn bản của cụm. Trên `tp-form-06`: 15 cụm Part 7 = 10 cụm một văn bản, 2 cụm hai, 3 cụm ba. **Trục "đoạn đơn / đoạn kép" của lục giác dựng được mà không cần nhãn kỹ năng.**

Thêm vào đó:

- `time_limit_seconds` và `elapsed_seconds` nằm sẵn trong `AttemptState` → ô "107/120 phút" là số thật.
- `target_score` nằm trong **phiên đăng nhập** (`user.profile.target_score`, xem `UserProfilePublic`) → không cần gọi thêm `/profile`.
- `GET /attempts/{id}/result` cho điểm quy đổi và `scale_note`.

**Kết luận của §1:** đồng hồ điểm, bảng từng phần, bản đồ 200 câu và cả sáu trục của lục giác (lớp nét liền) đều dựng được **hôm nay**, không cần đụng tới backend. Cái phải trả giá nằm ở §2.1.

### 1b. Một cái bẫy: đừng lấy nhãn kỹ năng để tách đoạn đơn / đoạn kép

Taxonomy có sẵn `PART_7_SINGLE_PASSAGE` và `PART_7_MULTIPLE_PASSAGE`, nên phản xạ đầu tiên là đọc `question_set_label`. Đo thử thì:

```
PART_7_SINGLE_PASSAGE · thực tế nhiều đoạn = false → 13
PART_7_SINGLE_PASSAGE · thực tế nhiều đoạn = true  →  3
PART_7_MULTIPLE_PASSAGE                            →  0
```

**Ba cụm bị gán "một đoạn" trong khi chúng có 2–3 văn bản, và mã "nhiều đoạn" chưa từng được gán cho bất kỳ cụm nào.** Nhãn ở đây sai một cách im lặng, còn `passage_2 / passage_3` thì luôn đúng vì nó *là* nội dung. Dùng cột, không dùng nhãn.

Điều này cũng đặt giới hạn cho hướng "chuyển lục giác sang các facet của taxonomy" mà `AI-ENGINEERING-PLAN` §9b mong muốn: hiện `question_label` mới có **232** hàng `question_type` và **49** hàng `grammar` — 2 trong 6 facet — và với 72 mã trên một part 54 câu thì phần lớn ô sẽ là n=1. Sáu trục theo **nhóm part** là lựa chọn đúng cho lúc này, không phải giải pháp tạm.

---

## 2. Thứ còn thiếu, xếp theo giá phải trả

### 2.1 Tải trọng: 238 KB cho một trang toàn thanh và ô vuông

Đo thật trên lượt 200 câu:

| Endpoint | Kích thước |
|---|---|
| `GET /attempts/{id}` (`AttemptState`) | **243 562 byte ≈ 238 KB** |
| `GET /attempts/{id}/result` | **247 byte** |

238 KB là toàn bộ đề: ngữ liệu Part 6–7, bốn phương án mỗi câu, URL audio, ảnh, lời giải thích. Không sao khi màn kết quả là **phần đuôi của lượt vừa làm** — dữ liệu đã nằm sẵn trong bộ nhớ trình duyệt. Nhưng nó hỏng ở hai chỗ:

- **Mở lại kết quả từ lịch sử** (`/learn/attempts` → bấm vào một lượt) phải tải lại 238 KB chỉ để vẽ mấy cái thanh.
- **Lớp so sánh** ở §2.2 cần N lượt trước → N × 238 KB. Với ba lượt là hơn 700 KB cho một lớp nét đứt.

Cần một endpoint **gọn**, ví dụ `GET /attempts/{id}/breakdown`, trả về mảng `{number, part, set_id, passage_count, outcome}` với `outcome ∈ {correct, wrong, blank}` — vài KB thay vì vài trăm. Hai ràng buộc bắt buộc:

- **Cùng một cổng như `_state`**: không được lộ kết quả từng câu của một lượt **chưa nộp**, vì đó chính là đáp án. `coach.py` đã có `_owned_submitted_attempt`, dùng lại.
- **Trả mảng trần, không bọc `Page[T]`**: số câu của một đề có trần cứng (200) nên nó thuộc nhóm (A) trong `app/schemas/common.py`. Bọc phân trang là bắt frontend xử lý một trường hợp không thể xảy ra.

Có endpoint này rồi thì màn kết quả tách hẳn khỏi màn làm bài, và cái nút "Xem chi tiết từng câu" mới là chỗ tải 238 KB — đúng lúc người dùng thật sự cần đọc đề.

### 2.2 Lớp so sánh — câu hỏi cần trả lời trước khi code

Lớp nét đứt trên lục giác cần đúng/tổng theo part của **các lượt trước**. `AttemptSummary` cố ý không mang danh sách câu (một trang lịch sử vài chục lượt × 200 câu là vài MB), nên phải gọi `breakdown` cho từng lượt cũ, hoặc thêm một endpoint trả thẳng đường cơ sở.

Hai quyết định phải chốt trước, vì chọn sai thì con số vẫn hiện ra và vẫn sai:

- **So với lượt nào?** Cùng một đề, hay N lượt gần nhất bất kể đề? So ngang qua hai đề khác nhau là đo **độ khó của đề** ngang với đo tiến bộ của người học. Đề xuất: **cùng `test_slug`, ba lượt gần nhất**, và nói ra ngay trên nhãn chú thích. Bản preview ghi "trung bình 2 lượt trước" mà không nói *của cái gì* — chính là chỗ mập mờ này.
- **Chỉ có một lượt thì trông ra sao?** Đây là trường hợp **thường gặp**: trong 7 tài khoản từng nộp bài, **5 tài khoản chỉ có đúng một lượt** — không có gì để so. Cần một hình dạng được thiết kế cho "chưa có gì để so", không phải đơn giản ẩn lớp nét đứt đi rồi để phần chú thích nói về một thứ không hiện ra.

### 2.3 Tốc độ làm bài — đây là sửa lược đồ, không phải sửa giao diện

Khối "Tốc độ làm phần Đọc" trong bản mẫu vẽ bốn thanh "giây mỗi câu so với mục tiêu". **Không con số nào trong đó dựng lại được**, và lý do nằm ở hai chỗ:

- `attempt_item.answered_at` **bị ghi đè mỗi lần đổi đáp án** (`save_answer` gán `datetime.now(UTC)` ở mọi lượt lưu). Nó trả lời "lần cuối chạm vào câu này là lúc nào", không phải "câu này tốn bao lâu" — và một lần đổi ý là mất luôn dấu vết lần đầu.
- `attempt_part` chỉ có `(attempt_id, part)`. Nó trả lời "lượt này gồm những part nào", không phải "ở part này bao lâu".

Hai đường đi, và nên chọn (a):

**(a) Đồng hồ theo part** — thêm `attempt_part.elapsed_seconds`, cộng dồn khi người làm chuyển part. Một cột, và nó đúng bằng thứ khối này cần hiển thị. Phải dùng lại đúng cách `attempt.elapsed_seconds` đang xử lý tạm dừng: cộng dồn qua các lần nghỉ chứ **không** suy ra từ `now() - started_at`, nếu không một tab để mở qua đêm sẽ báo Part 7 mất chín tiếng.

**(b) Mốc trả lời lần đầu** — thêm `attempt_item.first_answered_at`, chỉ ghi một lần. Cho phép tính "giây mỗi câu", nhưng nhiễu (người ta nhảy qua nhảy lại giữa các câu) và tốn 200 lượt ghi thêm mỗi lượt làm bài.

Trước khi có (a), **khối này không được tồn tại**. Bản preview từng in "vượt mục tiêu 20 giây" cho một con số chưa ai đo — một câu chữ trông như kết quả đo và không phải.

### 2.4 Nhận xét của trợ giảng — cùng một mô hình, khác hẳn hình dạng chi phí

`coach.py` hiện có: giải thích **một câu** (`POST /coach/{attempt_id}/items/{question_id}/coach`) và hỏi đáp (`/chat`), cả hai đứng sau `rate_limit(..., fail_open=False)` theo `ADR-003` §3.4.

Nhận xét cả bài **không** tái dùng được đường đó, vì hai thứ khác nhau ở chỗ quan trọng nhất:

- Giải thích một câu **giống nhau với mọi người học** → cache được vào `coach_explanation`, chi phí hội tụ về 0 (`AI-ENGINEERING-PLAN` §3).
- Nhận xét một lượt làm bài **riêng cho lượt đó** → không chia sẻ được, không tiền tính được, mỗi lần sinh là một lần trả tiền.

Nên nó cần: hạn mức riêng, khoá cache riêng theo `attempt_id`, và **sinh khi người dùng mở trang chứ không sinh lúc nộp bài** — nếu sinh lúc nộp thì mọi lượt đều trả tiền cho một trang có thể không ai mở. Lưu vào **bảng riêng**, đừng nhét vào `coach_explanation` với `question_id` nullable: một khoá rõ ràng bị biến thành hai hình dạng là cách chắc chắn nhất để sau này không ai biết đếm cái gì.

Và nhớ con số ở §0: **0 hàng `coach_explanation`** — cả đường trợ giảng chưa từng chạy thật lần nào.

### 2.5 Mục tiêu điểm — 5 trên 821 hồ sơ

Cột "Mục tiêu" và vạch mục tiêu trên đồng hồ cần `target_score`. Cần **ba** trạng thái, không phải một:

- **Chưa đặt** (99,4% tài khoản): không vẽ vạch trên cung, và ô bên phải trở thành lời mời đặt mục tiêu, dẫn sang `/profile`. Đây là trạng thái mặc định, nên nó phải là trạng thái được thiết kế kỹ nhất — không phải một ô trống.
- **Chưa đạt**: còn thiếu N điểm.
- **Đã đạt**: bản mẫu không hề có nhánh này, vì số bịa (742) luôn thấp hơn mục tiêu bịa (800). Lượt thật đầu tiên chạy qua là 730/700 → **đã vượt**, và thứ sẽ hiện ra nếu không ai nghĩ tới nhánh này là "còn thiếu −30 điểm".

### 2.6 Lượt không có điểm quy đổi

`scoring.py` **từ chối đoán**, nên `total_scaled` là `NULL` bất cứ khi nào không tra được bảng, và `scale_note` nói lý do. Đo thật: **5 trong 13 lượt đã nộp/hết giờ không có điểm quy đổi** — tất cả đều là lượt trên `toeic-2024-test-1`, một đề mới có 34 câu đã xuất bản. Đề rút gọn và lượt làm một phần cũng rơi vào nhóm này.

Bản preview giả định mọi lượt đều là 200 câu có điểm. Bản thật cần:

- Đồng hồ điểm **không vẽ** khi không có điểm, chứ không vẽ số 0 — 0 là một điểm số, `NULL` là "không tra được", và in nhầm thì người học tin vào một con số sai vĩnh viễn nằm trên lượt của mình.
- Chỗ đứng cho `scale_note`. Bản preview không có ô nào cho nó; `ResultScreen` hiện tại thì có.
- Lượt `scope='partial'`: không có điểm, và lục giác chỉ có vài trục — cần hình dạng riêng hay ẩn hẳn khối đó.

---

## 3. Bốn lỗi bản preview đã mắc — bản thật đừng lặp lại

Ghi lại vì cả bốn đều **xanh** cho tới khi số thật chạy qua.

1. **Hai nguồn cho cùng một sự thật.** Bảng từng part khai số câu đúng riêng, bản đồ 200 ô khai riêng, không gì bắt chúng khớp. Lúc dựng trang chúng **đã lệch thật**: bảng ghi Part 4 là 24 câu đúng trong khi bản đồ đếm 23. Cả hai đều trông hợp lý, và không ai đếm tay 200 ô vuông. Bản thật chỉ có **một** danh sách kết quả từng câu; mọi con số cắt ra từ đó.
2. **Khung SVG vừa khít dữ liệu mẫu.** Lục giác cắt mất nhãn khi một trục chạm 100% — dữ liệu bịa không có trục nào chạm trần. Vạch mục tiêu 700 rơi *trên* cung chứ không ngoài rìa như mốc 800, nên nhãn đè lên nét vẽ. Khung phải chừa chỗ cho **nhãn**, không phải cho hình.
3. **Lời nhận xét chọn bằng `axis.sub === "Đoạn kép"`.** Số thật cho ra một cặp điểm yếu khác, mà câu nhận xét vẫn nói về đoạn kép — và nói về một mốc thời gian hệ thống không hề đo. Nhận xét phải là **dữ liệu đi kèm con số**, hoặc do máy sinh, không phải chuỗi viết cứng chọn theo tên trục.
4. **Con số nhỏ mang dáng vẻ kết luận.** Trục "đoạn kép" của lượt thật là 73% so với "đoạn đơn" 64% — nhìn như một phát hiện, thực ra là **11/15 câu**, nhiễu thuần tuý. Trục nào có ít câu thì phải nói ra số câu, nếu không giao diện đang mời người học sửa một thứ không hỏng.

---

## 4. Thứ tự làm

Mỗi bước tự nó dùng được, và không bước nào chờ bước sau.

1. **`GET /attempts/{id}/breakdown` + dựng lại màn kết quả trên nó.** Đồng hồ điểm (chưa có vạch mục tiêu), bảng từng part, bản đồ 200 câu, lục giác lớp nét liền. Chạy được với **một** lượt và **không** cần mục tiêu — tức là với 5 trên 7 tài khoản đang có dữ liệu, và với 816 hồ sơ chưa đặt mục tiêu.
2. **Ô mục tiêu, đủ ba trạng thái** (§2.5), kèm lời mời đặt mục tiêu. Rẻ, và nó là thứ làm cho con số 5/821 bắt đầu tăng.
3. **Ô trên bản đồ bấm được**, nhảy thẳng tới câu đó trong màn xem lại. Đây là chỗ 238 KB xứng đáng được tải, và là thứ biến bản đồ từ trang trí thành đường đi.
4. **Lớp so sánh** (§2.2), sau khi đã chốt "so với lượt nào" và hình dạng lúc chỉ có một lượt.
5. **`attempt_part.elapsed_seconds` + khối tốc độ** (§2.3).
6. **Nhận xét trợ giảng** (§2.4), sau cùng: nó tốn tiền mỗi lần chạy, và nó là khối duy nhất mà một câu sai không lộ ra bằng cách nhìn.

---

## 5. Không làm

- **Không ship khối tốc độ bằng số ước lượng.** Không có mốc thời gian thì không có khối đó.
- **Không so điểm ngang qua hai đề khác nhau mà không nói rõ**, kể cả đường xu hướng trên trang lịch sử — chênh lệch giữa hai đề tự sinh có thể lớn hơn chênh lệch giữa hai lần thi của cùng một người.
- **Không dùng `question_label` cho lục giác** cho tới khi độ phủ đủ và số liệu ở §1b được sửa.
- **Không thêm `first_answered_at`** trước khi trả lời được "câu này tốn bao lâu" nghĩa là gì khi người làm quay lại câu đó ba lần.
- **Không sinh nhận xét trợ giảng lúc nộp bài.** Sinh khi mở trang, và cache theo `attempt_id`.
