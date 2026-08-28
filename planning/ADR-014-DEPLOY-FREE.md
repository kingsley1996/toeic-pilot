# ADR-014 — Lên production trên gói miễn phí, không có thẻ tín dụng

Trạng thái: **đã quyết, chưa dựng.** ROADMAP §8 mang trạng thái thật.

Ràng buộc không phải "rẻ" mà là **"không có phương tiện thanh toán"**. Hai thứ
đó nghe giống nhau và loại ra hai tập nhà cung cấp khác hẳn nhau: gần như mọi
gói free đáng dùng của năm 2026 đều giữ thẻ để chống lạm dụng, kể cả khi không
bao giờ trừ tiền. Tài liệu này chọn trong phần còn lại.

Ngày khảo sát: **2026-08-28**. Mọi con số dưới đây đều có hạn sử dụng — xem §10.

---

## 0. Vì sao đây là một tài liệu ngắn, chứ không phải một danh sách thoả hiệp

Câu hỏi phải trả lời trước: **triển khai miễn phí bắt kiến trúc phải nhượng bộ
những gì?** Trả lời: không gì cả. Và đó không phải may mắn — bốn quyết định đã
chốt từ trước đúng bằng lý do khác nay trả cổ tức ở đây:

| Quyết định đã có | Vì sao nó cứu chỗ này |
|---|---|
| Nhà cung cấp lưu trữ là **biến môi trường, không phải nhánh code** (ADR-006 §2.8) | Đổi sang Supabase là điền bốn dòng, không phải sửa một dòng mã |
| **API không bao giờ phục vụ byte media** (A4.1, ADR-006 §2.9) | 94 MB audio không đi qua tiến trình HTTP, nên 512 MB RAM và 0.1 CPU là đủ |
| **Worker là ảnh riêng** có ffmpeg và extra `content` | Production không cần ffmpeg, không cần mạng ra ngoài, không cần chạy worker nào |
| **Redis là phụ thuộc mềm** (`/ready` báo `degraded`, không 503) | Hạn mức Redis cạn giữa tháng thì sản phẩm chậm đi chứ không sập |

Nếu bốn điều trên chưa có sẵn thì tài liệu này sẽ dài gấp ba và mỗi mục là một
lần cắt bớt tính năng.

---

## 1. Phân bổ

| Thành phần | Nơi chạy | Hạn mức gói free | Thẻ |
|---|---|---|---|
| Web (Next.js) | **Vercel** Hobby | 100 GB truyền, 1 M request | không |
| API (FastAPI) | **Render** web service | 750 giờ/tháng, 512 MB, 0.1 CPU | không |
| Postgres + pgvector | **Supabase** | 500 MB | không |
| Audio | **Supabase Storage** (driver `s3`) | 1 GB, egress 5 GB/tháng | không |
| Ảnh | **Cloudinary** | 25 GB | không |
| Redis | **Upstash** | 256 MB, 500 K lệnh/tháng | không |
| Giữ thức | **UptimeRobot** hoặc cron-job.org | chu kỳ 5 phút | không |

**Hai worker không triển khai.** `tts_worker` và `skilltag_worker` là công cụ
của máy soạn nội dung; `push_media` đẩy audio sinh sẵn lên object store từ máy
dev. Đó vốn là chủ ý của A4.1 chứ không phải một sự cắt giảm vì tiền.

---

## 2. Ứng viên bị loại, và lý do đo được

Ghi lại để lần sau không phải khảo sát lại — và để thấy vì sao danh sách còn
lại ngắn đến thế.

| Ứng viên | Lý do loại |
|---|---|
| **Render Postgres** | Gói free **hết hạn sau 30 ngày**, rồi 14 ngày ân hạn trước khi xoá. Đó là một bản demo, không phải một cơ sở dữ liệu. Chính điều này ép DB ra khỏi Render. |
| **Render Key Value** (Redis của chính Render) | Gói free **chỉ nằm trong bộ nhớ, mất sạch mỗi lần khởi động lại**. Thứ hỏng là danh sách thu hồi token: sau mỗi lần restart, mọi `jti` đã thu hồi biến mất và **"Đăng xuất" âm thầm thôi thu hồi**. Không có lỗi nào để bắt — Redis vẫn khoẻ, `EXISTS` trả 0, và mã đã cố ý *fail open* nên cũng không cảnh báo. Đúng thứ Upstash tồn tại để tránh. |
| **Hugging Face Spaces** | Docker Space nay **bắt buộc gói PRO**. Trước kia là lựa chọn mạnh nhất (2 vCPU, 16 GB, không thẻ); không còn. |
| **Koyeb** | Giữ $29 để xác minh thẻ, và tầng Starter đã đóng với người đăng ký mới sau khi công ty bị mua lại. |
| **Fly.io, Railway, Google Cloud Run, Oracle Always Free, Cloudflare R2** | Đều yêu cầu thẻ. Oracle chỉ giữ $1 và không trừ, nhưng ràng buộc là *không có thẻ*, không phải *không mất tiền*. |
| **PythonAnywhere** | Không chạy ASGI, và gói free chặn kết nối ra ngoài tới host tuỳ ý. |

---

## 3. Ba quyết định bắt buộc, cả ba hỏng im lặng

### 3.1 Session pooler cổng 5432 — không phải transaction pooler 6543

Kết nối trực tiếp của Supabase nay **chỉ có IPv6**, còn Render free chỉ có
IPv4, nên bắt buộc đi qua Supavisor. Có hai cổng và chọn nhầm thì hỏng muộn:

- **6543 (transaction)** không hỗ trợ prepared statement, mà `psycopg[binary]`
  tự bật chúng sau vài lần thực thi cùng một câu lệnh. Nghĩa là ứng dụng chạy
  đúng lúc mới lên rồi đổ ở lần gọi thứ sáu của một truy vấn — kiểu hỏng không
  bao giờ trùng với lần triển khai gây ra nó.
- **5432 (session)** giữ nguyên mọi tính năng Postgres và là thứ Alembic cần ở
  entrypoint.

Chọn 5432. Nếu một ngày buộc phải dùng 6543 thì phải tắt prepared statement ở
chuỗi kết nối, và ghi lý do ngay tại đó.

### 3.2 `/ready` là cái chuông giữ sống cả ba dịch vụ

Ba mối nguy độc lập, cùng một cách xử lý:

| Dịch vụ | Ngủ khi nào | Hậu quả |
|---|---|---|
| Render free | 15 phút không traffic | Khởi động lạnh ~50 giây |
| Supabase free | **7 ngày** không request | Ngủ hẳn, phải vào bấm tay |
| Upstash | không hoạt động kéo dài | Thu hồi tài nguyên |

`/ready` đã chạy `SELECT 1` trên Postgres và `ping` lên Redis, nên **một cái
ping 5 phút một lần vào đúng endpoint ấy đánh thức cả ba** và đồng thời xác
nhận cả ba còn sống. Không dựng thêm gì.

Kiểu hỏng của Supabase đặc biệt khó chẩn đoán nếu bỏ qua mục này: web chạy,
Postgres chạy, chỉ audio 404 — vì storage ngủ theo project. Cảnh báo đó đã nằm
sẵn trong `.env.example`.

### 3.3 Ngân sách giờ chỉ dư sáu tiếng

750 giờ/tháng, mà tháng 31 ngày có **744 giờ**. Một service thức suốt vừa khít
và **không còn chỗ cho bất kỳ service free thứ hai nào** trong cùng workspace —
kể cả một bản staging dựng "chỉ để thử". Muốn có biên, hẹn pinger chạy trong
khung giờ thức (07:00–24:00 ≈ 527 giờ/tháng); ngoài khung ấy khách đầu tiên chịu
một lần khởi động lạnh.

### 3.4 Region của Supabase phải khớp region của Render

Đo ngày 2026-08-28, từ máy ở Việt Nam tới Supabase đặt ở `ap-northeast-1` (Tokyo):
**117 ms một truy vấn**, so với **0,1 ms** tới Postgres trong máy. Chậm hơn một
nghìn lần, và cái giá không nằm ở một truy vấn mà ở việc **nhân với số truy vấn
của mỗi trang**: `/profile/stats` tốn 1 765 ms, tức khoảng mười lăm vòng.

Không endpoint nào chậm vì nó viết tệ. Chúng chậm vì mỗi vòng phải bay qua biển.

Nên region không phải một ô chọn cho tiện. Render free chỉ có Oregon, Frankfurt,
Ohio và **Singapore** — không có Tokyo. Đặt Supabase ở Tokyo là tự chuốc lấy một
chặng xuyên vùng vĩnh viễn cho mọi truy vấn. **Cả hai phải là Singapore.**

Đổi region thì phải tạo project Supabase mới — Supabase không di chuyển project.
Nghĩa là việc này **rẻ lúc chưa có người dùng và đắt dần về sau**, nên nếu định
đổi thì đổi sớm.

**Quyết định thực tế (2026-08-28): giữ Tokyo.** Cái giá được cân nhắc rồi chấp
nhận — Render ở Singapore, Supabase ở Tokyo, khoảng 70 ms mỗi truy vấn thay vì
~5 ms nếu cùng vùng. Ghi ra đây để lần sau không ai đọc mục này rồi tưởng là
cấu hình đặt nhầm. Muốn đổi thì quy trình đã có và đã kiểm: `export-content.sh`
→ project mới → `import-content.sql` → `content.sql` → `push_media`.

Ngưỡng nên xét lại: khi một trang bất kỳ vượt **2 giây** vì số vòng truy vấn,
hoặc khi có người dùng thật ở xa phàn nàn về tốc độ.

---

## 4. Hạn mức nào chạm trước — đo, không đoán

| Hạn mức | Sức chứa | Mức dùng hôm nay | Ai chạm trước |
|---|---|---|---|
| Upstash 500 K lệnh/tháng | ~16 000 request có xác thực mỗi ngày | pinger tốn 8 640/tháng | **cái này** |
| Supabase Storage 1 GB | — | 94 MB, 3 995 tệp | rộng |
| Supabase egress 5 GB/tháng | ~2 500 phiên học | — | thứ nhì |
| Supabase DB 500 MB | — | 38 bảng, ~300 từ, 55 câu hỏi | rất rộng |
| Vercel 100 GB truyền | — | — | không bao giờ |

Con số Redis đến từ một sự thật kiểm được trong mã, không phải ước lượng:
`get_current_user` gọi **đúng một lệnh `EXISTS`** cho mỗi request đã đăng nhập,
để hỏi danh sách thu hồi token. Rate limiter chỉ chạm vào các endpoint auth.

Nghĩa là **hạn mức đáng theo dõi đầu tiên là Redis, không phải băng thông** —
ngược với trực giác thông thường về một ứng dụng nhiều audio, và ngược đúng vì
API không phục vụ byte audio nào (§0).

---

## 5. Cái giá, nói thẳng

- **Đăng nhập Apple không bật được.** Apple chỉ nhận domain HTTPS mình sở hữu,
  `*.onrender.com` thì không. Google chạy bình thường. ADR-008 đã lường: thiếu
  biến thì `/auth/apple/start` trả 404 và giao diện không hiện nút, nên không có
  gì hỏng — chỉ là một nửa tính năng nằm ngoài tầm cho tới khi có domain thật.
- **Vercel Hobby cấm dùng thương mại.** Hôm nay là dự án cá nhân nên hợp lệ.
  Ngày TOEIC Pilot thu tiền, giấy phép ấy hết hiệu lực **trước** khi chạm bất kỳ
  hạn mức kỹ thuật nào — và đó là một sự cố pháp lý, không phải một cảnh báo
  dùng quá.
- **512 MB và 0.1 CPU là chậm thật.** Không phải chậm trên giấy.
- **Khởi động lạnh ~50 giây** mỗi khi pinger hỏng, mà pinger hỏng thì không ai
  báo.

---

## 6. Biến môi trường phải đổi

Không có thay đổi mã nào trong danh sách này — đó là điểm của §0.

```
ENVIRONMENT=production
SECRET_KEY=<openssl rand -hex 32>          # mặc định sẽ bị từ chối khởi động
DATABASE_URL=postgresql+psycopg://...@aws-0-<region>.pooler.supabase.com:5432/postgres
REDIS_URL=rediss://...upstash.io:6379      # rediss, có TLS
CORS_ORIGINS=["https://<app>.vercel.app"]
WEB_BASE_URL=https://<app>.vercel.app
OAUTH_CALLBACK_BASE_URL=https://<api>.onrender.com

AUDIO_STORAGE_DRIVER=s3
AUDIO_PUBLIC_BASE_URL=https://<ref>.supabase.co/storage/v1/object/public/<bucket>
S3_ENDPOINT_URL=https://<ref>.supabase.co/storage/v1/s3
S3_REGION=<region>
S3_BUCKET=<bucket>

IMAGE_STORAGE_DRIVER=cloudinary
IMAGE_PUBLIC_BASE_URL=https://res.cloudinary.com/<cloud>/image/upload
CLOUDINARY_CLOUD_NAME / _API_KEY / _API_SECRET
```

**Khoá ghi S3 không thuộc về môi trường của API.** Chỉ `push_media` chạy ở máy
dev cần chúng; API chỉ nối chuỗi để tạo URL phát. Đặt chúng vào Render là mở
rộng phạm vi rò rỉ mà không đổi lại được gì (ADR-006 §2.8a).

---

## 7. Đường dựng: API đi bằng ảnh dựng sẵn, web thì không

Hai nửa của hệ thống lên production theo hai cách khác nhau, và sự bất đối xứng
ấy là bắt buộc chứ không phải bỏ dở.

### 7.1 API — CI dựng ảnh, Render chỉ kéo về chạy

Render dựng được từ `docker/api.Dockerfile`, nhưng **CI đã dựng đúng ảnh đó rồi
và còn khởi động nó** (job `docker`). Để Render dựng lại là dựng hai lần từ cùng
một Dockerfile, và tệ hơn thế: **thứ chạy ở production khi ấy chưa từng được ai
khởi động thử**. Job `docker` tồn tại chính vì P0-2 từng cho ra một ảnh build
sạch mà chạy thì chết — rồi lại để production dùng một ảnh khác với ảnh đã kiểm
là bỏ đi phần lớn giá trị của nó.

Nên: CI đẩy ảnh lên **GHCR**, Render trỏ vào tag đó. Repo là public nên GHCR
miễn phí, ảnh để public thì Render **không cần khoá registry nào**, và GitHub
Actions không giới hạn phút với repo public.

Một chi tiết phải biết trước: **service kiểu ảnh KHÔNG tự deploy lại khi có tag
mới**. Phải gọi deploy hook — một URL Render cấp — ở bước cuối của CI. Không có
bước ấy thì ảnh mới nằm im trong registry và không ai báo gì cả; production cứ
chạy bản cũ và mọi thứ trông hoàn toàn bình thường.

Đổi lại được ba thứ: một định nghĩa build thay vì hai, ảnh chạy đúng là ảnh đã
kiểm, và phần dựng chuyển khỏi máy build chậm của gói free.

### 7.2 Web — Vercel không chạy container

Không phải hạn chế của gói free: **Vercel không nhận ảnh Docker ở bất kỳ gói
nào.** Nó dựng Next.js theo đường riêng của nó.

Còn chuyển web sang Render để "Docker cho cả hai" thì đụng thẳng §3.3: 750 giờ
free mỗi tháng, tháng 31 ngày cần 744 giờ cho **một** service thức suốt. Hai
service là 1 488 giờ — gấp đôi ngân sách. Đồng dạng cho một container chạy cả
hai tiến trình: Next server (~200 MB) cộng uvicorn (~200 MB) nằm sát trần 512 MB,
và nó gộp lại đúng hai thứ kiến trúc đang giữ tách.

Nói cách khác, **cái làm cả phương án này khả thi chính là việc web không chạy
bằng Docker**. Vercel là chỗ duy nhất trong bảng §1 không tiêu giờ của ai.

### 7.3 Phần "gọn" của web nằm ở chỗ khác

Thứ đáng dọn không phải công nghệ dựng mà là **lệnh dựng nằm trong ô cấu hình
trên dashboard**. Một lệnh chỉ tồn tại trong giao diện web của nhà cung cấp thì
không nằm trong git, không ai review, và không có gì nhắc khi nó sai.

Chuyển nó vào repo: Vercel ưu tiên script `vercel-build` trong `package.json`
của thư mục gốc dự án, nên

```json
"vercel-build": "cd ../.. && pnpm turbo build --filter=@toeic-pilot/web"
```

trong `apps/web/package.json` thay hẳn ô ấy. Bắt buộc đi qua turbo vì
`packages/shared/package.json` trỏ `main` vào `./dist/index.js` — `next build`
một mình không dựng `dist`, và cái hỏng ra là lỗi import chứ không phải một câu
nói rằng thiếu bước build.

---

## 8. Runbook

1. **Supabase** — tạo project, bật extension `vector`, tạo bucket **public** cho
   audio, lấy khoá S3 ở *Project Settings › Storage › S3 access keys*. Lấy chuỗi
   kết nối ở tab **Session pooler** (§3.1).
2. **Upstash** — tạo Redis database, chép URL `rediss://`.
3. **Cloudinary** — lấy ba khoá.
4. **Đẩy media** từ máy dev: `uv run python -m app.content.push_media --dry-run`
   rồi chạy thật.
5. **CI — đã dựng sẵn.** Lần đẩy đầu tiên lên `main` sinh ra
   `ghcr.io/kingsley1996/toeic-pilot-api` với hai tag: `main` (thứ Render trỏ
   vào) và `<sha>` (để truy được bản nào đang chạy). Vào *Packages* của repo đổi
   package sang **public**, để Render khỏi cần khoá registry nào.
6. **Render** — Web Service kiểu **Existing Image**, trỏ vào `…-api:main`, điền
   biến ở §6. `api-entrypoint.sh` tự chạy `alembic upgrade head` trước khi uvicorn
   nghe cổng. Lấy **deploy hook** rồi đặt nó thành secret `RENDER_DEPLOY_HOOK`
   của repo — chưa có secret thì CI vẫn đẩy ảnh và chỉ ghi một `::warning::`, vì
   một hook chưa cấu hình không phải lý do để đánh đỏ cả nhánh.
7. **Đem nội dung lên** (§10). Schema vừa được `alembic upgrade head` dựng ở
   bước 6, giờ nạp dữ liệu vào:
   ```
   ./scripts/export-content.sh
   docker run --rm -i postgres:17 psql "$SUPABASE_URL" -q -v ON_ERROR_STOP=1 < scripts/import-content.sql
   docker run --rm -i postgres:17 psql "$SUPABASE_URL" -q -v ON_ERROR_STOP=1 < content.sql
   ```
8. **Vercel** — Root Directory `apps/web`. **Không điền Build Command**: script
   `vercel-build` đã có trong `apps/web/package.json` và Vercel ưu tiên nó (§7.3).
   Đặt `NEXT_PUBLIC_API_URL` **lúc build**, không phải lúc chạy.
9. **UptimeRobot** — theo dõi `https://<api>.onrender.com/ready`, chu kỳ 5 phút.
10. Sửa lại `CORS_ORIGINS` và `WEB_BASE_URL` bằng domain Vercel thật, rồi
   deploy lại Render.
11. **Tự phong admin.** Đăng ký một tài khoản bình thường trên web, rồi ở SQL
   Editor của Supabase chạy `update users set role = 'admin' where email = '…';`
   và đăng nhập lại (vai trò nằm trong token). Không có script nào làm việc này
   và đó là chủ ý — `register` cố ý không cho chọn vai trò, vì một đăng ký tự
   chọn được vai trò thì không phải hệ phân quyền.

`docker/web.Dockerfile` **không dùng ở đây** — nó là ảnh dev (`NODE_ENV=development`,
`pnpm dev`). Vercel dựng thẳng từ nguồn.

---

## 9. Cố ý KHÔNG làm

- **Không chạy worker nào trên production.** Sinh audio ở máy soạn nội dung rồi
  đẩy lên. Dựng worker ở đây sẽ mang ffmpeg, edge-tts và một lần gọi mạng vào
  môi trường phục vụ request — đúng thứ ảnh riêng ở A4.1 tồn tại để ngăn.
- **Không phục vụ media qua FastAPI** để né việc dựng object store. Mount tĩnh
  `/media` chỉ bật khi `environment == "development"`, và luật đó không được nới
  ra vì lý do triển khai.
- **Không dùng transaction pooler** để "tiết kiệm kết nối". Xem §3.1.
- **Không đưa khoá ghi S3 vào API.** Xem §6.
- **Không dựng lại ảnh API ở phía Render.** Xem §7.1 — thứ chạy phải là thứ
  CI đã khởi động thử.
- **Không đưa web vào Docker để cho đồng bộ.** Xem §7.2; nó tốn gấp đôi ngân
  sách giờ và đổi lại đúng một cảm giác gọn gàng.
- **Không tự động hoá việc dựng hạ tầng** (Terraform, script tạo project).
  Toàn bộ việc này làm **một lần**; một script chạy một lần là mã phải bảo trì
  đổi lấy đúng con số không lần chạy thứ hai.

---

## 10. Đem dữ liệu lên: nội dung, không phải lịch sử học

Database dev **không** được bê nguyên lên. Đo ngày 2026-08-28: **1 606 tài khoản,
1 581 trong đó có timestamp trong email** — rác do e2e sinh ra, mỗi lần chạy một
mẻ. Kéo theo chúng là 19 869 hàng `ai_interaction`, 3 435 `ruby_event`,
2 797 `attempt_item`, 1 362 `dictation_attempt`. Đem hết lên nghĩa là production
khai trương với một nghìn năm trăm tài khoản giả.

Cũng không nên đem tài khoản thật: mật khẩu ở máy dev là mật khẩu dev, và
`users.hashed_password` đi theo nguyên vẹn. Admin của production dựng mới ở §8
bước 11.

### 10.1 Lằn ranh đã nằm sẵn trong schema

Không phải một danh sách phải nghĩ ra và bảo trì. Hỏi catalog một câu là ra:

| Loại cột | Bảng | Ràng buộc |
|---|---|---|
| `created_by`, `published_by`, `reviewed_by`, `updated_by` | nội dung | **nullable** |
| `user_id` | lịch sử một người học | **NOT NULL** |

Không có ngoại lệ nào trong 45 khoá ngoại trỏ vào `users`. Nên quy tắc là: bảng
nào có `user_id` NOT NULL thì bỏ; bảng nội dung thì giữ và **gán NULL cho cột
tác giả** — nội dung ở production không thuộc về một tài khoản dev nào.

`scripts/export-content.sql` suy ra cả hai danh sách từ `pg_constraint` chứ
không gõ tay, nên thêm một bảng về sau nó tự biết bảng ấy thuộc phía nào. Ba
bảng con (`attempt_item`, `attempt_part`, `coach_message`) đi theo bằng
`CASCADE` mà không cần ai nhớ tới chúng.

### 10.2 Schema do Alembic dựng, dữ liệu nạp sau

Dump cả schema lẫn dữ liệu là sai ở đây, vì schema dev **không** bằng schema
Alembic: container `api` chạy `metadata.create_all` mỗi lần reload, và
`tests/test_concurrency.py` cũng vậy. Bê nó lên là bê luôn phần trôi dạt ấy vào
production.

Nên: Render khởi động, `alembic upgrade head` dựng schema chuẩn, rồi mới nạp
`pg_dump --data-only`. Kết quả đã kiểm bằng cách chạy đủ vòng ở máy — 33 bảng,
số hàng khớp tuyệt đối giữa nguồn và đích.

### 10.3 `alembic upgrade head` KHÔNG để lại schema rỗng

Chỗ này chỉ lộ ra khi chạy thật, và nó làm việc nạp **dừng giữa chừng**: migration
`027` seed một hàng `backdrop_setting`, `041`+`047` seed 45 hàng `pet_species`.
Bản dump đụng khoá chính, `psql` dừng ở đó, và **mọi bảng phía sau im lặng không
có gì** — `vocabulary_entry`, `dictation_item`, `score_conversion` đều bằng 0
trong khi ba bảng đầu trông hoàn toàn bình thường.

`scripts/import-content.sql` dọn đích trước khi nạp, và dọn theo catalog chứ
không theo tên hai bảng ấy — một migration seed thêm bảng mới về sau sẽ không
làm hỏng lại. Nó cũng khiến việc nạp **chạy lại được**, điều đáng giá vì lần
nhập đầu tiên hiếm khi trôi một mạch.

---

## 11. Điều kiện xét lại

Rời gói miễn phí khi **bất kỳ** điều nào sau đây đúng, không phải khi "thấy
chật":

- Có người dùng thật đều đặn — lúc đó 0.1 CPU và 50 giây khởi động lạnh thôi là
  bất tiện và thành lý do rời bỏ.
- Dự án bắt đầu thu tiền → giấy phép Vercel Hobby hết hiệu lực ngay (§5).
- Redis vượt ~400 K lệnh/tháng, tức khoảng 80 % hạn mức.
- Cần đăng nhập Apple, hoặc cần một domain riêng.

Bước rẻ nhất khi tới lúc: giữ nguyên mọi thứ và chỉ nâng Render lên gói trả phí
nhỏ nhất. Đó là hệ quả trực tiếp của việc mỗi thành phần nằm ở một nhà cung cấp
riêng — không có gói nào phải nâng theo.

**Mọi con số ở đây đo ngày 2026-08-28 và sẽ mục.** Điều kiện thẻ tín dụng là thứ
đổi nhanh nhất: Hugging Face và Koyeb đều đã rời khỏi danh sách này chỉ trong
một năm. Kiểm lại trước khi tin, đừng chép sang tài liệu khác.
