# Nghe từ YouTube (Listening Lab — slice YouTube)

Học dictation từ video YouTube thật: dán link → hệ thống tự lấy phụ đề public
(cùng track player dùng) → sửa nếu cần → tạo bài → nghe-chép từng câu.
Không tải/re-host video hay phụ đề về server (SPEC-REAL-WORLD-LISTENING §3, §19).

## 1. Luồng dùng

```text
/learn/dictation → "Listening Lab — học từ video YouTube"
  → /learn/listening: dán URL → resolve → preview + tên (oEmbed) + tự lấy phụ đề
  → sửa transcript (SRT/VTT) → [Tạo bài học]
  → /learn/listening/[id]: video trái + list Transcript phải + ô chép dưới
  → gõ đúng → dòng mở chữ + viền xanh → F5 vẫn còn
```

Tab TikTok/Upload hiện disabled "sắp có" (giữ khung UX, không code chết).

## 2. Kiến trúc

```text
URL → resolve_source → fetch_youtube_captions → parse → validate → filter
  → listening_content + listening_segments → replay/submit → listening_attempts
```

Backend (`apps/api`):

| Thứ | File | Ghi chú |
|---|---|---|
| 3 bảng | `app/models/listening.py` + migration `089_listening_lab.py` | content/segment/attempt; KHÔNG bảng exercise (1 segment = 1 bài) |
| Resolve URL | `app/services/listening_source.py` | thuần cú pháp, không fetch mạng; TikTok → `UNSUPPORTED_SOURCE` |
| Parse/validate | `app/services/listening_transcript.py` | 1 parser SRT+VTT; overlap chỉ warning |
| Lọc câu thoại | `is_speakable()` cùng file | loại `[Music]`/`[♪♪♪]`; lyric giữ nguyên |
| Lấy phụ đề | `app/services/listening_youtube_captions.py` | InnerTube (private API!) + timedtext, whitelist host, transport mock được |
| Chấm bài | reuse `app/services/dictation.py::grade` | KHÔNG fork bộ chấm |
| 5 endpoints | `app/api/routes/listening.py` | captions (rate-limit 30/10ph) · contents ×2 · attempts; ownership 404-chéo |

Tiền lệ quan trọng: `ApiError` web mang `detail` có cấu trúc (`{code, errors}`)
để UI map câu thân thiện — endpoint nào cũng nên trả `code` thay vì câu chữ.

Frontend (`apps/web`):

| Thứ | File |
|---|---|
| Adapter phát lại | `src/lib/listening-player.ts` (đúng interface SPEC §10 + `getDuration`) |
| Khung player | `src/components/listening-player.tsx` |
| Trang tạo / học | `src/app/learn/listening/page.tsx`, `[id]/page.tsx` |
| Lối vào | `PanelLink` trong `src/app/learn/dictation/page.tsx` + tag mới/thử nghiệm |

Luật hành vi (đã chốt với user, đừng đổi lén):

- Phát luôn dừng cuối câu đang nghe (replay HOẶC latch theo `stops`).
- Bấm play: trong câu → resume; đứng cuối câu → TIẾN sang câu kế (cả ba cùng
  đi); tua đi xa → resume đúng chỗ, không lôi bài tập theo.
- Tua không bao giờ tự phát. Đáp đúng thì ở yên — đi tiếp chỉ bằng nút.
- MỘT state hiện tại duy nhất: video tới đâu thì cả bài (list + bài tập +
  cuộn) theo tới đó. Dính biên 0.3s (dừng ngay mốc thì ở yên); tua-nhảy thì đi
  ngay. Chữ gõ dở mất theo khi qua câu — chấp nhận vì qua câu luôn là hành
  động của user.
- Chưa đúng che `*` dài bằng từ; đúng mở chữ + viền xanh; F5 giữ nguyên
  (seed từ `completed_segment_ids`).

## 3. Bẫy đã gặp (đọc trước khi đụng player/transcript)

1. **Constructor thiếu `width`/`height`** → API vẫn bắn `onReady` nhưng không đẻ
   iframe: nút treo `loading` vĩnh viễn, không một lỗi nào. Luôn truyền kích
   thước (`'100%'` + khung CSS quyết cỡ thật).
2. **Đưa node React cho `YT.Player`** → API thay node ngay dưới chân React;
   remount (StrictMode dev) dựng player trên node đã rời DOM: request embed vẫn
   đi, khung rỗng. Iframe do effect tự `createElement`/`remove`, React chỉ giữ
   khung bọc rỗng (`listening-player.tsx`).
3. **Dud instance** (`ctor X`, không có `seekTo`): `new` lần hai trong lúc lần
   một dọn dở trả về object nội bộ. Method YT gắn BẤT ĐỒNG BỘ nên không kiểm
   hình dạng lúc `new` được (loại luôn cả player lành!) — dấu hiệu dud thật là
   `onReady` không bao giờ tới → đợi ready có hạn (8s) + thử lại 1 lần
   (`PlayerFailed` riêng, không đè alert mã cụ thể).
4. **Timedtext v3 vs srv1**: InnerTube trả `<p t="1360" d="1680">` (MILI-giây),
   parser cũ chỉ biết `<text start="12.42">` (giây) → parse rỗng + nhầm tỉ lệ
   (seek tới phút 22 của video 3 phút). Suy đơn vị từ TÊN attr, không đoán theo
   độ lớn số.
5. **`key={segment.id}` trên player** → đổi câu remount iframe (chớp + load
   lại như reload trang). Một player sống suốt bài, đổi câu chỉ seek.
6. **Seek bất đồng bộ**: poll đọc giờ cũ vài tick sau seek mà chốt pause ngay
   là pause oan → replay chờ tới khi giờ chạm segment mới tính dừng
   (`SEEK_EPS`), pause đòi tick-trước-đã-gần-chốt (liên tục tới nơi).
7. **Bấm play trên video bypass toggle** → không chốt lại → poll giết bằng chốt
   stale trong 500ms. Chốt lại ở MỌI lượt phát mới (chuyển paused→playing),
   pause đòi status YouTube xác nhận đang phát thật.
8. **Nhãn nút nói dối**: "Tiếp tục" mà phát lại câu cũ. Bấm đúng cuối câu thì
   tiến (`onAdvance`), hết bài thì nút thành "Nghe lại".
9. **Enter đi tiếp sau khi đúng** (component dictation chung): Lab tắt bằng
   prop `advanceOnEnter={false}`, flow cũ giữ nguyên.
10. **Bài nhạc/nền thành bài học**: segment nào cũng thành exercise → lọc
    `is_speakable` ở create + captions endpoint; hết lời thoại thì 422 chứ
    không lưu bài rỗng.
11. **Đồng hồ tử lớn hơn mẫu**: mẫu số là cuối câu đang làm, tua đi nơi khác là
    sai → dùng `getDuration()` thật.
12. **Highlight nhảy câu khi pause ở biên**: tick chạm mốc bắt đầu câu sau là
    follow nhảy dù chưa phát — dính biên `FOLLOW_EPS`, ở yên câu trước.
13. **Turnstile flake khi register 2 lần liên tiếp** trong e2e → gộp 1 test,
    1 lần register.
14. **`eslint-disable` sai cú pháp** (thêm chữ sau tên rule) = rule không tồn
    tại → lỗi. Giải thích viết dòng riêng, tên rule đứng một mình.
15. **BSD/macOS**: `sed -i` và `grep \|` khác GNU — kiểm tra output sau mỗi lần
    dùng trong script; `//` trong Python là lỗi cú pháp (đã dính 2 lần).
16. **Pipe nuốt exit code**: `cmd | tail` luôn exit 0 → `&& commit` chạy cả khi
    test đỏ (đã push 1 commit lỗi kiểu này). Chạy test trần, commit lệnh riêng.
17. **`@toeic-pilot/shared` resolve qua `dist/`**: regen `api-types` xong phải
    `pnpm --filter @toeic-pilot/shared build`, không tsc báo thiếu field oan.
18. **Bấm play thẳng trên video bypass mọi chốt của mình**: poll giết phát lại
    bằng chốt stale trong nửa giây — chốt lại ở MỌI lượt phát mới (phát hiện
    qua chuyển paused→playing), pause đòi status YouTube xác nhận.
19. **Bài tập/list/video ba nơi ba ngả**: gộp thành MỘT state (video tới đâu cả
    bài theo tới đó). Cửa sổ settle 1200ms sau mỗi lần bấm đi để tick stale
    trong lúc seek bay không lôi bài tập đi lung tung.

## 4. Verify slice này

```bash
# backend (apps/api, dùng .venv)
.venv/bin/python -m pytest tests/test_listening_api.py tests/test_listening_source.py \
  tests/test_listening_transcript.py tests/test_listening_youtube_captions.py -q
.venv/bin/python -m ruff check app/ && .venv/bin/python -m mypy app/api/routes/listening.py \
  app/schemas/listening.py app/services/listening_*.py app/models/listening.py
# web
pnpm --filter @toeic-pilot/web exec tsc --noEmit
pnpm --filter @toeic-pilot/web exec eslint src/app/learn/listening/ src/lib/listening-*.ts \
  src/components/listening-player.tsx e2e/listening.spec.ts
pnpm --filter @toeic-pilot/web exec prettier --check <các file trên>
pnpm --filter @toeic-pilot/web exec playwright test e2e/listening.spec.ts e2e/dictation.spec.ts
```

Playback thật (seek/pause đúng mốc, tua, F5) không assert được ổn định trong CI
(CI không có loa/mạng ổn định cho iframe) — kiểm tay bằng probe Playwright trỏ
dev stack khi sửa player, theo mẫu các `check*.mjs` đã xoá.

## 5. Bot-wall trên prod (IP datacenter bị chặn)

Triệu chứng: cùng video local lấy phụ đề được, prod trả
`{"detail":{"code":"VIDEO_UNAVAILABLE"}}`. Đọc log Render:
`youtube playability LOGIN_REQUIRED for <id>: Sign in to confirm you're not a bot`
(= tường bot theo IP egress, không phải region/video hỏng — video vẫn public,
oEmbed vẫn ra). Trình duyệt gọi thẳng InnerTube cũng chết (403/CORS) nên không
có đường vòng qua client.

- **(a) Chấp nhận + dán tay (mặc định hiện tại, đề xuất giữ).** Auto-fetch là
  best-effort có nút thử lại; dán tay luôn chạy, không đụng YouTube. Đúng triết
  lý SPEC: transcript là dữ liệu user đưa, server chỉ tiện tay lấy hộ.
- **(b) Cache phụ đề theo `video_id` (TTL đề xuất 30 ngày).** Video nào lấy được
  1 lần thì user sau khỏi gọi YouTube. Cần gật về SPEC §3 trước (lưu nội dung
  YouTube trên server mình, dù chỉ là chữ).
- **(c) Google OAuth per-user.** Request mang danh user thật → hết tường bot,
  mở luôn video giới hạn tuổi. Giá: project + consent `youtube.readonly`
  (sensitive → chờ verification Google vài ngày–vài tuần, giới hạn ~100 user
  trước đó), bảng `google_credentials` (refresh token mã hóa đảo ngược — repo
  hiện chỉ hash một chiều), routes OAuth, job refresh, UI kết nối/ngắt, tuân thủ
  Google API User Data Policy. Công 2–4 ngày + chờ duyệt. Thứ tự nếu đi: OAuth
  trước, verification song song, captions chuyển connected-first; dán tay giữ
  nguyên làm đường cuối. KHÔNG làm: dán cookie/token thủ công.

## 6. Thư viện bài có sẵn (ĐÃ LÀM — user gật scope + bản quyền 2026-09-18)

Bài public (`listening_content.is_public`, migration 090) đọc được kể cả khách
(`get_optional_user`, tiến độ chỉ hiện khi login — cùng luật ADR-015); nộp bài
vẫn cần tài khoản; bài riêng của người khác vẫn 404. Endpoint
`GET /listening/library` + hub section "Thư viện bài có sẵn" + link "Nguồn
video gốc" mỗi trang học (ghi nguồn + gỡ khi bị khiếu nại).

Seed offline (cấm CI, IP local sạch mới qua được tường bot):
`uv run python scripts/seed_listening_library.py [--apply]` (dry-run mặc định).
Loạt đầu 5 video sub tay: meetings-easy-English, 2 TED công sở, 2 Rick Astley
(vui). Thêm video = thêm dòng vào `VIDEOS`, chạy lại (trùng public thì bỏ qua).

Lên prod: `alembic upgrade head` trước (dev từng phải `stamp 089` vì bảng dựng
bằng `create_all` — prod đi migration chuẩn thì không), rồi chạy seed với
`DATABASE_URL` của prod. Vận hành: video bị xoá/gỡ là bài thối — cần job kiểm
tra định kỳ (phase sau; trước mắt kiểm tay).
