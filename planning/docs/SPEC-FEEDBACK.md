# SPEC-FEEDBACK — Góp ý từ người học

Trạng thái: **đã duyệt, đang làm** (2026-09-08). Runbook đồng bộ đề không liên quan.

## 0. Mục tiêu

Người học gửi góp ý (bug / yêu cầu tính năng / lỗi nội dung) kèm ảnh minh hoạ,
ngay trong app qua một nút nổi ở mép phải. Admin xem list, duyệt hoặc từ chối;
duyệt thì trao ruby. Một feature, ba mặt: gửi — xem — thưởng.

## 1. Dữ liệu (migration `074_feedback`)

Bảng `feedback`, pattern theo `models/health.py` + `TimestampMixin`:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID pk | |
| user_id | FK users, CASCADE, NOT NULL | Gửi từ app, bắt buộc đăng nhập |
| type | String(16) CHECK | `bug` / `feature` / `content` / `other` |
| description | Text NOT NULL | Nội dung góp ý |
| screenshot_storage_key | String(512) NULL | **Pattern avatar** (`UserProfile.avatar_storage_key`): khoá thô, KHÔNG tạo hàng `image_asset` — ảnh người dùng không có giấy phép/provenance (ADR-006 §2.1) |
| status | String(16) CHECK | `pending` / `approved` / `rejected`, default `pending`, index |
| admin_note | Text NULL | Ghi chú của admin khi xử lý |
| reviewed_by | UUID FK users NULL | |
| reviewed_at | DateTime NULL | |
| created_at / updated_at | TimestampMixin | |

Tiền tố khoá ảnh: `feedback/` — thêm `FEEDBACK_KEY_PREFIX` + `feedback_storage_key_for()`
vào `core/media.py`, cạnh `avatar_storage_key_for()`.

## 2. Ruby

- `RUBY_SOURCES` thêm `"feedback_reward"` (models/ruby.py) — nguồn KIẾM thường, **nằm trong
  `ruby_rule`** (khác `admin_grant`/`encounter`): mức thưởng là quyết định vận hành, admin
  sửa được ở `/admin/ruby` không cần deploy.
- `DEFAULT_RUBY_RULES` thêm hàng `{"source_type": "feedback_reward", "label": "Góp ý được duyệt",
  "amount": 20, "position": 8}`.
- **Bẫy gieo lười:** `rules()` chỉ gieo khi bảng RỖNG (ruby.py:75). Prod/dev đã có 7 hàng nên
  mặc định mới không tự xuất hiện — migration 074 phải `INSERT ... ON CONFLICT DO NOTHING`
  hàng `ruby_rule` này. (Khác `pet_species.lines`: cột mới thì `alembic` đủ; hàng mới thì không.)
- Trao khi duyệt: `earn(db, user_id=feedback.user_id, source_type="feedback_reward",
  source_id=feedback.id)` rồi `db.commit()`. Idempotent nhờ `uq_ruby_event_source`
  `(user_id, source_type, source_id)` — duyệt hai lần không trao hai lần. Từ chối sau khi
  duyệt KHÔNG rút ruby (sổ cái bất biến).

## 3. API

### Người học — `routes/feedback.py`, prefix `/feedback`, tag `feedback`

| Endpoint | Ghi chú |
|---|---|
| `POST /feedback/screenshot/ticket` | Nhân bản `avatar_ticket` (profile.py:108): quota riêng chặt (`Quota(limit=10, window=600)`), sinh khoá dưới `feedback/`, trả `UploadTicket`. Trình duyệt POST thẳng provider — đúng ticket→POST→confirm của ADR-006 |
| `POST /feedback` | Body `FeedbackCreate {type, description, screenshot_storage_key?}`. Kiểm khoá bắt đầu `feedback/` + `driver.verify()` (như `avatar_confirm`) — không thì AI URL vỡ. **Tạo = confirm**, không có bước 3. Chống spam: đếm feedback `pending` của user, ≥ 10 thì 409; rate_limit bucket `feedback-create` |
| `GET /feedback/mine` | Feedback của mình, mới nhất trước, tối đa 50 — người gửi cần thấy trạng thái |

### Admin — `routes/admin_feedback.py`, prefix `/admin/feedback`, `require_role("admin")`

| Endpoint | Ghi chú |
|---|---|
| `GET /admin/feedback?status=&offset=&limit=` | `Page[FeedbackPublic]` (schemas/common.py:40), filter tuỳ chọn |
| `POST /admin/feedback/{id}/approve` | Đặt `approved` + reviewed_by/at + `earn(...)` trong cùng transaction. Idempotent: đã approved thì 409 |
| `POST /admin/feedback/{id}/reject` | Body `{admin_note?}`, đặt `rejected` + reviewed_by/at. Đã rejected thì 409 |
| `PATCH /admin/feedback/{id}` | Sửa `admin_note` — ghi chú thêm được khi còn pending |

Kích thước ảnh: ticket cho phép ≤ 5 MB, jpg/png/webp (slim hơn khu nội dung).

## 4. Schemas (`schemas/feedback.py`)

`FeedbackCreate` (type, description, screenshot_storage_key?) · `FeedbackPublic` (đủ +
`image_url` sinh từ `driver.public_url`, chỉ trả khi có khoá) · `FeedbackRejectBody`.
Đặt tên theo quy ước `XPublic`/`XCreate` của pet.py.

## 5. Frontend

### Nút nổi — `components/feedback-dock.tsx`

- Vị trí: `fixed right-4 top-1/2 -translate-y-1/2 z-40` — cùng z-40 với coach-chat,
  KHÔNG `box-shadow` thường (DESIGN-SYSTEM: chỉ `shadow-overlay`).
- Cụm dock 1 nút (chỗ trống cho nút social sau này). Icon: MessageSquarePlus.
- Mount trong `AppShell` (app-shell.tsx:159) — nhánh `bareLayout` (admin + màn làm bài)
  **không** hiện: người đang thi không cần góp ý, khu admin đã có đường riêng.
- Mở modal: **ảnh trước** (file input → xin ticket → POST thẳng provider → thumbnail),
  rồi segmented chọn type, rồi textarea mô tả, rồi Gửi. Thành công → toast cảm ơn
  (dùng `PetlandToast`? — không, toast chung `components/toast.tsx`).

### Admin — `app/admin/feedback/page.tsx`

- Pattern `admin/ruby/page.tsx`: `useRequireSession({canEdit:true})` + `apiFetch` + `Panel`.
- Tabs lọc trạng thái (pending/approved/rejected/all), hàng: type, mô tả, ảnh
  (thumbnail `<img>` mở thẳng URL), ngày, người gửi.
- Hàng pending: ô số ruby (default lấy `adminRubyRules`), nút Duyệt / Từ chối (kèm ghi chú).
- Thêm `ADMIN_LINKS` mục "Feedback" nhóm System (admin-shell.tsx:45).

## 6. Hợp đồng dùng chung

`API_ROUTES` thêm: `feedback`, `feedbackMine`, `feedbackScreenshotTicket`,
`adminFeedback`, `adminFeedbackApprove(id)`, `adminFeedbackReject(id)`,
`adminFeedbackEdit(id)`. Rồi `pnpm gen:api-types` — commit cả `api-types.ts` +
`openapi.json` (CI `contract` sẽ bắt nếu quên).

## 7. Tests (`tests/test_feedback.py`)

Fixture `client` + `auth()` của conftest. Bảy bài tối thiểu:

1. Tạo thành công → 200, status pending, có ảnh thì khoá phải dưới `feedback/`.
2. Khoá sai vùng (khác prefix) → 400 — đúng bẫy `avatar_confirm`.
3. Loại type lạ → 422; mô tả rỗng → 422.
4. Cap 10 pending → feedback thứ 11 → 409.
5. `GET /mine` chỉ thấy của mình.
6. Approve trao đúng 20 (theo rule), approve lần 2 → 409 và sổ không tăng — idempotent.
7. Reject không trao ruby; rule `feedback_reward` tồn tại sau migration (SQLite create_all
   sẽ thiếu hàng — bài test phải chạy lệnh gieo/migration tương đương, xem §2).

## 8. Cái chủ ý KHÔNG làm

- Không trang "lịch sử góp ý" cho người học — `GET /mine` đủ, UI gộp vào modal.
- Không thông báo đẩy khi admin xử lý — người học tự mở modal xem.
- Không rút ruby khi chuyển approved → rejected (sổ cái bất biến, ruby.py đầu tệp).
- Không đếm ảnh `feedback/` vào lệnh dọn mồ côi khu nội dung — tiền tố riêng chính vì thế.
