# Phase 2 — Hạ tầng Audio

**Trạng thái:** Đã chốt quyết định (2026-08-08) · **Đã triển khai xong (2026-08-09)**
**Thay thế cho:** `ADR-002` mà `REVIEW-OPUS.md` §8 Sprint 2 yêu cầu
**Liên quan:** `REVIEW-OPUS.md` §7b (rủi ro kiến trúc số 2), §7a (data model — vẫn đang mở)

Tài liệu này có hai phần với vòng đời khác nhau:

- **Phần A — Quyết định kiến trúc.** Còn giá trị sau khi triển khai xong. Đọc lại sau 6 tháng vẫn phải trả lời được "vì sao lại làm thế này".
- **Phần B — Nhật ký triển khai.** Checklist đã hết hạn và được thu gọn thành bản ghi kết quả + các chỗ lệch so với kế hoạch.

---
---

# PHẦN A — QUYẾT ĐỊNH KIẾN TRÚC

## A1. Bối cảnh và vấn đề

Phase 2 (Learning Hub) gồm Dictation và Vocabulary by topic. Cả hai đều cần audio. Phase 3 (TOEIC Practice) còn cần nhiều hơn — Listening Part 1–4.

Nhưng cả `PLAN.md` lẫn `ARCHITECTURE.md` **không nhắc một chữ nào** về audio. Repo cũng không có gì:

- Không object storage, không CDN
- Không dependency nào liên quan: không `boto3`, không `ffmpeg`, không thư viện TTS, không cả `python-multipart`
- Không model/migration nào cho media — model duy nhất là `User`
- Docker Compose chỉ có 4 service: `postgres`, `redis`, `api`, `web`

`REVIEW-OPUS.md` §7b xếp đây là **rủi ro kiến trúc số 2 của dự án**. Cùng với §7a (data model), nó là một trong hai thứ chặn Phase 2.

**Mục tiêu:** dựng đường ống audio chạy được ngay, không cần tài khoản hay thẻ thanh toán nào, mà không khoá đường nâng cấp lên CDN khi cần scale.

## A2. Các quyết định

### A2.1 — Storage: thư mục local trước, Cloudflare R2 sau

| | |
|---|---|
| **Chốt** | Giai đoạn đầu: ghi file vào thư mục, FastAPI serve tĩnh tại `/media` (**chỉ bật ở development**). Khi có domain: chuyển sang Cloudflare R2 |
| **Thay vì** | AWS S3 · MinIO trong Compose · Backblaze B2 · Supabase Storage |
| **Vì sao** | Người dùng loại AWS (nhà cung cấp), nhưng chấp nhận S3 API — nên R2 là đích hợp lý. **Nhưng R2 chỉ có egress $0 + CDN khi gắn custom domain, mà domain đó phải nằm trên DNS của Cloudflare.** URL mặc định `pub-*.r2.dev` bị rate-limit và **không được CDN cache** — dùng nó thì R2 không hơn gì. Hiện chưa có domain ⇒ chưa vào R2 lúc này |
| **Vì sao không MinIO** | MinIO là service thứ 5 mà **runtime không dùng, CI không cần**, chỉ một script offline gọi tới. Thêm nó là thêm chi phí vận hành cho một runtime không tồn tại |
| **Đánh đổi** | Thư mục local không scale và không có CDN. Chấp nhận được vì MVP chưa có tải thật, và key là content-addressed nên chuyển nhà chỉ là copy file + đổi biến env |

Ước lượng dung lượng để biết free tier có đủ không: clip dictation ~10 giây ≈ 80 KB; một từ vựng ≈ 8–16 KB; một đề Listening đầy đủ ≈ 20 MB. Toàn bộ audio cho MVP **dưới 1 GB** — free tier 10 GB của R2 không phải giải pháp tạm bợ mà đủ dùng rất lâu.

**Điều quan trọng cần nhớ:** chi phí thật của một app audio là **egress**, không phải dung lượng lưu trữ. Đó là lý do R2 (egress $0) được chọn làm đích thay vì S3 (egress ~$0,09/GB).

### A2.2 — Nguồn audio: chỉ TTS, không cào (ở MVP)

| | |
|---|---|
| **Chốt** | Sinh toàn bộ audio bằng TTS từ transcript |
| **Thay vì** | Cào audio từ nguồn miễn phí · kết hợp cả hai |
| **Vì sao** | **Với dictation, transcript chính là đáp án chấm bài** — nên phải có text trước dù chọn đường nào. Cào audio thì vẫn phải kiếm transcript khớp; nguồn không kèm transcript thì phải chạy ASR, tức thêm cả một hệ thống nữa. TTS đi ngược lại rất có lợi: soạn text một lần, audio gần như miễn phí |
| **Thêm một lý do** | TOEIC bắt buộc 4 giọng Mỹ/Anh/Úc/Canada. Với TTS đây chỉ là đổi tham số voice; với cào thì nó thành bài toán tìm nguồn |
| **Đánh đổi** | Giọng TTS kém tự nhiên hơn giọng người thật. Chấp nhận ở MVP; cào có thể thêm sau qua cùng bảng `audio_asset`, phân biệt bằng cột `source` |

### A2.3 — Engine TTS: edge-tts

| | |
|---|---|
| **Chốt** | `edge-tts` |
| **Thay vì** | Azure Speech free tier (500K ký tự neural/tháng) · Piper (chạy local) |
| **Vì sao** | Miễn phí, không cần tài khoản hay API key, đủ 4 giọng, chất lượng neural cao. Piper bị loại vì giọng Úc/Canada gần như không có — không đáp ứng yêu cầu TOEIC |
| **Đánh đổi** | edge-tts là client reverse-engineer API **không chính thức** của Microsoft. Xem A3 |

### A2.4 — Phục vụ audio: URL công khai cố định

| | |
|---|---|
| **Chốt** | URL công khai, không presigned |
| **Thay vì** | Presigned URL hết hạn ngắn |
| **Vì sao** | Hệ quả quan trọng nhất: **runtime API không gọi object store lần nào** — nó chỉ ghép chuỗi `{base_url}/{storage_key}`. Không thêm round-trip trước mỗi lần phát, CDN cache được tối đa, tua/seek mượt |
| **Đánh đổi** | Ai có URL đều nghe được, không chống được hotlink. Audio là nội dung học chứ không phải tài sản bí mật; siết lại sau vẫn được mà không phải đổi kiến trúc |

### A2.5 — Thời điểm sinh: offline, không phải runtime

| | |
|---|---|
| **Chốt** | Script offline sinh sẵn toàn bộ, runtime chỉ đọc |
| **Thay vì** | Sinh khi user mở bài lần đầu rồi cache |
| **Vì sao** | Không job queue, không trạng thái `pending`/`failed`, không retry, không 202 + polling. Kiểm soát được chất lượng trước khi user nhìn thấy |
| **Đánh đổi** | Nội dung mới phải chạy script thủ công. Chấp nhận được vì nội dung học không sinh ra liên tục |

Quyết định này còn là **cơ chế giảm rủi ro chính** cho A2.3 — xem A3.

### A2.6 — Đường đi của dữ liệu: manifest commit vào repo

| | |
|---|---|
| **Chốt** | Pipeline xuất `content/manifest/audio_assets.jsonl` (commit vào repo); một lệnh `seed` riêng upsert vào DB theo `source_hash` |
| **Thay vì** | Script sinh audio ghi thẳng vào DB |
| **Vì sao** | Ghi thẳng vào DB ngầm giả định **chỉ có một database**. Thực tế script chạy ở máy dev còn dữ liệu phải tới được DB production. Manifest giải quyết: được review trong PR, CI validate được **không cần mạng**, và `seed` chỉ cần stdlib + sqlalchemy nên chạy được trong image production mà không phải cài `edge-tts` |
| **Đánh đổi** | Thêm một bước. Đổi lại được tính tái tạo và một artifact review được |

## A3. Rủi ro đã biết và cách khoanh vùng

**Rủi ro: edge-tts có thể chết bất cứ lúc nào.** Nó là client reverse-engineer của tính năng Read Aloud trên Edge. Microsoft đổi token ký `Sec-MS-GEC` định kỳ; mỗi lần đổi, thư viện chết đồng loạt với lỗi 403 cho tới khi upstream vá. Việc này đã xảy ra nhiều lần. Ngoài ra có rate-limit theo IP, và về lý thuyết là vi phạm ToS.

**Cơ chế giảm thiểu chính không phải abstraction, mà là quyết định sinh offline (A2.5).**

```
sinh OFFLINE, không phải runtime
   ↓
file mp3 đã sinh nằm trên đĩa/R2 và trong manifest
   ↓
edge-tts chết ⇒ chặn NỘI DUNG MỚI, không làm hỏng nội dung đã có
```

`TTSEngine` Protocol chỉ khoanh vùng *code* — nó cho phép đổi adapter mà không viết lại pipeline. Nó **không** cứu được:

- **Voice identity.** Nếu phải đổi engine giữa chừng, bài cũ giữ giọng cũ, bài mới giọng mới. Không né được, chỉ có thể chấp nhận hoặc sinh lại toàn bộ.
- **Rate limit.** Cần retry + backoff. May mắn là `source_hash` idempotent cho khả năng resume miễn phí — chạy lại chỉ làm phần còn thiếu.

## A4. Ràng buộc bất biến

Bốn điều dưới đây là những chỗ dễ làm sai và hậu quả không hiện ra ngay. Vi phạm bất kỳ điều nào đều tạo ra lỗi âm thầm.

### A4.1 — Không file nào trong chuỗi import của `app/main.py` được import `app.content`

Image production build bằng `uv sync --frozen --no-dev`, **không có** extra `content`. Job `docker` trong CI chạy `from app.main import app`. Nếu pipeline rò rỉ vào chuỗi import runtime, image sẽ chết vì thiếu `edge-tts`.

`app/content/__init__.py` phải **rỗng**. `app/models/audio.py` chỉ import sqlalchemy và `app.core.media` (thuần stdlib).

Có hai cái bẫy an toàn cho quy tắc này. `tests/test_content_isolation.py` chạy `import app.main` trong subprocess rồi soi `sys.modules` — dưới một giây, ngay trên máy dev. Job `docker` bắt được bằng cách boot image thật, chậm hơn nhưng là bằng chứng cuối cùng.

### A4.2 — `source_hash` là hash của INPUT, không phải hash của bytes

```
source_hash = sha256(source_text | voice | engine | engine_version)
```

**Không** phải sha256 của file mp3. TTS không tất định theo byte — hash bytes sẽ làm hỏng idempotency: chạy lại sinh ra hash mới, dẫn tới insert trùng thay vì skip.

Đây là toàn bộ cơ sở của tính idempotent. Đặt tên `content_hash` là sai và đã gây nhầm lẫn một lần trong quá trình thiết kế.

### A4.3 — `voice` lưu trong DB và trong hash là voice LOGIC, không phải ID của nhà cung cấp

Lưu `us_female_1`, **không** lưu `en-US-JennyNeural`. Adapter của từng engine tự map logic → ID nhà cung cấp.

Ràng buộc này đã trả cổ tức ngay trong lúc triển khai: `en-AU-WilliamNeural` bị Microsoft đổi tên thành `en-AU-WilliamMultilingualNeural`. Vì hash tính trên tên logic, sửa một dòng trong bảng map là xong — không asset nào phải sinh lại.

Nếu ID nhà cung cấp lọt vào hash, ngày đổi sang Piper/Azure sẽ làm **mọi `source_hash` cũ vô hiệu**, buộc sinh lại toàn bộ thư viện audio. Đây chính là khác biệt giữa một abstraction dùng được và một abstraction trang trí.

### A4.6 — Dàn narrator: bốn giọng, giới tính gắn cứng vào quốc tịch

Thêm 2026-09-01, sau khi đo lại đề thật.

`LOGICAL_VOICE_ACCENTS` có **tám** giọng (4 accent × 2 giới) và cả tám vẫn hợp lệ cho nội dung dán tay. Nhưng đề thật chỉ có **bốn** narrator, và cặp quốc tịch–giới tính của họ cố định qua mọi bộ đề chính thức:

| Accent | Giới tính | Giọng logic |
|---|---|---|
| en-US | nữ | `us_female_1` |
| en-CA | nam | `ca_male_1` |
| en-GB | nữ | `uk_female_1` |
| en-AU | nam | `au_male_1` |

Bốn cặp còn lại — Mỹ nam, Canada nữ, Anh nam, Úc nữ — **không tồn tại trong bài thi**. ETS không công bố luật này; nó là kết luận đối chiếu các bộ 公式問題集, nhưng nó nhất quán và kéo theo một hệ quả mà một dàn tám giọng tự do không có:

> **Một hội thoại hai người là một nam một nữ, nên hai người nói LUÔN khác quốc tịch.**

Đó là lý do `TOEIC_NARRATORS` nằm ở `app/core/media.py` chứ không ở `blueprint.py`: nó là một sự thật về miền, và cả phần sinh đề, phần từ vựng lẫn phần dictation đều phải theo cùng một dàn — người học gặp bốn giọng ấy trong phòng thi, nên gặp một dàn khác lúc luyện là luyện một thứ sẽ không gặp.

**Việc rải giọng là chia đều rồi xáo, không phải xoay vòng.** `pool[(index + seed) % len(pool)]` không phải ngẫu nhiên mà là đếm: 25 câu Part 2 trên tám cặp lặp lại đúng thứ tự ấy ba lần, và `seed` chỉ dịch điểm bắt đầu. `_deal` chia đều theo seed, `_spread` đẩy hai ô liền nhau ra khỏi nhau, và `_casting_problems` đặt luật cứng ở tầng part: mỗi accent chiếm 15–35% số lượt nói, và không ba ô liền nhau dùng chung một dàn giọng. Đo trên 60 seed: tỉ lệ nằm trong dải 24–27%, không seed nào bị từ chối.

**Chất lượng thì không đối xứng, và không sửa được ở tầng này.** edge-tts còn giọng thế hệ HD cho `en-US` (Ava, Andrew) nhưng chỉ còn thế hệ cũ cho `en-GB`, `en-AU` và `en-CA` — `en-CA` là kém nhất. Đồng đều bốn accent đòi đổi engine cho ba locale kia, và không nhà cung cấp lớn nào có giọng `en-CA` riêng (tiếng Canada quá gần tiếng Mỹ). Đây là giới hạn đã biết, không phải thứ bỏ sót.

### A4.4 — `audio_asset.source_text` KHÔNG phải nguồn sự thật để chấm bài

Nó là text đã đưa vào TTS, tồn tại để tính hash và sinh lại. Khi §7a tạo `dictation_item.transcript`, **transcript ở đó mới là đáp án chấm bài**.

Nếu lẫn lộn hai thứ này, sẽ có hai bản sao lệch nhau và không ai biết bản nào đúng. Phải ghi comment cảnh báo ngay trong model.

**Cập nhật 2026-08-09 — hai bản sao *có thể* lệch nhau thật, và giờ đã có cái phát hiện.** Sửa `transcript` mà không sinh lại audio ⇒ học viên nghe câu cũ nhưng bị chấm theo câu mới. `app/services/media_state.py` bắt được bằng cách tính lại `source_hash` từ transcript hiện tại và so với `audio_asset.source_hash` — không cần thêm cột nào, thuần tuý là cổ tức của A4.2. Cổng publish từ chối nội dung lệch; `backfill_audio` sinh lại. Nó so với **`dictation_item.transcript`**, không bao giờ với `source_text` — đúng như mục này quy định. Chi tiết: [`MEDIA-PIPELINE.md`](MEDIA-PIPELINE.md) §10.1.

### A4.5 — Hash của một clip nhiều giọng phải mang cả DANH SÁCH lượt, có thứ tự

Hệ quả trực tiếp của A4.2, thêm vào 2026-08-10 khi §10.2 được gỡ.

`conversation_source_hash(turns, gap_ms, engine, engine_version)` băm từng cặp `(text, voice)` **theo đúng thứ tự xuất hiện**, kèm `gap_ms` và số lượt. Ba thứ trong đó, bỏ cái nào cũng hỏng im lặng theo cùng một kiểu — lần sinh sau "bỏ qua vì đã có" trong khi nội dung đã khác:

- **Thứ tự.** Đảo hai lượt là một đoạn hội thoại khác.
- **`gap_ms`.** Khoảng lặng là một phần của file phát ra.
- **Tiền tố `"conversation"`.** Không có nó, một hội thoại *một lượt* băm trùng với một clip đơn cùng text và giọng — hai thứ tạo bằng hai đường khác nhau dùng chung một `storage_key`, và cái tới sau lặng lẽ thắng.

`audio_asset.voice` của clip loại này là `"multi"`, nên `media_state.clip_state` **không xác minh được nó**. Hiện chưa cần: `media_state` chỉ soi `dictation_item` và `vocabulary_audio`, còn clip hội thoại gắn vào `question`/`question_set`. Sẽ cần khi Part 3 có bản ghi lời lưu trong database.

## A5. Đường nâng cấp lên Cloudflare R2

Điều kiện tiên quyết: **có domain trên DNS Cloudflare**. Không có thì R2 không mang lại lợi ích gì so với hiện tại.

`ObjectStore` Protocol có hai hiện thực — `LocalDirStore` (bây giờ) và `S3ObjectStore` (sau). Key content-addressed nên chuyển nhà = copy file + đổi biến env, không sửa code gọi.

Khi làm `S3ObjectStore`, **ba cấu hình bắt buộc**; thiếu bất kỳ cái nào là mất phần lớn giá trị:

| Cấu hình | Vì sao |
|---|---|
| botocore `Config(request_checksum_calculation="when_required", response_checksum_validation="when_required")` | boto3 ≥ 1.36 mặc định gửi `x-amz-checksum-crc32` + `aws-chunked`, **gây lỗi với R2**. Đây là footgun số 1 hiện nay |
| `ContentType="audio/mpeg"` tường minh lúc `put_object` | Mặc định là `binary/octet-stream`; trình duyệt xử lý sai và không seek được |
| `CacheControl="public, max-age=31536000, immutable"` | Không set thì mất phần lớn giá trị CDN. An toàn tuyệt đối vì key là content-addressed |

Ngoài ra: `region="auto"`, endpoint `https://<account-id>.r2.cloudflarestorage.com`. R2 **vẫn yêu cầu gắn thẻ thanh toán** để bật, kể cả khi chỉ dùng free tier (10 GB storage, 10M lượt đọc/tháng, egress không giới hạn).

**CORS:** thẻ `<audio src>` thuần **không cần** CORS. Chỉ cần khi đọc audio bằng `fetch()`/Web Audio API — ví dụ vẽ waveform. MVP dùng `<audio>` native nên để ngoài phạm vi; nếu sau này làm waveform thì phải cấu hình CORS trên bucket.

**Không bao giờ proxy audio qua FastAPI.** Sẽ mất range request (không tua được) và đốt băng thông của API.

## A6. Ảnh hưởng đã biết tới §7a (data model)

`audio_asset` được thiết kế **độc lập** với schema domain chưa có. Chiều phụ thuộc là domain → asset, nên §7a sẽ **thêm** bảng chứ không **sửa** `audio_asset`.

Nhưng có một điều §7a phải biết trước:

> **Yêu cầu 4 giọng làm một cột FK đơn không đủ.** Mỗi từ vựng cần 4 asset (US/UK/AU/CA). §7a sẽ phải thêm bảng nối, đại loại `vocabulary_audio(entry_id, audio_asset_id, accent)`.

`accent` chuẩn hoá theo BCP-47: `en-US`, `en-GB`, `en-AU`, `en-CA`. Không dùng free text.

## A7. Khi nào nên xem lại tài liệu này

- **Khi có domain trên Cloudflare** → thực hiện A5, chuyển sang R2
- **Khi edge-tts chết** → đổi adapter; cân nhắc Azure Speech free tier; chấp nhận lệch giọng giữa nội dung cũ và mới (A3)
- **Khi bắt đầu cào audio thật** → thêm `source='scraped'`, cần thêm ffmpeg (chuẩn hoá loudness, tách đoạn) và chỗ lưu nguồn gốc + giấy phép
- **Khi làm waveform UI** → cấu hình CORS trên bucket (A5)
- **Khi audio vượt ~8 GB** → xem lại free tier R2 và chiến lược lưu trữ

---
---

# PHẦN B — NHẬT KÝ TRIỂN KHAI

> Checklist gốc đã hoàn thành ngày **2026-08-09** và được thay bằng bản ghi này.
> Phần A ở trên vẫn là tài liệu sống. Phần B chỉ còn giá trị tra cứu "đã làm gì, lệch chỗ nào".

## B1. Kết quả

| Hạng mục | Kết quả |
|---|---|
| Naming content-addressed | `app/core/media.py` — thuần stdlib, cả runtime lẫn pipeline đều import được |
| Bảng | `audio_asset` + migration `002_audio_assets` (`down_revision="001_initial"`), `upgrade`/`downgrade` đều chạy sạch trên Postgres |
| Pipeline offline | `app/content/{settings,tts,storage,manifest,generate,seed}.py`, sau extra `content` |
| Nội dung mẫu | 16 clip đã sinh thật bằng edge-tts (3 từ × 4 giọng + 4 câu dictation), phủ đủ 4 accent |
| Manifest | `apps/api/content/manifest/audio_assets.jsonl` — commit vào repo, sắp xếp theo hash |
| Phục vụ | `/media` mount, **chỉ khi `environment == "development"`**; 200 + `audio/mpeg`, 206 cho Range |
| Test | 62 → **119** (2 test `external` bị deselect mặc định) |
| CI | job `api` đổi sang `uv sync --extra dev --extra content` |
| Service mới | **không có** — đúng như A2.1 |

## B2. Những chỗ lệch so với checklist gốc

Năm chỗ. Bốn cái đầu là cải thiện phát hiện lúc làm; cái cuối là lỗi thật mà test bắt được.

1. **Tách thêm `app/content/manifest.py`.** Checklist để hàm đọc/ghi manifest nằm trong `generate.py`. Nhưng `seed.py` cũng cần chúng, mà `seed` phải chạy được trong image production. Import ngược từ `generate` sẽ kéo theo cả chuỗi phụ thuộc của pipeline. Module riêng thuần stdlib giải quyết gọn, và chỗ này cũng là nơi đặt `validate_record()` — dùng chung bởi cả `seed` lẫn test CI.

2. **`ObjectStore` có thêm `exists()`.** Checklist chỉ ghi `put()`. Nhưng manifest được commit còn file mp3 thì `.gitignore` — nên trên một bản clone mới, entry tồn tại mà bytes thì không. Nếu chỉ skip theo manifest, những entry đó sẽ **không bao giờ** được sinh lại. Điều kiện skip đúng là *có trong manifest* **và** *có file trong store*. Có test riêng cho tình huống này.

3. **Thêm `tests/test_content_isolation.py`.** A4.1 trước đó chỉ được bảo vệ bởi job `docker` trong CI — đúng nhưng chậm và chỉ đỏ sau khi đã push. Test này chạy `import app.main` trong subprocess rồi soi `sys.modules`, mất chưa tới một giây. (Phải là subprocess: chính session test này có import `app.content` ở chỗ khác, kiểm tra in-process sẽ báo rò rỉ giả.) Đã xác nhận nó đỏ khi cố tình vi phạm.

4. **Thêm `alembic/script.py.mako`.** File này thiếu trong repo, nghĩa là lệnh `alembic revision --autogenerate` mà `CLAUDE.md` ghi trong mục Commands **chưa bao giờ tạo được file**. Phát hiện khi dùng autogenerate để kiểm tra model và migration `002` có khớp nhau không.

5. **`en-AU-WilliamNeural` không còn tồn tại** — Microsoft đã đổi tên thành `en-AU-WilliamMultilingualNeural`. `tests/test_tts_external.py` bắt được bằng cách đối chiếu `LOGICAL_VOICES` với catalogue thật. Đây chính là chỗ A4.3 trả cổ tức: vì hash tính trên **tên logic**, đổi id nhà cung cấp không làm hỏng một asset nào đã sinh — chỉ sửa một dòng trong bảng map. Nếu id nhà cung cấp nằm trong hash thì đã phải sinh lại toàn bộ thư viện.

## B3. Đã kiểm chứng bằng cách chạy thật

- `generate` chạy hai lần: lần hai skip 16/16, không gọi TTS
- `seed` chạy hai lần: `16 inserted` → `0 inserted · 16 unchanged`, `count(*)` không đổi
- `curl -I` trên `/media/...`: **200** + `content-type: audio/mpeg`; với `Range: bytes=0-1024` trả **206** ⇒ tua được
- 12 file vocabulary có 12 md5 khác nhau (kích thước byte trùng nhau chỉ vì mp3 CBR cùng độ dài 1,776 s)
- Image production: `edge_tts` và `mutagen` **vắng mặt**; `from app.main import app` chạy được; `app.content.seed` import được; `app.content.generate` hỏng đúng chỗ gọi `mutagen`
- `alembic upgrade head` → `downgrade base` → `upgrade head` sạch; `--autogenerate` cho diff rỗng ⇒ model và migration khớp nhau

## B5. Ghép clip nhiều giọng — đã kiểm chứng bằng cách chạy thật (2026-08-10)

Chạy tay, không dựng test, đúng theo luật ở `CLAUDE.md`: *"nếu một luồng chỉ kiểm được với dịch vụ thật thì chạy một lần bằng tay và ghi lại điều học được"*. Ở đây "dịch vụ thật" là ffmpeg cộng edge-tts, và bộ khung để kiểm tự động sẽ đắt hơn thứ nó bảo vệ.

| Kiểm | Kết quả |
|---|---|
| Nối 3 clip edge-tts cùng tham số, `-c copy` | 8304 ms, mong đợi 8236 ms — lệch do làm tròn biên khung |
| Nối 24 kHz mono với 44.1 kHz stereo | Lệch tham số ⇒ tự mã lại, ra 24 kHz mono, độ dài đúng |
| Part 2 đã sinh (`gap_ms=600`) | 16,8 s, `silencedetect` thấy đúng 3 khoảng lặng nội bộ |
| Part 3 đã sinh (`gap_ms=450`) | 39,6 s, đúng 3 ranh giới người nói |
| Phát từ Supabase | 200 · `audio/mpeg` · 237 692 byte · 39,576 s |

**Điều học được mà không đoán ra trước:**

1. **Đối chiếu độ dài KHÔNG bắt được lệch tham số.** Bản đầu của `join_turns` chỉ so độ dài file ra với tổng mong đợi. Nối 24 kHz mono với 44.1 kHz stereo: ffmpeg không báo lỗi, ffprobe vẫn đọc ra độ dài gần đúng, phép kiểm lọt — nhưng phần sau phát sai tốc độ. Phải kiểm **tham số**, không kiểm triệu chứng. Phép so độ dài vẫn giữ, nhưng chỉ còn là lưới thứ hai cho hỏng nặng.
2. **`gap_ms` là phần cộng thêm, không phải tổng.** edge-tts đệm ~1,1 s ở mỗi ranh giới lượt. `gap_ms=0` cho ra ~1,1 s, vốn đã là nhịp tự nhiên.

## B4. Chưa làm (có chủ ý)

- **`S3ObjectStore` / R2** — chặn bởi điều kiện tiên quyết ở A5: phải có domain trên DNS Cloudflare. Biến `R2_*` đã có sẵn trong `.env.example` dưới dạng comment.
- **Nội dung thật** — 16 clip hiện tại là mẫu để chứng minh đường ống chạy được, không phải giáo trình. Nội dung thật phụ thuộc vào data model (§7a).
