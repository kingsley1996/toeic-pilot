/**
 * Ô nào trong tấm ghép là CON GÌ, và nó đóng vai gì trong thế giới.
 *
 * `petland-sprite.ts` trả lời "loài nuôi được nào vẽ bằng ô nào". Tệp này trả
 * lời câu rộng hơn: trong 180 ô của `creatures.png` (và mấy ô sống trong hai tấm
 * nền), ô nào là **thú nuôi**, ô nào là **dân làng**, ô nào là **sinh vật hoang
 * dã**, và ô nào là **kẻ xâm nhập**. Không có nó thì mọi tính năng sau — gặp NPC
 * ngẫu nhiên, đánh kẻ xâm nhập bằng câu hỏi tiếng Anh — đều phải mở tấm ghép ra
 * đếm lại từ đầu, và mỗi lần đếm lại là một lần đếm khác.
 *
 * **Phân loại bằng MẮT, một lần, và ghi ra đây.** Tấm ghép không nói ô nào là
 * gì: nó chỉ là 180 hình 16×16 xếp cạnh nhau. Đây là kết quả của việc giải mã
 * PNG rồi phóng to từng khối sáu hàng mà xem — nên nó là dữ liệu người đọc chứ
 * không phải suy ra được, và thêm một gói sprite mới thì phải làm lại.
 *
 * **Bảng này là TẠM, đúng nghĩa mà `SPECIES_TILE` từng là tạm.** Ngày kẻ xâm
 * nhập có máu, có phần thưởng và có bộ câu hỏi gắn kèm thì nó phải xuống
 * database như `pet_species` đã xuống — vì lúc đó nó là thứ người vận hành cân
 * chỉnh, không phải thứ lập trình viên sửa. Giữ ở đây tới lúc đó, và giữ NHỎ để
 * lúc chuyển không mất gì.
 *
 * Không React, không Pixi, không đường dẫn ảnh: chỉ số và vai trò. Nhờ vậy máy
 * chủ cũng chép sang được nguyên xi vào ngày nó cần biết ô 42 là con ent.
 */

/**
 * Vai của một ô sinh vật.
 *
 *   · `pet` — nuôi được, ra từ trứng. Nguồn sự thật là bảng `pet_species` trong
 *     database; ở đây liệt kê để một ô không thể vừa là thú nuôi vừa là quái.
 *   · `npc` — người và sinh vật thân thiện sống trong làng. Đứng yên một chỗ,
 *     đi lại quanh nhà, và là thứ con thú tới bắt chuyện được.
 *   · `wildlife` — chim, cá, côn trùng, thú hoang. Có mặt để cảnh sống, không
 *     nói chuyện và không đánh nhau.
 *   · `intruder` — kẻ xâm nhập. Xuất hiện ở rìa bản đồ, và đây là thứ mà tính
 *     năng "trả lời câu hỏi tiếng Anh để đánh" sẽ gắn vào.
 */
export type CreatureRole = "pet" | "npc" | "wildlife" | "intruder";

/**
 * Ô nào thuộc vai nào, viết theo KHOẢNG cho gọn và cho đọc lại được.
 *
 * `creatures.png` xếp khá gọn theo chủ đề — sáu hàng đầu gần như toàn sinh vật
 * huyền thoại, sáu hàng cuối gần như toàn thú thật — nên khoảng là cách viết
 * trung thực nhất với tấm ghép. Những ô lệch khỏi chủ đề của hàng mình được
 * liệt kê riêng ở `EXCEPTIONS`, và **ngoại lệ thắng khoảng**.
 *
 * Hàng 0–5 (ô 0–59): xác sống, bộ xương, ma cà rồng, đầu lâu lửa, thần chết,
 * mắt bay, medusa, yêu tinh, chằn tinh, hiệp sĩ, pháp sư, quái đầu bò, người
 * thằn lằn, tiên cá, thiên thần, quỷ, rồng, người cây, người tuyết, tinh linh
 * bốn nguyên tố, ngựa một sừng.
 *
 * Hàng 6–11 (ô 60–119): cá, thầy tu áo choàng, sên nhớt vàng/xám, gấu, sói,
 * vua yêu tinh, phù thuỷ, tiểu quỷ, lạc đà, xác ướp, thần đèn, người cây, cú.
 *
 * Hàng 12–17 (ô 120–179): dơi, cú, chim ưng, côn trùng, ếch, rùa, vịt, dê, cừu,
 * đà điểu, sư tử, hổ, voi, hươu cao cổ, hươu, gấu, khỉ đột, mèo, cá heo, cá
 * mập, sóc, rái cá, thỏ, gấu mèo, chồn hôi.
 */
const RANGES: ReadonlyArray<{ from: number; to: number; role: CreatureRole }> = [
  // Sáu hàng đầu: gần như toàn sinh vật huyền thoại, và phần lớn là thù địch.
  { from: 0, to: 59, role: "intruder" },
  // Hai hàng cá và mấy hàng thú lớn xen quái — xem `EXCEPTIONS`.
  { from: 60, to: 119, role: "intruder" },
  // Sáu hàng cuối: thú thật. Mười hai con nuôi được đều nằm trong khoảng này.
  { from: 120, to: 179, role: "wildlife" },
];

/**
 * Những ô lệch khỏi chủ đề của hàng mình. **Ngoại lệ thắng khoảng.**
 *
 * Đây là chỗ dễ sai nhất trong cả tệp, nên nó được viết thành từng dòng có tên
 * chứ không phải một dãy số: một ô xếp nhầm vai nghĩa là con thú đi tới bắt
 * chuyện với một con quái, hoặc người chơi bị hỏi câu tiếng Anh vì một con thỏ.
 */
const EXCEPTIONS: ReadonlyArray<{ tile: number; role: CreatureRole; what: string }> = [
  // --- hàng 0–5: những con KHÔNG thù địch nằm lẫn trong đám quái ---
  { tile: 9, role: "npc", what: "người lùn mũ xanh" },
  { tile: 12, role: "npc", what: "tiên có cánh" },
  { tile: 19, role: "npc", what: "pháp sư râu bạc" },
  { tile: 27, role: "npc", what: "tiên cá" },
  { tile: 35, role: "npc", what: "thiên thần" },
  { tile: 36, role: "npc", what: "thiên thần nhỏ" },
  { tile: 37, role: "npc", what: "thiên thần áo trắng" },
  { tile: 50, role: "wildlife", what: "ngựa nâu" },
  { tile: 51, role: "wildlife", what: "ngựa một sừng trắng" },
  { tile: 52, role: "wildlife", what: "ngựa trắng" },

  // --- hàng 6–11: cá và mấy con hiền nằm lẫn trong đám quái ---
  { tile: 60, role: "wildlife", what: "cá xanh" },
  { tile: 61, role: "wildlife", what: "cá hồng" },
  { tile: 62, role: "wildlife", what: "cá xám" },
  { tile: 63, role: "wildlife", what: "cá nâu" },
  { tile: 64, role: "wildlife", what: "cá cam" },
  { tile: 70, role: "wildlife", what: "cá xanh (hàng hai)" },
  { tile: 71, role: "wildlife", what: "cá hồng (hàng hai)" },
  { tile: 72, role: "wildlife", what: "cá xám (hàng hai)" },
  { tile: 73, role: "wildlife", what: "cá nâu (hàng hai)" },
  { tile: 74, role: "wildlife", what: "cá cam (hàng hai)" },
  { tile: 92, role: "wildlife", what: "gấu con" },
  { tile: 100, role: "npc", what: "phù thuỷ mũ xanh" },
  { tile: 101, role: "wildlife", what: "gấu nâu" },
  { tile: 103, role: "wildlife", what: "gà trống" },
  { tile: 106, role: "wildlife", what: "lạc đà" },
  { tile: 109, role: "npc", what: "thần đèn" },
  { tile: 117, role: "pet", what: "cú — loài nuôi được" },

  // --- hàng 12–17: quái nằm lẫn trong đám thú thật ---
  { tile: 120, role: "intruder", what: "mắt bay" },
  { tile: 121, role: "intruder", what: "cây ăn thịt sẫm" },
  { tile: 122, role: "intruder", what: "cây ăn thịt" },
  { tile: 123, role: "intruder", what: "tiểu quỷ đỏ" },
  { tile: 124, role: "intruder", what: "yêu tinh cầm khiên" },
  { tile: 128, role: "intruder", what: "hiệp sĩ giáp xám" },
];

/**
 * Bốn mươi loài nuôi được, theo đúng bộ mặc định của `pet_species`.
 *
 * Chép lại ở đây KHÔNG phải để tra khi vẽ — bảng trong database mới là nguồn sự
 * thật, và ô của một loài admin đổi được. Chép để `roleOf` không bao giờ gọi một
 * con thú cưng là kẻ xâm nhập, và để một lần đọc tệp này thấy ngay ô nào đã có
 * chủ.
 *
 * Sáu ô cuối là hạng **huyền thoại**, và chúng nằm trong khoảng "sinh vật huyền
 * thoại" ở trên: kỳ lân, thiên mã, hai con rồng, tiên và thần đèn. `roleOf` xét
 * bảng này TRƯỚC mọi thứ khác, nên chúng thôi là kẻ xâm nhập kể từ ngày trở
 * thành thú nuôi — một con rồng vừa nở ra từ trứng thì không được phép quay lại
 * tấn công chủ nó.
 */
const PET_TILES: readonly number[] = [
  12, 30, 31, 33, 51, 92, 103, 109, 117, 129, 130, 134, 143, 145, 146, 147, 148, 149, 150, 151, 153,
  154, 155, 156, 157, 158, 159, 160, 161, 164, 165, 166, 168, 169, 170, 175, 176, 177, 178, 179,
];

/** Vai của một ô sinh vật. Ngoại lệ thắng khoảng; ô lạ coi như hoang dã. */
export function roleOf(tile: number): CreatureRole {
  if (PET_TILES.includes(tile)) return "pet";
  const exception = EXCEPTIONS.find((row) => row.tile === tile);
  if (exception) return exception.role;
  const range = RANGES.find((row) => tile >= row.from && tile <= row.to);
  // Ô ngoài tấm ghép hoặc chưa xếp: `wildlife` là mặc định AN TOÀN nhất — nó
  // không kéo theo hành vi nào. Mặc định `intruder` sẽ biến một ô đánh số nhầm
  // thành một trận đánh không ai hẹn.
  return range?.role ?? "wildlife";
}

/** Mọi ô thuộc một vai, theo thứ tự tăng dần. Dùng khi cần bốc ngẫu nhiên. */
export function tilesOf(role: CreatureRole): number[] {
  const all: number[] = [];
  for (let tile = 0; tile < 180; tile += 1) {
    if (roleOf(tile) === role) all.push(tile);
  }
  return all;
}

/**
 * Những ô SỐNG nằm trong hai tấm nền, tức là dân làng vẽ sẵn trên bản đồ.
 *
 * Khác `creatures.png` ở chỗ đây là ô của lớp `objects` trong `map.json`: bản đồ
 * đặt bác nông dân, con bò, con cừu, con gà ở đâu thì chúng ở đó. `petland-render`
 * đọc bảng này để tách chúng ra khỏi lớp tĩnh và cho chúng đi lại.
 *
 * Chỉ số đã đối chiếu bằng mắt với `farm.png` (12 cột): 108–109 là hai bác nông
 * dân, 120 cừu, 121 bò, 122 gà. 123 là bình sữa, KHÔNG phải vịt — đúng loại nhầm
 * khiến một cái bình đi dạo quanh chuồng.
 */
export const MAP_LIVING: Readonly<Record<string, ReadonlySet<number>>> = {
  farm: new Set([108, 109, 120, 121, 122]),
};

/** Ô nào trong tấm nền là NGƯỜI — tức là thứ bắt chuyện được, khác con vật. */
export const MAP_PEOPLE: Readonly<Record<string, ReadonlySet<number>>> = {
  farm: new Set([108, 109]),
};
