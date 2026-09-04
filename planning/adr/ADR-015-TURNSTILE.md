# ADR-015 — Cloudflare Turnstile ở cửa đăng ký và đăng nhập

Trạng thái: **đã quyết và đã dựng.** Tắt mặc định; bật bằng hai biến môi trường.
Ngày khảo sát: **2026-09-04**.

---

## 0. Câu hỏi thật, và vì sao câu trả lời hiển nhiên không dùng được

Yêu cầu là "tích hợp Cloudflare để bảo mật tốt hơn". Nhưng Cloudflare không phải
một thứ — nó là hai thứ, và chỉ một trong hai dùng được ở đây.

| | Cần gì | Dùng được hôm nay |
|---|---|---|
| **Proxy: chống DDoS, WAF, Bot Fight Mode, giấu IP gốc, CDN** | Một **tên miền riêng**, đổi nameserver sang Cloudflare | **Không** |
| **Turnstile: ô kiểm chống bot** | Không gì cả — nhúng vào trang bất kỳ | **Có** |

Phần proxy là phần người ta nghĩ tới khi nói "Cloudflare", và nó bị chặn bởi một
điều kiện kỹ thuật cứng: Cloudflare đòi apex domain nằm **ngay dưới một TLD hợp
lệ** và bạn phải trỏ được nameserver của nó. `*.vercel.app` và `*.onrender.com`
là tên miền của người khác. Không có cách nào lách.

Đây đúng là ràng buộc đã chặn R2 suốt từ trước (`ADR-006` §2.8a,
`PHASE2-AUDIO.md` §A4). Nên nó không phải một phát hiện mới, mà là **cùng một
tên miền chưa mua đang chặn thêm một thứ nữa** — và đó là dữ kiện đáng giá nhất
của tài liệu này: giá trị của việc mua một tên miền vừa tăng lên, vì bây giờ nó
mở khoá ba thứ chứ không phải một.

## 1. Turnstile giải quyết đúng cái lỗ mà mã nguồn tự nhận là có

Không phải "thêm một lớp bảo mật cho chắc". `app/api/routes/auth.py` đã viết sẵn
lời thú nhận, từ trước khi có tài liệu này:

> Nó KHÔNG chặn được botnet xoay IP. Chống dò mật khẩu thật sự cần đếm theo tài
> khoản, mà đếm theo tài khoản lại mở đường khoá tài khoản người khác.

Đó là một thế lưỡng nan thật:

- **Đếm theo IP** — cái đang có. Ở Việt Nam mạng di động chạy CGNAT, nên hạn mức
  phải rộng (60 lần / 10 phút), và một botnet đổi IP đi qua như không có gì.
- **Đếm theo tài khoản** — chặn được botnet, nhưng ai cũng khoá được tài khoản
  của người khác chỉ bằng cách gõ sai mật khẩu vài lần. Đổi một lỗ lấy một lỗ.

Turnstile không đếm gì cả. Nó bắt **mỗi lần gửi form phải trả một cái giá tính
toán ở trình duyệt**. Đổi IP không làm cái giá đó rẻ đi, và người dùng thật
không bị tính chung hạn mức với người ngồi cùng đường mạng. Đó là lối ra thứ ba
của thế lưỡng nan, và là lý do duy nhất đủ để dựng cái này.

Nó **không thay** bộ rate limit. Hai thứ chặn hai loại tấn công khác nhau, và
mục §3 dưới đây phụ thuộc vào việc cả hai cùng còn.

## 2. Bật khi và chỉ khi có đủ cả hai khoá

Cùng luật với nhà cung cấp đăng nhập (`ADR-008` §4): thiếu biến môi trường thì
tính năng **tắt**, không phải hỏng. Nhờ đó dev, CI và bộ e2e chạy y như trước.

Nhưng ở đây có thêm một luật mà OAuth không cần: **một nửa cấu hình thì API từ
chối khởi động.** Hai nửa hỏng theo hai kiểu, và kiểu thứ nhất không có triệu
chứng nào cả:

- **Chỉ có site key** → trang vẽ ô kiểm, máy chủ không kiểm. Mọi request thành
  công, ô kiểm hiện ra xanh lè, và hàng rào không tồn tại. Không log nào, không
  lỗi nào, không ai biết cho tới ngày bị tấn công.
- **Chỉ có secret** → máy chủ đòi token mà không chỗ nào phát ra. Không ai đăng
  nhập được nữa. Ầm ĩ, nhưng vẫn phải nổ sớm.

Vì cái thứ nhất im lặng nên cả hai bị bắt cùng một chỗ: `_reject_half_configured_turnstile`
trong `config.py`, cùng khuôn với `_reject_default_secret_in_production`.

**Site key do máy chủ phát ra** (`GET /auth/turnstile`, 204 khi tắt), không phải
do web đọc biến `NEXT_PUBLIC_` của riêng nó. Khoá này công khai theo thiết kế —
nó nằm trong HTML — nên không có gì phải giấu; lý do là **một nguồn sự thật**.
Hai bên đọc hai biến riêng thì sẽ có ngày chúng lệch nhau, và cái lệch ấy rơi
đúng vào kiểu hỏng im lặng vừa nói. Phần thưởng kèm theo: bật Turnstile lên
không cần build lại bản web.

## 3. Hỏng thì MỞ, chối thì ĐÓNG

Đây là quyết định dễ bị "sửa" ngược nhất trong cả tài liệu, nên lý lẽ ghi ở đây
và lặp lại ngay trên hàm.

- Cloudflare trả lời "không" → **chặn**.
- Không *hỏi được* Cloudflare — mạng chập, hết giờ chờ, phía họ 5xx → **cho qua**,
  ghi một dòng cảnh báo.

Đóng lại nghe an toàn hơn. Nhưng nó biến một sự cố của Cloudflare thành một sự
cố **của mình**: không ai đăng nhập được nữa. Đó đúng là lựa chọn mà
`rate_limit_anonymous` đã cân nhắc và ghi ra khi Redis chết — một phụ thuộc mềm
không được phép kéo sập sản phẩm.

Và cái giá của việc mở thì **đo được**: trong lúc Cloudflare hỏng, hàng rào tụt
về đúng mức bảo vệ của hôm qua — rate limit theo IP vẫn chạy — chứ không tụt về
không. Đó là lý do §1 nói "không thay" chứ không phải "thay".

Lý lẽ này đứng được **chỉ vì kẻ tấn công không điều khiển được đường mạng ra của
máy chủ ta**. Ngày nào Turnstile bị đặt sau một thứ mà người ngoài chọc hỏng
được, nó hết hiệu lực.

## 4. Token dùng một lần, và đó là thứ định hình cả giao diện

Token Turnstile sống 5 phút và Cloudflare **chỉ nhận mỗi cái đúng một lần**.
Điều đó va vào hai chỗ có thật:

- Trang đăng ký gọi liền `POST /register` rồi `POST /login` — **hai lần gửi cho
  một lần bấm nút**, vì `register` trả `UserPublic` chứ không trả token.
- Gõ sai mật khẩu rồi gửi lại là một lần nữa, ở đúng cái form hay bị gõ sai nhất.

Nên `useTurnstile()` không phát ra "cái token". Nó phát ra `take()`: mỗi lần gọi
trả về một token **còn dùng được**, tự `reset()` ô kiểm và đợi cái mới khi cái cũ
đã tiêu. Thiết kế ngược lại — giữ một token trong state rồi dùng lại — cho ra
một lỗi 403 khó hiểu ở ngay chỗ người dùng vừa gõ đúng mật khẩu.

Cũng vì thế **403 ở đây không có nghĩa "người này là bot"**, và lời từ chối phải
nói đúng như vậy: *"Xác minh chống bot đã hết hạn. Thử lại lần nữa."* — không
buộc tội ai cả.

## 5. Cái giá, nói thẳng

- **~0,5 giây mỗi lần đăng ký hoặc đăng nhập.** Đo tại máy ngày 2026-09-04:
  register 1002 ms, login 517 ms, so với vài chục ms trước đó. Đó là một vòng
  mạng ra `challenges.cloudflare.com` nằm thẳng trên đường xác thực.
- **Cổng đứng SAU rate limit trong danh sách `dependencies`, và thứ tự đó có
  nghĩa.** Rate limit là một phép đếm trong Redis; cổng này là một vòng mạng đi
  ra. Đảo lại thì một trận lụt request biến thành một trận lụt request **đi ra**,
  tức là ta tự trả tiền băng thông cho kẻ tấn công.
- **Một script bên thứ ba, và nó tiêu một món nợ đã được ghi trước** — xem §6.
- Bộ e2e chạy với Turnstile **tắt**. Nghĩa là đường có-bật không được e2e phủ;
  nó được phủ bằng `tests/test_turnstile.py`, trong đó có cả bài ghim chiều
  "hỏng thì mở" của §3 — đúng cái dễ bị sửa ngược nhất.

## 6. Món nợ P1-7b: lý do hoãn đã hết hiệu lực

`ADR-008` §1 viết ra một lời hứa, và bây giờ phải trả nó:

> Token còn nằm trong `localStorage` thay vì cookie httpOnly **vì ứng dụng này
> không có script bên thứ ba nào**. […] Nhúng `accounts.google.com/gsi/client`
> là làm lý do đó hết hiệu lực ngay lập tức — và khi đó nợ P1-7b phải trả
> **trước** tính năng đang làm, chứ không phải sau.

Tài liệu này nhúng `challenges.cloudflare.com/turnstile/v0/api.js`. Tiền đề
"không script bên thứ ba nào" **không còn đúng**, nên P1-7b chuyển từ *hoãn có lý
do viết ra* sang **nợ đang mở, không còn lý lẽ nào chống đỡ**.

Ghi ra hai điều thu hẹp phạm vi, nhưng **không** điều nào cứu lại tiền đề:

- Script chỉ tải trên các trang có form đăng nhập (`/login`, `/register`, và hộp
  thoại chặn ở khu luyện thi), không phải mọi trang. Nhưng đó **đúng là những
  trang ghi token**, tức là chỗ đắt nhất.
- Đây là script của một nhà cung cấp bảo mật, không phải một widget quảng cáo.
  Điều đó đổi *xác suất*, không đổi *mô hình mối đe doạ* — mà tiền đề đã ghi là
  một câu khẳng định tuyệt đối, không phải một ước lượng rủi ro.

Quyết định: **dựng Turnstile trước, và ghi P1-7b thành nợ mở không còn lý lẽ**
(`ROADMAP.md` §4). Đây là một sự đánh đổi có ý thức, không phải một chỗ bỏ sót:
lỗ botnet xoay IP ở §1 là thứ đang mở với mọi người trên Internet ngay lúc này,
còn P1-7b là thứ chỉ thành vấn đề *nếu* có một lỗ XSS. Nhưng thứ tự mà ADR-008
yêu cầu đã bị đảo, và tài liệu này nói ra điều đó thay vì im lặng.

## 7. Việc bên ngoài repo

Ở `dash.cloudflare.com` → Turnstile → Add widget (miễn phí, không cần thẻ):

1. **Hostname**: thêm cả tên miền production lẫn `localhost` nếu muốn thử tại
   máy. Gói free cho tối đa 20 widget, mỗi widget 10 hostname.
2. **Mode**: `Managed`. Cloudflare tự quyết có bắt bấm hay không theo mức rủi ro.
3. Chép Site Key và Secret Key vào `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY`
   trên Render, rồi **`up -d` chứ không `restart`** — `env_file` chỉ áp lúc *tạo*
   container.

Khoá thử của Cloudflare, dùng được ngay mà không cần tài khoản nào (đã ghi cả ở
`.env.example`):

| | Site key | Secret key |
|---|---|---|
| Luôn qua | `1x00000000000000000000AA` | `1x0000000000000000000000000000000AA` |
| Luôn từ chối | `2x00000000000000000000AB` | `2x0000000000000000000000000000000AA` |

Kiểm nhanh rằng cổng thật sự bay tới Cloudflare, chứ không chỉ trông như thế —
đặt secret **luôn từ chối** rồi:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/api/v1/auth/register \
  -H 'content-type: application/json' -H 'cf-turnstile-response: XXXX.DUMMY.TOKEN.XXXX' \
  -d '{"email":"x@example.com","password":"mat-khau-du-dai-123"}'
```

403, và log API có một dòng `turnstile rejected a token: ['invalid-input-response']`.
Đặt secret **luôn qua** mà vẫn 403 nghĩa là request chưa hề ra tới Cloudflare.

## 8. Còn lại gì khi có tên miền

Không thuộc phạm vi lần này, ghi ra để lần sau không phải khảo sát lại. Gói free
của Cloudflare, sau khi trỏ nameserver:

- **Chống DDoS L3/L4/L7** không giới hạn — thứ đáng giá nhất, và là thứ duy nhất
  đứng giữa một container 512 MB / 0.1 CPU và một trận lụt.
- **Free Managed Ruleset** của WAF — một tập con của bộ đầy đủ, không sửa được
  hành vi từng luật, không có OWASP Core Ruleset.
- **Bot Fight Mode** (bản cơ bản; `Super` cần trả tiền).
- **Rate limiting: đúng MỘT luật**, đếm theo IP, cửa sổ cố định 10 giây. Hẹp hơn
  bộ rate limit đang có trong ứng dụng, nên nó bổ sung chứ không thay thế.
- Universal SSL, giấu IP gốc, CDN cho tài nguyên tĩnh.

**Một cái bẫy phải xử lý cùng lúc với việc trỏ nameserver, và nó hỏng im lặng:**
`client_ip()` đọc **hop cuối** của `X-Forwarded-For`. Sau Cloudflare, hop cuối là
IP **của Cloudflare**, nên cả thế giới dùng chung một khoá rate limit và hạn mức
biến thành hạn mức toàn hệ thống — không lỗi nào, chỉ là bỗng nhiên người dùng
thật bị chặn. Lúc đó `client_ip` phải đọc `CF-Connecting-IP` trước, và chỉ tin
header ấy khi request thật sự đến từ dải IP của Cloudflare.
