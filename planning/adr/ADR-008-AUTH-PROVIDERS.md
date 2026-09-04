# ADR-008 — Đăng nhập bằng Google và Apple

**Trạng thái:** đã dựng (2026-08-22) · Google chạy thật được ở local, Apple chờ domain HTTPS
**Bối cảnh:** trước đó chỉ có email + mật khẩu (`POST /auth/login`)

---

## 1. Luồng phía máy chủ, không nhúng SDK

Cả Google lẫn Apple đều có SDK JavaScript nhúng được vào trang, và cả hai đều **bị loại**.

Lý do không phải sở thích. `CLAUDE.md` và `ROADMAP.md` P1-7b ghi một lời hứa: token còn nằm trong `localStorage` thay vì cookie httpOnly **vì ứng dụng này không có script bên thứ ba nào** và chỉ có đúng một `dangerouslySetInnerHTML` in ra một hằng số. Nhúng `accounts.google.com/gsi/client` là làm lý do đó hết hiệu lực ngay lập tức — và khi đó nợ P1-7b phải trả **trước** tính năng đang làm, chứ không phải sau.

> **Cập nhật 2026-09-04 (ADR-015).** Điều kiện hết hiệu lực nói ở trên **đã xảy ra**: Turnstile
> nhúng `challenges.cloudflare.com/turnstile/v0/api.js` vào các trang có form đăng nhập. Tiền đề
> "không script bên thứ ba nào" không còn đúng, và P1-7b chuyển thành nợ mở không còn lý lẽ —
> `ADR-015` §6 ghi lại sự đánh đổi ấy. Quyết định của mục này **không đổi**: nó không chỉ dựa
> vào tiền đề đó, và giao đường đăng nhập cho SDK của nhà cung cấp vẫn là một thay đổi lớn hơn
> hẳn việc đặt một ô kiểm cạnh form.

Nên luồng là mã uỷ quyền phía máy chủ: `/auth/{provider}/start` → chuyển hướng cả trang → nhà cung cấp → callback về API → API đổi mã lấy `id_token`, xác minh, rồi phát token của **chính hệ thống này**. Token của Google hay Apple không bao giờ đi tiếp vào ứng dụng; nó là bằng chứng danh tính cho đúng một lần đăng nhập.

## 2. `user_identity`, không phải cột `google_id`

Bảng riêng `(provider, subject)` thay vì thêm cột cho mỗi nhà cung cấp. Một cột mỗi bên nghĩa là mỗi nhà cung cấp mới là một migration trên bảng nóng nhất hệ thống, và một tài khoản dùng cả hai đường phải nhớ điền cả hai cột.

**Khoá tra cứu là `sub`, không phải email.** `sub` là định danh bền bên nhà cung cấp; email thì đổi được, và với Apple nó còn có thể là địa chỉ chuyển tiếp ẩn khác hẳn hộp thư thật. Tra theo email nghĩa là ai đổi email bên Google sẽ thành một người mới với hệ thống này, mất sạch lịch sử học.

`user_identity.email` giữ nguyên giá trị **lúc liên kết**, không đồng bộ lại: nó là bằng chứng cho quyết định liên kết đã xảy ra. Apple chỉ gửi email ở lần cấp quyền **đầu tiên**, nên một cột "luôn mới nhất" sẽ tự rỗng ở lần đăng nhập thứ hai mà không có gì báo.

## 3. `users.hashed_password` bỏ NOT NULL

Cách rẻ hơn là nhét một chuỗi băm rác vào cho tài khoản đăng nhập bằng nhà cung cấp — và đó chính là cái bẫy: hàng như thế trông y hệt tài khoản có mật khẩu, nên mọi phép hỏi "người này đặt mật khẩu chưa" đều trả lời sai.

Hai đường mật khẩu vì thế phải xử lý NULL, và **mỗi đường một kiểu**:

- `POST /auth/login` trả **thông báo chung** như khi sai mật khẩu. Nói "tài khoản này dùng Google" là xác nhận email nào có tài khoản ở đây và bằng đường nào — một máy dò tài khoản miễn phí. Lời nhắc đúng chỗ nằm ở trang đăng nhập, nơi mọi nút cùng hiện cho tất cả mọi người.
- `POST /auth/password` nói **thẳng**, vì tới đó danh tính đã được chứng minh. Nó cũng **không** phải chỗ đặt mật khẩu lần đầu: endpoint này chứng minh quyền bằng chính mật khẩu cũ, nên với tài khoản không có mật khẩu thì nó không chứng minh được gì.

## 4. Luật liên kết theo email

Chỉ gắn danh tính mới vào một tài khoản cùng email khi nhà cung cấp nói email **đã xác minh** *và* nó **không phải địa chỉ ẩn**. Gắn bừa theo email là một đường chiếm tài khoản có thật: ai tạo được một danh tính mang email của người khác sẽ vào thẳng tài khoản đó.

Email trùng mà không đủ điều kiện thì **từ chối kèm lối ra** ("đăng nhập bằng mật khẩu, rồi liên kết trong hồ sơ"), chứ không lặng lẽ tạo tài khoản thứ hai cùng email — `users.email` là UNIQUE nên nó cũng không tạo được.

Một chi tiết dễ làm hỏng cả luật này: **Apple gửi `email_verified` dạng chuỗi `"true"`, Google gửi boolean `true`.** Một phép so `is True` sẽ coi mọi tài khoản Apple là chưa xác minh, và luật liên kết im lặng ngừng hoạt động.

## 5. `state` và `nonce` trong Redis, fail **closed**

`state` chống CSRF, `nonce` chống phát lại `id_token` — hai thứ khác nhau, cần cả hai. Cất trong Redis, TTL 10 phút, và **đọc là xoá**: không xoá thì một URL callback bị ghi lại (lịch sử trình duyệt, log proxy, ảnh chụp màn hình) còn dùng lại được suốt thời gian sống của nó.

Đường này **fail closed** khi Redis hỏng, ngược hẳn với `rate_limit_anonymous`. Ở đó Redis hỏng mà chặn hết thì không ai đăng nhập được — một phụ thuộc mềm làm sập sản phẩm. Ở đây Redis là thứ **duy nhất** chứng minh callback thuộc về một lần bấm có thật; bỏ qua nó là bỏ luôn lớp chống CSRF mà `state` sinh ra để làm.

## 6. Token trả về qua **fragment**

Callback chuyển hướng về `{web}/auth/callback#token=…`. Fragment chứ không query: query đi vào log máy chủ, vào header `Referer` của mọi tài nguyên trên trang đích, và nằm đọc được trong lịch sử trình duyệt. Trang đích xoá fragment bằng `replaceState` ngay sau khi đọc.

Đây là cách **ít tệ nhất** khi token còn ở `localStorage`, không phải cách đúng. Ngày P1-7b được trả (cookie httpOnly), cả cơ chế này biến mất và callback đặt cookie thẳng.

`next` chỉ nhận đường dẫn nội bộ. Nhận URL tuyệt đối là dựng sẵn một open redirect, và nó tệ hơn bình thường ở đây: trang lừa đảo hiện ra **ngay sau một lần đăng nhập thật**, tức sau khi người dùng vừa được xác nhận rằng mọi thứ bình thường.

## 7. Bật/tắt bằng chính thông tin cấu hình

Không có cờ `enabled` riêng. Nhà cung cấp bật khi và chỉ khi có đủ biến của nó; thiếu thì endpoint trả **404** và `GET /auth/providers` không liệt kê nó, nên giao diện không hiện nút.

404 chứ không 503: 404 nói đúng sự thật — đường này không tồn tại ở bản triển khai này. 503 ngụ ý "có nhưng đang hỏng" và mời người ta thử lại một thứ sẽ không bao giờ chạy cho tới khi có người điền khoá.

---

## 8. Runbook: lấy thông tin ở đâu

### Google (chạy thật được ở local)

1. [Google Cloud Console](https://console.cloud.google.com/) → tạo project (hoặc dùng project sẵn có).
2. **APIs & Services → OAuth consent screen**: chọn *External*, điền tên ứng dụng, email hỗ trợ, email liên hệ. Khi còn ở chế độ *Testing*, thêm chính email của bạn vào **Test users** — nếu không, đăng nhập sẽ bị từ chối với thông báo về việc app chưa được xác minh.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**, loại **Web application**.
4. **Authorized redirect URIs** — thêm đúng chuỗi này, khớp từng ký tự:

   ```
   http://localhost:8000/api/v1/auth/google/callback
   ```

   Đây là chỗ sai phổ biến nhất của cả luồng, và triệu chứng là `redirect_uri_mismatch` hiện trên màn hình của Google chứ không phải trong log của ta.
5. Chép Client ID và Client secret vào `.env`:

   ```
   GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```
6. `docker compose up -d api` để nạp lại biến môi trường — **`restart` không đọc lại `.env`**, đây là cái bẫy đã ghi trong CLAUDE.md.

### Apple (cần domain HTTPS, không chạy được ở localhost)

Cần tài khoản Apple Developer trả phí. Apple **không nhận `localhost`** làm return URL, nên phần này chỉ bật được ở môi trường đã có domain thật.

1. [developer.apple.com](https://developer.apple.com/account) → **Certificates, Identifiers & Profiles**.
2. **Identifiers → +** → **App IDs**, bật *Sign in with Apple*. (Cần App ID trước, kể cả khi chỉ dùng web.)
3. **Identifiers → +** → **Services IDs** → tạo. Chuỗi này chính là `APPLE_CLIENT_ID`.
4. Chọn Service ID vừa tạo → **Configure**:
   - *Domains and Subdomains*: domain của API,
   - *Return URLs*: `https://<domain>/api/v1/auth/apple/callback`.
5. **Keys → +** → bật *Sign in with Apple* → tạo → **tải tệp `.p8`**. Tệp này **chỉ tải được MỘT lần**; mất là phải tạo khoá mới.
6. Điền `.env`: `APPLE_CLIENT_ID` (Service ID), `APPLE_TEAM_ID` (góc trên phải trang tài khoản), `APPLE_KEY_ID` (của khoá vừa tạo), `APPLE_PRIVATE_KEY` (toàn bộ nội dung `.p8`, giữ nguyên xuống dòng).

Lưu ý về "client secret" của Apple: nó **không phải một chuỗi Apple phát ra**. Đó là một JWT ký ES256 bằng khoá `.p8`, hạn tối đa 6 tháng, và `app/services/oauth.py` **tự sinh mới cho mỗi lần đổi mã**. Ký sẵn một chuỗi rồi cất vào `.env` cũng chạy — trong sáu tháng, rồi hỏng với triệu chứng "đăng nhập Apple không được" mà không có gì trong log nhắc tới ngày hết hạn.

---

## 9. Cố ý CHƯA làm

- **Gỡ liên kết / quản lý danh tính trong trang hồ sơ.** Cần khi một người có cả mật khẩu lẫn Google và muốn bỏ một cái. Chưa có màn hình nào, nên gỡ liên kết hiện chỉ làm được bằng SQL.
- **Đặt mật khẩu lần đầu cho tài khoản Google/Apple.** Cần một bằng chứng khác (email xác minh), tức là hạ tầng gửi mail — một tính năng riêng.
- **Đăng nhập không mật khẩu bằng email (magic link / OTP).** Cùng lý do: nó là hạ tầng gửi mail cộng một bảng token dùng một lần, không phải một biến thể của việc này.
