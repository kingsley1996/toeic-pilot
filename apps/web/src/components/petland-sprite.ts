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

/** Mã loài → chỉ số ô. Xem `public/pet/CREDITS.md` để biết cách đổi chỉ số sang toạ độ. */
export const SPECIES_TILE: Record<string, number> = {
  cat: 169,
  squirrel: 175,
  frog: 147,
  duck: 150,
  monkey: 168,
  turtle: 149,
  owl: 117,
  deer: 161,
  raccoon: 178,
  tiger: 157,
  bear: 165,
  giraffe: 159,
};

/** Ô mặc định khi mã loài không có trong bảng — một con thú lạ vẫn hơn một ô trống. */
export const FALLBACK_TILE = SPECIES_TILE.cat;

export function tileForSpecies(species: string): number {
  return SPECIES_TILE[species] ?? FALLBACK_TILE;
}
