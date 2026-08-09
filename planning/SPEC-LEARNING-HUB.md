# Learning Hub — đặc tả tạm thời

**Trạng thái:** 🟡 **TẠM THỜI** · cập nhật 2026-08-09
**Mục đích:** ghi lại bộ mặc định đã chọn để xây, **không** phải để chốt trên giấy

> **Đã dựng xong theo đúng đặc tả này** — 8 endpoint học viên, 4 trang (`/learn`, `/learn/vocabulary`, `/learn/review`, `/learn/dictation`), SM-2 ở `app/services/srs.py`, chấm dictation ở `app/services/dictation.py`. Cái chưa có là **nội dung để dùng thử**: 3 từ và 4 câu. Nên §5 dưới đây vẫn là dự đoán chứ chưa phải quan sát — chưa ai học đủ lâu để biết 20 từ mới/ngày là nhiều hay ít.

> Tài liệu này tồn tại để **bị sửa**. Nó là bộ gọn nhất chạy được đầu-cuối, dựng lên để dùng thử rồi chỉnh — không phải kết quả của một vòng thiết kế. Mỗi lựa chọn dưới đây đều có ghi phương án thay thế đã cân nhắc, để lúc sửa không phải nghĩ lại từ đầu.
>
> Khi đã dùng thử và chốt, tài liệu này hoặc được nâng lên thành đặc tả thật, hoặc bị xoá và thay bằng acceptance criteria trong `ROADMAP.md` (`REVIEW-OPUS.md` §7c).

---

## 1. Phạm vi

| Có | Không có (ở vòng này) |
|---|---|
| Từ vựng theo chủ đề, 4 accent | Trắc nghiệm, gõ lại từ |
| Ôn tập SM-2 bằng flashcard | Thống kê, biểu đồ tiến độ |
| Dictation từng câu, chấm theo từ | Dictation nhiều câu, chỉnh tốc độ phát |
| Admin dán hàng loạt + sửa từng mục | Nhập từ Excel, sửa hàng loạt |
| Chặn publish khi audio thiếu/lệch | Lên lịch xuất bản |

---

## 2. Từ vựng — học viên

### 2.1 Duyệt
Chủ đề → danh sách từ → chi tiết từ. Chỉ hiện `status='published'`.

Chi tiết một từ: `headword`, `phonetic`, nghĩa Anh, nghĩa Việt, câu ví dụ (+ dịch), và **4 nút accent** US/UK/AU/CA. Chọn accent nào thì phát clip của accent đó — thẻ `<audio>` thuần, không waveform.

### 2.2 Ôn tập — flashcard tự chấm

```
mặt trước:  headword + phonetic + nút nghe
   ↓ lật
mặt sau:    nghĩa Việt + nghĩa Anh + ví dụ
   ↓
[Quên]  [Khó]  [Được]  [Dễ]
  0       3      4       5     ← grade đưa vào SM-2
```

**Vì sao tự chấm chứ không trắc nghiệm:** SM-2 cần điểm chất lượng 0–5 để giãn lịch. Trắc nghiệm chỉ cho đúng/sai, không phân biệt được "nhớ chật vật" với "nhớ ngay" — mà đó chính là thông tin thuật toán dùng. Trắc nghiệm và gõ lại từ có thể thêm sau; chúng là thêm chế độ, không phải thay thuật toán.

Bốn nút, không phải sáu: SM-2 gốc dùng thang 0–5, nhưng 0/1/2 đều là "quên" nên gộp lại. Đây là quy ước Anki đã dùng nhiều năm.

### 2.3 Phiên ôn tập

| Tham số | Mặc định | Vì sao |
|---|---|---|
| Từ đến hạn mỗi phiên | tối đa 100 | Đủ cho một buổi, không gây choáng |
| Từ mới mỗi ngày | 20 | Không giới hạn từ mới là cách chắc chắn nhất để tạo ra một núi nợ ôn tập sau hai tuần |
| Thứ tự | đến hạn lâu nhất trước, rồi đến từ mới | Ôn cái sắp quên trước khi học cái mới |

Truy vấn dùng index `ix_vocabulary_review_state_due` `(user_id, due_at)` đã có sẵn.

### 2.4 SM-2

```
grade < 3  →  repetitions = 0, interval = 1 ngày, lapses += 1
grade ≥ 3  →  repetitions 0 → 1 ngày · 1 → 6 ngày · n → round(interval × EF)

EF' = EF + (0.1 − (5−grade) × (0.08 + (5−grade) × 0.02))      sàn 1.30
```

Mỗi lần ôn ghi **hai** chỗ: cập nhật `vocabulary_review_state` (hiện tại) và chèn `vocabulary_review_log` (lịch sử). Log lưu `interval_days` và `ease_factor` **tại thời điểm ôn**, để sau này chỉnh tham số còn đánh giá lại được.

---

## 3. Dictation — học viên

### 3.1 Làm bài
Một bài = **một câu**. Nghe (không giới hạn số lần), gõ lại, nộp. Không chỉnh tốc độ ở vòng này.

Gom theo chủ đề, dùng chung bảng `topic` với từ vựng.

### 3.2 Chấm

```
chuẩn hoá:  về chữ thường → bỏ dấu câu → gộp khoảng trắng
so khớp:    từng từ, thuật toán LCS → diff mất/thừa/khớp
accuracy:   số từ khớp / số từ trong transcript × 100
```

**Bỏ dấu câu vì nghe không cho biết dấu phẩy nằm ở đâu.** Trừ điểm vì dấu câu là trừ điểm một thứ dictation không đo. Chính tả thì vẫn tính — sai chính tả là nghe sai hoặc không biết viết, cả hai đều đáng báo.

Lưu `submitted_text` **nguyên văn**, không lưu bản đã chuẩn hoá: chuẩn hoá là hành vi của bộ chấm, mà bộ chấm sẽ đổi. Chỉ giữ bản đã xử lý thì không bao giờ chấm lại được bằng luật mới.

`word_diff` lưu JSONB để UI tô lại màu mà không phải chấm lại.

### 3.3 Sau khi nộp
Hiện transcript đúng, tô màu từng từ (khớp / thiếu / thừa), và `accuracy`. Cho làm lại — mỗi lần là một hàng `dictation_attempt` mới, không ghi đè.

**Chấm theo `dictation_item.transcript`, không phải `audio_asset.source_text`.** Hai cột này thường giống nhau, và đó chính là cái bẫy.

---

## 4. Admin

### 4.1 Vai trò

| | Xem draft | Tạo/sửa | Publish |
|---|---|---|---|
| `learner` | ✗ | ✗ | ✗ |
| `editor` | ✓ | ✓ | ✗ |
| `admin` | ✓ | ✓ | ✓ |

Người viết không tự duyệt bài của mình.

`require_role` là **dependency**, không phải kiểm tra trong thân hàm — thân hàm dễ quên khi thêm route mới.

### 4.2 Nhập hàng loạt

Cùng mô hình `parse → review → commit` của `ADR-005`: **parse không bao giờ ghi database.**

Từ vựng, mỗi dòng một từ, ngăn bằng `|`:

```
invoice | noun | /ˈɪnvɔɪs/ | a bill for goods or services | hóa đơn | Please pay the invoice by Friday. | Vui lòng thanh toán hóa đơn trước thứ Sáu.
deadline | noun | /ˈdedlaɪn/ | the latest time something must be done | hạn chót | The deadline is next Monday. | Hạn chót là thứ Hai tới.
```

Dictation, mỗi dòng một câu:

```
The quarterly report is due before the end of the month.
Please submit your expense claims to the finance department.
```

Chọn `topic` và `difficulty` cho cả lô ở màn hình dán, sửa từng mục sau nếu cần.

### 4.3 Audio

Admin **không** bấm nút sinh audio. API không gọi được edge-tts — image production không có thư viện đó (`PHASE2-AUDIO` §A4.1), và sinh đồng bộ trong request sẽ kéo theo job queue, trạng thái pending/failed, retry (`§A2.5` đã bác).

Thay vào đó:

```
admin tạo từ  →  draft, chưa có audio
                       │
    (ngoài luồng)  uv run python -m app.content.backfill_audio
                       │  quét DB tìm mục thiếu hoặc lệch audio
                       │  sinh → store → nối vào vocabulary_audio
                       ↓
              badge chuyển xanh  →  publish được
```

UI chỉ **hiển thị trạng thái** và cho **yêu cầu sinh lại**; nó không điều khiển TTS.

### 4.4 Chặn publish

Không publish được khi audio **thiếu** hoặc **đã lệch**.

Lệch = hash tính lại từ text hiện tại khác `audio_asset.source_hash`:

```python
sha256(text_hiện_tại │ voice │ engine │ version) != audio_asset.source_hash
```

Đây là chỗ đóng điểm yếu `MEDIA-PIPELINE` §10.1: sửa `headword` từ `recieve` thành `receive` mà audio vẫn đọc từ sai thì hiện tại **không có gì phát hiện**. Với dictation còn nặng hơn vì transcript là đáp án chấm bài.

Không cần thêm cột nào — đây là cổ tức của việc hash tính trên input (`§A4.2`).

---

## 5. Sẽ phải chỉnh sau khi dùng thử

Ghi trước những chỗ tôi đoán là sẽ phải đổi, để lúc đó không tưởng là phát hiện mới:

- **20 từ mới/ngày** là con số mượn từ Anki, chưa có căn cứ nào cho ứng dụng này.
- **Bốn nút** có thể là quá nhiều với người mới. Hai nút (Chưa thuộc / Thuộc) học nhanh hơn nhưng nuôi SM-2 kém hơn.
- **Không giới hạn số lần nghe lại** làm dictation dễ hơn hẳn so với thi thật. Có thể cần chế độ giới hạn 2 lần.
- **Ngưỡng typo**: hiện sai một ký tự là sai. Có thể quá khắt khe với người gõ nhanh.
- **Dictation một câu** có thể quá ngắn để luyện nghe thật; đoạn nhiều câu sát TOEIC hơn nhưng cần thêm bảng.
- **Dán ngăn bằng `|`** sẽ hỏng nếu nghĩa của từ có chứa dấu `|`. Đủ dùng cho MVP, không đủ về lâu dài.
