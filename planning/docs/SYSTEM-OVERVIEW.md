# TOEIC Pilot — hệ thống hiện tại

**Viết lại từ source ngày 2026-09-01.** Đây là mô tả **cái đang chạy**, không phải bản ghi
quyết định — quyết định nằm ở `adr/`, trạng thái nằm ở `ROADMAP.md`. Mọi con số dưới đây
đo được bằng lệnh ghi kèm, nên chúng kiểm lại được thay vì phải tin.

## 1. Đo được gì

| | Số | Đo bằng |
|---|---|---|
| Bảng database | **57** | `len(Base.metadata.tables)` |
| Migration | **51** | `ls alembic/versions/*.py` |
| Thao tác HTTP | **189** | `len(app.openapi()["paths"])` trải theo method |
| Module Python | 183 tệp, **39 524 dòng** | `app/**/*.py` |
| Router · service | 26 · 42 | `app/api/routes/` · `app/services/` |
| Route Next.js | **49** | `find apps/web/src/app -name page.tsx` |
| Spec e2e | 8 | `apps/web/e2e/*.spec.ts` |
| Test API | **949 passed**, 2 skipped | `uv run pytest` |

Nội dung trong database dev:

| | Số |
|---|---|
| Đề · câu hỏi | 5 · **655** |
| Câu có giải thích | 124 / 655 |
| Từ vựng · câu dictation | 303 · 62 |
| Bản thu (`audio_asset`) | 2 779 |
| Tài khoản | 1 647 |

**124/655 câu có giải thích** là con số chặn RAG (`adr/ADR-003-AI-LAYER.md` §3.3): truy hồi
vẫn gần như không có gì để truy.

## 2. Hình dạng

```
apps/web    Next.js  ──apiFetch()──►  apps/api    FastAPI
   │                                     │
   │  packages/shared ◄──gen:api-types───┘   (hợp đồng SINH RA từ OpenAPI)
   │                                     │
   └─ media ◄── Supabase Storage         ├─ Postgres + pgvector
              Cloudinary                 └─ Redis (phụ thuộc MỀM)

apps/api/app/content/**   đường ống NGOÀI LUỒNG — không gì với tới được từ app.main
docker/worker.Dockerfile  image riêng, có ffmpeg + extra `content`
```

Frontend không bao giờ viết cứng đường dẫn API hay hình dạng phản hồi; cả hai đến từ
`@toeic-pilot/shared`, mà `packages/shared/src/api-types.ts` được **sinh ra** bằng
`pnpm gen:api-types`. Job `contract` của CI sinh lại và fail nếu bản đã commit khác.

## 3. Endpoint, theo khu

| Khu | Thao tác |
|---|---|
| `/admin/**` | **114** |
| `/pet` · `/attempts` · `/auth` | 11 · 10 · 9 |
| `/profile` · `/vocabulary*` | 7 · 10 |
| `/dictation*` · `/assistant` | 5 · 3 |
| còn lại (progression, ruby, media, health…) | 20 |

**114 trên 189 thao tác là admin.** Đó không phải mất cân đối mà là hệ quả của một quyết
định: nội dung là nút thắt, nên công cụ soạn nội dung được xây trước
(`adr/ADR-005-CONTENT-TOOLING.md`).

## 4. Ranh giới không được phá

Bốn ranh giới có **phép kiểm tự động** đứng sau, không phải quy ước ai đó phải nhớ:

| Ranh giới | Ai giữ |
|---|---|
| Không gì với tới được từ `app.main` được import `app.content` | `tests/test_content_isolation.py` (subprocess, <1s) + job `docker` boot image thật |
| Hợp đồng TS phải khớp OpenAPI | Job `contract` của CI |
| Nhãn trong tài liệu phải khớp `labels.py` | `tests/test_labels.py` đọc lại chính tài liệu |
| Các lớp của Petland không được import chéo | `apps/web/scripts/check-petland-layers.mjs` |

Ranh giới thứ nhất là ranh giới quan trọng nhất: ảnh production build `--no-dev` **không có**
extra `content`, nên một lượt rò rỉ làm container chết lúc khởi động chứ không phải lúc build.

## 5. Phụ thuộc, và cái nào mềm

| | Cứng hay mềm | Hỏng thì sao |
|---|---|---|
| Postgres | **cứng** | `/ready` trả 503 |
| Redis | **mềm** | log cảnh báo, `/ready` báo `degraded` |
| Supabase Storage / Cloudinary | mềm với API | API **không bao giờ** phục vụ byte media |
| edge-tts | chỉ ngoài luồng | chặn nội dung MỚI, không chạm nội dung đã có |
| Nhà cung cấp LLM | mềm | ngân sách token **fail closed** (§3.4) |

Redis mềm ở hầu hết chỗ nhưng **không phải mọi chỗ**, và hai chiều ngược nhau là cố ý:
`rate_limit_anonymous` **fail open** (Redis sập thì không ai đăng nhập được là tệ hơn),
còn `rate_limit` trên đường LLM **fail closed** (ở đó Redis là thứ duy nhất giữa một tài
khoản và hoá đơn).

## 6. Học viên đi qua đâu

`/dashboard` là nhà; mọi thứ để học nằm dưới `/learn/**` — `vocabulary`, `dictation`,
`tests`, `review`, `typing`, `attempts`. Petland là góc thú cưng. `/admin/**` là khu soạn
nội dung, gác bằng `require_role` **dạng dependency, không bao giờ là phép kiểm trong thân
hàm** — một phép kiểm trong handler là cái người ta quên chép sang route kế tiếp.

## 7. Nội dung đi vào bằng đường nào

Hai đường, và chúng khác nhau ở chỗ ai duyệt:

**Dán tay** — editor dán, parser trả về hàng kèm lỗi, người duyệt, rồi commit thành `draft`.
Parse **không bao giờ ghi**; publish là hành động riêng, chỉ admin.

**Sinh bằng đồ thị** — `plan → write → check → load`, mô tả ở `EXAM-GRAPH.md`, thao tác ở
`EXAM-GENERATION-RUNBOOK.md`. Đầu ra vẫn là `draft` và vẫn qua mắt người.

Audio **không bao giờ** sinh trong một request: API không import nổi đường ống TTS, và hàng
đợi là một **truy vấn** ("cái gì thiếu audio hoặc không còn khớp lời thoại") chứ không phải
một bảng job. Nút "sinh audio" ở admin bấm chuông Redis và trả **202**.

## 8. Những gì hệ thống KHÔNG làm

Ghi ra vì mỗi mục là một quyết định, không phải một thiếu sót:

- **Không RAG.** Bị chặn bởi nội dung (124/655 câu có giải thích), không phải kỹ thuật.
- **Không LLM trên đường chấm điểm.** Chấm, SM-2, quy đổi điểm và diff dictation là số học
  chính xác; đưa LLM vào là biến chúng thành xấp xỉ (`AI-ENGINEERING-PLAN.md` §2).
- **API không phục vụ byte media.** Proxy qua FastAPI làm mất range request và đốt băng
  thông của API (`adr/ADR-006-MEDIA-UPLOAD.md` §2.9).
- **Không có cookie httpOnly.** Hoãn *có lý do viết ra*: không script bên thứ ba nào trên
  bất kỳ trang nào. Thêm một cái là lý do đó hết hiệu lực.
- **Branch protection chưa bật.** Cần quyền admin repo.
