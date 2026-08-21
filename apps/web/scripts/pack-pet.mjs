/**
 * Gộp các khung hình rời của mascot thành strip ngang cho `components/petland.tsx`.
 *
 *   node scripts/pack-pet.mjs --measure     # chỉ đo, không ghi
 *   node scripts/pack-pet.mjs
 *
 * Hai luật dưới đây kế thừa từ bộ đóng gói đầu tiên (dành cho một bộ sprite mua
 * sẵn, không nằm trong kho này), vì cả hai vẫn hỏng im lặng y hệt:
 *
 * 1. **Một khung cắt duy nhất cho MỌI frame của MỌI hoạt ảnh.** Trim theo hộp bao
 *    của TỪNG frame thì mỗi frame ra một cỡ khác nhau, và khi ép vào một ô chung,
 *    con thú phình to thu nhỏ theo từng khung hình — đúng lỗi "nhảy lên thì pet
 *    nhỏ đi" ghi ở ROADMAP §4m.
 * 2. **Thu nhỏ bằng trung bình vùng trên alpha nhân sẵn.** Không nhân alpha trước
 *    thì màu của các pixel trong suốt bị kéo vào rìa, tạo viền tối chỉ thấy khi
 *    đặt lên nền sáng.
 *
 * Khác bản cũ ở một chỗ đáng nói. Bộ dino mua sẵn đã được HOẠ SĨ căn trên cùng
 * một canvas, nên khung cắt chung chỉ việc giữ lại thứ có sẵn. Bộ này không có
 * sẵn gì cả: căn chỉnh đến từ anchor sheet lúc sinh, rồi `generate2dsprite.py
 * process --align feet --scale-strategy preserve` chốt lại. Nên script này ĐO và
 * IN RA độ lệch đường chân giữa các clip — nếu khâu trên trượt thì đây là chỗ duy
 * nhất phát hiện được trước khi nó thành một con thú giật lên mỗi lần đổi hoạt
 * ảnh. Lệch 8px không sai ở bất kỳ phép kiểm nào khác: từng hoạt ảnh vẫn tự nhất
 * quán, chỉ lúc CHUYỂN giữa chúng mới lộ.
 *
 * `FOOT_Y` và `ANCHOR_X` cũng do script này đo và in ra để chép vào
 * `petland-sprite.ts`. Không đoán bằng mắt: `check-petland-fit.mjs` kiểm hai số
 * đó, và sai vài pixel làm con thú lơ lửng hoặc lún xuống đất.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { bbox, decodePng, encodePng } from "./png.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/*
 * Khung gốc nằm NGOÀI `public/`: không trang nào tham chiếu chúng, nên để trong
 * thư mục tĩnh là bắt Next phục vụ ra ngoài một bản sao vô dụng. Chúng vẫn trong
 * kho vì thiếu chúng thì các strip thành thứ không tái tạo được — đúng khuyết
 * điểm MEDIA-PIPELINE §10.3.
 */
const petArg = process.argv.indexOf("--pet");
const PET = petArg >= 0 ? process.argv[petArg + 1] : "cat";
const SRC = path.join(root, `assets/mascots/${PET}`);
const OUT = path.join(root, `public/mascots/${PET}`);

/** Chiều cao ô đích. Chiều rộng suy ra từ hộp bao chung để không méo hình. */
const TARGET_H = 117;

/*
 * Thứ tự chuẩn, nhưng chỉ lấy những clip THỰC SỰ có thư mục. `petland-sprite.ts`
 * nói rõ một mascot có thể "thiếu hẳn một hoạt ảnh" và chỉ cần viết lại bảng ánh
 * xạ ý định — nên bộ đóng gói không được đòi đủ năm.
 */
const CLIP_ORDER = ["idle", "walk", "run", "jump", "sleep"];
const CLIPS = CLIP_ORDER.filter((c) => fs.existsSync(path.join(SRC, c)));

function framesOf(clip) {
  const dir = path.join(SRC, clip);
  if (!fs.existsSync(dir)) throw new Error(`thiếu thư mục khung hình: ${dir}`);
  const files = fs
    .readdirSync(dir)
    .filter((f) => /^\d+\.png$/.test(f))
    .sort((a, b) => Number.parseInt(a, 10) - Number.parseInt(b, 10));
  if (files.length === 0) throw new Error(`không có khung hình nào trong ${dir}`);
  return files.map((f) => path.join(dir, f));
}

/** Trung bình vùng trên alpha nhân sẵn, từ một hình chữ nhật của ảnh nguồn. */
function downscaleCrop(img, crop, outW, outH) {
  const out = Buffer.alloc(outW * outH * 4);
  for (let y = 0; y < outH; y += 1) {
    for (let x = 0; x < outW; x += 1) {
      /*
       * Biên nguồn tính bằng số thực rồi làm tròn. Khung cắt chung hiếm khi chia
       * hết cho cỡ đích, và ép nó chia hết sẽ cắt mất vài pixel ở một cạnh — tức
       * là dịch đường chân đi đúng từng đó, thứ `check-petland-fit.mjs` sẽ báo
       * mà không nói được nguyên nhân nằm ở đây.
       */
      const sx0 = crop.x + Math.floor((x * crop.w) / outW);
      const sx1 = crop.x + Math.max(sx0 - crop.x + 1, Math.floor(((x + 1) * crop.w) / outW));
      const sy0 = crop.y + Math.floor((y * crop.h) / outH);
      const sy1 = crop.y + Math.max(sy0 - crop.y + 1, Math.floor(((y + 1) * crop.h) / outH));
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      let n = 0;
      for (let sy = sy0; sy < sy1; sy += 1) {
        for (let sx = sx0; sx < sx1; sx += 1) {
          const i = (sy * img.width + sx) * 4;
          const sa = img.data[i + 3];
          r += img.data[i] * sa;
          g += img.data[i + 1] * sa;
          b += img.data[i + 2] * sa;
          a += sa;
          n += 1;
        }
      }
      const o = (y * outW + x) * 4;
      out[o + 3] = Math.round(a / n);
      if (a > 0) {
        out[o] = Math.round(r / a);
        out[o + 1] = Math.round(g / a);
        out[o + 2] = Math.round(b / a);
      }
    }
  }
  return { width: outW, height: outH, data: out };
}

function main() {
  const loaded = {};
  for (const clip of CLIPS) {
    loaded[clip] = framesOf(clip).map((f) => decodePng(fs.readFileSync(f)));
  }

  // Hộp bao chung của TẤT CẢ khung hình của TẤT CẢ clip.
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -1;
  let y1 = -1;
  for (const clip of CLIPS) {
    for (const img of loaded[clip]) {
      const b = bbox(img);
      x0 = Math.min(x0, b.x0);
      y0 = Math.min(y0, b.y0);
      x1 = Math.max(x1, b.x1);
      y1 = Math.max(y1, b.y1);
    }
  }
  const crop = { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
  console.log(`hộp bao chung: x ${x0}..${x1} y ${y0}..${y1} (${crop.w}x${crop.h})`);

  const feet = {};
  for (const clip of CLIPS) feet[clip] = Math.max(...loaded[clip].map((img) => bbox(img).y1));
  const feetVals = Object.values(feet);
  const spreadSrc = Math.max(...feetVals) - Math.min(...feetVals);
  for (const clip of CLIPS) console.log(`  đáy ${clip.padEnd(6)} y=${feet[clip]}`);

  const cellH = TARGET_H;
  const cellW = Math.round((crop.w / crop.h) * cellH);
  const scale = crop.h / cellH;

  /*
   * Ngưỡng đo bằng pixel của Ô ĐÍCH, không phải pixel nguồn. Bản đầu đo bằng
   * pixel nguồn và vì thế phụ thuộc vào việc ảnh gốc to hay nhỏ: cùng một sai
   * lệch NHÌN THẤY được lại đạt ở bộ này và trượt ở bộ kia chỉ vì hộp bao khác
   * cỡ. 7px nguồn của một bộ là 2.7px thật, 18px nguồn của bộ khác là 6.3px.
   */
  const spread = spreadSrc / scale;
  console.log(
    `  lệch đường chân giữa các clip: ${spreadSrc}px nguồn = ${spread.toFixed(1)}px trên ô ${cellH}`,
  );
  if (spread > 4) {
    console.error(
      `⚠ lệch ${spread.toFixed(1)}px là dấu hiệu sinh ảnh chưa đều — đã tự căn lại khi đóng gói,\n` +
        `  nhưng nếu vượt xa thì nên sinh lại clip lệch nhất thay vì dựa vào việc căn.`,
    );
  }

  /*
   * Căn đường chân GIỮA các clip bằng cách dịch cửa sổ cắt của từng clip.
   *
   * Đây là phần mở rộng của đúng thao tác `--align feet` đã làm trong một clip,
   * và nó đúng vì điểm thấp nhất của cả năm clip đều LÀ mặt đất — kể cả tư thế
   * nằm ngủ. Nó chỉ sửa vị trí dọc; sai lệch TỈ LỆ không được sửa ở đây và vẫn
   * do `body_scale_cv` bắt, nên một clip sinh hỏng vẫn không lọt qua im lặng.
   *
   * Mốc là clip có bàn chân THẤP nhất, để mọi dịch chuyển đều đi lên và cửa sổ
   * cắt không bao giờ tụt ra ngoài đáy ảnh.
   */
  const feetRef = Math.max(...feetVals);
  const cropOf = (clip) => {
    const y = crop.y + feet[clip] - feetRef;
    if (y < 0) throw new Error(`căn đường chân đẩy cửa sổ cắt của ${clip} ra ngoài ảnh`);
    return { ...crop, y };
  };

  if (process.argv.includes("--measure")) {
    console.log(`\nô đề nghị: ${cellW}x${cellH}  (FOOT_Y đo sau khi đóng gói)`);
    return;
  }

  fs.mkdirSync(OUT, { recursive: true });
  const meta = { cell: { w: cellW, h: cellH }, clips: {} };
  let anchorX = 0;
  /*
   * Đường chân đo trên ô ĐÃ ĐÓNG GÓI, không suy từ ảnh nguồn: phép thu nhỏ làm
   * tròn, nên một con số suy ra trước khi thu nhỏ lệch được một pixel so với thứ
   * thật sự nằm trong tệp — và `check-petland-fit.mjs` so khớp tuyệt đối.
   */
  const idleFeetRows = new Set();

  for (const clip of CLIPS) {
    const frames = loaded[clip];
    const sheet = {
      width: cellW * frames.length,
      height: cellH,
      data: Buffer.alloc(cellW * frames.length * cellH * 4),
    };
    frames.forEach((img, k) => {
      const small = downscaleCrop(img, cropOf(clip), cellW, cellH);
      if (clip === "idle") idleFeetRows.add(bbox(small).y1);
      if (clip === "idle" && k === 0) {
        /*
         * Tâm ngang của tư thế ĐỨNG, cũng là điểm `scaleX(-1)` lật quanh. Lấy từ
         * khung idle đầu tiên chứ không phải tâm ô: ô rộng hơn con thú đứng, nên
         * lật quanh tâm ô đẩy nó ngang cả chục pixel — đúng lý do hằng số này tồn
         * tại riêng thay vì được suy ra từ `CELL.w / 2`.
         */
        const b = bbox(small);
        anchorX = Math.round((b.x0 + b.x1) / 2);
      }
      for (let y = 0; y < cellH; y += 1) {
        small.data.copy(
          sheet.data,
          (y * sheet.width + k * cellW) * 4,
          y * cellW * 4,
          (y + 1) * cellW * 4,
        );
      }
    });
    const file = path.join(OUT, `${clip}.png`);
    fs.writeFileSync(file, encodePng(sheet));
    meta.clips[clip] = frames.length;
    console.log(
      `${clip.padEnd(6)} ${String(frames.length).padStart(2)} frame  ` +
        `${sheet.width}x${sheet.height}  ${(fs.statSync(file).size / 1024).toFixed(0)} KB`,
    );
  }

  fs.writeFileSync(path.join(OUT, "atlas.json"), `${JSON.stringify(meta, null, 2)}\n`);

  /*
   * Tư thế ĐỨNG là tư thế duy nhất buộc phải có bàn chân trùng nhau tuyệt đối —
   * nó là thứ người xem nhìn lâu nhất, và một pixel nhấp nháy ở đó đọc ra thành
   * con thú rung chân. `check-petland-fit.mjs` kiểm đúng điều kiện này.
   */
  if (idleFeetRows.size !== 1) {
    console.error(
      `✗ bàn chân tư thế đứng nằm ở ${idleFeetRows.size} hàng khác nhau: ${[...idleFeetRows]}`,
    );
    process.exitCode = 1;
  }
  // +1 vì FOOT_Y là hàng MẶT ĐẤT, còn bbox trả về hàng cuối CÒN pixel.
  const footY = Math.max(...idleFeetRows) + 1;

  console.log(`\nô ${cellW}x${cellH} — đồng nhất cho mọi hoạt ảnh`);
  console.log(`chép vào petland-sprite.ts:  SHEET_BASE = "/mascots/${PET}"`);
  console.log(`                             CELL = { w: ${cellW}, h: ${cellH} }`);
  console.log(`                             FOOT_Y = ${footY}`);
  console.log(`                             ANCHOR_X = ${anchorX}`);
}

main();
