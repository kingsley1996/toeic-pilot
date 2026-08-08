# Phase 2 — Hạ tầng Audio

**Trạng thái:** Đã chốt quyết định (2026-08-08) · Chưa triển khai
**Thay thế cho:** `ADR-002` mà `REVIEW-OPUS.md` §8 Sprint 2 yêu cầu
**Liên quan:** `REVIEW-OPUS.md` §7b (rủi ro kiến trúc số 2), §7a (data model — vẫn đang mở)

Tài liệu này có hai phần với vòng đời khác nhau:

- **Phần A — Quyết định kiến trúc.** Còn giá trị sau khi triển khai xong. Đọc lại sau 6 tháng vẫn phải trả lời được "vì sao lại làm thế này".
- **Phần B — Checklist thực thi.** Hết hạn ngay khi làm xong. Xoá hoặc thu gọn thành một dòng khi Phase 2 kết thúc.

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

`app/content/__init__.py` phải **rỗng**. `app/models/audio.py` chỉ import sqlalchemy.

Job `docker` chính là cái bẫy an toàn cho quy tắc này — nó đỏ ngay khi có ai vi phạm.

### A4.2 — `source_hash` là hash của INPUT, không phải hash của bytes

```
source_hash = sha256(source_text | voice | engine | engine_version)
```

**Không** phải sha256 của file mp3. TTS không tất định theo byte — hash bytes sẽ làm hỏng idempotency: chạy lại sinh ra hash mới, dẫn tới insert trùng thay vì skip.

Đây là toàn bộ cơ sở của tính idempotent. Đặt tên `content_hash` là sai và đã gây nhầm lẫn một lần trong quá trình thiết kế.

### A4.3 — `voice` lưu trong DB và trong hash là voice LOGIC, không phải ID của nhà cung cấp

Lưu `us_female_1`, **không** lưu `en-US-JennyNeural`. Adapter của từng engine tự map logic → ID nhà cung cấp.

Nếu ID nhà cung cấp lọt vào hash, ngày đổi sang Piper/Azure sẽ làm **mọi `source_hash` cũ vô hiệu**, buộc sinh lại toàn bộ thư viện audio. Đây chính là khác biệt giữa một abstraction dùng được và một abstraction trang trí.

### A4.4 — `audio_asset.source_text` KHÔNG phải nguồn sự thật để chấm bài

Nó là text đã đưa vào TTS, tồn tại để tính hash và sinh lại. Khi §7a tạo `dictation_item.transcript`, **transcript ở đó mới là đáp án chấm bài**.

Nếu lẫn lộn hai thứ này, sẽ có hai bản sao lệch nhau và không ai biết bản nào đúng. Phải ghi comment cảnh báo ngay trong model.

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

# PHẦN B — CHECKLIST THỰC THI

> ⚠️ **Phần này hết hạn khi triển khai xong.** Khi Phase 2 kết thúc, xoá toàn bộ Phần B và thay bằng một dòng ghi ngày hoàn thành. Phần A giữ lại.

## B1. Files cần tạo

### Runtime — không thêm dependency nào

| File | Nội dung |
|---|---|
| `apps/api/app/core/media.py` | Thuần stdlib. `source_hash(text, voice, engine, engine_version) -> str` · `storage_key_for(source_hash, ext="mp3") -> str` (dạng `audio/{h[:2]}/{h}.mp3`) · `public_audio_url(storage_key) -> str` — **phải xử lý dấu `/` thừa ở cuối base URL** (lỗi double-slash kinh điển). Đặt ở `core` để cả test lẫn `app/content` import được mà không cần extra |
| `apps/api/app/models/audio.py` | `AudioAsset`. Chỉ import sqlalchemy. Theo style `Mapped[...]` của `app/models/user.py` |
| `apps/api/alembic/versions/002_audio_assets.py` | `revision="002_audio_assets"`, **`down_revision="001_initial"`** (revision id thật, không phải tên file) |

Schema `audio_asset`:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | UUID | PK |
| `storage_key` | String(512) | unique |
| `source_hash` | String(64) | unique, index — xem A4.2 |
| `mime_type` | String(64) | |
| `size_bytes` | Integer | |
| `duration_ms` | Integer | |
| `source` | String(16) | `tts`/`scraped`/`uploaded` + CHECK constraint. **Không** dùng native enum — Alembic downgrade với enum type rất phiền |
| `engine` | String(32) | vd `edge-tts` |
| `engine_version` | String(32) | |
| `voice` | String(32) | **logic**, vd `us_female_1` — xem A4.3 |
| `accent` | String(8) | BCP-47 |
| `source_text` | Text nullable | + comment cảnh báo — xem A4.4 |
| `created_at` | DateTime(tz) | |

### Content pipeline — extra `content`, cô lập hoàn toàn

| File | Nội dung |
|---|---|
| `apps/api/app/content/__init__.py` | **Rỗng.** Xem A4.1 |
| `apps/api/app/content/settings.py` | `ContentSettings(BaseSettings)`: `object_store_dir`, `tts_engine_version`, (để dành) `r2_*`. **Không đụng `app.core.config`** — credential ghi bucket không được nằm trong env của process phục vụ HTTP |
| `apps/api/app/content/tts.py` | `TTSEngine` Protocol (`name`, `version`, `synthesize(text, voice) -> bytes`). `LOGICAL_VOICES` map `us_female_1 → {"edge": "en-US-…", "accent": "en-US"}`, đủ 4 accent. `EdgeTTSEngine` có retry + backoff |
| `apps/api/app/content/storage.py` | `ObjectStore` Protocol (`put(key, data, content_type)`). `LocalDirStore` bây giờ; `S3ObjectStore` khi làm A5 |
| `apps/api/app/content/generate.py` | CLI `python -m app.content.generate --input <jsonl> [--dry-run]`. Đọc spec → `source_hash` → skip nếu đã có trong manifest → synth → `mutagen` đọc duration → `put` → append manifest. **Không chạm DB** |
| `apps/api/app/content/seed.py` | CLI `python -m app.content.seed`. Đọc manifest → upsert theo `source_hash`. **Chỉ stdlib + sqlalchemy** |
| `apps/api/content/sources/*.jsonl` | Input spec (text + voice logic) |
| `apps/api/content/manifest/audio_assets.jsonl` | Artifact commit vào repo |

### Tests

`tests/test_media.py` · `tests/test_audio_model.py` · `tests/test_content_manifest.py` · `tests/test_tts_external.py` (marker `external`)

## B2. Files cần sửa

| File | Thay đổi |
|---|---|
| `apps/api/app/core/config.py` | Thêm **duy nhất** `audio_public_base_url: str = "http://localhost:8000/media"`. Không thêm secret nào |
| `apps/api/app/main.py` | Mount `StaticFiles` tại `/media`, **có guard `settings.environment == "development"`**. Starlette có sẵn, không thêm dep |
| `app/models/__init__.py` · `alembic/env.py` · `tests/conftest.py` | Import `AudioAsset` ở **cả ba** chỗ. `CLAUDE.md` đã ghi: thiếu chỗ thứ ba là "no such table" trong test |
| `apps/api/pyproject.toml` | Group `content = ["edge-tts>=7", "mutagen>=1.47"]` (thêm `boto3` khi làm A5) · mypy overrides cho `edge_tts.*`/`mutagen.*` theo khuôn `jose.*` đang có · marker `external` · `addopts = -m "not external"` |
| `.env.example` | `AUDIO_PUBLIC_BASE_URL=` · block `R2_*` comment rõ *"content pipeline only — API runtime không cần"* |
| `.github/workflows/ci.yml` | Job `api`: `uv sync --extra dev --extra content`. Không có thì mypy/ruff bỏ sót `app/content/` |
| `docker/docker-compose.yml` | **Không thêm service.** Chỉ thêm `AUDIO_PUBLIC_BASE_URL` vào `environment` của `api` |
| `CLAUDE.md` | Mục storage/content + quy tắc cô lập import (A4.1) |

## B3. Thứ tự triển khai

1. `app/core/media.py` + `tests/test_media.py` — thuần stdlib, xanh ngay, không phụ thuộc gì
2. `models/audio.py` + migration 002 + import ở 3 chỗ + `tests/test_audio_model.py`
3. `app/content/{settings,tts,storage}.py` + `generate.py` — verify bằng `--dry-run` rồi sinh thật ~10 clip
4. `seed.py` + manifest + `tests/test_content_manifest.py`
5. `main.py` mount + config + `.env.example` + `pyproject.toml` + CI + `CLAUDE.md`

Job `contract` **không đổi ở cả 5 bước** vì chưa có endpoint mới. Khoảnh khắc §7a lộ `audio_url` ra response mới phải chạy `pnpm gen:api-types`, commit kết quả, và thêm entry vào `API_ROUTES`.

## B4. Verification

### Test tự động — theo convention hiện có (`apps/api/tests/conftest.py`)

- **Pure unit, không fixture:** `source_hash()` tất định (2 lần cùng input ⇒ cùng kết quả; đổi voice ⇒ đổi hash) · `public_audio_url()` với base URL **có và không có** dấu `/` cuối
- **Dùng `db_session`** (SQLite/StaticPool có sẵn): unique constraint trên `source_hash` và `storage_key` · **chạy `seed` hai lần cho ra cùng số hàng** — đây là test giá trị nhất, nó chính là thứ chứng minh idempotency
- **Manifest validation, không cần mạng:** mỗi dòng có `storage_key == storage_key_for(source_hash)` và `accent` thuộc 4 giá trị hợp lệ. Bắt được manifest sửa tay
- **Marker `external`** (khác `integration` vốn nghĩa "cần Postgres thật"): test gọi edge-tts thật, mặc định deselect. **CI tuyệt đối không gọi edge-tts**

### Kiểm chứng end-to-end thủ công

```bash
cd apps/api && uv sync --extra dev --extra content

uv run alembic upgrade head
docker compose -f ../../docker/docker-compose.yml exec -T postgres \
  psql -U toeic -d toeic -c '\d audio_asset'

uv run python -m app.content.generate --input content/sources/sample.jsonl --dry-run
uv run python -m app.content.generate --input content/sources/sample.jsonl
uv run python -m app.content.generate --input content/sources/sample.jsonl   # lần 2 phải skip toàn bộ

uv run python -m app.content.seed
uv run python -m app.content.seed                    # lần 2: số hàng không đổi

uv run uvicorn app.main:app --port 8000 &
curl -sI http://localhost:8000/media/audio/ab/abc….mp3            # 200 + Content-Type: audio/mpeg
curl -sI -H 'Range: bytes=0-1024' http://localhost:8000/media/…   # 206 ⇒ tua được
```

### Kiểm chứng cô lập import — quan trọng nhất, bảo vệ image production

```bash
docker build -f docker/api.Dockerfile -t toeic-api:audio .
docker run --rm -e RUN_MIGRATIONS=0 -e DATABASE_URL=sqlite+pysqlite:///:memory: \
  toeic-api:audio .venv/bin/python -c "from app.main import app; print('ok')"
```

Image build bằng `--no-dev` nên **không có** `edge-tts`/`mutagen`. Lệnh này xanh ⇒ chứng minh `app.content` không rò rỉ vào chuỗi import runtime (A4.1).

### Gate đầy đủ — 13 gate hiện có phải giữ xanh

```bash
cd apps/api && uv run ruff check app tests && uv run ruff format --check app tests \
  && uv run mypy && uv run pytest
cd ../.. && pnpm format:check && pnpm --filter @toeic-pilot/web lint && pnpm build
```
