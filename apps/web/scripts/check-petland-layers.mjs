/**
 * Giữ đúng ranh giới giữa phần SẼ ĐỔI và phần KHÔNG ĐỔI của Petland.
 *
 *   node scripts/check-petland-layers.mjs
 *
 * Cách chia tệp chỉ có giá trị nếu nó được giữ, và nó không tự giữ được: thêm
 * một dòng `import` từ `petland-sprite` vào `petland-ui` thì mọi thứ vẫn chạy,
 * mọi bài kiểm vẫn xanh, và cái giá chỉ đến vào ngày ai đó đổi mascot — lúc đó
 * người sửa không có cách nào biết những tệp nào đã lặng lẽ dính vào nó.
 *
 * Cùng loại với `tests/test_content_isolation.py` bên API: một quy ước không
 * được kiểm là một quy ước sẽ hỏng.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Tệp → những thứ nó KHÔNG được nhập, kèm lý do in ra khi vi phạm. */
const RULES = [
  {
    file: "src/components/petland-ui.tsx",
    banned: ["petland-sprite", "petland-render", "petland-map", "petland.tsx", "pixi.js"],
    why: "giao diện tương tác phải sống sót qua việc đổi mascot và đổi bối cảnh",
  },
  {
    file: "src/components/petland-pet.ts",
    banned: ["petland-sprite", "petland-render", "petland-map", "petland-ui", "react", "pixi.js"],
    why: "nhu cầu và hành động là số học thuần, không dính ảnh và không dính React",
  },
  {
    file: "src/components/petland-map.ts",
    banned: ["petland-sprite", "petland-render", "petland-ui", "react", "pixi.js"],
    why: "lưới, va chạm và tìm đường phải kiểm được mà không cần trình duyệt",
  },
  {
    file: "src/components/petland-history.ts",
    banned: ["petland-render", "petland-ui", "react", "pixi.js"],
    why: "lịch sử sửa là số học thuần; nó chạy được ngoài React và đó là cách nó được kiểm",
  },
  {
    file: "src/components/petland-sprite.ts",
    banned: ["petland-render", "petland-map", "petland-ui", "petland-pet", "react", "pixi.js"],
    why: "mô tả loài là số đo thuần; biết tới bối cảnh thì đổi loài lại phải đọc cả bối cảnh",
  },
  {
    file: "src/components/pixel-icon.tsx",
    banned: ["petland"],
    why: "bộ biểu tượng dùng được ở bất cứ đâu, không riêng góc thú cưng",
  },
];

/*
 * Luật quan trọng nhất, và nó không nằm trong bảng trên vì nó nói theo chiều
 * ngược lại: **CHỈ `petland-render.ts` được nhập `pixi.js`**.
 *
 * Không có nó, sáu tháng nữa "đổi renderer" là một cuộc tìm kiếm toàn dự án — và
 * mỗi tệp lặng lẽ dính vào Pixi là một tệp phải đọc lại. Nó cũng giữ luôn con số
 * bundle: Pixi phải nằm trong đúng một chunk nạp lười, và một `import` thứ hai ở
 * chỗ khác kéo nó vào gói dùng chung mà không có gì báo (ADR-010 §15).
 */
const PIXI_OWNER = "src/components/petland-render.ts";

const IMPORT = /^\s*import[\s\S]*?from\s+["']([^"']+)["']/gm;

let bad = 0;
for (const rule of RULES) {
  const src = fs.readFileSync(path.join(root, rule.file), "utf8");
  const specifiers = [...src.matchAll(IMPORT)].map((m) => m[1]);
  const hits = specifiers.filter((spec) => rule.banned.some((b) => spec.includes(b)));
  if (hits.length > 0) {
    console.error(`✗ ${rule.file} nhập ${hits.join(", ")} — ${rule.why}`);
    bad += 1;
  } else {
    console.log(`  ${rule.file.replace("src/components/", "")} sạch (${specifiers.length} import)`);
  }
}

/* Chiều ngược lại: chỉ MỘT tệp được biết đường dẫn tới ảnh mascot, và chỉ một
   tệp được biết đường dẫn tới bức tranh. Rải chúng ra là thứ khiến việc thay đổi
   trở thành một cuộc đi tìm. */
const ASSETS = [
  { needle: "/mascots/", owners: ["src/components/petland-sprite.ts"], what: "ảnh mascot" },
  {
    needle: "/landscape/",
    owners: ["src/components/petland.tsx"],
    what: "bức tranh bối cảnh",
  },
];

/*
 * Quét cả `src/app`, không chỉ `src/components`.
 *
 * Bản trước chỉ đọc `src/components`, nên một đường dẫn ảnh viết thẳng trong một
 * `page.tsx` lọt qua mà không ai biết — đúng chỗ dễ viết nhất, vì trang mới thì
 * không ai nhớ tới luật này. `src/remotion` vào danh sách vì cùng lý do, ngay
 * khi thư mục đó bắt đầu vẽ cảnh Petland.
 */
const files = [];
for (const dir of ["src/components", "src/app", "src/remotion"]) {
  const stack = [path.join(root, dir)];
  while (stack.length > 0) {
    const at = stack.pop();
    for (const entry of fs.readdirSync(at, { withFileTypes: true })) {
      const full = path.join(at, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (/\.tsx?$/.test(entry.name)) files.push(path.relative(root, full));
    }
  }
}

for (const { needle, owners, what } of ASSETS) {
  const users = files.filter((f) => {
    const src = fs.readFileSync(path.join(root, f), "utf8");
    // Bỏ qua chú thích: nhắc tới đường dẫn trong lời giải thích là chuyện bình thường.
    return src
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "")
      .includes(needle);
  });
  const stray = users.filter((f) => !owners.includes(f));
  if (stray.length > 0) {
    console.error(
      `✗ ${what} (${needle}) bị tham chiếu ngoài ${owners.join(", ")}: ${stray.join(", ")}`,
    );
    bad += 1;
  } else {
    console.log(`  ${what} chỉ được ${owners.map((o) => path.basename(o)).join(" + ")} biết`);
  }
}

console.log("\n✓ ranh giới còn nguyên: đổi mascot hay đổi bối cảnh không lan sang giao diện");

// Quét toàn thư mục nguồn: luật ở trên chỉ soi những tệp được liệt kê, còn tệp
// MỚI thì không ai nhớ thêm vào bảng — mà đúng tệp mới mới là chỗ dễ nhập nhầm.
const roots = ["src/components", "src/app", "src/remotion"];
for (const dir of roots) {
  const stack = [path.join(root, dir)];
  while (stack.length > 0) {
    const at = stack.pop();
    for (const entry of fs.readdirSync(at, { withFileTypes: true })) {
      const full = path.join(at, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      if (!/\.(ts|tsx)$/.test(entry.name)) continue;
      const rel = path.relative(root, full);
      if (rel === PIXI_OWNER) continue;
      if (/from "pixi\.js"|import\("pixi\.js"\)/.test(fs.readFileSync(full, "utf8"))) {
        console.error(`✗ ${rel} nhập "pixi.js" — chỉ ${PIXI_OWNER} được phép.`);
        bad += 1;
      }
    }
  }
}

if (bad > 0) process.exit(1);
console.log("✓ chỉ petland-render.ts nhập pixi.js");
