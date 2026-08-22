# USER-ROAD — Level, badge, khung avatar, XP và daily task

**Trạng thái:** 📋 **KẾ HOẠCH, chưa code** · lập 2026-08-21
**Phạm vi:** bốn thứ gắn với nhau thành một vòng: hoạt động → XP → level → badge + khung avatar, và daily task là thứ nói cho học viên biết hôm nay làm gì.

> Tài liệu này là **kế hoạch**, không phải bản ghi hiện trạng. Khi code xong, trạng thái đi về [`ROADMAP.md`](ROADMAP.md) như mọi thứ khác; phần lý do ở lại đây.

---

## 0. Bốn quyết định đã chốt

Hỏi và chốt trước khi viết, vì mỗi cái đổi hẳn hình dạng công việc:

| Quyết định | Chọn | Bị loại |
|---|---|---|
| Lưu XP | **Sổ cái `xp_event`**, mỗi hoạt động một hàng bất biến | Suy ra khi đọc; sổ cái + backfill |
| Daily task | **3 việc cố định, số liệu động** | Thay đổi theo người học; cố định hoàn toàn |
| Chống cày | **Trần XP mỗi ngày** | Chỉ tính lần đầu mỗi mục; chưa chống gì |
| Badge cũ | **Trao ngược theo lịch sử** | Mọi người bắt đầu từ đầu |

**Có một bất đối xứng cố ý ở đây, và nó sẽ thành câu hỏi của người dùng đầu tiên nhìn thấy:** XP bắt đầu từ 0 cho tất cả, còn badge thì tính cả quá khứ. Nên một người đã học 300 từ sẽ thấy badge "300 từ" ngay lập tức **nhưng vẫn ở level 1**. Điều đó nhất quán nếu hiểu đúng vai trò hai thứ — XP đo *hoạt động kể từ khi ra mắt*, badge ghi nhận *thành tựu trọn đời* — nhưng giao diện phải nói ra, nếu không nó đọc thành lỗi. Đảo lại được bằng một lần chạy backfill sinh `xp_event` từ lịch sử; quyết định đó để mở.

---

## 1. Nền: những gì đã có, đừng dựng lại

Ba sổ ghi hoạt động **đã tồn tại** và là nguồn duy nhất cần thiết:

| Bảng | Ghi cái gì | Có sẵn cột thời gian |
|---|---|---|
| `vocabulary_review_log` | mỗi lượt ôn SM-2, kèm grade 0–6 | `reviewed_at` |
| `dictation_attempt` | mỗi lần kiểm một câu, kèm `is_complete` | `created_at` |
| `attempt` | mỗi lượt làm đề, kèm `submitted_at` | `started_at`, `submitted_at` |

`app/services/profile_stats.py` **đã** suy ra chuỗi ngày, lưới hoạt động 365 ngày và số ngày hoạt động từ chính ba nguồn đó, **tính theo múi giờ của người học** (`user_profile.timezone`, NOT NULL vì đúng lý do này). Daily task và trần XP mỗi ngày phải dùng lại đúng định nghĩa "ngày" đó — định nghĩa thứ hai là chỗ chuỗi ngày và daily task nói hai điều khác nhau về cùng một hôm, và không ai báo.

---

## 2. XP — sổ cái, không phải bộ đếm

### 2.1 Vì sao là sổ cái

`profile_stats.py` mở đầu bằng luật của dự án: *"Không có bảng thống kê nào ở đây và không nên có... một bộ đếm ghi song song với lịch sử sẽ lệch khỏi lịch sử ngay lần đầu có một hàng bị xoá hoặc chấm lại, và không có gì phát hiện ra sự bất đồng đó."*

Một cột `user_profile.xp` cộng dồn **là** cái bộ đếm đó. Sổ cái thì không: mỗi hàng `xp_event` là một **sự kiện đã xảy ra**, bất biến, trỏ về nguyên nhân của nó. Level là `SUM` trên sổ cái — vẫn suy ra khi đọc, đúng luật.

Cái sổ cái mua thêm mà cách suy-ra-hoàn-toàn không có: **đổi công thức XP sau này không làm ai tụt level.** Nếu XP tính lại từ lịch sử mỗi lần đọc thì hạ giá một hoạt động là hạ level của tất cả những người đã làm nó — người dùng mất level mà không làm gì sai. Sổ cái ghi lại *số điểm đã trao lúc đó*, nên quá khứ đứng yên.

### 2.2 Bảng

```
xp_event
  id             uuid pk
  user_id        uuid  → users.id, ON DELETE CASCADE
  source_type    text  NOT NULL   -- 'vocabulary_review' | 'dictation_complete' | 'attempt_submit' | 'daily_task' | 'streak_bonus'
  source_id      uuid  NULL       -- hàng gốc, NULL cho nguồn không có hàng (streak)
  amount         int   NOT NULL   -- luôn > 0; không có XP âm, xem 2.5
  awarded_on     date  NOT NULL   -- NGÀY THEO MÚI GIỜ NGƯỜI HỌC, không phải UTC
  created_at     timestamptz NOT NULL default now()

  UNIQUE (user_id, source_type, source_id)   -- khi source_id NOT NULL
  INDEX (user_id, awarded_on)
```

**`UNIQUE (user_id, source_type, source_id)` là cột sống của thiết kế này**, không phải một ràng buộc phòng xa. Không có nó, một lần bấm hai lần, một request lặp lại, hay một job chạy lại là XP nhân đôi — và vì sổ cái bất biến, không có cách nào sửa ngoài việc xoá hàng, tức là phá chính thứ làm nó đáng tin. Ghi XP đi qua một `INSERT ... ON CONFLICT DO NOTHING`; trùng thì im lặng bỏ qua, không phải lỗi.

**`awarded_on` lưu ngày đã quy đổi, không lưu UTC rồi quy đổi lúc đọc.** Trần mỗi ngày và daily task đều hỏi "hôm nay được bao nhiêu", và quy đổi múi giờ trong `WHERE` của mỗi truy vấn là chỗ để lệch. Người học đổi múi giờ thì các hàng cũ giữ nguyên ngày cũ — đúng: chúng đã xảy ra trong ngày đó, ở nơi đó.

### 2.3 Nguồn XP và mức điểm

Mức hiệu chỉnh theo **nhịp thật đo được**, không theo cảm giác: trung vị **2 lượt ôn mỗi ngày hoạt động**, p90 là **4**, cao nhất từng thấy 33. Một thang cho rằng người ta ôn 50 từ/ngày sẽ khiến level 2 là thứ không ai với tới.

| Nguồn | XP | Ghi chú |
|---|---|---|
| `vocabulary_review` | **2** | mỗi lượt ôn, mọi grade. Trả lời sai vẫn được điểm — xem 2.5 |
| `dictation_complete` | **5** | chỉ khi `is_complete`, tức đúng trọn câu. Lần kiểm hỏng không tính |
| `attempt_submit` | **30** | mỗi lượt làm đề **đã nộp**. Bỏ dở không tính |
| `daily_task` | **10** mỗi việc | ba việc, tối đa 30/ngày |
| `streak_bonus` | **5 × min(chuỗi, 10)** | trao một lần mỗi ngày, tối đa 50. **Chưa dựng ở lát 1** |

### 2.4 Trần mỗi ngày

**120 XP/ngày.** Một ngày học chăm theo p90 (4 lượt ôn = 8, một câu dictation = 5, ba daily task = 30) là **43 XP**; cộng một lượt làm đề là **73**. Trần 120 để chỗ cho một ngày dày đặc mà vẫn chặn được việc chơi minigame liên tục.

Trần **cắt phần vượt** chứ không bỏ cả lần trao: còn 3 điểm mà hoạt động đáng 5 thì trao 3. Người dùng thấy thanh nhích chậm dần rồi dừng, thay vì thấy nó đứng khựng giữa chừng.

Ba tính chất phải giữ:

- **Vượt trần thì hoạt động vẫn ghi bình thường, chỉ không sinh `xp_event`.** SM-2, tiến độ dictation, lượt làm đề không bao giờ bị ảnh hưởng bởi luật gamification. Học vẫn là học.
- **Trần cưỡng chế lúc GHI, không lúc đọc.** Sổ cái phải nói đúng số điểm đã trao; nếu cưỡng chế lúc đọc thì trần trở thành một công thức, và đổi trần sẽ đổi cả quá khứ — mất đúng cái lợi ở 2.1.
- **Giao diện phải nói khi đã chạm trần**, nếu không người dùng học tiếp và tưởng hệ thống hỏng. Một dòng "hôm nay đã đạt tối đa 120 XP" là đủ.

**Vì sao cần trần:** hai minigame từ vựng **ghi lượt ôn SM-2 thật** (ROADMAP §4u — đó là điểm mạnh của chúng, tiến độ nhích lên thật). Nhưng nó cũng có nghĩa chơi lại một chủ đề là cày XP được, và không có trần thì con đường tối ưu để lên level là chơi game chứ không phải học.

### 2.5 Sai vẫn được điểm, và đó là chủ ý

`vocabulary_review` trao XP cho **mọi** grade, kể cả grade 0. Thưởng theo độ đúng nghe công bằng hơn nhưng tạo ra một khuyến khích tồi: nó trả tiền cho việc **tránh những từ khó**. SM-2 vốn đã phạt câu sai bằng cách bắt gặp lại sớm hơn — đó là hậu quả đúng và đã đủ. XP ở đây đo *đã xuất hiện và đã học*, không đo *đã giỏi*; badge và level không thay được vai trò của điểm số bài thi.

Không có XP âm và không có đường trừ XP. Một hệ có thể tụt là hệ mà người dùng sợ dùng.

---

## 3. Level

### 3.1 Đường cong

Ngưỡng tích luỹ, tăng dần nhưng **không tăng mãi** — sau level 20 mỗi level cách nhau một khoảng cố định, để người học lâu năm vẫn thấy nhích:

```
XP cần để lên level n  =  15 · n^1.45      (n ≤ 20)
                          tuyến tính +90   (n > 20)
```

> **Bộ này đã hạ xuống ngày 2026-08-22** (ROADMAP §4w). Bản đầu là `50 · n^1.6`
> với bậc tuyến tính 500, và nó được đặt cạnh giả định "~50 XP mỗi ngày" — trong
> khi nhịp ĐO ĐƯỢC là trung vị 2 lượt ôn/ngày, tức khoảng 14 XP kể cả khi làm
> xong một daily task. Ở nhịp đó, level 2 mất 11 ngày và level 10 mất gần năm
> tháng: phần thưởng đầu tiên rơi vào lúc người ta đã quyết định xong là có quay
> lại hay không.

| Level | XP tích luỹ | Nhịp nhẹ (~14 XP/ngày) | Nhịp chăm (~43 XP/ngày) |
|---|---|---|---|
| 2 | 40 | 3 ngày | 1 ngày |
| 5 | 154 | 11 ngày | 4 ngày |
| 10 | 422 | 30 ngày | 10 ngày |
| 20 | 1 155 | 82 ngày | 27 ngày |
| 30 | 2 055 | 5 tháng | 7 tuần |
| 50 | 3 855 | 9 tháng | 3 tháng |

**Bậc tuyến tính phải tính lại MỖI LẦN đổi hệ số hoặc số mũ** — với bộ hiện tại, bậc 19→20 là **83**, nên tuyến tính đặt 90. Bản đầu của kế hoạch ghi 1800 cho đường cong cũ trong khi bậc thật ở đó là **476**: sai gần bốn lần. Test `test_level_curve_is_monotonic_and_joins_without_a_step` bắt được ngay khi code chạy, và nó vẫn canh chỗ nối sau mỗi lần chỉnh. Một bậc đột ngột đắt gấp bốn ngay tại điểm gãy đọc ra là lỗi tính toán, và nó rơi đúng vào người học đã đi được xa nhất.

Đường cong là **một hàm thuần trong `app/services/leveling.py`**, cùng loại với `srs.py`: không chạm cơ sở dữ liệu, test được không cần session, và là chỗ duy nhất biết công thức.

### 3.2 Level là suy ra, luôn luôn

Không có cột `level`. `level_from_xp(total_xp)` và `total_xp = SUM(xp_event.amount)`. Cột level là bộ đếm thứ hai, với đúng vấn đề ở 2.1 và thêm một cái nữa: nó có thể lệch khỏi XP mà không có gì đối chiếu.

---

## 4. Badge

### 4.1 Suy ra từ lịch sử, không cần backfill

Badge **không** đọc `xp_event`. Chúng đọc thẳng lịch sử học — và vì thế "trao ngược theo lịch sử" không cần một lần chạy backfill nào: badge đúng theo định nghĩa ngay lần đọc đầu tiên.

| Mã | Điều kiện | Nguồn |
|---|---|---|
| `first_steps` | lượt ôn đầu tiên | `vocabulary_review_log` |
| `words_50` / `words_150` / `words_300` | số từ **đã thuộc** | `mastery()` trên `vocabulary_review_state` |
| `dictation_10` / `dictation_50` | số câu `is_complete` riêng biệt | `dictation_attempt` |
| `first_test` | nộp đề đầu tiên | `attempt.submitted_at` |
| `test_700` / `test_850` | điểm quy đổi cao nhất | `attempt.scaled_score` |
| `streak_7` / `streak_30` / `streak_100` | chuỗi ngày **dài nhất** | `compute_streaks` đã có |
| `level_5` / `level_10` / `level_20` | level hiện tại | `xp_event` |

Ba badge cuối là ngoại lệ có chủ ý: chúng đọc XP, nên với tài khoản cũ chúng sẽ mở muộn hơn phần còn lại. Đó chính là bất đối xứng ở mục 0, hiện ra ở chỗ dễ thấy nhất.

**Dùng `longest_streak` chứ không `current_streak`.** Một badge đã đạt rồi biến mất vì hôm nay nghỉ là hình phạt cho việc nghỉ một ngày, và nó dạy người dùng rằng hệ thống lấy lại thứ đã cho.

### 4.2 Bảng `user_badge` — chỉ để biết "cái nào chưa xem"

```
user_badge
  user_id     uuid  → users.id, ON DELETE CASCADE
  code        text
  awarded_at  timestamptz NOT NULL default now()
  seen_at     timestamptz NULL
  PRIMARY KEY (user_id, code)
```

Bảng này **không** quyết định badge có hay không — điều kiện ở 4.1 mới quyết định. Nó chỉ giữ hai thứ mà lịch sử không tự nói được: **lần đầu hệ thống nhìn thấy** badge này, và **người dùng đã xem thông báo chưa**. Không có nó thì không có thông báo "bạn vừa mở badge mới", vì mỗi lần đọc trang badge nào cũng "mới".

Ghi lười: mỗi lần tính badge, cái nào đủ điều kiện mà chưa có hàng thì `INSERT ... ON CONFLICT DO NOTHING`. Với tài khoản cũ, lần đọc đầu tiên sau khi ra mắt sẽ trao một loạt cùng lúc — giao diện nên gộp thành một thông báo, không phải mười.

---

## 5. Khung avatar

Khung mở theo level, thuần trang trí, không ảnh hưởng gì tới học.

| Level | Khung | Hình thức |
|---|---|---|
| 1–4 | không | viền `rule-strong` như hiện tại |
| 5–9 | Đồng | viền 2px `--ok` |
| 10–19 | Bạc | viền 2px `--action` |
| 20–29 | Vàng | viền 2px `--warn` + góc cắt |
| 30+ | Bậc thầy | viền 2px `--action` + vòng ngoài `--action-tint` |

**Ba ràng buộc từ design system, cả ba đều hỏng im lặng nếu bỏ qua:**

- **Không `box-shadow`.** Cám dỗ lớn nhất của "khung phát sáng" là đổ bóng. Luật là viền và màu nền, không bóng. Ngoại lệ duy nhất đã có tên là `shadow-overlay` cho lớp phủ thật.
- **Một bán kính 4px.** Thang Tailwind đã bị thay, nên `rounded-full` cho avatar tròn phải kiểm lại chứ đừng giả định.
- **Không đặt màu mới.** Bảng trên chỉ dùng token đã có (`ok`, `action`, `warn`, `action-tint`). Và **không dùng thang bốn accent** `--accent-{us,uk,au,ca}`: nó là thang *phân loại cho giọng đọc*, mượn sang bậc level là làm một màu mang hai nghĩa.

`Avatar` trong `src/components/ui.tsx` nhận thêm một prop `frame?: FrameTier`, mặc định không có. Component đó dùng ở nav và shell, nên đổi chữ ký phải giữ mọi chỗ gọi cũ chạy được.

---

## 6. Daily task

### 6.1 Ba khe cố định

Luôn đúng ba dòng, luôn cùng thứ tự, mỗi ngày. Người học mở lên là biết hôm nay làm gì mà không phải chọn.

| Khe | Việc | Mục tiêu |
|---|---|---|
| 1 | Ôn từ vựng | `min(10, số từ đến hạn)`, tối thiểu 5 nếu có từ chưa học |
| 2 | Dictation | 3 câu đúng trọn |
| 3 | Luyện đề | 10 câu trả lời trong một lượt làm đề bất kỳ |

### 6.2 Cái bẫy: mục tiêu không được di chuyển

Mục tiêu "ôn hết số từ đến hạn" nghe đúng nhưng **hỏng theo kiểu không ai báo**: số từ đến hạn **giảm dần khi bạn ôn**, nên thanh tiến độ chạy tới rồi lùi lại, và với một số lịch SM-2 thì nhiệm vụ không bao giờ đóng được.

Nên mục tiêu là **một số cố định được kẹp bởi tình trạng**, không phải chính tình trạng: *"ôn 10 từ"*, kẹp xuống nếu có ít hơn 10 từ khả dụng. Con số động ở đây là **cái kẹp**, không phải cái đích. Tiến độ đếm hoạt động **trong ngày hôm đó**, luôn tăng.

### 6.3 Không có bảng daily task

Trạng thái ba việc suy ra từ hoạt động trong ngày, giống mọi thứ khác trong dự án này:

- khe 1: `COUNT(vocabulary_review_log)` hôm nay
- khe 2: `COUNT(DISTINCT item_id WHERE is_complete)` hôm nay
- khe 3: `COUNT(attempt_item đã trả lời)` hôm nay

Thứ **duy nhất** cần ghi là XP thưởng khi hoàn thành, và nó đã có chỗ: một hàng `xp_event` với `source_type='daily_task'`, `source_id` là uuid tất định sinh từ `(user_id, ngày, khe)` — nhờ đó `UNIQUE` ở 2.2 tự lo việc không trao hai lần, không cần bảng nào khác.

### 6.4 Đặt ở đâu

Đầu `/dashboard`, **trên** khối từ vựng hiện có. Đó là trang đích sau khi đăng nhập, và mục tiêu của tính năng này đúng là "mở lên, biết làm gì". Nếu ba việc đã xong hết thì khối thu lại thành một dòng, không biến mất — biến mất làm người ta tưởng hỏng.

---

## 7. Bề mặt API

| Endpoint | Trả về |
|---|---|
| `GET /api/v1/progression` | `{ xp_total, level, xp_into_level, xp_for_next, frame_tier, xp_today, daily_cap }` |
| `GET /api/v1/progression/badges` | danh sách badge kèm `earned`, `awarded_at`, `seen` |
| `POST /api/v1/progression/badges/seen` | đánh dấu đã xem, tắt chấm đỏ |
| `GET /api/v1/daily-tasks` | ba khe kèm `target`, `progress`, `done`, `xp` |

Ghi XP **không** có endpoint riêng. Nó xảy ra bên trong các đường ghi đã tồn tại (`/vocabulary-review/review`, `/dictation/{id}/attempt`, `/attempts/{id}/submit`) qua một hàm dùng chung ở `app/services/progression.py`. Một endpoint "cộng XP cho tôi" là một endpoint người ta gọi thẳng.

---

## 8. Thứ tự làm

Bốn lát, mỗi lát tự nó chạy được và kiểm được. **Cả bốn đã dựng xong** (ROADMAP §4v, §4x); chỉ còn `streak_bonus` ở §2.3. Khung và huy hiệu ngoài token màu còn **gắn được tranh riêng**, tải lên trong `/admin/progression`.

> **Mọi con số trong tài liệu này giờ là CẤU HÌNH, không phải hằng số** (ROADMAP §4w). Mức XP, trần ngày, đường cong level, ba khe daily task, bậc khung và luật badge đều là hàng trong database, sửa ở `/admin/progression`. Các con số viết ở đây là **bộ mặc định** và lý do chọn chúng — vẫn đáng đọc, vì đó là điểm xuất phát và là lập luận đằng sau. Nhưng đừng đọc chúng như thứ đang chạy: hỏi database.

1. **Sổ cái + level** — migration `xp_event`, `leveling.py` thuần, gắn ghi XP vào ba đường ghi, `GET /progression`. Chưa có giao diện gì ngoài một con số.
2. **Daily task** — `GET /daily-tasks`, khối trên dashboard, XP thưởng. Đây là lát mang lại giá trị người dùng lớn nhất và **nên làm sớm**, không để cuối.
3. **Badge** — điều kiện suy ra, bảng `user_badge` cho trạng thái đã xem, trang badge.
4. **Khung avatar** — prop `frame` trên `Avatar`, năm bậc.

---

## 9. Cố ý KHÔNG làm

- **Không bảng xếp hạng.** Một người học TOEIC cạnh tranh với người lạ là cạnh tranh sai đối tượng, và nó thưởng cho người rảnh chứ không cho người tiến bộ.
- **Không chuỗi ngày "mua lại được".** Chuỗi ngày là số đo, không phải tiền tệ.
- **Không XP cho việc đăng nhập.** Nó trả tiền cho việc mở trang, và đó đúng là thứ làm giao diện đầy nút giả.
- **Không gamification ở màn làm bài.** Cùng lý do Petland vắng mặt ở đó: thứ nhảy nhót cạnh người đang tính giờ là cạnh tranh trực tiếp với sự tập trung.

---

## 10. Kiểm

- `leveling.py` thuần → test bảng giá trị, gồm cả ranh giới level và chỗ đường cong chuyển sang tuyến tính.
- **Trần XP**: test rằng hoạt động vượt trần **vẫn ghi SM-2 bình thường** mà không sinh `xp_event`. Đây là phần dễ hỏng nhất và hỏng theo hướng tệ nhất.
- **Chống trao hai lần**: gọi cùng một đường ghi hai lần, khẳng định đúng một hàng `xp_event`.
- **Múi giờ**: một người ở `Asia/Ho_Chi_Minh` hoạt động lúc 23:00 giờ địa phương phải rơi vào ngày địa phương, không phải ngày UTC. Cùng bẫy `compute_streaks` đã xử lý.
- **Mục tiêu không lùi**: test rằng tiến độ khe 1 không giảm khi số từ đến hạn giảm.
- E2E: một tài khoản mới thấy ba việc, làm xong một việc, thấy XP tăng và việc đó đóng lại — rồi **nạp lại trang** và nó vẫn đóng.
- Đếm thống kê người dùng phải lọc `email !~ '[0-9]{13}'`: 541 trong 574 tài khoản là do e2e tự đăng ký.
