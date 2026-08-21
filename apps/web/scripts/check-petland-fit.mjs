/**
 * Kiểm bằng SỐ rằng con thú nằm trọn trong bức tranh ở MỌI điểm trên đường đi,
 * mọi khung hình, cả hai hướng, và ở đỉnh cú nhảy.
 *
 *   node scripts/check-petland-fit.mjs [--debug]
 *
 * `--debug` vẽ đường đi và hộp bao con thú lên một bản sao bức tranh
 * (`/tmp/petland-debug.png`) để nhìn tận mắt xem nó có đứng trên mặt đất không —
 * thứ mà con số không trả lời được: một đường đi lọt trong khung vẫn có thể đi
 * thẳng qua giữa lòng sông.
 *
 * Lý do có script này: lỗi hình học ở đây chỉ hiện ở MỘT khung hình của MỘT hoạt
 * ảnh ở MỘT quãng đường, và ba lần nhìn bằng mắt trước đó đều bỏ sót.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { bbox, decodePng, encodePng } from "./png.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
/* Không còn một thư mục cố định: mọi mascot trong sổ đăng ký đều phải lọt khung
   cảnh, không riêng con đang được đặt mặc định. Một con chỉ hỏng khi người dùng
   chọn nó là loại lỗi không ai gặp cho tới khi có người gặp. */
const sheetsOf = (id) => path.join(root, "public/mascots", id);

/** Đọc hằng số thẳng từ component, để hai bên không trôi khỏi nhau. */
function constant(file, name) {
  const src = fs.readFileSync(path.join(root, file), "utf8");
  const m = src.match(new RegExp(`^(?:export )?const ${name} = (-?\\d+(?:\\.\\d+)?)`, "m"));
  if (!m) throw new Error(`không đọc được hằng số ${name} trong ${file}`);
  return Number(m[1]);
}

/*
 * Số đo của mascot NHẬP thẳng từ mô-đun mô tả nó, không bóc bằng biểu thức chính
 * quy. Bản trước cào chúng ra khỏi `petland.tsx`, và khi chúng chuyển sang
 * `petland-sprite.ts` thì script này ném lỗi — mà chạy qua một đường ống thì mã
 * thoát bị nuốt, nên nó nhìn như vẫn đang kiểm trong lúc chẳng kiểm gì cả.
 */
const sprite = await import(path.join(root, "src/components/petland-sprite.ts"));
const JUMP_H = constant("src/components/petland.tsx", "JUMP_H");
const WORLD_W = constant("src/components/petland-scene.ts", "WORLD_W");
const WORLD_H = constant("src/components/petland-scene.ts", "WORLD_H");

/* Đường đi được đọc từ chính module dữ liệu — chép lại vào đây là tạo ra một
   bản thứ hai sẽ lệch đi mà không ai báo. */
const scene = await import(path.join(root, "src/components/petland-scene.ts")).catch(async () => {
  // Node không chạy được TypeScript trực tiếp ở mọi phiên bản: rút mảng PATH
  // ra bằng cách đọc file. Chỉ số nguyên và số thực, không có biểu thức.
  const src = fs.readFileSync(path.join(root, "src/components/petland-scene.ts"), "utf8");
  const body = src.match(/export const PATH: Anchor\[\] = \[([\s\S]*?)\n\];/)[1];
  const PATH = [
    ...body.matchAll(/\{\s*x:\s*(-?[\d.]+),\s*y:\s*(-?[\d.]+),\s*scale:\s*([\d.]+)/g),
  ].map((m) => ({ x: Number(m[1]), y: Number(m[2]), scale: Number(m[3]) }));
  return { PATH };
});
const PATH = scene.PATH;
if (!PATH || PATH.length < 2) throw new Error("không đọc được PATH");

/** Hộp bao từng khung hình của một dải, cho một mascot cụ thể. */
function frameBoxes(dir, cellW, cellH, clip, count) {
  const img = decodePng(fs.readFileSync(path.join(dir, `${clip}.png`)));
  const out = [];
  for (let k = 0; k < count; k += 1) {
    const cell = { width: cellW, height: cellH, data: Buffer.alloc(cellW * cellH * 4) };
    for (let y = 0; y < cellH; y += 1) {
      img.data.copy(
        cell.data,
        y * cellW * 4,
        (y * img.width + k * cellW) * 4,
        (y * img.width + k * cellW + cellW) * 4,
      );
    }
    out.push(bbox(cell));
  }
  return out;
}

/** Nội suy như `pointAt`, nhưng lấy mẫu dày để không bỏ sót đoạn giữa. */
function samples(n) {
  const segs = PATH.slice(1).map((p, i) => Math.hypot(p.x - PATH[i].x, p.y - PATH[i].y));
  const total = segs.reduce((a, b) => a + b, 0);
  const out = [];
  for (let s = 0; s <= n; s += 1) {
    let left = (total * s) / n;
    let i = 0;
    while (i < segs.length - 1 && left > segs[i]) {
      left -= segs[i];
      i += 1;
    }
    const t = segs[i] === 0 ? 0 : Math.min(1, left / segs[i]);
    const a = PATH[i];
    const b = PATH[i + 1];
    out.push({
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
      scale: a.scale + (b.scale - a.scale) * t,
    });
  }
  return out;
}

let bad = 0;
const note = (msg) => {
  console.error(`✗ ${msg}`);
  bad += 1;
};

const pts = samples(240);
console.log(
  `đường đi ${PATH.length} điểm neo · lấy ${pts.length} mẫu · ` +
    `cỡ ${Math.min(...PATH.map((p) => p.scale))}–${Math.max(...PATH.map((p) => p.scale))}`,
);

for (const [id, mascot] of Object.entries(sprite.MASCOTS)) {
  const SHEETS = sheetsOf(id);
  const CELL_W = mascot.cell.w;
  const CELL_H = mascot.cell.h;
  const FOOT_Y = mascot.footY;
  const ANCHOR_X = mascot.anchorX;

  const meta = JSON.parse(fs.readFileSync(path.join(SHEETS, "atlas.json"), "utf8"));
  if (meta.cell.w !== CELL_W || meta.cell.h !== CELL_H) {
    note(`${id}: ô của atlas ${meta.cell.w}x${meta.cell.h} khác sổ đăng ký ${CELL_W}x${CELL_H}`);
    continue;
  }
  console.log(
    `\n— ${id} (${mascot.label}) · ô ${CELL_W}x${CELL_H} · FOOT_Y ${FOOT_Y} · ANCHOR_X ${ANCHOR_X}`,
  );

  for (const [clip, count] of Object.entries(meta.clips)) {
    const boxes = frameBoxes(SHEETS, CELL_W, CELL_H, clip, count);
    const lift = clip === "jump" ? JUMP_H : 0;
    let worst = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity };
    for (const p of pts) {
      for (const b of boxes) {
        // Quay phải, và quay trái (lật quanh ANCHOR_X). Tư thế nằm không bao giờ
        // quay trái — `toggleSleep` và nhánh tự ngủ đều ép `dir = 1`.
        const spans = [[b.x0, b.x1]];
        if (clip !== "sleep") spans.push([2 * ANCHOR_X - b.x1, 2 * ANCHOR_X - b.x0]);
        for (const [lo, hi] of spans) {
          worst.left = Math.min(worst.left, p.x + (lo - ANCHOR_X) * p.scale);
          worst.right = Math.max(worst.right, p.x + (hi - ANCHOR_X) * p.scale);
        }
        worst.top = Math.min(worst.top, p.y + (b.y0 - FOOT_Y) * p.scale - lift * p.scale);
        worst.bottom = Math.max(worst.bottom, p.y + (b.y1 - FOOT_Y) * p.scale);
      }
    }
    if (worst.left < 0) note(`${id}/${clip}: tràn mép trái ${Math.round(-worst.left)}px`);
    if (worst.right > WORLD_W)
      note(`${id}/${clip}: tràn mép phải ${Math.round(worst.right - WORLD_W)}px`);
    if (worst.top < 0) note(`${id}/${clip}: vượt mép trên ${Math.round(-worst.top)}px`);
    if (worst.bottom > WORLD_H)
      note(`${id}/${clip}: thò khỏi mép dưới ${Math.round(worst.bottom - WORLD_H)}px`);
    console.log(
      `${clip.padEnd(6)} ${String(count).padStart(2)} khung  ` +
        `x ${Math.round(worst.left)}..${Math.round(worst.right)}/${WORLD_W}  ` +
        `y ${Math.round(worst.top)}..${Math.round(worst.bottom)}/${WORLD_H}`,
    );
  }

  /* Tư thế ĐỨNG là tư thế duy nhất buộc phải có bàn chân trùng nhau tuyệt đối. */
  const idleFeet = new Set(
    frameBoxes(SHEETS, CELL_W, CELL_H, "idle", meta.clips.idle).map((b) => b.y1),
  );
  if (idleFeet.size !== 1) {
    note(`${id}: đứng yên mà bàn chân ở ${idleFeet.size} hàng khác nhau: ${[...idleFeet]}`);
  } else if ([...idleFeet][0] !== FOOT_Y - 1) {
    // FOOT_Y là hàng MẶT ĐẤT, nên pixel cuối của con thú phải ở FOOT_Y - 1.
    note(`${id}: FOOT_Y=${FOOT_Y} nhưng pixel cuối ở hàng ${[...idleFeet][0]}, cần ${FOOT_Y - 1}`);
  }
}

/*
 * Các vùng của lớp hạt phải nằm trên ĐÚNG chất liệu, và đây là phép kiểm bằng
 * số cho việc đó — nhìn bằng mắt vào một ô 400px trên bức tranh 1376px thì không
 * phân biệt được mép vũng nước với bãi cỏ sát nó, và tôi đã đoán sai hai lần.
 *
 * Ngưỡng lấy từ chính bức tranh: cỏ thì xanh lá (g trội), nước thì hoặc xanh lơ
 * (b >= g) hoặc rất sáng — vũng nước trong tranh đầy vệt phản chiếu màu cam của
 * đống lửa, nên "nước thì xanh" là một luật sai ở đúng chỗ nó cần đúng nhất.
 */
{
  const bg = decodePng(fs.readFileSync(path.join(root, "assets/landscape/petland-2.png")));
  const at = (x, y) => {
    const i = (Math.round(y) * bg.width + Math.round(x)) * 4;
    return [bg.data[i], bg.data[i + 1], bg.data[i + 2]];
  };
  const fraction = (r, ok) => {
    let hit = 0;
    let n = 0;
    for (let y = r.y; y < r.y + r.h; y += 2) {
      for (let x = r.x; x < r.x + r.w; x += 2) {
        n += 1;
        if (ok(at(x, y))) hit += 1;
      }
    }
    return hit / n;
  };
  const isSky = ([r, g, b]) => b > r + 14 && b > g + 8 && (r + g + b) / 3 < 125;
  /*
   * "Là nước" ở đây được định nghĩa NGƯỢC: không phải xanh-lá-trội.
   *
   * Luật thuận — "nước thì xanh lơ" — sai ở đúng chỗ nó cần đúng nhất: vũng nước
   * trong tranh gần nửa là vệt phản chiếu màu cam của đống lửa, nên một ô nằm
   * trọn trong lòng nước cũng chỉ đạt ~65%. Thứ duy nhất tiếp giáp nước là CỎ, và
   * cỏ thì xanh lá trội, nên đo cái đó tách sạch: cỏ 61–65%, nước 98–99%.
   *
   * Giới hạn đã biết: nó không phân biệt được nước với GỖ, nên một ô đè lên cột
   * cầu vẫn lọt. Đó là việc của ảnh gỡ lỗi.
   */
  const isWater = ([r, g, b]) => !(g > r + 6 && g > b + 6);
  const check = (label, rects, ok, floor) => {
    rects.forEach((r, i) => {
      const f = fraction(r, ok);
      const line = `${label}[${i}] ${r.x},${r.y} ${r.w}x${r.h} → ${(f * 100).toFixed(0)}% đúng chất liệu`;
      if (f < floor) note(`${line} (cần ≥ ${floor * 100}%)`);
      else console.log(`  ${line}`);
    });
  };
  console.log("\nvùng của lớp hạt:");
  check("trời ", scene.SKY ?? [], isSky, 0.95);
  check("nước ", scene.WATER ?? [], isWater, 0.9);
}

/*
 * Không nét vẽ nào của mặt nước được rơi ra ngoài mặt nước.
 *
 * Việc nhốt hiệu ứng vào các ô chỉ có nghĩa nếu hạt Ở LẠI trong ô, mà vệt sáng
 * thì TRÔI: ở tốc độ hiện tại một vệt đi gần 60px trong đời nó, thừa sức ra khỏi
 * ô và nằm lấp lánh trên bãi cỏ. Đã xảy ra thật, và ảnh chụp chỉ cho thấy nó sau
 * khi phóng to đúng góc — nên phép kiểm này chạy thẳng lớp hạt và đọc từng nét.
 *
 * `ctx` giả ở đây nhỏ đúng bằng phần `petland-fx` dùng tới. Không phải một bản
 * mô phỏng canvas — nó chỉ ghi lại các nét, và nếu module dùng thêm API mới thì
 * nó ném lỗi ngay chứ không âm thầm bỏ qua.
 */
{
  /* `petland-fx.ts` nhập qua alias `@/` của bundler, thứ Node không phân giải
     được. Chép ra một bản tạm đã đổi alias thành đường dẫn tương đối rồi nạp —
     rẻ hơn nhiều so với dựng cả một hook phân giải module chỉ để chạy một file. */
  const fxSrc = fs
    .readFileSync(path.join(root, "src/components/petland-fx.ts"), "utf8")
    // Node ESM đòi ĐUÔI file trong đường dẫn tương đối; bundler thì không, nên
    // phải thêm vào chứ không chỉ đổi tiền tố.
    .replace(/"@\/components\/([\w-]+)"/g, '"./$1.ts"');
  const tmp = path.join(root, "src/components/.petland-fx.check.ts");
  fs.writeFileSync(tmp, fxSrc);
  let createFx;
  try {
    ({ createFx } = await import(`${tmp}?v=${Date.now()}`));
  } finally {
    fs.unlinkSync(tmp);
  }
  const rects = [];
  const ellipses = [];
  const stub = {
    canvas: { width: WORLD_W, height: WORLD_H },
    globalAlpha: 1,
    globalCompositeOperation: "source-over",
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    clearRect() {},
    beginPath() {},
    arc() {},
    fill() {},
    stroke() {},
    fillRect(x, y, w, h) {
      // Vầng sáng đống lửa cũng dùng `fillRect`, nhưng với một gradient chứ không
      // với một chuỗi màu — đó là thứ phân biệt được hai bên.
      if (typeof this.fillStyle === "string") rects.push({ x, y, w, h });
    },
    ellipse(x, y, rx, ry) {
      ellipses.push({ x, y, rx, ry });
    },
    createRadialGradient() {
      return { addColorStop() {} };
    },
  };

  const fx = createFx();
  let clock = 0;
  for (let i = 0; i < 1800; i += 1) {
    clock += 1000 / 60;
    fx.draw(clock, 1 / 60, stub);
  }

  const inside = (x, y) =>
    (scene.WATER ?? []).some(
      (r) => x >= r.x - 0.5 && x <= r.x + r.w + 0.5 && y >= r.y - 0.5 && y <= r.y + r.h + 0.5,
    );
  const strayRect = rects.find((r) => !inside(r.x, r.y) || !inside(r.x + r.w, r.y + r.h));
  const strayEllipse = ellipses.find(
    (e) => !inside(e.x - e.rx, e.y - e.ry) || !inside(e.x + e.rx, e.y + e.ry),
  );
  if (strayRect) note(`vệt nước vẽ ngoài mặt nước: ${JSON.stringify(strayRect)}`);
  if (strayEllipse) note(`gợn sóng vẽ ngoài mặt nước: ${JSON.stringify(strayEllipse)}`);
  if (!strayRect && !strayEllipse) {
    console.log(
      `\nlớp hạt: ${rects.length} vệt + ${ellipses.length} gợn sóng qua 30 giây mô phỏng, ` +
        "không nét nào ra khỏi mặt nước",
    );
  }
}

if (process.argv.includes("--debug")) {
  const scenePath = path.join(root, "assets/landscape/petland-2.png");
  const img = decodePng(fs.readFileSync(scenePath));
  const set = (x, y, c) => {
    x = Math.round(x);
    y = Math.round(y);
    if (x < 0 || y < 0 || x >= img.width || y >= img.height) return;
    const i = (y * img.width + x) * 4;
    img.data[i] = c[0];
    img.data[i + 1] = c[1];
    img.data[i + 2] = c[2];
  };
  const idle = frameBoxes("idle", meta.clips.idle)[0];
  for (const p of pts) {
    for (let dy = -2; dy <= 2; dy += 1) set(p.x, p.y + dy, [255, 40, 40]);
  }
  for (const p of PATH) {
    // Hộp bao con thú ở từng điểm neo: nhìn được ngay nó đứng trên cái gì.
    const l = p.x + (idle.x0 - ANCHOR_X) * p.scale;
    const r = p.x + (idle.x1 - ANCHOR_X) * p.scale;
    const t = p.y + (idle.y0 - FOOT_Y) * p.scale;
    for (let x = l; x <= r; x += 1) {
      set(x, t, [80, 255, 120]);
      set(x, p.y, [80, 255, 120]);
    }
    for (let y = t; y <= p.y; y += 1) {
      set(l, y, [80, 255, 120]);
      set(r, y, [80, 255, 120]);
    }
  }
  /* Vùng của lớp hạt. Đây là nửa quan trọng hơn của ảnh gỡ lỗi: con số chỉ nói
     được vùng có nằm trong bức tranh không, không nói được nó có nằm trên MẶT
     NƯỚC không — và một vệt lấp lánh trên bãi cỏ thì nhìn là thấy ngay. */
  const box = (r, c) => {
    for (let x = r.x; x <= r.x + r.w; x += 1) {
      set(x, r.y, c);
      set(x, r.y + r.h, c);
    }
    for (let y = r.y; y <= r.y + r.h; y += 1) {
      set(r.x, y, c);
      set(r.x + r.w, y, c);
    }
  };
  for (const r of scene.SKY ?? []) box(r, [120, 190, 255]);
  for (const r of scene.WATER ?? []) box(r, [60, 240, 255]);
  for (const r of scene.GLOW_ZONES ?? []) box(r, [255, 230, 90]);
  if (scene.FIRE) {
    for (let a = 0; a < 360; a += 2) {
      const rad = (a * Math.PI) / 180;
      set(scene.FIRE.x + Math.cos(rad) * 14, scene.FIRE.y + Math.sin(rad) * 14, [255, 120, 40]);
    }
  }

  fs.writeFileSync("/tmp/petland-debug.png", encodePng(img));
  console.log(
    "\nđã vẽ /tmp/petland-debug.png — đường đi đỏ, hộp con thú xanh lá,\n" +
      "  trời xanh nhạt, nước xanh lơ, vùng đom đóm vàng, đống lửa cam",
  );
}

if (bad > 0) process.exit(1);
console.log("\n✓ con thú nằm trọn trong bức tranh ở mọi điểm trên đường đi");
