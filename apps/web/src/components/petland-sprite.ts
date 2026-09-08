/**
 * Loài nào vẽ bằng ô nào, và ô ấy nằm ở TẤM nào.
 *
 * **Đây là tệp duy nhất biết một `species` trông ra sao**, và nó không biết gì
 * khác: không bản đồ, không React, không Pixi. Đổi bộ sprite hay thêm tấm chỉ
 * đụng tới đây.
 *
 * Bản trước của tệp này là sổ đăng ký mascot: mỗi con một thư mục ảnh, năm dải
 * hoạt ảnh, ba con số đo tay (`cell`, `footY`, `anchorX`) mà `pack-pet.mjs` in
 * ra cho người chép vào. Giờ mỗi loài là **một tấm và một số** — chỉ số ô trong
 * tấm ghép — vì gói Tiny Creatures không có khung hoạt ảnh và chuyển động được
 * sinh lúc vẽ (ADR-010 §14.5). Thêm một loài mới tốn một dòng.
 */

import type { CreatureSheetId } from "@toeic-pilot/shared";

export type CreatureSheet = {
  /** Đường dẫn ảnh. Chỉ tệp này được biết nó. */
  url: string;
  cols: number;
  rows: number;
  /**
   * Số ô CÓ VẼ. Nhỏ hơn `cols * rows` khi hàng cuối chưa đầy.
   *
   * Đây là GỢI Ý CHO GIAO DIỆN, không phải luật: luật nằm ở
   * `CREATURE_SHEET_TILES` phía API, và máy chủ trả 422 cho ô vượt trần. Lệch
   * số ở đây làm ô nhập cho gõ một giá trị máy chủ từ chối — một lỗi nói ra
   * được, không phải một con thú tàng hình.
   */
  tiles: number;
};

/**
 * Các tấm ghép sinh vật.
 *
 * `CreatureSheetId` đến từ API qua OpenAPI, nên **thiếu một tấm ở đây là lỗi
 * `tsc`**, không phải `undefined` lúc chạy — cùng khuôn `Record<MascotId,
 * Mascot>`. Thêm tấm: một dòng ở `CREATURE_SHEET_TILES` bên API, một dòng ở
 * đây, rồi `pnpm gen:api-types`.
 *
 * Số cột đã bị đoán sai một lần: nút thu gọn của góc thú cưng lấy số cột từ
 * `SHEET_COLS.town` (12, số cột của tấm NỀN) trong khi chia hàng cho 10 — nên
 * nó cắt ra một mảnh của con khác, đủ giống một con thú để không ai nhận ra là
 * sai. Đó là lý do bảng này ở một chỗ và mọi nơi khác phải hỏi nó.
 */
export const CREATURE_SHEETS: Record<CreatureSheetId, CreatureSheet> = {
  creatures: { url: "/pet/creatures.png", cols: 10, rows: 18, tiles: 180 },
  dinos: { url: "/pet/dinos.png", cols: 10, rows: 2, tiles: 16 },
  myth: { url: "/pet/myth.png", cols: 10, rows: 5, tiles: 44 },
};

export const DEFAULT_CREATURE_SHEET: CreatureSheetId = "creatures";

/**
 * Tấm của một loài, chịu được cả giá trị thiếu.
 *
 * Hàng cũ trong database không có cột `sheet`, và một lượt gọi API hỏng cũng
 * cho ra `undefined`. Cả hai đều phải vẽ ra được thứ gì đó: rơi về tấm gốc cho
 * ra con thú SAI ở một hàng dữ liệu hỏng, còn ném lỗi thì cho ra một góc thú
 * cưng trắng trơn.
 */
export function creatureSheet(id: string | null | undefined): CreatureSheet {
  return CREATURE_SHEETS[id as CreatureSheetId] ?? CREATURE_SHEETS[DEFAULT_CREATURE_SHEET];
}

/** Số cột của tấm gốc. Giữ lại vì `petland-bestiary.ts` đánh số theo nó. */
export const CREATURE_COLS = CREATURE_SHEETS.creatures.cols;
export const CREATURE_ROWS = CREATURE_SHEETS.creatures.rows;
