# SPEC-HALL-OF-FAME — Sảnh danh vọng: BXH level học viên + level thú cưng

Hai bảng xếp hạng toàn hệ thống, chỉ đọc, không mùa giải ở v1:

- **BXH học viên**: xếp theo tổng XP (`SUM(xp_event)`), hiện level.
- **BXH thú cưng**: xếp theo MỌI con trong tủ (`pet_owned`), hiện level + tên
  riêng. Một hàng là một con — một người được chiếm nhiều hàng.

## 0. Quyết định khóa trước khi dựng

**Hiện level nào?** `level_reached` (mốc nước cao đã lưu), không tính lại từ
tổng XP. Bảng ngưỡng là dữ liệu admin sửa được — tính lại lúc đọc thì một lần
nâng chuẩn làm cả bảng tụt level cùng lúc, và người đứng đầu hôm qua có thể rớt
hạng mà không làm gì sai. `level_reached` đã tồn tại ở cả hai bên
(`user_profile`, `pet_owned`) đúng cho việc này.

**Xếp bằng gì?** Tổng XP (học viên), cặp `(level_reached, xp)` (thú). Không xếp
bằng level thuần: level là bậc thang, cả trăm người cùng Lv 5 thì thứ hạng là
bốc thăm.

**Ai được lên bảng?** TẤT CẢ — mọi user lên bảng học viên, mọi con ĐANG NUÔI
lên bảng thú. Không cổng private, không opt-in.

Tên hiển thị: `display_name` nếu có, không thì email che (`local` giữ 2 ký tự
đầu + `"***"` — `"linhdn0908@gmail.com"` thành `"li***"`). Quy tắc này sống
trong một hàm duy nhất phía backend để bảng và mọi chỗ sau này che giống nhau;
không bao giờ lộ nguyên email của người khác.

**Thú nào lên bảng?** TẤT CẢ con trong tủ — không riêng con đang nuôi. Một hàng
là một con, `my_rank` là hạng của con TỐT NHẤT của người xem, và mọi hàng của
mình đều highlight. Mở trứng mới là có thêm hàng để leo — đúng vòng lặp gacha
muốn khuyến khích.

## 1. API

`GET /hall-of-fame/users?limit=N` và `GET /hall-of-fame/pets?limit=N`
(`1 ≤ N ≤ 100`, mặc định 20). Đọc công khai (kể cả khách, theo tinh thần
ADR-015: nội dung tổng hợp không phải dữ liệu riêng); đăng nhập thì kèm highlight.

Response mỗi bảng:

- `entries[]`: `{rank, display_name, level, xp_total, is_me}` (bảng thú thêm
  `species`, `nickname`, `tier`, `tile`, `sheet`). Bảng học viên kèm
  `avatar_url` dựng ở backend theo đúng cách `profile_public` (có ảnh thì URL
  thật, không thì null để giao diện rơi về chữ cái đầu).
- `my_rank: int | null` — hạng của chính người gọi (`null` khi khách, khi chưa
  đặt tên, hoặc (bảng thú) khi chưa mở trứng.
- `total: int` — tổng số người trên bảng (để in "hạng 7/132").

Truy vấn, mỗi bảng đúng 2 câu:

1. Top N: `SUM(xp_event)` theo user (kể cả tổng 0 — tài khoản mới vẫn có hàng),
   `ORDER BY xp_total DESC LIMIT N`. Bảng thú: mọi hàng `pet_owned`,
   `ORDER BY (level_reached, xp) DESC LIMIT N` — không join `pet_state`, con
   nào cũng lên được.
2. Hạng của tôi: `1 + COUNT(người/con có tổng lớn hơn tôi)`. Bảng thú so theo
   con tốt nhất của tôi. Không kéo cả bảng về đếm ở Python.

Level tính ở Python trên N hàng đã lấy (đường cong thú là hằng số code,
đường cong người đọc một lần từ `progression_config`). Không tính level trong
SQL: hai đường cong sống ở hai nơi khác nhau, và SQL không phải chỗ thứ ba.

## 2. UI — `/hall-of-fame`

Hai tab (Học viên / Thú cưng). Top 3 dạng podium (nhất to hơn, màu hạng cho
thú), còn lại danh sách. Dòng của mình highlight + ghim câu "Hạng của bạn:
7/132" kể cả khi ngoài top N (dữ liệu đã có trong response, không gọi thêm).

Lối vào: link từ dashboard (kề CTA placement/kế hoạch — đó là nơi mắt tìm "mình
đang ở đâu") và từ trang profile. Không nhét vào sidebar: nav đã chốt theo
khu học, thêm mục mới là thêm một chỗ phải nhớ.

## 3. Không làm ở v1

- Mùa giải / BXH tuần-tháng (cần cột thời gian trên XP + job chốt mùa — để khi
  có người hỏi "sao tôi leo mãi không lên" vì top đã đóng băng).
- Lọc theo bạn bè (chưa có quan hệ bạn bè).
- Huy hiệu top (trao sau khi bảng sống, không vẽ trước).
- Opt-out riêng (chưa đặt tên đã là opt-out; thêm cờ khi có người yêu cầu).

## 4. Kiểm

- Thứ hạng đúng khi XP genesis rải rác + đồng hạng (đồng XP thì `rank` nào?
  chốt: cùng hạng, hạng kế nhảy — `1,2,2,4`, một dòng trong docstring test).
- Chưa đặt tên thì hiện email che (`li***`), không vắng mặt; hai user cùng
  tiền tố che vẫn là hai dòng riêng (rank + level + dòng highlight phân biệt).
- Không bao giờ lộ nguyên email người khác — test ghim đúng định dạng che.
- Đổi con đang nuôi không đụng gì tới bảng thú (mọi con đều đã ở đó); nở con
  mới thì bảng có thêm hàng ngay lần đọc sau.
- Khách đọc được, `is_me` toàn false, `my_rank` null.
- `limit=101` → 422.
- Bảng thú trống (chưa ai mở trứng) → `entries: []` + empty state "Chưa ai mở
  trứng", không 404. Bảng học viên praktisch không bao giờ trống.

## 5. Rollout

Không migration. Không backfill (level_reached đã có từ trước ở cả hai bảng).
Deploy xong là bảng có số.
