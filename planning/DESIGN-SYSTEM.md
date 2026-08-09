# Design System — TOEIC Pilot

**Trạng thái:** đặc tả thiết kế · 2026-08-09
**Phạm vi:** toàn bộ `apps/web`. Đây là **nguồn sự thật cho giao diện** — token, kiểu chữ, icon, component, chuyển động.
**Chưa triển khai.** Tài liệu này mô tả hệ thống *sẽ* dựng; code hiện tại vẫn là hệ cũ. Mục 13 là danh sách di trú.

> Quy tắc chung: một quyết định về hình thức được ra **một lần** ở đây, không ra lại ở từng trang. Nếu bạn đang chọn màu hay bo góc trong một file `page.tsx`, bạn đang làm sai chỗ.

---

## 1. Hệ cũ sai ở đâu

Không phải sai kỹ thuật. Kiến trúc token của hệ cũ đúng: màu nằm ở CSS variable, sáng/tối là một định nghĩa, không có `dark:` rải khắp nơi. **Giữ nguyên kiến trúc đó.**

Vấn đề là **các giá trị**, và tất cả đều là giá trị mặc định của công cụ chứ không phải lựa chọn cho sản phẩm này:

| Hệ cũ | Đến từ đâu |
|---|---|
| `Geist` + `Geist_Mono` | Font mặc định của `create-next-app` |
| `--brand: 79 70 229` (indigo-600) | Bảng màu mặc định Tailwind |
| Thang xám `zinc` | Bảng màu mặc định Tailwind |
| `rounded-lg` / `rounded-xl` khắp nơi | Mặc định của mọi bản sao shadcn/ui |
| `shadow-sm` trên mọi bề mặt | Như trên |
| `hover:-translate-y-0.5` trên card | Như trên |
| 17 emoji làm icon ở 10 file | Không có bộ icon nào được chọn |

Ghép lại, kết quả là một dashboard SaaS không phân biệt được với bất kỳ dashboard SaaS nào khác. Với một sản phẩm mà người dùng phải quay lại **mỗi ngày trong nhiều tháng**, sự vô danh đó là một chi phí thật.

Ba hướng thoát mà tài liệu này **cố ý không đi**, vì chúng đã trở thành mặc định mới:

1. Nền kem `#F4F1EA` + serif tương phản cao + điểm nhấn terracotta
2. Nền đen tuyền + một màu neon acid duy nhất
3. Bố cục nhật báo: kẻ chỉ mảnh, bo góc bằng 0, cột dày đặc

---

## 2. Hướng thiết kế: **Calibration**

**Đối tượng:** người Việt đi làm hoặc sắp đi làm, cần một con số TOEIC cụ thể cho một mục đích cụ thể.
**Việc duy nhất của giao diện mỗi ngày:** đưa họ vào 20 phút luyện tập, rồi nói thật cho họ biết họ đang ở đâu.

Sản phẩm này không phải một app flashcard có thêm audio. Điều đặc trưng nhất về nó — đọc từ chính codebase, không phải từ brief — là **nó ám ảnh với sự chính xác**:

- Nó **từ chối xuất bản** một clip không còn khớp với text của nó (`app/services/media_state.py`).
- Nó chấm dictation **theo từng từ** bằng diff, không phải đúng/sai cả câu (`app/services/dictation.py`).
- Nó **từ chối đoán** khi thiếu bảng quy đổi điểm, thay vì nội suy — vì một điểm số sai âm thầm sẽ nằm vĩnh viễn trên bài làm (`app/services/scoring.py`).
- Nó lưu `interval_days` và `ease_factor` **tại thời điểm ôn**, để sau này chỉnh tham số còn đánh giá lại được.

Vậy nên: giao diện là **mặt đọc của một thiết bị đo**. Không phải máy đo skeuomorphic có núm vặn và vân kim loại — mà là sự chính xác: số liệu thẳng hàng, đơn vị luôn được ghi rõ, thang đo có vạch chia thật, và khi máy không đo được thì nó **nói là không đo được** chứ không hiện số 0.

**Vì sao không chọn hướng "phiếu trả lời trắc nghiệm"** (ô tròn A/B/C/D, bút chì 2B, vạch định vị). Đó là hình ảnh dễ nhận ra nhất của thế giới TOEIC, và là đề xuất hiển nhiên. Nhưng nó là hình ảnh của **kỳ thi**, mà kỳ thi là Sprint 5 — chưa dựng. Sản phẩm đang tồn tại hôm nay là một máy luyện nghe và nhớ từ. Thiết kế cho phần chưa có là thiết kế cho một sản phẩm khác.

### 2.1 Rủi ro đã chọn: màu hành động là **chu sa**, không phải xanh dương

Gần như mọi sản phẩm ed-tech dùng xanh dương làm màu chính. Xanh dương là màu của *thông tin* — nó lùi lại. Nhưng toàn bộ sản phẩm này phụ thuộc vào **một hành vi duy nhất: hôm nay có mở app ra không.** Màu của hành động phải tiến lên.

Chu sa (`#C2340F`) còn là màu của con dấu — dấu đóng lên một thứ để nói rằng nó đã xong và đã được duyệt. Trùng khít với hai khoảnh khắc quan trọng nhất của app: **cổng publish** ở phía admin, và **"xong bài hôm nay"** ở phía học viên.

**Rủi ro của nó, và cách khử.** Cam đỏ dễ bị đọc nhầm thành lỗi. Ba biện pháp, bắt buộc:

1. Màu lỗi là **`#A31220`** — đỏ thẫm ngả lạnh, tách bạch cả về sắc lẫn độ sáng khỏi chu sa. Không bao giờ dùng chung token.
2. **Lỗi không bao giờ chỉ dựa vào màu.** Mọi thông báo lỗi phải có icon + viền + nền nhạt. Xem §11.
3. Chu sa **bị cấm dùng làm màu phân loại dữ liệu** (§4). Thấy chu sa ở đâu thì ở đó có việc cần làm — không có ngoại lệ.

---

## 3. Token màu

Tất cả giá trị dưới đây **đã được kiểm bằng công thức tương phản WCAG 2.1**, không phải chọn bằng mắt. Cột cuối là tỉ số thật.

### 3.1 Sáng

| Token | Hex | Vai trò | Tương phản |
|---|---|---|---|
| `ground` | `#E9EDF0` | Nền trang. Xám ngả lạnh — **không** trắng, **không** kem | — |
| `panel` | `#FFFFFF` | Bề mặt nổi: card, bảng, popover | — |
| `recess` | `#DDE3E8` | Bề mặt chìm: header bảng, ô nhập vô hiệu hoá | — |
| `rule` | `#CBD4DB` | Kẻ chia trang trí, viền card | — |
| `rule-strong` | `#738999` | **Viền ô nhập / ranh giới component** | 3.09 / ground · 3.64 / panel |
| `ink` | `#0F171D` | Chữ chính | 15.37 / ground · 18.09 / panel |
| `ink-muted` | `#4A5964` | Chữ phụ, mô tả | 6.14 / ground · 7.23 / panel |
| `ink-faint` | `#5E6C77` | Nhãn siêu nhỏ, chú thích | 4.59 / ground · 5.40 / panel |
| `action` | `#C2340F` | **Hành động chính.** Chữ trắng ở trên | 5.54 (trắng trên nền này) |
| `action-hover` | `#A82B0B` | Trạng thái hover | — |
| `action-ink` | `#9A2709` | Chữ/link màu hành động | 7.87 / panel |
| `action-tint` | `#FCEDE8` | Nền nhạt của hành động | 6.90 (với `action-ink`) |
| `ok` | `#17694A` | Đúng, đã publish, hợp lệ | 6.65 / panel |
| `ok-tint` | `#E4F1EA` | | 5.73 (với `ok`) |
| `warn` | `#8A5A06` | Audio lệch, sắp hết hạn | 5.92 / panel |
| `warn-tint` | `#FBF0DC` | | 5.25 (với `warn`) |
| `alert` | `#A31220` | Lỗi, sai, từ chối | 7.88 / panel |
| `alert-tint` | `#FBE9EA` | | 6.73 (với `alert`) |

### 3.2 Tối

Không phải bản đảo của bảng sáng. Nền tối là **xanh đá đậm ngả lam**, không phải đen tuyền — đen tuyền cộng một màu neon là mặc định số 2 ở §1.

| Token | Hex | Tương phản |
|---|---|---|
| `ground` | `#0D1317` | — |
| `panel` | `#151D22` | — |
| `recess` | `#080C0F` | — |
| `rule` | `#243037` | — |
| `rule-strong` | `#576E7E` | 3.20 / panel · 3.51 / ground |
| `ink` | `#E8EEF2` | 14.58 / panel · 15.98 / ground |
| `ink-muted` | `#9AAAB5` | 7.14 / panel |
| `ink-faint` | `#798792` | 4.63 / panel |
| `action` | `#FF6B3D` | **chữ `#160B05` ở trên**, 6.85 |
| `action-hover` | `#FF8355` | — |
| `action-ink` | `#FF8A5F` | 7.36 / panel |
| `action-tint` | `#2A1109` | 7.66 (với `action-ink`) |
| `ok` | `#4BD69B` | 8.35 (với `ok-tint`) |
| `ok-tint` | `#0B2A1E` | — |
| `warn` | `#E8A93C` | 7.67 (với `warn-tint`) |
| `warn-tint` | `#2E2007` | — |
| `alert` | `#F87A82` | 6.58 / panel |
| `alert-tint` | `#2E0D10` | — |

> **Nút hành động ở chế độ tối dùng chữ tối, không phải chữ trắng.** Chữ trắng trên `#FF6B3D` chỉ đạt 2.83 — trượt cả ngưỡng 4.5 lẫn ngưỡng 3.0. Đây là lỗi rất hay gặp và nó không tự lộ ra ở chế độ sáng.

---

## 4. Thang phân loại bốn giọng — ràng buộc riêng của sản phẩm này

Đa số design system cần **một** màu thương hiệu. Sản phẩm này cần thêm một thứ hiếm: **một thang phân loại đúng bốn giá trị**, xuất hiện liên tục, và mang **dữ liệu** chứ không phải trang trí. Mỗi từ vựng đều có bốn clip: US, UK, AU, CA.

Ba ràng buộc, theo thứ tự ưu tiên:

1. **Không dùng màu cờ.** Đỏ-trắng-xanh cho US là câu trả lời hiển nhiên và nó sai: bốn lá cờ này dùng gần như cùng một bộ màu, nên chúng không phân biệt được với nhau.
2. **Phải phân biệt được khi chuyển sang thang xám**, cho người mù màu. Nên bốn màu được đặt trên một **bậc thang độ sáng**, không chỉ khác sắc.
3. **Không bao giờ là kênh thông tin duy nhất.** Nhãn hai chữ (`US` `UK` `AU` `CA`) luôn đi kèm. Màu là mã hoá dư thừa.

| Giọng | Sáng | Tối | Sắc |
|---|---|---|---|
| US | `#133965` | `#4187D6` | lam |
| UK | `#5F398B` | `#A57BD5` | tím |
| AU | `#0C6A5E` | `#31B9A6` | lục lam |
| CA | `#976906` | `#E4B95C` | hoàng thổ |

Bậc thang độ sáng — tỉ số giữa hai màu **liền kề** trên thang xám:

```
sáng:   US ──1.36x──> UK ──1.32x──> AU ──1.34x──> CA
tối:    US ──1.13x──> UK ──1.35x──> AU ──1.32x──> CA
```

Cả tám màu đều đạt ≥ 4.5 so với `panel`, nên dùng được cả làm nền chip lẫn làm chữ.

**Chu sa không có mặt ở đây, và không bao giờ được có mặt.** Nếu sau này cần giọng thứ năm, lấy sắc mới trên bậc thang — không lấy màu hành động.

---

## 5. Chữ

### 5.1 Ràng buộc đứng trước mọi ràng buộc khác: tiếng Việt

Giao diện này là tiếng Việt. Điều đó loại bỏ phần lớn các font "có cá tính" mà một design system thường chọn, và nó áp một luật mà thiết kế cho tiếng Anh không bao giờ gặp:

> **Tiếng Việt chồng hai dấu lên một nguyên âm.** `ế` `ộ` `ữ` `ậ` `ổ` mang cả dấu phụ âm sắc *và* dấu thanh. Chữ Việt cần **nhiều** khoảng đứng hơn chữ Anh, không phải ít hơn.

**Luật cứng: không có `line-height` nào dưới `1.25` ở bất cứ đâu, kể cả tiêu đề lớn.** Tiêu đề display trong thiết kế tiếng Anh thường đặt `1.0`–`1.1`; ở đây làm vậy sẽ cắt cụt dấu hoặc khiến hai dòng chạm nhau.

### 5.2 Ba vai trò

| Vai trò | Font | Vì sao |
|---|---|---|
| **Display** | `Archivo` | Grotesque công nghiệp, hơi hẹp, có trục variable độ rộng. Đọc như chữ trên bảng chỉ dẫn và bảng điều khiển — đúng hướng §2. Có subset `vietnamese`. |
| **Body** | `Be Vietnam Pro` | Được **thiết kế cho tiếng Việt** bởi một xưởng chữ Việt, dấu được vẽ chứ không phải lắp thêm. Không ai chọn font này theo quán tính. |
| **Data** | `IBM Plex Mono` | Số liệu, điểm, khoảng ôn, thời lượng audio, hash. Có `tnum` thật. |

> **Cần xác minh trước khi triển khai:** máy dựng tài liệu này không có mạng nên chưa gọi được Google Fonts API để xác nhận subset. Chạy `curl "https://fonts.googleapis.com/css2?family=Archivo&display=swap"` và kiểm `unicode-range` có chứa `U+0102` (Ă) trước khi khoá. Nếu `IBM Plex Mono` thiếu subset `vietnamese`, đổi sang `JetBrains Mono`; font data chỉ dựng số và nhãn ASCII nên đây là rủi ro thấp.

### 5.3 Thang chữ

Tất cả `line-height` ghi tuyệt đối, không ghi hệ số, để dấu tiếng Việt không phụ thuộc vào font-size kế thừa.

| Tên | Size / Leading | Font | Weight | Tracking | Dùng ở |
|---|---|---|---|---|---|
| `readout` | 64 / 72 (mobile 48 / 56) | Archivo | 600 | −0.02em | Con số điểm §10 |
| `display` | 30 / 38 | Archivo | 600 | −0.015em | `h1` |
| `title` | 22 / 30 | Archivo | 600 | −0.01em | `h2`, tiêu đề card |
| `subtitle` | 17 / 26 | Archivo | 600 | 0 | `h3` |
| `body` | 15 / 25 | Be Vietnam Pro | 400 | 0 | Văn bản |
| `body-strong` | 15 / 25 | Be Vietnam Pro | 600 | 0 | Nhãn form |
| `small` | 13 / 21 | Be Vietnam Pro | 400 | 0 | Mô tả phụ |
| `label` | 11 / 16 | Be Vietnam Pro | 600 | +0.08em, VIẾT HOA | Eyebrow, nhãn cột |
| `data` | 13 / 20 | IBM Plex Mono | 500 | 0 | Số, mã, thời lượng |
| `data-lg` | 17 / 26 | IBM Plex Mono | 500 | 0 | Số nổi bật trong dòng |

**`font-variant-numeric: tabular-nums` bật mặc định** cho `data`, `data-lg`, `readout`, và mọi ô bảng chứa số. Số nhảy cột khi cập nhật là thứ phá vỡ cảm giác "thiết bị đo" nhanh nhất.

---

## 6. Khoảng cách, bo góc, độ nổi

### 6.1 Khoảng cách
Thang 4px: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`. Không dùng giá trị ngoài thang. Khoảng cách trong một khối dùng số nhỏ; giữa các khối dùng `32` trở lên.

### 6.2 Bo góc — **một giá trị**

```
radius        4px    mọi thứ: nút, ô nhập, card, badge, popover
radius-pill   999px  chỉ dành cho chip giọng đọc (§4)
radius-none   0      chỉ dành cho thang điểm và vạch chia (§10)
```

`4px` thay cho `rounded-lg`/`rounded-xl` (8/12px) của hệ cũ. Bo góc chặt đọc như thiết bị; bo góc 12px đọc như mọi bản sao shadcn. **Không chọn `0`** — đó là mặc định số 3 ở §1.

### 6.3 Độ nổi — **bỏ đổ bóng**

Đây là thay đổi lớn nhất về mặt thị giác, và là đòn bẩy chống-slop mạnh nhất.

> **Cấm `box-shadow`.** Độ nổi được diễn đạt bằng **viền + bậc nền**, không bằng bóng.

```
chìm      recess    + rule
phẳng     ground    (không viền)
nổi       panel     + rule
nổi+chọn  panel     + rule-strong
```

Ba ngoại lệ duy nhất, không có ngoại lệ thứ tư:

1. **Vòng focus** (§11)
2. **Header dính**, chỉ một đường kẻ `rule` ở đáy khi trang đã cuộn — không phải bóng
3. **Lớp phủ thật** (modal, popover, menu thả xuống): `0 8px 24px rgb(0 0 0 / 0.18)` ở chế độ sáng, `0 8px 24px rgb(0 0 0 / 0.5)` ở chế độ tối

Kèm theo, **bỏ `hover:-translate-y-0.5` trên card.** Card nhấc lên khi rê chuột là một trong những dấu hiệu rõ nhất của giao diện sinh tự động. Hover đổi `rule` → `rule-strong` và đổi nền một bậc là đủ.

---

## 7. Chuyển động

```
duration-state   120ms   hover, press, đóng/mở
duration-enter   200ms   nội dung xuất hiện
easing           cubic-bezier(0.2, 0, 0, 1)
```

Chỉ **một** khoảnh khắc được dàn dựng trong toàn bộ app:

**Bảng chấm dictation hiện ra từng từ, trái sang phải, lệch nhau 24ms.** Vì đó chính là cách người ta nghe lại câu — theo thời gian, từ trái sang. Nó phục vụ nội dung chứ không trang trí. Tổng thời gian bị chặn ở 600ms; câu dài hơn 25 từ thì bỏ stagger, hiện cùng lúc.

Mọi thứ khác là fade 120ms. Không có parallax, không có nền động, không có hiệu ứng cuộn.

`@media (prefers-reduced-motion: reduce)` **tắt toàn bộ**, kể cả stagger — chỉ giữ đổi màu tức thời.

---

## 8. Icon

### 8.1 Bộ icon

**[Lucide](https://lucide.dev)** qua `lucide-react`. Giấy phép ISC, cây icon tree-shake được, lưới 24px với nét đều — hợp với hướng thiết bị đo, và được bảo trì tốt nhất trong các bộ mã nguồn mở.

```bash
pnpm --filter @toeic-pilot/web add lucide-react
```

### 8.2 Luật

1. **Không dùng emoji ở bất kỳ đâu trong giao diện.** Emoji hiển thị khác nhau trên từng hệ điều hành, không nhận màu theme, không co giãn theo thang chữ, và đọc như bản nháp.
2. **Ba cỡ, không có cỡ thứ tư:** `14` (trong chữ `small`), `16` (mặc định, trong nút và nav), `20` (đứng một mình, empty state).
3. **Độ dày nét:** `2` ở cỡ 14, `1.75` ở cỡ 16 và 20. Đặt tường minh, đừng dựa vào mặc định.
4. **Icon không bao giờ mang nghĩa một mình.** Đi cùng chữ thì `aria-hidden="true"`; đứng một mình thì bắt buộc `aria-label`.
5. **Không đặt icon trong vòng tròn màu.** Cụm "icon tròn màu pastel + tiêu đề + một dòng mô tả" là mẫu slop dễ nhận ra nhất. Icon nằm thẳng trên nền, màu `ink-muted`.
6. **Icon nhận màu từ `currentColor`**, không bao giờ đặt màu riêng.

### 8.3 Bảng thay thế emoji

17 chỗ, 10 file. Đây là danh sách đầy đủ — quét lại bằng `grep -rnP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' src/` sau khi xong, kết quả phải rỗng.

| File | Emoji | Icon Lucide | Ghi chú |
|---|---|---|---|
| `app/not-found.tsx` | 🧭 | `Compass` | |
| `app/error.tsx` | ⚠️ | `TriangleAlert` | |
| `app/page.tsx` | 🎧 | `Headphones` | Dictation |
| `app/page.tsx` | 🗣️ | `Languages` | Từ vựng — **không** dùng `Mic`, app không thu âm |
| `app/page.tsx` | 🔁 | `RotateCcw` | Ôn tập |
| `app/learn/page.tsx` | 🔁 | `RotateCcw` | |
| `app/learn/page.tsx` | 🎧 | `Headphones` | |
| `app/learn/page.tsx` | 📚 | `BookOpen` | |
| `app/learn/vocabulary/page.tsx` | 🗂️ | `Library` | |
| `app/learn/dictation/page.tsx` | 🎧 | `Headphones` | |
| `app/learn/review/page.tsx` | ✅ | `CalendarCheck` | "Hôm nay không có từ đến hạn" — về **lịch** |
| `app/learn/review/page.tsx` | 🎉 | `CircleCheck` | "Xong phiên" — về **hoàn thành** |
| `app/admin/page.tsx` | 🗂️ | `Library` | |
| `app/admin/page.tsx` | 🎧 | `Headphones` | |
| `app/admin/vocabulary/page.tsx` | 🗂️ | `Library` | |
| `app/admin/dictation/page.tsx` | 🎧 | `Headphones` | |
| `components/admin-bits.tsx` | ⚠ | `TriangleAlert` | cỡ 14 |

Hai chỗ đáng chú ý vì emoji đang **giấu mất một khác biệt có thật**:

- `review/page.tsx` dùng ✅ và 🎉 cho hai trạng thái khác hẳn nhau. "Chưa có gì đến hạn" là thông tin về lịch; "vừa học xong" là thông tin về thành tựu. Hai icon khác nhau nói ra điều đó.
- `page.tsx` dùng 🗣️ cho từ vựng gợi ý người dùng sẽ **nói**. Họ không nói — họ nghe và nhớ. `Languages` đúng hơn.

### 8.4 Icon cố định theo khái niệm

Một khái niệm dùng **một** icon trong toàn app. Bảng này là bảng tra bắt buộc.

| Khái niệm | Icon |
|---|---|
| Dictation / nghe | `Headphones` |
| Phát audio · Tạm dừng | `Play` · `Pause` |
| Giọng đọc / accent | `AudioLines` |
| Từ vựng | `Library` |
| Ôn tập (SRS) | `RotateCcw` |
| Chủ đề | `BookOpen` |
| Đã publish | `CircleCheck` |
| Bản nháp | `CircleDashed` |
| Audio thiếu | `CircleSlash` |
| Audio lệch | `TriangleAlert` |
| Xuất bản (hành động) | `Send` |
| Lỗi / bị từ chối | `OctagonAlert` |
| Tài khoản | `UserRound` |
| Thoát | `LogOut` |
| Menu (mobile) | `Menu` |

Ba icon trạng thái audio (`CircleCheck` / `CircleDashed` / `CircleSlash` / `TriangleAlert`) khớp thẳng với `AudioState` trong `app/services/media_state.py`. **Giữ chúng khớp nhau** — thêm trạng thái ở backend thì thêm icon ở đây.

---

## 9. Component

Mọi component sống ở `src/components/ui.tsx`. Dùng ở hơn một màn hình thì thuộc về đó.

### 9.1 Nút

| Biến thể | Nền | Chữ | Viền | Dùng khi |
|---|---|---|---|---|
| `primary` | `action` | trắng (sáng) / `#160B05` (tối) | — | **Một** trên mỗi màn hình |
| `secondary` | `panel` | `ink` | `rule-strong` | Hành động phụ |
| `quiet` | trong suốt | `ink-muted` | — | Hành động thứ ba, thanh công cụ |
| `destructive` | `alert` | trắng | — | Xoá, huỷ bỏ |

Cỡ: `sm` 28px · `md` 36px · `lg` 44px. Bo `4px`. Không bóng.

**Vô hiệu hoá vẫn hiện rõ**, `opacity: 0.45`, không ẩn đi — ở màn admin, nút Publish bị mờ **chính là thông báo**: nội dung chưa sẵn sàng. Kèm theo `title` nói rõ vì sao.

Bỏ biến thể `success` của hệ cũ. Nút không phải là nơi báo trạng thái; nó là nơi ra lệnh.

### 9.2 Bề mặt

- **`Panel`** — nền `panel`, viền `rule`, bo 4, **không bóng**.
- **`PanelLink`** — như trên; hover đổi viền sang `rule-strong` và nền sang `recess`. **Không nhấc lên, không đổ bóng.**
- **`Recess`** — nền `recess`, dùng cho header bảng và vùng chỉ đọc.

### 9.3 Chip giọng đọc — component riêng

Đây là thành phần đặc thù nhất của sản phẩm, nên nó có định nghĩa riêng chứ không mượn `Badge`.

```
┌──────────────────────────────────────────┐
│  ▸  ●US   ●UK   ●AU   ●CA      0:01.8    │
│     ^^^^                        ^^^^^^   │
│     chip bo tròn, màu §4        IBM Plex │
│     đang chọn = nền đặc         Mono     │
│     chưa chọn = chấm + viền              │
└──────────────────────────────────────────┘
```

- Nhãn hai chữ **luôn hiện**, không bao giờ chỉ có chấm màu.
- Chip đang chọn: nền màu giọng, chữ `panel`. Chưa chọn: nền trong suốt, viền `rule-strong`, chữ `ink-muted`, một chấm 6px màu giọng.
- Clip thiếu: chip vô hiệu hoá + `CircleSlash` cỡ 14. **Không giấu chip đi** — người học cần biết giọng đó tồn tại nhưng chưa có.
- Thời lượng đọc từ `audio_asset.duration_ms`, định dạng `m:ss.d`, tabular.

### 9.4 Nhãn trạng thái

Chữ `label`, bo 4, viền + nền nhạt, **luôn có icon** (§8.4).

| Trạng thái | Token | Icon |
|---|---|---|
| Đã publish | `ok` / `ok-tint` | `CircleCheck` |
| Nháp | `ink-muted` / `recess` | `CircleDashed` |
| Audio lệch | `warn` / `warn-tint` | `TriangleAlert` |
| Audio thiếu | `alert` / `alert-tint` | `CircleSlash` |

### 9.5 Ô nhập

Viền `rule-strong` (**không** `rule` — xem §11.2), nền `panel`, bo 4, cao 36px.
Lỗi: viền `alert` + một dòng `small` màu `alert` **có icon** `OctagonAlert` cỡ 14 phía dưới. Không bao giờ chỉ đổi màu viền.

### 9.6 Trạng thái rỗng

```
┌────────────────────────────────────────────┐
│                                            │
│   [icon 20px, ink-muted]                   │
│                                            │
│   Chưa có từ nào đến hạn hôm nay           │  ← title
│   Quay lại ngày mai, hoặc học một chủ đề   │  ← small, ink-muted
│   mới ngay bây giờ.                        │
│                                            │
│   [ Học chủ đề mới ]                       │  ← luôn có một hành động
│                                            │
└────────────────────────────────────────────┘
```

**Căn trái, không căn giữa.** Khối căn giữa trong hộp viền là mẫu slop. Icon 20px màu `ink-muted`, **không** `text-4xl opacity-60` như hệ cũ (đó là cách để emoji trông cho ra hồn).

Mọi trạng thái rỗng phải nói **bước tiếp theo**. "Không có dữ liệu" không nói gì mà người đọc chưa tự biết.

### 9.7 Skeleton

Giữ nguyên cách tiếp cận của hệ cũ — đây là chỗ hệ cũ làm đúng. Khối có **đúng hình dạng** của nội dung sắp tới, `recess`, nhấp nháy 1.4s. Không bao giờ dùng chữ "Đang tải…".

---

## 10. Thành phần chữ ký: **thang điểm có vạch chia**

Thứ người dùng nhớ về sản phẩm này. Nó **không** phải "một con số to với nhãn nhỏ và một dải gradient" — đó là câu trả lời mẫu.

```
   ĐIỂM ƯỚC TÍNH                                        cập nhật 09.08

   ┌─ 645 ─────────────────────────────────────────────────────────┐
   │  IBM Plex Mono 64px, tabular                                  │
   └───────────────────────────────────────────────────────────────┘

   10        255       405       605       785       905      990
   ├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
   ██████████████████████████████████▓                    ╎
                                     ▲                    ╎
                                    bạn                mục tiêu 800
   Cơ bản    Sơ cấp   Sơ cấp+   Hạn chế   Làm việc+  Quốc tế

   ┌──────────────────────────┬──────────────────────────┐
   │ LISTENING          340   │ READING            305   │
   │ ├──────────────▓──┤ /495 │ ├────────────▓────┤ /495 │
   └──────────────────────────┴──────────────────────────┘
```

Bốn quyết định, mỗi cái đều xuất phát từ miền chứ không từ thẩm mỹ:

1. **Vạch chia là ngưỡng thật.** `255 · 405 · 605 · 785 · 905` là sáu bậc năng lực ETS công bố, không phải các mốc tròn cho đẹp. Đây chính là nguyên tắc "thiết bị cấu trúc phải mã hoá điều gì đó có thật": vạch chia trả lời câu hỏi *"645 nghĩa là gì?"* — câu hỏi mà một dải gradient không trả lời được.
2. **Thang không tuyến tính, và nó được vẽ đúng như vậy.** Quy đổi TOEIC đến từ bảng `score_conversion` chứ không từ công thức. Thang phải vẽ theo bảng thật của đề đó.
3. **Mục tiêu là một vạch riêng, không phải điểm cuối.** Nó là mốc do người học đặt, không phải giới hạn của thang. Vẽ bằng nét đứt, `ink-muted`.
4. **Khi không quy đổi được thì nói thẳng.** `app/services/scoring.py` **từ chối đoán** khi thiếu hàng quy đổi, vì một điểm sai âm thầm sẽ nằm vĩnh viễn trên bài làm. Giao diện phải tôn trọng điều đó: hiện `—` ở chỗ con số, thang chuyển sang `rule`, và một dòng `small` nói *"Đề này chưa có bảng quy đổi."* **Không hiện 0. Không nội suy. Không ẩn thành phần đi.**

Bo góc `0` ở thang và vạch chia — đây là ngoại lệ `radius-none` ở §6.2. Vạch chia của thiết bị đo không bo tròn.

---

## 11. Sàn chất lượng

Không thương lượng. Đây là điều kiện để một màn hình được coi là xong.

### 11.1 Vòng focus
Mọi phần tử tương tác, chỉ hiện với bàn phím:
`outline: 2px solid action; outline-offset: 2px`.
Đạt 5.54 (sáng) và 6.03 (tối) so với `panel` — vượt ngưỡng 3.0 của WCAG 1.4.11.

### 11.2 Một lỗi có thật trong code hiện tại

> `CONTROL` trong `ui.tsx` đặt viền ô nhập bằng `border-border-strong`, và ô nhập dùng nền `bg-surface`. Ở chế độ sáng đó là `#D4D4D8` trên `#FFFFFF` — tỉ số **1.48**, trong khi WCAG 1.4.11 yêu cầu **3.0** cho ranh giới của một component. Ở chế độ tối là `#3F3F46` trên `#09090B` — **1.91**. Cả hai đều trượt, và chế độ sáng trượt nặng hơn.
>
> Nghĩa là ranh giới ô nhập hiện **không nhìn thấy được** với người thị lực kém. Token `rule-strong` mới (`#738999` / `#576E7E`) đạt 3.09–3.64. Đây là lý do `rule` và `rule-strong` **không thể hoán đổi cho nhau**: `rule` dành cho kẻ trang trí, `rule-strong` dành cho ranh giới component — và chỉ `rule-strong` mới có nghĩa vụ tương phản.

### 11.3 Còn lại

- **Không có thông tin nào chỉ nằm ở màu.** Trạng thái đi kèm icon và chữ. Bốn giọng đọc đi kèm nhãn hai chữ.
- **Chữ đạt 4.5** ở mọi tổ hợp trong §3 — đã kiểm bằng số, không phải bằng mắt.
- **Vùng chạm ≥ 44×44px** trên mobile, kể cả khi phần nhìn thấy nhỏ hơn.
- **Đáp ứng tới 360px** không tràn ngang.
- **Cỡ chữ dùng `rem`**, để tôn trọng cỡ chữ hệ thống của người dùng.
- **Ngôn ngữ:** câu mệnh lệnh, viết hoa đầu câu, không viết hoa toàn bộ trừ `label`. Nút nói đúng việc nó làm — nút "Xuất bản" phải sinh ra thông báo "Đã xuất bản", không phải "Thành công".

---

## 12. Triển khai

### 12.1 Ba trạng thái theme, không phải hai

Hệ cũ chỉ có `@media (prefers-color-scheme: dark)` nên không thể làm nút chuyển theme. Cấu trúc dưới đây cho phép cả ba: theo hệ thống (mặc định), ép sáng, ép tối.

`src/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/*
 * Ba trạng thái, không phải hai:
 *   :root                                   -> sáng, và là mặc định khi theo hệ thống
 *   @media (dark) :root:not([data-theme=light]) -> theo hệ thống, hệ thống đang tối
 *   :root[data-theme="dark"]                -> người dùng ép tối, thắng mọi thứ
 *
 * Không màu nào được định nghĩa DUY NHẤT bên trong khối media hoặc khối
 * [data-theme] — làm vậy thì một trong ba trạng thái sẽ thiếu màu.
 */
:root {
  --ground: 233 237 240;
  --panel: 255 255 255;
  --recess: 221 227 232;
  --rule: 203 212 219;
  --rule-strong: 115 137 153;

  --ink: 15 23 29;
  --ink-muted: 74 89 100;
  --ink-faint: 94 108 119;

  --action: 194 52 15;
  --action-hover: 168 43 11;
  --action-ink: 154 39 9;
  --action-tint: 252 237 232;
  --on-action: 255 255 255;

  --ok: 23 105 74;
  --ok-tint: 228 241 234;
  --warn: 138 90 6;
  --warn-tint: 251 240 220;
  --alert: 163 18 32;
  --alert-tint: 251 233 234;

  --accent-us: 19 57 101;
  --accent-uk: 95 57 139;
  --accent-au: 12 106 94;
  --accent-ca: 151 105 6;

  --overlay-shadow: 0 8px 24px rgb(0 0 0 / 0.18);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: 13 19 23;
    --panel: 21 29 34;
    --recess: 8 12 15;
    --rule: 36 48 55;
    --rule-strong: 87 110 126;

    --ink: 232 238 242;
    --ink-muted: 154 170 181;
    --ink-faint: 121 135 146;

    --action: 255 107 61;
    --action-hover: 255 131 85;
    --action-ink: 255 138 95;
    --action-tint: 42 17 9;
    --on-action: 22 11 5;

    --ok: 75 214 155;
    --ok-tint: 11 42 30;
    --warn: 232 169 60;
    --warn-tint: 46 32 7;
    --alert: 248 122 130;
    --alert-tint: 46 13 16;

    --accent-us: 65 135 214;
    --accent-uk: 165 123 213;
    --accent-au: 49 185 166;
    --accent-ca: 228 185 92;

    --overlay-shadow: 0 8px 24px rgb(0 0 0 / 0.5);
  }
}

:root[data-theme="dark"] {
  /* Y hệt khối trên. Tách ra để nút chuyển theme thắng được cả hai chiều:
     ép tối khi hệ thống đang sáng, và ép sáng khi hệ thống đang tối. */
  --ground: 13 19 23;
  --panel: 21 29 34;
  --recess: 8 12 15;
  --rule: 36 48 55;
  --rule-strong: 87 110 126;

  --ink: 232 238 242;
  --ink-muted: 154 170 181;
  --ink-faint: 121 135 146;

  --action: 255 107 61;
  --action-hover: 255 131 85;
  --action-ink: 255 138 95;
  --action-tint: 42 17 9;
  --on-action: 22 11 5;

  --ok: 75 214 155;
  --ok-tint: 11 42 30;
  --warn: 232 169 60;
  --warn-tint: 46 32 7;
  --alert: 248 122 130;
  --alert-tint: 46 13 16;

  --accent-us: 65 135 214;
  --accent-uk: 165 123 213;
  --accent-au: 49 185 166;
  --accent-ca: 228 185 92;

  --overlay-shadow: 0 8px 24px rgb(0 0 0 / 0.5);
}

@layer base {
  html {
    -webkit-text-size-adjust: 100%;
  }

  body {
    @apply bg-ground text-ink antialiased;
    font-family: var(--font-body);
    font-size: 0.9375rem; /* 15px */
    line-height: 1.667;   /* 25px — chữ Việt chồng hai dấu, cần khoảng đứng rộng */
  }

  h1, h2, h3 {
    font-family: var(--font-display);
    font-weight: 600;
  }

  /* Không line-height nào dưới 1.25, kể cả tiêu đề lớn: `ế` `ộ` `ữ` mang hai
     tầng dấu và sẽ bị cắt hoặc chạm dòng trên. */
  h1 { font-size: 1.875rem; line-height: 2.375rem; letter-spacing: -0.015em; }
  h2 { font-size: 1.375rem; line-height: 1.875rem; letter-spacing: -0.01em; }
  h3 { font-size: 1.0625rem; line-height: 1.625rem; }

  /* Số phải thẳng cột. Số nhảy cột khi cập nhật phá vỡ cảm giác thiết bị đo
     nhanh hơn bất cứ thứ gì khác. */
  .font-data, table td, table th {
    font-variant-numeric: tabular-nums;
  }

  :focus-visible {
    outline: 2px solid rgb(var(--action));
    outline-offset: 2px;
    border-radius: 4px;
  }
}

@layer utilities {
  .shadow-overlay { box-shadow: var(--overlay-shadow); }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 12.2 Chống nháy theme

`data-theme` phải được đặt **trước khi trang vẽ**, nếu không người chọn theme tối sẽ thấy một nháy trắng mỗi lần tải. Script này chạy đồng bộ trong `<head>` của `layout.tsx`:

```tsx
<script
  dangerouslySetInnerHTML={{
    __html: `try{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}catch(e){}`,
  }}
/>
```

Không có `try/catch` thì Safari ở chế độ riêng tư sẽ ném lỗi và làm hỏng lần dựng đầu tiên.

### 12.3 `tailwind.config.ts`

```ts
import type { Config } from "tailwindcss";

/** `<alpha-value>` giữ cho `bg-action/10` vẫn hoạt động. */
const c = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

export default {
  content: [
    "./src/components/**/*.{ts,tsx}",
    "./src/app/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ground: c("--ground"),
        panel: c("--panel"),
        recess: c("--recess"),
        rule: c("--rule"),
        "rule-strong": c("--rule-strong"),

        ink: c("--ink"),
        "ink-muted": c("--ink-muted"),
        "ink-faint": c("--ink-faint"),

        action: c("--action"),
        "action-hover": c("--action-hover"),
        "action-ink": c("--action-ink"),
        "action-tint": c("--action-tint"),
        "on-action": c("--on-action"),

        ok: c("--ok"),
        "ok-tint": c("--ok-tint"),
        warn: c("--warn"),
        "warn-tint": c("--warn-tint"),
        alert: c("--alert"),
        "alert-tint": c("--alert-tint"),

        "accent-us": c("--accent-us"),
        "accent-uk": c("--accent-uk"),
        "accent-au": c("--accent-au"),
        "accent-ca": c("--accent-ca"),
      },
      // Một bán kính. `rounded-pill` chỉ dành cho chip giọng đọc.
      borderRadius: { DEFAULT: "4px", pill: "999px", none: "0" },
      borderColor: { DEFAULT: c("--rule") },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        data: ["var(--font-data)"],
      },
      transitionTimingFunction: { DEFAULT: "cubic-bezier(0.2, 0, 0, 1)" },
      transitionDuration: { DEFAULT: "120ms", enter: "200ms" },
      // Đổ bóng bị bỏ có chủ ý (§6.3). Lớp phủ dùng utility `.shadow-overlay`.
      boxShadow: { none: "none" },
    },
  },
  plugins: [],
} satisfies Config;
```

### 12.4 Font trong `layout.tsx`

```tsx
import { Archivo, Be_Vietnam_Pro, IBM_Plex_Mono } from "next/font/google";

// `subsets` PHẢI có "vietnamese". Thiếu nó thì `ế` `ộ` `ữ` rơi về font hệ thống
// và dòng chữ sẽ lẫn hai kiểu chữ khác nhau — rất dễ lọt vì tiếng Anh không lộ.
const display = Archivo({
  variable: "--font-display",
  subsets: ["latin", "vietnamese"],
  weight: ["600"],
});
const body = Be_Vietnam_Pro({
  variable: "--font-body",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
});
const data = IBM_Plex_Mono({
  variable: "--font-data",
  subsets: ["latin"],
  weight: ["500"],
});
```

---

## 13. Di trú

Đổi tên token là thao tác cơ học, nhưng phải làm **một lượt** — trộn tên cũ và mới thì hai bảng màu cùng sống trong một trang.

### 13.1 Bảng đổi tên

| Cũ | Mới | Đổi gì ngoài tên |
|---|---|---|
| `surface` | `ground` | Trắng → xám ngả lạnh |
| `surface-raised` | `panel` | — |
| `surface-sunken` | `recess` | — |
| `border` | `rule` | — |
| `border-strong` | `rule-strong` | **Đậm hơn hẳn** — sửa lỗi ở §11.2 |
| `text` | `ink` | — |
| `text-muted` | `ink-muted` | — |
| `text-subtle` | `ink-faint` | Đậm hơn, để đạt 4.5 |
| `brand` | `action` | **Indigo → chu sa.** Đổi nghĩa, không chỉ đổi màu |
| `brand-hover` | `action-hover` | |
| `brand-soft` | `action-tint` | |
| `brand-text` | `action-ink` | |
| `success` / `success-soft` | `ok` / `ok-tint` | |
| `warning` / `warning-soft` | `warn` / `warn-tint` | |
| `danger` / `danger-soft` | `alert` / `alert-tint` | Tách khỏi chu sa về sắc và độ sáng |
| — | `accent-us/uk/au/ca` | Mới (§4) |
| — | `on-action` | Mới — chữ trên nút chính, **khác nhau giữa hai theme** |

### 13.2 Thứ tự làm

1. `globals.css` + `tailwind.config.ts` + font trong `layout.tsx` — bảng token mới, tên mới
2. `pnpm add lucide-react`; thay 17 emoji theo §8.3; xác nhận `grep` cho kết quả rỗng
3. `components/ui.tsx` — biến thể nút, bỏ bóng, bỏ `hover:-translate-y-0.5`, một bán kính, `EmptyState` căn trái
4. `components/app-shell.tsx` — dùng icon Lucide cho nav và menu; header dùng kẻ chỉ thay cho bóng
5. `components/audio-button.tsx` → chip giọng đọc §9.3
6. `components/admin-bits.tsx` — nhãn trạng thái audio §9.4, khớp với `AudioState`
7. Các trang, theo thứ tự: `learn/**` → `admin/**` → `login`/`register`/`dashboard` → `error`/`not-found`
8. Thang điểm §10 — dựng cùng Sprint 5, khi đã có `attempt` để hiển thị

### 13.3 Kiểm trước khi coi là xong

- [ ] `grep -rnP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' apps/web/src` → rỗng
- [ ] `grep -rn 'shadow-sm\|shadow-md\|rounded-lg\|rounded-xl' apps/web/src` → rỗng
- [ ] `grep -rn 'brand\|surface\|text-subtle' apps/web/src` → rỗng (token cũ đã hết)
- [ ] Không có mã màu hex nào ngoài `globals.css`
- [ ] Duyệt toàn app bằng **bàn phím**: mọi điểm dừng đều thấy vòng focus
- [ ] Duyệt toàn app ở **cả hai theme**, kể cả trạng thái lỗi và trạng thái rỗng
- [ ] Ép cỡ chữ hệ thống lên 200%: không có gì tràn hoặc bị cắt
- [ ] Kiểm một màn hình có nhiều dấu tiếng Việt (`Ôn tập · Từ vựng · Câu nghe · Xuất bản`) ở mọi cỡ chữ: không dấu nào bị cắt hay chạm dòng trên
- [ ] `pnpm --filter @toeic-pilot/web lint` và `pnpm build` xanh

---

## 14. Khi nào xem lại tài liệu này

- **Thêm giọng đọc thứ năm** → mở rộng bậc thang §4. Không lấy `action`.
- **Sprint 5 (TOEIC Practice)** → thang điểm §10 rời khỏi giấy. Lúc đó sẽ cần thêm: ô tròn đáp án, đồng hồ đếm ngược, và **phần ghi công ảnh Part 1** — `ADR-004` §4.2 bắt buộc hiển thị attribution, lưu mà không hiện vẫn là vi phạm CC-BY.
- **Sprint 7 (AI Layer)** → cần ngôn ngữ hình thức cho nội dung do máy sinh, và cho trạng thái đang phát sinh (streaming). Cả hai chưa có ở đây.
- **Có người dùng thật** → §10 và §9.3 là hai chỗ đáng đo trước tiên.
