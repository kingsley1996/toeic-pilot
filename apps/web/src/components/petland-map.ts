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

/**
 * Những ô của tấm ghép `water` thật sự LÀ nước.
 *
 * Không phải cả tấm: ô 1 của nó là cỏ và được dùng 99 lần trong bản đồ hiện tại,
 * nên "sheet === water" là một phép thử sai — nó sẽ biến gần hết bãi cỏ thành ao.
 *
 * Bộ ghép bờ là 3×3, nhưng chỉ SÁU ô đầu tính là nước — và ranh giới nằm ở ĐÁY
 * Ô, không phải ở giữa ô.
 *
 * Con thú neo ở đáy ô của nó, nên thứ quyết định nó đứng hay bơi là cái nằm dưới
 * chân nó. Hàng trên (18–20) có cỏ ở nửa trên và nước ở dưới — chân ngập, tính là
 * bơi. Hàng giữa (36–38) là nước đầy. Hàng dưới (54–56) thì ngược lại: nước ở
 * trên, cỏ ở dưới, tức là con thú đứng trên bờ.
 *
 * Đây không phải suy luận trên giấy: bản đầu tính cả chín ô, và ảnh chụp cho
 * thấy con thú bị cắt ngang kèm gợn nước trong khi đang đứng hẳn trên cỏ.
 */
const WATER_TILES: ReadonlySet<number> = new Set([18, 19, 20, 36, 37, 38]);

/** Ô này có nước không — dùng để vẽ con thú đang bơi và để khách tránh đứng dưới ao. */
export function isWater(map: MapData, x: number, y: number): boolean {
  if (!inBounds(map, x, y)) return false;
  const cell = map.ground[y * map.w + x];
  return cell !== null && cell.sheet === "water" && WATER_TILES.has(cell.index);
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

/**
 * Chỗ đứng cho một vị khách: **đứng được, và nằm trong tầm nhìn**.
 *
 * Hai ràng buộc, và bỏ ràng buộc nào cũng hỏng im lặng. Bốc bằng một công thức
 * thuần trên toạ độ bản đồ (`4 + seed % 9`) thì khách rơi vào tường — và tệ hơn,
 * rơi ra **ngoài khung nhìn**: khung mặc định là 14×8 ô của một bản đồ 18×13,
 * còn máy quay thì chỉ bám con thú. Khách không có mặt trên màn hình thì không
 * thấy sprite, không thấy dấu hiệu, không bấm vào đâu được — cả cơ chế trông như
 * chưa được dựng, mà máy chủ thì vẫn báo có một cuộc đang chờ.
 *
 * Nên khoảng cách đo quanh CON THÚ chứ không quanh tâm bản đồ: máy quay bám con
 * thú, nên "gần con thú" là định nghĩa duy nhất của "nhìn thấy được" mà chỗ này
 * biết được. Bộ số mặc định bám đúng vùng chết của máy quay: nó giữ con thú
 * trong khoảng ±2 ô ngang và ±1,5 ô dọc quanh tâm, nên ±4 ngang luôn nằm trong
 * khung, còn chiều dọc thì **lệch xuống dưới** (1 lên, 2 xuống) vì dấu hiệu nhô
 * hơn một ô lên trên đầu khách và sẽ bị cắt mất ở hàng trên cùng.
 *
 * `seed` chọn trong danh sách đã lọc chứ không bốc rồi thử lại: cùng một khách
 * luôn ra cùng một ô sau khi tải lại trang, và không có vòng lặp nào có thể
 * không kết thúc.
 *
 * `taken` là những ô đã có người đứng — tối đa bốn vị khách cùng lúc, và hai
 * người chồng khít lên nhau là một cú bấm không biết mở thẻ của ai.
 */
export function spotNear(
  map: MapData,
  near: Tile,
  seed: number,
  taken: ReadonlySet<string> = new Set(),
  span: { x: number; up: number; down: number } = { x: 4, up: 1, down: 2 },
): Tile {
  const free: Tile[] = [];
  const any: Tile[] = [];
  for (let dy = -span.up; dy <= span.down; dy += 1) {
    for (let dx = -span.x; dx <= span.x; dx += 1) {
      // Không đứng chồng lên con thú, và không đứng sát tới mức che mất nó.
      if (Math.abs(dx) <= 1 && Math.abs(dy) <= 1) continue;
      const x = near.x + dx;
      const y = near.y + dy;
      // Khách không đứng giữa ao: con thú thì bơi được, còn một NPC lội tới ngực
      // giữa hồ để giao bài tập thì đọc ra là đặt sai chỗ.
      if (!isWalkable(map, x, y) || isWater(map, x, y)) continue;
      any.push({ x, y });
      if (!taken.has(`${x},${y}`)) free.push({ x, y });
    }
  }
  // Ô đã có người là điều KIÊNG, không phải điều cấm: hết chỗ trống thì vẫn
  // phải trả về một ô đứng được, còn hơn đẩy vị khách vào tường. Chồng nhau chỉ
  // xấu; đứng trong tường thì không bấm được.
  const options = free.length > 0 ? free : any;
  // Bản đồ chật tới mức không còn ô nào quanh con thú: lùi về ô đứng được gần
  // nhất chứ không trả một ô tường.
  if (options.length === 0) return nearestWalkable(map, near);
  return options[seed % options.length];
}

/**
 * Ô kề `at` mà đứng được, gần `from` nhất.
 *
 * Để con thú dừng CẠNH vị khách chứ không giẫm lên người ta: hai sprite chồng
 * khít lên nhau thì con nào hiện ra trước là chuyện của thứ tự thêm vào danh
 * sách vẽ, không phải của khung cảnh.
 *
 * Chọn ô gần `from` nhất nên con thú đi đường ngắn nhất, thay vì vòng qua lưng
 * khách để tới cái ô đầu tiên trong danh sách.
 */
export function neighbourOf(map: MapData, at: Tile, from: Tile): Tile | null {
  const around = [
    { x: at.x + 1, y: at.y },
    { x: at.x - 1, y: at.y },
    { x: at.x, y: at.y + 1 },
    { x: at.x, y: at.y - 1 },
  ].filter((spot) => isWalkable(map, spot.x, spot.y));
  if (around.length === 0) return null;
  return around.reduce((best, spot) =>
    Math.abs(spot.x - from.x) + Math.abs(spot.y - from.y) <
    Math.abs(best.x - from.x) + Math.abs(best.y - from.y)
      ? spot
      : best,
  );
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
export function findPath(
  map: MapData,
  from: Tile,
  to: Tile,
  blocked: ReadonlySet<string> = new Set(),
): Tile[] {
  if (!isWalkable(map, to.x, to.y) || !isWalkable(map, from.x, from.y)) return [];
  // Ô có người đứng cũng là ô không đi qua được. Không có nó thì con thú xuyên
  // thẳng qua một NPC trên đường tới chỗ được bấm, và hai sprite chồng khít lên
  // nhau — cùng lý do `neighbourOf` tồn tại.
  if (blocked.has(`${to.x},${to.y}`)) return [];
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
      if (!isWalkable(map, nx, ny) || blocked.has(`${nx},${ny}`)) continue;
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

/**
 * Ô kế tiếp cho một sinh vật đang đi lang thang quanh chỗ của nó.
 *
 * Trả về `null` khi không đi đâu được — bị kẹt bốn phía, hoặc bán kính bằng 0.
 * Người gọi hiểu đó là "đứng yên lượt này", không phải một lỗi.
 *
 * Hai luật, cả hai đều là để con vật trông có chủ đích thay vì trôi dạt:
 *
 *   · **Không đi quá `radius` ô khỏi NHÀ.** Bò trong chuồng phải ở lại trong
 *     chuồng; không có ràng buộc này thì sau mười phút cả đàn dồn về một góc bản
 *     đồ và cảnh nuôi trồng biến mất.
 *   · **Đo bằng khoảng cách Chebyshev** (ô xa nhất theo một trục), không phải
 *     đường chim bay: lưới này đi bốn hướng, nên hình vuông mới là hình mà một
 *     con vật thật sự đi hết được.
 *
 * `rand` là tham số chứ không gọi thẳng `Math.random`, cùng lý do `srs.review`
 * nhận `now`: một chuyển động không lặp lại được thì không kiểm được bằng gì cả.
 */
export function wanderStep(
  map: MapData,
  from: Tile,
  home: Tile,
  radius: number,
  rand: () => number,
): Tile | null {
  if (radius <= 0) return null;
  const options: Tile[] = [];
  for (const [dx, dy] of [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ] as const) {
    const next = { x: from.x + dx, y: from.y + dy };
    if (!isWalkable(map, next.x, next.y)) continue;
    if (Math.max(Math.abs(next.x - home.x), Math.abs(next.y - home.y)) > radius) continue;
    options.push(next);
  }
  if (options.length === 0) return null;
  return options[Math.min(options.length - 1, Math.floor(rand() * options.length))];
}

/**
 * Một ô đi được, cách `from` ít nhất `min` ô — chỗ để dắt con thú đi dạo.
 *
 * Quét cả bản đồ rồi bốc ngẫu nhiên trong số hợp lệ, chứ không bốc bừa rồi thử
 * lại: bản đồ 18×13 là 234 ô nên quét hết rẻ hơn một vòng lặp thử-và-sai không
 * có điểm dừng, và bản đồ chật (hầu hết là tường) sẽ làm vòng lặp kia quay mãi.
 */
export function strollTarget(
  map: MapData,
  from: Tile,
  min: number,
  rand: () => number,
  max = Number.POSITIVE_INFINITY,
): Tile | null {
  const options: Tile[] = [];
  for (let y = 0; y < map.h; y += 1) {
    for (let x = 0; x < map.w; x += 1) {
      if (!isWalkable(map, x, y)) continue;
      const away = Math.abs(x - from.x) + Math.abs(y - from.y);
      // `max` để dùng cho việc TỰ đi lang thang: nút "Đi dạo" muốn một chuyến
      // thật xa, còn con thú tự đi thì chỉ quanh quẩn, và bán kính ấy chính là
      // thứ diễn tả tình trạng của nó.
      if (away < min || away > max) continue;
      options.push({ x, y });
    }
  }
  if (options.length === 0) return null;
  return options[Math.min(options.length - 1, Math.floor(rand() * options.length))];
}
