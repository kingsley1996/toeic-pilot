# Extract đề reference từ bộ sách 2024 (RC + LC)

Runbook cho thao tác: lấy test thứ N từ hai PDF trong `~/Downloads`, dựng thành
**một** thư mục `content/generated/tp-2024-{NN}/` (cả hai nửa LC + RC của
cùng một đề) để `compare` đối trùng lặp + đo band từ. Hai script ghi vào cùng
thư mục, mỗi script chỉ dọn part của mình (LC = p1–p4, RC = p5–p7).

## 1. Chạy

```bash
cd apps/api
uv run --with pymupdf python scripts/extract_ets2024_rc.py --test 4
uv run --with ocrmac --with pymupdf python scripts/extract_ets2024_lc.py --test 4
uv run python scripts/normalize_ref_paste.py content/generated/tp-2024-04/paste
```

Bước 3 chuẩn hoá về format nhà (chỉ p3–p7, không đụng p1/p2 đang vá tay):
gộp marker đôi, lột nhãn `W-Am:` + số câu ghim trong script, p6 `---1xx---`
→ `------- (n) -------` + stem `Blank (n)`, trả option lạc khỏi passage về
câu thiếu, cắt option lai Việt-Anh, gộp passage cụt <15 từ. Idempotent.
Dòng `CÒN:` in ra là tầng 2 (nội dung mất thật do OCR) — vá theo mục 2 dưới đây.

`--start/--end` (RC) và `--start` (LC, trang key 1-based) để định vị tay khi
máy dò ranh giới trật. LC cache OCR vào `<out>/_ocr/pages.json` — parse lại
không tốn OCR; `--redo-ocr` khi đổi tham số render.

Paste của nhà đánh số **thứ tự trong part**, không theo số đề — script LC đổi
Part 2 (số đề 6–35) thành `p2-01..25` cho khớp `compare`/family; câu hụt (kiểm
tra dòng `CHECK P2 thiếu`) để trống số thứ tự kế tiếp chứ không nhảy số đề.

## 2. Đọc STATS + xử lý CHECK (từng mục đã xảy ra thật ở test 1)

Kỳ vọng: RC `100/100`; LC `key=100 · p2≈24 · p3 39 · p4 30`. Mọi dòng `CHECK`
là lớp phòng thủ cuối — **không được bỏ qua**, nhưng mỗi loại chỉ mất vài phút:

- **`trang có bảng đồ hoạ` (RC)**: sách in schedule/price-table bằng text,
  `get_text` làm phẳng vỡ cột. Dựng lại bằng `page.get_text('words')`: cluster
  y ~4px, cột theo x, **cắt tại dòng tiếng Việt đầu** (bản dịch song song).
  Viết `graphics/p7-0X.txt` (`kind: schedule` + bảng pipe) và thay phần bảng
  trong paste bằng một dòng note. Test 1 có đúng 1 bảng (trang 18, set 149-150);
  thường nhiều hơn ở set 170s.
- **`blank Part 6 thiếu`**: marker `---131---` bị đứt trang thành `145---`/
  `- --145---` — postpass của script đã nối lại phần lớn; số còn lại vá regex
  trên chính tệp.
- **`còn tiếng Việt/giải thích`**: postpass xoá dòng có ký tự Việt; vụ việc sót
  thường là brand-name dòng lẻ xen vào — xoá tay.
- **`set không lời thoại` (LC)**: header `62-64` hoặc số cài bị OCR nuốt →
   turns dồn vào set trước. Xem `pages.json` của 2 trang quanh set đó, tìm dòng
   đầu hội thoại (`W-… <số>`), tách tay danh sách turns.
- **Graphic của LC (P3/P4)**: KHÔNG dựng `graphics/pX-NN.txt`. Ảnh thật của
  sách sẽ upload trực tiếp qua admin — tệp text mô tả bảng là thừa. Bảng trong
  **RC** (P7) vẫn dựng text như thông lệ vì `compare`/`check` cần chuỗi.
- **`P2 thiếu` (LC)**: số câu dính vào dòng của câu trước. Tìm số trong
  `pages.json`, thêm khối bằng regex nới `^(\d{1,2})`.
- **P1 statements > 24**: dòng chú giải (parenthetical gloss) lọt filter —
  cắt theo `(pg, y)` trùng lặp với statement thật; 24 là chuẩn.

## 3. Bẫy đã trả giá (đừng trả lại lần hai)

1. **`pypdf` vỡ layout 2 cột của PDF sách** — sinh fragment `'wha'`,
   `'usiness'` trông như từ tiếng Anh và **đo tần suất sẽ tin nó**. PyMuPDF
   `get_text('text')` là bắt buộc với file có text layer.
2. **tesseract chết với trang lẫn Hàn-Anh** (LC scan): trả 0 dòng không báo lỗi.
   Chỉ Apple Vision (`ocrmac`) đọc được; dùng `language_preference=['en-US']`
   và **whitelist ký tự** khi lọc — tỉ lệ ASCII thuần không chặn nổi
   `'§öl 4IC BiöC recipe'`.
3. **Vị trí cột KHÔNG cố định giữa các trang LC**: có trang hội thoại trái/
   câu hỏi phải, có trang đảo ngược. Mọi logic theo `x` cố định đều sai —
   phân loại theo nội dung dòng, dùng x chỉ để gom cluster quanh số câu.
4. **Object identity khi nối dòng**: `turns.append([pg,y,t0,x]); cur=t0` — nếu
   append một list *khác* rồi mutate bản sao, continuation lặng lẽ biến mất
   giữa chừng câu (đã xảy ra, mất ~45 phút vì thủ phạm trông như OCR lỗi).
5. **Câu một chữ số** (`7.`, `9.`, số trang `10`): mọi regex số câu phải
   `\d{1,3}` + kiểm khoảng; `\d{2,3}` âm thầm bỏ trọn Part 2 đầu sổ.
6. **Sổ câu LC bắt đầu từ 1, RC từ 101** — dùng lẫn là off-by-100 im lặng.
7. Page-window mặc định (RC +41, LC +31) có thể lệch khi sách dãn trang; nếu
   STATS ra 40/100 hoặc P3/P4 gộp vào nhau, xem lại `--start/--end` trước khi
   nghi parser.
8. Sách là **hàng giả lập ETS, không phải ETS**: đặc từ hơn đề thật ~2-3 lần
   (ngoài-10k 10-17% vs official sample ~7%, cùng `_content_words`). Dùng nó
   để chặn trùng lặp và bắt style hình thức, KHÔNG dùng làm đích band từ vựng
   hay wpm — xem SPEC-EXAM-DIFFICULTY §12.

## 4. Nghiệm thu

```bash
uv run python -m app.content.generate_exam compare --slug tp-form-XX   # thấy tp-2024-XX trong danh sách, exit 0
grep -rn "가-힣\|Ø\|HOTLINE" content/generated/tp-2024-*/paste | head  # phải rỗng
uv run python scripts/audit_ref_questions.py content/generated/tp-2024-XX/paste  # bảng cấp câu, vào GAPS.md của thư mục
```

`scripts/add_explanations_2024.py` gắn Answer+Explanation cho P2/P5/P6 (idempotent,
đáp án P5/P6 là DẪN XUẤT — sách chỉ in 46/100 nên phần thiếu ghi rõ trong text).

Mở mắt 2-3 tệp/set ngẫu nhiên mỗi part — `compare` xanh không nghĩa là hội
thoại không bị cắt giữa câu (nó chỉ đọc stem+options+material).

