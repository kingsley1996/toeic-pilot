import { SHEET_COLS, type Cell, type SheetId } from "@/components/petland-map";

/**
 * Bảng chọn ô, xếp theo VIỆC người vẽ đang làm chứ không theo thứ tự tệp.
 *
 * Bốn tấm ghép cộng lại là 594 ô, và thứ tự trong tệp là thứ tự của người đóng
 * gói: cây nằm cạnh mái nhà, còn `water.png` thì hơn hai phần ba là xe tăng và
 * máy bay của Tiny Battle — không dùng được ô nào cho góc thú cưng. Cuộn qua
 * ngần ấy ô để tìm một bụi cỏ là lý do bảng chọn cũ khó dùng.
 *
 * **Nhóm là lớp phủ, không phải bộ lọc.** Ô nào không được xếp nhóm vẫn tới
 * được qua mục "Toàn bộ tấm ghép". Đó là chủ ý: bảng này do người đọc ảnh xếp
 * ra, nên nó sẽ có chỗ sai, và một cái sai ở đây phải làm ô khó tìm chứ không
 * được làm ô biến mất.
 *
 * Sửa nhóm chỉ cần sửa tệp này; giao diện đọc nó chứ không tự biết gì.
 */
/** Ô trong bảng chọn luôn có thật — `null` là "xoá", việc của công cụ Erase. */
export type PaletteCell = NonNullable<Cell>;

export type PaletteGroup = {
  id: string;
  label: string;
  hint?: string;
  cells: PaletteCell[];
};

const at = (sheet: SheetId, ...indices: number[]): PaletteCell[] =>
  indices.map((index) => ({ sheet, index }));

/** Một khối chữ nhật trong tấm ghép — cách Kenney xếp gần như mọi thứ. */
const block = (sheet: SheetId, col: number, row: number, w: number, h: number): PaletteCell[] => {
  const cols = SHEET_COLS[sheet];
  const out: PaletteCell[] = [];
  for (let r = row; r < row + h; r++)
    for (let c = col; c < col + w; c++) out.push({ sheet, index: r * cols + c });
  return out;
};

export const PALETTE: PaletteGroup[] = [
  {
    id: "ground",
    label: "Mặt đất",
    hint: "Cỏ, đất, lối đi, sàn đá — vẽ ở tầng nền",
    cells: [
      ...at("town", 0, 1, 2),
      ...block("town", 0, 1, 3, 3),
      ...at("town", 39, 40, 41, 42, 43),
      ...block("stone", 0, 0, 3, 2),
      ...block("stone", 0, 2, 4, 2),
      ...block("farm", 0, 0, 2, 4),
    ],
  },
  {
    id: "water",
    label: "Nước và bờ",
    hint: "Bộ ghép bờ ao, hồ, thác — ô nước tự làm thú cưng bơi",
    // Hai khối chứ không một: cột 3–4 của các hàng dưới là MŨI TÊN và vạch
    // cảnh báo của Tiny Battle, không phải nước.
    cells: [...block("water", 0, 0, 5, 2), ...block("water", 0, 2, 3, 3)],
  },
  {
    id: "trees",
    label: "Cây và bụi",
    hint: "Cây hai ô xếp chồng, cây một ô, bụi, nấm",
    cells: [
      ...at("town", 3, 15, 4, 16, 27, 28, 5, 17, 29),
      ...block("town", 6, 0, 3, 3),
      ...block("town", 9, 0, 3, 3),
      ...at("farm", 3, 15, 27, 39),
    ],
  },
  {
    id: "cave",
    label: "Hang và đá",
    hint: "Miệng hang tối, tường đá, hốc đá",
    cells: [
      ...at("stone", 9, 10, 11, 21, 22, 23, 33, 34, 35, 45, 46, 47),
      ...at("stone", 4, 5, 16, 17),
      ...block("stone", 6, 0, 2, 3),
    ],
  },
  {
    id: "fire",
    label: "Lửa và ánh sáng",
    hint: "Ngọn lửa trong hốc tường, lò than, cửa chấn song",
    // Đúng hai ô. 28 và 40 là tường gạch trơn — đã thử và nhìn ra ngay khi
    // dựng ảnh từng nhóm, chứ mã thì không phân biệt được.
    cells: at("stone", 29, 41),
  },
  {
    id: "fence",
    label: "Hàng rào và biển",
    hint: "Rào gỗ, cột, biển chỉ đường",
    cells: [...block("town", 8, 3, 4, 3), ...at("town", 83, 80, 81, 82)],
  },
  {
    id: "props",
    label: "Đồ đạc",
    hint: "Thùng, hòm, ghế, bàn, dụng cụ, khúc gỗ",
    cells: [
      ...at("farm", 2, 14, 26, 38),
      ...at("town", 93, 94, 95, 105, 106, 107),
      ...at("town", 115, 116, 117, 118, 119, 127, 128, 129, 130, 131),
      ...at("stone", 63, 64, 65, 66, 67, 68, 72, 73, 74, 75, 79, 80),
    ],
  },
  {
    id: "farm",
    label: "Vườn và nông trại",
    hint: "Luống rau, cây trồng, kiện cỏ, giếng, máng nước",
    cells: [...block("farm", 3, 0, 9, 6), ...block("farm", 0, 6, 6, 3)],
  },
  {
    id: "building",
    label: "Nhà cửa",
    hint: "Mái, tường, cửa, cổng đá",
    cells: [...block("town", 0, 4, 8, 3), ...block("town", 0, 7, 6, 4)],
  },
  {
    id: "animals",
    label: "Vật nuôi",
    hint: "Cừu, bò, gà — trang trí, không phải thú cưng",
    cells: at("farm", 120, 121, 122),
  },
];

/** Mọi ô của một tấm, theo đúng thứ tự tệp. Lối thoát khi nhóm ở trên xếp sai. */
export function allCells(sheet: SheetId, rows: number): PaletteCell[] {
  return Array.from({ length: SHEET_COLS[sheet] * rows }, (_, index) => ({ sheet, index }));
}
