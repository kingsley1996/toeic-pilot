# Cửa hậu QA miễn xác minh Turnstile

Agent QA của chính ta (bot) không qua được Cloudflare Turnstile, nên không test
được full luồng đăng ký/đăng nhập trên prod. Cửa hậu này cho phép request mang
secret đi qua mà không cần token Turnstile.

## Field (cố định trong code, không bí mật)

| Field | Giá trị | Nằm ở |
|---|---|---|
| Header | `x-qa-bypass` | `app/services/turnstile.py::QA_BYPASS_HEADER` |
| Env | `QA_BYPASS_SECRET` | `app/core/config.py::qa_bypass_secret`, set trên Render (service API) |

**Giá trị secret KHÔNG nằm trong repo, log hay client.** Nó chỉ sống trong env
Render. Mất dấu secret thì xem mục "Xoay" — không cần đọc lại giá trị cũ.

## Luật

- Env trống = cửa hậu không tồn tại (đoán đúng tên header cũng 403).
- Chỉ miễn Turnstile. Rate limit, auth, phân quyền chạy y nguyên.
- Mỗi lần dùng ghi một dòng `warning` với IP (không ghi secret) — thấy IP lạ
  dùng bypass thì coi như lộ, xoay ngay.
- Test ghim trong `apps/api/tests/test_turnstile.py`: đúng secret qua + không
  gọi Cloudflare; sai secret 403; env trống 403.

## Dùng trong test (script ở /tmp, không commit)

1. Browser gắn header vào mọi request: `extraHTTPHeaders: { "x-qa-bypass": <secret> }`.
2. Stub `window.turnstile` trước khi trang chạy (`addInitScript`): `render`
   gọi `callback` bất đồng bộ (defer `setTimeout`, gọi đồng bộ sẽ race với
   `waiting` trong `take()`), `reset` cũng gọi lại `callback`, token là chuỗi
   bất kỳ (server bỏ qua nội dung khi secret khớp).

## Xoay secret

Đổi giá trị `QA_BYPASS_SECRET` trên Render → đợi API redeploy → báo agent giá
trị mới. Không cần deploy code.
