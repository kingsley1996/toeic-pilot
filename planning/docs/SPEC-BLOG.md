# SPEC-BLOG — Blog: bài viết chia sẻ + kênh SEO

Blog là kênh nội dung biên tập (editorial) của ToeicPilot: bài viết kiến thức
TOEIC, mẹo từng part, ngữ pháp, từ vựng theo chủ đề — vừa cho người học đọc,
vừa là cửa ngõ SEO (Google index) dẫn vào funnel học (placement → plan →
practice).

## 0. Quyết định khóa trước khi dựng

**Ai viết bài ở v1? Chỉ admin/staff, không UGC.** Bài của người dùng đồng nghĩa
với kiểm duyệt, chống spam, báo cáo vi phạm, trách nhiệm nội dung — một dự án
riêng. Blog v1 là kênh một chiều: đội nội dung viết, người học đọc và chia sẻ.
UGC (bài cộng đồng, bình luận) để v2, sau khi kênh đã có traffic.

**Lưu bài ở DB (`blog_post`), không phải file MDX.** Cần workflow
draft → publish, hẹn giờ thì v2, tìm kiếm, sửa nhanh trên admin — file MDX
trong repo không làm được mà không deploy lại web. Pattern đã có: grammar
lesson cũng là bảng + admin CRUD + render bằng `MarkdownLite`.

**Body viết bằng markdown-lite, không thêm engine mới.** `MarkdownLite`
(`apps/web/src/components/markdown-lite.tsx`, 242 dòng) đã render được lesson
ngữ pháp, giải thích, tactics — đủ cho bài blog (tiêu đề, in đậm/nghiêng,
list, bảng, link, ảnh). Không remark, không MDX, không component nhúng trong
bài ở v1. Muốn nhúng quiz/flashcard giữa bài thì để v2.

**Slug bất biến sau publish.** Đổi slug gãy backlink và mất điểm SEO đã tích.
Admin được sửa slug khi còn draft; đã published thì field khóa (muốn đổi phải
unpublish → sửa → publish lại, và chịu mất URL cũ — v2 mới có bảng redirect
301).

**Bài blog là nội dung công khai, đọc không cần đăng nhập** — cùng tinh thần
ADR-015 như hall-of-fame: Google phải đọc được full text SSR, và người đọc
chưa có tài khoản vẫn đọc hết bài (paywall/giới hạn bài đọc để v2 nếu cần,
hiện tại không).

**Không bình luận ở v1.** Bình luận = kiểm duyệt + spam + thêm bảng. CTA cuối
mỗi bài thay bằng "Học tiếp" dẫn vào funnel có sẵn (test đầu vào, luyện part,
từ vựng) — blog phục vụ tăng trưởng, không phải mạng xã hội.

**Ảnh bìa v1 là URL ngoài, không upload nội bộ.** Tránh đụng luồng media
ADR-006 (làm cho audio/video đề thi, có ticket/confirm/quota). Người viết up
ảnh lên host sẵn có (Supabase bucket public / Cloudinary) rồi dán URL vào.
Upload file từ editor để v2.

## 1. DB (1 bảng, 1 migration)

`blog_post`:

- `id UUID pk`, `slug TEXT UNIQUE NOT NULL` (lowercase, `a-z0-9-`, check
  constraint), `title TEXT NOT NULL` (≤120), `excerpt TEXT NOT NULL` (10–160
  ký tự — vừa là sapo vừa là meta description, một nguồn duy nhất),
  `body TEXT NOT NULL` (markdown-lite, ≥300 ký tự ở cổng publish),
  `cover_image_url TEXT NULL`, `category TEXT NOT NULL`
  (v1 là text tự do theo danh mục chốt ở §5, không bảng taxonomy riêng),
  `tags TEXT[] NOT NULL DEFAULT '{}'`, `author_name TEXT NOT NULL DEFAULT 'ToeicPilot'`,
  `status TEXT NOT NULL DEFAULT 'draft'` (`draft|published`, check),
  `published_at TIMESTAMPTZ NULL` (set lúc publish lần đầu, không đổi khi sửa),
  `created_by UUID NULL` (người bấm publish, không FK cứng để xóa staff không
  vỡ bài), `created_at`, `updated_at`.
- Index: `UNIQUE(slug)`, `btree(status, published_at DESC)` cho hub,
  `GIN(tags)`.

Không bảng `blog_category`, `blog_comment`, `blog_view` ở v1 — thêm khi có nhu
cầu thật (đếm view thì dùng analytics có sẵn, không cột riêng).

## 2. API

Public (`apps/api/app/api/routes/blog.py`, prefix `/blog`):

- `GET /blog/posts?category=&tag=&q=&page=&page_size=` (mặc định 12, trần 50):
  chỉ `status=published`, sắp `published_at DESC`. Item gọn:
  `{slug, title, excerpt, cover_image_url, category, tags, author_name,
  published_at, reading_minutes}` (`reading_minutes = ceil(words/200)`, tính
  lúc đọc, không lưu).
- `GET /blog/posts/{slug}`: full + `body`. Draft → 404 (không 403 — không để
  lộ sự tồn tại của bài chưa duyệt, cùng lý lẽ với topic-session null).
- `q` tìm trong `title+excerpt` (`ILIKE`, trần 50 ký tự); đủ cho v1, FTS để
  khi >200 bài.

Admin (`POST /admin/blog/posts`, `PATCH /admin/blog/posts/{id}`,
`POST .../publish`, `POST .../unpublish`, `GET /admin/blog/posts` cả draft):
đi chung guard admin hiện tại. Cổng publish từ chối khi thiếu
title/excerpt/body/slug/category, excerpt ngoài 10–160, body <300 ký tự, slug
sai format hoặc trùng — trả 422 liệt kê từng lỗi (giống cổng publish đề thi:
nói rõ thiếu gì, không "lỗi chung chung").

## 3. Admin UI (`/admin/blog`)

- Danh sách: bảng title/category/status/published_at + nút Publish/Unpublish,
  filter status + category + ô tìm.
- Form soạn (`lesson-form.tsx` của grammar là mẫu — copy cấu trúc, không trừu
  tượng hóa chung): ô slug (tự gợi ý từ title, khóa sau publish), title +
  đếm ký tự, excerpt + đếm 10–160, category dropdown, tags nhập phẩy,
  cover URL + preview ảnh, textarea body + **preview `MarkdownLite` cạnh bên**
  (đúng như form grammar đã làm), nút Lưu draft / Publish (hiện lỗi cổng
  từng dòng).
- E2E: soạn → publish → bài hiện ở hub public (giống test soạn grammar).

## 4. Web public + SEO

- `/blog` (hub, SSR): hero + filter category (query param, SSR luôn để mỗi
  category có URL crawl được: `/blog?category=meo-part-3`) + lưới card
  (cover, title, excerpt, ngày, phút đọc). Title: "Blog luyện thi TOEIC…",
  desc riêng.
- `/blog/[slug]` (SSR + ISR 600 như trang cảnh): breadcrumb, H1 = title,
  meta bài, cover, body qua `MarkdownLite`, tag link, khối "Bài liên quan"
  (cùng category, trừ mình, 3 bài — query thuần, không engine gợi ý ở v1),
  khối "Học tiếp" (CTA placement + luyện part, §6), nút chia sẻ: copy link +
  `navigator.share` fallback copy (không SDK Facebook/Zalo ở v1 — SDK bên thứ
  ba là nợ P1 kiểu Turnstile, đã học bài).
- Mỗi bài render JSON-LD `BlogPosting` (headline, description, image,
  datePublished, author) — copy pattern JSON-LD trang cảnh đang có.
- `sitemap.ts` thêm: `/blog` (weekly, 0.8) + từng slug published (monthly,
  0.7). Nguồn slug: fetch API lúc build (như SCENES là hằng số — blog thì
  động nên gọi API, cache ISR). `robots.ts` giữ nguyên (cho phép hết).
- Ảnh cover bắt buộc `alt = title`, `width/height` chống CLS; bài không cover
  vẫn publish được (card rơi về nền chữ như avatar hall-of-fame).

## 5. Danh mục + nội dung mồi (viết trước khi mở blog)

5 category v1, slug cố định (đổi tên hiển thị được, đổi slug không):

1. `meo-lam-bai` — chiến thuật từng part (7 part × ≥1 bài).
2. `ngu-phap` — điểm ngữ pháp hay ra thi, link sang lesson grammar có sẵn.
3. `tu-vung` — cụm/collocation theo chủ đề, link sang board từ vựng.
4. `kinh-nghiem` — lộ trình, quản lý thời gian, chuyện người học.
5. `thong-bao` — cập nhật sản phẩm, đề mới (để user cũ có lý do quay lại).

Mồi tối thiểu 10 bài (2/category, trừ thông-báo 1) mới hiện link Blog ở nav —
blog trống làm hại uy tín hơn không có blog. Mỗi bài: 800–1500 từ, ≥3 link
nội bộ (sang bài khác + sang trang học), excerpt viết tay không trùng câu đầu
body (trùng nguyên văn bị Google coi là desc kém).

## 6. Funnel: blog → học (blog không đứng một mình)

- Cuối mỗi bài: khối "Học tiếp" 2 nút — "Test đầu vào miễn phí" (`/learn/placement`)
  cho khách, "Luyện part N" (`/learn/parts/N`) đúng part bài viết nhắc tới
  (field optional `related_part INT NULL` ở bảng — nullable, không ép bài nào
  cũng gắn).
- Giữa bài dài (>1000 từ): 1 banner CTA placement chèn tự động sau heading thứ
  2 (render-time, không lưu vào body — sửa CTA không phải sửa 100 bài).
- Đo bằng event analytics có sẵn cho 2 nút này (click-through blog → placement);
  3 tháng không có click thì xem lại vị trí CTA, không đoán.

## 7. Plan theo pha (mỗi pha xong là chạy được, không pha dở)

- **P1 — API + DB (2–3 ngày):** migration `blog_post`, route public + admin,
  cổng publish, pytest (publish gate từng lỗi, draft 404, phân trang, `q`).
- **P2 — Admin UI (2 ngày):** list + form soạn kiểu lesson-form, preview
  MarkdownLite, e2e soạn→publish→hiện hub.
- **P3 — Public + SEO (2–3 ngày):** `/blog`, `/blog/[slug]` SSR + ISR,
  JSON-LD, sitemap động, share/copy, khối Học tiếp + banner giữa bài, e2e
  public 0 4xx + check meta/canonical.
- **P4 — Nội dung mồi (song song từ P2, theo người viết):** 10 bài theo §5,
  nhập qua chính form admin (ăn luôn dogfood test form), rồi mới hiện nav.
- **P5 — Đo (sau mở 2–4 tuần):** Search Console (impression/click top bài),
  click-through CTA; quyết định v2 theo số.

Tổng code ~1 tuần dev (không tính giờ viết bài). Không dependency mới, không
bảng phụ, không SDK chia sẻ.

## 8. Không làm ở v1 (ghi để khỏi ai "tiện tay" thêm)

Bình luận, UGC/bài cộng đồng, like/bookmark, đếm view riêng, hẹn giờ đăng,
series nhiều kỳ, newsletter/email, tìm kiếm FTS, upload ảnh từ editor,
redirect 301 đổi slug, đa ngôn ngữ, AMP, paywall. Mỗi thứ là một spec riêng
khi số liệu P5 đòi.
