# Tranh khung avatar và huy hiệu

Nguồn của những gì đang nằm trên Cloudinary dưới `toeic-pilot/progression/`. Giữ ở
đây vì **ảnh không tái tạo được** — cùng cái bẫy `MEDIA-PIPELINE` §10.3 đã ghi:
`media/` bị gitignore, model sinh ảnh không tất định, và một tấm bị xoá nhầm trên
kho thì không có cách nào dựng lại đúng như cũ. Tệp ở đây nhỏ (vài chục KB) và là
bản đã xử lý xong, sẵn sàng tải lên lại.

## Cách làm một tấm mới

Bộ skill `agent-sprite-forge` ở `~/.claude/skills/`. Nó vốn dựng cho sprite game
nên **chỉ dùng hai mắt xích đầu**: sinh ảnh, rồi tách nền. Phần sheet, frame,
animation, anchor, Godot đều không liên quan.

```bash
# 1. Sinh — nền PHẢI là #FF00FF đặc, đó là quy ước của bước tách nền phía sau.
python3 ~/.claude/skills/_imagegen/image_gen.py --aspect 1:1 \
  --out raw.png --prompt "...; solid #FF00FF magenta background, generous magenta padding, nothing touching the image edges"

# 2. Tách nền + cắt sát + xuất PNG trong suốt. `--rows 1 --cols 1` vì đây là một
#    tấm tĩnh, không phải sheet.
~/.claude/skills/.venv/bin/python \
  ~/.claude/skills/generate2dsprite/scripts/generate2dsprite.py process \
  --input raw.png --target asset --mode single --rows 1 --cols 1 \
  --cell-size 512 --fit-scale 0.98 --align center --component-mode largest \
  --output-dir out/
# -> out/single-1.png
```

**Bước 1b — chuẩn hoá nền — là bắt buộc, không phải tuỳ chọn.** Model KHÔNG vẽ
đúng `#FF00FF` một cách đáng tin: sáu khung của lượt bronze→challenger đều ra nền
hồng đậm (~#E8207F), và bước tách nền khoá theo magenta thuần nên nó trượt sạch.
Cái hỏng không kêu: sản phẩm vẫn là một PNG "trong suốt", chỉ có điều tâm vẫn đặc
100% — tức cái khung sẽ che kín avatar. Chỉ đo mới thấy.

```bash
~/.claude/skills/.venv/bin/python normalise_bg.py raw.png raw-magenta.png
```

`normalise_bg.py` lấy màu nền từ chính BỐN GÓC ảnh chứ không so với một danh sách
sắc hồng: góc là chỗ duy nhất chắc chắn là nền (prompt đã bắt chừa lề), nên nó tự
nói model vừa vẽ nền màu gì. Một danh sách cứng sẽ hỏng ở lần model chọn sắc thứ
bảy. Sau bước này, `tâm đặc` rơi từ 100% xuống 0% và pixel ám hồng từ ~50% xuống
dưới 2%.

Kiểm nhanh sau khi xử lý — hai con số này bắt đúng hai kiểu hỏng đã gặp:

```python
op = alpha > 40                      # tâm đặc phải ~0%: khung không được bịt avatar
fringe = op & (r>120) & (b>120) & (g<r-40) & (g<b-40)   # ám hồng nên dưới ~2%
```

Cỡ: khung **512px**, huy hiệu **256px**. Khung cần to hơn vì nó phóng lên quanh
avatar `lg` (64px) và tràn ra 25% mỗi phía.

Rồi tải lên trong `/admin/progression`, nút Upload ở đúng hàng của bậc/huy hiệu đó.

## Hai điều học được khi chạy thật

- **Provider tự chọn là `flux2` chạy tại máy** (`mlx-community/flux2-klein-4b-4bit`),
  ~2,5 phút một tấm, đỉnh 12,37 GB RAM trên máy M2 16 GB — chạy được. Không dùng
  Qwen-Image: 20B cộng text encoder 7B thì máy này treo.
- **Nói rõ trong prompt là KHÔNG được vẽ đường viền hồng/magenta.** Bước tách nền
  chỉ xoá nền, nó không phân biệt được nền với một nét vẽ cùng màu. `frame-gold`
  còn ~2,7% pixel ám hồng ở rìa vì model tự vẽ một nét viền hồng nhạt — ở cỡ hiển
  thị thật thì gần như không thấy, nhưng lần sau thì viết thêm câu đó vào prompt.

## Prompt đã dùng

Xem `frame-gold.prompt.txt` và `badge-streak_7.prompt.txt`.
