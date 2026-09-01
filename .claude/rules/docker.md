---
paths:
  - "docker/**"
  - "**/Dockerfile*"
  - "**/.dockerignore"
---

# Image và compose

**Ảnh production của API không cần trình biên dịch.** `gcc` và `libpq-dev` từng nằm trong
`api.Dockerfile` để build psycopg — nhưng dependency là `psycopg[binary]`, mà wheel của nó
đã gói sẵn libpq, nên chưa bao giờ có gì được biên dịch. Bỏ hai gói đó cộng với tách
builder/runtime đưa image từ 510MB xuống 321MB và gỡ một bộ công cụ C khỏi tiến trình phục
vụ HTTP. Image chạy uid 10001; `uv` **cố ý ở lại** stage runtime, vì service compose của dev
ghi đè CMD bằng `uv run uvicorn --reload` và bỏ nó đi là tiết kiệm vài megabyte để đổi lấy
vòng lặp phát triển. `UV_FROZEN=1` cộng `--no-sync` giữ cho lúc khởi động không bao giờ đi
giải dependency qua mạng.

**Worker là image RIÊNG, và sự tách đó chính là mục đích.** `docker/worker.Dockerfile` mang
ffmpeg và extra `content`; `api.Dockerfile` không mang cái nào. Gộp lại sẽ không hỏng gì vào
ngày gộp — nó hỏng vào ngày có người thấy `app.content` đã cài sẵn rồi import nó vào một
request handler "vì nó ở ngay đó", đặt edge-tts, ffmpeg và một lượt gọi mạng lên đường phục
vụ. Image riêng cho A4.1 một hình dạng vật lý thay vì một quy ước ai đó phải nhớ.

Worker bỏ hai gói kia nhưng **ở lại root**, cố ý: nó ghi vào `media/` và `content/` qua
bind mount của host, và một user không phải root mất quyền ghi vào đúng hai thư mục nó sinh
ra để ghi — cách sửa nhanh cho việc đó là `chmod 777`, tệ hơn. Nó cũng không phục vụ request
nào.

**Không bao giờ bind-mount `../apps/api` vào container — mount `../apps/api/app`.** Cả thư
mục bao gồm `.venv`, và `uv run` bên trong container sẽ thấy một virtualenv macOS, xoá nó, và
dựng một cái Linux **đè lên của host**. Mọi `uv run` trên host sau đó fail với
`broken symbolic link to /usr/local/bin/python3.12`, một thông báo không hề nhắc tới Docker.

**`.dockerignore` là chịu lực** — xem `CLAUDE.md`.
