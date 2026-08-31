# Media Pipeline — Audio và Image hoạt động thế nào

**Trạng thái:** Mô tả hiện trạng · 2026-08-09
**Phạm vi:** những gì **đang chạy trong repo**, không phải những gì dự định làm

Tài liệu này trả lời **"nó hoạt động thế nào"** và **"chỗ nào yếu"**. Câu hỏi **"vì sao lại thiết kế thế"** đã có chỗ khác trả lời, và tài liệu này cố ý không lặp lại:

- [`PHASE2-AUDIO.md`](PHASE2-AUDIO.md) Phần A — quyết định kiến trúc audio (đây là ADR-002)
- [`ADR-004-IMAGES.md`](ADR-004-IMAGES.md) — quyết định về ảnh
- [`ADR-001-DATA-MODEL.md`](ADR-001-DATA-MODEL.md) — nơi media gắn vào schema domain

Khi hai bên mâu thuẫn, **các ADR đúng** — đó là bản ghi quyết định; tài liệu này chỉ mô tả hiện trạng và sẽ lỗi thời trước.

---

## 1. Toàn cảnh

Hai đường ống **cấu trúc giống hệt nhau, đầu vào khác nhau**.

```
   AUDIO                                    IMAGE
   ─────                                    ─────
   content/sources/*.jsonl                  content/sources/images/*.jsonl
   {"text", "voices"}                       {"url", "license", "attribution"}
        │                                        │
        │  source_hash(                          │  image_source_hash(
        │    text│voice│engine│version)          │    url│transform_version)
        ↓                                        ↓
   đã có trong manifest VÀ file tồn tại?    (cùng một câu hỏi)
        │ chưa                                   │ chưa
        ↓                                        ↓
   edge-tts  ──► mp3                        httpx GET ──► bytes
        │                                        │
   mutagen → duration_ms                    Pillow → RGB, ≤1280px, JPEG q82, xoá EXIF
        │                                        │
        └──────────►  LocalDirStore.put()  ◄──────┘
                             │
              media/audio/ab/….mp3  ·  media/image/cd/….jpg
                             │
                    append vào manifest, sắp xếp theo hash
                             │
                    ┌────────┴────────┐
                    │  commit vào git │   ← chỉ manifest, KHÔNG có file media
                    └────────┬────────┘
                             │
                  uv run python -m app.content.seed
                             │
                  audio_asset  ·  image_asset
```

Điểm cần nắm ngay: **manifest được commit, file media thì không.** `apps/api/media/` nằm trong `.gitignore`. Hệ quả của điều này xuất hiện lại nhiều lần ở mục 9 và 10.

---

## 2. Nền chung — `app/core/media.py`

Thuần stdlib, và đó là điều kiện bắt buộc: cả API runtime lẫn pipeline offline đều import nó, mà hai bên có tập phụ thuộc khác nhau (mục 7).

### 2.1 Đặt tên content-addressed

```
audio/{hash[:2]}/{hash}.mp3
image/{hash[:2]}/{hash}.jpg
```

Shard hai ký tự chỉ để `ls` trong thư mục local còn dùng được khi thư viện lớn lên. Trên object store nó vô nghĩa vì không có thư mục thật.

### 2.2 Hash tính trên INPUT, không phải trên bytes

```python
source_hash(text, voice, engine, engine_version)    # audio
image_source_hash(source_url, transform_version)    # image
```

Ghép bằng `\x1f` (unit separator) chứ không phải `|`, để một text chứa dấu `|` không va vào cặp (text, voice) khác.

Với audio, lý do là **bắt buộc**: TTS không tất định theo byte, tổng hợp cùng một câu hai lần ra hai file mp3 khác nhau. Hash bytes sẽ cho hash mới mỗi lần chạy, biến "bỏ qua cái đã có" thành "chèn bản trùng".

Với ảnh thì tải về **là** tất định — nhưng ta không lưu bytes gốc, mà lưu bản đã chuẩn hoá, và Pillow không cam kết cho ra cùng bytes giữa các phiên bản. Nên vẫn hash input, cùng một lý do.

Hệ quả quan trọng, sẽ dùng lại ở mục 10: **so được hash hiện tại với hash đã lưu là biết audio còn khớp text hay không.** Nếu hash bytes thì không làm được điều này.

### 2.3 URL công khai

```python
public_audio_url(storage_key) -> f"{base_url.rstrip('/')}/{storage_key.lstrip('/')}"
```

Chỉ là ghép chuỗi. **Runtime không gọi object store lần nào** — không round-trip trước mỗi lần phát, CDN cache được tối đa, và range request đi thẳng tới nơi lưu nên tua được.

---

## 3. Đường ống audio

### 3.1 Đầu vào

```jsonl
{"text": "invoice", "voices": ["us_female_1", "ca_male_1", "uk_female_1", "au_male_1"]}
{"text": "The quarterly report is due Friday.", "voice": "us_female_1"}
```

`voices` sinh ra **N clip riêng biệt của cùng một text**, mỗi clip một giọng. Đây là hình dạng cho từ vựng: một từ, bốn accent. Nó **không** phải cách diễn đạt hội thoại nhiều người nói — xem 10.1.

### 3.2 Giọng logic

```python
LOGICAL_VOICES = {
    "us_female_1": LogicalVoice(accent="en-US", edge="en-US-AvaNeural"),
    "au_male_1":   LogicalVoice(accent="en-AU", edge="en-AU-WilliamMultilingualNeural"),
    ...  # 8 giọng, phủ đủ 4 accent × 2 giới
}
```

Tám giọng là những gì **dùng được**; bốn trong số đó là dàn narrator của đề thật (`TOEIC_NARRATORS`, PHASE2-AUDIO §A4.6) và mọi thứ tự sinh chỉ dùng bốn giọng ấy.

Trong DB và trong hash chỉ có `us_female_1`. ID nhà cung cấp nằm gọn ở đây.

Điều này đã trả cổ tức thật: Microsoft đổi tên `en-AU-WilliamNeural` thành `en-AU-WilliamMultilingualNeural`, và toàn bộ việc phải làm là sửa một dòng trong bảng map — không asset nào phải sinh lại.

**Dictation chọn giọng theo STORY, không theo từng câu.** `voice_for_dictation`
lấy khoá từ `story_id` nếu câu thuộc một bài, chỉ rơi về `item.id` với câu lẻ.
Ban đầu nó lấy theo `item.id` cho mọi trường hợp, và kết quả là một bài văn liền
mạch bị bốn giọng đọc luân phiên từng câu — đã thấy thật trong dev DB: sáu câu
của một story dùng ba giọng khác nhau.

Suy ra từ id chứ không lưu thành cột, nên không cần migration và không bao giờ
lệch. Nhưng đổi chính sách **không** làm mới audio đã có: `media_state` cố ý chỉ
hỏi "clip này có khớp text không", không hỏi "có đúng chính sách hiện tại
không". Story thu trước bản sửa giữ nguyên giọng lẫn lộn cho tới khi gỡ liên kết
audio rồi chạy lại `backfill_audio`.


### 3.3 Sinh

`EdgeTTSEngine.synthesize()` gọi `asyncio.run()` quanh `edge_tts.Communicate(...).stream()`, gom các chunk `type == "audio"`. Retry với backoff luỹ thừa, mặc định 4 lần, hệ số 2s.

`engine_version` **không** lấy từ phiên bản gói cài đặt mà là một núm vặn thủ công (`ContentSettings.tts_engine_version`, mặc định `"1"`). Nếu lấy từ gói thì mỗi lần nâng cấp edge-tts sẽ vô hiệu hoá toàn bộ thư viện audio.

### 3.4 Chạy lại

Bỏ qua khi **có trong manifest** VÀ **file tồn tại trong store**. Cả hai vế đều cần: manifest commit vào git còn mp3 thì không, nên trên một bản clone mới entry tồn tại mà bytes thì không. Chỉ xét manifest thì những entry đó vĩnh viễn không được sinh lại.

---

## 4. Đường ống image

### 4.1 Đầu vào

```jsonl
{"url": "https://upload.wikimedia.org/...jpg",
 "license": "CC BY 4.0",
 "attribution": "Goterrestrial, \"…\", CC BY 4.0, via Wikimedia Commons",
 "alt_text": "A forklift loading goods into a shipping container."}
```

Ba trường đầu **bắt buộc và không được rỗng**. Parser từ chối ngay ở tầng đọc spec, trước cả khi có kết nối mạng: phần lớn ảnh giấy phép mở là CC-BY, dùng được **với điều kiện** ghi công. Thiếu ghi công không phải lỗi định dạng mà là vi phạm giấy phép.

### 4.2 Tải

`httpx.get` với `follow_redirects=True` và header `User-Agent` định danh. Header này **bắt buộc chứ không phải lịch sự**: Wikimedia trả 403 cho User-Agent mặc định của thư viện. Giữa các lần tải có `image_fetch_delay_seconds` (mặc định 1,5s) — Wikimedia đã trả 429 giữa chừng ngay ở lượt chạy ba ảnh đầu tiên.

Lỗi httpx được bọc thành `FetchError` để không rò kiểu của thư viện ra ngoài.

### 4.3 Chuẩn hoá

| Bước | Vì sao |
|---|---|
| `convert("RGB")` | Ảnh CMYK và ảnh có alpha đều hỏng hoặc lỗi khi lưu JPEG |
| `thumbnail((1280, 1280))` LANCZOS | Chỉ thu nhỏ, **không phóng to**; giữ nguyên tỉ lệ |
| JPEG q82, `optimize=True` | Ảnh chụp; PNG là lãng phí |
| Lưu từ object mới | Nhờ vậy EXIF bị bỏ — EXIF hay chứa toạ độ GPS và thông tin thiết bị của người chụp |

### 4.4 Chịu lỗi

Một ảnh hỏng **không** làm hỏng lượt chạy: ghi lỗi ra stderr, đếm vào `failed`, bỏ qua, tiếp tục. Manifest vẫn được ghi với phần thành công, và tiến trình trả về mã khác 0.

Đây không phải giả định: 429 của Wikimedia làm hỏng ảnh thứ ba trong ba ảnh. Hai ảnh kia được giữ, lần chạy sau nhặt nốt ảnh còn thiếu.

---

## 5. Nạp vào database

```
uv run python -m app.content.seed          # audio_asset + image_asset, từ hai manifest
uv run python -m app.content.seed_scores   # bảng quy đổi điểm (không liên quan media)
```

`seed` chỉ dùng **stdlib + SQLAlchemy**, nên chạy được trong image production vốn không có extra `content`. Upsert theo `source_hash`: chưa có thì insert, có mà khác thì update, giống hệt thì bỏ qua.

Trước khi ghi, mỗi bản ghi phải qua `validate_record` / `validate_image_record`. Bộ kiểm này chạy **không cần mạng và không cần database**, nên CI dùng luôn nó để bắt manifest bị sửa tay: hash không đúng 64 ký tự hex, `storage_key` không khớp hash, accent lạ, `license` rỗng.

---

## 6. Phục vụ

```
development:  /media  ──►  StaticFiles(apps/api/media)
production:   AUDIO_PUBLIC_BASE_URL ──► CDN / object store, API không tham gia
```

Mount `/media` có guard `settings.environment == "development"`, và tự `mkdir` thư mục vì `StaticFiles` từ chối khởi động nếu thư mục không tồn tại — mà thư mục đó bị gitignore, nên một bản clone mới sẽ không boot nổi API.

Đã kiểm chứng: `200` + `content-type: audio/mpeg` (và `image/jpeg`), `206 Partial Content` với header `Range` ⇒ tua được.

**Không bao giờ proxy media qua FastAPI.** Mất range request là mất khả năng tua, và đốt băng thông của API.

---

## 7. Ranh giới cô lập

```
app/main.py  ──X──►  app/content/*        ← CẤM
app/content/*  ────►  app/core/media.py   ← được, media.py thuần stdlib
app/content/seed.py ►  app/models/*       ← được, chỉ cần sqlalchemy
```

Image production build `uv sync --frozen --no-dev` **không có** extra `content`, nên không có `edge-tts`, `mutagen`, `pillow`. Nếu pipeline rò rỉ vào chuỗi import runtime thì container không khởi động được — và hỏng lúc chạy chứ không phải lúc build.

Hai lớp bảo vệ: `tests/test_content_isolation.py` chạy `import app.main` trong subprocess rồi soi `sys.modules`, dưới một giây; job `docker` trong CI boot image thật, chậm hơn nhưng là bằng chứng cuối cùng.

Đã kiểm chứng bên trong image production: `edge_tts`, `mutagen`, `PIL` đều vắng mặt; `app.main` import được; `app.content.seed` import được; `app.content.generate` hỏng đúng ở chỗ gọi `mutagen`.

---

## 8. Hiện trạng thật trong repo

| | |
|---|---|
| Clip audio | **67** — 3 từ × {headword, example} × 4 accent, cộng các câu dictation |
| Ảnh | **3** — Wikimedia Commons, CC BY 4.0 / CC BY-SA 3.0 / CC BY 2.0 |
| Manifest | `content/manifest/audio_assets.jsonl` (67 dòng), `image_assets.jsonl` (3 dòng) — commit vào repo |
| File media | `apps/api/media/` — 70 file, **gitignore**, không commit |
| Test | 296 thu thập, 294 chạy; 2 test `external` gọi edge-tts thật và **mặc định bị deselect** |

*(số liệu kiểm lại 2026-08-09)*

Con số clip tăng từ 38 lên 67 trong lúc dựng và kiểm cây dictation: mỗi câu mới cần một clip, và một đợt phải sinh lại vì **giọng đọc chuyển sang chọn theo story** thay vì theo từng câu (§3.2).

Toàn bộ số này là **mẫu chứng minh đường ống chạy được**, không phải nội dung để dạy ai.

---

## 9. Điểm mạnh

Xếp theo mức độ đã được chứng minh bằng sự cố thật, không phải theo lý thuyết.

### 9.1 — Hash trên input làm cho việc đổi nhà cung cấp gần như miễn phí
**Đã chứng minh.** Microsoft đổi tên một giọng edge-tts giữa chừng; sửa một dòng map là xong. Nếu ID nhà cung cấp lọt vào hash thì toàn bộ thư viện phải sinh lại.

### 9.2 — Sinh offline khoanh vùng được sự cố của bên thứ ba
edge-tts là client reverse-engineer, có thể 403 hàng loạt bất cứ lúc nào. Vì file đã sinh nằm trên đĩa, sự cố **chặn nội dung mới** chứ không làm hỏng nội dung đã có. Đây là cơ chế giảm rủi ro chính, mạnh hơn nhiều so với việc trừu tượng hoá `TTSEngine`.

### 9.3 — Chạy lại luôn an toàn, và chỉ làm phần còn thiếu
**Đã chứng minh** ở cả hai đường ống: audio chạy lần hai skip 16/16 không gọi TTS; ảnh sau lỗi 429 chạy lại chỉ tải đúng ảnh còn thiếu.

### 9.4 — Runtime không chạm object store
Không round-trip trước mỗi lần phát, CDN cache tối đa, range request hoạt động. Đường nâng cấp lên R2 là copy file + đổi biến env, không sửa code gọi.

### 9.5 — Manifest là artifact review được và CI kiểm được offline
Sửa tay một dòng manifest sẽ bị bắt bởi test, không cần mạng, không cần database.

### 9.6 — Cô lập import được ép bằng máy, không bằng lời dặn
Hai lớp bảo vệ, một nhanh một chắc. Đã kiểm chứng test đỏ đúng khi cố tình vi phạm.

### 9.7 — Chi tiết nhỏ nhưng đúng
Ghi file bằng write-then-rename (lượt chạy bị ngắt không để lại mp3 cụt); chặn key thoát khỏi thư mục gốc (`../../etc/passwd`); manifest sắp xếp theo hash nên sinh lại ở máy khác cho diff rỗng; xoá EXIF nên không phát tán GPS của người chụp.

---

## 10. Điểm yếu

Xếp theo mức độ nghiêm trọng.

**§10.1 đã được sửa** (xem bên dưới). Hai lỗi thật còn lại là **§10.2** và **§10.3** — phần còn lại là giới hạn đã biết.

### 10.1 — ✅ ĐÃ SỬA · Audio lệch khỏi text

**Vấn đề.** `vocabulary_audio` chỉ có `(entry_id, kind, accent) → audio_asset_id`. **Không có gì nối audio với phiên bản text đã sinh ra nó.**

Sửa `vocabulary_entry.headword` từ `recieve` thành `receive` ⇒ audio vẫn đọc `recieve`, hàng nối vẫn trỏ tới nó, không có cảnh báo nào. Học viên nghe một đằng nhìn một nẻo.

Với `dictation_item.transcript` thì nặng hơn: transcript **là đáp án chấm bài**. Sửa transcript mà audio giữ nguyên ⇒ học viên nghe câu cũ, bị chấm theo câu mới.

**Đã sửa, và không cần thêm cột nào** — nhờ mục 2.2. `app/services/media_state.py` tính lại hash từ text hiện tại rồi so với `audio_asset.source_hash`:

```python
sha256(text_hiện_tại │ voice │ engine │ version) != audio_asset.source_hash  ⇒ stale
```

Ba chỗ dùng nó:

| Chỗ | Làm gì |
|---|---|
| `POST /admin/{loại}/{id}/publish` | **Từ chối publish** nếu bất kỳ clip nào `missing` hoặc `stale` |
| `GET /admin/{loại}` | Trả trạng thái từng clip; `/admin` render thành badge `missing`/`stale`/`current` |
| `app/content/backfill_audio.py` | Hàng đợi của worker **là** câu truy vấn này — nên chạy lại chỉ tìm thấy ít việc hơn, không có bảng hàng đợi, không có trạng thái retry |

Hai chi tiết dễ làm sai nếu ai đó viết lại chỗ này:

- `engine` và `engine_version` lấy từ **chính hàng asset**, không phải từ settings. Câu hỏi ở đây là *"clip này có được tạo từ text này không"* — chuyện đúng/sai. *"Clip này có được tạo bởi engine hiện tại không"* là câu hỏi khác, chuyện sinh lại, và nó **không được** chặn publish: tăng `tts_engine_version` không làm audio cũ đọc sai từ.
- Dictation so với `item.transcript`, **không bao giờ** so với `audio_asset.source_text` — `source_text` chỉ ghi lại thứ đã đưa cho TTS, còn transcript mới là đáp án (`PHASE2-AUDIO` §A4.4).

**Còn hở:** cổng chỉ chặn ở **thời điểm publish**. Sửa text của một mục **đã published** thì nó vẫn đang published với audio đã lệch — không có gì tự hạ nó xuống `draft`. Hiện phải chạy `backfill_audio` để phát hiện.

### 10.2 — ✅ ĐÃ GỠ (2026-08-10) — clip nhiều giọng cho Part 2 và Part 3

> Mục này từng là blocker lớn nhất của Sprint 5 và được nhắc lại ở `CLAUDE.md`, `ADR-006` §5 và `ROADMAP` mục 4d. Giữ nguyên phần mô tả cũ bên dưới vì lập luận vẫn đúng — chỉ kết luận "bất khả thi" là sai.

**Vấn đề (vẫn đúng như đã mô tả):** `SpecItem` là `(text, voice)` — một text, một giọng, một clip. `voices: [...]` chỉ nhân bản cùng một text ra nhiều accent. Không diễn đạt được "lượt 1 giọng nam, lượt 2 giọng nữ, ghép thành một file".

| Part | Cần | Trước | Nay |
|---|---|---|---|
| 1 | 1 giọng đọc 4 câu | ✅ | ✅ |
| 4 | 1 giọng độc thoại | ✅ | ✅ |
| 2 | câu hỏi 1 giọng + 3 đáp giọng khác | ❌ | ✅ |
| 3 | hội thoại 2–3 giọng | ❌ | ✅ |

**Vì sao nó không thật sự bất khả thi.** Ghi chú cũ nói đúng thứ còn thiếu — *"cần bước ghép audio, mà repo cố ý không có ffmpeg"* — nhưng rút ra kết luận rộng hơn tiền đề. "Repo không có ffmpeg" đúng ở chỗ nó cần đúng: **ảnh production không có và không cần**. Đường ống nội dung thì chạy offline, sau extra `content`, nơi edge-tts đã là một điều kiện tiên quyết của máy soạn nội dung. ffmpeg là cùng loại điều kiện đó.

**Cách làm.**

- Spec có thêm dạng thứ hai: `{"turns": [{text, voice}, ...], "gap_ms": N}`. Hai dạng cũ không đổi.
- `conversation_source_hash` băm **cả danh sách lượt** cùng `gap_ms` — thứ tự có tính, số lượt có tính, và tiền tố `"conversation"` giữ cho hội thoại một lượt không trùng hash với một clip đơn.
- `app/content/audio_join.py` nối ở mức khung (`-c copy`), với khoảng lặng **sinh theo đúng tham số đo được của lượt đầu**.

**Ba điều học được khi chạy thật, không đoán ra được:**

1. **Phép kiểm độ dài không bắt được lệch tham số.** Bản đầu chỉ đối chiếu độ dài file ra với tổng mong đợi. Thử nối 24 kHz mono với 44.1 kHz stereo: ffmpeg **không báo lỗi**, ffprobe vẫn đọc ra độ dài gần đúng, phép kiểm lọt — nhưng phần sau phát sai tốc độ. Tham số phải được kiểm **thẳng**, không suy ra từ triệu chứng. Khi lệch thì mã lại thay vì từ chối, vì ca lệch có thật: trộn bản thu người thật vào giữa các lượt TTS.
2. **`gap_ms` là phần CỘNG THÊM.** edge-tts tự chèn ~1,1 s đệm ở mỗi ranh giới lượt. Đo bằng `silencedetect`: `gap_ms=600` cho ra khoảng lặng thật ~1,74 s. Nên `gap_ms=0` không phải là không có khoảng lặng — nó là ~1,1 s, vốn đã là nhịp hội thoại tự nhiên.
3. **Trộn accent trong một clip là hợp lệ và cần thiết** — Part 2 cố ý hỏi ở accent này và đáp ở accent khác. Nhưng `audio_asset.accent` giữ đúng một giá trị, nên khi các lượt khác accent thì spec **phải khai** `"accent"`. Chọn hộ sẽ ghi một giá trị trông như dữ liệu thật mà không ai từng cân nhắc.

**Đã sinh thật:** `content/sources/demo_part2_responses.jsonl` (3 câu Part 2) và `demo_part3_conversations.jsonl` (2 hội thoại Part 3). Kiểm bằng `silencedetect`: clip Part 2 dài 16,8 s có đúng 3 khoảng lặng nội bộ; hội thoại Part 3 dài 39,6 s có đúng 3 ranh giới người nói.

**Còn lại:** `audio_asset.voice` của clip nhiều giọng là `"multi"`, nên `media_state.clip_state` không xác minh được nó — nhưng cũng chưa cần: `media_state` chỉ soi `dictation_item` và `vocabulary_audio`, còn clip hội thoại gắn vào `question`/`question_set`. Khi Part 3 có bản ghi lời lưu trong database thì sẽ cần một phép kiểm tương ứng.

### 10.3 — 🔴 Ảnh **không** tái tạo được, dù audio thì có

Đây là bất đối xứng bị che khuất bởi việc hai đường ống trông giống nhau.

- **Audio**: input là text, nằm trong spec đã commit ⇒ sinh lại được vĩnh viễn.
- **Ảnh**: input là **URL của người khác**. URL chết ⇒ không bao giờ tải lại được.

Mà `apps/api/media/` bị gitignore. Nên với ảnh, **thư mục media là bản sao duy nhất** — mất là mất hẳn, dù manifest vẫn đầy đủ. Câu "thư mục media chỉ là cache tái tạo được" chỉ đúng cho audio.

Bản gốc trước chuẩn hoá cũng không được giữ, nên sau này muốn kích thước lớn hơn thì cũng phải tải lại từ URL đó.

### 10.4 — 🟡 `seed` không bao giờ xoá

Upsert theo `source_hash`: insert, update, hoặc bỏ qua. Xoá một dòng khỏi manifest thì **hàng trong DB ở lại vĩnh viễn**, trỏ tới một file mà `generate` sẽ không bao giờ tạo lại. Trôi lệch âm thầm, không có gì phát hiện.

### 10.5 — 🟡 Không có đường upload

Không có cách nào đưa ảnh **bạn tự chụp**, ảnh từ tài khoản stock trả phí, hay audio thu bởi người thật vào hệ thống. `AUDIO_SOURCES` và `IMAGE_SOURCES` đều đã có giá trị `uploaded` — schema hỗ trợ, **đường đi thì chưa xây**.

### 10.6 — 🟡 Chất lượng TTS

Giọng tổng hợp không bằng giọng người thật, và luyện nghe TOEIC thì đây không phải chi tiết nhỏ. `PHASE2-AUDIO` §A2.2 đã thừa nhận và chấp nhận ở MVP.

Kèm theo: **không chuẩn hoá độ lớn (loudness)**. Các giọng edge-tts có thể chênh mức âm lượng, và trong một bài nghe thì chênh lệch đó gây khó chịu thật.

### 10.7 — 🟡 `question_set` không có chỗ chứa ảnh

Part 7 đôi khi có biểu đồ, biểu mẫu, lịch trình. `question_set` có `audio_asset_id` và ba cột `passage`, **không có `image_asset_id`**. Bảng biểu đơn giản nhét vào `passage` dạng text được; biểu đồ thật thì không.

### 10.8 — 🟡 Không có gì kiểm chứng media còn phục vụ được

`/ready` kiểm Postgres và ping Redis, **không kiểm media**. Nếu `AUDIO_PUBLIC_BASE_URL` cấu hình sai ở production thì mọi media 404 trong khi container vẫn báo healthy. Cũng không có công cụ nào dò hàng mồ côi (hàng trong DB mất file, hoặc file không có hàng).

### 10.9 — 🟡 `tts_engine_version` là núm vặn thủ công

Quên tăng sau khi đổi thứ gì đó có ý nghĩa ⇒ audio cũ được giữ im lặng. Tăng nhầm ⇒ sinh lại toàn bộ thư viện. Không có gì nhắc.

### 10.10 — ⚪ Giấy phép chỉ được **khai báo**, không được **xác minh**

Cột NOT NULL ép người nhập điền, nhưng không có gì kiểm tra chuỗi đó có đúng không. Không có API nào nói được một URL đang ở giấy phép gì một cách đáng tin.

Và `attribution` hiện **chưa được hiển thị ở đâu cả** vì chưa có endpoint nào — lưu ghi công mà không bao giờ render ra thì vẫn là vi phạm CC-BY. Ràng buộc này đã ghi ở `ADR-004` §4.2 nhưng chưa có gì thực thi.

### 10.11 — ⚪ Chưa có CDN

`LocalDirStore` không scale và không có CDN. R2 bị chặn bởi điều kiện tiên quyết: phải có domain trên DNS Cloudflare (`PHASE2-AUDIO` §A5). Chấp nhận được ở MVP vì chưa có tải thật.

---

## 11. Những thứ trông như thiếu sót nhưng là cố ý

Đừng "sửa" mấy chỗ này mà không đọc ADR tương ứng trước:

| Trông như thiếu | Thật ra |
|---|---|
| `LocalDirStore.put()` bỏ qua `content_type` | Thư mục không có chỗ ghi nó. Tham số vẫn nằm trong chữ ký vì `S3ObjectStore` **bắt buộc** phải gửi, nếu không R2 lưu thành `binary/octet-stream` và trình duyệt không tua được |
| Không có bảng CORS cho bucket | Thẻ `<audio>`/`<img>` thuần không cần CORS. Chỉ cần khi đọc bằng `fetch()`/Web Audio API, ví dụ vẽ waveform |
| Không có service MinIO trong Compose | Là service thứ năm mà runtime không dùng, CI không cần, chỉ một script offline gọi tới |
| Test `external` bị deselect | Chúng gọi edge-tts thật. CI tuyệt đối không được gọi. Còn tự khoá thêm bằng biến `TOEIC_ALLOW_EXTERNAL_TTS` vì `-m` trên dòng lệnh sẽ ghi đè `addopts` |
| `/media` chỉ có ở development | Production phục vụ từ CDN. Proxy qua FastAPI sẽ mất range request |
| `alt_text` nullable | Với Part 1 nó khó: mô tả ảnh quá rõ là **lộ đáp án**. Chưa quyết được nên chưa ép |

---

## 12. Bản đồ code

| Đường dẫn | Vai trò |
|---|---|
| `app/core/media.py` | Hash, đặt tên, ghép URL, hằng số accent/source. **Thuần stdlib** |
| `app/models/audio.py` · `image.py` | Bảng `audio_asset`, `image_asset` |
| `app/content/settings.py` | Cấu hình pipeline, **tách khỏi `app.core.config`** — credential ghi bucket không được nằm trong env của tiến trình phục vụ HTTP |
| `app/content/tts.py` | `TTSEngine` Protocol, `LOGICAL_VOICES`, `EdgeTTSEngine` |
| `app/content/storage.py` | `ObjectStore` Protocol, `LocalDirStore` |
| `app/content/manifest.py` | Đọc/ghi/validate manifest. Thuần stdlib |
| `app/content/generate.py` | CLI sinh audio |
| `app/content/images.py` | CLI tải + chuẩn hoá ảnh |
| `app/content/seed.py` | Manifest → DB. Chỉ stdlib + sqlalchemy |
| `app/content/backfill_audio.py` | Worker ngoài luồng: sinh audio cho nội dung DB đang thiếu hoặc đã lệch. Hàng đợi là một **câu truy vấn**, không phải một bảng |
| `app/services/media_state.py` | Clip còn khớp text không? **Được API import**, nên chỉ phụ thuộc `app.core` + `app.models` |
| `tests/test_media.py` | Hash và đặt tên |
| `tests/test_content_pipeline.py` | Logic skip/sinh của audio, engine giả |
| `tests/test_images.py` | Chuẩn hoá, giấy phép, chịu lỗi |
| `tests/test_content_manifest.py` | Validate manifest + tính idempotent của seed |
| `tests/test_content_isolation.py` | Ranh giới `app.main` ↮ `app.content` |
| `tests/test_tts_external.py` | Đối chiếu `LOGICAL_VOICES` với catalogue thật (marker `external`) |
| `tests/test_services.py` | Trong đó có `media_state`: `missing` / `stale` / `current` |
| `tests/test_admin_api.py` | Cổng publish từ chối audio thiếu/lệch |
