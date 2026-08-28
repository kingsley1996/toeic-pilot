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
const { restAt, atRest, advance, takeOver, STEP_SECONDS } = await import(
  join(base, "petland-pet.ts")
);

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

console.log(bad === 0 ? "\nTẤT CẢ ĐỀU ĐÚNG" : `\n${bad} chỗ SAI`);
process.exit(bad === 0 ? 0 : 1);
