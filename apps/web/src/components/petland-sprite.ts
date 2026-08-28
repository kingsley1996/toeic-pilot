/**
 * Loài nào vẽ bằng ô nào trong `public/pet/creatures.png`.
 *
 * **Đây là tệp duy nhất biết một `species` trông ra sao**, và nó không biết gì
 * khác: không bản đồ, không React, không Pixi. Đổi bộ sprite hay đổi loài chỉ
 * đụng tới đây.
 *
 * Bản trước của tệp này là sổ đăng ký mascot: mỗi con một thư mục ảnh, năm dải
 * hoạt ảnh, ba con số đo tay (`cell`, `footY`, `anchorX`) mà `pack-pet.mjs` in
 * ra cho người chép vào. Giờ mỗi loài là **một số** — chỉ số ô trong tấm ghép —
 * vì gói Tiny Creatures không có khung hoạt ảnh và chuyển động được sinh lúc vẽ
 * (ADR-010 §14.5). Thêm một loài mới tốn một dòng.
 *
 * Bảng này là **tạm**: `pet_species` (ADR-010 §6.3) sẽ nhận việc, để admin thêm
 * loài mà không cần deploy. Giữ ở đây tới lúc đó, và giữ NHỎ để lúc chuyển không
 * mất gì.
 */

/**
 * Hình học của `creatures.png`: 160×288 pixel, ô 16px, tức 10 cột × 18 hàng.
 *
 * Ở đây vì đây là tệp biết "một loài trông ra sao", và vì con số này đã bị đoán
 * sai một lần: nút thu gọn của góc thú cưng lấy số cột từ `SHEET_COLS.town`
 * (12, số cột của tấm NỀN) trong khi chia hàng cho 10 — nên nó cắt ra một mảnh
 * của con khác, đủ giống một con thú để không ai nhận ra là sai.
 */
export const CREATURE_COLS = 10;
export const CREATURE_ROWS = 18;

/**
 * Ô vẽ trên NÚT THU GỌN, và chỉ thế thôi.
 *
 * Trước đây chỗ này là một bảng `SPECIES_TILE` gồm mười hai mã loài — một bản
 * sao thứ hai của bảng loài, và nó đã trôi đúng như chú thích cạnh nó cảnh báo:
 * backend lên bốn mươi loài, bảng này vẫn nằm ở mười hai. Chưa hỏng gì, vì chỗ
 * duy nhất còn gọi tới nó luôn truyền `"cat"`.
 *
 * Nên cách sửa không phải là cập nhật bảng cho đủ bốn mươi — làm thế là hẹn một
 * lần trôi nữa vào ngày ai đó thêm loài thứ bốn mươi mốt. Xoá hẳn bảng đi: ô của
 * MỘT loài đến từ máy chủ (`PetPublic.tile`, xem chú thích ở `petland.tsx`), và
 * cái nút thu gọn thì vẽ trước khi có lượt gọi nào nên nó cần đúng một hằng số.
 */
export const LAUNCHER_TILE = 169;
