/**
 * Kiểm máy trạng thái đi lại của thú cưng — chạy bằng
 * `node --experimental-strip-types apps/web/scripts/check-petland-walk.mjs`.
 *
 * Nó ở đây, cạnh `check-petland-layers.mjs`, vì cùng một lý do: có những thứ
 * `tsc` và eslint không nhìn thấy được, và cách duy nhất còn lại là chạy thử.
 * Đi lại của con thú đã sinh ra BA lỗi liên tiếp mà mọi phép kiểm tự động đều
 * xanh — lệch một ô, giật mỗi ô, và bấm sang trái thì nhích sang phải — nên nó
 * được tách thành số học thuần để đo trực tiếp.
 *
 * Cả ba lỗi ấy đều đã được xem ĐỎ ở đây bằng cách gỡ đúng đoạn mã chúng canh.
 */

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const base = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "components");
const {
  restAt,
  atRest,
  advance,
  takeOver,
  conditionOf,
  tricksOf,
  wanderRange,
  STEP_SECONDS,
  WALK_TIRED_BELOW,
  HUNGRY_BELOW,
  CHEERFUL_ABOVE,
} = await import(join(base, "petland-pet.ts"));

/*
 * `dt` phải RUNG, không được là 1/60 tròn trịa.
 *
 * 1/60 chia đúng 18 khung cho một ô 0,3 giây, nên phần dư của `progress` luôn
 * bằng 0 — và bài kiểm chạy trong điều kiện đó sẽ không thấy gì khi ai đó vứt
 * phần dư đi. `requestAnimationFrame` thật không bao giờ đều như thế.
 */
let seed = 12345;
const jitter = () => {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return 1 / (45 + (seed % 2600) / 100); // ~45..71 fps
};

let bad = 0;
const fail = (msg) => {
  bad += 1;
  console.log("SAI:", msg);
};
const steerTo = (dx, dy) => (at) => ({ x: at.x + dx, y: at.y + dy });
const stand = () => null;

// --- 1. Đi liên tục: quãng đường phải khớp nhịp, phần dư không được vứt ----
{
  const w = restAt({ x: 5, y: 5 });
  let prev = w.tile.x,
    seconds = 0;
  while (seconds < 20) {
    const dt = jitter();
    seconds += dt;
    advance(w, dt, steerTo(1, 0));
    if (w.tile.x < prev) fail(`đi phải mà ô lùi: ${prev} -> ${w.tile.x}`);
    if (w.tile.y !== 5) fail(`đi phải mà đổi hàng: y = ${w.tile.y}`);
    prev = w.tile.x;
  }
  const tiles = w.tile.x - 5;
  const want = Math.round(seconds / STEP_SECONDS);
  if (Math.abs(tiles - want) > 1)
    fail(`${seconds.toFixed(1)}s ở nhịp ${STEP_SECONDS}s phải đi ~${want} ô, đi được ${tiles}`);
  else
    console.log(
      `đi liên tục ${seconds.toFixed(1)}s: ${tiles} ô (mong ~${want}) — phần dư không bị vứt`,
    );
}

// --- 2. Thả phím: đứng ĐÚNG ô, `from` trùng `tile` ------------------------
{
  const w = restAt({ x: 5, y: 5 });
  for (let i = 0; i < 40; i += 1) advance(w, jitter(), steerTo(1, 0));
  const mid = { ...w.tile };
  for (let i = 0; i < 40; i += 1) advance(w, jitter(), stand);
  if (!atRest(w)) fail("thả phím rồi mà `from` vẫn khác `tile`");
  if (w.progress !== 0) fail(`đứng yên mà progress = ${w.progress}`);
  if (w.tile.x < mid.x) fail("dừng lại rồi mà ô lùi về sau");
  console.log(`thả phím: đứng ở (${w.tile.x},${w.tile.y}), from trùng tile, progress = 0`);
}

// --- 3. Đổi hướng giữa lúc đang đi: không bao giờ nhích thêm sang phải ----
{
  for (let at = 1; at <= 30; at += 1) {
    const w = restAt({ x: 8, y: 5 });
    for (let i = 0; i < 30 + at; i += 1) advance(w, jitter(), steerTo(1, 0));
    const peak = Math.max(w.from.x, w.tile.x);
    takeOver(w, steerTo(-1, 0));
    for (let i = 0; i < 200; i += 1) {
      advance(w, jitter(), steerTo(-1, 0));
      if (Math.max(w.from.x, w.tile.x) > peak) {
        fail(
          `đổi sang trái ở pha ${at} mà vẫn nhích sang phải: ${peak} -> ${Math.max(w.from.x, w.tile.x)}`,
        );
        break;
      }
    }
  }
  console.log("đổi hướng giữa lúc đang đi, 30 pha: không pha nào đi ngược");
}

// --- 4. Bấm phím GIỮA một tuyến do chuột nạp -----------------------------
{
  // Đây mới là chỗ hàng đợi thật sự có nhiều ô: `steer` cấp thẳng ô kế tiếp
  // khi giữ phím, còn tuyến chuột thì nằm nguyên trong hàng đợi.
  for (let at = 1; at <= 30; at += 1) {
    const w = restAt({ x: 4, y: 5 });
    w.queue = Array.from({ length: 8 }, (_, i) => ({ x: 5 + i, y: 5 }));
    for (let i = 0; i < at; i += 1) advance(w, jitter(), stand);
    const peak = Math.max(w.from.x, w.tile.x);
    takeOver(w, steerTo(-1, 0));
    if (w.queue.some((t) => t.x > peak)) {
      fail(`bấm sang trái ở pha ${at} mà tuyến chuột cũ vẫn còn ô bên phải trong hàng đợi`);
      continue;
    }
    for (let i = 0; i < 200; i += 1) {
      advance(w, jitter(), steerTo(-1, 0));
      if (Math.max(w.from.x, w.tile.x) > peak) {
        fail(`bấm sang trái ở pha ${at} mà vẫn đi tiếp tuyến cũ sang phải`);
        break;
      }
    }
  }
  console.log("giành quyền lái giữa một tuyến chuột, 30 pha: tuyến cũ bị bỏ ngay");
}

// --- 5. Gõ một nhát rồi nhả ngay: vẫn phải đi đúng một ô ------------------
{
  const w = restAt({ x: 5, y: 5 });
  takeOver(w, steerTo(0, -1)); // keydown
  for (let i = 0; i < 60; i += 1) advance(w, jitter(), stand); // đã nhả phím
  if (w.tile.y !== 4 || w.tile.x !== 5)
    fail(`gõ một nhát lên: mong (5,4), được (${w.tile.x},${w.tile.y})`);
  if (!atRest(w)) fail("gõ một nhát xong mà không về trạng thái đứng yên");
  console.log("gõ một nhát rồi nhả ngay: đi đúng một ô, rồi đứng");
}

// --- 6. Không có chỗ đi: đứng yên sạch sẽ --------------------------------
{
  const w = restAt({ x: 5, y: 5 });
  for (let i = 0; i < 120; i += 1) advance(w, jitter(), stand);
  if (w.tile.x !== 5 || w.tile.y !== 5) fail("không có chỗ đi mà vẫn dịch");
  if (!atRest(w) || w.progress !== 0) fail("không có chỗ đi mà không ở trạng thái đứng yên");
  console.log("đâm tường / không có chỗ đi: đứng yên sạch sẽ");
}

// --- 7. Đường đi VÒNG QUA ô có người đứng ---------------------------------
{
  const { readFileSync } = await import("node:fs");
  const { parseMap, findPath, isWalkable } = await import(join(base, "petland-map.ts"));
  const map = parseMap(
    JSON.parse(readFileSync(join(base, "..", "..", "public", "pet", "map.json"), "utf8")),
  );

  // Đứng ở đâu cũng vậy: đường tới đích không được đi qua ô đã có người.
  let checked = 0;
  for (let y = 0; y < map.h; y += 1) {
    for (let x = 0; x < map.w; x += 1) {
      if (!isWalkable(map, x, y)) continue;
      const goal = { x: 14, y: 4 };
      if (!isWalkable(map, goal.x, goal.y)) continue;
      const plain = findPath(map, { x, y }, goal);
      if (plain.length < 3) continue;
      // Chặn đúng ô giữa đường đi, rồi đòi đường mới phải tránh nó.
      const guest = plain[Math.floor(plain.length / 2)];
      const blocked = new Set([`${guest.x},${guest.y}`]);
      const around = findPath(map, { x, y }, goal, blocked);
      checked += 1;
      if (around.some((t) => t.x === guest.x && t.y === guest.y)) {
        fail(`đường từ (${x},${y}) vẫn xuyên qua ô có người ở (${guest.x},${guest.y})`);
      }
    }
  }
  console.log(`đường đi vòng qua khách: ${checked} tuyến, không tuyến nào xuyên qua`);
}

// --- 8. Tình trạng và phạm vi lang thang (ADR-013) ------------------------
{
  const at = (fullness, energy, mood) => conditionOf({ fullness, energy, mood });

  // Thứ tự ưu tiên là thứ tự CẤP BÁCH: kiệt sức trước đói, đói trước vui. Đảo
  // lại thì một con vừa kiệt vừa vui sẽ nhảy tại chỗ thay vì ngồi bệt xuống.
  // Ca quyết định: vừa đói VỪA kiệt sức. Thiếu nó thì đảo thứ tự hai nhánh đầu
  // không làm bài kiểm đỏ — mà đó chính là điều "thứ tự ưu tiên" nói.
  if (at(HUNGRY_BELOW - 0.01, WALK_TIRED_BELOW - 0.01, 0.9) !== "exhausted") {
    fail("vừa đói vừa kiệt sức thì phải là kiệt sức");
  }
  if (at(0.9, WALK_TIRED_BELOW - 0.01, 0.9) !== "exhausted") fail("kiệt sức phải thắng vui");
  if (at(HUNGRY_BELOW - 0.01, 0.9, 0.9) !== "hungry") fail("đói phải thắng vui");
  if (at(0.9, WALK_TIRED_BELOW - 0.01, 0.0) !== "exhausted") fail("dưới ngưỡng sức phải là kiệt");
  if (at(0.9, 0.9, CHEERFUL_ABOVE) !== "cheerful") fail("đúng ngưỡng vui phải là vui");
  if (at(0.9, 0.9, CHEERFUL_ABOVE - 0.01) !== "content")
    fail("dưới ngưỡng vui phải là bình thường");

  // Ngay TRÊN ngưỡng thì không còn là kiệt/đói — ranh giới phải đúng cả hai phía.
  if (at(0.9, WALK_TIRED_BELOW, 0.5) === "exhausted") fail("đúng ngưỡng sức không còn là kiệt");
  if (at(HUNGRY_BELOW, 0.9, 0.5) === "hungry") fail("đúng ngưỡng no không còn là đói");

  // Kiệt sức thì NGỒI IM, và càng khoẻ càng đi xa.
  if (wanderRange("exhausted") !== null) fail("kiệt sức mà vẫn tự đi");
  const near = wanderRange("hungry");
  const mid = wanderRange("content");
  const far = wanderRange("cheerful");
  if (!(near < mid && mid < far)) fail(`phạm vi phải tăng dần: ${near} / ${mid} / ${far}`);

  // Xin giảm chuyển động thì KHÔNG tự đi, dù tình trạng thế nào. Bài kiểm ảnh
  // chụp không với tới luật này: nó chỉ thấy hai khung hình liền nhau, còn
  // chuyến đi thì vài giây mới tới một lần.
  for (const c of ["exhausted", "hungry", "content", "cheerful"]) {
    if (wanderRange(c, true) !== null) fail(`giảm chuyển động mà ${c} vẫn tự đi`);
  }
  console.log(
    "tình trạng và phạm vi lang thang: ngưỡng, thứ tự ưu tiên và chốt giảm-chuyển-động đều đúng",
  );
}

// --- 9. Vốn tiết mục theo bậc hiếm (ADR-013 §5) ---------------------------
{
  const TIERS = ["common", "uncommon", "rare", "epic", "legendary", "god"];
  const sets = TIERS.map((t) => tricksOf(t));

  // CỘNG DỒN: bậc trên phải có tất cả những gì bậc dưới có. Không có luật này
  // thì "hiếm hơn" thôi là "khác đi", và hai con cạnh nhau không so được.
  for (let i = 1; i < sets.length; i += 1) {
    for (const trick of sets[i - 1]) {
      if (!sets[i].has(trick)) fail(`${TIERS[i]} thiếu "${trick}" mà ${TIERS[i - 1]} có`);
    }
    if (sets[i].size <= sets[i - 1].size) {
      fail(`${TIERS[i]} không thêm tiết mục nào so với ${TIERS[i - 1]}`);
    }
  }
  if (sets[0].size !== 0) fail("bậc thường phải là mốc không, không có tiết mục nào");

  // Bậc lạ hay thiếu bậc thì rơi về mốc không, không nổ và không tự cho tiết mục.
  for (const odd of [undefined, "", "mythic"]) {
    if (tricksOf(odd).size !== 0) fail(`bậc lạ ${JSON.stringify(odd)} phải rơi về mốc không`);
  }
  console.log(`tiết mục theo bậc: cộng dồn qua ${TIERS.length} bậc, bậc lạ rơi về mốc không`);
}

console.log(bad === 0 ? "\nTẤT CẢ ĐỀU ĐÚNG" : `\n${bad} chỗ SAI`);
process.exit(bad === 0 ? 0 : 1);
