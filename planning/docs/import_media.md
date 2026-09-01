# Nhập audio và ảnh có sẵn vào một đề

Sổ tay thao tác cho `app/content/import_media.py`. Quyết định và lý do nằm ở
[`ADR-007-TEST-AUTHORING.md`](../adr/ADR-007-TEST-AUTHORING.md) §2.4 và §2.7; file này
chỉ trả lời "đặt tên thế nào và gõ lệnh gì".

---

> Có hai đường đưa ảnh vào đề, và chúng bổ sung chứ không thay nhau:
> **tải lên tại chỗ** trong màn soạn đề (một vài bức, thấy ngay ô nào thiếu), và
> **lệnh này** (cả lô, sau khi đã dán chữ). Thư viện ảnh dùng chung đã bị xoá.

## 0. Điều kiện tiên quyết

**Dán nội dung trước, media sau.** Lệnh này chỉ *gắn* file vào câu và cụm đã tồn
tại — nó không tạo câu hỏi nào. Chưa dán thì không có ô nào để gắn, và lệnh sẽ
nói ra điều đó rồi thoát.

```bash
cd apps/api
uv sync --extra dev --extra content     # cần mutagen (đọc độ dài mp3) và Pillow
```

Lệnh đọc `DATABASE_URL` và `*_STORAGE_DRIVER` từ `.env` ở gốc repo, chạy từ máy
host. File được đẩy **thẳng** lên nhà cung cấp đang cấu hình (ảnh → Cloudinary,
audio → S3/Supabase); không cần chạy `push_media` sau đó.

---

## 1. Cấu trúc thư mục

Không bắt buộc một cấu trúc cố định — lệnh nhận **một thư mục mỗi lần chạy** và
quét cả thư mục con. Cấu trúc dưới đây là thứ hợp với cách chạy từng part:

```
toeic-2024-test1/
├── audios/
│   ├── part1/   6 file    mỗi câu một clip
│   ├── part2/  25 file    mỗi câu một clip
│   ├── part3/  13 file    mỗi HỘI THOẠI một clip
│   └── part4/  10 file    mỗi BÀI NÓI một clip
└── images/
    ├── part1/   6 file    mỗi câu một ảnh
    ├── part3/   vài file  hình của các cụm cuối
    └── part4/   vài file  hình của các cụm cuối
```

### Số lượng phải khớp

| Part | Số câu | File audio | Ảnh |
|---|---|---|---|
| 1 | 1–6 | **6** — mỗi câu một clip | **6** — mỗi câu một bức |
| 2 | 7–31 | **25** — mỗi câu một clip | không có |
| 3 | 32–70 | **13** — 13 hội thoại × 3 câu | chỉ vài cụm cuối |
| 4 | 71–100 | **10** — 10 bài nói × 3 câu | chỉ vài cụm cuối |

**Part 3 và 4 không phải một file mỗi câu.** Một đoạn hội thoại phục vụ ba câu và
đề phát nó một lần, nên hệ thống chỉ có **một** ô cho cả cụm. 39 file cho Part 3
nghĩa là bạn đang có ba bản sao của mỗi bản thu.

**Part 2 không có ảnh nào.** Đề in con số 0 chữ ở đó — không đề bài, không đáp
án in ra, không hình.

---

## 2. Quy tắc đặt tên

Lệnh khớp file với ô bằng **con số trong tên file**. Số đó nghĩa là gì thì do
`--match` quyết định, và chọn sai chế độ là khớp sai chứ không phải khớp trượt.

### `--match index` — số là **thứ tự trong part** (cần `--part`)

```
part2/1_abc.mp3   → câu thứ 1 của Part 2  = câu 7
part2/10_xyz.mp3  → câu thứ 10 của Part 2 = câu 16
part3/11_def.webp → hình của cụm thứ 11 của Part 3
```

Dùng khi nguồn đánh số lại từ 1 ở mỗi part — cách phổ biến nhất. Tra theo **vị
trí**, nên chỗ trống không đẩy các ô còn lại (quan trọng với hình Part 3/4, nơi
chỉ vài cụm có hình).

### `--match number` — số là **số câu chính thức** (1–100)

```
32.mp3      → cụm mở đầu ở câu 32
32-34.mp3   → cũng cụm đó (lấy số ĐẦU)
part3_62.mp3 → cụm mở đầu ở câu 62 (nhãn "part3" được gỡ trước khi đọc số)
```

Với Part 3/4 thì số phải là **số câu mở đầu cụm** — 32, 35, 38… chứ không phải
33 hay 34.

Đây là chế độ mặc định.

### `--match order` — không có số, xếp theo tên

Chỉ dùng khi tên file không chứa số nào. Ghép theo thứ tự, nên **bắt buộc** phải
soát bảng `--dry-run` trước.

### Hai luật đọc số, cả hai đến từ lỗi thật

- **Nhãn part được gỡ trước.** `part3_32.mp3` đọc thẳng cho ra `3`, mà `3` là
  một câu Part 1 có thật (Part 1 chạy 1–6) — nên nó khớp **thành công vào sai
  câu**. Các dạng `part3`, `Part_3`, `p3`, `phan3` đều được gỡ.
- **Lấy số đầu, không lấy số cuối.** `32-34.mp3` là cụm mở đầu ở 32; số cuối cho
  34, và 34 không mở đầu cụm nào.

---

## 3. Các bước

### Bước 1 — dán nội dung bốn part

`/admin/tests/<slug>` → chọn Part → **Chép mẫu** để lấy đúng định dạng → dán →
**Phân tích** → **Ghi**. Part 1/2 gõ lời thoại; Part 3/4 cần khối `[SCRIPT]`
cho cả cụm.

### Bước 2 — xem thử bảng khớp audio

Luôn chạy `--dry-run` trước. Nó không ghi gì.

```bash
cd apps/api
D=~/Downloads/toeic-2024-test1

for p in 1 2 3 4; do
  uv run python -m app.content.import_media audio \
    --test <slug> --dir $D/audios/part$p --part $p \
    --match index --accent en-US --dry-run
done
```

Bảng in ra có dạng:

```
13 khớp · 0 bỏ qua (đã có) · 0 file thừa · 0 ô còn trống

  1_s8aztbbc.mp3   -> Part 3 cụm từ câu 32 · Đặt lại phòng họp
  2_pawtxo5l.mp3   -> Part 3 cụm từ câu 35 · ...
```

Soát cột phải: số câu có tăng đều đúng bước không (Part 1/2 bước 1, Part 3/4
bước 3), và dòng cuối có đúng câu cuối của part không.

### Bước 3 — chạy thật

Bỏ `--dry-run` khi bảng đúng:

```bash
for p in 1 2 3 4; do
  uv run python -m app.content.import_media audio \
    --test <slug> --dir $D/audios/part$p --part $p \
    --match index --accent en-US
done
```

### Bước 4 — ảnh Part 1

```bash
uv run python -m app.content.import_media image \
  --test <slug> --dir $D/images/part1 --part 1 --match index \
  --source-url "https://..." \
  --license "CC0" \
  --attribution "Tên tác giả / nguồn" \
  --dry-run
```

### Bước 5 — hình Part 3/4

Chỉ vài cụm cuối mỗi part có hình, nên **ô trống là bình thường** ở đây và không
làm lệnh dừng.

```bash
uv run python -m app.content.import_media image \
  --test <slug> --dir $D/images/part3 --part 3 --match index \
  --alt-text "Lịch trình phòng họp" \
  --source-url "https://..." --license "..." --attribution "..." \
  --dry-run
```

`--alt-text` áp cho **cả lô**. Mỗi hình cần mô tả riêng thì chạy từng file với
`--dir` trỏ vào một thư mục chứa đúng một ảnh.

### Bước 6 — xuất bản

Về `/admin/tests/<slug>`, xuất bản từng câu rồi xuất bản đề. Cổng chặn sẽ từ
chối câu nào còn thiếu audio hoặc thiếu ảnh Part 1, kèm lý do.

---

## 4. Ba thứ bắt buộc khai, không có mặc định

| Cờ | Bắt buộc khi | Vì sao không đoán hộ |
|---|---|---|
| `--accent` | mọi lần nhập audio | Người học lọc nội dung theo accent. Không ai ngoài bạn biết bản thu giọng gì, và đoán sai là ghi một giá trị sai vào cột hiển thị. |
| `--source-url` `--license` `--attribution` | mọi lần nhập ảnh | Ba cột NOT NULL. Phần lớn ảnh mở là CC-BY — dùng được *với điều kiện* ghi công, và ghi công chỉ có tác dụng nếu nó được lưu. |
| `--alt-text` | ảnh `--part 3` hoặc `4` | Hình là dữ liệu phải đọc mới trả lời được. |

### Chữ thay ảnh: Part 1 và Part 3/4 ngược nhau

Hai chỗ trông giống nhau, luật ngược nhau:

- **Part 1 để trống.** Bức ảnh *chính là* câu hỏi, nên mô tả kỹ là đưa luôn đáp
  án. Lệnh không nhận `--alt-text` cho Part 1 như một yêu cầu, và không nên điền.
- **Part 3/4 bắt buộc.** Hình là dữ liệu, và người học vẫn phải **nghe** mới trả
  lời được — nên mô tả nó không lộ gì. Bỏ trống là biến câu đó thành không làm
  được với máy đọc màn hình.

---

## 5. Đọc lỗi

| Thông báo | Nghĩa | Cách sửa |
|---|---|---|
| `KHÔNG khớp ô nào` | File có số không ứng với ô nào | Sai `--match`, hoặc sai `--part`, hoặc số vượt quá số ô của part |
| `(trống) <- Part N ... chưa có audio` | Có ô không nhận được file nào | Thiếu file, hoặc số đếm lệch (xem bảng §1) |
| `Dừng: còn file thừa hoặc ô trống` | Có lệch, **chưa ghi gì** | Soát bảng rồi chạy lại |
| `--match index cần --part` | `index` không có nghĩa nếu không biết part | Thêm `--part N` |
| `chưa có câu Part 1-4 nào` | Đề chưa dán nội dung | Làm bước 1 |

**Lệnh dừng thay vì làm phần khớp được.** Nhập một nửa để lại một đề thiếu đúng
vài bản thu, và chỗ thiếu chỉ lộ ra khi có người ngồi làm tới câu đó. Mã thoát:
`0` xong, `1` có lệch nên dừng, `2` sai tham số hoặc thiếu điều kiện.

---

## 6. Chạy lại

Chạy lại an toàn. Ô đã có media bị **bỏ qua**, in ra dưới nhãn `[đã có, bỏ qua]`,
và chỉ số của các ô còn lại **không** dịch đi — nên lần chạy thứ hai khớp y hệt
lần đầu.

`--overwrite` gắn đè lên ô đã có. Dùng khi thay bản thu, và **chỉ khi** đã xem
`--dry-run --overwrite` trước.

---

## 7. Một điều về trình sinh audio

File nhập bằng lệnh này được ghi `source="uploaded"`, nên worker TTS
(`app/content/tts_worker.py`) **không bao giờ** ghi đè lên chúng. Bấm "Sinh audio
còn thiếu" trong màn quản trị chỉ đụng vào cụm chưa có bản thu — bản thu người
đọc nằm nguyên chỗ của nó.
