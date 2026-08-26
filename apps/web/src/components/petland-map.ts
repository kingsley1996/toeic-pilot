/**
 * Bản đồ ô của góc thú cưng: kiểu dữ liệu, va chạm, tìm đường.
 *
 * **Số học thuần.** Không React, không Pixi, không đường dẫn ảnh. Cùng kỷ luật
 * với `petland-pet.ts`, và cùng lý do: thứ quyết định "đi được tới đâu" phải
 * kiểm được mà không cần trình duyệt, và phải sống sót qua việc đổi renderer.
 *
 * **Bản đồ là DỮ LIỆU, không phải mã nguồn.** Bản trước vẽ bằng chuỗi ký tự kèm
 * bảng tra, và lập luận cho nó là "nhìn thấy bố cục ngay trong code". Lập luận
 * ấy hết giá trị từ khi có trình sửa trực quan: **trình sửa CHÍNH LÀ cái nhìn**,
 * và nó tốt hơn hẳn mấy dòng ký tự. Thêm nữa, bốn tấm ghép có gần 600 ô — không
 * nhét vừa một ký tự mỗi ô.
 *
 * Bản đồ sống ở `public/pet/map.json`, do `/admin/petland` xuất ra.
 */

/** Cỡ ô nguồn. Mọi hệ số phóng phải là SỐ NGUYÊN của con số này (ADR-010 §13). */
export const TILE = 16;

/** Tấm ghép ô nào. Xem `public/pet/CREDITS.md`. */
export type SheetId = "town" | "farm" | "water" | "stone";

export const SHEET_IDS: readonly SheetId[] = ["town", "farm", "water", "stone"];

/**
 * Số cột của từng tấm. Sai số cột thì ô vẫn vẽ ra, chỉ là vẽ NHẦM ô — không có
 * lỗi nào, không có gì báo, chỉ có bản đồ trông lạ.
 */
export const SHEET_COLS: Record<SheetId, number> = {
  town: 12,
  farm: 12,
  water: 18,
  stone: 12,
};

/** Số hàng, để bảng chọn ô biết vẽ dài bao nhiêu. */
export const SHEET_ROWS: Record<SheetId, number> = {
  town: 11,
  farm: 11,
  water: 11,
  stone: 11,
};

export type Cell = { sheet: SheetId; index: number } | null;

/**
 * Một bản đồ hoàn chỉnh.
 *
 * `solid` tách khỏi hai tầng ảnh có chủ ý. Ô chặn đường không suy ra được từ ô
 * ảnh: cái ao chặn vì mặt đất, cái cây chặn vì vật thể, còn luống rau thì KHÔNG
 * chặn dù cũng là vật thể. Suy ra từ ảnh nghĩa là phải nuôi một danh sách "ảnh
 * nào thì chặn", và danh sách đó sai vào ngày ai đó thêm một ô mới. Người thiết
 * kế tự quyết, và trình sửa cho họ nhìn thấy nó.
 */
export type MapData = {
  w: number;
  h: number;
  ground: Cell[];
  objects: Cell[];
  solid: boolean[];
};

export type Tile = { x: number; y: number };

export function emptyMap(w: number, h: number): MapData {
  const size = w * h;
  return {
    w,
    h,
    ground: Array<Cell>(size).fill(null),
    objects: Array<Cell>(size).fill(null),
    solid: Array<boolean>(size).fill(false),
  };
}

/**
 * Đọc bản đồ từ dữ liệu chưa tin được (tệp JSON tự sửa hoặc tự xuất).
 *
 * Trả `null` thay vì ném, để chỗ gọi quyết định làm gì khi tệp hỏng — góc thú
 * cưng vắng mặt còn hơn cả trang trắng.
 */
export function parseMap(raw: unknown): MapData | null {
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Partial<MapData>;
  const { w, h } = data;
  if (typeof w !== "number" || typeof h !== "number" || w < 1 || h < 1) return null;
  const size = w * h;
  const layer = (value: unknown): Cell[] | null =>
    Array.isArray(value) && value.length === size ? (value as Cell[]) : null;
  const ground = layer(data.ground);
  const objects = layer(data.objects);
  if (!ground || !objects) return null;
  const solid =
    Array.isArray(data.solid) && data.solid.length === size
      ? (data.solid as boolean[])
      : Array<boolean>(size).fill(false);
  return { w, h, ground, objects, solid };
}

export function inBounds(map: MapData, x: number, y: number): boolean {
  return x >= 0 && y >= 0 && x < map.w && y < map.h;
}

export function isWalkable(map: MapData, x: number, y: number): boolean {
  return inBounds(map, x, y) && !map.solid[y * map.w + x];
}

/** Ô đứng được gần nhất, để vị trí đã lưu từ bản đồ CŨ không kẹt trong tường. */
export function nearestWalkable(map: MapData, from: Tile): Tile {
  if (isWalkable(map, from.x, from.y)) return from;
  for (let r = 1; r < Math.max(map.w, map.h); r += 1) {
    for (let dy = -r; dy <= r; dy += 1) {
      for (let dx = -r; dx <= r; dx += 1) {
        if (Math.abs(dx) !== r && Math.abs(dy) !== r) continue;
        if (isWalkable(map, from.x + dx, from.y + dy)) {
          return { x: from.x + dx, y: from.y + dy };
        }
      }
    }
  }
  return { x: 0, y: 0 };
}

const STEPS: readonly Tile[] = [
  { x: 1, y: 0 },
  { x: -1, y: 0 },
  { x: 0, y: 1 },
  { x: 0, y: -1 },
];

/**
 * Đường ngắn nhất từ `from` tới `to`, gồm cả ô đích và KHÔNG gồm ô xuất phát.
 *
 * BFS chứ không A\*: bản đồ vài trăm ô nên BFS chạy trong micro giây và không có
 * hàm ước lượng nào để viết sai. Một hàm ước lượng sai cho ra đường đi *hợp lệ
 * nhưng vòng vèo* — trông như con thú bị lẫn chứ không như một lỗi.
 *
 * Bốn hướng, không đi chéo: đi chéo qua khe giữa hai gốc cây trông như xuyên
 * qua vật thể.
 *
 * Đích không đứng được thì trả mảng rỗng — bấm vào gốc cây là không làm gì, chứ
 * không phải đi tới ô cạnh nó. "Gần đúng chỗ bấm" đọc ra là điều khiển không
 * chính xác.
 */
export function findPath(map: MapData, from: Tile, to: Tile): Tile[] {
  if (!isWalkable(map, to.x, to.y) || !isWalkable(map, from.x, from.y)) return [];
  if (from.x === to.x && from.y === to.y) return [];

  const start = from.y * map.w + from.x;
  const goal = to.y * map.w + to.x;
  const prev = new Int32Array(map.w * map.h).fill(-1);
  const seen = new Uint8Array(map.w * map.h);
  seen[start] = 1;

  const queue: number[] = [start];
  for (let head = 0; head < queue.length; head += 1) {
    const at = queue[head];
    if (at === goal) break;
    const ax = at % map.w;
    const ay = (at / map.w) | 0;
    for (const step of STEPS) {
      const nx = ax + step.x;
      const ny = ay + step.y;
      if (!isWalkable(map, nx, ny)) continue;
      const next = ny * map.w + nx;
      if (seen[next]) continue;
      seen[next] = 1;
      prev[next] = at;
      queue.push(next);
    }
  }

  if (!seen[goal]) return [];
  const path: Tile[] = [];
  for (let at = goal; at !== start; at = prev[at]) {
    path.push({ x: at % map.w, y: (at / map.w) | 0 });
  }
  return path.reverse();
}
