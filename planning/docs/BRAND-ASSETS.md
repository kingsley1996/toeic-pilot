# Bộ nhận diện — logo, favicon, ảnh OG

Runbook sinh tài sản thương hiệu bằng model ảnh, và những chỗ model **không**
làm được nên phải làm tay.

Ngày khảo sát: **2026-09-05**.

---

## 0. Đang có gì, thiếu gì

| | Trạng thái |
|---|---|
| `apps/web/src/app/favicon.ico` | ~~Vẫn là favicon mặc định của Next.js~~ **Đã thay 2026-09-05.** Trước đó là bản của Next.js — 25 931 byte, vào repo từ commit đầu tiên (`V1 - githubpilot init project`, 2026-08-07) và chưa ai đụng, nên mọi tab trình duyệt hiện logo Vercel suốt một tháng |
| `icon.png`, `apple-icon.png` | **Đã có** (512 và 180), sinh từ §3.1 |
| Ảnh OG | **Không có.** `layout.tsx` chỉ khai `title` và `description`, nên link dán vào Zalo hay Messenger hiện ra trống. Với sản phẩm người học chuyền tay nhau, đây là chỗ thiếu đắt nhất |
| Dấu hiệu ở thanh trên | Ô vuông cam chữ **T** — chỗ tạm, và nó không nhắc gì tới con mascot |
| `public/brand/pilot-*.png` | **Bản sắc thật của dự án.** Bốn trạng thái: `idle`, `blink`, `cheer`, `hide` |

## 1. Con mascot là bản sắc, không phải chữ T

Mọi prompt dưới đây **dẫn xuất từ nó**, không phát minh cái mới. Tả lại để model
dựng đúng nhân vật ấy:

> Gấu con tròn, mũ da phi công màu nâu có hai vạt che tai, **kính bay đẩy lên
> trán** (hai vòng tròn nối bằng cầu, có quai), mặt màu kem, hai mắt bầu dục đen
> đặc, miệng cười nhỏ, má ửng hồng, khăn quàng màu kem. Nét viền nâu sẫm dày và
> đều, màu phẳng kiểu cel, không chuyển sắc, không đổ bóng.

Bảng màu, lấy từ `globals.css` (nguồn thật, không chép tay vào đây):

| Token | Sáng | Tối |
|---|---|---|
| `--action` | `#C2340F` | `#FF6B3D` |
| `--ground` | `#E9EDF0` | `#0D1317` |
| `--ink` | `#0F171D` | `#E8EEF2` |

## 2. Ba thứ model làm không được, và chúng định hình prompt

**Đừng bao giờ nhờ nó viết chữ.** Model dựng "TOEIC Pilot" sai chính tả là
chuyện thường, và một logo sai chính tả không sửa được bằng cách sinh lại. Sinh
**biểu tượng** thôi; wordmark đặt bằng font thật ở bước sau.

**Favicon không phải logo thu nhỏ.** Ở 16×16, cái đầu gấu có mắt, má hồng và
khăn quàng thành một vệt nâu. Nó phải là một **bản vẽ khác**, rút gọn từ cùng ý
tưởng — xem prompt 2.

**Màu sẽ sai.** Model không trúng `#C2340F`. Sinh trên nền phẳng rồi tô lại theo
token; đó cũng là lý do mọi prompt đều đòi nền phẳng, không chuyển sắc.

## 3. Prompt

### 3.1 Biểu tượng chính — app icon, 512×512

```
A flat vector app icon, centered, on a solid warm red-orange background. The
subject is the head of a round cartoon bear cub wearing a brown leather aviator
cap with ear flaps, and round flight goggles pushed up onto the forehead.
Cream-coloured face, two large solid black oval eyes, a small curved smile, soft
pink cheek blush. A cream scarf wraps the neck, just the top edge visible. Thick
dark brown outline of even weight, flat cel-shaded colours, no gradients, no
texture, no shadow. Simple bold shapes readable at small size. Generous even
margin around the subject. Square composition.
```

```
Negative: text, letters, words, numbers, watermark, signature, gradient, drop
shadow, 3d render, photorealistic, busy detail, thin lines, multiple characters,
full body, background scenery
```

### 3.2 Favicon — vẽ riêng cho 16px

Rút gọn còn **cặp kính bay**: hai vòng tròn và một quai. Đọc được ở 16px, và nó
nói đúng chữ "Pilot" trong tên sản phẩm.

```
A minimal flat vector emblem: a pair of vintage aviator flight goggles seen
straight on, two round lenses joined by a bridge, with a strap band running left
and right to the edges. Cream lenses, dark brown frame, thick uniform outline.
Extremely simplified, only three or four shapes total, no small details. Solid
warm red-orange background, square, centered, large margin. Icon design intended
to stay legible when scaled down to 16 pixels.
```

```
Negative: text, letters, numbers, face, eyes, character, gradient, shadow,
texture, thin lines, fine detail, realistic leather, reflections
```

### 3.3 Ảnh OG — 1200×630

```
A wide horizontal illustration on a solid deep charcoal background. On the right
side, a round cartoon bear cub in a brown leather aviator cap with goggles pushed
up on the forehead and a cream scarf, standing and facing the viewer, cheerful.
Flat cel-shaded vector style, thick dark brown outlines, no gradients. The left
two thirds of the image are empty flat background with no objects, leaving clear
space for text to be added later. Warm red-orange accent used sparingly. Clean,
calm, uncluttered.
```

Chừa trống hai phần ba bên trái là **cố ý**: "TOEIC Pilot" và dòng mô tả đặt sau
bằng font thật, không để model viết — xem §2.

## 4. Sau khi có ảnh

Tô lại nền đúng token ở §1. Đặt tên để Next.js tự nhận, khỏi phải khai `icons`
trong `metadata`:

```
apps/web/src/app/favicon.ico          ← 16/32/48 từ §3.2, THAY bản của Next.js
apps/web/src/app/icon.png             ← 512, từ §3.1
apps/web/src/app/apple-icon.png       ← 180, từ §3.1
apps/web/src/app/opengraph-image.png  ← 1200×630, từ §3.3
```

Rồi thêm khối `openGraph` vào `metadata` ở `app/layout.tsx` — không có nó thì
tệp `opengraph-image.png` vẫn được Next.js nhặt, nhưng `title`/`description` của
thẻ chia sẻ sẽ rơi về mặc định.

**ICO phải là RGBA, không phải RGB.** Bộ giải mã của Next.js từ chối PNG dạng
RGB nhúng trong `.ico`, và nó không từ chối một mình cái ảnh — **mọi trang trả
500** với `Format error decoding Ico: The PNG is not in RGBA format`. Pillow lưu
RGB theo mặc định, nên phải `.convert("RGBA")` trước khi `save`. Dựng sạch, chạy
thì chết: đúng loại lỗi mà job `docker` của CI tồn tại để bắt.

**Kiểm ở kích thước thật, đừng kiểm ở bản 512.** Một biểu tượng đẹp ở 512 mà
nhoè ở 16 là chuyện thường, và tab trình duyệt là chỗ duy nhất người dùng thật
sự nhìn thấy favicon. Thu về 16×16 rồi nhìn, trước khi commit.

Đo ngày 2026-09-05 trên đúng bản của §3.1: **dùng được từ 32px trở lên.** Ở 32px
kính đọc ra hai ô, mũ và mặt tách bạch. Ở 16px nó là một vệt nâu có mảng kem —
nhận ra được là "một nhân vật đội mũ", không hơn. Cắt sát thêm 7% mỗi bên giúp
thấy rõ hơn hẳn, và đó là lý do `favicon.ico` cắt sát hơn `icon.png`.

Nên §3.2 vẫn còn nguyên giá trị: favicon 16px xứng đáng có một bản vẽ riêng.
Bản đang dùng là chỗ tạm — nó đúng thương hiệu, chỉ là chưa sắc.

**Màu nền model trả về là `#FA3F19`**, không khớp token nào; đã tô lại thành
`#C2340F` để nó khớp ô cam ở thanh trên. Ngưỡng 40 trên tổng sai lệch ba kênh là
đủ: nó bắt hết nền phẳng mà không đụng vào nét viền nâu.

## 5. Ô chữ T đã bị thay (2026-09-05)

Nay là `components/brand.tsx`, **một định nghĩa** cho cả ba chỗ dùng nó — thanh
trên, sidebar, chân trang.

Ba chỗ ấy trước đây là ba bản chép giống hệt nhau, và chúng **đã kịp trôi khỏi
nhau**: bản ở thanh trên mang một dòng comment giải thích vì sao bo góc vuông,
bản ở sidebar thì không, còn bản ở chân trang dùng `font-semibold` thay vì
`font-data`. Không ai thấy, vì không ai đặt ba cái cạnh nhau bao giờ.

Ảnh là `public/brand/mark.png` — **cắt sát hơn `icon.png`**. Bản kia chừa lề
rộng vì iOS và Android tự bo góc và tự thêm nền; ở đây 28 pixel nào cũng đắt, và
giữ nguyên lề ấy thì cái đầu chỉ còn 19px. Nguồn 128px đủ cho 28px ở màn hình 4×.

Đo ở đúng cỡ giao diện dùng: **28px và 24px đều đọc rõ** — mũ, kính, mặt, má hồng
tách bạch. Xa ngưỡng mờ 16px của §4.

`<img>` thường chứ không `next/image`, kèm `eslint-disable` — cùng lý lẽ và cùng
khuôn với `Avatar` ở `ui.tsx`: tài sản tĩnh, kích thước cố định, bộ tối ưu không
có gì để tối ưu ở một tệp 18 KB.
