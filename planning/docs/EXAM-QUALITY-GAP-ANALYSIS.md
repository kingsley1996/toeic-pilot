# Phân tích chất lượng đề AI vs đề tham chiếu (tp-2024-01)

Đo trên: `tp-form-17` + `tp-form-18` (AI sinh, pipeline mới) so với `tp-2024-01`
(đề tham chiếu 200 câu, đủ P1–P7) và mẫu chính thức của ETS
(`toeic-listening-reading-sample-test.pdf`, 34 trang, 2 546 từ).

> **Caveat đọc trước:** `tp-2024-01` là sách luyện thi giả lập ETS, KHÔNG phải đề
> thật (`EXTRACT-REF-2024.md` §3.8). Sách này đặc từ gấp ~2–3 lần đề thật nên chỉ
> dùng để chặn trùng lặp + bắt style hình thức, không neo band từ hay tốc độ đọc
> vào nó. Mọi chữ "sát đề thật" dưới đây nghĩa là "sát tp-2024-01 + sample ETS".

## 1. Điểm tốt — giữ nguyên

### 1.1. Khung cấu trúc khớp 100%

103 ô / 200 câu, số ô từng part, số câu từng cụm, vị trí câu hình (P3-câu-3,
P4-câu-2), mẫu câu `"Look at the graphic. …"` — AI copy y nguyên số lượng, vị trí
lẫn mẫu câu (grep 3+2 cả hai bên). P7 đúng 10 single + 2 đôi + 3 ba (29+15+10 =
54 câu). P6 đúng 4 đoạn × 4 câu. Đây là phần pipeline làm tốt nhất: đề sinh ra là
đề "đúng hình hài" ngay, không phải sửa cấu trúc bằng tay.

### 1.2. Cân bằng đáp án chuẩn

tp-form-18: A51/B49/C54/D46 (~25% mỗi chữ). Ngưỡng lệch >40% của cổng
`check_answer_spread` trùng với yêu cầu thực tế của đề trắc nghiệm.

### 1.3. Hệ cổng kiểm tra đa tầng, có ngưỡng số

Block (chặn) vs flag (cờ) tách bạch; echo nhiễu <0.2, paraphrase cân cụm, bắc cầu
2 tài liệu P7, rò rỉ chéo 2 chiều, VIC xuất hiện đúng 1 lần. Đề tham chiếu không
có quy trình nào tương đương mà máy kiểm được — đây là lợi thế cấu trúc của
pipeline, không phải điểm cần "sát thật".

### 1.4. Giải thích 200/200 có trích nguyên văn

Sách tham chiếu không in key Reading (đáp án P5/P6/P7 là dẫn xuất khi extract).
AI sinh explanation kèm trích dẫn chuỗi con thật — vượt nguồn tham chiếu ở điểm này.

### 1.5. Chống trùng + publish gate + sync idempotent

`compare` chặn trùng khít trước publish; cổng publish từ chối khi thiếu/lệch
media; export phân 3 loại (test / explanations / placement) để không xóa nhầm
lịch sử học viên. Quy trình vận hành đã chín.

## 2. Điểm cần cải thiện (xếp theo mức lệch)

### P0-1. Thoại P3/P4: AI dài hơn thật ~1/3, đều đều thiếu cụm ngắn

| | P3 (từ/cụm) | P4 (từ/cụm) |
|---|---|---|
| Thật | **98**, biên độ 70–115 | **94**, biên độ 77–114 |
| form-18 | **135** (+37%), bó hẹp 120–151 | **129** (+37%), bó hẹp 123–133 |
| form-17 | 78 (−21%) | 97 (≈ khớp) |

Hai form lệch hai hướng ngược nhau → không phải model "cố" viết dài/ngắn, mà là
**thiếu cổng trần + cổng phân bố**: volume hiện tại chỉ có ngưỡng tối thiểu
(P3/P4 ≥30), không có trần, không kiểm phương sai. Thoại AI đều chằn chặn, thiếu
cụm ngắn 70 từ của đề thật — mà cụm ngắn chính là chỗ khó (ít chứng cứ để bám).

Hành động: thêm cổng `max` + kiểm biên độ (vd ≥1 cụm <85 từ và ≥1 cụm >110 từ mỗi
part), áp cho cả `write` lẫn `check`.

### P0-2. Paraphrase đáp đúng còn yếu: AI copy, đề thật đổi chữ

Mẫu đề thật — đáp đúng hiếm khi copy nguyên mệnh đề (trừ 1–2 câu detail):

- Thoại *"if you brought any **brochures** … **put those out**"* → đáp
  **"Displaying informational materials"** (đổi cả danh + động từ).
- Thoại *"Especially the **peach pie** … **sharing the recipe**?"* → đáp
  **"A dessert recipe"** (thượng vị hóa + danh từ hóa).
- Thoại *"That will require **management approval**"* → đáp
  **"A change will not be immediate"** (không trùng từ nào ngoài ý).

Đối chứng AI (form-18 P3-01 Q3): thoại *"send me the **files of the replacement
candidates before Friday**"* → đáp **"Send candidate files before Friday"** — gần
như逐字.

Cổng echo hiện tại chỉ siết **nhiễu** (<0.2), không siết **đáp đúng**. Hành động:
thêm cổng "đáp đúng phủ từ thoại tối đa X%", nới cho câu detail (đề thật cũng giữ
từ ở detail: *"move their **vehicles**"* → **"Move their vehicles"**), siết cho
câu inference/implication/topic.

### P0-3. Nhồi câu hàm ý gấp ~2.5 lần đề thật, sai phân bố part

Đề thật: **3 câu hàm ý, cả 3 ở P4, P3 = 0**. Form-18: 10 nhãn implication (5 P3 +
5 P4). Dạng khó bị lạm dụng thành dạng phổ biến thì mất tác dụng phân loại.

Hành động: blueprint ép `implication` về P4 (~3 cụm/đề), P3 giữ 0–1; đồng thời xoay
khuôn hỏi (`implication_kind` đã có 4 biến thể — kiểm tra `spread` của nó, hiện
model vẫn lãnh trọn khuôn quote-a-line dễ viết nhất).

### P0-4. P7: thừa email, thiếu chất liệu đời thường; hình render thay bảng text

- Thật (15 cụm): NOTICE ×4, ADVERT ×3, ARTICLE/REVIEW ×3, EMAIL ×2, TEXT_CHAIN ×2,
  SCHEDULE ×1. Single toàn văn bản "đời thường": hướng dẫn lắp ráp trong hộp hàng,
  nội quy khán phòng, thông báo rau thừa tặng cộng đồng, review máy rửa bát, tin
  tuyển dụng hãng bay. Multi toàn text+text đặc thù: báo + review 2 sao + email xin
  lỗi của chủ quán; hóa đơn + mail khiếu nại; quảng cáo khóa học + forum học viên;
  thư người bán + vé phà.
- AI: **EMAIL ×6/15 (gấp 3 lần)**, ANNOUNCE ×1; multi nào cũng kẹp bảng giá/lịch/
  khảo sát render thành hình riêng.

Hai việc: (a) bổ sung topic vào mixes P7 (notice, review sản phẩm, tuyển dụng,
combo khiếu nại, vé/phiếu); (b) quyết policy hình P7: đề thật có 2 cụm đọc bảng
(schedule liên văn phòng, hóa đơn) nhưng là **passage dạng bảng inline**, không
phải hình render — paste P7 ba form đều 0 câu `"Look at the graphic"`. Cân nhắc
dạng `passage` text-table thay vì graphic render ở P7.

Độ dài P7 cũng cần cổng trần: multi thật lên tới 394 từ/file, AI max chỉ 244
(form-18 còn ngắn hơn thật 18% toàn part).

### P1-1. P4 thiếu hẳn 4 dạng bài nói

Thật có: **tour thuyết minh** (nhà kính, khu khảo cổ), **podcast how-to** (sửa mái
nhà), **diễn văn gây quỹ**, **diễn văn khánh thành của thị trưởng**, **public
lecture** (làm vườn). AI chỉ quanh quẩn meeting/training/workshop/thông báo
(TALK/MEETING/ADVERT/TELEPHONE chia đều).

Hành động: thêm speech_type + cast tương ứng vào `PART4_MIX` (tour cần 1 giọng
dẫn + danh từ địa điểm; podcast cần mở đầu episode; diễn văn cần xưng hô
"distinguished guests…").

### P1-2. P2 thiếu WHAT-question, chia đều quá tay

Thật: WHO ×4, STATEMENT ×3, WHEN ×1, WHAT ×1 (`"What type of job…?"`).
AI: WHEN/HOW/WHERE đều ×3, **WHAT = 0** (bù bằng `Which…?`), WHO/STATEMENT nhẹ
hơn thật. Hành động: chỉnh bảng mixes P2 theo phân bố thật (WHO 4, STATEMENT 3,
WHEN 1, WHAT ≥1).

### P1-3. Band từ vựng: mỏng đầu phổ, đặc đuôi

ETS sample (`_content_words`): ≤3k **79.6%**, ngoài-10k **6.8%.** Họ đề AI: ≤3k
thấp hơn 4–13 điểm, ngoài-10k 7.3–11%. Nghịch lý: form viết tay dài chuẩn ETS nhất
lại đặc từ nhất — dài mà không loãng được vì model rải từ khó thay vì từ thường.

Đích đề xuất (≥75% / ≤8%) mới là "đường chỉ qua giữa", **chưa cho làm cổng**.
Hành động: cần thêm 2–3 nguồn thật đo được rồi mới đóng cổng (đừng neo vào sách
2024 — nó đặc gấp 2–3 lần đề thật).

### P1-4. Tốc độ đọc 124 vs 150–160 wpm

Toàn bộ phần Nghe dễ hơn ở một trục phủ mọi câu (`tts_rate -20%`). Đây là **nợ có
ý thức** (đổi rate dời `source_hash` → recast cả thư viện) — giữ nguyên, ghi nhận
để khi nào recast thì làm một thể, đừng sửa lẻ từng đề.

## 3. Ma trận đối chiếu nhanh

| Tiêu chí | Đề thật / ETS | form-17 | form-18 | Việc cần làm |
|---|---|---|---|---|
| Khung 103 ô/200 câu | ✓ | ✓ | ✓ | giữ |
| Câu hình LC 5 đúng vị trí/mẫu câu | ✓ | ✓ | ✓ | giữ |
| Balance đáp án ~25% | ✓ | ✓ | ✓ (51/49/54/46) | giữ |
| Thoại P3/P4 ~95–100 từ, biên rộng | ✓ | P3 ngắn 21% | dài 37%, đều | cổng trần + biên độ |
| Paraphrase đáp đúng | mạnh (trừ detail) | — | copy nguyên | cổng phủ từ theo dạng câu |
| Hàm ý 3 câu, đều P4 | ✓ | thưa | 10 nhãn | ép về P4, xoay khuôn |
| P7 ít email, nhiều chất liệu | ✓ | EMAIL ×6 | EMAIL ×6 | bổ sung topic + policy hình P7 |
| P4 đủ dạng (tour, podcast, diễn văn) | ✓ | thiếu | thiếu | thêm speech_type |
| P2 đủ WHAT, WHO ×4 | ✓ | thiếu WHAT | thiếu WHAT | chỉnh mixes |
| Band từ ≤3k ~80% | 79.6% | 66–76% | ~67% | đo thêm nguồn rồi đóng cổng |
| Tốc độ đọc 150–160 wpm | ✓ | 124 | 124 | nợ có ý thức, giữ |
| Explanation 200/200 | sách thiếu key RC | ✓ | ✓ | giữ, vượt nguồn |

## 4. Thứ tự làm đề xuất

1. Cổng volume thoại (trần + biên độ) — chạm mọi câu Nghe, sửa 1 cổng.
2. Cổng paraphrase đáp đúng theo dạng câu — nâng khó mà không cần viết lại đề.
3. Mixes P2/P4/P7 (WHAT-question, speech_type mới, topic đời thường) — sửa bảng tĩnh.
4. Policy hình P7 (text-table vs render) — quyết 1 lần, áp mọi đề sau.
5. Band từ thành cổng — sau khi có thêm nguồn thật để neo.
